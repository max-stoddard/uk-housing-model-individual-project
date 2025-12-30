# -*- coding: utf-8 -*-
"""
Class to study households' age distribution based on Wealth and Assets Survey data.
Creates weighted distributions for each age band as "<AgeBand>-<WAS_DATASET>-Weighted.csv".

@author: Adrian Carro, Max Stoddard
"""

from __future__ import division
import os
import sys

import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from was.CSVWrite import write_rows
from was.IO import read_was_data
from was.RowFilters import drop_missing_rows, filter_positive_values
from was.Config import WAS_DATASET, WAS_DATA_ROOT
from was.Constants import WAS_WEIGHT, WAS_DATASET_AGE_BAND_MAPS


# Read Wealth and Assets Survey data for households
root = WAS_DATA_ROOT
age_columns = list(WAS_DATASET_AGE_BAND_MAPS.keys())
chunk = read_was_data(root, [WAS_WEIGHT] + age_columns)
pd.set_option("display.max_columns", None)

chunk = chunk[age_columns + [WAS_WEIGHT]]

for age_column, bucket_data in WAS_DATASET_AGE_BAND_MAPS.items():
    bucket_mapping = {
        **bucket_data["TEXT_MAPPING"],
        **bucket_data["WAS_VALUE_MAPPING"],
    }
    chunk[age_column] = chunk[age_column].map(bucket_mapping)

# Filter down to keep only columns of interest & drop missing/invalid codes
chunk = drop_missing_rows(chunk, age_columns + [WAS_WEIGHT])
# Keep positive weights for weighted distributions.
chunk = filter_positive_values(chunk, [WAS_WEIGHT])

for age_column, bucket_data in WAS_DATASET_AGE_BAND_MAPS.items():
    # Map age buckets to middle of bucket value by using the corresponding dictionary
    bin_edges = bucket_data["BIN_EDGES"]
    frequency, histogram_bin_edges = np.histogram(
        chunk[age_column].values,
        bins=bin_edges,
        density=True,
        weights=chunk[WAS_WEIGHT].values,
    )

    # Print distributions to file
    output_filename = f"{age_column}-{WAS_DATASET}-Weighted.csv"
    # Write weighted age distribution for calibration.
    rows = []
    for element, lower_edge, upper_edge in zip(
        frequency, histogram_bin_edges[:-1], histogram_bin_edges[1:]
    ):
        if lower_edge == bin_edges[0] and element == 0:
            continue
        rows.append((lower_edge, upper_edge, element))
    write_rows(
        output_filename,
        "# Age (lower edge), Age (upper edge), Probability\n",
        rows,
    )
