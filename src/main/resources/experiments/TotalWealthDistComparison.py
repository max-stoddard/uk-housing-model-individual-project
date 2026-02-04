# -*- coding: utf-8 -*-
"""
Compare WAS Wave 3 and Round 8 total wealth distributions.
"""

from __future__ import annotations, division

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import LogLocator, NullLocator

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "calibration-code"))
)
from was.Config import WAVE_3_DATA, ROUND_8_DATA
from was.ComparisonStats import (
    compute_percent_stats,
    format_currency,
    print_distribution_summary,
    print_percent_comparison,
    to_std_dev_stats,
)
from was.Distributions import binned_distribution_to_edges, read_binned_distribution
from was.Experiments import (
    build_was_comparison_rows,
    get_dataset_label,
    get_output_dir,
    write_stats_csv,
)
from was.Plotting import apply_axis_grid, format_currency_axis, plot_hist_overlay
import TotalWealthDist


def _pick_primary_output(output_files: list[str]) -> str:
    """Prefer a stable total-wealth measure for comparisons."""
    preferred = [
        "NetFinancialWealth-TotalPropertyWealth-Weighted.csv",
        "GrossFinancialWealth-GrossHousingWealth-Weighted.csv",
        "NetFinancialWealth-GrossHousingWealth-Weighted.csv",
    ]
    for name in preferred:
        if name in output_files:
            return name
    return output_files[0]


def main() -> None:
    output_dir = get_output_dir(__file__)
    wave_label, wave_period = get_dataset_label(WAVE_3_DATA)
    round_label, round_period = get_dataset_label(ROUND_8_DATA)
    wave_title = f"{wave_label} ({wave_period})"
    round_title = f"{round_label} ({round_period})"

    # Read the W3 distribution before running R8 to avoid overwriting filenames.
    wave_outputs = TotalWealthDist.run_total_wealth_distribution(WAVE_3_DATA)
    wave_file = _pick_primary_output(wave_outputs["output_files"])
    wave_dist = read_binned_distribution(wave_file)

    round_outputs = TotalWealthDist.run_total_wealth_distribution(ROUND_8_DATA)
    round_file = _pick_primary_output(round_outputs["output_files"])
    round_dist = read_binned_distribution(round_file)

    wave_log_edges, wave_hist = binned_distribution_to_edges(
        wave_dist,
        log_edges=False,
    )
    round_log_edges, round_hist = binned_distribution_to_edges(
        round_dist,
        log_edges=False,
    )
    wave_edges = np.exp(wave_log_edges)
    round_edges = np.exp(round_log_edges)

    if wave_edges.shape != round_edges.shape:
        raise ValueError("Wealth bin edges are not aligned between datasets.")

    wave_stats = to_std_dev_stats(wave_outputs["output_stats"][wave_file])
    round_stats = to_std_dev_stats(round_outputs["output_stats"][round_file])
    percent_stats = compute_percent_stats(wave_stats, round_stats)
    stats_rows = build_was_comparison_rows(
        wave_stats,
        round_stats,
        value_formatters={
            "mean": format_currency,
            "stddev": format_currency,
        },
    )
    stats_path = os.path.join(output_dir, "TotalWealthDistStats.csv")
    write_stats_csv(stats_path, stats_rows, separator=";")

    print_distribution_summary(
        f"{wave_title} total wealth distribution",
        wave_stats,
    )
    print_distribution_summary(
        f"{round_title} total wealth distribution",
        round_stats,
    )
    print_percent_comparison(
        "Comparison (Round 8 % vs Wave 3)",
        percent_stats,
    )

    fig, ax = plt.subplots(figsize=(11, 5))
    plot_hist_overlay(
        wave_edges,
        wave_hist,
        round_hist,
        xlabel="Total wealth (GBP, log scale)",
        ylabel="Probability density",
        title=None,
        model_label=wave_title,
        data_label=round_title,
        log_x=True,
        ax=ax,
    )
    apply_axis_grid(ax, axis="both")
    format_currency_axis(ax, axis="x")
    ax.xaxis.set_major_locator(LogLocator(base=10, subs=(1.0,), numticks=100))
    ax.xaxis.set_minor_locator(NullLocator())

    fig.tight_layout()
    fig.savefig(
        os.path.join(output_dir, "TotalWealthDistComparison.png"),
        dpi=300,
    )
    plt.show()


if __name__ == "__main__":
    main()
