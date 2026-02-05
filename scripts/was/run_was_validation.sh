#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"

python3 "$repo_root/src/main/resources/validation-code/TotalWealthDist.py"
python3 "$repo_root/src/main/resources/validation-code/IncomeDist.py"
python3 "$repo_root/src/main/resources/validation-code/HousingWealthDist.py"
python3 "$repo_root/src/main/resources/validation-code/FinancialWealthDist.py"
