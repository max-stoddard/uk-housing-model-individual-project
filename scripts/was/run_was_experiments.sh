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
cd "${repo_root}"

log "Running experiments (GUI enabled: ${gui_enabled})."

modules=(
  "scripts.python.experiments.was.personal_allowance"
  "scripts.python.experiments.was.age_distribution_comparison"
  "scripts.python.experiments.was.btl_probability_per_income_percentile_comparison"
  "scripts.python.experiments.was.age_gross_income_joint_dist_comparison"
  "scripts.python.experiments.was.gross_income_net_wealth_joint_dist_comparison"
  "scripts.python.experiments.was.total_wealth_dist_comparison"
)

for module_name in "${modules[@]}"; do
  log "Running ${module_name}"
  python3 -m "${module_name}"
done
