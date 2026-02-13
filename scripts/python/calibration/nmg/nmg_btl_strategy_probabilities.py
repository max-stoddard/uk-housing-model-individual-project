#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute BTL_P_INCOME_DRIVEN and BTL_P_CAPITAL_DRIVEN from NMG CSV data.

Default method:
  - legacy_weighted

Expected production usage:
  - run on NMG 2024 data (or another explicitly chosen target-year dataset)

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.nmg.btl_strategy import (
    LEGACY_WEIGHTED,
    PROXY_DATA_SCHEMA_2024,
    METHOD_CHOICES,
    aggregate_probabilities,
    validate_required_columns,
)
from scripts.python.helpers.nmg.columns import (
    BtlStrategyColumnNames as ColumnNames,
    BtlStrategyTargetKeys as TargetKeys,
)


def _positive_year(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("target-year must be an integer.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("target-year must be positive.")
    return parsed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compute BTL strategy probabilities from NMG data for calibration."
        ),
    )
    parser.add_argument("nmg_csv", help="Path to NMG CSV file.")
    parser.add_argument(
        "--method",
        default=LEGACY_WEIGHTED,
        choices=METHOD_CHOICES,
        help="Calibration method (default: legacy_weighted).",
    )
    parser.add_argument(
        "--target-year",
        type=_positive_year,
        default=2024,
        help="Dataset year for metadata and reporting (default: 2024).",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    csv_path = Path(args.nmg_csv)
    if not csv_path.exists():
        parser.error(f"Missing NMG CSV: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit("Input CSV has no header row.")
        rows = list(reader)
        header = reader.fieldnames

    columns = ColumnNames()
    try:
        validate_required_columns(header, columns)
    except ValueError as exc:
        raise SystemExit(str(exc))

    try:
        result = aggregate_probabilities(
            rows=rows,
            columns=columns,
            method_name=args.method,
        )
    except ValueError as exc:
        raise SystemExit(str(exc))

    target_keys = TargetKeys()
    stats = result.parse_stats
    print("Computed BTL strategy probabilities from NMG data")
    print(f"File: {csv_path}")
    print(f"Target year: {args.target_year}")
    print(f"Method: {result.method_name}")
    print(f"Weighted: {'enabled' if result.weighted else 'disabled'}")
    print(f"Classifier: {result.classifier}")
    print(f"Schema: {result.data_schema}")
    print(f"Rows read: {stats.total_rows}")
    print(f"Rows used: {stats.rows_used}")
    print(f"Rows missing required columns: {stats.rows_missing_required}")
    print(f"Rows with invalid screen values: {stats.rows_invalid_screen}")
    print(f"Rows filtered by screen condition: {stats.rows_filtered_screen}")
    print(f"Rows with invalid strategy flags: {stats.rows_invalid_flags}")
    if result.weighted:
        print(f"Rows with invalid weight: {stats.rows_invalid_weight}")
    print(f"Denominator rows: {result.denominator_rows}")
    print(f"Denominator weight: {format_float(result.denominator_weight)}")
    if result.data_schema == PROXY_DATA_SCHEMA_2024:
        print(
            "Note: using 2024 proxy schema (qbe22b + be22bb_*), "
            "not the legacy boe72/boe77 strategy questions."
        )
    print("")
    print(f"{target_keys.income} = {format_float(result.income_probability)}")
    print(f"{target_keys.capital} = {format_float(result.capital_probability)}")
    print("")
    print(f"BTL_P_MIX_DRIVEN (implied) = {format_float(result.mixed_probability)}")


if __name__ == "__main__":
    main()
