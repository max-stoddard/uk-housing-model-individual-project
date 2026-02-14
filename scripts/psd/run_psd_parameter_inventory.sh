#!/usr/bin/env bash
set -euo pipefail

# Summary:
#   Enumerate PSD-tagged config keys and their classifications.
# Purpose:
#   Quick visibility into which config parameters are pure-direct, blocked, or hybrid.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

python3 -m scripts.python.experiments.psd.psd_parameter_inventory \
  --config-path src/main/resources/config.properties \
  --emit-format table \
  "$@"

