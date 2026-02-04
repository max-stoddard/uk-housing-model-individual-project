# -*- coding: utf-8 -*-
"""
Class to study households' income distribution depending on their age based on
Wealth and Assets Survey data. This is the code used to create file
"AgeGrossIncomeJointDist.csv".

@author: Adrian Carro, Max Stoddard
"""

from __future__ import annotations, division

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from was.CSVWrite import write_joint_distribution
from was.RowFilters import filter_percentile_outliers, filter_positive_values
from was.Timing import start_timer, end_timer
from was import Config as was_config
from was import DerivedColumns as was_derived
from was.Dataset import reload_was_modules
from was.Statistics import weighted_mean_variance_skew, weighted_stats_by_bins


def _load_income_age_chunk(
    dataset: str,
) -> tuple[pd.DataFrame, dict[str, object], object, object, object]:
    """Load and filter income/age data for the selected WAS dataset."""
    config, constants, io_module, derived = reload_was_modules(
        dataset,
        extra_modules=(was_derived,),
    )
    age_column_key = next(iter(constants.WAS_DATASET_AGE_BAND_MAPS))
    use_column_constants = [
        constants.WAS_WEIGHT,
        constants.WAS_GROSS_ANNUAL_INCOME,
        constants.WAS_NET_ANNUAL_INCOME,
        constants.WAS_GROSS_ANNUAL_RENTAL_INCOME,
        constants.WAS_NET_ANNUAL_RENTAL_INCOME,
        age_column_key,
    ]
    chunk = io_module.read_was_data(config.WAS_DATA_ROOT, use_column_constants)

    derived.derive_non_rent_income_columns(chunk)
    chunk.rename(columns={age_column_key: "Age"}, inplace=True)
    chunk = chunk[
        [
            "Age",
            derived.GROSS_NON_RENT_INCOME,
            derived.NET_NON_RENT_INCOME,
            constants.WAS_WEIGHT,
        ]
    ]
    # Trim extreme tails so the joint distribution is less sensitive to outliers.
    chunk = filter_percentile_outliers(
        chunk,
        lower_bound_column=derived.NET_NON_RENT_INCOME,
        upper_bound_column=derived.GROSS_NON_RENT_INCOME,
    )
    chunk = filter_positive_values(
        chunk,
        [derived.GROSS_NON_RENT_INCOME, derived.NET_NON_RENT_INCOME],
    )
    if chunk.empty:
        raise ValueError("No rows left after income filters.")

    age_bucket_data = constants.WAS_DATASET_AGE_BAND_MAPS[age_column_key]
    age_from_text = chunk["Age"].map(age_bucket_data["TEXT_MAPPING"])
    age_from_values = pd.to_numeric(chunk["Age"], errors="coerce").map(
        age_bucket_data["WAS_VALUE_MAPPING"]
    )
    chunk["Age"] = age_from_text.fillna(age_from_values)

    return chunk, age_bucket_data, config, constants, derived


def compute_income_bounds(dataset: str | None = None) -> tuple[float, float]:
    """Return min net and max gross non-rent income after filtering."""
    target_dataset = dataset or was_config.WAS_DATASET
    chunk, _, _, _, derived = _load_income_age_chunk(target_dataset)
    min_net_income = float(chunk[derived.NET_NON_RENT_INCOME].min())
    max_gross_income = float(chunk[derived.GROSS_NON_RENT_INCOME].max())
    return min_net_income, max_gross_income


def run_income_age_joint_prob_dist(
    dataset: str | None = None,
    income_bin_edges: np.ndarray | None = None,
) -> dict[str, object]:
    """Generate joint distributions of income by age for a WAS dataset."""
    target_dataset = dataset or was_config.WAS_DATASET
    timer_start = start_timer(os.path.basename(__file__), "calibration")

    chunk, age_bucket_data, config, constants, derived = _load_income_age_chunk(
        target_dataset
    )

    if income_bin_edges is None:
        min_net_income = float(chunk[derived.NET_NON_RENT_INCOME].min())
        max_gross_income = float(chunk[derived.GROSS_NON_RENT_INCOME].max())
        income_bin_edges = np.linspace(
            np.log(min_net_income),
            np.log(max_gross_income),
            26,
        )

    # Capture a weighted summary of gross non-rent income to contextualize shifts.
    gross_stats = weighted_mean_variance_skew(
        chunk[derived.GROSS_NON_RENT_INCOME].astype(float),
        chunk[constants.WAS_WEIGHT].astype(float),
    )
    age_gross_stats = weighted_stats_by_bins(
        chunk["Age"].astype(float),
        chunk[derived.GROSS_NON_RENT_INCOME].astype(float),
        chunk[constants.WAS_WEIGHT].astype(float),
        age_bucket_data["BIN_EDGES"],
    )

    age_bin_edges = age_bucket_data["BIN_EDGES"][1:]
    frequency_gross = np.histogram2d(
        chunk["Age"].values,
        np.log(chunk[derived.GROSS_NON_RENT_INCOME].values),
        bins=[age_bin_edges, income_bin_edges],
        density=True,
        weights=chunk[constants.WAS_WEIGHT].values,
    )[0]
    frequency_net = np.histogram2d(
        chunk["Age"].values,
        np.log(chunk[derived.NET_NON_RENT_INCOME].values),
        bins=[age_bin_edges, income_bin_edges],
        density=True,
        weights=chunk[constants.WAS_WEIGHT].values,
    )[0]

    output_files = {}
    write_joint_distribution(
        "AgeGrossIncomeJointDist.csv",
        "Age",
        "Gross Income",
        frequency_gross,
        age_bin_edges,
        income_bin_edges,
        x_is_log=False,
        y_is_log=True,
    )
    output_files["gross"] = "AgeGrossIncomeJointDist.csv"
    write_joint_distribution(
        "AgeNetIncomeJointDist.csv",
        "Age",
        "Net Income",
        frequency_net,
        age_bin_edges,
        income_bin_edges,
        x_is_log=False,
        y_is_log=True,
    )
    output_files["net"] = "AgeNetIncomeJointDist.csv"

    end_timer(timer_start)
    return {
        "dataset": config.WAS_DATASET,
        "output_files": output_files,
        "age_bin_edges": age_bin_edges,
        "income_bin_edges": income_bin_edges,
        "gross_stats": {
            "mean": gross_stats[0],
            "variance": gross_stats[1],
            "skew": gross_stats[2],
        },
        "age_gross_stats": age_gross_stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate joint income/age distributions for WAS."
    )
    parser.add_argument(
        "--dataset",
        choices=[was_config.WAVE_3_DATA, was_config.ROUND_8_DATA],
        default=was_config.WAS_DATASET,
        help="Select the WAS dataset (W3 or R8).",
    )
    args = parser.parse_args()
    run_income_age_joint_prob_dist(args.dataset)


if __name__ == "__main__":
    main()
