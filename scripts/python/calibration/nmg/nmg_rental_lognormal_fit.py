#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute log-normal rental price parameters from Bank of England NMG survey CSV.

Filters:
  - qhousing in {3,4} by default; configurable via CLI
  - rent column: SPQ07free_1 or spq07free_1
  - weight column: we_factor (can be disabled via CLI)

Outputs:
  RENTAL_PRICES_SCALE (mu)  = mean of log(rent)
  RENTAL_PRICES_SHAPE (sigma) = std dev of log(rent)

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.nmg.columns import RentalLognormalColumns as ColumnNames
from scripts.python.helpers.nmg.parsing import (
    parse_int,
    parse_positive_float,
    parse_qhousing_values,
)

@dataclass
class ColumnIndices:
    qhousing: int
    rent: int
    weight: int


@dataclass
class WeightedRunningStats:
    count: int = 0
    weight_sum: float = 0.0
    mean: float = 0.0
    m2: float = 0.0
    min_value: float = math.inf
    max_value: float = -math.inf

    def update(self, value: float, weight: float) -> None:
        if weight <= 0:
            return
        self.count += 1
        temp = self.weight_sum + weight
        delta = value - self.mean
        self.mean += weight * delta / temp
        self.m2 += weight * delta * (value - self.mean)
        self.weight_sum = temp
        if value < self.min_value:
            self.min_value = value
        if value > self.max_value:
            self.max_value = value

    def variance(self) -> float:
        if self.weight_sum <= 0:
            return 0.0
        return self.m2 / self.weight_sum

    def std(self) -> float:
        return math.sqrt(self.variance())


@dataclass
class ParseStats:
    total_rows: int = 0
    rows_missing_required: int = 0
    rows_invalid_qhousing: int = 0
    rows_non_private: int = 0
    rows_invalid_rent: int = 0
    rows_invalid_weight: int = 0
    rows_used: int = 0


def resolve_indices(header: Sequence[str], columns: ColumnNames) -> ColumnIndices:
    lookup = {name: idx for idx, name in enumerate(header)}
    rent_name = None
    for candidate in columns.rent_candidates:
        if candidate in lookup:
            rent_name = candidate
            break

    missing = []
    if columns.qhousing not in lookup:
        missing.append(columns.qhousing)
    if rent_name is None:
        missing.append("rent(" + "|".join(columns.rent_candidates) + ")")
    if columns.weight not in lookup:
        missing.append(columns.weight)
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Missing required columns: {missing_text}")
    return ColumnIndices(
        qhousing=lookup[columns.qhousing],
        rent=lookup[rent_name],
        weight=lookup[columns.weight],
    )


def iter_rows(path: Path, delimiter: str) -> Iterator[list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        for row in reader:
            yield row


def update_stats_from_file(
    stats: WeightedRunningStats,
    parse_stats: ParseStats,
    path: Path,
    delimiter: str,
    columns: ColumnNames,
    qhousing_values: set[int],
    use_weights: bool,
) -> None:
    rows = iter_rows(path, delimiter)
    try:
        header = next(rows)
    except StopIteration:
        return
    indices = resolve_indices(header, columns)
    required_max_index = max(indices.qhousing, indices.rent, indices.weight)

    for row in rows:
        parse_stats.total_rows += 1
        if len(row) <= required_max_index:
            parse_stats.rows_missing_required += 1
            continue

        qhousing_raw = row[indices.qhousing]
        qhousing_value = parse_int(qhousing_raw)
        if qhousing_value is None:
            parse_stats.rows_invalid_qhousing += 1
            continue
        if qhousing_value not in qhousing_values:
            parse_stats.rows_non_private += 1
            continue

        rent = parse_positive_float(row[indices.rent])
        if rent is None:
            parse_stats.rows_invalid_rent += 1
            continue

        if use_weights:
            weight = parse_positive_float(row[indices.weight])
            if weight is None:
                parse_stats.rows_invalid_weight += 1
                continue
            stats.update(math.log(rent), weight)
        else:
            stats.update(math.log(rent), 1.0)
        parse_stats.rows_used += 1


def compute_parameters(
    paths: Iterable[Path],
    delimiter: str,
    columns: ColumnNames,
    qhousing_values: set[int],
    use_weights: bool,
) -> tuple[WeightedRunningStats, ParseStats]:
    stats = WeightedRunningStats()
    parse_stats = ParseStats()
    for path in paths:
        update_stats_from_file(
            stats,
            parse_stats,
            path,
            delimiter,
            columns,
            qhousing_values,
            use_weights,
        )
    return stats, parse_stats


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute log-normal rental price parameters from NMG CSV data.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more NMG CSV files (headered).",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="CSV delimiter (default: ',').",
    )
    parser.add_argument(
        "--qhousing-values",
        default="3,4",
        help="Comma-separated qhousing values to include (default: 3,4).",
    )
    parser.add_argument(
        "--no-weights",
        action="store_true",
        help="Disable we_factor weighting (treat each row equally).",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    paths = [Path(p) for p in args.files]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        parser.error(f"Missing files: {', '.join(missing)}")

    columns = ColumnNames()
    try:
        qhousing_values = parse_qhousing_values(args.qhousing_values)
    except ValueError as exc:
        parser.error(str(exc))
    use_weights = not args.no_weights

    stats, parse_stats = compute_parameters(
        paths,
        delimiter=args.delimiter,
        columns=columns,
        qhousing_values=qhousing_values,
        use_weights=use_weights,
    )

    if stats.weight_sum <= 0:
        raise SystemExit("No valid weighted rents found; cannot compute parameters.")

    mu = stats.mean
    sigma = stats.std()

    print("Computed log-normal rental parameters from NMG data")
    print(f"Files: {len(paths)}")
    print(f"Total rows read: {parse_stats.total_rows}")
    print(f"Rows used: {parse_stats.rows_used}")
    qhousing_label = ",".join(str(v) for v in sorted(qhousing_values))
    print(f"Rows with qhousing not in {{{qhousing_label}}}: {parse_stats.rows_non_private}")
    print(f"Rows with invalid qhousing: {parse_stats.rows_invalid_qhousing}")
    print(f"Rows with invalid rent: {parse_stats.rows_invalid_rent}")
    if use_weights:
        print(f"Rows with invalid weight: {parse_stats.rows_invalid_weight}")
    print(f"Rows missing required fields: {parse_stats.rows_missing_required}")
    print("")
    print(f"RENTAL_PRICES_SCALE = {format_float(mu)}")
    print(f"RENTAL_PRICES_SHAPE = {format_float(sigma)}")
    print("")
    print(f"Weighting: {'enabled' if use_weights else 'disabled'}")
    print(f"qhousing values: {{{qhousing_label}}}")


if __name__ == "__main__":
    main()
