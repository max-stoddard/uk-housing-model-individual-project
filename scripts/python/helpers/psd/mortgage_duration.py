"""Reusable mortgage-duration estimation helpers for PSD term-band data."""

from __future__ import annotations

import math
from dataclasses import dataclass

from scripts.python.helpers.psd.bins import (
    PsdBin,
    build_bins_from_category_masses,
    sort_bins_for_quantile,
)
from scripts.python.helpers.psd.metrics import binned_weighted_quantile
from scripts.python.helpers.psd.quarterly_long import (
    LongPsdRow,
    aggregate_category_sales,
    aggregate_category_sales_by_period,
)

TERM_GROUP = "Number of sales by mortgage term"
UNSPECIFIED_TERM_LABEL = "Mortgage Term Bands - Unspecified"
METHOD_CHOICES = ("weighted_mean", "weighted_median", "modal_midpoint")
DEFAULT_TOP_OPEN_YEARS = (40, 45, 50)
DISCONTINUITY_PENALTY = {
    "weighted_median": 0,
    "weighted_mean": 1,
    "modal_midpoint": 2,
}


@dataclass(frozen=True)
class MortgageDurationResult:
    method_name: str
    open_top_assumption: int
    method_id: str
    year_estimate_raw: float
    year_estimate_rounded: int
    quarter_mean: float
    quarter_std: float
    sensitivity_range: float
    legacy_distance_to_25: float
    status: str
    quarter_estimates_rounded: tuple[int, ...]
    excluded_share: float


def std(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((item - mean) ** 2 for item in values) / len(values)
    return math.sqrt(variance)


def term_bins_from_category_sales(category_sales: dict[str, float]) -> tuple[list[PsdBin], float]:
    sales = dict(category_sales)
    total_with_unspecified = sum(sales.values())
    unspecified_mass = sales.pop(UNSPECIFIED_TERM_LABEL, 0.0)
    term_bins = build_bins_from_category_masses(sales)
    if not term_bins:
        raise ValueError("No usable mortgage-term bins after filtering.")

    excluded_share = 0.0
    if total_with_unspecified > 0.0:
        excluded_share = unspecified_mass / total_with_unspecified
    return term_bins, excluded_share


def weighted_mean_duration(bins: list[PsdBin], open_top_year: int) -> float:
    total_mass = sum(item.mass for item in bins)
    if total_mass <= 0.0:
        raise ValueError("Cannot compute weighted mean from empty/zero-mass bins.")
    weighted_sum = 0.0
    for item in bins:
        lower = 0.0 if item.lower is None else item.lower
        upper = float(open_top_year) if item.upper is None else item.upper
        midpoint = (lower + upper) / 2.0
        weighted_sum += midpoint * item.mass
    return weighted_sum / total_mass


def modal_midpoint_duration(bins: list[PsdBin], open_top_year: int) -> float:
    if not bins:
        raise ValueError("Cannot compute modal midpoint from empty bins.")
    sorted_bins = sort_bins_for_quantile(bins)
    modal_bin = max(sorted_bins, key=lambda item: (item.mass, -(item.lower or 0.0)))
    lower = 0.0 if modal_bin.lower is None else modal_bin.lower
    upper = float(open_top_year) if modal_bin.upper is None else modal_bin.upper
    return (lower + upper) / 2.0


def estimate_duration_years(
    bins: list[PsdBin],
    *,
    method_name: str,
    open_top_year: int,
) -> float:
    if method_name == "weighted_mean":
        return weighted_mean_duration(bins, open_top_year)
    if method_name == "weighted_median":
        return binned_weighted_quantile(
            bins,
            0.5,
            float(open_top_year),
            interpolation="linear",
        )
    if method_name == "modal_midpoint":
        return modal_midpoint_duration(bins, open_top_year)
    raise ValueError(f"Unsupported method: {method_name}")


def run_mortgage_duration_search(
    rows: list[LongPsdRow],
    *,
    target_year: int,
    top_open_years: tuple[int, ...],
    methods: tuple[str, ...],
) -> tuple[list[MortgageDurationResult], tuple[str, ...]]:
    quarterly_maps = aggregate_category_sales_by_period(
        rows,
        group=TERM_GROUP,
        year=target_year,
    )
    quarter_labels = sorted([label for label in quarterly_maps if "Q" in label])
    if not quarter_labels:
        raise ValueError(f"No quarterly mortgage-term rows found for {target_year}.")

    year_sales = aggregate_category_sales(
        rows,
        group=TERM_GROUP,
        year=target_year,
        quarter=None,
    )
    year_bins, year_excluded_share = term_bins_from_category_sales(year_sales)

    quarter_bins: dict[int, list[PsdBin]] = {}
    for label in quarter_labels:
        quarter_number = int(label.split("Q", 1)[1].strip())
        quarter_sales = aggregate_category_sales(
            rows,
            group=TERM_GROUP,
            year=target_year,
            quarter=quarter_number,
        )
        bins, _ = term_bins_from_category_sales(quarter_sales)
        quarter_bins[quarter_number] = bins

    method_to_raw_estimates: dict[str, list[float]] = {method: [] for method in methods}
    provisional: list[MortgageDurationResult] = []
    for method in methods:
        for open_top_year in top_open_years:
            year_raw = estimate_duration_years(
                year_bins,
                method_name=method,
                open_top_year=open_top_year,
            )
            quarter_raw: list[float] = []
            quarter_rounded: list[int] = []
            for quarter_number in sorted(quarter_bins.keys()):
                quarter_estimate = estimate_duration_years(
                    quarter_bins[quarter_number],
                    method_name=method,
                    open_top_year=open_top_year,
                )
                quarter_raw.append(quarter_estimate)
                quarter_rounded.append(round(quarter_estimate))

            method_to_raw_estimates[method].append(year_raw)
            provisional.append(
                MortgageDurationResult(
                    method_name=method,
                    open_top_assumption=open_top_year,
                    method_id=f"{method}_round|open_top={open_top_year}",
                    year_estimate_raw=year_raw,
                    year_estimate_rounded=round(year_raw),
                    quarter_mean=sum(quarter_raw) / len(quarter_raw),
                    quarter_std=std([float(value) for value in quarter_rounded]),
                    sensitivity_range=0.0,
                    legacy_distance_to_25=abs(round(year_raw) - 25.0),
                    status="candidate",
                    quarter_estimates_rounded=tuple(quarter_rounded),
                    excluded_share=year_excluded_share,
                )
            )

    method_sensitivity = {
        method: max(values) - min(values)
        for method, values in method_to_raw_estimates.items()
    }
    finalized: list[MortgageDurationResult] = []
    for result in provisional:
        finalized.append(
            MortgageDurationResult(
                method_name=result.method_name,
                open_top_assumption=result.open_top_assumption,
                method_id=result.method_id,
                year_estimate_raw=result.year_estimate_raw,
                year_estimate_rounded=result.year_estimate_rounded,
                quarter_mean=result.quarter_mean,
                quarter_std=result.quarter_std,
                sensitivity_range=method_sensitivity[result.method_name],
                legacy_distance_to_25=result.legacy_distance_to_25,
                status=result.status,
                quarter_estimates_rounded=result.quarter_estimates_rounded,
                excluded_share=result.excluded_share,
            )
        )

    finalized.sort(
        key=lambda item: (
            item.quarter_std,
            item.sensitivity_range,
            DISCONTINUITY_PENALTY[item.method_name],
            item.method_id,
        )
    )
    return finalized, tuple(quarter_labels)


__all__ = [
    "DEFAULT_TOP_OPEN_YEARS",
    "DISCONTINUITY_PENALTY",
    "METHOD_CHOICES",
    "MortgageDurationResult",
    "TERM_GROUP",
    "UNSPECIFIED_TERM_LABEL",
    "estimate_duration_years",
    "run_mortgage_duration_search",
    "std",
    "term_bins_from_category_sales",
]
