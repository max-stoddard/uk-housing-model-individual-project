# Python Script Architecture and Maintenance Guide

## Purpose
`scripts/python` is the canonical home for Python calibration, validation, experiment, and helper code.

`src/main/resources` is reserved for model resources (CSV/config/supporting data) and must not become a Python code location again.

## Mandatory Maintenance Rule
If `scripts/python` structure or behavior contracts change (new/moved/removed modules, changed outputs, new env vars, CLI changes), this file must be updated in the same PR/commit set.

## Core Invariants
- Python executable code lives under `scripts/python`.
- Java/runtime data resources live under `src/main/resources`.
- Shell workflows remain the primary operator entrypoints under `scripts/was`.
- Refactors must preserve script behavior unless change is explicitly intentional and documented.
- Regression evidence is required for non-trivial behavior-affecting changes.

## Canonical Layout and Ownership
- `scripts/python/helpers/common`: cross-domain primitives (paths, formatting, properties, generic math)
- `scripts/python/helpers/was`: WAS-only reusable library
- `scripts/python/helpers/nmg`: NMG-only reusable library
- `scripts/python/calibration/was`: WAS calibration entry modules
- `scripts/python/calibration/nmg`: NMG calibration entry modules
- `scripts/python/calibration/legacy`: relocated legacy calibration scripts (min-change zone)
- `scripts/python/validation/was`: WAS validation entry modules
- `scripts/python/validation/legacy`: relocated legacy validation scripts (min-change zone)
- `scripts/python/experiments/was`: WAS comparison/experiment entry modules
- `scripts/python/experiments/nmg`: NMG experiment/search entry modules
- `scripts/python/tests/regression`: baseline vs refactor parity tooling

## Import and Layering Rules
- Entry modules can import helpers.
- Helpers may import only: standard library, same-domain helper modules, and `helpers/common`.
- Do not import across dataset domains (`helpers/was` <-> `helpers/nmg`) unless explicitly justified.
- Avoid entrypoint-to-entrypoint imports. If sharing is needed, move logic to helpers.
- Use package imports (`python3 -m ...` compatible), never `sys.path` hacks.

## Script Behavior Contracts
- Preserve existing CLI behavior by default.
- Additive flags are acceptable; breaking/removing flags requires explicit migration notes.
- Output defaults: calibration scripts write to current working directory unless `--output-dir` is provided.
- Output defaults: WAS experiments keep local `outputs/` behavior unless `--output-dir` is provided.
- New scripts that write files should expose `--output-dir` unless there is a strong reason not to.
- Keep generated filenames stable unless intentionally versioned.

## Runtime Configuration Contracts
WAS behavior is environment-driven via `scripts/python/helpers/was/config.py`.

Required/used env vars:
- `WAS_DATASET`: `W3` or `R8`
- `WAS_DATA_ROOT`
- `WAS_RESULTS_ROOT`
- `WAS_RESULTS_RUN_SUBDIR`

Do not reintroduce workflows that mutate Python source to switch datasets/results.

## Operational Entrypoints
Preferred operator commands:
- `scripts/was/run_was_calibration.sh`
- `scripts/was/run_was_validation.sh`
- `scripts/was/run_was_experiments.sh`

These should run from repo root and invoke Python modules (`python3 -m ...`).

## Regression and Acceptance Standard
For significant script refactors:
1. Run `scripts/python/tests/regression/run_regression.py` before removing legacy paths.
2. Compare schema, row counts, and numeric fields with tolerances `rtol=1e-9` and `atol=1e-12`.
3. Review `tmp/regression/report.json` and `tmp/regression/REPORT.md`.
4. Accept only when checks are PASS, or differences are explicitly documented as non-functional.

Note: regression artifacts under `tmp/` are evidence, not source code.

## Git Hygiene
- Do not commit generated caches or temporary outputs.
- Prefer committing harness code, not regression run artifacts.
- Keep refactors split into reviewable commits with clear scopes: helpers, entrypoint migrations, shell orchestration, cleanup/deletions.

## Legacy Zone Policy
`calibration/legacy` and `validation/legacy` are compatibility-focused.
- Keep minimal-touch changes unless there is a clear bug or migration requirement.
- Do not “modernize everything” in the same change as functional migration work.

## Change Checklist for Future Agents
Before finishing a Python-structure or behavior change:
1. Update this file for any structure/contract changes.
2. Verify module imports work with `python3 -m ...`.
3. Run relevant shell entrypoints.
4. Run regression harness when behavior parity is required.
5. Confirm no Python code remains/reappears in `src/main/resources`.
