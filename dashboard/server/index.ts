import express from 'express';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { compareParameters, getParameterCatalog, getVersions } from './lib/service';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dashboardRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(dashboardRoot, '..');

const app = express();
const host = '0.0.0.0';
const port = Number.parseInt(process.env.PORT ?? process.env.DASHBOARD_API_PORT ?? '8787', 10);
const gitStatsBaseCommit = process.env.DASHBOARD_GIT_STATS_BASE_COMMIT ?? '4e89f5e277cdba4b4ef0c08254e5731e19bd51c3';
const corsOrigin = process.env.DASHBOARD_CORS_ORIGIN?.trim() ?? '';

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

function parseShortStat(output: string) {
  const files = Number(output.match(/(\d+)\s+files?\s+changed/)?.[1] ?? 0);
  const insertions = Number(output.match(/(\d+)\s+insertions?\(\+\)/)?.[1] ?? 0);
  const deletions = Number(output.match(/(\d+)\s+deletions?\(-\)/)?.[1] ?? 0);
  return {
    filesChanged: files,
    insertions,
    deletions,
    lineChanges: insertions + deletions
  };
}

app.get('/healthz', (_req, res) => {
  res.json({ ok: true });
});

app.get('/api/versions', (_req, res) => {
  try {
    const versions = getVersions(repoRoot);
    res.json({ versions });
  } catch (error) {
    res.status(500).json({ error: (error as Error).message });
  }
});

app.get('/api/parameter-catalog', (_req, res) => {
  res.json({ items: getParameterCatalog() });
});

app.get('/api/git-stats', (_req, res) => {
  try {
    const shortStat = execFileSync('git', ['diff', '--shortstat', gitStatsBaseCommit], {
      cwd: repoRoot,
      encoding: 'utf-8'
    }).trim();
    const commitCount = Number(
      execFileSync('git', ['rev-list', '--count', `${gitStatsBaseCommit}..HEAD`], {
        cwd: repoRoot,
        encoding: 'utf-8'
      }).trim()
    );

    res.json({
      baseCommit: gitStatsBaseCommit,
      ...parseShortStat(shortStat),
      commitCount: Number.isFinite(commitCount) ? commitCount : 0
    });
  } catch (error) {
    console.warn(`[dashboard-api] git stats fallback enabled: ${(error as Error).message}`);
    res.json({
      baseCommit: gitStatsBaseCommit,
      filesChanged: 0,
      insertions: 0,
      deletions: 0,
      lineChanges: 0,
      commitCount: 0
    });
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

app.listen(port, host, () => {
  console.log(`[dashboard-api] listening on ${host}:${port}`);
});
