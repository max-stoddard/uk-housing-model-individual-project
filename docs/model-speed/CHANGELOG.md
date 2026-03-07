# Model Speed Changelog
Author: Max Stoddard

This changelog is dedicated only to the model-speed improvement programme.

## Entry Format
- Date
- Phase or change label
- Scope
- Benchmark and regression impact
- Required follow-up

## 2026-03-07 - Phase 1 Scaffolding
- Froze the speed programme baseline at `input-data-versions/v4.1` with `r8` as the validation target.
- Defined the primary engineering metric as `seconds_per_household_month = wall_clock_seconds / (TARGET_POPULATION * N_STEPS * N_SIMS)`.
- Kept end-to-end `wall_clock_seconds` as the main user-facing guardrail metric.
- Set the first scale SLO to `TARGET_POPULATION = 100000` in `core-minimal-100k` with a target runtime under `60s` on the pinned WSL2 benchmark setup.
- Pinned the benchmark environment around WSL2 Ubuntu, OpenJDK 25, and Maven 3.8.7.
- Added snapshot-local benchmark, regression, and profiling harnesses under `scripts/model/`.
- Added tracked benchmark mode definitions under `scripts/model/configs/`.
- Added the `docs/model-speed/` documentation set, including this changelog, the canonical README, the local agent guide, and baseline-manifest storage.
- Established the rule that all future speed changes must pass strict regression before merge.

Regression policy from this point:
- exact single-thread work must remain bitwise exact
- tolerance-based regression is reserved for a later explicitly approved parallel track

Historical runtime context captured before fresh harness remeasurement:
- recent validation logs in `tmp/validation-refresh-20260214-210435/` show roughly `14s` to `16.5s` for the existing `10k / 2000-step / 1-sim` configuration
- existing `Results/v4.1-output` footprint is roughly `66 MB`

Required follow-up:
- collect the first fully measured multi-repeat benchmark set with the new harness
- refresh the tracked summary snapshot in `docs/model-speed/baselines/`
- begin hotspot ranking from JFR evidence rather than intuition

## 2026-03-07 - JFR Reporting Artifacts
- Extended `scripts/model/model_speed.py` with JFR execution-sample parsing, modelStep phase attribution, method-share reporting, and self-contained SVG flame graph rendering.
- Added checked-in profiling artifacts under `docs/model-speed/profiles/` for both existing median JFR recordings:
  - `core-minimal-10k-modelstep-flamegraph.svg`
  - `e2e-default-10k-modelstep-flamegraph.svg`
  - `JFR_METHOD_BREAKDOWN.md`
- Added machine-readable method-share companions for both profiles as JSON and CSV.
- Locked the current JFR validation counts into the report-generation flow:
  - core-minimal-10k `ExecutionSample` count `1363`, modelStep count `1355`
  - e2e-default-10k `ExecutionSample` count `1705`, modelStep count `1693`

Required follow-up:
- regenerate the checked-in profiling artifacts after any future benchmark/profile refresh
- compare new phase shares against the current household-loop, rental-market, and household-stats-heavy baseline before prioritising the next optimisation slice
