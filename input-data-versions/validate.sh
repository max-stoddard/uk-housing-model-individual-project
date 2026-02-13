#!/usr/bin/env bash
# Generic validation runner for input-data versions.
# Author: Max Stoddard

set -euo pipefail

print_usage() {
  cat <<EOF
Usage: $(basename "$0") <subfolder> <w3|r8> [--graphs|--no-graphs]

Arguments:
  <subfolder>  Input-data version folder name (for example: v0, v1, v4).
  <w3|r8>      WAS dataset selector.

Options:
  --graphs     Enable matplotlib plots during validation.
  --no-graphs  Disable matplotlib plots during validation (default).
EOF
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
  print_usage
  exit 1
fi

input_version="$1"
dataset_key="$2"
graphs_flag="${3:---no-graphs}"

case "${graphs_flag}" in
  --graphs)
    show_graphs="1"
    ;;
  --no-graphs)
    show_graphs="0"
    ;;
  *)
    echo "Unknown graph option: ${graphs_flag}" >&2
    print_usage
    exit 1
    ;;
esac

case "${dataset_key,,}" in
  w3)
    dataset_const="WAVE_3_DATA"
    expected_dataset="W3"
    expected_file="private-datasets/was/was_wave_3_hhold_eul_final.dta"
    ;;
  r8)
    dataset_const="ROUND_8_DATA"
    expected_dataset="R8"
    expected_file="private-datasets/was/was_round_8_hhold_eul_may_2025.privdata"
    ;;
  *)
    echo "Unsupported dataset: ${dataset_key} (expected w3 or r8)." >&2
    print_usage
    exit 1
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "${repo_root}"

export WAS_VALIDATION_PLOTS="${show_graphs}"

bash scripts/demos/run-validation-step.sh \
  "${input_version}" \
  "Results/${input_version}-output" \
  "${dataset_const}" \
  "${expected_dataset}" \
  "${expected_file}"
