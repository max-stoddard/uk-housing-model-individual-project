# Project Agent Guide

## Mission + Scope
This repository contains an agent-based model of the UK housing market. Java in `src/main/java` provides the model core, and Python in `scripts/python` provides calibration, validation, and experiment workflows.

This guide is the fast-start context for future agents and contributors working in this repo. Use it to orient quickly and avoid structural mistakes.
If Python-script context is needed, read the instructions in [`scripts/python/AGENT_SCRIPT_STRUCTURE.md`](scripts/python/AGENT_SCRIPT_STRUCTURE.md).

## Agent Requirements
- Treat this file and linked agent docs as living operational guidance. If any instruction is incorrect, outdated, or missing for the task at hand, update it in the same change.
- If project structure changes (new/moved/removed top-level or workflow-critical paths), update this `AGENTS.md` in the same change.
- If Python script architecture or behavior contracts change, update `scripts/python/AGENT_SCRIPT_STRUCTURE.md` in the same change.
- When creating a new source/documentation file, include Max Stoddard as the author in file header/front matter where that project convention exists.
- Do not read any csv files under `private-datasets/` directly. If needed for a task, only read the first 10 lines to avoid exceeding your context window or ask the user for the structure/schema or a safe summary of required fields first.
- For long independent experiment/calibration sweeps, prefer deterministic sharded execution with `gnu parallel` to reduce wall-clock time in Codex runs. Current workstation default is `16` workers unless constrained by the task.

## Git Commit Best Practices
- Use subject format exactly: `<type> [MS]: <description>`.
- Allowed types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
- Description must state both what changed and why it changed.
- Keep one logical concern per commit.
- Run relevant checks before committing dashboard changes: `npm run lint`, `npm run build`, `npm run test:smoke` (from `dashboard/`).
- Do not commit generated artifacts (`dashboard/node_modules`, `dashboard/dist`, `dashboard/.smoke-dist`, `Results`, `tmp`).
- AGENTS files are ignore-matched by default; when intentionally changed, stage explicitly with `git add -f`.

## Fast Orientation
- `dashboard`: React + TypeScript local web dashboard for input-data comparison.
- `dashboard/server`: Node API layer serving version/catalog/compare endpoints for the dashboard.
- `dashboard/shared`: Shared TypeScript types and parameter catalog metadata.
- `dashboard/AGENTS.md`: Folder-scoped dashboard guide for structure, API contracts, and agent best practices.
- `run-dashboard.sh`: Root entrypoint to install/start dashboard API + frontend locally.
- `render.yaml`: Render Blueprint for deploying dashboard static site + API service from this monorepo.
- `.github/workflows/dashboard-ci.yml`: GitHub Actions deployment gate for dashboard lint/build/smoke checks, with optional Render deploy-hook fallback on `master` pushes.
- `src/main/java`: Java model implementation (core simulation code).
- `scripts/python`: Python calibration/validation/experiments and helper modules.
- `scripts/python/calibration/ppd`: PPD house-price calibration entry modules.
- `scripts/python/calibration/legacy/total_wealth_dist.py`: legacy WAS total-wealth calibration script (relocated from non-legacy calibration).
- `scripts/python/helpers/ppd`: PPD helper modules shared by calibration/experiments.
- `scripts/python/experiments/ppd`: PPD method-search and reproduction experiments.
- `scripts/python/experiments/was/personal_allowance.py`: WAS personal-allowance experiment entrypoint (single vs double allowance fit diagnostic).
- `scripts/python/calibration/ppd/house_price_lognormal_fit.py`: method-selectable PPD calibration entrypoint (`--method`).
- `scripts/python/calibration/CALIBRATION_PARAMETER_CHANGELOG.md`: canonical calibration provenance ledger (commands, method rationale, and evidence links across versions).
- `scripts/python/AGENTS_WAS_VALIDATION_EXPERIMENT_FINDINGS.md`: consolidated findings and reproducible evidence for WAS validation behavior and `v3.x` housing-wealth error diagnostics.
- `scripts/was`: Shell entrypoints that orchestrate key WAS Python workflows.
- `scripts/psd`: Shell entrypoints that orchestrate PSD experiment/calibration workflows.
- `src/main/resources`: Model resources and data files used at runtime.
- `input-data-versions`: Versioned input-data snapshots.
- `input-data-versions/AGENTS.md`: Folder-scoped guide for snapshot structure, switching, validation, and best practices.
- `input-data-versions/validate.sh`: Generic validation entrypoint (`<subfolder> <w3|r8> [--graphs|--no-graphs]`).
- `private-datasets`: Private source datasets (not for public commit).
- `Results`: Generated outputs from runs/experiments.
- `tmp`: Temporary and regression artifacts.

## Legacy Document Context
- `docs/OldDocs/2016 Feb - Model Equations and Stats.pdf`: historical model mechanics reference for mortgage approval and downpayment behavior; useful for interpreting why downpayment parameters are lognormal and split by borrower type.
- `docs/OldDocs/2022 March - Original Model Improvements.pdf`: policy/validation context for PSD-era owner-occupier mortgage metrics; explicitly aligns internal hard LTI limits (HM `5.6`, FTB `5.4`) and PSD 2011 framing used by experiments.
- Treat both PDFs as context documents: they support interpretation and rationale but do not replace data-driven reproduction from PSD tables.
