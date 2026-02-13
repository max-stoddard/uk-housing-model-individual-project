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

import numpy as np
import pandas as pd

from scripts.python.helpers.was.csv_write import write_joint_distribution
from scripts.python.helpers.was.income_processing import (
    DEFAULT_INCOME_TRIM_PERCENTILE,
    filter_positive_then_trim_income_rows,
    resolve_income_bounds,
)
from scripts.python.helpers.was.timing import start_timer, end_timer
from scripts.python.helpers.was import config as was_config
from scripts.python.helpers.was import derived_columns as was_derived
from scripts.python.helpers.was.dataset import reload_was_modules
from scripts.python.helpers.was.statistics import weighted_mean_variance_skew, weighted_stats_by_bins
from scripts.python.helpers.common.paths import resolve_output_path

INCOME_TRIM_PERCENTILE = DEFAULT_INCOME_TRIM_PERCENTILE
ROUND8_OUTPUT_AGE_MAX = 95.0


def _filter_income_rows(
    chunk: pd.DataFrame,
    gross_income_column: str,
    net_income_column: str,
) -> pd.DataFrame:
    """Apply stable positive-value and tail trimming filters for income rows."""
    return filter_positive_then_trim_income_rows(
        chunk,
        gross_income_column=gross_income_column,
        net_income_column=net_income_column,
        percentile=INCOME_TRIM_PERCENTILE,
    )


def _resolve_income_bounds(
    chunk: pd.DataFrame,
    gross_income_column: str,
    net_income_column: str,
) -> tuple[float, float]:
    """Compute lower/upper bounds used for automatic income binning."""
    return resolve_income_bounds(
        chunk,
        gross_income_column=gross_income_column,
        net_income_column=net_income_column,
    )


def _resolve_age_bin_edges(age_bucket_data: dict[str, object], dataset: str) -> np.ndarray:
    """Return age bin edges for output/statistics, with dataset-specific adjustments."""
    age_bin_edges = np.asarray(age_bucket_data["BIN_EDGES"], dtype=float).copy()
    if dataset == was_config.ROUND_8_DATA and age_bin_edges.size >= 2:
        age_bin_edges[-1] = ROUND8_OUTPUT_AGE_MAX
    if np.any(np.diff(age_bin_edges) <= 0):
        raise ValueError(f"Age bin edges must be strictly increasing, got {age_bin_edges.tolist()}")
    return age_bin_edges


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
    chunk = _filter_income_rows(
        chunk,
        derived.GROSS_NON_RENT_INCOME,
        derived.NET_NON_RENT_INCOME,
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
    return _resolve_income_bounds(
        chunk,
        derived.GROSS_NON_RENT_INCOME,
        derived.NET_NON_RENT_INCOME,
    )


def run_income_age_joint_prob_dist(
    dataset: str | None = None,
    income_bin_edges: np.ndarray | None = None,
    output_dir: str | None = None,
) -> dict[str, object]:
    """Generate joint distributions of income by age for a WAS dataset."""
    target_dataset = dataset or was_config.WAS_DATASET
    timer_start = start_timer(os.path.basename(__file__), "calibration")

    chunk, age_bucket_data, config, constants, derived = _load_income_age_chunk(
        target_dataset
    )

    if income_bin_edges is None:
        min_net_income, max_gross_income = _resolve_income_bounds(
            chunk,
            derived.GROSS_NON_RENT_INCOME,
            derived.NET_NON_RENT_INCOME,
        )
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
        _resolve_age_bin_edges(age_bucket_data, target_dataset),
    )

    age_bin_edges = _resolve_age_bin_edges(age_bucket_data, target_dataset)[1:]
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
    gross_filename = "AgeGrossIncomeJointDist.csv"
    gross_output_path = resolve_output_path(gross_filename, output_dir)
    write_joint_distribution(
        gross_output_path,
        "Age",
        "Gross Income",
        frequency_gross,
        age_bin_edges,
        income_bin_edges,
        x_is_log=False,
        y_is_log=True,
    )
    output_files["gross"] = gross_output_path
    net_filename = "AgeNetIncomeJointDist.csv"
    net_output_path = resolve_output_path(net_filename, output_dir)
    write_joint_distribution(
        net_output_path,
        "Age",
        "Net Income",
        frequency_net,
        age_bin_edges,
        income_bin_edges,
        x_is_log=False,
        y_is_log=True,
    )
    output_files["net"] = net_output_path

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
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory for output files. Defaults to current working directory.",
    )
    args = parser.parse_args()
    run_income_age_joint_prob_dist(args.dataset, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
