# Dashboard Agent Guide
Author: Max Stoddard

## Purpose
`dashboard/` is the local web UI for comparing versioned model input parameters in `input-data-versions/`.

This guide is for future agents working only in the dashboard stack. Keep it short, accurate, and update it when dashboard structure or contracts change.

## Fast Orientation
- `dashboard/src`: React frontend (routes, pages, components, styles).
- `dashboard/src/pages/HomePage.tsx`: Landing page.
- `dashboard/src/pages/ComparePage.tsx`: Main comparison workspace.
- `dashboard/src/components/CompareCard.tsx`: Format-specific rendering logic for comparison cards.
- `dashboard/src/components/EChart.tsx`: ECharts wrapper.
- `dashboard/src/lib/api.ts`: Frontend API calls.
- `dashboard/server`: Express API server.
- `dashboard/server/index.ts`: API route registration (`/api/versions`, `/api/parameter-catalog`, `/api/compare`).
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
  - `GET /api/versions`
  - `GET /api/parameter-catalog`
  - `GET /api/compare?left=<version>&right=<version>&ids=<csv>&provenanceScope=range|through_right`
- The dashboard currently compares only the parameter groups explicitly listed in `dashboard/shared/catalog.ts`.
- Version selector source of truth is folder snapshots under `input-data-versions/` (filtered and sorted by `server/lib/versioning.ts`).
- Structured version metadata source of truth is `input-data-versions/version-notes.json`.
- Compare response items include `changeOriginsInRange` provenance entries derived from `version-notes.json`.
- Provenance scope semantics:
  - `range`: include updates in `(left, right]` (compare mode).
  - `through_right`: include full history through `right` (single-version mode history tracking).
- Every version-notes entry must include `method_variations` (empty array allowed); compare payload origins include filtered `methodVariations`.

## Best Practices
- Keep `shared/types.ts` and backend response shapes synchronized before changing UI rendering.
- Add or change compare cards only through `shared/catalog.ts`; avoid hardcoding IDs in UI components.
- Prefer extending `server/lib/service.ts` with clear, format-specific helpers rather than one large branching block.
- Keep step-rate handling for `national_insurance_rates` and `income_tax_rates` as piecewise-threshold logic (not mass rebinning).
- Keep page mode semantics stable:
  - default `single` mode renders latest version and provenance `through_right`.
  - optional `compare` mode renders left/right delta with provenance `range`.
- When adding a new visualization format, do all three:
  - add type in `shared/types.ts`
  - produce payload in `server/lib/service.ts`
  - render it in `src/components/CompareCard.tsx`
- Maintain concise, practical explanations in catalog metadata (meaning + likely directional effect).
- Keep charts readable first (labels, units, deltas); avoid adding decorative complexity that obscures comparisons.

## Development Commands
From `dashboard/`:

```bash
npm run lint
npm run build
npm run test:smoke
```

From repo root:

```bash
./run-dashboard.sh
```

## Guardrails
- Do not read private datasets directly for dashboard work unless specifically required and approved.
- Do not commit generated artifacts (`dist/`, `.smoke-dist/`, `node_modules/`).
- If you change dashboard structure, API contracts, or command workflow, update this file in the same change.
