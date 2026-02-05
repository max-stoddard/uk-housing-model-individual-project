# -*- coding: utf-8 -*-
"""
Class to study households' total wealth (financial + housing) distribution, for
validation purposes, based on Wealth and Assets Survey data.

@author: Adrian Carro, Max Stoddard
"""

from __future__ import annotations, division

import argparse
import os
import sys

import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from was.CSVWrite import write_1d_distribution
from was.RowFilters import filter_positive_values
from was.Timing import start_timer, end_timer
from was import Config as was_config
from was import DerivedColumns as was_derived
from was.Dataset import reload_was_modules
from was.Statistics import log_binned_mean_variance_skew


def run_total_wealth_distribution(dataset: str | None = None) -> dict[str, object]:
    """Generate total-wealth distributions for a WAS dataset."""
    target_dataset = dataset or was_config.WAS_DATASET
    config, constants, io_module, derived = reload_was_modules(
        target_dataset,
        extra_modules=(was_derived,),
    )
    timer_start = start_timer(os.path.basename(__file__), "validation")

    use_column_constants = [
        constants.WAS_WEIGHT,
        constants.WAS_GROSS_FINANCIAL_WEALTH,
        constants.WAS_NET_FINANCIAL_WEALTH,
        constants.WAS_NATIONAL_SAVINGS_VALUE,
        constants.WAS_CHILD_TRUST_FUND_VALUE,
        constants.WAS_CHILD_OTHER_SAVINGS_VALUE,
        constants.WAS_SAVINGS_ACCOUNTS_VALUE,
        constants.WAS_CASH_ISA_VALUE,
        constants.WAS_CURRENT_ACCOUNT_CREDIT_VALUE,
        constants.WAS_FORMAL_FINANCIAL_ASSETS,
        constants.WAS_TOTAL_PROPERTY_WEALTH,
        constants.WAS_PROPERTY_VALUE_SUM,
        constants.WAS_MAIN_RESIDENCE_VALUE,
        constants.WAS_OTHER_HOUSES_TOTAL_VALUE,
        constants.WAS_BTL_HOUSES_TOTAL_VALUE,
    ]
    chunk = io_module.read_was_data(config.WAS_DATA_ROOT, use_column_constants)

    derived.derive_liquid_financial_wealth_column(chunk)
    derived.derive_gross_housing_wealth_column(chunk)
    chunk = chunk[
        [
            constants.WAS_WEIGHT,
            constants.WAS_NET_FINANCIAL_WEALTH,
            constants.WAS_GROSS_FINANCIAL_WEALTH,
            derived.LIQ_FINANCIAL_WEALTH,
            constants.WAS_TOTAL_PROPERTY_WEALTH,
            constants.WAS_PROPERTY_VALUE_SUM,
            derived.GROSS_HOUSING_WEALTH,
        ]
    ]

    min_wealth_bin = 2.0
    max_wealth_bin = 16.0
    wealth_bin_edges = np.linspace(min_wealth_bin, max_wealth_bin, 57)

    financial_wealth_measures = [
        constants.WAS_NET_FINANCIAL_WEALTH,
        constants.WAS_GROSS_FINANCIAL_WEALTH,
        derived.LIQ_FINANCIAL_WEALTH,
    ]
    housing_wealth_measures = [
        constants.WAS_TOTAL_PROPERTY_WEALTH,
        constants.WAS_PROPERTY_VALUE_SUM,
        derived.GROSS_HOUSING_WEALTH,
    ]

    output_files = []
    output_stats = {}
    for financial_wealth_measure in financial_wealth_measures:
        for housing_wealth_measure in housing_wealth_measures:
            derived.derive_total_wealth_column(
                chunk,
                financial_wealth_measure,
                housing_wealth_measure,
            )
            temp_chunk = filter_positive_values(chunk, [derived.TOTAL_WEALTH])
            log_total = np.log(temp_chunk[derived.TOTAL_WEALTH].astype(float))
            # Match the histogram range so stats reflect what is plotted.
            in_range = (log_total >= wealth_bin_edges[0]) & (
                log_total <= wealth_bin_edges[-1]
            )
            temp_chunk = temp_chunk[in_range]
            log_total = log_total[in_range]
            frequency = np.histogram(
                log_total.values,
                bins=wealth_bin_edges,
                density=True,
                weights=temp_chunk[constants.WAS_WEIGHT].values,
            )[0]
            # Keep summary stats aligned with the log-binned histogram.
            mean, variance, skew = log_binned_mean_variance_skew(
                wealth_bin_edges,
                frequency,
                skew_in_log_space=True,
            )
            label = (
                f"Total Wealth ({financial_wealth_measure} + {housing_wealth_measure})"
            )
            output_filename = (
                f"{financial_wealth_measure}-{housing_wealth_measure}-Weighted.csv"
            )
            write_1d_distribution(
                output_filename,
                label,
                wealth_bin_edges,
                frequency,
                log_label=True,
            )
            output_files.append(output_filename)
            output_stats[output_filename] = {
                "mean": mean,
                "variance": variance,
                "skew": skew,
            }

    end_timer(timer_start)
    return {
        "dataset": config.WAS_DATASET,
        "output_files": output_files,
        "output_stats": output_stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate total wealth distributions for WAS."
    )
    parser.add_argument(
        "--dataset",
        choices=[was_config.WAVE_3_DATA, was_config.ROUND_8_DATA],
        default=was_config.WAS_DATASET,
        help="Select the WAS dataset (W3 or R8).",
    )
    args = parser.parse_args()
    run_total_wealth_distribution(args.dataset)


if __name__ == "__main__":
    main()
