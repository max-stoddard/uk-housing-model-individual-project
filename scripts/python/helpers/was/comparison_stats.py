"""
Shared helpers for experiment comparison tables and summaries.

@author: Max Stoddard
"""

from __future__ import annotations

import math
from typing import Callable, Mapping


def safe_percent_diff(new_value: float, old_value: float) -> float:
    """Return percent difference from old_value to new_value."""
    if old_value:
        return (new_value - old_value) / old_value * 100.0
    return float("nan")


def compute_percent_stats(
    wave_stats: Mapping[str, float],
    round_stats: Mapping[str, float],
) -> dict[str, float]:
    """Compute percent differences for matching metric keys."""
    return {
        key: safe_percent_diff(round_stats[key], wave_stats[key])
        for key in wave_stats
    }


def format_value(value: float, decimals: int = 3) -> str:
    """Format a float for LaTeX-friendly tables."""
    if value != value:
        return "--"
    return f"{value:.{decimals}f}"


def format_currency(value: float, decimals: int = 2, symbol: str = "£") -> str:
    """Format a float as currency with separators."""
    if value != value:
        return "--"
    return f"{symbol}{value:,.{decimals}f}"


def format_percent(value: float, decimals: int = 2) -> str:
    """Format a percent value for LaTeX-friendly tables."""
    if value != value:
        return "--"
    return f"{value:.{decimals}f}\\%"


def build_latex_stats_rows(
    wave_label: str,
    wave_period: str,
    wave_stats: Mapping[str, float],
    round_label: str,
    round_period: str,
    round_stats: Mapping[str, float],
    percent_label: str,
    value_decimals: int = 3,
    percent_decimals: int = 2,
    value_formatters: Mapping[str, Callable[[float], str]] | None = None,
) -> list[dict[str, str]]:
    """Build LaTeX-friendly rows for wave, round, and percent-diff entries."""
    metric_keys = list(wave_stats.keys())
    rows: list[dict[str, str]] = []
    formatter_map = value_formatters or {}

    wave_row = {"dataset": wave_label, "period": wave_period}
    for key in metric_keys:
        formatter = formatter_map.get(key)
        wave_row[key] = (
            formatter(wave_stats[key])
            if formatter
            else format_value(wave_stats[key], value_decimals)
        )
    rows.append(wave_row)

    round_row = {"dataset": round_label, "period": round_period}
    for key in metric_keys:
        formatter = formatter_map.get(key)
        round_row[key] = (
            formatter(round_stats[key])
            if formatter
            else format_value(round_stats[key], value_decimals)
        )
    rows.append(round_row)

    percent_stats = compute_percent_stats(wave_stats, round_stats)
    percent_row = {"dataset": percent_label, "period": "--"}
    for key in metric_keys:
        percent_row[key] = format_percent(percent_stats[key], percent_decimals)
    rows.append(percent_row)

    return rows


def to_std_dev_stats(stats: Mapping[str, float]) -> dict[str, float]:
    """Return a stats dict with variance replaced by standard deviation."""
    if "stddev" in stats:
        return dict(stats)
    if "std_dev" in stats:
        updated = dict(stats)
        updated["stddev"] = updated.pop("std_dev")
        return updated
    if "variance" not in stats:
        return dict(stats)
    updated: dict[str, float] = {}
    for key, value in stats.items():
        if key == "variance":
            updated["stddev"] = math.sqrt(value) if value >= 0.0 else float("nan")
        else:
            updated[key] = value
    return updated


def _select_spread_key(stats: Mapping[str, float]) -> str:
    """Prefer standard deviation when present; fall back to variance."""
    if "stddev" in stats:
        return "stddev"
    if "std_dev" in stats:
        return "std_dev"
    return "variance"


def print_distribution_summary(
    label: str,
    stats: Mapping[str, float],
    decimals: int = 3,
) -> None:
    """Print a summary line for a distribution's mean, spread, and skew."""
    spread_key = _select_spread_key(stats)
    spread_label = "stddev" if spread_key in ("stddev", "std_dev") else "variance"
    print(
        "{}: mean={:.{d}f}, {}={:.{d}f}, skew={:.{d}f}".format(
            label,
            stats["mean"],
            spread_label,
            stats[spread_key],
            stats["skew"],
            d=decimals,
        )
    )


def print_percent_comparison(
    label: str,
    percent_stats: Mapping[str, float],
    decimals: int = 2,
) -> None:
    """Print a percent-difference summary line."""
    spread_key = _select_spread_key(percent_stats)
    spread_label = "stddev" if spread_key in ("stddev", "std_dev") else "variance"
    print(
        "{}: mean={:.{d}f}%, {}={:.{d}f}%, skew={:.{d}f}%".format(
            label,
            percent_stats["mean"],
            spread_label,
            percent_stats[spread_key],
            percent_stats["skew"],
            d=decimals,
        )
    )
