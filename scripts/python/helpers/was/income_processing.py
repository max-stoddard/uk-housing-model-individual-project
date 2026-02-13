"""
Helpers for stable income filtering and bounds in WAS calibrations.

@author: Max Stoddard
"""

from __future__ import annotations

import pandas as pd

from scripts.python.helpers.was.row_filters import (
    filter_percentile_outliers,
    filter_positive_values,
)

DEFAULT_INCOME_TRIM_PERCENTILE = 0.01


def filter_positive_then_trim_income_rows(
    chunk: pd.DataFrame,
    gross_income_column: str,
    net_income_column: str,
    percentile: float = DEFAULT_INCOME_TRIM_PERCENTILE,
) -> pd.DataFrame:
    """Filter to positive incomes, then trim extreme tails by percentile."""
    filtered = filter_positive_values(
        chunk,
        [gross_income_column, net_income_column],
    )
    return filter_percentile_outliers(
        filtered,
        lower_bound_column=net_income_column,
        upper_bound_column=gross_income_column,
        percentile=percentile,
    )


def resolve_income_bounds(
    chunk: pd.DataFrame,
    gross_income_column: str,
    net_income_column: str,
) -> tuple[float, float]:
    """Return validated lower/upper income bounds from filtered rows."""
    min_net_income = float(chunk[net_income_column].min())
    max_gross_income = float(chunk[gross_income_column].max())
    if min_net_income <= 0 or max_gross_income <= min_net_income:
        raise ValueError(
            "Invalid income bounds after filtering: "
            f"min_net_income={min_net_income}, max_gross_income={max_gross_income}"
        )
    return min_net_income, max_gross_income
