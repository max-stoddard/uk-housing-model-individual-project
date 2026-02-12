# -*- coding: utf-8 -*-
"""
Class to study the probability of a household becoming a buy-to-let investor depending
on its income percentile, based on Wealth and Assets Survey data. This is the code used
to create the file "BTLProbabilityPerIncomePercentileBin.csv".

@author: Adrian Carro, Max Stoddard
"""

from __future__ import annotations, division

import argparse
import os

import pandas as pd
from scipy import stats

from scripts.python.helpers.was.csv_write import write_rows
from scripts.python.helpers.was.row_filters import filter_percentile_outliers
from scripts.python.helpers.was.timing import start_timer, end_timer
from scripts.python.helpers.was import config as was_config
from scripts.python.helpers.was import derived_columns as was_derived
from scripts.python.helpers.was.dataset import reload_was_modules
from scripts.python.helpers.common.paths import resolve_output_path

GROSS_NON_RENT_INCOME_PERCENTILE = "GrossNonRentIncomePercentile"

# List of household variables currently used
# DVTotGIRw3                  Household Gross Annual (regular) income
# DVTotNIRw3                  Household Net Annual (regular) income
# DVGrsRentAmtAnnualw3_aggr   Household Gross Annual income from rent
# DVNetRentAmtAnnualw3_aggr   Household Net Annual income from rent


def run_btl_probability_per_income_percentile_bin(
    dataset: str | None = None,
    output_dir: str | None = None,
) -> dict[str, object]:
    """Generate BTL probabilities per income percentile for a WAS dataset."""
    target_dataset = dataset or was_config.WAS_DATASET
    config, constants, io_module, derived = reload_was_modules(
        target_dataset,
        extra_modules=(was_derived,),
    )
    timer_start = start_timer(os.path.basename(__file__), "calibration")

    use_columns = [
        constants.WAS_WEIGHT,
        constants.WAS_GROSS_ANNUAL_INCOME,
        constants.WAS_NET_ANNUAL_INCOME,
        constants.WAS_GROSS_ANNUAL_RENTAL_INCOME,
        constants.WAS_NET_ANNUAL_RENTAL_INCOME,
    ]
    chunk = io_module.read_was_data(config.WAS_DATA_ROOT, use_columns)
    pd.set_option("display.max_columns", None)

    derived.derive_non_rent_income_columns(chunk)

    chunk = filter_percentile_outliers(
        chunk,
        lower_bound_column=derived.GROSS_NON_RENT_INCOME,
        upper_bound_column=derived.GROSS_NON_RENT_INCOME,
    )

    income_values = chunk[derived.GROSS_NON_RENT_INCOME].values
    chunk[GROSS_NON_RENT_INCOME_PERCENTILE] = [
        stats.percentileofscore(income_values, x, "weak") for x in income_values
    ]

    rows = []
    for percentile in range(100):
        n_total = len(
            chunk[
                (percentile < chunk[GROSS_NON_RENT_INCOME_PERCENTILE])
                & (chunk[GROSS_NON_RENT_INCOME_PERCENTILE] <= percentile + 1.0)
            ]
        )
        n_btl = len(
            chunk[
                (percentile < chunk[GROSS_NON_RENT_INCOME_PERCENTILE])
                & (chunk[GROSS_NON_RENT_INCOME_PERCENTILE] <= percentile + 1.0)
                & (chunk[constants.WAS_GROSS_ANNUAL_RENTAL_INCOME] > 0.0)
            ]
        )
        rows.append((percentile / 100, (percentile + 1) / 100, n_btl / n_total))

    output_filename = "BTLProbabilityPerIncomePercentileBin.csv"
    output_path = resolve_output_path(output_filename, output_dir)
    write_rows(
        output_path,
        "# Gross non-rental income percentile (lower edge), "
        "gross non-rental income percentile (upper edge), BTL probability\n",
        rows,
    )

    end_timer(timer_start)
    return {"dataset": config.WAS_DATASET, "output_file": output_path}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate BTL probabilities per income percentile."
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
    run_btl_probability_per_income_percentile_bin(
        args.dataset,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
