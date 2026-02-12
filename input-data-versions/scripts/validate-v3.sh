#!/usr/bin/env bash
# Validate input-data version v3.
# Author: Max Stoddard

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

bash scripts/demos/run-validation-step.sh \
  "v3" \
  "Results/v3-output" \
  "ROUND_8_DATA" \
  "R8" \
  "private-datasets/was/was_round_8_hhold_eul_may_2025.privdata"
