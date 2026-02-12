#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Search method variants to reproduce DESIRED_RENT_SCALE and DESIRED_RENT_EXPONENT.

This script evaluates combinations of:
  - qhousing filters
  - income/rent source mappings
  - fit methods

and ranks them by Euclidean distance to target config values.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.nmg.columns import (
    DesiredRentColumnNames as ColumnNames,
    DesiredRentTargetKeys as TargetKeys,
)
from scripts.python.helpers.nmg.fitting import HAVE_SCIPY, fit_log_weighted, fit_nls_weighted
from scripts.python.helpers.nmg.observations import (
    get_income_from_row,
    get_rent_from_row,
)
from scripts.python.helpers.nmg.parsing import (
    parse_float,
    parse_int,
    read_properties,
    resolve_optional_column,
)


@dataclass(frozen=True)
class MethodSpec:
    qhousing_name: str
    qhousing_values: frozenset[int]
    income_source: str
    rent_source: str
    fit_method: str


@dataclass(frozen=True)
class MethodResult:
    method: MethodSpec
    rows_used: int
    scale: float
    exponent: float
    distance: float
    d_scale: float
    d_exponent: float


def evaluate_method(
    rows: Sequence[dict[str, str]],
    columns: ColumnNames,
    rent_free_column: str | None,
    method: MethodSpec,
    target_scale: float,
    target_exponent: float,
) -> MethodResult | None:
    x_values: list[float] = []
    y_values: list[float] = []
    weights: list[float] = []

    for row in rows:
        qhousing = parse_int(row.get(columns.qhousing))
        if qhousing is None or qhousing not in method.qhousing_values:
            continue

        income = get_income_from_row(row, method.income_source, columns)
        rent = get_rent_from_row(row, method.rent_source, columns, rent_free_column)
        weight = parse_float(row.get(columns.weight))

        if income is None or income <= 0:
            continue
        if rent is None or rent <= 0:
            continue
        if weight is None or weight <= 0:
            continue

        x_values.append(income)
        y_values.append(rent)
        weights.append(weight)

    if len(x_values) < 3:
        return None

    x = np.asarray(x_values, dtype=float)
    y = np.asarray(y_values, dtype=float)
    w = np.asarray(weights, dtype=float)

    if method.fit_method == "log_weighted":
        scale, exponent = fit_log_weighted(x, y, w)
    elif method.fit_method == "nls_weighted":
        scale, exponent = fit_nls_weighted(x, y, w)
    else:
        raise ValueError(f"Unsupported fit method: {method.fit_method}")

    d_scale = abs(scale - target_scale)
    d_exponent = abs(exponent - target_exponent)
    distance = math.sqrt(d_scale**2 + d_exponent**2)

    return MethodResult(
        method=method,
        rows_used=len(x_values),
        scale=scale,
        exponent=exponent,
        distance=distance,
        d_scale=d_scale,
        d_exponent=d_exponent,
    )


def build_method_specs() -> list[MethodSpec]:
    qhousing_sets = {
        "q4": frozenset({4}),
        "q34": frozenset({3, 4}),
        "q345": frozenset({3, 4, 5}),
        "q34598": frozenset({3, 4, 5, 98}),
    }

    income_sources = [
        "incomev2comb_upper",
        "incomev2comb_mid",
        "incomev2comb_lower",
        "sum_free_income",
        "self_free_income",
    ]
    rent_sources = [
        "spq07_upper",
        "spq07_mid",
        "spq07_lower",
        "spq07_free",
        "spq07_free_or_upper",
        "spq07_free_or_mid",
        "spq07_free_or_lower",
    ]
    fit_methods = ["log_weighted"]
    if HAVE_SCIPY:
        fit_methods.append("nls_weighted")

    specs: list[MethodSpec] = []
    for q_name, q_values in qhousing_sets.items():
        for income_source in income_sources:
            for rent_source in rent_sources:
                for fit_method in fit_methods:
                    specs.append(
                        MethodSpec(
                            qhousing_name=q_name,
                            qhousing_values=q_values,
                            income_source=income_source,
                            rent_source=rent_source,
                            fit_method=fit_method,
                        )
                    )
    return specs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Search NMG desired-rent calibration methods and rank by closeness to "
            "DESIRED_RENT_SCALE/EXPONENT targets."
        ),
    )
    parser.add_argument("nmg_csv", help="Path to NMG CSV (e.g. private-datasets/nmg/nmg-2016.csv).")
    parser.add_argument(
        "--config-path",
        default="src/main/resources/config.properties",
        help="Path to config.properties with target DESIRED_RENT_* values.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Number of top methods to print (default: 20).",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    csv_path = Path(args.nmg_csv)
    if not csv_path.exists():
        parser.error(f"Missing NMG CSV: {csv_path}")

    config_path = Path(args.config_path)
    if not config_path.exists():
        parser.error(f"Missing config file: {config_path}")

    props = read_properties(config_path)
    target_keys = TargetKeys()
    if target_keys.scale not in props or target_keys.exponent not in props:
        raise SystemExit(
            "Could not find DESIRED_RENT_SCALE and DESIRED_RENT_EXPONENT in config file."
        )
    target_scale = float(props[target_keys.scale])
    target_exponent = float(props[target_keys.exponent])

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit("Input CSV has no header row.")
        rows = list(reader)
        header = reader.fieldnames

    columns = ColumnNames()
    missing = []
    for required in (columns.qhousing, columns.weight):
        if required not in header:
            missing.append(required)
    if missing:
        raise SystemExit("Missing required columns: " + ", ".join(missing))

    rent_free_column = resolve_optional_column(header, columns.rent_free_candidates)

    results: list[MethodResult] = []
    for method in build_method_specs():
        try:
            result = evaluate_method(
                rows=rows,
                columns=columns,
                rent_free_column=rent_free_column,
                method=method,
                target_scale=target_scale,
                target_exponent=target_exponent,
            )
        except ValueError:
            continue
        if result is not None:
            results.append(result)

    if not results:
        raise SystemExit("No valid method variants produced enough usable rows for fitting.")

    results.sort(key=lambda row: row.distance)
    top_k = max(1, args.top_k)

    print("Desired rent method search")
    print(f"CSV: {csv_path}")
    print(f"Config: {config_path}")
    print(f"Target {target_keys.scale} = {format_float(target_scale)}")
    print(f"Target {target_keys.exponent} = {format_float(target_exponent)}")
    print(f"SciPy available: {'yes' if HAVE_SCIPY else 'no'}")
    print("")
    print(
        "Rank\tDistance\t|dScale|\t|dExp|\tRows\tQHousing\tIncome\tRent\tFit\tScale\tExponent"
    )
    for rank, row in enumerate(results[:top_k], start=1):
        print(
            f"{rank}\t{format_float(row.distance)}\t{format_float(row.d_scale)}\t"
            f"{format_float(row.d_exponent)}\t{row.rows_used}\t{row.method.qhousing_name}\t"
            f"{row.method.income_source}\t{row.method.rent_source}\t{row.method.fit_method}\t"
            f"{format_float(row.scale)}\t{format_float(row.exponent)}"
        )

    best = results[0]
    qhousing_values = ",".join(str(v) for v in sorted(best.method.qhousing_values))
    print("\nBest method")
    print(f"qhousing-values: {qhousing_values}")
    print(f"income-source: {best.method.income_source}")
    print(f"rent-source: {best.method.rent_source}")
    print(f"fit-method: {best.method.fit_method}")
    print(f"rows-used: {best.rows_used}")
    print(f"DESIRED_RENT_SCALE ~= {format_float(best.scale)}")
    print(f"DESIRED_RENT_EXPONENT ~= {format_float(best.exponent)}")


if __name__ == "__main__":
    main()
