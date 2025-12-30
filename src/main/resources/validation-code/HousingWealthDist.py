# -*- coding: utf-8 -*-
"""
Class to study households' housing wealth distribution, for validation purposes, based on Wealth and Assets Survey
data.

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
    GROSS_HOUSING_WEALTH,
    derive_gross_housing_wealth_column,
)
from was.Config import WAS_DATA_ROOT, WAS_RESULTS_ROOT
from was.Plotting import plot_hist_overlay
from was.RowFilters import filter_positive_values
from was.IO import read_results, read_was_data
from was.Constants import (
    WAS_WEIGHT,
    WAS_TOTAL_PROPERTY_WEALTH,
    WAS_PROPERTY_VALUE_SUM,
    WAS_MAIN_RESIDENCE_VALUE,
    WAS_OTHER_HOUSES_TOTAL_VALUE,
    WAS_BTL_HOUSES_TOTAL_VALUE,
)


# Set control variables and addresses. Available variables to print and plot are:
# WAS_TOTAL_PROPERTY_WEALTH, WAS_PROPERTY_VALUE_SUM, WAS_GROSS_HOUSING_WEALTH
printResults = False
plotResults = True
start_time = 1000
end_time = 2000
min_log_bin_edge = 6.0
max_log_bin_edge = 16.0
# variableToPlot = WAS_GROSS_HOUSING_WEALTH
variableToPlot = WAS_TOTAL_PROPERTY_WEALTH
rootData = WAS_DATA_ROOT
rootResults = WAS_RESULTS_ROOT

# Read Wealth and Assets Survey data for households
use_column_constants = [
    WAS_WEIGHT,
    WAS_TOTAL_PROPERTY_WEALTH,
    WAS_PROPERTY_VALUE_SUM,
    WAS_MAIN_RESIDENCE_VALUE,
    WAS_OTHER_HOUSES_TOTAL_VALUE,
    WAS_BTL_HOUSES_TOTAL_VALUE,
]
chunk = read_was_data(rootData, use_column_constants)

# List of household variables currently used
# HPROPWW3                      Total (net) property wealth (net, i.e., = DVPropertyW3 - HMORTGW3)
# DVPropertyW3                  Total (gross) property wealth (sum of all property values)
# DVHValueW3                    Value of main residence
# DVHseValW3_sum                Total value of other houses
# DVBltValW3_sum                Total value of buy to let houses

# Derive gross housing wealth column for distribution.
derive_gross_housing_wealth_column(chunk)
# Filter down to keep only housing wealth
chunk = chunk[
    [
        WAS_TOTAL_PROPERTY_WEALTH,
        WAS_PROPERTY_VALUE_SUM,
        GROSS_HOUSING_WEALTH,
        WAS_WEIGHT,
    ]
]
# Keep positive wealth values for log-scale histogram.
chunk = filter_positive_values(
    chunk,
    [WAS_TOTAL_PROPERTY_WEALTH, WAS_PROPERTY_VALUE_SUM, GROSS_HOUSING_WEALTH],
)

# Define bin edges and widths
number_of_bins = int(max_log_bin_edge - min_log_bin_edge) * 4 + 1
bin_edges = np.logspace(min_log_bin_edge, max_log_bin_edge, number_of_bins, base=np.e)

# If printing data to files is required, histogram data and print results
if printResults:
    for variable in [
        WAS_TOTAL_PROPERTY_WEALTH,
        WAS_PROPERTY_VALUE_SUM,
        GROSS_HOUSING_WEALTH,
    ]:
        hist = np.histogram(
            chunk[variable].values,
            bins=bin_edges,
            density=True,
            weights=chunk[WAS_WEIGHT].values,
        )[0]
        # Write housing wealth distribution for validation.
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
        os.path.join(rootResults, "test", "HousingWealth-run1.csv"),
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
    # Plot model vs WAS housing wealth distributions for validation.
    plot_hist_overlay(
        bin_edges,
        model_hist,
        WAS_hist,
        xlabel="{}".format(variableToPlot),
        ylabel="Frequency (fraction of cases)",
        title="Distribution of Mark-to-market Net Housing Wealth ({})".format(
            variableToPlot
        ),
        log_x=True,
    )
    plt.show()
