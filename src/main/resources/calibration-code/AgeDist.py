# -*- coding: utf-8 -*-
"""
Class to study households' age distribution based on Wealth and Assets Survey data.
Creates weighted distributions for each age band as "<AgeBand>-<WAS_DATASET>-Weighted.csv".

@author: Adrian Carro, Max Stoddard
"""

from __future__ import annotations, division

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from was.CSVWrite import write_rows
from was.RowFilters import drop_missing_rows, filter_positive_values
from was.Timing import start_timer, end_timer
from was import Config as was_config
from was.Dataset import reload_was_modules


def run_age_distribution(dataset: str | None = None) -> dict[str, object]:
    """Generate weighted age distributions for a WAS dataset."""
    target_dataset = dataset or was_config.WAS_DATASET
    config, constants, io_module = reload_was_modules(target_dataset)
    timer_start = start_timer(os.path.basename(__file__), "calibration")

    age_columns = list(constants.WAS_DATASET_AGE_BAND_MAPS.keys())
    chunk = io_module.read_was_data(
        config.WAS_DATA_ROOT,
        [constants.WAS_WEIGHT] + age_columns,
    )
    pd.set_option("display.max_columns", None)

    chunk = chunk[age_columns + [constants.WAS_WEIGHT]]

    for age_column, bucket_data in constants.WAS_DATASET_AGE_BAND_MAPS.items():
        bucket_mapping = {
            **bucket_data["TEXT_MAPPING"],
            **bucket_data["WAS_VALUE_MAPPING"],
        }
        chunk[age_column] = chunk[age_column].map(bucket_mapping)

    # Filter down to keep only columns of interest & drop missing/invalid codes.
    chunk = drop_missing_rows(chunk, age_columns + [constants.WAS_WEIGHT])
    # Keep positive weights for weighted distributions.
    chunk = filter_positive_values(chunk, [constants.WAS_WEIGHT])

    output_files = {}
    for age_column, bucket_data in constants.WAS_DATASET_AGE_BAND_MAPS.items():
        # Map age buckets to middle of bucket value by using the corresponding dictionary.
        bin_edges = bucket_data["BIN_EDGES"]
        frequency, histogram_bin_edges = np.histogram(
            chunk[age_column].values,
            bins=bin_edges,
            density=True,
            weights=chunk[constants.WAS_WEIGHT].values,
        )

        # Write weighted age distribution for calibration.
        output_filename = f"{age_column}-{config.WAS_DATASET}-Weighted.csv"
        rows = []
        for element, lower_edge, upper_edge in zip(
            frequency, histogram_bin_edges[:-1], histogram_bin_edges[1:]
        ):
            if lower_edge == bin_edges[0] and element == 0:
                continue
            rows.append((lower_edge, upper_edge, element))
        write_rows(
            output_filename,
            "# Age (lower edge), Age (upper edge), Probability\n",
            rows,
        )
        output_files[age_column] = output_filename

    end_timer(timer_start)
    return {
        "dataset": config.WAS_DATASET,
        "age_columns": age_columns,
        "output_files": output_files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate WAS age distributions.")
    parser.add_argument(
        "--dataset",
        choices=[was_config.WAVE_3_DATA, was_config.ROUND_8_DATA],
        default=was_config.WAS_DATASET,
        help="Select the WAS dataset (W3 or R8).",
    )
    args = parser.parse_args()
    run_age_distribution(args.dataset)


if __name__ == "__main__":
    main()
