#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "$repo_root"

python3 -m scripts.python.calibration.was.personal_allowance
python3 -m scripts.python.calibration.was.age_dist
python3 -m scripts.python.calibration.was.wealth_income_joint_prob_dist
python3 -m scripts.python.calibration.was.income_age_joint_prob_dist
python3 -m scripts.python.calibration.was.btl_probability_per_income_percentile_bin
python3 -m scripts.python.calibration.was.total_wealth_dist
