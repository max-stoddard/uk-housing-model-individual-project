# Model Speed Programme
Author: Max Stoddard

## Purpose
This folder is the canonical planning and operational home for iterative model-speed work on the Java ABM in `src/main/java`.

The programme is intentionally performance-engineering-led:

1. Freeze a reproducible benchmark baseline.
2. Measure before changing anything.
3. Profile before choosing hotspots.
4. Optimise one hotspot family at a time.
5. Re-run strict regression checks after every accepted change.

No speed change is accepted on anecdote alone.

## Frozen Baseline
- Input snapshot: `input-data-versions/v4.1`
- Validation dataset target: `r8`
- Benchmark host assumption: WSL2 Ubuntu
- Runtime toolchain target: OpenJDK 25, Maven 3.8.7
- Primary optimisation goal: reduce single-run latency and improve scale-normalised throughput enough to make larger `TARGET_POPULATION` runs practical

Important:
- The speed harness is snapshot-local and does **not** mutate `src/main/resources`.
- This is deliberate because the repository often has active uncommitted resource edits.
- The legacy validation entrypoint `bash input-data-versions/validate.sh v4.1 r8 --no-graphs` still switches live resources and should therefore be run only from a clean or explicitly prepared worktree state.

## Metrics
Primary engineering metric:

```text
seconds_per_household_month = wall_clock_seconds / (TARGET_POPULATION * N_STEPS * N_SIMS)
```

Why this is primary:
- It normalises scale.
- It makes population-growth progress visible even when absolute runtime changes are noisy.
- It directly aligns with the programme goal of making larger `TARGET_POPULATION` runs practical.

Guardrail metric:
- `end-to-end wall_clock_seconds` for the whole model run, including JVM startup and output generation for the chosen benchmark mode

Supporting metrics:
- `model_computing_seconds` from the model’s own stdout
- `max_rss_kb`
- `user_cpu_seconds`
- `system_cpu_seconds`
- `output_bytes`
- `gc_pause_count`
- `gc_pause_time_ms_total`

## Scale SLO
First major scale SLO:
- `v4.1`
- `core-minimal-100k`
- `TARGET_POPULATION = 100000`
- practical runtime target: under `60s` on the pinned benchmark setup

This SLO is used to decide whether exact single-thread optimisation is sufficient or whether a later parallel track is justified.

## Benchmark Modes
Authoritative tracked mode definitions live under [`scripts/model/configs`](/home/max/dev/uni/project/models/uk-housing-model-individual-project/scripts/model/configs).

At runtime the harness materialises a full snapshot-local config copy under `tmp/model-speed/generated-configs/` by:
- loading `input-data-versions/v4.1/config.properties`
- rewriting resource paths to `input-data-versions/v4.1/...`
- applying the pinned mode overrides

Supported modes:
- `e2e-default-10k`: `v4.1` default output contract at `TARGET_POPULATION = 10000`
- `core-minimal-10k`: same economic model, recorder-heavy outputs disabled, `TARGET_POPULATION = 10000`
- `core-minimal-100k`: same minimal-output contract, `TARGET_POPULATION = 100000`

## Workflow
### 1. Benchmark First
Canonical benchmark command:

```bash
bash scripts/model/run-speed-benchmark.sh \
  --snapshot v4.1 \
  --mode e2e-default-10k \
  --repeat 5 \
  --output-root tmp/model-speed/benchmarks
```

What it does:
- compiles the Java project
- resolves a direct runtime classpath
- materialises a snapshot-local benchmark config
- runs one warm-up plus the requested measured repeats
- captures `/usr/bin/time -v`
- captures GC logs and a parsed GC summary
- hashes output files for every measured run
- emits a run TSV and aggregate summary JSON
- re-runs the median measured case with JFR enabled

For large-scale minimal benchmarking, enable the population ladder sanity check:

```bash
MODEL_SPEED_POPULATION_LADDER=1 \
bash scripts/model/run-speed-benchmark.sh \
  --snapshot v4.1 \
  --mode core-minimal-100k \
  --repeat 3 \
  --output-root tmp/model-speed/benchmarks
```

The ladder run records one measured pass each at `10k`, `25k`, `50k`, and `100k`.

### 2. Profile Second
Canonical JFR profile command:

```bash
bash scripts/model/profile-model.sh \
  --snapshot v4.1 \
  --mode core-minimal-10k \
  --profiler jfr \
  --output-root tmp/model-speed/profiles
```

Canonical `perf` command:

```bash
bash scripts/model/profile-model.sh \
  --snapshot v4.1 \
  --mode core-minimal-10k \
  --profiler perf \
  --output-root tmp/model-speed/profiles
```

Use JFR first. Only reach for `perf` if JFR does not make CPU or allocation hotspots clear enough on WSL.

Current checked-in profiling artifacts from the existing smoke recordings live under [`docs/model-speed/profiles`](/home/max/dev/uni/project/models/uk-housing-model-individual-project/docs/model-speed/profiles):
- `core-minimal-10k-modelstep-flamegraph.svg`
- `e2e-default-10k-modelstep-flamegraph.svg`
- `JFR_METHOD_BREAKDOWN.md`

These artifacts are generated from JFR `jdk.ExecutionSample` events and should be read as sample-share estimates, not exact per-method stopwatch timings.

### 3. Optimise In Narrow Slices
Default hotspot order unless profiling disproves it:
1. recorder and output overhead
2. whole-population collectors and recounts
3. repeated per-step allocations
4. repeated mortgage, tax, income, and wealth recomputation inside household flow
5. market queue and data-structure costs

Rules:
- one hotspot family per change
- one speed changelog entry per change
- one benchmark delta report per change
- stop reworking a subsystem once measured gains flatten

### 4. Regression Gate Every Change
Exact regression command:

```bash
bash scripts/model/run-speed-regression.sh \
  --snapshot v4.1 \
  --mode e2e-default-10k \
  --contract exact \
  --baseline-manifest docs/model-speed/baselines/v4.1-e2e-default-10k.exact.sha256 \
  --output-root tmp/model-speed/regressions
```

Future tolerance contract command shape:

```bash
bash scripts/model/run-speed-regression.sh \
  --snapshot v4.1 \
  --mode e2e-default-10k \
  --contract tolerance \
  --baseline-manifest path/to/tolerance-spec.json \
  --output-root tmp/model-speed/regressions
```

Current policy:
- single-thread speed work must remain bitwise exact
- tolerance-based regression is reserved for a later explicitly approved parallel track

## Acceptance Criteria
Every accepted speed change must pass:
- `mvn -q -DskipTests compile`
- exact deterministic regression on `v4.1 / e2e-default-10k`
- full benchmark rerun on the three fixed benchmark modes
- `bash input-data-versions/validate.sh v4.1 r8 --no-graphs`

Exact means:
- same output file set
- same byte content
- same file hashes

The benchmark delta report for each accepted speed change must show:
- primary metric delta
- wall-clock delta
- RSS delta
- GC delta
- output-volume delta

## Tracked Baselines
Tracked baseline manifests and summary snapshots live in [`docs/model-speed/baselines`](/home/max/dev/uni/project/models/uk-housing-model-individual-project/docs/model-speed/baselines).

Rules:
- only tracked manifests and summary snapshots belong there
- raw run outputs belong in `tmp/model-speed/`
- generated configs belong in `tmp/model-speed/generated-configs/`
- `Results/` is not the canonical home for speed-regression baselines

## Parallelisation Policy
Parallel work is intentionally deferred.

Open a separate parallel track only if:
- exact single-thread work has plateaued
- the `100k < 60s` SLO is still not met
- the regression contract for the new track is explicitly written down first

Preferred order if that track opens:
1. outer-loop parallelism (`N_SIMS`, seed batches, sweeps)
2. only then consider intra-run parallelism

The exact single-thread path remains the canonical reference even after any future parallel track begins.
