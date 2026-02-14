#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reusable method-search helpers for PPD house-price lognormal reproduction.

@author: Max Stoddard
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from scripts.python.helpers.common.math_stats import euclidean_distance_2d

PPD_PRICE_INDEX = 1
PPD_DATE_INDEX = 2
PPD_CATEGORY_INDEX = 14
PPD_STATUS_INDEX = 15

CATEGORY_MODES = ("all", "a_only")
STATUS_MODES = ("all", "a_only")
YEAR_MODES = ("all_rows", "transfer_year_equals_target")
STD_MODES = ("population", "sample")
DEFAULT_TRIM_FRACTIONS = (0.0, 0.001)


@dataclass(frozen=True)
class PpdRow:
    price: float
    transfer_year: int | None
    ppd_category_type: str
    record_status: str


@dataclass
class PpdParseStats:
    total_rows: int = 0
    skipped_rows: int = 0
    rows_missing_required_fields: int = 0
    rows_invalid_price: int = 0
    rows_non_positive_price: int = 0
    rows_invalid_transfer_year: int = 0
    rows_loaded: int = 0


@dataclass(frozen=True)
class MethodSpec:
    category_mode: str
    status_mode: str
    year_mode: str
    std_mode: str
    trim_fraction: float

    @property
    def method_id(self) -> str:
        return (
            f"category={self.category_mode}|status={self.status_mode}|year={self.year_mode}|"
            f"std={self.std_mode}|trim={self.trim_fraction:g}"
        )


@dataclass(frozen=True)
class MethodResult:
    method: MethodSpec
    mu: float
    sigma: float
    distance: float
    abs_d_mu: float
    abs_d_sigma: float
    rows_after_category: int
    rows_after_status: int
    rows_after_year: int
    rows_used: int
    trimmed_each_side: int


@dataclass(frozen=True)
class SearchOutput:
    target_scale: float
    target_shape: float
    parse_stats: PpdParseStats
    results: list[MethodResult]
    skipped_methods: int


def _parse_transfer_year(raw_transfer_date: str) -> int | None:
    value = raw_transfer_date.strip()
    if len(value) < 4:
        return None
    year_token = value[:4]
    if not year_token.isdigit():
        return None
    return int(year_token)


def load_ppd_rows(
    path: Path,
    *,
    delimiter: str = ",",
    skip_rows: int = 0,
    price_index: int = PPD_PRICE_INDEX,
    transfer_date_index: int = PPD_DATE_INDEX,
    category_index: int = PPD_CATEGORY_INDEX,
    status_index: int = PPD_STATUS_INDEX,
) -> tuple[list[PpdRow], PpdParseStats]:
    max_required_index = max(price_index, transfer_date_index, category_index, status_index)
    parse_stats = PpdParseStats()
    rows: list[PpdRow] = []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        for row_index, row in enumerate(reader):
            parse_stats.total_rows += 1
            if row_index < skip_rows:
                parse_stats.skipped_rows += 1
                continue
            if len(row) <= max_required_index:
                parse_stats.rows_missing_required_fields += 1
                continue

            price_raw = row[price_index].strip()
            if not price_raw:
                parse_stats.rows_invalid_price += 1
                continue
            try:
                price = float(price_raw)
            except ValueError:
                parse_stats.rows_invalid_price += 1
                continue
            if price <= 0:
                parse_stats.rows_non_positive_price += 1
                continue

            transfer_year = _parse_transfer_year(row[transfer_date_index])
            if transfer_year is None:
                parse_stats.rows_invalid_transfer_year += 1

            rows.append(
                PpdRow(
                    price=price,
                    transfer_year=transfer_year,
                    ppd_category_type=row[category_index].strip(),
                    record_status=row[status_index].strip(),
                )
            )
            parse_stats.rows_loaded += 1

    return rows, parse_stats


def build_method_specs(
    trim_fractions: Iterable[float] = DEFAULT_TRIM_FRACTIONS,
) -> list[MethodSpec]:
    methods: list[MethodSpec] = []
    for category_mode in CATEGORY_MODES:
        for status_mode in STATUS_MODES:
            for year_mode in YEAR_MODES:
                for std_mode in STD_MODES:
                    for trim_fraction in trim_fractions:
                        methods.append(
                            MethodSpec(
                                category_mode=category_mode,
                                status_mode=status_mode,
                                year_mode=year_mode,
                                std_mode=std_mode,
                                trim_fraction=float(trim_fraction),
                            )
                        )
    return methods


def _passes_category_mode(row: PpdRow, mode: str) -> bool:
    if mode == "all":
        return True
    if mode == "a_only":
        return row.ppd_category_type == "A"
    raise ValueError(f"Unsupported category_mode: {mode}")


def _passes_status_mode(row: PpdRow, mode: str) -> bool:
    if mode == "all":
        return True
    if mode == "a_only":
        return row.record_status == "A"
    raise ValueError(f"Unsupported status_mode: {mode}")


def _passes_year_mode(row: PpdRow, mode: str, target_year: int) -> bool:
    if mode == "all_rows":
        return True
    if mode == "transfer_year_equals_target":
        return row.transfer_year == target_year
    raise ValueError(f"Unsupported year_mode: {mode}")


def _trim_prices(prices: list[float], trim_fraction: float) -> tuple[list[float], int]:
    if trim_fraction < 0.0 or trim_fraction >= 0.5:
        raise ValueError(f"trim_fraction must be in [0, 0.5): {trim_fraction}")
    if not prices:
        raise ValueError("No prices provided for trimming.")

    if trim_fraction == 0.0:
        return list(prices), 0

    sorted_prices = sorted(prices)
    trim_count = int(len(sorted_prices) * trim_fraction)
    if trim_count == 0:
        return sorted_prices, 0
    if 2 * trim_count >= len(sorted_prices):
        raise ValueError("Trim fraction removes all rows.")

    return sorted_prices[trim_count : len(sorted_prices) - trim_count], trim_count


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _std(values: list[float], mode: str) -> float:
    if mode not in STD_MODES:
        raise ValueError(f"Unsupported std_mode: {mode}")
    if not values:
        raise ValueError("No values provided for standard deviation.")

    mean = _mean(values)
    if mode == "population":
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return math.sqrt(variance)

    if len(values) < 2:
        return 0.0
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def evaluate_method(
    rows: Iterable[PpdRow],
    *,
    method: MethodSpec,
    target_scale: float,
    target_shape: float,
    target_year: int,
) -> MethodResult:
    rows_after_category = [row for row in rows if _passes_category_mode(row, method.category_mode)]
    rows_after_status = [row for row in rows_after_category if _passes_status_mode(row, method.status_mode)]
    rows_after_year = [
        row
        for row in rows_after_status
        if _passes_year_mode(row, method.year_mode, target_year)
    ]
    if not rows_after_year:
        raise ValueError(f"No rows remain after filters for {method.method_id}.")

    trimmed_prices, trimmed_each_side = _trim_prices(
        [row.price for row in rows_after_year],
        method.trim_fraction,
    )
    if not trimmed_prices:
        raise ValueError(f"No rows remain after trimming for {method.method_id}.")

    log_prices = [math.log(price) for price in trimmed_prices]
    mu = _mean(log_prices)
    sigma = _std(log_prices, method.std_mode)
    abs_d_mu = abs(mu - target_scale)
    abs_d_sigma = abs(sigma - target_shape)
    distance = euclidean_distance_2d(mu, sigma, target_scale, target_shape)

    return MethodResult(
        method=method,
        mu=mu,
        sigma=sigma,
        distance=distance,
        abs_d_mu=abs_d_mu,
        abs_d_sigma=abs_d_sigma,
        rows_after_category=len(rows_after_category),
        rows_after_status=len(rows_after_status),
        rows_after_year=len(rows_after_year),
        rows_used=len(trimmed_prices),
        trimmed_each_side=trimmed_each_side,
    )


def rank_method_results(results: Iterable[MethodResult]) -> list[MethodResult]:
    return sorted(
        results,
        key=lambda result: (
            result.distance,
            result.abs_d_mu,
            result.abs_d_sigma,
            result.method.method_id,
        ),
    )


def run_method_search(
    rows: list[PpdRow],
    *,
    target_scale: float,
    target_shape: float,
    target_year: int,
    parse_stats: PpdParseStats,
    trim_fractions: Iterable[float] = DEFAULT_TRIM_FRACTIONS,
) -> SearchOutput:
    results: list[MethodResult] = []
    skipped_methods = 0
    for method in build_method_specs(trim_fractions):
        try:
            result = evaluate_method(
                rows,
                method=method,
                target_scale=target_scale,
                target_shape=target_shape,
                target_year=target_year,
            )
            results.append(result)
        except ValueError:
            skipped_methods += 1

    if not results:
        raise ValueError("No method produced a valid estimate.")

    ranked = rank_method_results(results)
    return SearchOutput(
        target_scale=target_scale,
        target_shape=target_shape,
        parse_stats=parse_stats,
        results=ranked,
        skipped_methods=skipped_methods,
    )

