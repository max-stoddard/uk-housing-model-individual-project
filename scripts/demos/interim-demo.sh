#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_root}"

pause() {
  echo
  read -r -n 1 -s -p "Press any key (or Enter) to continue..."
  echo
  echo
}

echo "=== Part 1/3: v0 parameters + Wave 3 validation ==="
bash scripts/demos/run-validation-step.sh \
  "v0" \
  "Results/v0-output" \
  "WAVE_3_DATA" \
  "W3" \
  "private-datasets/was/was_wave_3_hhold_eul_final.dta"

pause

echo "=== Part 2/3: Experiments (GUI enabled) ==="
./scripts/was/run_was_experiments.sh true

pause

echo "=== Part 3/3: v1 parameters + Round 8 validation ==="
bash scripts/demos/run-validation-step.sh \
  "v1" \
  "Results/v1-output" \
  "ROUND_8_DATA" \
  "R8" \
  "private-datasets/was/was_round_8_hhold_eul_may_2025.privdata"
