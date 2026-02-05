#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../helpers/log.sh"
LOG_TAG="VALIDATE"
LOG_COLOR="\033[1;36m"
log_init

if [[ $# -ne 5 ]]; then
  log_err "Usage: $0 <input_version> <output_dir> <dataset_const> <expected_dataset> <expected_file>"
  exit 1
fi

input_version="$1"
output_dir="$2"
dataset_const="$3"
expected_dataset="$4"
expected_file="$5"

repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

update_config() {
  local dataset="$1"
  local results_subdir="$2"
  python3 - <<PY
from pathlib import Path
import re
import sys

path = Path("src/main/resources/was/Config.py")
text = path.read_text()

dataset = "${dataset}"
results = "${results_subdir}"

dataset_pattern = r'WAS_DATASET = os.getenv\\("WAS_DATASET", [A-Z0-9_]+\\)'
new_dataset = f'WAS_DATASET = os.getenv("WAS_DATASET", {dataset})'
text, dataset_count = re.subn(dataset_pattern, new_dataset, text)

results_pattern = (
    r'WAS_RESULTS_RUN_SUBDIR = os.getenv\\(\\n'
    r'\\s*"WAS_RESULTS_RUN_SUBDIR",\\n'
    r'\\s*"[^"]*",\\n'
    r'\\)'
)
new_results = (
    'WAS_RESULTS_RUN_SUBDIR = os.getenv(\\n'
    '    "WAS_RESULTS_RUN_SUBDIR",\\n'
    f'    "{results}",\\n'
    ')'
)
text, results_count = re.subn(results_pattern, new_results, text)

if dataset_count != 1 or results_count != 1:
    sys.exit("Failed to update Config.py; expected patterns not found.")

path.write_text(text)
print(f"Updated Config.py: WAS_DATASET={dataset}, WAS_RESULTS_RUN_SUBDIR={results}")
PY
}

show_config_summary() {
  python3 - <<'PY'
import os
import sys

sys.path.append(os.path.abspath("src/main/resources"))
from was import Config

print(f"WAS_DATASET={Config.WAS_DATASET}")
print(f"WAS_DATA_FILENAME={Config.WAS_DATA_FILENAME}")
print(f"WAS_RESULTS_RUN_SUBDIR={Config.WAS_RESULTS_RUN_SUBDIR}")
PY
}

verify_config() {
  local expected_dataset="$1"
  local expected_file="$2"
  python3 - <<PY
import os
import sys

sys.path.append(os.path.abspath("src/main/resources"))
from was import Config

expected_dataset = "${expected_dataset}"
expected_file = "${expected_file}"

if Config.WAS_DATASET != expected_dataset:
    raise SystemExit(
        f"Config check failed: expected WAS_DATASET={expected_dataset}, got {Config.WAS_DATASET}"
    )
if Config.WAS_DATA_FILENAME != expected_file:
    raise SystemExit(
        f"Config check failed: expected WAS_DATA_FILENAME={expected_file}, got {Config.WAS_DATA_FILENAME}"
    )
print("Config check OK.")
PY
}

run_model() {
  local output_dir="$1"
  log "Running model simulation -> ${output_dir}"
  mvn exec:java -Dexec.args="-outputFolder ${output_dir} -dev"
}

log "Validation step: switch data -> run model -> validate outputs."
log "Input version: ${input_version}"
log "Output folder: ${output_dir}"

./scripts/helpers/switch-input-data.sh "${input_version}"
run_model "${output_dir}"
log "Updating validation config to point at output folder"
update_config "${dataset_const}" "${output_dir}"
show_config_summary
log "Verifying dataset selection"
verify_config "${expected_dataset}" "${expected_file}"
log "Running validation suite"
./scripts/was/run_was_validation.sh
