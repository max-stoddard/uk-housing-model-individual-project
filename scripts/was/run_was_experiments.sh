#!/usr/bin/env bash
set -euo pipefail

gui_arg="${1:-false}"
case "${gui_arg}" in
  true|TRUE|True|1|yes|YES|y|Y)
    gui_enabled=true
    ;;
  false|FALSE|False|0|no|NO|n|N|"")
    gui_enabled=false
    ;;
  *)
    echo "Usage: $(basename "$0") [true|false]" >&2
    exit 1
    ;;
esac

# Avoid GUI popups when running batch experiments unless explicitly enabled.
if [[ "${gui_enabled}" != "true" ]]; then
  export MPLBACKEND=Agg
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
experiments_dir="${repo_root}/src/main/resources/experiments"

scripts=(
  "AgeDistributionComparison.py"
  "BTLProbabilityPerIncomePercentileComparison.py"
  "AgeGrossIncomeJointDistComparison.py"
  "GrossIncomeNetWealthJointDistComparison.py"
  "TotalWealthDistComparison.py"
)

for script_name in "${scripts[@]}"; do
  script_path="${experiments_dir}/${script_name}"
  if [[ -f "${script_path}" ]]; then
    echo "Running ${script_name}"
    python3 "${script_path}"
  else
    echo "Skipping missing ${script_name}"
  fi
done
