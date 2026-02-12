# -*- coding: utf-8 -*-
"""
Compare WAS Wave 3 and Round 8 age distributions using generated calibration CSVs.

Creates distributions by running AgeDist for each dataset, then plots the resulting
age bin histograms and prints mean/standard-deviation/skew statistics.

@author: Max Stoddard
"""

from __future__ import annotations, division

import argparse
import os

import matplotlib.pyplot as plt
import pandas as pd

from scripts.python.helpers.was.config import WAVE_3_DATA, ROUND_8_DATA
from scripts.python.helpers.was.comparison_stats import (
    compute_percent_stats,
    print_distribution_summary,
    print_percent_comparison,
    to_std_dev_stats,
)
from scripts.python.helpers.was.distributions import read_binned_distribution
from scripts.python.helpers.was.experiments import (
    build_was_comparison_rows,
    get_dataset_label,
    get_output_dir,
)
from scripts.python.helpers.was.plotting import apply_axis_grid, format_age_axis
from scripts.python.helpers.was.statistics import mean_variance_skew, normalize_distribution
from scripts.python.calibration.was import age_dist


def _split_final_bin_uniform(distribution: pd.DataFrame) -> pd.DataFrame:
    """Split the final bin into two equal-width bins, splitting mass uniformly."""
    if distribution.empty:
        return distribution
    last_row = distribution.iloc[-1]
    width = float(last_row["upper_edge"] - last_row["lower_edge"])
    if width <= 0:
        return distribution
    split_point = float(last_row["upper_edge"])
    extended_upper = split_point + width
    half_prob = float(last_row["probability"]) / 2.0

    trimmed = distribution.iloc[:-1].copy()
    split_rows = pd.DataFrame(
        [
            {
                "lower_edge": float(last_row["lower_edge"]),
                "upper_edge": split_point,
                "probability": half_prob,
            },
            {
                "lower_edge": split_point,
                "upper_edge": extended_upper,
                "probability": half_prob,
            },
        ]
    )
    return pd.concat([trimmed, split_rows], ignore_index=True)


def _plot_overlay(
    wave_3: pd.DataFrame,
    round_8: pd.DataFrame,
    wave_3_label: str,
    round_8_label: str,
    output_path: str | None = None,
) -> None:
    """Plot overlayed age distributions with shared styling."""
    fig, ax = plt.subplots(figsize=(10, 6))

    wave_3_prob = normalize_distribution(wave_3["probability"])
    round_8_prob = normalize_distribution(round_8["probability"])

    wave_3_widths = wave_3["upper_edge"] - wave_3["lower_edge"]
    round_8_widths = round_8["upper_edge"] - round_8["lower_edge"]

    ax.bar(
        wave_3["lower_edge"],
        height=wave_3_prob,
        width=wave_3_widths,
        align="edge",
        alpha=0.5,
        color="b",
        label=wave_3_label,
    )
    ax.bar(
        round_8["lower_edge"],
        height=round_8_prob,
        width=round_8_widths,
        align="edge",
        alpha=0.5,
        color="r",
        label=round_8_label,
    )

    ax.set_xlabel("Age (lower edge)")
    ax.set_ylabel("Frequency (fraction of cases)")
    ax.legend()
    apply_axis_grid(ax, axis="both")
    format_age_axis(ax, axis="x")

    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=300)
    plt.show()


def _pick_primary_age_csv(output_files: dict[str, str]) -> str:
    """Pick the most comparable age band output for plotting."""
    for preferred in ("Age8", "Age9", "Age15"):
        if preferred in output_files:
            return output_files[preferred]
    return next(iter(output_files.values()))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare WAS Wave 3 and Round 8 age distributions."
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

    wave_3_outputs = age_dist.run_age_distribution(WAVE_3_DATA)
    round_8_outputs = age_dist.run_age_distribution(ROUND_8_DATA)

    wave_3_csv = _pick_primary_age_csv(wave_3_outputs["output_files"])
    round_8_csv = _pick_primary_age_csv(round_8_outputs["output_files"])

    wave_3_dist = read_binned_distribution(wave_3_csv)
    round_8_dist = read_binned_distribution(round_8_csv)
    round_8_dist = _split_final_bin_uniform(round_8_dist)

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

    stats_path = os.path.join(output_dir, "AgeDistributionStats.csv")
    stats_df = pd.DataFrame(stats_rows)
    stats_df.to_csv(stats_path, index=False)

    print_distribution_summary(f"{wave_title} age distribution", wave_3_stats)
    print_distribution_summary(f"{round_title} age distribution", round_8_stats)
    print_percent_comparison(
        "Comparison (Round 8 % vs Wave 3)",
        percent_stats,
    )

    _plot_overlay(
        wave_3_dist,
        round_8_dist,
        wave_title,
        round_title,
        output_path=os.path.join(output_dir, "AgeDistributionComparison.png"),
    )


if __name__ == "__main__":
    main()
