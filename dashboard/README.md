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

Health endpoint:

- `GET /healthz`

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
- API web service: `uk-housing-market-abm-api`

Deploys are configured from `master` and gated by passing GitHub checks.

If Render stops showing commit events (for example, "No event for this commit"), first re-link the service repository in Render to the current GitHub repo identity (`max-stoddard/UK-Housing-Market-ABM`) and re-sync the Blueprint.

Optional resilience fallback:

- add `RENDER_STATIC_DEPLOY_HOOK` and `RENDER_API_DEPLOY_HOOK` as GitHub repository secrets
- `.github/workflows/dashboard-ci.yml` will call these hooks after checks pass on `master`, only when matching service paths changed
