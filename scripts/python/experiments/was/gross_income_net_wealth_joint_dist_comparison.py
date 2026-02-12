# -*- coding: utf-8 -*-
"""
Compare WAS Wave 3 and Round 8 gross-income vs net-wealth joint distributions.
"""

from __future__ import annotations, division

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import LogLocator, NullLocator

from scripts.python.helpers.was.config import WAVE_3_DATA, ROUND_8_DATA
from scripts.python.helpers.was.comparison_stats import format_currency, to_std_dev_stats
from scripts.python.helpers.was.distributions import (
    conditional_mean_variance_by_x,
    read_joint_distribution_grid,
)
from scripts.python.helpers.was.experiments import (
    build_was_comparison_rows,
    get_dataset_label,
    get_output_dir,
    write_stats_csv,
)
from scripts.python.helpers.was.plotting import apply_axis_grid, format_currency_axis
from scripts.python.calibration.was import wealth_income_joint_prob_dist


def _build_measure_rows(
    measure: str,
    wave_stats: dict[str, float],
    round_stats: dict[str, float],
) -> list[dict[str, str]]:
    """Build formatted rows for a specific measure."""
    money_formatters = {"mean": format_currency, "stddev": format_currency}
    rows = build_was_comparison_rows(
        wave_stats,
        round_stats,
        value_formatters=money_formatters,
    )
    for row in rows:
        row["measure"] = measure
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare WAS gross-income vs net-wealth joint distributions."
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

    wave_min_net, wave_max_gross, wave_min_wealth, wave_max_wealth = (
        wealth_income_joint_prob_dist.compute_income_wealth_bounds(WAVE_3_DATA)
    )
    round_min_net, round_max_gross, round_min_wealth, round_max_wealth = (
        wealth_income_joint_prob_dist.compute_income_wealth_bounds(ROUND_8_DATA)
    )
    # Use shared bins so the joint-distribution differences are comparable.
    shared_income_edges = np.linspace(
        np.log(min(wave_min_net, round_min_net)),
        np.log(max(wave_max_gross, round_max_gross)),
        26,
    )
    shared_wealth_edges = np.linspace(
        np.log(min(wave_min_wealth, round_min_wealth)),
        np.log(max(wave_max_wealth, round_max_wealth)),
        21,
    )

    wave_outputs = wealth_income_joint_prob_dist.run_wealth_income_joint_prob_dist(
        WAVE_3_DATA,
        income_bin_edges=shared_income_edges,
        wealth_bin_edges=shared_wealth_edges,
    )
    wave_income_edges, wave_wealth_edges, wave_grid = read_joint_distribution_grid(
        wave_outputs["output_files"]["gross_net"]
    )

    round_outputs = wealth_income_joint_prob_dist.run_wealth_income_joint_prob_dist(
        ROUND_8_DATA,
        income_bin_edges=shared_income_edges,
        wealth_bin_edges=shared_wealth_edges,
    )
    round_income_edges, round_wealth_edges, round_grid = read_joint_distribution_grid(
        round_outputs["output_files"]["gross_net"]
    )

    if not np.allclose(wave_income_edges, round_income_edges) or not np.allclose(
        wave_wealth_edges, round_wealth_edges
    ):
        raise ValueError("Income or wealth bin edges are not aligned between datasets.")

    stats_rows = []
    stats_rows.extend(
        _build_measure_rows(
            "gross_income",
            to_std_dev_stats(wave_outputs["stats"]["gross_income"]),
            to_std_dev_stats(round_outputs["stats"]["gross_income"]),
        )
    )
    stats_rows.extend(
        _build_measure_rows(
            "net_wealth",
            to_std_dev_stats(wave_outputs["stats"]["net_wealth"]),
            to_std_dev_stats(round_outputs["stats"]["net_wealth"]),
        )
    )
    stats_path = os.path.join(output_dir, "GrossIncomeNetWealthJointDistStats.csv")
    stats_df = [
        {
            "measure": row["measure"],
            "dataset": row["dataset"],
            "period": row["period"],
            "mean": row["mean"],
            "stddev": row["stddev"],
            "skew": row["skew"],
        }
        for row in stats_rows
    ]
    write_stats_csv(stats_path, stats_df, separator=";")

    # Use conditional means so income and wealth stay on comparable log scales.
    wave_income_mid, wave_mean, wave_variance = conditional_mean_variance_by_x(
        wave_income_edges,
        wave_wealth_edges,
        wave_grid,
        log_x=True,
        log_y=True,
    )
    wave_std_dev = np.sqrt(wave_variance)
    wave_mask = wave_income_mid > 1000.0
    wave_income_mid = wave_income_mid[wave_mask]
    wave_mean = wave_mean[wave_mask]
    wave_std_dev = wave_std_dev[wave_mask]

    round_income_mid, round_mean, round_variance = conditional_mean_variance_by_x(
        round_income_edges,
        round_wealth_edges,
        round_grid,
        log_x=True,
        log_y=True,
    )
    round_std_dev = np.sqrt(round_variance)
    round_mask = round_income_mid > 1000.0
    round_income_mid = round_income_mid[round_mask]
    round_mean = round_mean[round_mask]
    round_std_dev = round_std_dev[round_mask]

    fig, axes = plt.subplots(nrows=2, figsize=(11, 8), sharex=True)
    axes[0].plot(
        wave_income_mid,
        wave_mean,
        marker="o",
        label=wave_title,
    )
    axes[0].plot(
        round_income_mid,
        round_mean,
        marker="s",
        label=round_title,
    )
    axes[0].set_ylabel("Mean net wealth (GBP, log scale)")
    axes[0].set_yscale("log")
    apply_axis_grid(axes[0], axis="both")
    format_currency_axis(axes[0], axis="y")
    axes[0].legend()

    axes[1].plot(
        wave_income_mid,
        wave_std_dev,
        marker="o",
        label=wave_title,
    )
    axes[1].plot(
        round_income_mid,
        round_std_dev,
        marker="s",
        label=round_title,
    )
    axes[1].set_xlabel("Gross income (GBP, log scale)")
    axes[1].set_ylabel("Net wealth standard deviation (GBP, log scale)")
    axes[1].set_xscale("log")
    axes[1].set_yscale("log")
    apply_axis_grid(axes[1], axis="both")
    format_currency_axis(axes[1], axis="x")
    format_currency_axis(axes[1], axis="y")

    for axis in axes:
        axis.xaxis.set_major_locator(
            LogLocator(base=10, subs=(1.0, 2.0, 5.0), numticks=8)
        )
        axis.yaxis.set_major_locator(
            LogLocator(base=10, subs=(1.0, 2.0, 5.0), numticks=8)
        )
        axis.xaxis.set_minor_locator(NullLocator())
        axis.yaxis.set_minor_locator(NullLocator())

    fig.tight_layout()
    fig.savefig(
        os.path.join(output_dir, "GrossIncomeNetWealthJointDistComparison.png"),
        dpi=300,
    )
    plt.show()


if __name__ == "__main__":
    main()
