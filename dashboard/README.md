# UK Housing Model Dashboard
Author: Max Stoddard

Local React dashboard for visualizing `input-data-versions/` model parameters, with optional version comparison and provenance tracking.

## Run

From repository root:

```bash
./run-dashboard.sh
```

## Useful commands

```bash
cd dashboard
npm run lint
npm run build
npm run test:smoke
npm run start:server
```

## Production Runtime

The frontend can call either same-origin API routes or an external API base URL.

- `VITE_API_BASE_URL` (optional): absolute API origin, for example `https://uk-housing-market-abm-api.onrender.com`
  - if unset, frontend calls relative `/api/*` paths.

Dashboard API environment variables:

- `PORT` (preferred in production): HTTP port.
- `DASHBOARD_API_PORT` (local fallback): HTTP port when `PORT` is not set.
- `DASHBOARD_CORS_ORIGIN` (optional): allowed browser origin for cross-origin requests (for split frontend/API deploys).
- `DASHBOARD_GIT_STATS_BASE_COMMIT` (optional): git base commit used by `/api/git-stats`.
- `DASHBOARD_ENABLE_MODEL_RUNS` (optional): set to `true` to enable model-run APIs/UI.
- `DASHBOARD_WRITE_USERNAME` + `DASHBOARD_WRITE_PASSWORD` (optional pair): enables write-login mode when both are set.
- `DASHBOARD_MAVEN_BIN` (optional): Maven executable used by model runs (defaults to `mvn`).

Write-access behavior:

- If `DASHBOARD_WRITE_USERNAME` and `DASHBOARD_WRITE_PASSWORD` are both unset:
  - auth is disabled,
  - local development can use write features without login.
- If both are set:
  - dashboard write actions require login (single global username/password),
  - read-only pages remain available without login.
- If model runs are enabled (`DASHBOARD_ENABLE_MODEL_RUNS=true`) but credentials are unset:
  - API enters fail-closed mode for write actions (`503`),
  - login is intentionally disabled until credentials are configured,
  - read-only pages remain available.

Write actions requiring login in auth-enabled mode:

- queue model runs
- cancel model runs
- clear finished jobs from queue history
- delete runs from Model Results

### Local Auth Setup

Default local workflow (no login):

```bash
cd dashboard
npm run dev
```

Optional local auth testing (login required):

```bash
cd dashboard
export DASHBOARD_ENABLE_MODEL_RUNS=true
export DASHBOARD_WRITE_USERNAME=admin
export DASHBOARD_WRITE_PASSWORD=change-me
npm run dev
```

Then open `/login` in the web app and sign in with that username/password.

Health endpoint:

- `GET /healthz`
- `GET /api/runtime-deps` (runtime diagnostics):
  - returns `java`, `maven`, `mavenBin`, and `versionInfo` for dependency checks.

`/api/git-stats` behavior:

- uses local git endpoint-diff semantics (`git diff --shortstat` + `git rev-list`) from base commit to `HEAD`
- weekly stats use the same local git semantics over the rolling 7-day window
- if local git stats fail in runtime, API returns a safe zero-valued payload so homepage rendering remains stable
- response includes `weekly` metrics for rolling last 7 days:
  - `weekly.filesChanged`
  - `weekly.lineChanges`
  - `weekly.commitCount`

Expected parity check: `/api/git-stats` should match `./scripts/helpers/git-stats.sh` on the same branch and `HEAD`.

## Render Deployment

Repository root includes `render.yaml` with:

- static web service: `uk-housing-market-abm`
- API web service: `uk-housing-market-abm-api` (Docker runtime with Java + Maven)

Remote model runs require Java and Maven in the API runtime. The Blueprint now uses Docker for the API service to provide both dependencies.

- Dockerfile: `dashboard/Dockerfile.api`
- API runtime dependency diagnostics: `GET /api/runtime-deps`

If you deploy API as plain `runtime: node` without Java/Maven, run submission will fail with `spawn mvn ENOENT`. In that case either:

- migrate to Docker runtime (recommended), or
- disable remote execution (`DASHBOARD_ENABLE_MODEL_RUNS=false`) and keep read-only usage.

Current server behavior when `DASHBOARD_ENABLE_MODEL_RUNS=true` but Java/Maven are missing:

- API does **not** crash on startup
- `/api/runtime-deps` reports missing dependencies
- model-run endpoints return disabled errors until dependencies are available

For remote write-login mode, configure these API environment variables in Render:

- `DASHBOARD_ENABLE_MODEL_RUNS=true` (blueprint default is `true`)
- `DASHBOARD_WRITE_USERNAME` (secret)
- `DASHBOARD_WRITE_PASSWORD` (secret)

Deploys are configured from `master` and gated by passing GitHub checks.

If Render stops showing commit events (for example, "No event for this commit"), first re-link the service repository in Render to the current GitHub repo identity (`max-stoddard/UK-Housing-Market-ABM`) and re-sync the Blueprint.

Optional resilience fallback:

- add `RENDER_STATIC_DEPLOY_HOOK` and `RENDER_API_DEPLOY_HOOK` as GitHub repository secrets
- `.github/workflows/dashboard-ci.yml` will call these hooks after checks pass on `master`, only when matching service paths changed
