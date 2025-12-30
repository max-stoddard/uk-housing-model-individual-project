"""
Helper functions for writing data to CSV in WAS calibration and validation scripts.

@author: Max Stoddard
"""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np


def write_rows(
    file_name: str,
    header: str,
    rows: Iterable[Sequence[object]],
) -> None:
    """Write a CSV file with a header and iterable row values."""
    with open(file_name, "w") as handle:
        handle.write(header)
        for row in rows:
            handle.write(", ".join(str(value) for value in row) + "\n")


def write_1d_distribution(
    file_name: str,
    label: str,
    bin_edges: np.ndarray,
    frequency: np.ndarray,
    log_label: bool = False,
) -> None:
    """Write a 1D distribution with lower/upper edges and probabilities."""
    prefix = "Log " if log_label else ""
    header = (
        f"# {prefix}{label} (lower edge), {prefix}{label} (upper edge), Probability\n"
    )
    rows = (
        (lower_edge, upper_edge, element)
        for element, lower_edge, upper_edge in zip(
            frequency, bin_edges[:-1], bin_edges[1:]
        )
    )
    write_rows(file_name, header, rows)


def write_joint_distribution(
    file_name: str,
    x_label: str,
    y_label: str,
    frequency: np.ndarray,
    x_bins: np.ndarray,
    y_bins: np.ndarray,
    x_is_log: bool = False,
    y_is_log: bool = False,
    normalize_rows: bool = True,
    zero_ok: bool = False,
) -> None:
    """Write a 2D distribution with lower/upper edges and probabilities."""
    x_prefix = "Log " if x_is_log else ""
    y_prefix = "Log " if y_is_log else ""
    header = (
        f"# {x_prefix}{x_label} (lower edge), {x_prefix}{x_label} (upper edge), "
        f"{y_prefix}{y_label} (lower edge), {y_prefix}{y_label} (upper edge), Probability\n"
    )
    rows = []
    for line, x_lower, x_upper in zip(frequency, x_bins[:-1], x_bins[1:]):
        line_sum = sum(line)
        if normalize_rows and line_sum == 0 and zero_ok:
            for y_lower, y_upper in zip(y_bins[:-1], y_bins[1:]):
                rows.append((x_lower, x_upper, y_lower, y_upper, 0.0))
            continue
        for element, y_lower, y_upper in zip(line, y_bins[:-1], y_bins[1:]):
            value = element / line_sum if normalize_rows else element
            rows.append((x_lower, x_upper, y_lower, y_upper, value))
    write_rows(file_name, header, rows)
