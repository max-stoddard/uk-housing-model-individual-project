#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Search BTL strategy calibration methods against config target values.

This script is intended for reproduction/analysis workflows, especially when
comparing 2014-method variants to legacy config values.

Latest experiment findings (run on February 13, 2026):
  - Dataset: private-datasets/nmg/nmg-2014.csv
  - Config: input-data-versions/v3/config.properties
  - Targets:
    - BTL_P_INCOME_DRIVEN = 0.4927
    - BTL_P_CAPITAL_DRIVEN = 0.1458
  - Best-ranked method:
    - legacy_unweighted
    - Schema: legacy_boe72_boe77
    - Rows used: 343
    - PIncome = 0.4927113703
    - PCapital = 0.1457725948
    - Distance ~= 0.0000296704
  - Interpretation:
    - Legacy unweighted classification reproduces historical 2014 targets almost exactly.

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.common.math_stats import euclidean_distance_2d
from scripts.python.helpers.nmg.btl_strategy import (
    PROXY_DATA_SCHEMA_2024,
    METHOD_CHOICES,
    aggregate_probabilities,
    get_method_spec,
    validate_required_columns,
)
from scripts.python.helpers.nmg.columns import (
    BtlStrategyColumnNames as ColumnNames,
    BtlStrategyTargetKeys as TargetKeys,
)
from scripts.python.helpers.nmg.parsing import read_properties


@dataclass(frozen=True)
class RankedResult:
    method_name: str
    weighted: bool
    classifier: str
    data_schema: str
    denominator_rows: int
    denominator_weight: float
    income_probability: float
    capital_probability: float
    mixed_probability: float
    distance: float
    d_income: float
    d_capital: float


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Search NMG BTL strategy calibration methods and rank by closeness "
            "to BTL_P_INCOME_DRIVEN and BTL_P_CAPITAL_DRIVEN."
        ),
    )
    parser.add_argument("nmg_csv", help="Path to NMG CSV (e.g. private-datasets/nmg/nmg-2014.csv).")
    parser.add_argument(
        "--config-path",
        default="src/main/resources/config.properties",
        help="Path to config.properties with target BTL_P_* values.",
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

    properties = read_properties(config_path)
    target_keys = TargetKeys()
    if target_keys.income not in properties or target_keys.capital not in properties:
        raise SystemExit(
            "Could not find BTL_P_INCOME_DRIVEN and BTL_P_CAPITAL_DRIVEN in config file."
        )
    target_income = float(properties[target_keys.income])
    target_capital = float(properties[target_keys.capital])

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

    ranked: list[RankedResult] = []
    for method_name in METHOD_CHOICES:
        try:
            result = aggregate_probabilities(
                rows=rows,
                columns=columns,
                method_name=method_name,
            )
        except ValueError:
            continue
        d_income = abs(result.income_probability - target_income)
        d_capital = abs(result.capital_probability - target_capital)
        distance = euclidean_distance_2d(
            result.income_probability,
            result.capital_probability,
            target_income,
            target_capital,
        )
        ranked.append(
            RankedResult(
                method_name=result.method_name,
                weighted=result.weighted,
                classifier=result.classifier,
                data_schema=result.data_schema,
                denominator_rows=result.denominator_rows,
                denominator_weight=result.denominator_weight,
                income_probability=result.income_probability,
                capital_probability=result.capital_probability,
                mixed_probability=result.mixed_probability,
                distance=distance,
                d_income=d_income,
                d_capital=d_capital,
            )
        )

    if not ranked:
        raise SystemExit("No methods produced valid results for this dataset.")

    ranked.sort(key=lambda item: item.distance)
    top_k = max(1, args.top_k)

    print("NMG BTL strategy method search")
    print(f"CSV: {csv_path}")
    print(f"Config: {config_path}")
    print(f"Target {target_keys.income} = {format_float(target_income)}")
    print(f"Target {target_keys.capital} = {format_float(target_capital)}")
    if any(item.data_schema == PROXY_DATA_SCHEMA_2024 for item in ranked):
        print(
            "Note: proxy schema detected (qbe22b + be22bb_*); "
            "legacy boe72/boe77 strategy questions are unavailable in this dataset."
        )
    print("")
    print(
        "Rank\tDistance\t|dIncome|\t|dCapital|\tMethod\tWeighted\tClassifier\tSchema\tRows\tDenominatorWeight\t"
        "PIncome\tPCapital\tPMixed"
    )
    for rank, item in enumerate(ranked[:top_k], start=1):
        print(
            f"{rank}\t{format_float(item.distance)}\t{format_float(item.d_income)}\t"
            f"{format_float(item.d_capital)}\t{item.method_name}\t"
            f"{'yes' if item.weighted else 'no'}\t{item.classifier}\t"
            f"{item.data_schema}\t"
            f"{item.denominator_rows}\t{format_float(item.denominator_weight)}\t"
            f"{format_float(item.income_probability)}\t"
            f"{format_float(item.capital_probability)}\t"
            f"{format_float(item.mixed_probability)}"
        )

    best = ranked[0]
    best_spec = get_method_spec(best.method_name)
    print("\nBest method")
    print(f"method: {best_spec.method_name}")
    print(f"weighted: {'yes' if best_spec.weighted else 'no'}")
    print(f"classifier: {best_spec.classifier}")
    print(f"schema: {best.data_schema}")
    print(f"rows-used: {best.denominator_rows}")
    print(f"denominator-weight: {format_float(best.denominator_weight)}")
    print(f"{target_keys.income} ~= {format_float(best.income_probability)}")
    print(f"{target_keys.capital} ~= {format_float(best.capital_probability)}")


if __name__ == "__main__":
    main()
