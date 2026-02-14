#!/usr/bin/env bash
set -euo pipefail

# Summary:
#   Reproduce the locked PSD-2024 values used for input-data-versions v3.4-v3.6.
# Purpose:
#   Run the pinned calibration command and print explicit version-mapping blocks.
#
# Method assumptions (pinned):
#   - Term method: modal_midpoint_round
#   - Term open-top year: 45
#   - Downpayment method: median_anchored_nonftb_independent
#   - Within-bin points: 11
#
# Source datasets:
#   - private-datasets/psd/2024/psd-quarterly-2024.csv
#   - private-datasets/psd/2024/psd-monthly-2024-p1-sales-borrower.csv
#   - private-datasets/psd/2024/psd-monthly-2024-p2-ltv-sales.csv

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

calibration_output="$("${script_dir}/run_psd_2024_pure_direct_calibration.sh" modal_midpoint_round)"
printf "%s\n" "${calibration_output}"

duration="$(printf "%s\n" "${calibration_output}" | awk -F' = ' '/^MORTGAGE_DURATION_YEARS = / {print $2; exit}')"
ftb_scale="$(printf "%s\n" "${calibration_output}" | awk -F' = ' '/^DOWNPAYMENT_FTB_SCALE = / {print $2; exit}')"
ftb_shape="$(printf "%s\n" "${calibration_output}" | awk -F' = ' '/^DOWNPAYMENT_FTB_SHAPE = / {print $2; exit}')"
oo_scale="$(printf "%s\n" "${calibration_output}" | awk -F' = ' '/^DOWNPAYMENT_OO_SCALE = / {print $2; exit}')"
oo_shape="$(printf "%s\n" "${calibration_output}" | awk -F' = ' '/^DOWNPAYMENT_OO_SHAPE = / {print $2; exit}')"

printf "\nVersion mapping (locked)\n"
printf "v3.4 keys:\n"
printf "MORTGAGE_DURATION_YEARS = %s\n" "${duration}"
printf "\n"
printf "v3.5 keys:\n"
printf "DOWNPAYMENT_FTB_SCALE = %s\n" "${ftb_scale}"
printf "DOWNPAYMENT_FTB_SHAPE = %s\n" "${ftb_shape}"
printf "\n"
printf "v3.6 keys:\n"
printf "DOWNPAYMENT_OO_SCALE = %s\n" "${oo_scale}"
printf "DOWNPAYMENT_OO_SHAPE = %s\n" "${oo_shape}"

