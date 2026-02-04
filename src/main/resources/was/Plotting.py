"""
Plotting helpers for WAS validation scripts.

@author: Max Stoddard
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm
from matplotlib.ticker import FuncFormatter


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
    title: str | None,
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
    if title:
        axes.set_title(title)
    return axes


def print_hist_percent_diff(
    bin_edges: np.ndarray,
    model_hist: np.ndarray,
    data_hist: np.ndarray,
    label: str,
    print_buckets: bool = False,
) -> None:
    """Print percentage-point differences per bucket and total absolute difference."""
    percent_diff = (model_hist - data_hist) * 100.0
    total_diff = float(np.sum(np.abs(model_hist - data_hist)) * 100.0)
    print(f"{label} total diff: {total_diff:.6f} %")
    if not print_buckets:
        return
    for lower_edge, upper_edge, diff, model_value, data_value in zip(
        bin_edges[:-1], bin_edges[1:], percent_diff, model_hist, data_hist
    ):
        print(
            f"{label} bucket {lower_edge}, {upper_edge}: "
            f"{diff:.6f} % (model={model_value:.6f}, data={data_value:.6f})"
        )


def format_currency_axis(
    ax: plt.Axes,
    axis: str = "y",
    symbol: str = "£",
) -> None:
    """Format an axis with currency ticks and two decimals."""
    formatter = FuncFormatter(lambda value, _: f"{symbol}{value:,.2f}")
    if axis == "x":
        axis_obj = ax.xaxis
    elif axis == "y":
        axis_obj = ax.yaxis
    else:
        raise ValueError("axis must be 'x' or 'y'.")
    axis_obj.set_major_formatter(formatter)
    axis_obj.set_minor_formatter(formatter)
    axis_obj.offsetText.set_visible(False)


def format_age_axis(ax: plt.Axes, axis: str = "x") -> None:
    """Format an axis with integer age ticks."""
    formatter = FuncFormatter(lambda value, _: f"{value:.0f}")
    if axis == "x":
        ax.xaxis.set_major_formatter(formatter)
    elif axis == "y":
        ax.yaxis.set_major_formatter(formatter)
    else:
        raise ValueError("axis must be 'x' or 'y'.")


def apply_axis_grid(ax: plt.Axes, axis: str = "both", alpha: float = 0.3) -> None:
    """Add faint gridlines to the requested axis."""
    ax.grid(True, axis=axis, alpha=alpha)


def plot_joint_difference(
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    difference: np.ndarray,
    xlabel: str,
    ylabel: str,
    colorbar_label: str,
    log_x: bool = False,
    log_y: bool = True,
    cmap: str = "coolwarm",
    ax: plt.Axes | None = None,
) -> plt.Axes:
    """Plot a joint-distribution difference heatmap centered on zero."""
    axes = ax or plt.gca()
    max_abs = float(np.max(np.abs(difference))) if difference.size else 0.0
    norm = (
        TwoSlopeNorm(vcenter=0.0, vmin=-max_abs, vmax=max_abs)
        if max_abs > 0.0
        else None
    )
    x_plot_edges = np.exp(x_edges) if log_x else x_edges
    y_plot_edges = np.exp(y_edges) if log_y else y_edges
    mesh = axes.pcolormesh(
        x_plot_edges,
        y_plot_edges,
        difference.T,
        shading="auto",
        cmap=cmap,
        norm=norm,
    )
    if log_x:
        axes.set_xscale("log")
    if log_y:
        axes.set_yscale("log")
    axes.set_xlabel(xlabel)
    axes.set_ylabel(ylabel)
    plt.colorbar(mesh, ax=axes, label=colorbar_label)
    return axes
