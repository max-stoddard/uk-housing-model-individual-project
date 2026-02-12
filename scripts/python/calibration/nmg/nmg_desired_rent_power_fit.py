#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute DESIRED_RENT_SCALE and DESIRED_RENT_EXPONENT from NMG CSV data.

Default method (chosen to reduce band-edge and level-space fitting bias):
  - qhousing in {3,4,5}
  - income source: incomev2comb mapped to annual midpoints
  - rent source: spq07 mapped to monthly midpoints
  - fit: weighted linear regression in log space

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.nmg.columns import DesiredRentColumnNames as ColumnNames
from scripts.python.helpers.nmg.fitting import (
    HAVE_SCIPY,
    fit_log_weighted,
    fit_nls_weighted,
)
from scripts.python.helpers.nmg.observations import (
    get_income_from_row,
    get_rent_from_row,
    validate_required_desired_rent_columns,
)
from scripts.python.helpers.nmg.parsing import (
    parse_float,
    parse_int,
    parse_qhousing_values,
    resolve_optional_column,
)


@dataclass
class ParseStats:
    total_rows: int = 0
    rows_invalid_qhousing: int = 0
    rows_filtered_qhousing: int = 0
    rows_invalid_income: int = 0
    rows_invalid_rent: int = 0
    rows_invalid_weight: int = 0
    rows_used: int = 0


def validate_required_columns(
    header: Sequence[str],
    columns: ColumnNames,
    income_source: str,
    rent_source: str,
) -> str | None:
    rent_free_column = resolve_optional_column(header, columns.rent_free_candidates)
    validate_required_desired_rent_columns(
        header,
        columns,
        income_source,
        rent_source,
        rent_free_column,
    )
    return rent_free_column


def build_observations(
    rows: Sequence[dict[str, str]],
    columns: ColumnNames,
    qhousing_values: set[int],
    income_source: str,
    rent_source: str,
    rent_free_column: str | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, ParseStats]:
    stats = ParseStats()
    x_values: list[float] = []
    y_values: list[float] = []
    weights: list[float] = []

    for row in rows:
        stats.total_rows += 1

        qhousing = parse_int(row.get(columns.qhousing))
        if qhousing is None:
            stats.rows_invalid_qhousing += 1
            continue
        if qhousing not in qhousing_values:
            stats.rows_filtered_qhousing += 1
            continue

        income = get_income_from_row(row, income_source, columns)
        if income is None or income <= 0:
            stats.rows_invalid_income += 1
            continue

        rent = get_rent_from_row(row, rent_source, columns, rent_free_column)
        if rent is None or rent <= 0:
            stats.rows_invalid_rent += 1
            continue

        weight = parse_float(row.get(columns.weight))
        if weight is None or weight <= 0:
            stats.rows_invalid_weight += 1
            continue

        x_values.append(income)
        y_values.append(rent)
        weights.append(weight)
        stats.rows_used += 1

    return (
        np.asarray(x_values, dtype=float),
        np.asarray(y_values, dtype=float),
        np.asarray(weights, dtype=float),
        stats,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute DESIRED_RENT_SCALE and DESIRED_RENT_EXPONENT from NMG CSV data.",
    )
    parser.add_argument("nmg_csv", help="Path to NMG CSV file.")
    parser.add_argument(
        "--qhousing-values",
        default="3,4,5",
        help="Comma-separated qhousing values to include (default: 3,4,5).",
    )
    parser.add_argument(
        "--income-source",
        default="incomev2comb_mid",
        choices=["incomev2comb_upper", "incomev2comb_mid", "sum_free_income"],
        help=(
            "Income source mapping. Default uses income-band midpoints to avoid "
            "systematic upper-bound inflation."
        ),
    )
    parser.add_argument(
        "--rent-source",
        default="spq07_mid",
        choices=["spq07_upper", "spq07_mid", "spq07_free"],
        help=(
            "Rent source mapping. Default uses rent-band midpoints to avoid "
            "systematic upper-bound inflation."
        ),
    )
    parser.add_argument(
        "--fit-method",
        default="log_weighted",
        choices=["nls_weighted", "log_weighted"],
        help=(
            "Fit method. Default log_weighted balances proportional errors; "
            "nls_weighted minimizes level-space squared errors and can overweight "
            "high-rent observations."
        ),
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    csv_path = Path(args.nmg_csv)
    if not csv_path.exists():
        parser.error(f"Missing NMG CSV: {csv_path}")

    try:
        qhousing_values = parse_qhousing_values(args.qhousing_values)
    except ValueError as exc:
        parser.error(str(exc))

    if args.fit_method == "nls_weighted" and not HAVE_SCIPY:
        raise SystemExit(
            "fit-method=nls_weighted requires SciPy, which is unavailable."
        )

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit("Input CSV has no header row.")
        rows = list(reader)
        header = reader.fieldnames

    columns = ColumnNames()
    try:
        rent_free_column = validate_required_columns(
            header=header,
            columns=columns,
            income_source=args.income_source,
            rent_source=args.rent_source,
        )
    except ValueError as exc:
        raise SystemExit(str(exc))

    x, y, w, stats = build_observations(
        rows=rows,
        columns=columns,
        qhousing_values=qhousing_values,
        income_source=args.income_source,
        rent_source=args.rent_source,
        rent_free_column=rent_free_column,
    )

    if len(x) < 3:
        raise SystemExit(
            "No valid rows for fitting with selected settings. "
            "This likely indicates unsupported data shape for this source/method combination."
        )

    if args.fit_method == "log_weighted":
        scale, exponent = fit_log_weighted(x, y, w)
    else:
        scale, exponent = fit_nls_weighted(x, y, w)

    qhousing_label = ",".join(str(v) for v in sorted(qhousing_values))

    print("Computed desired rent power-law parameters from NMG data")
    print(f"File: {csv_path}")
    print(f"Rows read: {stats.total_rows}")
    print(f"Rows used: {stats.rows_used}")
    print(f"Rows with invalid qhousing: {stats.rows_invalid_qhousing}")
    print(
        f"Rows with qhousing not in {{{qhousing_label}}}: {stats.rows_filtered_qhousing}"
    )
    print(f"Rows with invalid income: {stats.rows_invalid_income}")
    print(f"Rows with invalid rent: {stats.rows_invalid_rent}")
    print(f"Rows with invalid weight: {stats.rows_invalid_weight}")
    print("")
    print(f"qhousing values: {{{qhousing_label}}}")
    print(f"income source: {args.income_source}")
    print(f"rent source: {args.rent_source}")
    print(f"fit method: {args.fit_method}")
    if args.fit_method == "log_weighted":
        print(
            "fit objective: weighted log-space regression (balances proportional errors across rent levels)"
        )
    else:
        print("fit objective: weighted level-space NLS (squared pound errors)")
        print(
            "warning: level-space NLS can overweight high-rent observations in the fit"
        )
    print("")
    print(f"DESIRED_RENT_SCALE = {format_float(scale)}")
    print(f"DESIRED_RENT_EXPONENT = {format_float(exponent)}")


if __name__ == "__main__":
    main()
