# -*- coding: utf-8 -*-
"""
Class to study households' financial wealth distribution, for validation purposes, based on Wealth and Assets Survey
data.

@author: Adrian Carro
"""

from __future__ import division
import os
import sys

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from was.CSVWrite import write_1d_distribution
from was.DerivedColumns import (
    LIQ_FINANCIAL_WEALTH,
    derive_liquid_financial_wealth_column,
)
from was.RowFilters import filter_positive_values
from was.IO import read_results, read_was_data
from was.Constants import (
    WAS_WEIGHT,
    WAS_GROSS_FINANCIAL_WEALTH,
    WAS_NET_FINANCIAL_WEALTH,
    WAS_NATIONAL_SAVINGS_VALUE,
    WAS_CHILD_TRUST_FUND_VALUE,
    WAS_CHILD_OTHER_SAVINGS_VALUE,
    WAS_SAVINGS_ACCOUNTS_VALUE,
    WAS_CASH_ISA_VALUE,
    WAS_CURRENT_ACCOUNT_CREDIT_VALUE,
)


# Set control variables and addresses. Available variables to print and plot are:
# WAS_GROSS_FINANCIAL_WEALTH, WAS_NET_FINANCIAL_WEALTH, LIQ_FINANCIAL_WEALTH
printResults = False
plotResults = True
start_time = 1000
end_time = 2000
min_log_bin_edge = 0.0
max_log_bin_edge = 20.0
variableToPlot = LIQ_FINANCIAL_WEALTH
rootData = r""  # ADD HERE PATH TO WAS DATA FOLDER
rootResults = r""  # ADD HERE PATH TO RESULTS FOLDER

# Read Wealth and Assets Survey data for households
use_column_constants = [
    WAS_WEIGHT,
    WAS_GROSS_FINANCIAL_WEALTH,
    WAS_NET_FINANCIAL_WEALTH,
    WAS_NATIONAL_SAVINGS_VALUE,
    WAS_CHILD_TRUST_FUND_VALUE,
    WAS_CHILD_OTHER_SAVINGS_VALUE,
    WAS_SAVINGS_ACCOUNTS_VALUE,
    WAS_CASH_ISA_VALUE,
    WAS_CURRENT_ACCOUNT_CREDIT_VALUE,
]
chunk = read_was_data(rootData, use_column_constants)

# List of household variables currently used
# HFINWNTW3_sum               Household Net financial Wealth (financial assets minus financial liabilities)
# HFINWW3_sum                 Gross Financial Wealth (financial assets only)

# Derive liquid financial wealth column for distribution.
derive_liquid_financial_wealth_column(chunk)
# Filter down to keep only financial wealth and total annual gross employee income
chunk = chunk[
    [
        WAS_GROSS_FINANCIAL_WEALTH,
        WAS_NET_FINANCIAL_WEALTH,
        LIQ_FINANCIAL_WEALTH,
        WAS_WEIGHT,
    ]
]
# Keep positive wealth values for log-scale histogram.
chunk = filter_positive_values(
    chunk,
    [WAS_GROSS_FINANCIAL_WEALTH, WAS_NET_FINANCIAL_WEALTH, LIQ_FINANCIAL_WEALTH],
)

# Define bin edges and widths
number_of_bins = int(max_log_bin_edge - min_log_bin_edge) * 4 + 1
bin_edges = np.logspace(min_log_bin_edge, max_log_bin_edge, number_of_bins, base=np.e)
bin_widths = [b - a for a, b in zip(bin_edges[:-1], bin_edges[1:])]

# If printing data to files is required, histogram data and print results
if printResults:
    for variable in [
        WAS_GROSS_FINANCIAL_WEALTH,
        WAS_NET_FINANCIAL_WEALTH,
        LIQ_FINANCIAL_WEALTH,
    ]:
        hist = np.histogram(
            chunk[variable].values,
            bins=bin_edges,
            density=True,
            weights=chunk[WAS_WEIGHT].values,
        )[0]
        # Write financial wealth distribution for validation.
        write_1d_distribution(
            "{}-Weighted.csv".format(variable),
            variable,
            bin_edges,
            hist,
            log_label=True,
        )

# If plotting data and results is required, read model results, histogram data and results and plot them
if plotResults:
    # Read model results
    results = read_results(
        os.path.join(rootResults, "test", "BankBalance-run1.csv"),
        start_time,
        end_time,
    )
    # Histogram model results
    model_hist = np.histogram(
        [x for x in results if x > 0.0], bins=bin_edges, density=False
    )[0]
    model_hist = model_hist / sum(model_hist)
    # Histogram data from WAS
    # Keep positive values for log-scale histogram.
    positive_chunk = filter_positive_values(chunk, [variableToPlot])
    WAS_hist = np.histogram(
        positive_chunk[variableToPlot].values,
        bins=bin_edges,
        density=False,
        weights=positive_chunk[WAS_WEIGHT].values,
    )[0]
    WAS_hist = WAS_hist / sum(WAS_hist)
    # Plot both model results and data from WAS
    plt.bar(
        bin_edges[:-1],
        height=model_hist,
        width=bin_widths,
        align="edge",
        label="Model results",
        alpha=0.5,
        color="b",
    )
    plt.bar(
        bin_edges[:-1],
        height=WAS_hist,
        width=bin_widths,
        align="edge",
        label="WAS data",
        alpha=0.5,
        color="r",
    )
    # Final plot details
    plt.gca().set_xscale("log")
    plt.xlabel("Liquid Financial Wealth (Bank Balance)")
    plt.ylabel("Frequency (fraction of cases)")
    plt.legend()
    plt.title("Distribution of {}".format(variableToPlot))
    plt.show()
