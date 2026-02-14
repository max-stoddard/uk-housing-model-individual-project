#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reusable method-search helpers for PSD/PPD buy-budget calibration.

@author: Max Stoddard
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from scripts.python.helpers.common.io_properties import read_properties
from scripts.python.helpers.common.math_stats import euclidean_distance_2d
from scripts.python.helpers.psd.bins import (
    PsdBin,
    build_bins_from_category_masses,
    build_bins_from_labeled_rows,
)
from scripts.python.helpers.psd.quarterly_long import (
    aggregate_category_sales,
    load_quarterly_psd_rows,
)
from scripts.python.helpers.psd.tables import (
    get_labeled_section_rows,
    get_year_column,
    load_psd_table,
)

METHOD_FAMILY_PSD_LOG_OLS_RESIDUAL = "psd_log_ols_residual"
METHOD_FAMILY_PSD_LOG_OLS_PPD_MOMENT_CLOSURE = "psd_log_ols_ppd_moment_closure"
METHOD_FAMILY_PSD_LOG_OLS_ROBUST_MU = "psd_log_ols_robust_mu"
METHOD_FAMILY_CHOICES = (
    METHOD_FAMILY_PSD_LOG_OLS_RESIDUAL,
    METHOD_FAMILY_PSD_LOG_OLS_PPD_MOMENT_CLOSURE,
    METHOD_FAMILY_PSD_LOG_OLS_ROBUST_MU,
)

COUPLING_CHOICES = ("independent", "comonotonic", "countermonotonic")

TARGET_BUY_SCALE_KEY = "BUY_SCALE"
TARGET_BUY_EXPONENT_KEY = "BUY_EXPONENT"
TARGET_BUY_MU_KEY = "BUY_MU"
TARGET_BUY_SIGMA_KEY = "BUY_SIGMA"

LEGACY_2011_LOAN_GROUP_SECTION = "3.1"
LEGACY_2011_LTI_SINGLE_SECTION = "3.7.1"
LEGACY_2011_LTI_JOINT_SECTION = "3.7.2"
LEGACY_2011_PROPERTY_GROUP_SECTION = "5.1"

MODERN_2024_INCOME_GROUP = "Number of sales by gross income bands"
MODERN_2024_PROPERTY_GROUP = "Number of sales by property value bands"
MODERN_2024_LOAN_GROUP = "Number of sales by loan amount bands"
MODERN_2024_LTV_GROUP = "Number of sales by loan-to-value (LTV) ratio"
MODERN_2024_BORROWER_GROUP = "Number of sales by type of borrower"

# Prevent scale dominance while avoiding over-weighting near-zero targets.
NORM_FLOOR_SCALE = 10.0
NORM_FLOOR_EXPONENT = 0.1
NORM_FLOOR_MU = 0.05
NORM_FLOOR_SIGMA = 0.05


@dataclass(frozen=True)
class MethodDiagnostics:
    rows_income_mass: float
    rows_price_mass: float
    paired_sample_size: int
    trimmed_each_side: int
    ppd_rows_used: int
    sigma2_clamped_to_zero: bool
    mu_upper_trimmed_count: int = 0


@dataclass(frozen=True)
class PpdMomentStats:
    rows_total: int
    rows_used: int
    mean_log_price: float
    variance_log_price: float


@dataclass(frozen=True)
class BuyMethodSpec:
    family: str
    loan_to_income_coupling: str
    income_to_price_coupling: str
    loan_open_upper_k: float
    lti_open_upper: float
    lti_open_lower: float
    income_open_upper_k: float
    property_open_upper_k: float
    trim_fraction: float
    within_bin_points: int
    quantile_grid_size: int
    mu_upper_trim_fraction: float = 0.0

    @property
    def method_id(self) -> str:
        return (
            f"family={self.family}|"
            f"loan_to_income={self.loan_to_income_coupling}|"
            f"income_to_price={self.income_to_price_coupling}|"
            f"loan_open_k={self.loan_open_upper_k:g}|"
            f"lti_open={self.lti_open_upper:g}|"
            f"lti_floor={self.lti_open_lower:g}|"
            f"income_open_k={self.income_open_upper_k:g}|"
            f"property_open_k={self.property_open_upper_k:g}|"
            f"trim={self.trim_fraction:g}|"
            f"within_bin_points={self.within_bin_points}|"
            f"grid={self.quantile_grid_size}|"
            f"mu_hi_trim={self.mu_upper_trim_fraction:g}"
        )


@dataclass(frozen=True)
class BuyMethodResult:
    method: BuyMethodSpec
    buy_scale: float
    buy_exponent: float
    buy_mu: float
    buy_sigma: float
    distance_norm: float
    abs_d_scale_norm: float
    abs_d_exponent_norm: float
    abs_d_mu_norm: float
    abs_d_sigma_norm: float
    diagnostics: MethodDiagnostics


@dataclass(frozen=True)
class BuySeedEstimate:
    buy_scale: float
    buy_exponent: float
    buy_mu: float
    buy_sigma: float
    method_id: str


@dataclass(frozen=True)
class BuySearchOutput:
    target_buy_scale: float
    target_buy_exponent: float
    target_buy_mu: float
    target_buy_sigma: float
    initial_seed: BuySeedEstimate
    ppd_stats: PpdMomentStats
    legacy_diagnostics: dict[str, float]
    results: list[BuyMethodResult]
    skipped_methods: int


@dataclass(frozen=True)
class BuyCalibrationOutput:
    method: BuyMethodSpec
    buy_scale: float
    buy_exponent: float
    buy_mu: float
    buy_sigma: float
    diagnostics: MethodDiagnostics
    ppd_stats: PpdMomentStats
    modern_diagnostics: dict[str, float]


@dataclass(frozen=True)
class SyntheticMarginals:
    income_values: list[float]
    income_weights: list[float]
    price_values: list[float]
    price_weights: list[float]
    diagnostics: dict[str, float]


def _target_denominators(
    target_scale: float,
    target_exponent: float,
    target_mu: float,
    target_sigma: float,
) -> tuple[float, float, float, float]:
    return (
        max(abs(target_scale), NORM_FLOOR_SCALE),
        max(abs(target_exponent), NORM_FLOOR_EXPONENT),
        max(abs(target_mu), NORM_FLOOR_MU),
        max(abs(target_sigma), NORM_FLOOR_SIGMA),
    )


def _weighted_mean(values: Iterable[float], weights: Iterable[float]) -> float:
    value_list = list(values)
    weight_list = list(weights)
    weight_sum = sum(weight_list)
    if weight_sum <= 0.0:
        raise ValueError("Weighted mean requires positive total weight.")
    return sum(value * weight for value, weight in zip(value_list, weight_list)) / weight_sum


def _weighted_variance(values: Iterable[float], weights: Iterable[float], mean: float | None = None) -> float:
    value_list = list(values)
    weight_list = list(weights)
    weight_sum = sum(weight_list)
    if weight_sum <= 0.0:
        raise ValueError("Weighted variance requires positive total weight.")
    center = _weighted_mean(value_list, weight_list) if mean is None else mean
    return (
        sum(weight * (value - center) ** 2 for value, weight in zip(value_list, weight_list)) / weight_sum
    )


def _weighted_quantile_series(values: list[float], weights: list[float], n_points: int) -> list[float]:
    if n_points <= 0:
        raise ValueError("n_points must be positive.")
    ordered = sorted(zip(values, weights), key=lambda item: item[0])
    cumulative: list[float] = []
    levels: list[float] = []
    total = 0.0
    for value, weight in ordered:
        total += weight
        cumulative.append(total)
        levels.append(value)
    if total <= 0.0:
        raise ValueError("Quantile series requires positive total weight.")

    output: list[float] = []
    pointer = 0
    for index in range(n_points):
        threshold = ((index + 0.5) / n_points) * total
        while pointer < len(cumulative) - 1 and threshold > cumulative[pointer]:
            pointer += 1
        output.append(levels[pointer])
    return output


def _pair_series(
    left_values: list[float],
    left_weights: list[float],
    right_values: list[float],
    right_weights: list[float],
    n_points: int,
    coupling: str,
) -> tuple[list[float], list[float]]:
    left_series = _weighted_quantile_series(left_values, left_weights, n_points)
    right_series = _weighted_quantile_series(right_values, right_weights, n_points)

    if coupling == "comonotonic":
        return left_series, right_series
    if coupling == "countermonotonic":
        return left_series, list(reversed(right_series))
    if coupling == "independent":
        # Deterministic cycle-shift to keep outputs reproducible.
        shift = n_points // 3
        shifted = right_series[shift:] + right_series[:shift]
        return left_series, shifted
    raise ValueError(f"Unsupported coupling: {coupling}")


def _trim_paired(
    income_values: list[float],
    price_values: list[float],
    trim_fraction: float,
) -> tuple[list[float], list[float], int]:
    if trim_fraction < 0.0 or trim_fraction >= 0.5:
        raise ValueError(f"trim_fraction must be in [0, 0.5): {trim_fraction}")
    if len(income_values) != len(price_values):
        raise ValueError("income and price paired series size mismatch.")
    if not income_values:
        raise ValueError("Cannot trim empty paired series.")
    if trim_fraction == 0.0:
        return list(income_values), list(price_values), 0

    paired = list(zip(income_values, price_values))
    paired.sort(key=lambda item: item[1])
    trim_count = int(len(paired) * trim_fraction)
    if trim_count == 0:
        return [item[0] for item in paired], [item[1] for item in paired], 0
    if 2 * trim_count >= len(paired):
        raise ValueError("Trim fraction removes all paired rows.")

    kept = paired[trim_count : len(paired) - trim_count]
    return [item[0] for item in kept], [item[1] for item in kept], trim_count


def _ols_log_fit(income_values: list[float], price_values: list[float]) -> tuple[float, float, list[float]]:
    if len(income_values) != len(price_values):
        raise ValueError("Cannot fit regression: paired size mismatch.")
    if len(income_values) < 2:
        raise ValueError("Need at least two paired samples for regression.")

    x_values = [math.log(max(value, 1e-12)) for value in income_values]
    y_values = [math.log(max(value, 1e-12)) for value in price_values]

    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(y_values) / len(y_values)
    sxx = sum((value - mean_x) ** 2 for value in x_values)
    if sxx <= 0.0:
        raise ValueError("Degenerate x-values; cannot estimate BUY_EXPONENT.")
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))

    exponent = sxy / sxx
    intercept = mean_y - exponent * mean_x
    scale = math.exp(intercept)
    residuals = [y - (intercept + exponent * x) for x, y in zip(x_values, y_values)]
    return scale, exponent, residuals


def _ppd_rows(path: Path, target_year: int | None) -> list[float]:
    prices: list[float] = []
    with path.open("r", encoding="utf-8", newline="", errors="replace") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if len(row) <= 1:
                continue
            if target_year is not None:
                if len(row) <= 2 or len(row[2]) < 4 or not row[2][:4].isdigit():
                    continue
                if int(row[2][:4]) != target_year:
                    continue
            try:
                price = float(row[1].strip())
            except ValueError:
                continue
            if price <= 0.0:
                continue
            prices.append(price)
    return prices


def load_ppd_moment_stats(path: Path | str, target_year: int | None = None) -> PpdMomentStats:
    ppd_path = Path(path)
    if not ppd_path.exists():
        raise ValueError(f"Missing PPD CSV: {ppd_path}")

    rows = _ppd_rows(ppd_path, target_year)
    if not rows:
        raise ValueError(f"No valid prices found in PPD CSV: {ppd_path}")

    log_prices = [math.log(value) for value in rows]
    mean_log_price = sum(log_prices) / len(log_prices)
    variance_log_price = sum((value - mean_log_price) ** 2 for value in log_prices) / len(log_prices)

    total_rows = 0
    with ppd_path.open("r", encoding="utf-8", newline="", errors="replace") as handle:
        for _ in csv.reader(handle):
            total_rows += 1

    return PpdMomentStats(
        rows_total=total_rows,
        rows_used=len(rows),
        mean_log_price=mean_log_price,
        variance_log_price=variance_log_price,
    )


def _expand_bins(
    bins: list[PsdBin],
    *,
    open_lower: float,
    open_upper: float,
    within_bin_points: int,
) -> tuple[list[float], list[float], float]:
    if within_bin_points <= 0:
        raise ValueError("within_bin_points must be positive.")

    values: list[float] = []
    weights: list[float] = []
    total_mass = 0.0

    for item in bins:
        if item.mass <= 0.0:
            continue
        lower = open_lower if item.lower is None else item.lower
        upper = open_upper if item.upper is None else item.upper
        if upper < lower and item.upper is None:
            # Guard against open-bin assumptions that fall below observed bin
            # lower edges (for example, £100,001+ with open_upper=100000).
            upper = lower
        if upper < lower:
            raise ValueError(f"Invalid bin bounds: {item}")

        if upper == lower:
            midpoints = [lower]
        else:
            width = upper - lower
            midpoints = [
                lower + ((index + 0.5) * width / within_bin_points)
                for index in range(within_bin_points)
            ]

        mass_per_point = item.mass / len(midpoints)
        total_mass += item.mass
        values.extend(midpoints)
        weights.extend([mass_per_point] * len(midpoints))

    if not values:
        raise ValueError("No usable values after bin expansion.")
    return values, weights, total_mass


def _legacy_2011_marginals(
    *,
    p3_csv: Path,
    p5_csv: Path,
    target_year: int,
    spec: BuyMethodSpec,
) -> SyntheticMarginals:
    p3_table = load_psd_table(p3_csv)
    p5_table = load_psd_table(p5_csv)
    p3_year_column = get_year_column(p3_table, target_year)
    p5_year_column = get_year_column(p5_table, target_year)

    loan_bins = build_bins_from_labeled_rows(
        get_labeled_section_rows(p3_table, LEGACY_2011_LOAN_GROUP_SECTION),
        p3_year_column,
    )
    lti_single_bins = build_bins_from_labeled_rows(
        get_labeled_section_rows(p3_table, LEGACY_2011_LTI_SINGLE_SECTION),
        p3_year_column,
    )
    lti_joint_bins = build_bins_from_labeled_rows(
        get_labeled_section_rows(p3_table, LEGACY_2011_LTI_JOINT_SECTION),
        p3_year_column,
    )
    lti_bins = lti_single_bins + lti_joint_bins
    property_bins = build_bins_from_labeled_rows(
        get_labeled_section_rows(p5_table, LEGACY_2011_PROPERTY_GROUP_SECTION),
        p5_year_column,
    )

    if not loan_bins or not lti_bins or not property_bins:
        raise ValueError("Missing required PSD 2011 bins for buy-budget estimation.")

    loan_values, loan_weights, loan_mass = _expand_bins(
        loan_bins,
        open_lower=0.0,
        open_upper=spec.loan_open_upper_k * 1_000.0,
        within_bin_points=spec.within_bin_points,
    )
    lti_values, lti_weights, lti_mass = _expand_bins(
        lti_bins,
        open_lower=spec.lti_open_lower,
        open_upper=spec.lti_open_upper,
        within_bin_points=spec.within_bin_points,
    )

    loans_series, lti_series = _pair_series(
        loan_values,
        loan_weights,
        lti_values,
        lti_weights,
        spec.quantile_grid_size,
        spec.loan_to_income_coupling,
    )
    income_values = [max(loan / max(lti, 1e-12), 1.0) for loan, lti in zip(loans_series, lti_series)]
    income_weights = [1.0] * len(income_values)

    price_values, price_weights, property_mass = _expand_bins(
        property_bins,
        open_lower=0.0,
        open_upper=spec.property_open_upper_k * 1_000.0,
        within_bin_points=spec.within_bin_points,
    )

    diagnostics = {
        "loan_bins": float(len(loan_bins)),
        "lti_bins": float(len(lti_bins)),
        "property_bins": float(len(property_bins)),
        "loan_mass": loan_mass,
        "lti_mass": lti_mass,
        "property_mass": property_mass,
    }

    return SyntheticMarginals(
        income_values=income_values,
        income_weights=income_weights,
        price_values=price_values,
        price_weights=price_weights,
        diagnostics=diagnostics,
    )


def _modern_2024_marginals(
    *,
    quarterly_csv: Path,
    target_year: int,
    spec: BuyMethodSpec,
) -> SyntheticMarginals:
    rows = load_quarterly_psd_rows(quarterly_csv)

    income_sales = aggregate_category_sales(rows, group=MODERN_2024_INCOME_GROUP, year=target_year)
    property_sales = aggregate_category_sales(rows, group=MODERN_2024_PROPERTY_GROUP, year=target_year)
    loan_sales = aggregate_category_sales(rows, group=MODERN_2024_LOAN_GROUP, year=target_year)
    ltv_sales = aggregate_category_sales(rows, group=MODERN_2024_LTV_GROUP, year=target_year)
    borrower_sales = aggregate_category_sales(rows, group=MODERN_2024_BORROWER_GROUP, year=target_year)

    if not income_sales:
        raise ValueError(f"Missing modern income group '{MODERN_2024_INCOME_GROUP}' for year {target_year}.")
    if not property_sales:
        raise ValueError(f"Missing modern property group '{MODERN_2024_PROPERTY_GROUP}' for year {target_year}.")

    income_bins = build_bins_from_category_masses(income_sales)
    property_bins = build_bins_from_category_masses(property_sales)

    if not income_bins or not property_bins:
        raise ValueError("No usable modern income/property bins after parsing.")

    income_values, income_weights, income_mass = _expand_bins(
        income_bins,
        open_lower=0.0,
        open_upper=spec.income_open_upper_k * 1_000.0,
        within_bin_points=spec.within_bin_points,
    )
    price_values, price_weights, property_mass = _expand_bins(
        property_bins,
        open_lower=0.0,
        open_upper=spec.property_open_upper_k * 1_000.0,
        within_bin_points=spec.within_bin_points,
    )

    diagnostics = {
        "income_bins": float(len(income_bins)),
        "property_bins": float(len(property_bins)),
        "income_mass": income_mass,
        "property_mass": property_mass,
        "loan_group_mass": float(sum(loan_sales.values())) if loan_sales else 0.0,
        "ltv_group_mass": float(sum(ltv_sales.values())) if ltv_sales else 0.0,
        "borrower_group_mass": float(sum(borrower_sales.values())) if borrower_sales else 0.0,
    }

    return SyntheticMarginals(
        income_values=income_values,
        income_weights=income_weights,
        price_values=price_values,
        price_weights=price_weights,
        diagnostics=diagnostics,
    )


def _fit_method(
    marginals: SyntheticMarginals,
    ppd_stats: PpdMomentStats,
    method: BuyMethodSpec,
) -> tuple[float, float, float, float, MethodDiagnostics]:
    paired_income, paired_price = _pair_series(
        marginals.income_values,
        marginals.income_weights,
        marginals.price_values,
        marginals.price_weights,
        method.quantile_grid_size,
        method.income_to_price_coupling,
    )
    paired_income, paired_price, trimmed_each_side = _trim_paired(
        paired_income,
        paired_price,
        method.trim_fraction,
    )

    buy_scale, buy_exponent, residuals = _ols_log_fit(paired_income, paired_price)

    sigma2_clamped_to_zero = False
    mu_upper_trimmed_count = 0
    if method.family == METHOD_FAMILY_PSD_LOG_OLS_RESIDUAL:
        buy_mu = sum(residuals) / len(residuals)
        buy_sigma = math.sqrt(sum((value - buy_mu) ** 2 for value in residuals) / len(residuals))
    elif method.family == METHOD_FAMILY_PSD_LOG_OLS_ROBUST_MU:
        if method.mu_upper_trim_fraction < 0.0 or method.mu_upper_trim_fraction >= 0.5:
            raise ValueError(
                f"mu_upper_trim_fraction must be in [0, 0.5): {method.mu_upper_trim_fraction}"
            )
        residuals_sorted = sorted(residuals)
        mu_upper_trimmed_count = int(len(residuals_sorted) * method.mu_upper_trim_fraction)
        if mu_upper_trimmed_count >= len(residuals_sorted):
            raise ValueError("mu_upper_trim_fraction trims all residuals.")
        kept = residuals_sorted[: len(residuals_sorted) - mu_upper_trimmed_count]
        buy_mu = sum(kept) / len(kept)

        # Keep sigma tied to the full residual spread (untrimmed), as used by
        # the robust reproduction experiment.
        residual_mu = sum(residuals) / len(residuals)
        buy_sigma = math.sqrt(
            sum((value - residual_mu) ** 2 for value in residuals) / len(residuals)
        )
    elif method.family == METHOD_FAMILY_PSD_LOG_OLS_PPD_MOMENT_CLOSURE:
        log_income = [math.log(max(value, 1e-12)) for value in paired_income]
        income_mu = sum(log_income) / len(log_income)
        income_var = sum((value - income_mu) ** 2 for value in log_income) / len(log_income)

        buy_mu = ppd_stats.mean_log_price - (math.log(max(buy_scale, 1e-12)) + buy_exponent * income_mu)
        sigma2 = ppd_stats.variance_log_price - (buy_exponent**2) * income_var
        if sigma2 < 0.0:
            sigma2_clamped_to_zero = True
            sigma2 = 0.0
        buy_sigma = math.sqrt(sigma2)
    else:
        raise ValueError(f"Unsupported family: {method.family}")

    diagnostics = MethodDiagnostics(
        rows_income_mass=sum(marginals.income_weights),
        rows_price_mass=sum(marginals.price_weights),
        paired_sample_size=len(paired_income),
        trimmed_each_side=trimmed_each_side,
        ppd_rows_used=ppd_stats.rows_used,
        sigma2_clamped_to_zero=sigma2_clamped_to_zero,
        mu_upper_trimmed_count=mu_upper_trimmed_count,
    )
    return buy_scale, buy_exponent, buy_mu, buy_sigma, diagnostics


def evaluate_method_against_targets(
    *,
    marginals: SyntheticMarginals,
    ppd_stats: PpdMomentStats,
    method: BuyMethodSpec,
    target_buy_scale: float,
    target_buy_exponent: float,
    target_buy_mu: float,
    target_buy_sigma: float,
) -> BuyMethodResult:
    buy_scale, buy_exponent, buy_mu, buy_sigma, diagnostics = _fit_method(marginals, ppd_stats, method)

    den_scale, den_exponent, den_mu, den_sigma = _target_denominators(
        target_buy_scale,
        target_buy_exponent,
        target_buy_mu,
        target_buy_sigma,
    )

    abs_d_scale_norm = abs(buy_scale - target_buy_scale) / den_scale
    abs_d_exponent_norm = abs(buy_exponent - target_buy_exponent) / den_exponent
    abs_d_mu_norm = abs(buy_mu - target_buy_mu) / den_mu
    abs_d_sigma_norm = abs(buy_sigma - target_buy_sigma) / den_sigma

    distance_norm = math.sqrt(
        abs_d_scale_norm**2
        + abs_d_exponent_norm**2
        + abs_d_mu_norm**2
        + abs_d_sigma_norm**2
    )

    return BuyMethodResult(
        method=method,
        buy_scale=buy_scale,
        buy_exponent=buy_exponent,
        buy_mu=buy_mu,
        buy_sigma=buy_sigma,
        distance_norm=distance_norm,
        abs_d_scale_norm=abs_d_scale_norm,
        abs_d_exponent_norm=abs_d_exponent_norm,
        abs_d_mu_norm=abs_d_mu_norm,
        abs_d_sigma_norm=abs_d_sigma_norm,
        diagnostics=diagnostics,
    )


def rank_method_results(results: list[BuyMethodResult]) -> list[BuyMethodResult]:
    return sorted(
        results,
        key=lambda item: (
            item.distance_norm,
            item.abs_d_scale_norm,
            item.abs_d_exponent_norm,
            item.abs_d_mu_norm,
            item.abs_d_sigma_norm,
            item.method.method_id,
        ),
    )


def resolve_targets_from_config(
    config_path: Path | str,
    *,
    key_scale: str = TARGET_BUY_SCALE_KEY,
    key_exponent: str = TARGET_BUY_EXPONENT_KEY,
    key_mu: str = TARGET_BUY_MU_KEY,
    key_sigma: str = TARGET_BUY_SIGMA_KEY,
) -> tuple[float, float, float, float]:
    props = read_properties(Path(config_path))
    missing = [
        key
        for key in (key_scale, key_exponent, key_mu, key_sigma)
        if key not in props
    ]
    if missing:
        raise ValueError("Missing target keys in config: " + ", ".join(missing))
    return (
        float(props[key_scale]),
        float(props[key_exponent]),
        float(props[key_mu]),
        float(props[key_sigma]),
    )


def seed_method_spec() -> BuyMethodSpec:
    return BuyMethodSpec(
        family=METHOD_FAMILY_PSD_LOG_OLS_RESIDUAL,
        loan_to_income_coupling="comonotonic",
        income_to_price_coupling="comonotonic",
        loan_open_upper_k=3000.0,
        lti_open_upper=6.0,
        lti_open_lower=2.0,
        income_open_upper_k=200.0,
        property_open_upper_k=1200.0,
        trim_fraction=0.0,
        within_bin_points=11,
        quantile_grid_size=4000,
    )


def compute_initial_seed_2011(
    *,
    p3_csv: Path,
    p5_csv: Path,
    ppd_csv: Path,
    target_year_psd: int,
    target_year_ppd: int,
) -> tuple[BuySeedEstimate, PpdMomentStats, dict[str, float]]:
    spec = seed_method_spec()
    marginals = _legacy_2011_marginals(
        p3_csv=p3_csv,
        p5_csv=p5_csv,
        target_year=target_year_psd,
        spec=spec,
    )
    ppd_stats = load_ppd_moment_stats(ppd_csv, target_year=target_year_ppd)
    buy_scale, buy_exponent, buy_mu, buy_sigma, _ = _fit_method(marginals, ppd_stats, spec)

    return (
        BuySeedEstimate(
            buy_scale=buy_scale,
            buy_exponent=buy_exponent,
            buy_mu=buy_mu,
            buy_sigma=buy_sigma,
            method_id=spec.method_id,
        ),
        ppd_stats,
        marginals.diagnostics,
    )


def run_legacy_2011_method_search(
    *,
    p3_csv: Path,
    p5_csv: Path,
    ppd_csv: Path,
    config_path: Path,
    target_year_psd: int,
    target_year_ppd: int,
    methods: list[BuyMethodSpec],
    progress_callback: Callable[[int, int, int], None] | None = None,
) -> BuySearchOutput:
    target_scale, target_exponent, target_mu, target_sigma = resolve_targets_from_config(config_path)

    seed, ppd_stats, legacy_diagnostics = compute_initial_seed_2011(
        p3_csv=p3_csv,
        p5_csv=p5_csv,
        ppd_csv=ppd_csv,
        target_year_psd=target_year_psd,
        target_year_ppd=target_year_ppd,
    )

    results: list[BuyMethodResult] = []
    skipped_methods = 0
    total_methods = len(methods)
    for processed, method in enumerate(methods, start=1):
        try:
            marginals = _legacy_2011_marginals(
                p3_csv=p3_csv,
                p5_csv=p5_csv,
                target_year=target_year_psd,
                spec=method,
            )
            result = evaluate_method_against_targets(
                marginals=marginals,
                ppd_stats=ppd_stats,
                method=method,
                target_buy_scale=target_scale,
                target_buy_exponent=target_exponent,
                target_buy_mu=target_mu,
                target_buy_sigma=target_sigma,
            )
            results.append(result)
        except ValueError:
            skipped_methods += 1
        if progress_callback is not None:
            progress_callback(processed, total_methods, skipped_methods)

    if not results:
        raise ValueError("No method produced a valid estimate in legacy 2011 search.")

    return BuySearchOutput(
        target_buy_scale=target_scale,
        target_buy_exponent=target_exponent,
        target_buy_mu=target_mu,
        target_buy_sigma=target_sigma,
        initial_seed=seed,
        ppd_stats=ppd_stats,
        legacy_diagnostics=legacy_diagnostics,
        results=rank_method_results(results),
        skipped_methods=skipped_methods,
    )


def run_modern_calibration(
    *,
    quarterly_csv: Path,
    ppd_csv: Path,
    target_year_psd: int,
    target_year_ppd: int,
    method: BuyMethodSpec,
) -> BuyCalibrationOutput:
    if method.family not in METHOD_FAMILY_CHOICES:
        raise ValueError(f"Unsupported method family: {method.family}")

    ppd_stats = load_ppd_moment_stats(ppd_csv, target_year=target_year_ppd)
    marginals = _modern_2024_marginals(
        quarterly_csv=quarterly_csv,
        target_year=target_year_psd,
        spec=method,
    )

    # For production calibration, targets are irrelevant, so we use zero placeholders
    # and directly call _fit_method.
    buy_scale, buy_exponent, buy_mu, buy_sigma, diagnostics = _fit_method(
        marginals,
        ppd_stats,
        method,
    )

    return BuyCalibrationOutput(
        method=method,
        buy_scale=buy_scale,
        buy_exponent=buy_exponent,
        buy_mu=buy_mu,
        buy_sigma=buy_sigma,
        diagnostics=diagnostics,
        ppd_stats=ppd_stats,
        modern_diagnostics=marginals.diagnostics,
    )


def parse_method_id(method_id: str) -> BuyMethodSpec:
    fields: dict[str, str] = {}
    for token in method_id.split("|"):
        if "=" not in token:
            raise ValueError(f"Invalid method_id token: {token}")
        key, value = token.split("=", 1)
        fields[key] = value

    required = {
        "family",
        "loan_to_income",
        "income_to_price",
        "loan_open_k",
        "lti_open",
        "lti_floor",
        "income_open_k",
        "property_open_k",
        "trim",
        "within_bin_points",
        "grid",
    }
    missing = sorted(required - set(fields.keys()))
    if missing:
        raise ValueError("Missing method_id fields: " + ", ".join(missing))

    return BuyMethodSpec(
        family=fields["family"],
        loan_to_income_coupling=fields["loan_to_income"],
        income_to_price_coupling=fields["income_to_price"],
        loan_open_upper_k=float(fields["loan_open_k"]),
        lti_open_upper=float(fields["lti_open"]),
        lti_open_lower=float(fields["lti_floor"]),
        income_open_upper_k=float(fields["income_open_k"]),
        property_open_upper_k=float(fields["property_open_k"]),
        trim_fraction=float(fields["trim"]),
        within_bin_points=int(fields["within_bin_points"]),
        quantile_grid_size=int(fields["grid"]),
        mu_upper_trim_fraction=float(fields.get("mu_hi_trim", "0.0")),
    )


def method_specs_from_grid(
    *,
    families: Iterable[str],
    loan_to_income_couplings: Iterable[str],
    income_to_price_couplings: Iterable[str],
    loan_open_upper_k_values: Iterable[float],
    lti_open_upper_values: Iterable[float],
    lti_open_lower_values: Iterable[float],
    income_open_upper_k_values: Iterable[float],
    property_open_upper_k_values: Iterable[float],
    trim_fractions: Iterable[float],
    mu_upper_trim_fractions: Iterable[float] | None = None,
    within_bin_points: int,
    quantile_grid_size: int,
) -> list[BuyMethodSpec]:
    methods: list[BuyMethodSpec] = []
    for family in families:
        if family not in METHOD_FAMILY_CHOICES:
            raise ValueError(f"Unsupported family: {family}")
        if family == METHOD_FAMILY_PSD_LOG_OLS_ROBUST_MU:
            mu_trim_candidates = (
                [float(value) for value in mu_upper_trim_fractions]
                if mu_upper_trim_fractions is not None
                else [0.0]
            )
        else:
            mu_trim_candidates = [0.0]
        if not mu_trim_candidates:
            raise ValueError("mu_upper_trim_fractions must contain at least one value for robust family.")
        for mu_upper_trim_fraction in mu_trim_candidates:
            if mu_upper_trim_fraction < 0.0 or mu_upper_trim_fraction >= 0.5:
                raise ValueError(
                    f"mu_upper_trim_fraction must be in [0, 0.5): {mu_upper_trim_fraction}"
                )
        for loan_to_income_coupling in loan_to_income_couplings:
            if loan_to_income_coupling not in COUPLING_CHOICES:
                raise ValueError(f"Unsupported loan_to_income coupling: {loan_to_income_coupling}")
            for income_to_price_coupling in income_to_price_couplings:
                if income_to_price_coupling not in COUPLING_CHOICES:
                    raise ValueError(f"Unsupported income_to_price coupling: {income_to_price_coupling}")
                for loan_open_upper_k in loan_open_upper_k_values:
                    for lti_open_upper in lti_open_upper_values:
                        for lti_open_lower in lti_open_lower_values:
                            if lti_open_upper <= lti_open_lower:
                                continue
                            for income_open_upper_k in income_open_upper_k_values:
                                for property_open_upper_k in property_open_upper_k_values:
                                    for trim_fraction in trim_fractions:
                                        for mu_upper_trim_fraction in mu_trim_candidates:
                                            methods.append(
                                                BuyMethodSpec(
                                                    family=family,
                                                    loan_to_income_coupling=loan_to_income_coupling,
                                                    income_to_price_coupling=income_to_price_coupling,
                                                    loan_open_upper_k=float(loan_open_upper_k),
                                                    lti_open_upper=float(lti_open_upper),
                                                    lti_open_lower=float(lti_open_lower),
                                                    income_open_upper_k=float(income_open_upper_k),
                                                    property_open_upper_k=float(property_open_upper_k),
                                                    trim_fraction=float(trim_fraction),
                                                    within_bin_points=within_bin_points,
                                                    quantile_grid_size=quantile_grid_size,
                                                    mu_upper_trim_fraction=float(mu_upper_trim_fraction),
                                                )
                                            )
    return methods


DEFAULT_SELECTED_METHOD = BuyMethodSpec(
    family=METHOD_FAMILY_PSD_LOG_OLS_ROBUST_MU,
    loan_to_income_coupling="comonotonic",
    income_to_price_coupling="comonotonic",
    loan_open_upper_k=500.0,
    lti_open_upper=10.0,
    lti_open_lower=2.5,
    income_open_upper_k=100.0,
    property_open_upper_k=10000.0,
    trim_fraction=0.0,
    within_bin_points=11,
    quantile_grid_size=4000,
    mu_upper_trim_fraction=0.0063,
)


__all__ = [
    "BuyCalibrationOutput",
    "BuyMethodResult",
    "BuyMethodSpec",
    "BuySearchOutput",
    "BuySeedEstimate",
    "COUPLING_CHOICES",
    "DEFAULT_SELECTED_METHOD",
    "METHOD_FAMILY_CHOICES",
    "METHOD_FAMILY_PSD_LOG_OLS_PPD_MOMENT_CLOSURE",
    "METHOD_FAMILY_PSD_LOG_OLS_ROBUST_MU",
    "METHOD_FAMILY_PSD_LOG_OLS_RESIDUAL",
    "MODERN_2024_BORROWER_GROUP",
    "MODERN_2024_INCOME_GROUP",
    "MODERN_2024_LOAN_GROUP",
    "MODERN_2024_LTV_GROUP",
    "MODERN_2024_PROPERTY_GROUP",
    "TARGET_BUY_EXPONENT_KEY",
    "TARGET_BUY_MU_KEY",
    "TARGET_BUY_SCALE_KEY",
    "TARGET_BUY_SIGMA_KEY",
    "compute_initial_seed_2011",
    "evaluate_method_against_targets",
    "load_ppd_moment_stats",
    "method_specs_from_grid",
    "parse_method_id",
    "rank_method_results",
    "resolve_targets_from_config",
    "run_legacy_2011_method_search",
    "run_modern_calibration",
    "seed_method_spec",
]
