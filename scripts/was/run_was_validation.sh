#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../helpers/log.sh"
LOG_TAG="WAS-VALID"
LOG_COLOR="\033[1;33m"
log_init

repo_root="$(cd "${script_dir}/../.." && pwd)"

log "Running validation scripts (income, housing wealth, financial wealth)."
log "Income distribution validation"
python3 "$repo_root/src/main/resources/validation-code/IncomeDist.py"
log "Housing wealth validation"
python3 "$repo_root/src/main/resources/validation-code/HousingWealthDist.py"
log "Financial wealth validation"
python3 "$repo_root/src/main/resources/validation-code/FinancialWealthDist.py"
