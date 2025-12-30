# -*- coding: utf-8 -*-
"""
Class to study the probability of a household becoming a buy-to-let investor depending on its income percentile, based
on Wealth and Assets Survey data. This is the code used to create the file "BTLProbabilityPerIncomePercentileBin.csv".

@author: Adrian Carro, Max Stoddard
"""

from __future__ import division
import os
import sys

import pandas as pd
from scipy import stats

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from was.CSVWrite import write_rows
from was.DerivedColumns import (
    GROSS_NON_RENT_INCOME,
    derive_non_rent_income_columns,
)
from was.Config import WAS_DATA_ROOT
from was.RowFilters import filter_percentile_outliers
from was.IO import read_was_data
from was.Constants import (
    WAS_WEIGHT,
    WAS_NET_ANNUAL_INCOME,
    WAS_GROSS_ANNUAL_INCOME,
    WAS_NET_ANNUAL_RENTAL_INCOME,
    WAS_GROSS_ANNUAL_RENTAL_INCOME,
)

GROSS_NON_RENT_INCOME_PERCENTILE = "GrossNonRentIncomePercentile"

# List of household variables currently used
# DVTotGIRw3                  Household Gross Annual (regular) income
# DVTotNIRw3                  Household Net Annual (regular) income
# DVGrsRentAmtAnnualw3_aggr   Household Gross Annual income from rent
# DVNetRentAmtAnnualw3_aggr   Household Net Annual income from rent

# Read Wealth and Assets Survey data for households
root = WAS_DATA_ROOT
use_columns = [
    WAS_WEIGHT,
    WAS_GROSS_ANNUAL_INCOME,
    WAS_NET_ANNUAL_INCOME,
    WAS_GROSS_ANNUAL_RENTAL_INCOME,
    WAS_NET_ANNUAL_RENTAL_INCOME,
]
chunk = read_was_data(root, use_columns)
pd.set_option("display.max_columns", None)

# Derive non-rent income columns for percentile calculation.
derive_non_rent_income_columns(chunk)

# Filter out the 1% with highest GrossTotalIncome and the 1% with lowest NetTotalIncome
chunk = filter_percentile_outliers(
    chunk,
    lower_bound_column=WAS_NET_ANNUAL_INCOME,
    upper_bound_column=WAS_GROSS_ANNUAL_INCOME,
)

# Compute income percentiles (using gross non-rent income) of all households
chunk[GROSS_NON_RENT_INCOME_PERCENTILE] = [
    stats.percentileofscore(chunk[GROSS_NON_RENT_INCOME].values, x, "weak")
    for x in chunk[GROSS_NON_RENT_INCOME]
]

# Write to file probability of being a BTL investor for each percentile bin (of width 1%)
rows = []
for a in range(100):
    n_total = len(
        chunk[
            (a < chunk[GROSS_NON_RENT_INCOME_PERCENTILE])
            & (chunk[GROSS_NON_RENT_INCOME_PERCENTILE] <= a + 1.0)
        ]
    )
    n_BTL = len(
        chunk[
            (a < chunk[GROSS_NON_RENT_INCOME_PERCENTILE])
            & (chunk[GROSS_NON_RENT_INCOME_PERCENTILE] <= a + 1.0)
            & (chunk[WAS_GROSS_ANNUAL_RENTAL_INCOME] > 0.0)
        ]
    )
    rows.append((a / 100, (a + 1) / 100, n_BTL / n_total))
write_rows(
    "BTLProbabilityPerIncomePercentileBin.csv",
    "# Gross non-rental income percentile (lower edge), gross non-rental income percentile (upper edge), "
    "BTL probability\n",
    rows,
)
