"""Statistical helpers used by PSD method-search experiments."""

from __future__ import annotations

import math
from typing import Iterable

from scripts.python.helpers.psd.bins import PsdBin, sort_bins_for_quantile



def euclidean_distance(left: Iterable[float], right: Iterable[float]) -> float:
    """Compute Euclidean distance between same-length numeric vectors."""
    left_values = list(left)
    right_values = list(right)
    if len(left_values) != len(right_values):
        raise ValueError("Vector sizes differ in euclidean_distance().")
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left_values, right_values)))



def binned_weighted_quantile(
    bins: list[PsdBin],
    quantile: float,
    open_upper: float,
    *,
    interpolation: str = "linear",
) -> float:
    """Estimate a quantile from weighted bins using in-bin interpolation."""
    if not bins:
        raise ValueError("Cannot compute quantile from empty bin set.")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("Quantile must be in [0, 1].")
    if interpolation != "linear":
        raise ValueError(f"Unsupported interpolation: {interpolation}")

    ordered_bins = sort_bins_for_quantile([item for item in bins if item.mass > 0.0])
    total_mass = sum(item.mass for item in ordered_bins)
    if total_mass <= 0.0:
        raise ValueError("Total mass is zero; cannot compute quantile.")

    target_mass = quantile * total_mass
    cumulative_mass = 0.0

    for item in ordered_bins:
        next_mass = cumulative_mass + item.mass
        if target_mass <= next_mass:
            lower = 0.0 if item.lower is None else item.lower
            upper = open_upper if item.upper is None else item.upper
            if upper < lower:
                raise ValueError(f"Invalid bin with upper<lower: {item}")
            if item.mass == 0.0 or upper == lower:
                return lower
            fraction = (target_mass - cumulative_mass) / item.mass
            return lower + fraction * (upper - lower)
        cumulative_mass = next_mass

    # Numerical fallback for quantile==1.0.
    tail = ordered_bins[-1]
    return open_upper if tail.upper is None else tail.upper



def _weighted_mean_and_variance(values: list[float], weights: list[float]) -> tuple[float, float]:
    weight_sum = sum(weights)
    if weight_sum <= 0.0:
        raise ValueError("Weight sum must be positive.")
    mean = sum(value * weight for value, weight in zip(values, weights)) / weight_sum
    variance = sum(weight * (value - mean) ** 2 for value, weight in zip(values, weights)) / weight_sum
    return mean, variance



def _weighted_quantile_series(values: list[float], weights: list[float], n_points: int) -> list[float]:
    if n_points <= 0:
        raise ValueError("n_points must be positive.")

    ordered = sorted(zip(values, weights), key=lambda pair: pair[0])
    cumulative: list[float] = []
    levels: list[float] = []
    total_weight = 0.0
    for value, weight in ordered:
        total_weight += weight
        cumulative.append(total_weight)
        levels.append(value)
    if total_weight <= 0.0:
        raise ValueError("Total weight must be positive.")

    series: list[float] = []
    pointer = 0
    for index in range(n_points):
        quantile = (index + 0.5) / n_points
        threshold = quantile * total_weight
        while pointer < len(cumulative) - 1 and threshold > cumulative[pointer]:
            pointer += 1
        series.append(levels[pointer])
    return series



def lognormal_params_from_synthetic_downpayment(
    ltv_bins: list[PsdBin],
    property_bins: list[PsdBin],
    *,
    ltv_open_upper: float,
    property_open_upper_k: float,
    coupling: str,
    quantile_grid_size: int = 4000,
    within_bin_points: int = 11,
) -> tuple[float, float]:
    """Estimate (mu, sigma) of log downpayment from LTV and property marginals.

    `ltv_bins` are expected in percentage points (e.g., 75..85).
    `property_bins` are expected in absolute GBP values.
    `property_open_upper_k` is specified in thousands of GBP.
    """
    if coupling not in {"independent", "comonotonic", "countermonotonic"}:
        raise ValueError(f"Unsupported coupling: {coupling}")
    if within_bin_points <= 0:
        raise ValueError("within_bin_points must be positive.")

    ltv_values: list[float] = []
    ltv_weights: list[float] = []
    for item in ltv_bins:
        if item.mass <= 0.0:
            continue
        lower = 0.0 if item.lower is None else item.lower
        upper = ltv_open_upper if item.upper is None else item.upper
        if upper < lower:
            raise ValueError(f"Invalid LTV bin bounds: {item}")

        if upper == lower:
            midpoints = [lower]
        else:
            width = upper - lower
            midpoints = [
                lower + ((index + 0.5) * width / within_bin_points)
                for index in range(within_bin_points)
            ]

        mass_per_point = item.mass / len(midpoints)
        for midpoint in midpoints:
            midpoint_ratio = midpoint / 100.0
            # Guard against malformed bins implying >=100%.
            midpoint_ratio = min(max(midpoint_ratio, 0.0), 0.999999999)
            ltv_values.append(math.log(max(1.0 - midpoint_ratio, 1e-12)))
            ltv_weights.append(mass_per_point)

    property_values: list[float] = []
    property_weights: list[float] = []
    property_open_upper = property_open_upper_k * 1_000.0
    for item in property_bins:
        if item.mass <= 0.0:
            continue
        lower = 0.0 if item.lower is None else item.lower
        upper = property_open_upper if item.upper is None else item.upper
        if upper < lower:
            raise ValueError(f"Invalid property-value bin bounds: {item}")

        if upper == lower:
            midpoints = [lower]
        else:
            width = upper - lower
            midpoints = [
                lower + ((index + 0.5) * width / within_bin_points)
                for index in range(within_bin_points)
            ]

        mass_per_point = item.mass / len(midpoints)
        for midpoint in midpoints:
            midpoint_value = max(midpoint, 1e-12)
            property_values.append(math.log(midpoint_value))
            property_weights.append(mass_per_point)

    if not ltv_values or not property_values:
        raise ValueError("Missing LTV/property mass for downpayment fitting.")

    mean_ltv, var_ltv = _weighted_mean_and_variance(ltv_values, ltv_weights)
    mean_property, var_property = _weighted_mean_and_variance(property_values, property_weights)

    covariance = 0.0
    if coupling != "independent":
        ltv_series = _weighted_quantile_series(ltv_values, ltv_weights, quantile_grid_size)
        property_series = _weighted_quantile_series(property_values, property_weights, quantile_grid_size)
        if coupling == "countermonotonic":
            property_series = list(reversed(property_series))
        covariance = sum(
            (left - mean_ltv) * (right - mean_property)
            for left, right in zip(ltv_series, property_series)
        ) / quantile_grid_size

    mu = mean_ltv + mean_property
    variance = var_ltv + var_property + 2.0 * covariance
    sigma = math.sqrt(max(variance, 0.0))
    return mu, sigma


__all__ = [
    "binned_weighted_quantile",
    "euclidean_distance",
    "lognormal_params_from_synthetic_downpayment",
]
