#!/usr/bin/env bash
set -euo pipefail

# Summary:
#   Run PSD/PPD 2011 BUY* method search.
# Purpose:
#   Compare candidate methods for BUY_SCALE/BUY_EXPONENT/BUY_MU/BUY_SIGMA reproduction.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

python3 -m scripts.python.experiments.psd.psd_buy_budget_method_search \
  --p3-csv private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p3-loan-characteristic.csv \
  --p5-csv private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p5-property-characteristic.csv \
  --ppd-csv private-datasets/ppd/pp-2011.csv \
  --config-path input-data-versions/v0/config.properties \
  --target-year-psd 2011 \
  --target-year-ppd 2011 \
  --families psd_log_ols_residual,psd_log_ols_robust_mu \
  --loan-to-income-couplings comonotonic \
  --income-to-price-couplings comonotonic \
  --loan-open-upper-k 500,550,600,650,700,800,900,1000 \
  --lti-open-upper 7,8,9,10 \
  --lti-open-lower 2,2.25,2.5 \
  --income-open-upper-k 60,80,100 \
  --property-open-upper-k 8000,9000,10000,11000,12000 \
  --trim-fractions 0 \
  --mu-upper-trim-fracs 0.0055,0.006,0.0063,0.0065,0.007 \
  --quantile-grid-size 4000 \
  --top-k 5 \
  --progress-every 500 \
  --progress-every-seconds 2 \
  "$@"
