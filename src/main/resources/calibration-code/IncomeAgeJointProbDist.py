# -*- coding: utf-8 -*-
"""
Class to study households' income distribution depending on their age based on Wealth and Assets Survey data. This is
the code used to create file "AgeGrossIncomeJointDist.csv".

@author: Adrian Carro, Max Stoddard
"""

import os
import sys

import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from was.CSVWrite import write_joint_distribution
from was.DerivedColumns import (
    GROSS_NON_RENT_INCOME,
    NET_NON_RENT_INCOME,
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
    WAS_DATASET_AGE_BAND_MAPS,
)


# Read Wealth and Assets Survey data for households
root = WAS_DATA_ROOT
age_column_key = next(iter(WAS_DATASET_AGE_BAND_MAPS))
use_column_constants = [
    WAS_WEIGHT,
    WAS_GROSS_ANNUAL_INCOME,
    WAS_NET_ANNUAL_INCOME,
    WAS_GROSS_ANNUAL_RENTAL_INCOME,
    WAS_NET_ANNUAL_RENTAL_INCOME,
    age_column_key,
]
chunk = read_was_data(root, use_column_constants)
# Derive non-rent income columns for the joint distribution.
derive_non_rent_income_columns(chunk)
# Rename column with age as "Age"
chunk.rename(columns={age_column_key: "Age"}, inplace=True)
# Filter down to keep only columns of interest
chunk = chunk[["Age", GROSS_NON_RENT_INCOME, NET_NON_RENT_INCOME, WAS_WEIGHT]]
# Filter out the 1% with highest GrossNonRentIncome and the 1% with lowest NetNonRentIncome to stabilize joint distribution.
chunk = filter_percentile_outliers(
    chunk,
    lower_bound_column=NET_NON_RENT_INCOME,
    upper_bound_column=GROSS_NON_RENT_INCOME,
)
# Set bounds for log income bins after filtering.
min_net_income = chunk[NET_NON_RENT_INCOME].min()
max_gross_income = chunk[GROSS_NON_RENT_INCOME].max()
# Map age buckets to middle of bucket value by creating the corresponding dictionary
age_bucket_data = WAS_DATASET_AGE_BAND_MAPS[age_column_key]
age_from_text = chunk["Age"].map(age_bucket_data["TEXT_MAPPING"])
age_from_values = pd.to_numeric(chunk["Age"], errors="coerce").map(
    age_bucket_data["WAS_VALUE_MAPPING"]
)
chunk["Age"] = age_from_text.fillna(age_from_values)

# Create a 2D histogram of the data with logarithmic income bins (no normalisation here as we want column normalisation,
# to be introduced when plotting or printing)
income_bin_edges = np.linspace(np.log(min_net_income), np.log(max_gross_income), 26)
age_bin_edges = age_bucket_data["BIN_EDGES"][1:]
frequency_gross = np.histogram2d(
    chunk["Age"].values,
    np.log(chunk[GROSS_NON_RENT_INCOME].values),
    bins=[age_bin_edges, income_bin_edges],
    density=True,
    weights=chunk[WAS_WEIGHT].values,
)[0]
frequency_net = np.histogram2d(
    chunk["Age"].values,
    np.log(chunk[NET_NON_RENT_INCOME].values),
    bins=[age_bin_edges, income_bin_edges],
    density=True,
    weights=chunk[WAS_WEIGHT].values,
)[0]

# Print joint distributions to files
# Write age vs gross income distribution for calibration.
write_joint_distribution(
    "AgeGrossIncomeJointDist.csv",
    "Age",
    "Gross Income",
    frequency_gross,
    age_bin_edges,
    income_bin_edges,
    x_is_log=False,
    y_is_log=True,
)
# Write age vs net income distribution for calibration.
write_joint_distribution(
    "AgeNetIncomeJointDist.csv",
    "Age",
    "Net Income",
    frequency_net,
    age_bin_edges,
    income_bin_edges,
    x_is_log=False,
    y_is_log=True,
)
