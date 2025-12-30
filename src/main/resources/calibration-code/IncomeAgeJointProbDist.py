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
from was.IO import read_was_data
from was.WealthAssetsSurveyConstants import (
    WAS_WEIGHT,
    WAS_NET_ANNUAL_INCOME,
    WAS_GROSS_ANNUAL_INCOME,
    WAS_NET_ANNUAL_RENTAL_INCOME,
    WAS_GROSS_ANNUAL_RENTAL_INCOME,
    WAS_DATASET_AGE_BAND_MAPS,
)


# Read Wealth and Assets Survey data for households
root = r""  # ADD HERE PATH TO WAS DATA FOLDER
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
# Add column with total gross income, except rental income (gross)
chunk["GrossNonRentIncome"] = (
    chunk[WAS_GROSS_ANNUAL_INCOME] - chunk[WAS_GROSS_ANNUAL_RENTAL_INCOME]
)
# Add column with total net income, except rental income (net)
chunk["NetNonRentIncome"] = (
    chunk[WAS_NET_ANNUAL_INCOME] - chunk[WAS_NET_ANNUAL_RENTAL_INCOME]
)
# Rename column with age as "Age"
chunk.rename(columns={age_column_key: "Age"}, inplace=True)
# Filter down to keep only columns of interest
chunk = chunk[["Age", "GrossNonRentIncome", "NetNonRentIncome", WAS_WEIGHT]]
# Filter out the 1% with highest GrossNonRentIncome and the 1% with lowest NetNonRentIncome
one_per_cent = int(round(len(chunk.index) / 100))
chunk_ord_by_gross = chunk.sort_values("GrossNonRentIncome")
chunk_ord_by_net = chunk.sort_values("NetNonRentIncome")
max_gross_income = chunk_ord_by_gross.iloc[-one_per_cent]["GrossNonRentIncome"]
min_net_income = chunk_ord_by_net.iloc[one_per_cent]["NetNonRentIncome"]
chunk = chunk[chunk["GrossNonRentIncome"] <= max_gross_income]
chunk = chunk[chunk["NetNonRentIncome"] >= min_net_income]
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
    np.log(chunk["GrossNonRentIncome"].values),
    bins=[age_bin_edges, income_bin_edges],
    density=True,
    weights=chunk[WAS_WEIGHT].values,
)[0]
frequency_net = np.histogram2d(
    chunk["Age"].values,
    np.log(chunk["NetNonRentIncome"].values),
    bins=[age_bin_edges, income_bin_edges],
    density=True,
    weights=chunk[WAS_WEIGHT].values,
)[0]

# Print joint distributions to files
with open("AgeGrossIncomeJointDist.csv", "w") as f:
    f.write(
        "# Age (lower edge), Age (upper edge), Log Gross Income (lower edge), Log Gross Income (upper edge), "
        "Probability\n"
    )
    for line, ageLowerEdge, ageUpperEdge in zip(
        frequency_gross, age_bin_edges[:-1], age_bin_edges[1:]
    ):
        for element, incomeLowerEdge, incomeUpperEdge in zip(
            line, income_bin_edges[:-1], income_bin_edges[1:]
        ):
            f.write(
                "{}, {}, {}, {}, {}\n".format(
                    ageLowerEdge,
                    ageUpperEdge,
                    incomeLowerEdge,
                    incomeUpperEdge,
                    element / sum(line),
                )
            )
with open("AgeNetIncomeJointDist.csv", "w") as f:
    f.write(
        "# Age (lower edge), Age (upper edge), Log Net Income (lower edge), Log Net Income (upper edge), "
        "Probability\n"
    )
    for line, ageLowerEdge, ageUpperEdge in zip(
        frequency_net, age_bin_edges[:-1], age_bin_edges[1:]
    ):
        for element, incomeLowerEdge, incomeUpperEdge in zip(
            line, income_bin_edges[:-1], income_bin_edges[1:]
        ):
            f.write(
                "{}, {}, {}, {}, {}\n".format(
                    ageLowerEdge,
                    ageUpperEdge,
                    incomeLowerEdge,
                    incomeUpperEdge,
                    element / sum(line),
                )
            )
