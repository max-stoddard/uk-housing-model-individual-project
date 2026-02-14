#!/usr/bin/env bash
set -euo pipefail

# Summary:
#   Run the full PSD experiment suite plus 2024 calibration.
# Purpose:
#   One-command workflow for inventory, method searches, reporting, and 2024 calibration.
#
# Usage:
#   scripts/psd/run_psd_experiment_suite.sh [term-method]

term_method="${1:-modal_midpoint_round}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

"${script_dir}/run_psd_parameter_inventory.sh"
"${script_dir}/run_psd_lti_hard_max_method_search.sh"
"${script_dir}/run_psd_downpayment_method_search.sh"
"${script_dir}/run_psd_pure_reproduction_report.sh"
"${script_dir}/run_psd_mortgage_duration_method_search_2024.sh"
"${script_dir}/run_psd_2024_pure_direct_calibration.sh" "${term_method}"

