#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../helpers/log.sh"
LOG_TAG="DEMO"
LOG_COLOR="\033[1;31m"
log_init

repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

demo_newline() { printf '\n'; }

pause() {
  demo_newline
  printf '%s %s' "$(log_prefix)" "Press any key (or Enter) to continue..."
  read -r -n 1 -s
  demo_newline
  demo_newline
}

log "=== Part 1/3: v0 parameters + Wave 3 validation ==="
bash scripts/demos/run-validation-step.sh \
  "v0" \
  "Results/v0-output" \
  "WAVE_3_DATA" \
  "W3" \
  "private-datasets/was/was_wave_3_hhold_eul_final.dta"

pause

log "=== Part 2/3: Experiments (GUI enabled) ==="
./scripts/was/run_was_experiments.sh true

pause

log "=== Part 3/3: v1 parameters + Round 8 validation ==="
bash scripts/demos/run-validation-step.sh \
  "v1" \
  "Results/v1-output" \
  "ROUND_8_DATA" \
  "R8" \
  "private-datasets/was/was_round_8_hhold_eul_may_2025.privdata"
