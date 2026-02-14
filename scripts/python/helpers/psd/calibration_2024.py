"""Reusable 2024 PSD calibration helpers (downpayment + mortgage duration)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from scripts.python.helpers.psd.bins import (
    PsdBin,
    build_bins_from_category_masses,
    subtract_bin_masses,
)
from scripts.python.helpers.psd.metrics import (
    euclidean_distance,
    lognormal_params_from_synthetic_downpayment,
)
from scripts.python.helpers.psd.mortgage_duration import (
    TERM_GROUP,
    estimate_duration_years,
    term_bins_from_category_sales,
)
from scripts.python.helpers.psd.quarterly_long import (
    LongPsdRow,
    aggregate_category_sales,
)

FTB_LTV_GROUP = "Number of first-time-buyer sales by LTV ratio"
FTB_PROPERTY_GROUP = "Number of first-time buyer sales by property value"
ALL_LTV_GROUP = "Number of sales by loan-to-value (LTV) ratio"
ALL_PROPERTY_GROUP = "Number of sales by property value bands"
BORROWER_TYPE_GROUP = "Number of sales by type of borrower"
MEDIAN_LOAN_GROUP = "Median loan amounts (£)"
MEDIAN_LTV_GROUP = "Median loan-to-value (LTV) ratios (%)"
LTV_OPEN_CANDIDATES = (98.0, 99.0, 100.0)
SUPPORTED_DOWNPAYMENT_METHOD = "median_anchored_nonftb_independent"
SUPPORTED_TERM_METHODS = (
    "weighted_mean_round",
    "weighted_median_round",
    "modal_midpoint_round",
)


@dataclass(frozen=True)
class DownpaymentCandidate:
    ltv_open_upper: float
    property_open_upper_k: float
    coupling: str
    ftb_scale: float
    ftb_shape: float
    oo_scale: float
    oo_shape: float
    robust_distance: float


@dataclass(frozen=True)
class DownpaymentCalibrationResult:
    ftb_scale: float
    ftb_shape: float
    oo_scale: float
    oo_shape: float
    ltv_open_upper: float
    property_open_upper_k: float
    coupling: str
    property_tail_candidates_k: tuple[float, ...]
    robust_anchor_property_k: float
    candidate_count: int


@dataclass(frozen=True)
class MortgageDurationCalibrationResult:
    method: str
    open_top_year: int
    estimate_raw: float
    estimate_rounded: int
    excluded_share: float


@dataclass(frozen=True)
class ConsistencyCheckResult:
    name: str
    checked: bool
    matches: bool
    total_difference: float
    category_differences: dict[str, float]


def _component_median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("Cannot take median of empty list.")
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def derive_property_tail_candidates_k(
    rows: list[LongPsdRow],
    *,
    target_year: int,
) -> tuple[tuple[float, ...], float]:
    median_loan: dict[tuple[str, str], float] = {}
    median_ltv: dict[tuple[str, str], float] = {}
    ltv_weights: dict[tuple[str, str], float] = {}

    for row in rows:
        if row.period.year != target_year:
            continue
        key = (row.region, row.period.label)
        if row.group == MEDIAN_LOAN_GROUP:
            median_loan[key] = row.sales
        elif row.group == MEDIAN_LTV_GROUP:
            median_ltv[key] = row.sales
        elif row.group == ALL_LTV_GROUP:
            ltv_weights[key] = ltv_weights.get(key, 0.0) + row.sales

    property_estimates: list[tuple[float, float]] = []
    for key, loan_value in median_loan.items():
        if key not in median_ltv or key not in ltv_weights:
            continue
        ltv_value = median_ltv[key]
        if ltv_value <= 0.0:
            continue
        property_value = loan_value / (ltv_value / 100.0)
        property_estimates.append((property_value, ltv_weights[key]))

    if not property_estimates:
        return (300.0, 350.0, 400.0, 500.0, 600.0, 800.0, 1000.0), 300.0

    weight_sum = sum(weight for _, weight in property_estimates)
    weighted_mean_property = sum(value * weight for value, weight in property_estimates) / weight_sum
    anchor_k = max(300.0, weighted_mean_property / 1_000.0)

    start_k = math.ceil(anchor_k / 50.0) * 50.0
    steps = (0.0, 50.0, 100.0, 200.0, 300.0, 500.0, 700.0, 1_000.0)
    candidates = tuple(sorted({start_k + step for step in steps}))
    return candidates, anchor_k


def _build_downpayment_bins(rows: list[LongPsdRow], *, target_year: int) -> tuple[list[PsdBin], list[PsdBin], list[PsdBin], list[PsdBin]]:
    ftb_ltv_sales = aggregate_category_sales(rows, group=FTB_LTV_GROUP, year=target_year)
    ftb_property_sales = aggregate_category_sales(rows, group=FTB_PROPERTY_GROUP, year=target_year)
    all_ltv_sales = aggregate_category_sales(rows, group=ALL_LTV_GROUP, year=target_year)
    all_property_sales = aggregate_category_sales(rows, group=ALL_PROPERTY_GROUP, year=target_year)

    missing_groups = []
    if not ftb_ltv_sales:
        missing_groups.append(FTB_LTV_GROUP)
    if not ftb_property_sales:
        missing_groups.append(FTB_PROPERTY_GROUP)
    if not all_ltv_sales:
        missing_groups.append(ALL_LTV_GROUP)
    if not all_property_sales:
        missing_groups.append(ALL_PROPERTY_GROUP)
    if missing_groups:
        raise ValueError("Missing required group(s): " + ", ".join(missing_groups))

    ftb_ltv_bins = build_bins_from_category_masses(ftb_ltv_sales)
    ftb_property_bins = build_bins_from_category_masses(ftb_property_sales)
    all_ltv_bins = build_bins_from_category_masses(all_ltv_sales)
    all_property_bins = build_bins_from_category_masses(all_property_sales)
    if not ftb_ltv_bins or not ftb_property_bins or not all_ltv_bins or not all_property_bins:
        raise ValueError("Missing usable downpayment bins after category parsing.")
    return ftb_ltv_bins, ftb_property_bins, all_ltv_bins, all_property_bins


def calibrate_downpayment_2024(
    rows: list[LongPsdRow],
    *,
    target_year: int,
    within_bin_points: int,
    method_name: str,
) -> DownpaymentCalibrationResult:
    if method_name != SUPPORTED_DOWNPAYMENT_METHOD:
        raise ValueError(f"Unsupported downpayment method: {method_name}")

    ftb_ltv_bins, ftb_property_bins, all_ltv_bins, all_property_bins = _build_downpayment_bins(
        rows,
        target_year=target_year,
    )
    oo_ltv_bins = subtract_bin_masses(all_ltv_bins, ftb_ltv_bins)
    oo_property_bins = subtract_bin_masses(all_property_bins, ftb_property_bins)
    if not oo_ltv_bins or not oo_property_bins:
        raise ValueError("OO proxy bins are empty after all-minus-FTB subtraction.")

    property_tail_candidates_k, anchor_k = derive_property_tail_candidates_k(
        rows,
        target_year=target_year,
    )
    coupling = "independent"

    candidates: list[DownpaymentCandidate] = []
    for ltv_open_upper in LTV_OPEN_CANDIDATES:
        for property_open_upper_k in property_tail_candidates_k:
            ftb_scale, ftb_shape = lognormal_params_from_synthetic_downpayment(
                ftb_ltv_bins,
                ftb_property_bins,
                ltv_open_upper=ltv_open_upper,
                property_open_upper_k=property_open_upper_k,
                coupling=coupling,
                within_bin_points=within_bin_points,
            )
            oo_scale, oo_shape = lognormal_params_from_synthetic_downpayment(
                oo_ltv_bins,
                oo_property_bins,
                ltv_open_upper=ltv_open_upper,
                property_open_upper_k=property_open_upper_k,
                coupling=coupling,
                within_bin_points=within_bin_points,
            )
            candidates.append(
                DownpaymentCandidate(
                    ltv_open_upper=ltv_open_upper,
                    property_open_upper_k=property_open_upper_k,
                    coupling=coupling,
                    ftb_scale=ftb_scale,
                    ftb_shape=ftb_shape,
                    oo_scale=oo_scale,
                    oo_shape=oo_shape,
                    robust_distance=0.0,
                )
            )

    med_vector = (
        _component_median([item.ftb_scale for item in candidates]),
        _component_median([item.ftb_shape for item in candidates]),
        _component_median([item.oo_scale for item in candidates]),
        _component_median([item.oo_shape for item in candidates]),
    )

    scored: list[DownpaymentCandidate] = []
    for candidate in candidates:
        distance = euclidean_distance(
            (candidate.ftb_scale, candidate.ftb_shape, candidate.oo_scale, candidate.oo_shape),
            med_vector,
        )
        scored.append(
            DownpaymentCandidate(
                ltv_open_upper=candidate.ltv_open_upper,
                property_open_upper_k=candidate.property_open_upper_k,
                coupling=candidate.coupling,
                ftb_scale=candidate.ftb_scale,
                ftb_shape=candidate.ftb_shape,
                oo_scale=candidate.oo_scale,
                oo_shape=candidate.oo_shape,
                robust_distance=distance,
            )
        )

    median_property_candidate = _component_median([item.property_open_upper_k for item in scored])
    scored.sort(
        key=lambda item: (
            item.robust_distance,
            abs(item.property_open_upper_k - median_property_candidate),
            item.ltv_open_upper,
            item.property_open_upper_k,
        )
    )
    selected = scored[0]

    return DownpaymentCalibrationResult(
        ftb_scale=selected.ftb_scale,
        ftb_shape=selected.ftb_shape,
        oo_scale=selected.oo_scale,
        oo_shape=selected.oo_shape,
        ltv_open_upper=selected.ltv_open_upper,
        property_open_upper_k=selected.property_open_upper_k,
        coupling=selected.coupling,
        property_tail_candidates_k=property_tail_candidates_k,
        robust_anchor_property_k=anchor_k,
        candidate_count=len(scored),
    )


def calibrate_mortgage_duration_2024(
    rows: list[LongPsdRow],
    *,
    target_year: int,
    method_name: str,
    open_top_year: int,
) -> MortgageDurationCalibrationResult:
    if method_name not in SUPPORTED_TERM_METHODS:
        raise ValueError(
            f"Unsupported term method: {method_name}. "
            f"Expected one of: {', '.join(SUPPORTED_TERM_METHODS)}"
        )
    if open_top_year <= 35:
        raise ValueError("term open-top year must be > 35.")

    base_method = method_name.replace("_round", "")
    term_sales = aggregate_category_sales(rows, group=TERM_GROUP, year=target_year)
    if not term_sales:
        raise ValueError(f"Missing term-band rows for year {target_year}.")
    term_bins, excluded_share = term_bins_from_category_sales(term_sales)
    estimate_raw = estimate_duration_years(
        term_bins,
        method_name=base_method,
        open_top_year=open_top_year,
    )
    return MortgageDurationCalibrationResult(
        method=method_name,
        open_top_year=open_top_year,
        estimate_raw=estimate_raw,
        estimate_rounded=round(estimate_raw),
        excluded_share=excluded_share,
    )


def compare_quarterly_monthly_consistency(
    quarterly_rows: list[LongPsdRow],
    *,
    target_year: int,
    monthly_p1_rows: list[LongPsdRow] | None,
    monthly_p2_rows: list[LongPsdRow] | None,
) -> list[ConsistencyCheckResult]:
    checks: list[ConsistencyCheckResult] = []

    if monthly_p1_rows is None:
        checks.append(
            ConsistencyCheckResult(
                name="borrower_totals",
                checked=False,
                matches=False,
                total_difference=float("nan"),
                category_differences={},
            )
        )
    else:
        quarterly = aggregate_category_sales(
            quarterly_rows,
            group=BORROWER_TYPE_GROUP,
            year=target_year,
        )
        monthly: dict[str, float] = {}
        for row in monthly_p1_rows:
            if row.period.year != target_year:
                continue
            monthly[row.category] = monthly.get(row.category, 0.0) + row.sales
        categories = sorted(set(quarterly) | set(monthly))
        diffs = {category: quarterly.get(category, 0.0) - monthly.get(category, 0.0) for category in categories}
        total_diff = sum(diffs.values())
        matches = all(abs(value) < 1e-6 for value in diffs.values())
        checks.append(
            ConsistencyCheckResult(
                name="borrower_totals",
                checked=True,
                matches=matches,
                total_difference=total_diff,
                category_differences=diffs,
            )
        )

    if monthly_p2_rows is None:
        checks.append(
            ConsistencyCheckResult(
                name="ltv_totals",
                checked=False,
                matches=False,
                total_difference=float("nan"),
                category_differences={},
            )
        )
    else:
        quarterly = aggregate_category_sales(
            quarterly_rows,
            group=ALL_LTV_GROUP,
            year=target_year,
        )
        monthly: dict[str, float] = {}
        for row in monthly_p2_rows:
            if row.period.year != target_year:
                continue
            if not row.category:
                continue
            monthly[row.category] = monthly.get(row.category, 0.0) + row.sales
        categories = sorted(set(quarterly) | set(monthly))
        diffs = {category: quarterly.get(category, 0.0) - monthly.get(category, 0.0) for category in categories}
        total_diff = sum(diffs.values())
        matches = all(abs(value) < 1e-6 for value in diffs.values())
        checks.append(
            ConsistencyCheckResult(
                name="ltv_totals",
                checked=True,
                matches=matches,
                total_difference=total_diff,
                category_differences=diffs,
            )
        )

    return checks


__all__ = [
    "ALL_LTV_GROUP",
    "BORROWER_TYPE_GROUP",
    "ConsistencyCheckResult",
    "DownpaymentCalibrationResult",
    "FTB_LTV_GROUP",
    "FTB_PROPERTY_GROUP",
    "MortgageDurationCalibrationResult",
    "SUPPORTED_DOWNPAYMENT_METHOD",
    "SUPPORTED_TERM_METHODS",
    "calibrate_downpayment_2024",
    "calibrate_mortgage_duration_2024",
    "compare_quarterly_monthly_consistency",
    "derive_property_tail_candidates_k",
]
