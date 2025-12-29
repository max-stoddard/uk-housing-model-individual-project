# -*- coding: utf-8 -*-
"""
Class to study households' age distribution based on Wealth and Assets Survey data.
Creates weighted distributions for each age band as "<AgeBand>-<WAS_DATASET>-Weighted.csv".

@author: Adrian Carro
"""

from __future__ import division
import os
import sys

import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from WealthAssetsSurveyConstants import (
    WAS_COLUMN_MAP,
    WAS_COLUMN_RENAME_MAP,
    WAS_DATASET,
    WAS_DATA_FILENAME,
    WAS_DATA_SEPARATOR,
    WAS_WEIGHT,
    WAS_DATASET_AGE_BAND_MAPS,
)


# Read Wealth and Assets Survey data for households
root = r""
age_columns = list(WAS_DATASET_AGE_BAND_MAPS.keys())
chunk = pd.read_csv(
    os.path.join(root, WAS_DATA_FILENAME),
    usecols=[WAS_COLUMN_MAP[WAS_WEIGHT]]
    + [WAS_COLUMN_MAP[age_column] for age_column in age_columns],
    sep=WAS_DATA_SEPARATOR,
)
pd.set_option("display.max_columns", None)

# Rename columns to be used
chunk.rename(columns=WAS_COLUMN_RENAME_MAP, inplace=True)
chunk = chunk[age_columns + [WAS_WEIGHT]]

for age_column, bucket_data in WAS_DATASET_AGE_BAND_MAPS.items():
    bucket_mapping = {
        **bucket_data["TEXT_MAPPING"],
        **bucket_data["WAS_VALUE_MAPPING"],
    }
    chunk[age_column] = chunk[age_column].map(bucket_mapping)

# Filter down to keep only columns of interest & drop missing/invalid codes
chunk = chunk.dropna(subset=age_columns + [WAS_WEIGHT])
chunk = chunk[chunk[WAS_WEIGHT] > 0]

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
    with open(output_filename, "w") as f:
        f.write("# Age (lower edge), Age (upper edge), Probability\n")
        for element, lower_edge, upper_edge in zip(
            frequency, histogram_bin_edges[:-1], histogram_bin_edges[1:]
        ):
            if lower_edge == bin_edges[0] and element == 0:
                continue
            f.write(f"{lower_edge}, {upper_edge}, {element}\n")
