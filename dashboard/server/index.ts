import express from 'express';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { compareParameters, getInProgressVersions, getParameterCatalog, getVersions } from './lib/service';
import { buildZeroGitStats, getGitStats, type GitHubConfig } from './lib/gitStats';
import {
  getResultsCompare,
  getResultsRunDetail,
  getResultsRunFiles,
  getResultsRuns,
  getResultsSeries
} from './lib/results';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dashboardRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(dashboardRoot, '..');

const app = express();
const host = '0.0.0.0';
const port = Number.parseInt(process.env.PORT ?? process.env.DASHBOARD_API_PORT ?? '8787', 10);
const gitStatsBaseCommit = process.env.DASHBOARD_GIT_STATS_BASE_COMMIT ?? '4e89f5e277cdba4b4ef0c08254e5731e19bd51c3';
const corsOrigin = process.env.DASHBOARD_CORS_ORIGIN?.trim() ?? '';

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
    res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
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
  const window = String(req.query.window ?? 'tail120');
  const rawSmoothWindow = Number.parseInt(String(req.query.smoothWindow ?? '0'), 10);
  const smoothWindow = Number.isFinite(rawSmoothWindow) ? rawSmoothWindow : 0;

  try {
    const payload = getResultsCompare(repoRoot, runIds, indicatorIds, window, smoothWindow);
    res.json(payload);
  } catch (error) {
    res.status(400).json({ error: (error as Error).message });
  }
});

app.listen(port, host, () => {
  console.log(`[dashboard-api] listening on ${host}:${port}`);
});
