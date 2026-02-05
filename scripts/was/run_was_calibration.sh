#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
python3 "$repo_root/src/main/resources/calibration-code/PersonalAllowance.py"
python3 "$repo_root/src/main/resources/calibration-code/AgeDist.py"
python3 "$repo_root/src/main/resources/calibration-code/WealthIncomeJointProbDist.py"
python3 "$repo_root/src/main/resources/calibration-code/IncomeAgeJointProbDist.py"
python3 "$repo_root/src/main/resources/calibration-code/BTLProbabilityPerIncomePercentileBin.py"
