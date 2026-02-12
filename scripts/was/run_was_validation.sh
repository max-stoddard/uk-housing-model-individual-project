#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../helpers/log.sh"
LOG_TAG="WAS-VALID"
LOG_COLOR="\033[1;33m"
log_init

repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

log "Running validation scripts (income, housing wealth, financial wealth)."
log "Income distribution validation"
python3 -m scripts.python.validation.was.income_dist
log "Housing wealth validation"
python3 -m scripts.python.validation.was.housing_wealth_dist
log "Financial wealth validation"
python3 -m scripts.python.validation.was.financial_wealth_dist
