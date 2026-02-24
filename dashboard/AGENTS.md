# Dashboard Agent Guide
Author: Max Stoddard

## Purpose
`dashboard/` is the local web UI for comparing versioned model input parameters in `input-data-versions/`.

This guide is for future agents working only in the dashboard stack. Keep it short, accurate, and update it when dashboard structure or contracts change.

## Living File Requirement
- Treat this file as a living operational guide, not static documentation.
- If you change dashboard behavior, API contracts, workflow commands, page structure, or parameter/provenance semantics, update this file in the same change.
- Add concise "good to know" notes when you discover recurring pitfalls, edge cases, or debugging shortcuts that will help future tasks.
- Do not defer these updates to a later commit.

## Fast Orientation
- `dashboard/src`: React frontend (routes, pages, components, styles).
- `dashboard/public`: Static frontend assets served directly by Vite (for example favicon files).
- `dashboard/src/pages/HomePage.tsx`: Landing page.
- `dashboard/src/pages/ComparePage.tsx`: Main comparison workspace.
- `dashboard/src/components/CompareCard.tsx`: Format-specific rendering logic for comparison cards.
- `dashboard/src/components/EChart.tsx`: ECharts wrapper with `ResizeObserver`-based container resizing.
- `dashboard/src/lib/api.ts`: Frontend API calls.
- `dashboard/src/lib/compareChartOptions.ts`: Shared ECharts option builders reused by homepage previews and compare cards.
- `dashboard/src/lib/chartAxes.ts`: Canonical axis-title/unit mapping for all charted parameter cards.
- `dashboard/server`: Express API server.
- `dashboard/server/index.ts`: API route registration (`/healthz`, `/api/versions`, `/api/parameter-catalog`, `/api/git-stats`, `/api/compare`).
- `dashboard/server/lib/service.ts`: Comparison engine and payload builders.
- `dashboard/server/lib/io.ts`: Config/CSV parsing helpers.
- `dashboard/server/lib/versioning.ts`: Version discovery and semantic ordering.
- `dashboard/server/lib/versionNotes.ts`: Structured version-notes loader/validator used for provenance metadata.
- `dashboard/shared/types.ts`: Shared API payload and visualization types.
- `dashboard/shared/catalog.ts`: Canonical parameter-card catalog and curated explanations.
- `dashboard/tests/smoke.test.ts`: Smoke test for catalog/version/compare behavior.
- `run-dashboard.sh` (repo root): canonical local startup command.

## Runtime Contract
- API endpoints:
  - `GET /healthz`
  - `GET /api/versions` returning `{ versions: string[]; inProgressVersions: string[] }`
  - `GET /api/parameter-catalog`
  - `GET /api/git-stats`
  - `GET /api/compare?left=<version>&right=<version>&ids=<csv>&provenanceScope=range|through_right`
- Frontend API base URL behavior:
  - if `VITE_API_BASE_URL` is set, frontend calls `${VITE_API_BASE_URL}/api/*`.
  - if unset, frontend calls relative `/api/*` (same-origin).
- Favicon behavior:
  - production uses `/favicon.svg` (white house icon).
  - local development uses `/favicon-dev.svg` (orange house icon) via `import.meta.env.DEV` in `src/main.tsx`.
- Header environment tag behavior:
  - local development renders an orange `Dev` pill next to the `UK Housing Market ABM` title via `import.meta.env.DEV` in `src/App.tsx`.
  - local development also renders an orange `Preview non-dev` toggle next to that title; this toggle hides dev-only UI while remaining available so developers can switch back.
- Homepage git-stats visibility behavior:
  - `Lines Written`, `Files Changed`, and `Commits` cards are hidden in production.
  - in local development only, these cards render with an orange `Dev only` pill and a red `To fix` pill.
  - when dev features are disabled (production or local `Preview non-dev` mode), homepage does not call `/api/git-stats`.
  - latest snapshot card displays a red `In progress` pill when the latest version is in `/api/versions.inProgressVersions`.
  - homepage load retries automatically every 2 seconds when API requests fail with retryable errors, showing a waiting banner until data is available.
- Dev-only page visibility behavior:
  - `Run Model` and `Experiments` navigation entries and routes are dev-only.
  - when previewing non-dev in local development, those entries/routes are hidden and direct route access redirects to `/`.
- Compare setup panel behavior:
  - when open, setup collapse control is a compact icon button in the setup header.
  - when closed, setup restore control is a compact top-left icon button (not a full rail label).
  - version selectors append `(In progress)` for versions in `/api/versions.inProgressVersions`.
  - results header displays red `In progress` pills for selected in-progress versions.
  - compare-card graph legends/tooltips/titles append `(In progress)` to in-progress version labels.
  - compare cards with `changeOriginsInRange` containing `validationStatus=in_progress` display a red `In progress` status pill.
  - compare bootstrapping and parameter fetches auto-retry every 2 seconds on retryable API errors, showing a waiting banner until API responses recover.
- API runtime env precedence:
  - port: `PORT` first, fallback `DASHBOARD_API_PORT`, fallback `8787`.
  - CORS allowlist (optional): `DASHBOARD_CORS_ORIGIN`.
  - git-stats base commit (optional): `DASHBOARD_GIT_STATS_BASE_COMMIT`.
- `/api/git-stats` resolution order:
  - local git endpoint-diff metrics from base commit to `HEAD` (`git diff --shortstat` + `git rev-list`).
  - if local git stats fail, return zero-valued stats payload to keep homepage stable.
  - payload includes `weekly` rolling 7-day activity stats (`filesChanged`, `lineChanges`, `commitCount`).
  - metrics semantics match `scripts/helpers/git-stats.sh` when run on the same branch and `HEAD`.
- The dashboard currently compares only the parameter groups explicitly listed in `dashboard/shared/catalog.ts`.
  - Current compare taxonomy: `Household Demographics & Wealth`, `Government & Tax`, `Housing & Rental Market`, `Purchase & Mortgage`, `Bank & Credit Policy`, `BTL & Investor Behavior`.
- Catalog coverage now includes non-user-set calibrated scalar and file-backed sources from `config.properties` (including sale/rent initial mark-up distributions and bank credit-policy calibration keys).
- Reduction dynamics coverage is split into one shared probability card (`P_SALE_PRICE_REDUCE`, `P_RENT_PRICE_REDUCE`) plus separate Gaussian cards for sale and rent reduction-size parameters (`*_MU`, `*_SIGMA`).
- HPA expectation parameters are visualized as the expected-change equation line (`factor * trend + const`, with `DT=1`) across a fixed trend domain.
- Version selector source of truth is folder snapshots under `input-data-versions/` (filtered and sorted by `server/lib/versioning.ts`).
- Structured version metadata source of truth is `input-data-versions/version-notes.json`.
- `inProgressVersions` in `/api/versions` is derived from `version-notes.json` entries with `validation.status = in_progress` grouped by `snapshot_folder`.
- Compare response items include `changeOriginsInRange` provenance entries derived from `version-notes.json`.
- Compare provenance origins intentionally exclude `validationDataset`; validation-dataset tracking remains only in `version-notes.json`.
- Compare provenance origins include `parameterChanges`, where each item has `configParameter` and nullable `datasetSource`.
- Compare response `sourceInfo` includes version-aware dataset attribution arrays `datasetsLeft` and `datasetsRight`, each item carrying `tag`, `fullName`, `year`, optional `edition`, and optional `evidence`.
- Provenance scope semantics:
  - `range`: include updates in `(left, right]` (compare mode).
  - `through_right`: include full history through `right` (single-version mode history tracking).
- Every version-notes entry must include `method_variations` (empty array allowed); compare payload origins include filtered `methodVariations`.
- Every version-notes entry must include `parameter_changes` (empty array allowed), and `parameter_changes[].config_parameter` must match `config_parameters` as a set.
- Source-section labels are mode-specific by design: single mode renders only `Source`, compare mode renders `Left source` and `Right source`.

## Best Practices
- Keep `shared/types.ts` and backend response shapes synchronized before changing UI rendering.
- Keep `/api/git-stats` resilient in deployed environments where git metadata may be shallow or unavailable; zero fallback payloads must keep homepage rendering intact.
- Keep `/api/git-stats` response shape stable while preserving local endpoint-diff semantics.
- Add or change compare cards only through `shared/catalog.ts`; avoid hardcoding IDs in UI components.
- Keep calibrated-input coverage broad and explicit: when adding newly tracked calibrated sources, prefer extending existing card formats (`scalar`, `scalar_pair`, `binned_distribution`, etc.) rather than introducing custom one-off render paths.
- Prefer extending `server/lib/service.ts` with clear, format-specific helpers rather than one large branching block.
- Keep step-rate handling for `national_insurance_rates` and `income_tax_rates` as piecewise-threshold logic (not mass rebinning).
- Keep page mode semantics stable:
  - default `single` mode renders the latest non-`in_progress` version (falling back to latest when all are in progress) and provenance `through_right`.
  - optional `compare` mode renders left/right delta with provenance `range`.
- When adding a new visualization format, do all three:
  - add type in `shared/types.ts`
  - produce payload in `server/lib/service.ts`
  - render it in `src/components/CompareCard.tsx`
- Axis titles and units are mandatory:
  - every chart must include explicit x-axis and y-axis titles with units (`£`, `£/year`, `years`, `(-)`, `1/£`, etc.).
  - generic placeholders like `native units` are forbidden.
  - axis metadata must be centralized in `src/lib/chartAxes.ts`; when adding/changing parameter cards, update that file in the same change.
  - if axis metadata changes, update smoke tests that validate axis-spec completeness.
- Good to know for joint heatmaps:
  - use built-in interactive ECharts `visualMap` on the right side (`orient: vertical`, `calculable: true`) for consistent draggable keys.
  - avoid replacing it with custom non-interactive `graphic` legends unless explicitly requested.
  - use adaptive heatmap margin solving from label/title geometry (not fixed large `gridLeft`/`gridBottom` constants) to maximize heatmap body area.
  - compare-mode heatmaps should use explicit grid layout (`containLabel: false`, `outerBoundsMode: none`) to prevent auto-shifting from long labels.
  - compare-mode should keep `old`, `new`, and `delta` heatmaps side-by-side in one row; allow horizontal scroll when viewport width is constrained.
- Maintain concise, practical explanations in catalog metadata (meaning + likely directional effect).
- Keep charts readable first (labels, units, deltas); avoid adding decorative complexity that obscures comparisons.

## Development Commands
From `dashboard/`:

```bash
npm run lint
npm run build
npm run test:smoke
npm run start:server
```

From repo root:

```bash
./run-dashboard.sh
```

Deployment workflow-critical files live at repository root:

- `render.yaml`: Render Blueprint for static web + API web services.
- `.github/workflows/dashboard-ci.yml`: deploy-gating CI workflow for dashboard checks plus optional Render deploy-hook fallback on `master` pushes.
- Optional GitHub secrets for fallback triggers: `RENDER_STATIC_DEPLOY_HOOK`, `RENDER_API_DEPLOY_HOOK`.

## Guardrails
- Do not read private datasets directly for dashboard work unless specifically required and approved.
- Do not commit generated artifacts (`dist/`, `.smoke-dist/`, `node_modules/`).
- If you change dashboard structure, API contracts, or command workflow, update this file in the same change.
