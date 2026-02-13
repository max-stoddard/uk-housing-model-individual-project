# -*- coding: utf-8 -*-
"""
Class to study households' financial wealth distribution, for validation purposes, based on Wealth and Assets Survey
data.

@author: Adrian Carro, Max Stoddard
"""

from __future__ import division
import os

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from scripts.python.helpers.was.csv_write import write_1d_distribution
from scripts.python.helpers.was.derived_columns import (
    LIQ_FINANCIAL_WEALTH,
    derive_liquid_financial_wealth_column,
)
from scripts.python.helpers.was.config import (
    WAS_DATA_ROOT,
    WAS_RESULTS_ROOT,
    WAS_RESULTS_RUN_SUBDIR,
    WAS_VALIDATION_PLOTS,
)
from scripts.python.helpers.was.plotting import (
    format_currency_axis,
    plot_hist_overlay,
    print_hist_percent_diff,
)
from scripts.python.helpers.was.row_filters import filter_positive_values
from scripts.python.helpers.was.io import read_results, read_was_data
from scripts.python.helpers.was.constants import (
    WAS_WEIGHT,
    WAS_GROSS_FINANCIAL_WEALTH,
    WAS_NET_FINANCIAL_WEALTH,
    WAS_NATIONAL_SAVINGS_VALUE,
    WAS_CHILD_TRUST_FUND_VALUE,
    WAS_CHILD_OTHER_SAVINGS_VALUE,
    WAS_SAVINGS_ACCOUNTS_VALUE,
    WAS_CASH_ISA_VALUE,
    WAS_CURRENT_ACCOUNT_CREDIT_VALUE,
    WAS_FORMAL_FINANCIAL_ASSETS,
)
from scripts.python.helpers.was.timing import start_timer, end_timer


# Set control variables and addresses. Available variables to print and plot are:
# WAS_GROSS_FINANCIAL_WEALTH, WAS_NET_FINANCIAL_WEALTH, LIQ_FINANCIAL_WEALTH
printResults = False
plotResults = WAS_VALIDATION_PLOTS
printBucketDiffs = False
start_time = 1000
end_time = 2000
min_log_bin_edge = 0.0
max_log_bin_edge = 20.0
variableToPlot = LIQ_FINANCIAL_WEALTH
rootData = WAS_DATA_ROOT
rootResults = WAS_RESULTS_ROOT
results_run_dir = os.path.join(rootResults, WAS_RESULTS_RUN_SUBDIR)
timer_start = start_timer(os.path.basename(__file__), "validation")

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
    WAS_FORMAL_FINANCIAL_ASSETS,
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
# Define bin edges and widths
number_of_bins = int(max_log_bin_edge - min_log_bin_edge) * 4 + 1
bin_edges = np.logspace(min_log_bin_edge, max_log_bin_edge, number_of_bins, base=np.e)

# If printing data to files is required, histogram data and print results
if printResults:
    for variable in [
        WAS_GROSS_FINANCIAL_WEALTH,
        WAS_NET_FINANCIAL_WEALTH,
        LIQ_FINANCIAL_WEALTH,
    ]:
        # Keep positive values for log-scale histogram per measure.
        positive_chunk = filter_positive_values(chunk, [variable])
        hist = np.histogram(
            positive_chunk[variable].values,
            bins=bin_edges,
            density=True,
            weights=positive_chunk[WAS_WEIGHT].values,
        )[0]
        # Write financial wealth distribution for validation.
        write_1d_distribution(
            "{}-Weighted.csv".format(variable),
            variable,
            bin_edges,
            hist,
            log_label=True,
        )

# Build model/data histograms and print percentage-point differences regardless of plotting mode.
# Read model results
results = read_results(
    os.path.join(results_run_dir, "BankBalance-run1.csv"),
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
# Print percentage-point differences vs WAS for diagnostics.
print_hist_percent_diff(
    bin_edges,
    model_hist,
    WAS_hist,
    label="Financial wealth",
    print_buckets=printBucketDiffs,
)

# If plotting data and results is required, plot model and validation distributions.
if plotResults:
    # Plot model vs WAS financial wealth distributions for validation.
    axes = plot_hist_overlay(
        bin_edges,
        model_hist,
        WAS_hist,
        xlabel="Liquid Financial Wealth (Bank Balance)",
        ylabel="Frequency (fraction of cases)",
        title="Distribution of {}".format(variableToPlot),
        log_x=True,
        data_label="Validation data (WAS)",
    )
    format_currency_axis(axes, axis="x")
    plt.show()

end_timer(timer_start)
