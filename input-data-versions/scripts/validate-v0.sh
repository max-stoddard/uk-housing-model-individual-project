#!/usr/bin/env bash
# Validate input-data version v0.
# Author: Max Stoddard

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

bash scripts/demos/run-validation-step.sh \
  "v0" \
  "Results/v0-output" \
  "WAVE_3_DATA" \
  "W3" \
  "private-datasets/was/was_wave_3_hhold_eul_final.dta"
