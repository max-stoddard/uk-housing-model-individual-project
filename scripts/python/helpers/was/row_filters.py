"""
Filters for WAS calibration and validation dataframes.

@author: Max Stoddard
"""

from __future__ import annotations

import pandas as pd


def drop_missing_rows(chunk: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Drop rows with missing values in required columns."""
    return chunk.dropna(subset=columns)


def filter_positive_values(chunk: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Keep rows where all listed columns are strictly positive."""
    if not columns:
        return chunk
    return chunk[chunk[columns].gt(0).all(axis=1)]


def filter_percentile_outliers(
    chunk: pd.DataFrame,
    lower_bound_column: str,
    upper_bound_column: str,
    percentile: float = 0.01,
) -> pd.DataFrame:
    """Remove extreme low/high rows based on percentile bounds."""
    if chunk.empty or percentile <= 0:
        return chunk
    count = int(round(len(chunk.index) * percentile))
    if count <= 0 or count >= len(chunk.index):
        return chunk
    sorted_lower = chunk.sort_values(lower_bound_column)
    sorted_upper = chunk.sort_values(upper_bound_column)
    min_lower = sorted_lower.iloc[count][lower_bound_column]
    max_upper = sorted_upper.iloc[-count][upper_bound_column]
    return chunk[
        (chunk[lower_bound_column] >= min_lower)
        & (chunk[upper_bound_column] <= max_upper)
    ]
