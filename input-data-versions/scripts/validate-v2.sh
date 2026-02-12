#!/usr/bin/env bash
# Validate input-data version v2.
# Author: Max Stoddard

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

bash scripts/demos/run-validation-step.sh \
  "v2" \
  "Results/v2-output" \
  "ROUND_8_DATA" \
  "R8" \
  "private-datasets/was/was_round_8_hhold_eul_may_2025.privdata"
