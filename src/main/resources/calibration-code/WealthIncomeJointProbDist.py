# -*- coding: utf-8 -*-
"""
Class to study households' wealth distribution depending on income based on Wealth and Assets Survey data. This is the
code used to create file "GrossIncomeLiqWealthJointDist.csv".

@author: Adrian Carro, Max Stoddard
"""

import os
import sys

import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from was.DerivedColumns import (
    GROSS_NON_RENT_INCOME,
    NET_NON_RENT_INCOME,
    LIQ_FINANCIAL_WEALTH,
    derive_non_rent_income_columns,
    derive_liquid_financial_wealth_column,
)
from was.CSVWrite import write_joint_distribution
from was.RowFilters import filter_percentile_outliers, filter_positive_values
from was.IO import read_was_data
from was.Constants import (
    WAS_WEIGHT,
    WAS_NET_ANNUAL_INCOME,
    WAS_GROSS_ANNUAL_INCOME,
    WAS_NET_ANNUAL_RENTAL_INCOME,
    WAS_GROSS_ANNUAL_RENTAL_INCOME,
    WAS_GROSS_FINANCIAL_WEALTH,
    WAS_NET_FINANCIAL_WEALTH,
    WAS_NATIONAL_SAVINGS_VALUE,
    WAS_CHILD_TRUST_FUND_VALUE,
    WAS_CHILD_OTHER_SAVINGS_VALUE,
    WAS_SAVINGS_ACCOUNTS_VALUE,
    WAS_CASH_ISA_VALUE,
    WAS_CURRENT_ACCOUNT_CREDIT_VALUE,
)


def log_histogram2d(
    chunk,
    income_column,
    wealth_column,
    income_bins,
    wealth_bins,
    weights,
):
    return np.histogram2d(
        np.log(chunk[income_column].values),
        np.log(chunk[wealth_column].values),
        bins=[income_bins, wealth_bins],
        weights=weights,
    )


# Read Wealth and Assets Survey data for households
root = r""  # ADD HERE PATH TO WAS DATA FOLDER
use_column_constants = [
    WAS_WEIGHT,
    WAS_GROSS_ANNUAL_INCOME,
    WAS_NET_ANNUAL_INCOME,
    WAS_GROSS_ANNUAL_RENTAL_INCOME,
    WAS_NET_ANNUAL_RENTAL_INCOME,
    WAS_GROSS_FINANCIAL_WEALTH,
    WAS_NET_FINANCIAL_WEALTH,
    WAS_NATIONAL_SAVINGS_VALUE,
    WAS_CHILD_TRUST_FUND_VALUE,
    WAS_CHILD_OTHER_SAVINGS_VALUE,
    WAS_SAVINGS_ACCOUNTS_VALUE,
    WAS_CASH_ISA_VALUE,
    WAS_CURRENT_ACCOUNT_CREDIT_VALUE,
]
chunk = read_was_data(root, use_column_constants)

# List of household variables currently used
# HFINWNTW3_sum               Household Net financial Wealth (financial assets minus financial liabilities)
# HFINWW3_sum                 Gross Financial Wealth (financial assets only )
# DVTotGIRw3                  Household Gross Annual (regular) income
# DVTotNIRw3                  Household Net Annual (regular) income
# DVGrsRentAmtAnnualw3_aggr   Household Gross annual income from rent
# DVNetRentAmtAnnualw3_aggr   Household Net annual income from rent

# Derive non-rent income columns for income bins.
derive_non_rent_income_columns(chunk)
# Derive liquid financial wealth for wealth bins.
derive_liquid_financial_wealth_column(chunk)
# Filter down to keep only financial wealth and total annual gross employee income
chunk = chunk[
    [
        GROSS_NON_RENT_INCOME,
        NET_NON_RENT_INCOME,
        WAS_GROSS_FINANCIAL_WEALTH,
        WAS_NET_FINANCIAL_WEALTH,
        LIQ_FINANCIAL_WEALTH,
        WAS_WEIGHT,
    ]
]
# Remove extreme income outliers to stabilize joint distribution.
chunk = filter_percentile_outliers(
    chunk,
    lower_bound_column=NET_NON_RENT_INCOME,
    upper_bound_column=GROSS_NON_RENT_INCOME,
)
# Drop non-positive incomes to enable log binning.
chunk = filter_positive_values(chunk, [GROSS_NON_RENT_INCOME, NET_NON_RENT_INCOME])
max_gross_income = chunk[GROSS_NON_RENT_INCOME].max()
min_net_income = chunk[NET_NON_RENT_INCOME].min()
# Filter non-positive wealth values for log-scale bins.
chunk = filter_positive_values(
    chunk,
    [WAS_GROSS_FINANCIAL_WEALTH, WAS_NET_FINANCIAL_WEALTH, LIQ_FINANCIAL_WEALTH],
)
if chunk.empty:
    raise ValueError("No rows left after income and wealth filters.")


# Create a 2D histogram of the data with logarithmic income bins (no normalisation here as we want column normalisation,
# to be introduced when plotting or printing) and logarithmic wealth bins
income_bin_edges = np.linspace(np.log(min_net_income), np.log(max_gross_income), 26)
min_wealth = min(
    min(chunk[WAS_GROSS_FINANCIAL_WEALTH]),
    min(chunk[WAS_NET_FINANCIAL_WEALTH]),
    min(chunk[LIQ_FINANCIAL_WEALTH]),
)
max_wealth = max(
    max(chunk[WAS_GROSS_FINANCIAL_WEALTH]),
    max(chunk[WAS_NET_FINANCIAL_WEALTH]),
    max(chunk[LIQ_FINANCIAL_WEALTH]),
)
wealth_bin_edges = np.linspace(np.log(min_wealth), np.log(max_wealth), 21)
weights = chunk[WAS_WEIGHT].values
income_columns = {
    "gross": GROSS_NON_RENT_INCOME,
    "net": NET_NON_RENT_INCOME,
}
wealth_columns = {
    "gross": WAS_GROSS_FINANCIAL_WEALTH,
    "net": WAS_NET_FINANCIAL_WEALTH,
    "liq": LIQ_FINANCIAL_WEALTH,
}
frequencies = {}
xBins = None
yBins = None
for income_key, income_column in income_columns.items():
    for wealth_key, wealth_column in wealth_columns.items():
        frequency, xBins, yBins = log_histogram2d(
            chunk,
            income_column,
            wealth_column,
            income_bin_edges,
            wealth_bin_edges,
            weights,
        )
        frequencies[(income_key, wealth_key)] = frequency

# Print joint distributions to files
# Write joint income/wealth distributions for calibration.
write_joint_distribution(
    "GrossIncomeGrossWealthJointDist.csv",
    "Gross Income",
    "Gross Wealth",
    frequencies[("gross", "gross")],
    xBins,
    yBins,
    x_is_log=True,
    y_is_log=True,
)
write_joint_distribution(
    "GrossIncomeNetWealthJointDist.csv",
    "Gross Income",
    "Net Wealth",
    frequencies[("gross", "net")],
    xBins,
    yBins,
    x_is_log=True,
    y_is_log=True,
)
write_joint_distribution(
    "GrossIncomeLiqWealthJointDist.csv",
    "Gross Income",
    "Liq Wealth",
    frequencies[("gross", "liq")],
    xBins,
    yBins,
    x_is_log=True,
    y_is_log=True,
)
write_joint_distribution(
    "NetIncomeGrossWealthJointDist.csv",
    "Net Income",
    "Gross Wealth",
    frequencies[("net", "gross")],
    xBins,
    yBins,
    x_is_log=True,
    y_is_log=True,
    zero_ok=True,
)
write_joint_distribution(
    "NetIncomeNetWealthJointDist.csv",
    "Net Income",
    "Net Wealth",
    frequencies[("net", "net")],
    xBins,
    yBins,
    x_is_log=True,
    y_is_log=True,
    zero_ok=True,
)
write_joint_distribution(
    "NetIncomeLiqWealthJointDist.csv",
    "Net Income",
    "Liq Wealth",
    frequencies[("net", "liq")],
    xBins,
    yBins,
    x_is_log=True,
    y_is_log=True,
    zero_ok=True,
)
