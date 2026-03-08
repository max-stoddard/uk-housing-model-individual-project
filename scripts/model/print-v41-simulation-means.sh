#!/usr/bin/env bash
# Print post-200 simulation means for the canonical v4.1 results run.
# Author: Max Stoddard

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "${script_dir}/model_speed.py" results-summary "$@"
