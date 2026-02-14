#!/usr/bin/env bash
set -euo pipefail

# Summary:
#   Run sharded BUY* method-search in parallel and merge shard outputs.
# Purpose:
#   Speed up large 2011 reproduction searches while preserving deterministic ranking.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

workers="${PSD_BUY_PARALLEL_WORKERS:-16}"
shards="${PSD_BUY_PARALLEL_SHARDS:-16}"
output_root="${PSD_BUY_PARALLEL_OUTPUT_ROOT:-tmp/psd_buy_budget_shards}"

if (( workers <= 0 )); then
  echo "workers must be positive" >&2
  exit 1
fi
if (( shards <= 0 )); then
  echo "shards must be positive" >&2
  exit 1
fi

mkdir -p "${output_root}"

# Pinned defaults: robust reproduction grid that previously achieved
# Distance(norm) ~= 0.02926 on PSD/PPD 2011.
default_args=(
  --p3-csv private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p3-loan-characteristic.csv
  --p5-csv private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p5-property-characteristic.csv
  --ppd-csv private-datasets/ppd/pp-2011.csv
  --config-path input-data-versions/v0/config.properties
  --target-year-psd 2011
  --target-year-ppd 2011
  --families psd_log_ols_residual,psd_log_ols_robust_mu
  --loan-to-income-couplings comonotonic
  --income-to-price-couplings comonotonic
  --loan-open-upper-k 500,550,600,650,700,800,900,1000
  --lti-open-upper 7,8,9,10
  --lti-open-lower 2,2.25,2.5
  --income-open-upper-k 60,80,100
  --property-open-upper-k 8000,9000,10000,11000,12000
  --trim-fractions 0
  --mu-upper-trim-fracs 0.0055,0.006,0.0063,0.0065,0.007
  --quantile-grid-size 4000
  --top-k 5
  --progress-every 500
  --progress-every-seconds 2
)

common_args=("${default_args[@]}" "$@")
common_escaped="$(printf '%q ' "${common_args[@]}")"

echo "Running BUY* method-search shards in parallel"
echo "workers=${workers} shards=${shards} output_root=${output_root}"

indices="$(seq 0 $((shards - 1)))"

parallel_flags=(-j "${workers}" --line-buffer)
if [[ -t 1 && -t 2 ]]; then
  parallel_flags+=(--eta)
fi

parallel "${parallel_flags[@]}" \
  "python3 -m scripts.python.experiments.psd.psd_buy_budget_method_search \
    --shard-count ${shards} \
    --shard-index {1} \
    --output-dir ${output_root}/shard_{1} \
    --summary-json ${output_root}/shard_{1}/summary.json \
    ${common_escaped}" \
  ::: ${indices}

merged_csv="${output_root}/PsdBuyBudgetMethodSearchMerged.csv"

python3 - <<'PY' "${output_root}" "${merged_csv}"
from __future__ import annotations

import csv
import glob
import math
import os
import sys
from pathlib import Path

output_root = Path(sys.argv[1])
merged_csv = Path(sys.argv[2])

paths = sorted(glob.glob(str(output_root / "shard_*" / "PsdBuyBudgetMethodSearch.csv")))
if not paths:
    raise SystemExit("No shard CSV outputs found to merge.")

rows: list[dict[str, str]] = []
header: list[str] | None = None
for path in paths:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if header is None:
            header = list(reader.fieldnames or [])
        for row in reader:
            rows.append(row)

if not rows:
    raise SystemExit("Shard CSVs found, but no data rows to merge.")

def as_float(row: dict[str, str], key: str) -> float:
    raw = row.get(key, "")
    try:
        return float(raw)
    except ValueError:
        return math.inf

rows.sort(
    key=lambda row: (
        as_float(row, "distance_norm"),
        as_float(row, "abs_d_scale_norm"),
        as_float(row, "abs_d_exponent_norm"),
        as_float(row, "abs_d_mu_norm"),
        as_float(row, "abs_d_sigma_norm"),
        row.get("method_id", ""),
    )
)

final_header = list(header or [])
if "rank" not in final_header:
    final_header = ["rank"] + final_header

with merged_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=final_header)
    writer.writeheader()
    for rank, row in enumerate(rows, start=1):
        row_copy = dict(row)
        row_copy["rank"] = str(rank)
        writer.writerow(row_copy)

within_1_count = sum(
    1
    for row in rows
    if str(row.get("within_1pct_all_keys", "")).strip().lower() in {"true", "1", "yes"}
)
best = rows[0]
print("")
print("Merged BUY* search summary")
print(f"Merged rows: {len(rows)}")
print(f"Within 1% (all 4 keys): {within_1_count}")
print(f"Best method: {best.get('method_id', '')}")
print(
    "Best values: "
    f"scale={best.get('buy_scale', '')}, "
    f"exponent={best.get('buy_exponent', '')}, "
    f"mu={best.get('buy_mu', '')}, "
    f"sigma={best.get('buy_sigma', '')}"
)
print(f"Best distance(norm): {best.get('distance_norm', '')}")
print(f"Merged CSV: {merged_csv}")
PY
