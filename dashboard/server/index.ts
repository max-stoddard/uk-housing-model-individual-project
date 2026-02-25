import express from 'express';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { compareParameters, getInProgressVersions, getParameterCatalog, getVersions } from './lib/service';
import { buildZeroGitStats, getGitStats, type GitHubConfig } from './lib/gitStats';
import {
  deleteResultsRun,
  getResultsCompare,
  getResultsRunDetail,
  getResultsRunFiles,
  getResultsRuns,
  getResultsSeries
} from './lib/results';
import {
  cancelModelRunJob,
  clearModelRunJob,
  getModelRunJob,
  getModelRunJobLogs,
  getModelRunOptions,
  getResultsStorageSummary,
  listModelRunJobs,
  submitModelRun
} from './lib/modelRuns';
import { checkRuntimeDependencies } from './lib/runtimeDeps';
import { createWriteAuthControllerFromEnv, getWriteAuthConfigurationError, resolveDashboardWriteAccess } from './lib/writeAuth';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dashboardRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(dashboardRoot, '..');

const app = express();
const host = '0.0.0.0';
const port = Number.parseInt(process.env.PORT ?? process.env.DASHBOARD_API_PORT ?? '8787', 10);
const gitStatsBaseCommit = process.env.DASHBOARD_GIT_STATS_BASE_COMMIT ?? '4e89f5e277cdba4b4ef0c08254e5731e19bd51c3';
const corsOrigin = process.env.DASHBOARD_CORS_ORIGIN?.trim() ?? '';
const modelRunsConfigured = (process.env.DASHBOARD_ENABLE_MODEL_RUNS?.trim().toLowerCase() ?? '') === 'true';
const runtimeDependencies = checkRuntimeDependencies();
const runtimeDepsAvailable = runtimeDependencies.java.available && runtimeDependencies.maven.available;
const modelRunsEnabled = modelRunsConfigured && runtimeDepsAvailable;
const modelRunsDisabledReason =
  modelRunsConfigured && !runtimeDepsAvailable
    ? 'Model execution is unavailable because Java/Maven are missing in this API runtime. Deploy API with Docker runtime (Java+Maven) or install dependencies.'
    : 'Model execution is disabled in this environment.';
const writeAuth = createWriteAuthControllerFromEnv();
const writeAuthConfigurationError = getWriteAuthConfigurationError(writeAuth, modelRunsEnabled);

console.log(`[runtime-deps] java=${runtimeDependencies.java.available ? 'available' : 'missing'}`);
if (runtimeDependencies.java.versionOutput) {
  console.log(`[runtime-deps] java version: ${runtimeDependencies.java.versionOutput.split('\n')[0]}`);
}
if (runtimeDependencies.java.error) {
  console.error(`[runtime-deps] java error: ${runtimeDependencies.java.error}`);
}

console.log(
  `[runtime-deps] maven=${runtimeDependencies.maven.available ? 'available' : 'missing'} (bin=${runtimeDependencies.mavenBin})`
);
if (runtimeDependencies.maven.versionOutput) {
  console.log(`[runtime-deps] maven version: ${runtimeDependencies.maven.versionOutput.split('\n')[0]}`);
}
if (runtimeDependencies.maven.error) {
  console.error(`[runtime-deps] maven error: ${runtimeDependencies.maven.error}`);
}

if (modelRunsConfigured && !runtimeDepsAvailable) {
  console.error(
    '[dashboard-api] Model runs requested, but Java/Maven runtime dependencies are unavailable. ' +
      'API will remain online in read-only mode for model runs until dependencies are present.'
  );
}

const ghToken = process.env.DASHBOARD_GITHUB_TOKEN?.trim() ?? '';
const ghRepo = process.env.DASHBOARD_GITHUB_REPO?.trim() ?? '';
const ghBranch = process.env.DASHBOARD_GITHUB_BRANCH?.trim() || 'master';
const githubConfig: GitHubConfig | undefined =
  ghToken && ghRepo ? { token: ghToken, repo: ghRepo, branch: ghBranch } : undefined;

console.log(
  `[git-stats] config: token=${ghToken ? 'set' : 'MISSING'}, ` +
  `repo=${ghRepo || 'MISSING'}, branch=${ghBranch}, ` +
  `fallback=${githubConfig ? 'enabled' : 'DISABLED'}`
);

app.use(express.json());
app.use((req, res, next) => {
  if (!corsOrigin) {
    next();
    return;
  }

  const requestOrigin = req.get('origin');
  if (requestOrigin && requestOrigin === corsOrigin) {
    res.setHeader('Access-Control-Allow-Origin', corsOrigin);
    res.setHeader('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type,Authorization');
    res.setHeader('Vary', 'Origin');
  }

  if (req.method === 'OPTIONS') {
    res.status(204).end();
    return;
  }

  next();
});

app.get('/healthz', (_req, res) => {
  res.json({ ok: true });
});

app.get('/api/runtime-deps', (_req, res) => {
  const deps = checkRuntimeDependencies();
  res.json({
    java: deps.java.available,
    maven: deps.maven.available,
    mavenBin: deps.mavenBin,
    modelRunsConfigured,
    modelRunsEnabled: modelRunsConfigured && deps.java.available && deps.maven.available,
    versionInfo: {
      java: deps.java.versionOutput || null,
      maven: deps.maven.versionOutput || null,
      javaError: deps.java.error ?? null,
      mavenError: deps.maven.error ?? null
    }
  });
});

function requireWriteAccess(req: express.Request, res: express.Response): boolean {
  const access = resolveDashboardWriteAccess(writeAuth, req.get('authorization'), modelRunsEnabled);
  if (access.canWrite) {
    return true;
  }
  if (access.authMisconfigured) {
    res.status(503).json({
      error: writeAuthConfigurationError ?? 'Write access is unavailable due to server configuration.'
    });
    return false;
  }
  res.status(403).json({ error: 'Write access requires login.' });
  return false;
}

app.get('/api/auth/status', (req, res) => {
  const access = resolveDashboardWriteAccess(writeAuth, req.get('authorization'), modelRunsEnabled);
  res.json({
    authEnabled: access.authEnabled,
    canWrite: access.canWrite,
    authMisconfigured: access.authMisconfigured,
    modelRunsEnabled,
    modelRunsConfigured,
    modelRunsDisabledReason: modelRunsEnabled ? null : modelRunsDisabledReason
  });
});

app.post('/api/auth/login', (req, res) => {
  if (writeAuthConfigurationError) {
    res.status(503).json({ error: writeAuthConfigurationError });
    return;
  }

  const username = typeof req.body?.username === 'string' ? req.body.username : '';
  const password = typeof req.body?.password === 'string' ? req.body.password : '';
  const result = writeAuth.login(username, password);
  if (!result.ok) {
    res.status(401).json({ error: 'Invalid username or password.' });
    return;
  }
  res.json(result);
});

app.post('/api/auth/logout', (req, res) => {
  const access = resolveDashboardWriteAccess(writeAuth, req.get('authorization'), modelRunsEnabled);
  writeAuth.logout(access.token);
  res.json({ ok: true });
});

app.get('/api/versions', (_req, res) => {
  try {
    const versions = getVersions(repoRoot);
    const inProgressVersions = getInProgressVersions(repoRoot);
    res.json({ versions, inProgressVersions });
  } catch (error) {
    res.status(500).json({ error: (error as Error).message });
  }
});

app.get('/api/parameter-catalog', (_req, res) => {
  res.json({ items: getParameterCatalog() });
});

app.get('/api/git-stats', async (_req, res) => {
  try {
    const stats = await getGitStats({
      repoRoot,
      baseCommit: gitStatsBaseCommit,
      github: githubConfig
    });
    res.json(stats);
  } catch (error) {
    console.warn(`[dashboard-api] git stats unavailable: ${(error as Error).message}`);
    res.json(buildZeroGitStats(gitStatsBaseCommit));
  }
});

app.get('/api/compare', (req, res) => {
  const left = String(req.query.left ?? '');
  const right = String(req.query.right ?? '');
  const idsParam = String(req.query.ids ?? '');
  const provenanceScopeParam = String(req.query.provenanceScope ?? 'range');

  if (!left || !right) {
    res.status(400).json({ error: 'left and right query parameters are required' });
    return;
  }

  const ids = idsParam
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);

  const provenanceScope = provenanceScopeParam === 'through_right' ? 'through_right' : 'range';

  try {
    const payload = compareParameters(repoRoot, left, right, ids, provenanceScope);
    res.json(payload);
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.get('/api/results/runs', (_req, res) => {
  try {
    const runs = getResultsRuns(repoRoot);
    res.json({ runs });
  } catch (error) {
    res.status(500).json({ error: (error as Error).message });
  }
});

app.get('/api/results/storage', (_req, res) => {
  try {
    res.json(getResultsStorageSummary(repoRoot));
  } catch (error) {
    res.status(500).json({ error: (error as Error).message });
  }
});

app.get('/api/results/runs/:runId', (req, res) => {
  try {
    const detail = getResultsRunDetail(repoRoot, String(req.params.runId ?? ''));
    res.json(detail);
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.get('/api/results/runs/:runId/files', (req, res) => {
  try {
    const files = getResultsRunFiles(repoRoot, String(req.params.runId ?? ''));
    res.json({ runId: String(req.params.runId ?? ''), files });
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.delete('/api/results/runs/:runId', (req, res) => {
  if (!requireWriteAccess(req, res)) {
    return;
  }

  try {
    const payload = deleteResultsRun(repoRoot, String(req.params.runId ?? ''));
    res.json(payload);
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.get('/api/results/runs/:runId/series', (req, res) => {
  const runId = String(req.params.runId ?? '');
  const indicator = String(req.query.indicator ?? '');
  if (!indicator) {
    res.status(400).json({ error: 'indicator query parameter is required' });
    return;
  }

  const rawSmoothWindow = Number.parseInt(String(req.query.smoothWindow ?? '0'), 10);
  const smoothWindow = Number.isFinite(rawSmoothWindow) ? rawSmoothWindow : 0;

  try {
    const payload = getResultsSeries(repoRoot, runId, indicator, smoothWindow);
    res.json(payload);
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.get('/api/results/compare', (req, res) => {
  const runIds = String(req.query.runIds ?? '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
  const indicatorIds = String(req.query.indicatorIds ?? '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
  const window = String(req.query.window ?? 'post200');
  const rawSmoothWindow = Number.parseInt(String(req.query.smoothWindow ?? '0'), 10);
  const smoothWindow = Number.isFinite(rawSmoothWindow) ? rawSmoothWindow : 0;

  try {
    const payload = getResultsCompare(repoRoot, runIds, indicatorIds, window, smoothWindow);
    res.json(payload);
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.get('/api/model-runs/options', (req, res) => {
  try {
    const baseline = String(req.query.baseline ?? '').trim() || undefined;
    const payload = getModelRunOptions(repoRoot, baseline, modelRunsEnabled);
    res.json(payload);
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.post('/api/model-runs', (req, res) => {
  if (!modelRunsEnabled) {
    res.status(403).json({ error: modelRunsDisabledReason });
    return;
  }
  if (!requireWriteAccess(req, res)) {
    return;
  }

  try {
    const payload = submitModelRun(repoRoot, req.body);
    res.json(payload);
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.get('/api/model-runs/jobs', (_req, res) => {
  if (!modelRunsEnabled) {
    res.status(403).json({ error: modelRunsDisabledReason });
    return;
  }

  try {
    res.json({ jobs: listModelRunJobs() });
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.get('/api/model-runs/jobs/:jobId', (req, res) => {
  if (!modelRunsEnabled) {
    res.status(403).json({ error: modelRunsDisabledReason });
    return;
  }

  try {
    res.json(getModelRunJob(String(req.params.jobId ?? '')));
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.post('/api/model-runs/jobs/:jobId/cancel', (req, res) => {
  if (!modelRunsEnabled) {
    res.status(403).json({ error: modelRunsDisabledReason });
    return;
  }
  if (!requireWriteAccess(req, res)) {
    return;
  }

  try {
    res.json(cancelModelRunJob(repoRoot, String(req.params.jobId ?? '')));
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.delete('/api/model-runs/jobs/:jobId', (req, res) => {
  if (!modelRunsEnabled) {
    res.status(403).json({ error: modelRunsDisabledReason });
    return;
  }
  if (!requireWriteAccess(req, res)) {
    return;
  }

  try {
    res.json(clearModelRunJob(String(req.params.jobId ?? '')));
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.get('/api/model-runs/jobs/:jobId/logs', (req, res) => {
  if (!modelRunsEnabled) {
    res.status(403).json({ error: modelRunsDisabledReason });
    return;
  }

  const cursorRaw = Number.parseInt(String(req.query.cursor ?? '0'), 10);
  const limitRaw = Number.parseInt(String(req.query.limit ?? '200'), 10);

  try {
    const payload = getModelRunJobLogs(
      String(req.params.jobId ?? ''),
      Number.isFinite(cursorRaw) ? cursorRaw : undefined,
      Number.isFinite(limitRaw) ? limitRaw : undefined
    );
    res.json(payload);
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.listen(port, host, () => {
  console.log(`[dashboard-api] listening on ${host}:${port}`);
});
