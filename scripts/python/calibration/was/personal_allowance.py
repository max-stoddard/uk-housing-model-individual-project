# -*- coding: utf-8 -*-
"""
Class to show that a single personal allowance produces a better fit of the net income of households as a function of
their gross income, based on Wealth and Assets Survey data.

@author: Adrian Carro, Max Stoddard
"""

from __future__ import division
import os
from pathlib import Path

import pandas as pd
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[4]
TAX_RATE_FILE = str(REPO_ROOT / "src" / "main" / "resources" / "TaxRates.csv")
from scripts.python.helpers.was.derived_columns import (
    GROSS_NON_RENT_INCOME,
    NET_NON_RENT_INCOME,
    derive_non_rent_income_columns,
)
from scripts.python.helpers.was.timing import start_timer, end_timer
from scripts.python.helpers.was.config import WAS_DATA_ROOT
from scripts.python.helpers.was.row_filters import filter_percentile_outliers
from scripts.python.helpers.was.io import read_was_data
from scripts.python.helpers.was.constants import (
    WAS_WEIGHT,
    WAS_NET_ANNUAL_INCOME,
    WAS_GROSS_ANNUAL_INCOME,
    WAS_NET_ANNUAL_RENTAL_INCOME,
    WAS_GROSS_ANNUAL_RENTAL_INCOME,
)

timer_start = start_timer(os.path.basename(__file__), "calibration")

tax_rates = pd.read_csv(
    TAX_RATE_FILE, comment="#", header=None, names=["band_start", "rate"]
)
TAX_BANDS_AFTER_ALLOWANCE = list(zip(tax_rates["band_start"], tax_rates["rate"]))
TAX_BANDS_AFTER_ALLOWANCE.sort(key=lambda band: band[0])


def getNetFromGross(gross_income, allowance):
    """Implements tax bands and rates corresponding to the tax year 2025-26 from TaxRates.csv"""
    taxable_income = max(0, gross_income - allowance)

    tax_due = 0
    for index, (band_start, rate) in enumerate(TAX_BANDS_AFTER_ALLOWANCE):
        next_band_start = (
            TAX_BANDS_AFTER_ALLOWANCE[index + 1][0]
            if index + 1 < len(TAX_BANDS_AFTER_ALLOWANCE)
            else None
        )
        if taxable_income <= band_start:
            continue

        band_upper_limit = (
            next_band_start if next_band_start is not None else taxable_income
        )
        taxable_in_band = min(taxable_income, band_upper_limit) - band_start
        tax_due += taxable_in_band * rate

    return gross_income - tax_due


# Read Wealth and Assets Survey data for households
root = WAS_DATA_ROOT
use_columns = [
    WAS_WEIGHT,
    WAS_NET_ANNUAL_INCOME,
    WAS_GROSS_ANNUAL_INCOME,
    WAS_NET_ANNUAL_RENTAL_INCOME,
    WAS_GROSS_ANNUAL_RENTAL_INCOME,
]
chunk = read_was_data(root, use_columns)

# Derive non-rent income columns for analysis.
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

# Remove extreme income outliers to stabilize allowance fit.
chunk = filter_percentile_outliers(
    chunk,
    lower_bound_column=WAS_NET_ANNUAL_INCOME,
    upper_bound_column=WAS_GROSS_ANNUAL_INCOME,
)

# Compute logarithmic difference between predicted and actual net income for the 2025-2026 personal allowance
PERSONAL_ALLOWANCE_2025_26 = 12570
singleAllowanceDiff = sum(
    (np.log(getNetFromGross(g, PERSONAL_ALLOWANCE_2025_26)) - np.log(n)) ** 2
    for g, n in zip(
        chunk[WAS_GROSS_ANNUAL_INCOME].values, chunk[WAS_NET_ANNUAL_INCOME].values
    )
)
# Compute logarithmic difference between predicted and actual net income for a double personal allowance
doubleAllowanceDiff = sum(
    (np.log(getNetFromGross(g, 2 * PERSONAL_ALLOWANCE_2025_26)) - np.log(n)) ** 2
    for g, n in zip(
        chunk[WAS_GROSS_ANNUAL_INCOME].values, chunk[WAS_NET_ANNUAL_INCOME].values
    )
)
# Print results to screen
print(
    "Logarithmic difference between predicted and actual net income for a single personal allowance {:.2f}".format(
        singleAllowanceDiff
    )
)
print(
    "Logarithmic difference between predicted and actual net income for a double personal allowance {:.2f}".format(
        doubleAllowanceDiff
    )
)
end_timer(timer_start)
