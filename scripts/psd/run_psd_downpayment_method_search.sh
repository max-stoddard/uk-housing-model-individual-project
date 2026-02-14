#!/usr/bin/env bash
set -euo pipefail

# Summary:
#   Run PSD 2011 downpayment lognormal method search.
# Purpose:
#   Compare candidate methods for DOWNPAYMENT_FTB/OO SCALE+SHAPE reproduction.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

python3 -m scripts.python.experiments.psd.psd_downpayment_lognormal_method_search \
  --p3-csv private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p3-loan-characteristic.csv \
  --p5-csv private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p5-property-characteristic.csv \
  --p6-csv private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p6-ftbs.csv \
  --config-path src/main/resources/config.properties \
  --target-year 2011 \
  --within-bin-points 11 \
  --top-k 20 \
  "$@"

