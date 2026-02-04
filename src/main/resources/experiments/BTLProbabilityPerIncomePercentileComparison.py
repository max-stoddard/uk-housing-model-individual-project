# -*- coding: utf-8 -*-
"""
Compare WAS Wave 3 and Round 8 BTL probability by income percentile bins.

Creates distributions by running the BTL probability computation for each dataset,
then plots the resulting curves and writes LaTeX-friendly summary statistics.

@author: Max Stoddard
"""

from __future__ import annotations, division

import os
import sys

import matplotlib.pyplot as plt
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "calibration-code"))
)
from was.Config import WAVE_3_DATA, ROUND_8_DATA
from was.ComparisonStats import (
    compute_percent_stats,
    print_distribution_summary,
    print_percent_comparison,
    to_std_dev_stats,
)
from was.CSVWrite import write_rows
from was.Distributions import read_binned_distribution
from was.Experiments import (
    build_was_comparison_rows,
    get_dataset_label,
    get_output_dir,
    get_project_root,
)
from was.Plotting import apply_axis_grid
from was.Statistics import mean_variance_skew
import BTLProbabilityPerIncomePercentileBin


def _plot_overlay(
    wave_3: pd.DataFrame,
    round_8: pd.DataFrame,
    wave_3_label: str,
    round_8_label: str,
    output_path: str | None = None,
) -> None:
    """Plot overlayed BTL probability curves with shared styling."""
    fig, ax = plt.subplots(figsize=(10, 6))

    wave_3_mid = (wave_3["lower_edge"] + wave_3["upper_edge"]) / 2.0
    round_8_mid = (round_8["lower_edge"] + round_8["upper_edge"]) / 2.0

    ax.plot(wave_3_mid * 100, wave_3["probability"], color="b", label=wave_3_label)
    ax.plot(round_8_mid * 100, round_8["probability"], color="r", label=round_8_label)

    ax.set_xlabel("Gross non-rental income percentile (%)")
    ax.set_ylabel("BTL probability")
    ax.legend()
    apply_axis_grid(ax, axis="both")
    ax.set_xlim(0, 100)

    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=300)
    plt.show()


def _write_btl_probability(csv_path: str, distribution: pd.DataFrame) -> None:
    """Write a CSV with BTL probability per income percentile bin."""
    rows = distribution[["lower_edge", "upper_edge", "probability"]].itertuples(
        index=False, name=None
    )
    write_rows(
        csv_path,
        "# Gross non-rental income percentile (lower edge), "
        "gross non-rental income percentile (upper edge), BTL probability\n",
        rows,
    )


def main() -> None:
    output_dir = get_output_dir(__file__)
    root_dir = get_project_root(__file__)
    wave_label, wave_period = get_dataset_label(WAVE_3_DATA)
    round_label, round_period = get_dataset_label(ROUND_8_DATA)
    wave_title = f"{wave_label} ({wave_period})"
    round_title = f"{round_label} ({round_period})"

    wave_3_output = BTLProbabilityPerIncomePercentileBin.run_btl_probability_per_income_percentile_bin(
        WAVE_3_DATA
    )
    wave_3_dist = read_binned_distribution(wave_3_output["output_file"])
    _write_btl_probability(
        os.path.join(root_dir, "BTLProbabilityPerIncomePercentileBin-W3.csv"),
        wave_3_dist,
    )

    round_8_output = BTLProbabilityPerIncomePercentileBin.run_btl_probability_per_income_percentile_bin(
        ROUND_8_DATA
    )
    round_8_dist = read_binned_distribution(round_8_output["output_file"])
    _write_btl_probability(
        os.path.join(root_dir, "BTLProbabilityPerIncomePercentileBin-R8.csv"),
        round_8_dist,
    )

    wave_3_mean, wave_3_variance, wave_3_skew = mean_variance_skew(wave_3_dist)
    round_8_mean, round_8_variance, round_8_skew = mean_variance_skew(round_8_dist)

    wave_3_stats = to_std_dev_stats(
        {
            "mean": wave_3_mean,
            "variance": wave_3_variance,
            "skew": wave_3_skew,
        }
    )
    round_8_stats = to_std_dev_stats(
        {
            "mean": round_8_mean,
            "variance": round_8_variance,
            "skew": round_8_skew,
        }
    )
    percent_stats = compute_percent_stats(wave_3_stats, round_8_stats)
    stats_rows = build_was_comparison_rows(wave_3_stats, round_8_stats)

    stats_path = os.path.join(output_dir, "BTLProbabilityPerIncomePercentileStats.csv")
    stats_df = pd.DataFrame(stats_rows)
    stats_df.to_csv(stats_path, index=False)

    print_distribution_summary(
        f"{wave_title} BTL probability distribution",
        wave_3_stats,
    )
    print_distribution_summary(
        f"{round_title} BTL probability distribution",
        round_8_stats,
    )
    print_percent_comparison(
        "Comparison (Round 8 % vs Wave 3)",
        percent_stats,
    )

    _plot_overlay(
        wave_3_dist,
        round_8_dist,
        wave_title,
        round_title,
        output_path=os.path.join(
            output_dir, "BTLProbabilityPerIncomePercentileComparison.png"
        ),
    )


if __name__ == "__main__":
    main()
