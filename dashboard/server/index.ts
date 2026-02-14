import express from 'express';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { compareParameters, getParameterCatalog, getVersions } from './lib/service';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dashboardRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(dashboardRoot, '..');

const app = express();
const port = Number.parseInt(process.env.DASHBOARD_API_PORT ?? '8787', 10);

app.use(express.json());

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

app.listen(port, '127.0.0.1', () => {
  console.log(`[dashboard-api] http://localhost:${port}`);
});
