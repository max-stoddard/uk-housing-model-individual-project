#!/usr/bin/env bash
# Author: Max Stoddard

set -euo pipefail

python3 -m scripts.python.experiments.model.boe_policy_story_demo \
  --story-ids ftb_ltv_cap,affordability_cap \
  --workers "${BOE_WORKERS:-8}" \
  --output-dir "${BOE_OUTPUT_DIR:-tmp/boe_policy_story_demo}" \
  "$@"
