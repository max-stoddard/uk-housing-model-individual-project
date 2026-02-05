#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../helpers/log.sh"
LOG_TAG="WAS-EXPER"
LOG_COLOR="\033[1;35m"
log_init

gui_arg="${1:-false}"
case "${gui_arg}" in
  true|TRUE|True|1|yes|YES|y|Y)
    gui_enabled=true
    ;;
  false|FALSE|False|0|no|NO|n|N|"")
    gui_enabled=false
    ;;
  *)
    log_err "Usage: $(basename "$0") [true|false]"
    exit 1
    ;;
esac

# Avoid GUI popups when running batch experiments unless explicitly enabled.
if [[ "${gui_enabled}" != "true" ]]; then
  export MPLBACKEND=Agg
fi

repo_root="$(cd "${script_dir}/../.." && pwd)"
experiments_dir="${repo_root}/src/main/resources/experiments"

log "Running experiments (GUI enabled: ${gui_enabled})."

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
    log "Running ${script_name}"
    python3 "${script_path}"
  else
    log "Skipping missing ${script_name}"
  fi
done
