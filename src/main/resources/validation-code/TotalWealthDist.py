# -*- coding: utf-8 -*-
"""
Class to study households' total wealth (financial + housing) distribution, for validation purposes, based on Wealth and
Assets Survey data.

@author: Adrian Carro, Max Stoddard
"""

from __future__ import division
import os
import sys

import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from was.IO import read_was_data
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
    WAS_TOTAL_PROPERTY_WEALTH,
    WAS_PROPERTY_VALUE_SUM,
    WAS_MAIN_RESIDENCE_VALUE,
    WAS_OTHER_HOUSES_TOTAL_VALUE,
    WAS_BTL_HOUSES_TOTAL_VALUE,
)
from was.DerivedColumns import (
    GROSS_HOUSING_WEALTH,
    LIQ_FINANCIAL_WEALTH,
    TOTAL_WEALTH,
    derive_gross_housing_wealth_column,
    derive_liquid_financial_wealth_column,
    derive_total_wealth_column,
)


# Read Wealth and Assets Survey data for households
root = r""  # ADD HERE PATH TO WAS DATA FOLDER
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
    WAS_TOTAL_PROPERTY_WEALTH,
    WAS_PROPERTY_VALUE_SUM,
    WAS_MAIN_RESIDENCE_VALUE,
    WAS_OTHER_HOUSES_TOTAL_VALUE,
    WAS_BTL_HOUSES_TOTAL_VALUE,
]
chunk = read_was_data(root, use_column_constants)

# List of household variables currently used
# HFINWW3_sum                   Gross Financial Wealth (financial assets only)
# HFINWNTW3_sum                 Household Net financial Wealth (financial assets minus financial liabilities)

# Derive liquid financial wealth and gross housing wealth columns.
derive_liquid_financial_wealth_column(chunk)
derive_gross_housing_wealth_column(chunk)
# Filter down to keep only these columns
chunk = chunk[
    [
        WAS_WEIGHT,
        WAS_NET_FINANCIAL_WEALTH,
        WAS_GROSS_FINANCIAL_WEALTH,
        LIQ_FINANCIAL_WEALTH,
        WAS_TOTAL_PROPERTY_WEALTH,
        WAS_PROPERTY_VALUE_SUM,
        GROSS_HOUSING_WEALTH,
    ]
]

# Create wealth bins for histograms
min_wealth_bin = 2.0
max_wealth_bin = 16.0
wealth_bin_edges = np.linspace(min_wealth_bin, max_wealth_bin, 57)

# For each combination of housing wealth and financial wealth measures...
financial_wealth_measures = [
    WAS_NET_FINANCIAL_WEALTH,
    WAS_GROSS_FINANCIAL_WEALTH,
    LIQ_FINANCIAL_WEALTH,
]
housing_wealth_measures = [
    WAS_TOTAL_PROPERTY_WEALTH,
    WAS_PROPERTY_VALUE_SUM,
    GROSS_HOUSING_WEALTH,
]
for financial_wealth_measure in financial_wealth_measures:
    for housing_wealth_measure in housing_wealth_measures:
        # ...add total wealth column
        # Derive total wealth from financial and housing measures.
        derive_total_wealth_column(
            chunk, financial_wealth_measure, housing_wealth_measure
        )
        # For the sake of using logarithmic scales, filter out any zero and negative values
        temp_chunk = chunk[(chunk[TOTAL_WEALTH] > 0.0)]
        # ...create a histogram
        frequency = np.histogram(
            np.log(temp_chunk[TOTAL_WEALTH].values),
            bins=wealth_bin_edges,
            density=True,
            weights=temp_chunk[WAS_WEIGHT].values,
        )[0]
        # ...and print the distribution to a file
        with open(
            financial_wealth_measure + "-" + housing_wealth_measure + "-Weighted.csv",
            "w",
        ) as f:
            f.write(
                "# Log Total Wealth ("
                + financial_wealth_measure
                + " + "
                + housing_wealth_measure
                + ") (lower edge), Log Total Wealth ("
                + financial_wealth_measure
                + " + "
                + housing_wealth_measure
                + ") (upper edge), Probability\n"
            )
            for element, wealthLowerEdge, wealthUpperEdge in zip(
                frequency, wealth_bin_edges[:-1], wealth_bin_edges[1:]
            ):
                f.write(
                    "{}, {}, {}\n".format(wealthLowerEdge, wealthUpperEdge, element)
                )
