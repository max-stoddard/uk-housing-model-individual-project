"""
Plotting helpers for WAS validation scripts.

@author: Max Stoddard
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np


def set_log_x_axis(ax: plt.Axes | None = None) -> None:
    """Set the x-axis to log scale on the provided axes."""
    axes = ax or plt.gca()
    axes.set_xscale("log")


def plot_hist_overlay(
    bin_edges: np.ndarray,
    model_hist: np.ndarray,
    data_hist: np.ndarray,
    xlabel: str,
    ylabel: str,
    title: str,
    model_label: str = "Model results",
    data_label: str = "WAS data",
    model_color: str = "b",
    data_color: str = "r",
    alpha: float = 0.5,
    log_x: bool = False,
    ax: plt.Axes | None = None,
) -> plt.Axes:
    """Plot model and data histogram overlays with shared bin edges."""
    axes = ax or plt.gca()
    bin_widths = [b - a for a, b in zip(bin_edges[:-1], bin_edges[1:])]
    axes.bar(
        bin_edges[:-1],
        height=model_hist,
        width=bin_widths,
        align="edge",
        label=model_label,
        alpha=alpha,
        color=model_color,
    )
    axes.bar(
        bin_edges[:-1],
        height=data_hist,
        width=bin_widths,
        align="edge",
        label=data_label,
        alpha=alpha,
        color=data_color,
    )
    if log_x:
        set_log_x_axis(axes)
    axes.set_xlabel(xlabel)
    axes.set_ylabel(ylabel)
    axes.legend()
    axes.set_title(title)
    return axes
