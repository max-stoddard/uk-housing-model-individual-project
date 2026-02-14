#!/usr/bin/env bash
set -euo pipefail

# Summary:
#   Run PSD 2011 LTI hard-max method search.
# Purpose:
#   Compare candidate ways to reproduce BANK_LTI_HARD_MAX_FTB/HM from PSD bins.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

python3 -m scripts.python.experiments.psd.psd_lti_hard_max_method_search \
  --p3-csv private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p3-loan-characteristic.csv \
  --p6-csv private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p6-ftbs.csv \
  --config-path src/main/resources/config.properties \
  --target-year 2011 \
  --top-k 20 \
  "$@"

