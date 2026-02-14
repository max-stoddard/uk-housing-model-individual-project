#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Search PSD 2024 mortgage-duration method variants and rank by stability.

Latest experiment findings (run on February 13, 2026):
  - Dataset: private-datasets/psd/2024/psd-quarterly-2024.csv
  - Scope: year 2024, mortgage-term bands
  - Top-ranked method under current-2024 objective:
    - method = modal_midpoint
    - open-top years = 40 (equivalent for 45/50 under current mode bin)
    - year estimate ~= 32.5000
    - rounded = 32
    - quarter-to-quarter std (rounded) = 0
  - Interpretation:
    - 2024 term distributions have shifted upward versus legacy 25-year settings,
      and the modal-band midpoint is most stable under the configured ranking policy.

Historical context:
  - 2022 model docs state MORTGAGE_DURATION_YEARS=25 was estimated from PSD 2011
    as the median mortgage duration in that dataset.

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.common.paths import ensure_output_dir
from scripts.python.helpers.psd.mortgage_duration import (
    METHOD_CHOICES,
    MortgageDurationResult,
    run_mortgage_duration_search as run_mortgage_duration_search_from_rows,
)
from scripts.python.helpers.psd.quarterly_long import load_quarterly_psd_rows


def _parse_int_csv(value: str) -> tuple[int, ...]:
    out: list[int] = []
    for token in value.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        parsed = int(stripped)
        if parsed <= 35:
            raise ValueError("Open-top years must be > 35.")
        out.append(parsed)
    if not out:
        raise ValueError("Expected at least one open-top year.")
    return tuple(sorted(set(out)))


def _parse_methods(value: str) -> tuple[str, ...]:
    out: list[str] = []
    for token in value.split(","):
        method = token.strip()
        if not method:
            continue
        if method not in METHOD_CHOICES:
            raise ValueError(f"Unsupported method: {method}")
        out.append(method)
    if not out:
        raise ValueError("Expected at least one method.")
    return tuple(dict.fromkeys(out))


def run_mortgage_duration_search(
    *,
    quarterly_csv: Path,
    target_year: int,
    top_open_years: tuple[int, ...],
    methods: tuple[str, ...],
) -> tuple[list[MortgageDurationResult], tuple[str, ...]]:
    rows = load_quarterly_psd_rows(quarterly_csv)
    results, available_quarters = run_mortgage_duration_search_from_rows(
        rows,
        target_year=target_year,
        top_open_years=top_open_years,
        methods=methods,
    )
    return results, available_quarters


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search mortgage-duration methods on PSD 2024 quarterly term bands."
    )
    parser.add_argument(
        "--quarterly-csv",
        default="private-datasets/psd/2024/psd-quarterly-2024.csv",
        help="Path to PSD quarterly 2024 CSV.",
    )
    parser.add_argument(
        "--target-year",
        type=int,
        default=2024,
        help="Target calendar year (default: 2024).",
    )
    parser.add_argument(
        "--top-open-years",
        default="40,45,50",
        help="Comma-separated open-top assumptions for >35y bin (default: 40,45,50).",
    )
    parser.add_argument(
        "--methods",
        default="weighted_mean,weighted_median,modal_midpoint",
        help="Comma-separated methods to test (default: weighted_mean,weighted_median,modal_midpoint).",
    )
    parser.add_argument(
        "--emit-by-quarter",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Emit quarterly rounded estimates per method (default: true).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for CSV export.",
    )
    return parser


def _write_csv(results: list[MortgageDurationResult], output_dir: str) -> Path:
    output_root = ensure_output_dir(output_dir)
    output_path = output_root / "PsdMortgageDurationMethodSearch.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank",
                "method_id",
                "year_estimate_raw",
                "year_estimate_rounded",
                "open_top_assumption",
                "quarter_mean",
                "quarter_std",
                "sensitivity_range",
                "legacy_distance_to_25",
                "status",
                "excluded_share",
                "quarter_estimates_rounded",
            ]
        )
        for rank, result in enumerate(results, start=1):
            writer.writerow(
                [
                    rank,
                    result.method_id,
                    result.year_estimate_raw,
                    result.year_estimate_rounded,
                    result.open_top_assumption,
                    result.quarter_mean,
                    result.quarter_std,
                    result.sensitivity_range,
                    result.legacy_distance_to_25,
                    result.status,
                    result.excluded_share,
                    ",".join(str(item) for item in result.quarter_estimates_rounded),
                ]
            )
    return output_path


def main() -> None:
    args = build_arg_parser().parse_args()
    top_open_years = _parse_int_csv(args.top_open_years)
    methods = _parse_methods(args.methods)

    output = run_mortgage_duration_search(
        quarterly_csv=Path(args.quarterly_csv),
        target_year=args.target_year,
        top_open_years=top_open_years,
        methods=methods,
    )
    results, available_quarters = output

    print("PSD mortgage-duration method search")
    print(f"Quarterly CSV: {args.quarterly_csv}")
    print(f"Target year: {args.target_year}")
    print(f"Methods: {', '.join(methods)}")
    print(f"Open-top years: {', '.join(str(item) for item in top_open_years)}")
    print(f"Quarters: {', '.join(available_quarters)}")
    print("")
    print(
        "Rank\tMethod\tYearRaw\tYearRounded\tOpenTop\tQuarterMean\tQuarterStd\t"
        "SensitivityRange\tLegacyDistance25\tStatus"
    )
    for rank, result in enumerate(results, start=1):
        print(
            f"{rank}\t{result.method_id}\t{format_float(result.year_estimate_raw)}\t"
            f"{result.year_estimate_rounded}\t{result.open_top_assumption}\t"
            f"{format_float(result.quarter_mean)}\t{format_float(result.quarter_std)}\t"
            f"{format_float(result.sensitivity_range)}\t"
            f"{format_float(result.legacy_distance_to_25)}\t{result.status}"
        )

    if args.emit_by_quarter:
        print("\nQuarterly rounded estimates")
        print("method_id\tQ-estimates")
        for result in results:
            quarter_display = ", ".join(str(item) for item in result.quarter_estimates_rounded)
            print(f"{result.method_id}\t{quarter_display}")

    if args.output_dir:
        output_path = _write_csv(results, args.output_dir)
        print(f"\nWrote: {output_path}")


if __name__ == "__main__":
    main()
