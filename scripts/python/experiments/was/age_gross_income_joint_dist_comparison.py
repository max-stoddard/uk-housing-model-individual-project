# -*- coding: utf-8 -*-
"""
Compare WAS Wave 3 and Round 8 age-by-gross-income joint distributions.
"""

from __future__ import annotations, division

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np

from scripts.python.helpers.was.config import WAVE_3_DATA, ROUND_8_DATA
from scripts.python.helpers.was.comparison_stats import (
    compute_percent_stats,
    format_currency,
    print_distribution_summary,
    print_percent_comparison,
    to_std_dev_stats,
)
from scripts.python.helpers.was.distributions import (
    align_edges_by_duplication,
    conditional_mean_variance_by_x,
    read_joint_distribution_grid,
)
from scripts.python.helpers.was.experiments import (
    build_was_comparison_rows,
    get_dataset_label,
    get_output_dir,
    write_stats_csv,
)
from scripts.python.helpers.was.plotting import apply_axis_grid, format_age_axis, format_currency_axis
from scripts.python.calibration.was import income_age_joint_prob_dist


def _align_age_bins(
    wave_edges: np.ndarray,
    wave_grid: np.ndarray,
    round_edges: np.ndarray,
    round_grid: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Align age bins by duplicating the final row for the shorter set."""
    if len(wave_edges) >= len(round_edges):
        round_edges, round_grid = align_edges_by_duplication(
            wave_edges,
            round_edges,
            round_grid,
        )
        return wave_edges, wave_grid, round_edges, round_grid
    wave_edges, wave_grid = align_edges_by_duplication(
        round_edges,
        wave_edges,
        wave_grid,
    )
    return wave_edges, wave_grid, round_edges, round_grid


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare WAS age-by-gross-income joint distributions."
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for generated stats and plots.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir or get_output_dir(__file__)
    wave_label, wave_period = get_dataset_label(WAVE_3_DATA)
    round_label, round_period = get_dataset_label(ROUND_8_DATA)
    wave_title = f"{wave_label} ({wave_period})"
    round_title = f"{round_label} ({round_period})"

    wave_min_net, wave_max_gross = income_age_joint_prob_dist.compute_income_bounds(
        WAVE_3_DATA
    )
    round_min_net, round_max_gross = income_age_joint_prob_dist.compute_income_bounds(
        ROUND_8_DATA
    )
    # Use shared log-income bins so differences are comparable across datasets.
    shared_income_edges = np.linspace(
        np.log(min(wave_min_net, round_min_net)),
        np.log(max(wave_max_gross, round_max_gross)),
        26,
    )

    wave_outputs = income_age_joint_prob_dist.run_income_age_joint_prob_dist(
        WAVE_3_DATA,
        income_bin_edges=shared_income_edges,
    )
    wave_age_edges, wave_income_edges, wave_gross = read_joint_distribution_grid(
        wave_outputs["output_files"]["gross"]
    )

    round_outputs = income_age_joint_prob_dist.run_income_age_joint_prob_dist(
        ROUND_8_DATA,
        income_bin_edges=shared_income_edges,
    )
    round_age_edges, round_income_edges, round_gross = read_joint_distribution_grid(
        round_outputs["output_files"]["gross"]
    )

    wave_age_edges, wave_gross, round_age_edges, round_gross = _align_age_bins(
        wave_age_edges,
        wave_gross,
        round_age_edges,
        round_gross,
    )
    if not np.allclose(wave_income_edges, round_income_edges):
        raise ValueError("Income bin edges are not aligned between datasets.")

    wave_stats = to_std_dev_stats(wave_outputs["gross_stats"])
    round_stats = to_std_dev_stats(round_outputs["gross_stats"])
    percent_stats = compute_percent_stats(wave_stats, round_stats)
    stats_rows = build_was_comparison_rows(
        wave_stats,
        round_stats,
        value_formatters={
            "mean": format_currency,
            "stddev": format_currency,
        },
    )
    stats_path = os.path.join(output_dir, "AgeGrossIncomeJointDistStats.csv")
    write_stats_csv(stats_path, stats_rows, separator=";")

    print_distribution_summary(
        f"{wave_title} gross income distribution",
        wave_stats,
    )
    print_distribution_summary(
        f"{round_title} gross income distribution",
        round_stats,
    )
    print_percent_comparison(
        "Comparison (Round 8 % vs Wave 3)",
        percent_stats,
    )

    # Compare mean and standard deviation of gross income by age for each wave.
    wave_age_mid, wave_mean, wave_variance = conditional_mean_variance_by_x(
        wave_age_edges,
        wave_income_edges,
        wave_gross,
        log_x=False,
        log_y=True,
    )
    wave_std_dev = np.sqrt(wave_variance)
    round_age_mid, round_mean, round_variance = conditional_mean_variance_by_x(
        round_age_edges,
        round_income_edges,
        round_gross,
        log_x=False,
        log_y=True,
    )
    round_std_dev = np.sqrt(round_variance)

    fig, axes = plt.subplots(nrows=2, figsize=(11, 8), sharex=True)
    axes[0].plot(
        wave_age_mid,
        wave_mean,
        marker="o",
        label=wave_title,
    )
    axes[0].plot(
        round_age_mid,
        round_mean,
        marker="s",
        label=round_title,
    )
    axes[0].set_ylabel("Mean gross income (GBP, log scale)")
    axes[0].set_yscale("log")
    apply_axis_grid(axes[0], axis="both")
    format_currency_axis(axes[0], axis="y")
    axes[0].legend()

    axes[1].plot(
        wave_age_mid,
        wave_std_dev,
        marker="o",
        label=wave_title,
    )
    axes[1].plot(
        round_age_mid,
        round_std_dev,
        marker="s",
        label=round_title,
    )
    axes[1].set_xlabel("Age (midpoint)")
    axes[1].set_ylabel("Gross income standard deviation (GBP, log scale)")
    axes[1].set_yscale("log")
    apply_axis_grid(axes[1], axis="both")
    format_age_axis(axes[1], axis="x")
    format_currency_axis(axes[1], axis="y")

    fig.tight_layout()
    fig.savefig(
        os.path.join(output_dir, "AgeGrossIncomeJointDistComparison.png"),
        dpi=300,
    )
    plt.show()


if __name__ == "__main__":
    main()
