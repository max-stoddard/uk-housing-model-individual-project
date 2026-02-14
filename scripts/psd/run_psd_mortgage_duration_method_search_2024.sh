#!/usr/bin/env bash
set -euo pipefail

# Summary:
#   Run PSD 2024 mortgage-duration method search.
# Purpose:
#   Rank weighted-mean, weighted-median, and modal-midpoint duration estimators.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

python3 -m scripts.python.experiments.psd.psd_mortgage_duration_method_search \
  --quarterly-csv private-datasets/psd/2024/psd-quarterly-2024.csv \
  --target-year 2024 \
  --top-open-years 40,45,50 \
  --methods weighted_mean,weighted_median,modal_midpoint \
  --emit-by-quarter \
  "$@"

