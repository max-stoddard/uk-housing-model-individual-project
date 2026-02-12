"""
Collection of helper functions and constants for the derived WAS columns used across WAS
calibration/validation scripts.

@author: Max Stoddard
"""

from __future__ import annotations

import pandas as pd

from scripts.python.helpers.was.constants import (
    WAS_GROSS_ANNUAL_INCOME,
    WAS_GROSS_ANNUAL_RENTAL_INCOME,
    WAS_NET_ANNUAL_INCOME,
    WAS_NET_ANNUAL_RENTAL_INCOME,
    WAS_NATIONAL_SAVINGS_VALUE,
    WAS_CHILD_TRUST_FUND_VALUE,
    WAS_CHILD_OTHER_SAVINGS_VALUE,
    WAS_SAVINGS_ACCOUNTS_VALUE,
    WAS_CASH_ISA_VALUE,
    WAS_FORMAL_FINANCIAL_ASSETS,
    WAS_CURRENT_ACCOUNT_CREDIT_VALUE,
    WAS_MAIN_RESIDENCE_VALUE,
    WAS_OTHER_HOUSES_TOTAL_VALUE,
    WAS_BTL_HOUSES_TOTAL_VALUE,
)

# Household non-rent incomes
GROSS_NON_RENT_INCOME = "GrossNonRentIncome"
NET_NON_RENT_INCOME = "NetNonRentIncome"

# Household liquid financial wealth
LIQ_FINANCIAL_WEALTH = "LiqFinancialWealth"

# Household gross housing wealth
GROSS_HOUSING_WEALTH = "GrossHousingWealth"

# Household total wealth
TOTAL_WEALTH = "TotalWealth"


def derive_non_rent_income_columns(chunk: pd.DataFrame) -> pd.DataFrame:
    """Add a gross and net non-rent income columns to the dataframe."""
    chunk[GROSS_NON_RENT_INCOME] = (
        chunk[WAS_GROSS_ANNUAL_INCOME] - chunk[WAS_GROSS_ANNUAL_RENTAL_INCOME]
    )
    chunk[NET_NON_RENT_INCOME] = (
        chunk[WAS_NET_ANNUAL_INCOME] - chunk[WAS_NET_ANNUAL_RENTAL_INCOME]
    )
    return chunk


def derive_liquid_financial_wealth_column(chunk: pd.DataFrame) -> pd.DataFrame:
    """Add a liquid financial wealth column to this dataframe."""
    chunk[LIQ_FINANCIAL_WEALTH] = (
        chunk[WAS_NATIONAL_SAVINGS_VALUE].astype(float)
        + chunk[WAS_CHILD_TRUST_FUND_VALUE].astype(float)
        + chunk[WAS_CHILD_OTHER_SAVINGS_VALUE].astype(float)
        + chunk[WAS_SAVINGS_ACCOUNTS_VALUE].astype(float)
        + chunk[WAS_CASH_ISA_VALUE].astype(float)
        + chunk[WAS_FORMAL_FINANCIAL_ASSETS].astype(float)  # TODO: REQUIRES EXPERIMENT
        + chunk[WAS_CURRENT_ACCOUNT_CREDIT_VALUE].astype(float)
    )
    return chunk


def derive_gross_housing_wealth_column(chunk: pd.DataFrame) -> pd.DataFrame:
    """Add a gross housing wealth column to this dataframe."""
    chunk[GROSS_HOUSING_WEALTH] = (
        chunk[WAS_MAIN_RESIDENCE_VALUE].astype(float)
        + chunk[WAS_OTHER_HOUSES_TOTAL_VALUE].astype(float)
        + chunk[WAS_BTL_HOUSES_TOTAL_VALUE].astype(float)
    )
    return chunk


def derive_total_wealth_column(
    chunk: pd.DataFrame,
    financial_column: str,
    housing_column: str,
    total_column: str = TOTAL_WEALTH,
) -> pd.DataFrame:
    """Add a total wealth column from a financial and housing measure column."""
    chunk[total_column] = chunk[financial_column].astype(float) + chunk[
        housing_column
    ].astype(float)
    return chunk
