#!/usr/bin/env bash
set -euo pipefail

# Summary:
#   Calibrate PSD 2024 pure-direct keys (downpayment + mortgage duration).
# Purpose:
#   Produce model-ready values and diagnostics from 2024 quarterly PSD.
#
# Usage:
#   scripts/psd/run_psd_2024_pure_direct_calibration.sh [term-method] [extra args...]
# Example:
#   scripts/psd/run_psd_2024_pure_direct_calibration.sh modal_midpoint_round --output-dir tmp/psd

term_method="${1:-modal_midpoint_round}"
if [[ $# -gt 0 ]]; then
  shift
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

python3 -m scripts.python.calibration.psd.psd_2024_pure_direct_calibration \
  --quarterly-csv private-datasets/psd/2024/psd-quarterly-2024.csv \
  --monthly-p1-csv private-datasets/psd/2024/psd-monthly-2024-p1-sales-borrower.csv \
  --monthly-p2-csv private-datasets/psd/2024/psd-monthly-2024-p2-ltv-sales.csv \
  --target-year 2024 \
  --downpayment-method median_anchored_nonftb_independent \
  --term-method "${term_method}" \
  --term-open-top-year 45 \
  --within-bin-points 11 \
  "$@"

