# -*- coding: utf-8 -*-
"""
Class to study households' income distribution, for validation purposes, based on Wealth and Assets Survey data.

@author: Adrian Carro, Max Stoddard
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
    GROSS_NON_RENT_INCOME,
    NET_NON_RENT_INCOME,
    derive_non_rent_income_columns,
)
from was.RowFilters import filter_percentile_outliers, filter_positive_values
from was.IO import read_results, read_was_data
from was.Constants import (
    WAS_WEIGHT,
    WAS_NET_ANNUAL_INCOME,
    WAS_GROSS_ANNUAL_INCOME,
    WAS_NET_ANNUAL_RENTAL_INCOME,
    WAS_GROSS_ANNUAL_RENTAL_INCOME,
)


# Set control variables and addresses. Note that available variables to print and plot are "GrossTotalIncome",
# "NetTotalIncome", "GrossRentalIncome", "NetRentalIncome", "GrossNonRentIncome" and "NetNonRentIncome"
printResults = False
plotResults = True
start_time = 1000
end_time = 2000
min_log_income_bin_edge = 4.0
max_log_income_bin_edge = 12.25
variableToPlot = GROSS_NON_RENT_INCOME
rootData = r""  # ADD HERE PATH TO WAS DATA FOLDER
rootResults = r""  # ADD HERE PATH TO RESULTS FOLDER

# Read Wealth and Assets Survey data for households
use_columns = [
    WAS_WEIGHT,
    WAS_GROSS_ANNUAL_INCOME,
    WAS_NET_ANNUAL_INCOME,
    WAS_GROSS_ANNUAL_RENTAL_INCOME,
    WAS_NET_ANNUAL_RENTAL_INCOME,
]
chunk = read_was_data(rootData, use_columns)

# List of household variables currently used
# DVTotGIRw3                  Household Gross Annual (regular) income
# DVTotNIRw3                  Household Net Annual (regular) income
# DVGrsRentAmtAnnualw3_aggr   Household Gross Annual income from rent
# DVNetRentAmtAnnualw3_aggr   Household Net Annual income from rent

# Derive non-rent income columns for filtering and plots.
derive_non_rent_income_columns(chunk)

# Filter down to keep only columns of interest
chunk = chunk[
    [
        WAS_GROSS_ANNUAL_INCOME,
        WAS_NET_ANNUAL_INCOME,
        WAS_GROSS_ANNUAL_RENTAL_INCOME,
        WAS_NET_ANNUAL_RENTAL_INCOME,
        GROSS_NON_RENT_INCOME,
        NET_NON_RENT_INCOME,
        WAS_WEIGHT,
    ]
]

# Remove extreme income outliers to stabilize distribution.
chunk = filter_percentile_outliers(
    chunk,
    lower_bound_column=WAS_NET_ANNUAL_INCOME,
    upper_bound_column=WAS_GROSS_ANNUAL_INCOME,
)

results_file = os.path.join(
    rootResults, "test", "MonthlyGrossEmploymentIncome-run1.csv"
)

# If printing data to files is required, histogram data and print results
if printResults:
    number_of_bins = int(max_log_income_bin_edge - min_log_income_bin_edge) * 4 + 2
    income_bin_edges = np.linspace(
        min_log_income_bin_edge, max_log_income_bin_edge, number_of_bins
    )
    income_bin_widths = [
        b - a for a, b in zip(income_bin_edges[:-1], income_bin_edges[1:])
    ]
    for name in [
        WAS_GROSS_ANNUAL_INCOME,
        WAS_NET_ANNUAL_INCOME,
        WAS_GROSS_ANNUAL_RENTAL_INCOME,
        WAS_NET_ANNUAL_RENTAL_INCOME,
        GROSS_NON_RENT_INCOME,
        NET_NON_RENT_INCOME,
    ]:
        # Keep positive values for log-scale histogram.
        positive_chunk = filter_positive_values(chunk, [name])
        frequency = np.histogram(
            np.log(positive_chunk[name].values),
            bins=income_bin_edges,
            density=True,
            weights=positive_chunk[WAS_WEIGHT].values,
        )[0]
        # Write income distribution for validation output.
        write_1d_distribution(
            name + "-Weighted.csv",
            name,
            income_bin_edges,
            frequency,
            log_label=False,
        )

# If plotting data and results is required, read model results, histogram data and results and plot them
if plotResults:
    # Define bin edges and widths
    number_of_bins = int(max_log_income_bin_edge - min_log_income_bin_edge) * 4 + 2
    income_bin_edges = np.logspace(
        min_log_income_bin_edge, max_log_income_bin_edge, number_of_bins, base=np.e
    )
    income_bin_widths = [
        b - a for a, b in zip(income_bin_edges[:-1], income_bin_edges[1:])
    ]
    # Read model results
    results = read_results(results_file, start_time, end_time)
    # Histogram model results
    model_hist = np.histogram(
        [12.0 * x for x in results if x > 0.0], bins=income_bin_edges, density=False
    )[0]
    model_hist = model_hist / sum(model_hist)
    # Histogram data from WAS
    # Keep positive values for log-scale histogram.
    positive_chunk = filter_positive_values(chunk, [variableToPlot])
    WAS_hist = np.histogram(
        positive_chunk[variableToPlot].values,
        bins=income_bin_edges,
        density=False,
        weights=positive_chunk[WAS_WEIGHT].values,
    )[0]
    WAS_hist = WAS_hist / sum(WAS_hist)
    # Plot both model results and data from WAS
    plt.bar(
        income_bin_edges[:-1],
        height=model_hist,
        width=income_bin_widths,
        align="edge",
        label="Model results",
        alpha=0.5,
        color="b",
    )
    plt.bar(
        income_bin_edges[:-1],
        height=WAS_hist,
        width=income_bin_widths,
        align="edge",
        label="WAS data",
        alpha=0.5,
        color="r",
    )
    # Final plot details
    plt.gca().set_xscale("log")
    plt.xlabel("Income")
    plt.ylabel("Frequency (fraction of cases)")
    plt.legend()
    plt.title("Distribution of {}".format(variableToPlot))
    plt.show()
