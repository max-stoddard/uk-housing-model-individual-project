# -*- coding: utf-8 -*-
"""
Class to study households' wealth distribution depending on income based on Wealth
and Assets Survey data. This is the code used to create file
"GrossIncomeLiqWealthJointDist.csv".

@author: Adrian Carro, Max Stoddard
"""

from __future__ import annotations, division

import argparse
import os
import sys

import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from was.CSVWrite import write_joint_distribution
from was.Distributions import log_histogram2d
from was.RowFilters import filter_percentile_outliers, filter_positive_values
from was.Timing import start_timer, end_timer
from was import Config as was_config
from was import DerivedColumns as was_derived
from was.Dataset import reload_was_modules
from was.Statistics import weighted_mean_variance_skew


def _load_income_wealth_chunk(
    dataset: str,
) -> tuple[object, object, object, object]:
    """Load and filter income/wealth data for the selected WAS dataset."""
    config, constants, io_module, derived = reload_was_modules(
        dataset,
        extra_modules=(was_derived,),
    )
    use_column_constants = [
        constants.WAS_WEIGHT,
        constants.WAS_GROSS_ANNUAL_INCOME,
        constants.WAS_NET_ANNUAL_INCOME,
        constants.WAS_GROSS_ANNUAL_RENTAL_INCOME,
        constants.WAS_NET_ANNUAL_RENTAL_INCOME,
        constants.WAS_GROSS_FINANCIAL_WEALTH,
        constants.WAS_NET_FINANCIAL_WEALTH,
        constants.WAS_NATIONAL_SAVINGS_VALUE,
        constants.WAS_CHILD_TRUST_FUND_VALUE,
        constants.WAS_CHILD_OTHER_SAVINGS_VALUE,
        constants.WAS_SAVINGS_ACCOUNTS_VALUE,
        constants.WAS_CASH_ISA_VALUE,
        constants.WAS_CURRENT_ACCOUNT_CREDIT_VALUE,
        constants.WAS_FORMAL_FINANCIAL_ASSETS,
    ]
    chunk = io_module.read_was_data(config.WAS_DATA_ROOT, use_column_constants)

    derived.derive_non_rent_income_columns(chunk)
    derived.derive_liquid_financial_wealth_column(chunk)
    chunk = chunk[
        [
            derived.GROSS_NON_RENT_INCOME,
            derived.NET_NON_RENT_INCOME,
            constants.WAS_GROSS_FINANCIAL_WEALTH,
            constants.WAS_NET_FINANCIAL_WEALTH,
            derived.LIQ_FINANCIAL_WEALTH,
            constants.WAS_WEIGHT,
        ]
    ]
    # Trim 1% tails so joint distributions are less dominated by extreme incomes.
    chunk = filter_percentile_outliers(
        chunk,
        lower_bound_column=derived.NET_NON_RENT_INCOME,
        upper_bound_column=derived.GROSS_NON_RENT_INCOME,
        percentile=0.01,
    )
    chunk = filter_positive_values(
        chunk,
        [derived.GROSS_NON_RENT_INCOME, derived.NET_NON_RENT_INCOME],
    )
    chunk = filter_positive_values(
        chunk,
        [
            constants.WAS_GROSS_FINANCIAL_WEALTH,
            constants.WAS_NET_FINANCIAL_WEALTH,
            derived.LIQ_FINANCIAL_WEALTH,
        ],
    )
    if chunk.empty:
        raise ValueError("No rows left after income and wealth filters.")

    return chunk, config, constants, derived


def compute_income_wealth_bounds(
    dataset: str | None = None,
) -> tuple[float, float, float, float]:
    """Return min/max bounds for income and wealth after filtering."""
    target_dataset = dataset or was_config.WAS_DATASET
    chunk, _, constants, derived = _load_income_wealth_chunk(target_dataset)
    min_net_income = float(chunk[derived.NET_NON_RENT_INCOME].min())
    max_gross_income = float(chunk[derived.GROSS_NON_RENT_INCOME].max())
    min_wealth = min(
        float(chunk[constants.WAS_GROSS_FINANCIAL_WEALTH].min()),
        float(chunk[constants.WAS_NET_FINANCIAL_WEALTH].min()),
        float(chunk[derived.LIQ_FINANCIAL_WEALTH].min()),
    )
    max_wealth = max(
        float(chunk[constants.WAS_GROSS_FINANCIAL_WEALTH].max()),
        float(chunk[constants.WAS_NET_FINANCIAL_WEALTH].max()),
        float(chunk[derived.LIQ_FINANCIAL_WEALTH].max()),
    )
    return min_net_income, max_gross_income, min_wealth, max_wealth


def run_wealth_income_joint_prob_dist(
    dataset: str | None = None,
    income_bin_edges: np.ndarray | None = None,
    wealth_bin_edges: np.ndarray | None = None,
) -> dict[str, object]:
    """Generate joint distributions of wealth by income for a WAS dataset."""
    target_dataset = dataset or was_config.WAS_DATASET
    timer_start = start_timer(os.path.basename(__file__), "calibration")

    chunk, config, constants, derived = _load_income_wealth_chunk(target_dataset)
    if income_bin_edges is None or wealth_bin_edges is None:
        min_net_income = float(chunk[derived.NET_NON_RENT_INCOME].min())
        max_gross_income = float(chunk[derived.GROSS_NON_RENT_INCOME].max())
        min_wealth = min(
            float(chunk[constants.WAS_GROSS_FINANCIAL_WEALTH].min()),
            float(chunk[constants.WAS_NET_FINANCIAL_WEALTH].min()),
            float(chunk[derived.LIQ_FINANCIAL_WEALTH].min()),
        )
        max_wealth = max(
            float(chunk[constants.WAS_GROSS_FINANCIAL_WEALTH].max()),
            float(chunk[constants.WAS_NET_FINANCIAL_WEALTH].max()),
            float(chunk[derived.LIQ_FINANCIAL_WEALTH].max()),
        )
        income_bin_edges = np.linspace(
            np.log(min_net_income),
            np.log(max_gross_income),
            26,
        )
        wealth_bin_edges = np.linspace(np.log(min_wealth), np.log(max_wealth), 21)

    weights = chunk[constants.WAS_WEIGHT].values
    income_columns = {
        "gross": derived.GROSS_NON_RENT_INCOME,
        "net": derived.NET_NON_RENT_INCOME,
    }
    wealth_columns = {
        "gross": constants.WAS_GROSS_FINANCIAL_WEALTH,
        "net": constants.WAS_NET_FINANCIAL_WEALTH,
        "liq": derived.LIQ_FINANCIAL_WEALTH,
    }

    frequencies = {}
    x_bins = None
    y_bins = None
    for income_key, income_column in income_columns.items():
        for wealth_key, wealth_column in wealth_columns.items():
            frequency, x_bins, y_bins = log_histogram2d(
                chunk[income_column],
                chunk[wealth_column],
                income_bin_edges,
                wealth_bin_edges,
                weights,
            )
            frequencies[(income_key, wealth_key)] = frequency

    output_files = {}
    output_files["gross_gross"] = "GrossIncomeGrossWealthJointDist.csv"
    write_joint_distribution(
        output_files["gross_gross"],
        "Gross Income",
        "Gross Wealth",
        frequencies[("gross", "gross")],
        x_bins,
        y_bins,
        x_is_log=True,
        y_is_log=True,
    )
    output_files["gross_net"] = "GrossIncomeNetWealthJointDist.csv"
    write_joint_distribution(
        output_files["gross_net"],
        "Gross Income",
        "Net Wealth",
        frequencies[("gross", "net")],
        x_bins,
        y_bins,
        x_is_log=True,
        y_is_log=True,
    )
    output_files["gross_liq"] = "GrossIncomeLiqWealthJointDist.csv"
    write_joint_distribution(
        output_files["gross_liq"],
        "Gross Income",
        "Liq Wealth",
        frequencies[("gross", "liq")],
        x_bins,
        y_bins,
        x_is_log=True,
        y_is_log=True,
    )
    output_files["net_gross"] = "NetIncomeGrossWealthJointDist.csv"
    write_joint_distribution(
        output_files["net_gross"],
        "Net Income",
        "Gross Wealth",
        frequencies[("net", "gross")],
        x_bins,
        y_bins,
        x_is_log=True,
        y_is_log=True,
        zero_ok=True,
    )
    output_files["net_net"] = "NetIncomeNetWealthJointDist.csv"
    write_joint_distribution(
        output_files["net_net"],
        "Net Income",
        "Net Wealth",
        frequencies[("net", "net")],
        x_bins,
        y_bins,
        x_is_log=True,
        y_is_log=True,
        zero_ok=True,
    )
    output_files["net_liq"] = "NetIncomeLiqWealthJointDist.csv"
    write_joint_distribution(
        output_files["net_liq"],
        "Net Income",
        "Liq Wealth",
        frequencies[("net", "liq")],
        x_bins,
        y_bins,
        x_is_log=True,
        y_is_log=True,
        zero_ok=True,
    )

    gross_income_stats = weighted_mean_variance_skew(
        chunk[derived.GROSS_NON_RENT_INCOME].astype(float),
        chunk[constants.WAS_WEIGHT].astype(float),
    )
    net_wealth_stats = weighted_mean_variance_skew(
        chunk[constants.WAS_NET_FINANCIAL_WEALTH].astype(float),
        chunk[constants.WAS_WEIGHT].astype(float),
    )

    end_timer(timer_start)
    return {
        "dataset": config.WAS_DATASET,
        "output_files": output_files,
        "income_bin_edges": income_bin_edges,
        "wealth_bin_edges": wealth_bin_edges,
        "stats": {
            "gross_income": {
                "mean": gross_income_stats[0],
                "variance": gross_income_stats[1],
                "skew": gross_income_stats[2],
            },
            "net_wealth": {
                "mean": net_wealth_stats[0],
                "variance": net_wealth_stats[1],
                "skew": net_wealth_stats[2],
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate joint income/wealth distributions for WAS."
    )
    parser.add_argument(
        "--dataset",
        choices=[was_config.WAVE_3_DATA, was_config.ROUND_8_DATA],
        default=was_config.WAS_DATASET,
        help="Select the WAS dataset (W3 or R8).",
    )
    args = parser.parse_args()
    run_wealth_income_joint_prob_dist(args.dataset)


if __name__ == "__main__":
    main()
