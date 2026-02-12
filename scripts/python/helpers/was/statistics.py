"""
Statistical helpers for WAS distributions.

Provides moments for binned distributions stored as lower/upper/probability columns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def normalize_distribution(values: pd.Series) -> pd.Series:
    """Normalize distribution values so they sum to 1."""
    total = float(values.sum())
    if total == 0.0:
        return values
    return values / total


def mean_variance_skew(distribution: pd.DataFrame) -> tuple[float, float, float]:
    """Compute mean, variance, and skew using bin midpoints and probabilities."""
    probabilities = normalize_distribution(distribution["probability"])
    midpoints = (distribution["lower_edge"] + distribution["upper_edge"]) / 2.0
    mean = float((midpoints * probabilities).sum())
    variance = float((probabilities * (midpoints - mean) ** 2).sum())
    if variance == 0.0:
        return mean, variance, 0.0
    third_moment = float((probabilities * (midpoints - mean) ** 3).sum())
    skew = third_moment / (variance ** 1.5)
    return mean, variance, skew


def weighted_mean_variance_skew(
    values: pd.Series,
    weights: pd.Series,
) -> tuple[float, float, float]:
    """Compute weighted mean, variance, and skew for raw values."""
    total_weight = float(weights.sum())
    if total_weight == 0.0:
        return float("nan"), float("nan"), float("nan")
    mean = float((values * weights).sum() / total_weight)
    variance = float((weights * (values - mean) ** 2).sum() / total_weight)
    if variance == 0.0:
        return mean, variance, 0.0
    third_moment = float((weights * (values - mean) ** 3).sum() / total_weight)
    skew = third_moment / (variance ** 1.5)
    return mean, variance, skew


def weighted_stats_by_bins(
    bin_values: pd.Series,
    values: pd.Series,
    weights: pd.Series,
    bin_edges: np.ndarray,
) -> pd.DataFrame:
    """Compute weighted mean/variance for values grouped by bin edges."""
    bins = pd.cut(
        bin_values,
        bins=bin_edges,
        right=False,
        include_lowest=True,
    )
    results = []
    for interval in bins.cat.categories:
        mask = bins == interval
        if not mask.any():
            mean = float("nan")
            variance = float("nan")
        else:
            mean, variance, _ = weighted_mean_variance_skew(
                values[mask],
                weights[mask],
            )
        results.append(
            {
                "lower_edge": float(interval.left),
                "upper_edge": float(interval.right),
                "mean": mean,
                "variance": variance,
            }
        )
    return pd.DataFrame(results)


def log_binned_mean_variance_skew(
    log_bin_edges: np.ndarray,
    density: np.ndarray,
    skew_in_log_space: bool = False,
) -> tuple[float, float, float]:
    """Compute mean/variance from log-binned densities, with optional log-space skew."""
    if len(log_bin_edges) < 2 or len(density) != len(log_bin_edges) - 1:
        raise ValueError("log_bin_edges and density lengths do not align.")
    log_mid = (log_bin_edges[:-1] + log_bin_edges[1:]) / 2.0
    widths = log_bin_edges[1:] - log_bin_edges[:-1]
    probs = density * widths
    total_prob = float(probs.sum())
    if total_prob == 0.0:
        return float("nan"), float("nan"), float("nan")
    probs = probs / total_prob

    values = np.exp(log_mid)
    mean = float((values * probs).sum())
    variance = float((probs * (values - mean) ** 2).sum())
    if skew_in_log_space:
        log_mean = float((log_mid * probs).sum())
        log_variance = float((probs * (log_mid - log_mean) ** 2).sum())
        if log_variance == 0.0:
            return mean, variance, 0.0
        third_moment = float((probs * (log_mid - log_mean) ** 3).sum())
        skew = third_moment / (log_variance ** 1.5)
        return mean, variance, skew
    if variance == 0.0:
        return mean, variance, 0.0
    third_moment = float((probs * (values - mean) ** 3).sum())
    skew = third_moment / (variance ** 1.5)
    return mean, variance, skew
