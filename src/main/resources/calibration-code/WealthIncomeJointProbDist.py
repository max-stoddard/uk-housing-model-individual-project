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
from WealthAssetsSurveyConstants import (
    WAS_COLUMN_MAP,
    WAS_DATA_FILENAME,
    WAS_DATA_SEPARATOR,
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

WAS_GROSS_NON_RENT_INCOME = "GrossNonRentIncome"
WAS_NET_NON_RENT_INCOME = "NetNonRentIncome"
WAS_LIQ_FINANCIAL_WEALTH = "LiqFinancialWealth"


def write_joint_distribution(
    file_name,
    income_label,
    wealth_label,
    frequency,
    income_bins,
    wealth_bins,
    zero_ok=False,
):
    header = (
        "# Log {} (lower edge), Log {} (upper edge), Log {} (lower edge), "
        "Log {} (upper edge), Probability\n"
    ).format(income_label, income_label, wealth_label, wealth_label)
    with open(file_name, "w") as f:
        f.write(header)
        for line, incomeLowerEdge, incomeUpperEdge in zip(
            frequency, income_bins[:-1], income_bins[1:]
        ):
            line_sum = sum(line)
            if line_sum == 0:
                for wealthLowerEdge, wealthUpperEdge in zip(
                    wealth_bins[:-1], wealth_bins[1:]
                ):
                    f.write(
                        "{}, {}, {}, {}, {}\n".format(
                            incomeLowerEdge,
                            incomeUpperEdge,
                            wealthLowerEdge,
                            wealthUpperEdge,
                            0.0,
                        )
                    )
            else:
                for element, wealthLowerEdge, wealthUpperEdge in zip(
                    line, wealth_bins[:-1], wealth_bins[1:]
                ):
                    f.write(
                        "{}, {}, {}, {}, {}\n".format(
                            incomeLowerEdge,
                            incomeUpperEdge,
                            wealthLowerEdge,
                            wealthUpperEdge,
                            element / line_sum,
                        )
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
use_columns = [WAS_COLUMN_MAP[column] for column in use_column_constants]
chunk = pd.read_csv(
    os.path.join(root, WAS_DATA_FILENAME),
    usecols=use_columns,
    sep=WAS_DATA_SEPARATOR,
)

# List of household variables currently used
# HFINWNTW3_sum               Household Net financial Wealth (financial assets minus financial liabilities)
# HFINWW3_sum                 Gross Financial Wealth (financial assets only )
# DVTotGIRw3                  Household Gross Annual (regular) income
# DVTotNIRw3                  Household Net Annual (regular) income
# DVGrsRentAmtAnnualw3_aggr   Household Gross annual income from rent
# DVNetRentAmtAnnualw3_aggr   Household Net annual income from rent

# Rename columns to their constant names
chunk.rename(
    columns={WAS_COLUMN_MAP[column]: column for column in use_column_constants},
    inplace=True,
)
# Add column with total gross income, except rental income (gross)
chunk[WAS_GROSS_NON_RENT_INCOME] = (
    chunk[WAS_GROSS_ANNUAL_INCOME] - chunk[WAS_GROSS_ANNUAL_RENTAL_INCOME]
)
# Add column with total net income, except rental income (net)
chunk[WAS_NET_NON_RENT_INCOME] = (
    chunk[WAS_NET_ANNUAL_INCOME] - chunk[WAS_NET_ANNUAL_RENTAL_INCOME]
)
# Rename the different measures of financial wealth
chunk[WAS_LIQ_FINANCIAL_WEALTH] = (
    chunk[WAS_NATIONAL_SAVINGS_VALUE].astype(float)
    + chunk[WAS_CHILD_TRUST_FUND_VALUE].astype(float)
    + chunk[WAS_CHILD_OTHER_SAVINGS_VALUE].astype(float)
    + chunk[WAS_SAVINGS_ACCOUNTS_VALUE].astype(float)
    + chunk[WAS_CASH_ISA_VALUE].astype(float)
    + chunk[WAS_CURRENT_ACCOUNT_CREDIT_VALUE].astype(float)
)
# Filter down to keep only financial wealth and total annual gross employee income
chunk = chunk[
    [
        WAS_GROSS_NON_RENT_INCOME,
        WAS_NET_NON_RENT_INCOME,
        WAS_GROSS_FINANCIAL_WEALTH,
        WAS_NET_FINANCIAL_WEALTH,
        WAS_LIQ_FINANCIAL_WEALTH,
        WAS_WEIGHT,
    ]
]
# Filter out the 1% with highest GrossNonRentIncome and the 1% with lowest NetNonRentIncome
one_per_cent = int(round(len(chunk.index) / 100))
chunk_ord_by_gross = chunk.sort_values(WAS_GROSS_NON_RENT_INCOME)
chunk_ord_by_net = chunk.sort_values(WAS_NET_NON_RENT_INCOME)
max_gross_income = chunk_ord_by_gross.iloc[-one_per_cent][WAS_GROSS_NON_RENT_INCOME]
min_net_income = chunk_ord_by_net.iloc[one_per_cent][WAS_NET_NON_RENT_INCOME]
chunk = chunk[chunk[WAS_GROSS_NON_RENT_INCOME] <= max_gross_income]
chunk = chunk[chunk[WAS_NET_NON_RENT_INCOME] >= min_net_income]
# For logarithmic binning, drop any non-positive income values
chunk = chunk[
    (chunk[WAS_GROSS_NON_RENT_INCOME] > 0.0) & (chunk[WAS_NET_NON_RENT_INCOME] > 0.0)
]
max_gross_income = chunk[WAS_GROSS_NON_RENT_INCOME].max()
min_net_income = chunk[WAS_NET_NON_RENT_INCOME].min()
# For the sake of plotting in logarithmic scales, filter out any zero and negative values from all wealth columns
chunk = chunk[
    (chunk[WAS_GROSS_FINANCIAL_WEALTH] > 0.0)
    & (chunk[WAS_NET_FINANCIAL_WEALTH] > 0.0)
    & (chunk[WAS_LIQ_FINANCIAL_WEALTH] > 0.0)
]
if chunk.empty:
    raise ValueError("No rows left after income and wealth filters.")


# Create a 2D histogram of the data with logarithmic income bins (no normalisation here as we want column normalisation,
# to be introduced when plotting or printing) and logarithmic wealth bins
income_bin_edges = np.linspace(np.log(min_net_income), np.log(max_gross_income), 26)
min_wealth = min(
    min(chunk[WAS_GROSS_FINANCIAL_WEALTH]),
    min(chunk[WAS_NET_FINANCIAL_WEALTH]),
    min(chunk[WAS_LIQ_FINANCIAL_WEALTH]),
)
max_wealth = max(
    max(chunk[WAS_GROSS_FINANCIAL_WEALTH]),
    max(chunk[WAS_NET_FINANCIAL_WEALTH]),
    max(chunk[WAS_LIQ_FINANCIAL_WEALTH]),
)
wealth_bin_edges = np.linspace(np.log(min_wealth), np.log(max_wealth), 21)
weights = chunk[WAS_WEIGHT].values
income_columns = {
    "gross": WAS_GROSS_NON_RENT_INCOME,
    "net": WAS_NET_NON_RENT_INCOME,
}
wealth_columns = {
    "gross": WAS_GROSS_FINANCIAL_WEALTH,
    "net": WAS_NET_FINANCIAL_WEALTH,
    "liq": WAS_LIQ_FINANCIAL_WEALTH,
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
write_joint_distribution(
    "GrossIncomeGrossWealthJointDist.csv",
    "Gross Income",
    "Gross Wealth",
    frequencies[("gross", "gross")],
    xBins,
    yBins,
)
write_joint_distribution(
    "GrossIncomeNetWealthJointDist.csv",
    "Gross Income",
    "Net Wealth",
    frequencies[("gross", "net")],
    xBins,
    yBins,
)
write_joint_distribution(
    "GrossIncomeLiqWealthJointDist.csv",
    "Gross Income",
    "Liq Wealth",
    frequencies[("gross", "liq")],
    xBins,
    yBins,
)
write_joint_distribution(
    "NetIncomeGrossWealthJointDist.csv",
    "Net Income",
    "Gross Wealth",
    frequencies[("net", "gross")],
    xBins,
    yBins,
    zero_ok=True,
)
write_joint_distribution(
    "NetIncomeNetWealthJointDist.csv",
    "Net Income",
    "Net Wealth",
    frequencies[("net", "net")],
    xBins,
    yBins,
    zero_ok=True,
)
write_joint_distribution(
    "NetIncomeLiqWealthJointDist.csv",
    "Net Income",
    "Liq Wealth",
    frequencies[("net", "liq")],
    xBins,
    yBins,
    zero_ok=True,
)
