#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute log-normal house price parameters from one or more UK PPD CSV files.

PPD CSV format (headerless):
transaction_unique_identifier,price,date_of_transfer,postcode,property_type,
old_new,duration,paon,saon,street,locality,town_city,district,county,
ppd_category_type,record_status

Outputs:
  HOUSE_PRICES_SCALE (mu)  = mean of log(price)
  HOUSE_PRICES_SHAPE (sigma) = std dev of log(price)

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


@dataclass
class RunningStats:
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    min_value: float = math.inf
    max_value: float = -math.inf

    def update(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2
        if value < self.min_value:
            self.min_value = value
        if value > self.max_value:
            self.max_value = value

    def variance(self) -> float:
        if self.count < 2:
            return 0.0
        return self.m2 / (self.count - 1)

    def std(self) -> float:
        return math.sqrt(self.variance())


@dataclass
class ParseStats:
    total_rows: int = 0
    skipped_rows: int = 0
    invalid_rows: int = 0
    valid_prices: int = 0


def iter_prices(
    path: Path,
    price_index: int,
    delimiter: str,
    skip_rows: int,
) -> Iterator[float]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        for row_index, row in enumerate(reader):
            if row_index < skip_rows:
                continue
            if len(row) <= price_index:
                yield math.nan
                continue
            raw = row[price_index].strip()
            if not raw:
                yield math.nan
                continue
            try:
                price = float(raw)
            except ValueError:
                yield math.nan
                continue
            if price <= 0:
                yield math.nan
                continue
            yield price


def update_stats_from_file(
    stats: RunningStats,
    parse_stats: ParseStats,
    path: Path,
    price_index: int,
    delimiter: str,
    skip_rows: int,
) -> None:
    for price in iter_prices(path, price_index, delimiter, skip_rows):
        parse_stats.total_rows += 1
        if math.isnan(price):
            parse_stats.invalid_rows += 1
            continue
        parse_stats.valid_prices += 1
        stats.update(math.log(price))


def compute_parameters(
    paths: Iterable[Path],
    price_index: int,
    delimiter: str,
    skip_rows: int,
) -> tuple[RunningStats, ParseStats]:
    stats = RunningStats()
    parse_stats = ParseStats()
    for path in paths:
        update_stats_from_file(
            stats, parse_stats, path, price_index, delimiter, skip_rows
        )
    return stats, parse_stats


def format_float(value: float) -> str:
    return f"{value:.10f}".rstrip("0").rstrip(".")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute log-normal house price parameters from PPD CSV files.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more PPD CSV files (headerless).",
    )
    parser.add_argument(
        "--price-index",
        type=int,
        default=1,
        help="Zero-based index of the price column (default: 1).",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="CSV delimiter (default: ',').",
    )
    parser.add_argument(
        "--skip-rows",
        type=int,
        default=0,
        help="Number of initial rows to skip in each file (default: 0).",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    paths = [Path(p) for p in args.files]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        parser.error(f"Missing files: {', '.join(missing)}")

    stats, parse_stats = compute_parameters(
        paths,
        price_index=args.price_index,
        delimiter=args.delimiter,
        skip_rows=args.skip_rows,
    )

    if stats.count == 0:
        raise SystemExit("No valid prices found; cannot compute parameters.")

    mu = stats.mean
    sigma = stats.std()

    print("Computed log-normal parameters from PPD data")
    print(f"Files: {len(paths)}")
    print(f"Total rows read: {parse_stats.total_rows}")
    if args.skip_rows:
        print(f"Rows skipped per file: {args.skip_rows}")
    print(f"Valid prices: {parse_stats.valid_prices}")
    print(f"Invalid/empty rows: {parse_stats.invalid_rows}")
    print()
    print(f"HOUSE_PRICES_SCALE = {format_float(mu)}")
    print(f"HOUSE_PRICES_SHAPE = {format_float(sigma)}")


if __name__ == "__main__":
    main()
