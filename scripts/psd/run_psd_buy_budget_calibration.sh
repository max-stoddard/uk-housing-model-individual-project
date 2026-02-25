#!/usr/bin/env bash
set -euo pipefail

# Summary:
#   Run production BUY* calibration from PSD 2024 + PPD 2025.
# Purpose:
#   Emit model-ready BUY_SCALE/BUY_EXPONENT/BUY_MU/BUY_SIGMA using the selected default method.
#
# Legacy note:
#   This wrapper invokes the v3.8 reproduction-first BUY* method and is retained
#   for historical reproducibility only. Do not use for production updates.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

python3 -m scripts.python.calibration.psd.psd_buy_budget_calibration \
  --quarterly-csv private-datasets/psd/2024/psd-quarterly-2024.csv \
  --ppd-csv private-datasets/ppd/pp-2025.csv \
  --target-year-psd 2024 \
  --target-year-ppd 2025 \
  --method 'family=psd_log_ols_robust_mu|loan_to_income=comonotonic|income_to_price=comonotonic|loan_open_k=500|lti_open=10|lti_floor=2.5|income_open_k=100|property_open_k=10000|trim=0|within_bin_points=11|grid=4000|mu_hi_trim=0.0063' \
  "$@"
