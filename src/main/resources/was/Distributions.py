"""
Helpers for loading and reshaping binned distributions.

@author: Max Stoddard
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd


def read_binned_distribution(csv_path: str) -> pd.DataFrame:
    """Read a 1D binned distribution CSV into a tidy DataFrame."""
    return pd.read_csv(
        csv_path,
        comment="#",
        header=None,
        names=["lower_edge", "upper_edge", "probability"],
    )


def binned_distribution_to_edges(
    distribution: pd.DataFrame,
    log_edges: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return bin edges and probabilities from a binned distribution."""
    ordered = distribution.sort_values("lower_edge")
    lower = ordered["lower_edge"].to_numpy()
    upper = ordered["upper_edge"].to_numpy()
    edges = np.append(lower, upper[-1])
    if log_edges:
        edges = np.exp(edges)
    values = ordered["probability"].to_numpy()
    return edges, values


def read_joint_distribution(csv_path: str) -> pd.DataFrame:
    """Read a 2D joint distribution CSV into a tidy DataFrame."""
    return pd.read_csv(
        csv_path,
        comment="#",
        header=None,
        names=["x_lower", "x_upper", "y_lower", "y_upper", "probability"],
    )


def read_joint_distribution_grid(
    csv_path: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read a joint distribution CSV and return edges with grid values."""
    distribution = read_joint_distribution(csv_path)
    return joint_distribution_to_grid(distribution)


def log_histogram2d(
    x_values: pd.Series,
    y_values: pd.Series,
    x_bins: np.ndarray,
    y_bins: np.ndarray,
    weights: np.ndarray | None = None,
    density: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return a 2D histogram in log space using provided bins."""
    return np.histogram2d(
        np.log(x_values.values),
        np.log(y_values.values),
        bins=[x_bins, y_bins],
        weights=weights,
        density=density,
    )


def joint_distribution_to_grid(
    distribution: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert a joint distribution DataFrame into edges and a grid array."""
    x_lowers = np.sort(distribution["x_lower"].unique())
    y_lowers = np.sort(distribution["y_lower"].unique())

    grid = np.zeros((len(x_lowers), len(y_lowers)))
    for i, x_lower in enumerate(x_lowers):
        row = distribution[distribution["x_lower"] == x_lower].sort_values("y_lower")
        grid[i, :] = row["probability"].values

    max_x_upper = distribution["x_upper"].max()
    max_y_upper = distribution["y_upper"].max()
    x_edges = np.append(x_lowers, max_x_upper)
    y_edges = np.append(y_lowers, max_y_upper)
    return x_edges, y_edges, grid


def conditional_mean_by_x(
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    grid: np.ndarray,
    log_x: bool = False,
    log_y: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return midpoints and conditional means of y for each x bin."""
    x_mid, mean, _ = conditional_mean_variance_by_x(
        x_edges,
        y_edges,
        grid,
        log_x=log_x,
        log_y=log_y,
    )
    return x_mid, mean


def conditional_mean_variance_by_x(
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    grid: np.ndarray,
    log_x: bool = False,
    log_y: bool = False,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return midpoints with conditional mean and variance of y for each x bin."""
    x_mid = (x_edges[:-1] + x_edges[1:]) / 2.0
    y_mid = (y_edges[:-1] + y_edges[1:]) / 2.0
    if log_x:
        x_mid = np.exp(x_mid)
    if log_y:
        y_mid = np.exp(y_mid)

    means = []
    variances = []
    for row in grid:
        total = float(row.sum())
        if total == 0.0:
            means.append(float("nan"))
            variances.append(float("nan"))
            continue
        probs = row / total
        mean = float(probs @ y_mid)
        variance = float(probs @ (y_mid - mean) ** 2)
        means.append(mean)
        variances.append(variance)
    return x_mid, np.asarray(means), np.asarray(variances)


def align_edges_by_duplication(
    reference_edges: np.ndarray,
    edges: np.ndarray,
    grid: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Align shorter edges to a reference by duplicating the final row."""
    if len(edges) == len(reference_edges):
        return edges, grid
    if len(edges) + 1 != len(reference_edges):
        raise ValueError("Unable to align edges to reference.")
    width = edges[-1] - edges[-2]
    new_edges = np.append(edges, edges[-1] + width)
    new_grid = np.vstack([grid, grid[-1]])
    return new_edges, new_grid


def split_final_x_bin_uniform(
    x_edges: np.ndarray,
    grid: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Split the final x bin into two, duplicating the last row."""
    width = x_edges[-1] - x_edges[-2]
    new_edge = x_edges[-1] + width
    new_edges = np.append(x_edges, new_edge)
    new_grid = np.vstack([grid, grid[-1]])
    return new_edges, new_grid
