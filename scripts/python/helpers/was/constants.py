"""
Dataset column constants and mappings for the Wealth and Assets Survey.
Datasets used can be found at: https://datacatalogue.ukdataservice.ac.uk/studies/study/7215

@author: Max Stoddard
"""

from scripts.python.helpers.was.config import WAS_DATASET, WAVE_3_DATA, ROUND_8_DATA

### WAS Columns: ###

# Household Weight
WAS_WEIGHT = "Weight"

# Household Total Incomes
WAS_NET_ANNUAL_INCOME = "NetTotalIncome"  # Household Gross Annual (regular) income
WAS_GROSS_ANNUAL_INCOME = "GrossTotalIncome"  # Household Net Annual (regular) income

# Household Rental Incomes
WAS_NET_ANNUAL_RENTAL_INCOME = (
    "NetRentalIncome"  # Household Gross Annual income from rent
)
WAS_GROSS_ANNUAL_RENTAL_INCOME = (
    "GrossRentalIncome"  # Household Net Annual income from rent
)

# Household Total Wealth
WAS_GROSS_FINANCIAL_WEALTH = "GrossFinancialWealth"  # Gross Financial Wealth
WAS_NET_FINANCIAL_WEALTH = "NetFinancialWealth"  # Net Finanacial Wealth
WAS_NATIONAL_SAVINGS_VALUE = (
    "NationalSavingsValue"  # Household value of National Savings Product
)
WAS_CHILD_TRUST_FUND_VALUE = (
    "ChildTrustFundValue"  # Household value of children's trust funds
)
WAS_CHILD_OTHER_SAVINGS_VALUE = (
    "ChildOtherSavingsValue"  # Household value of other childrens savings
)
WAS_SAVINGS_ACCOUNTS_VALUE = (
    "SavingAccountsValue"  # Household value of savings accounts
)
WAS_CASH_ISA_VALUE = "CashISAValue"  # Household value of Cash ISA
WAS_CURRENT_ACCOUNT_CREDIT_VALUE = (
    "CurrentAccountCreditValue"  # Household value of current account in credit
)
WAS_FORMAL_FINANCIAL_ASSETS = "FormalFinancialAssets"
WAS_TOTAL_PROPERTY_WEALTH = "TotalPropertyWealth"  # Total property wealth
WAS_PROPERTY_VALUE_SUM = "PropertyValueSum"  # Sum of all property values
WAS_MAIN_RESIDENCE_VALUE = "MainResidenceValue"  # Value of main residence
WAS_OTHER_HOUSES_TOTAL_VALUE = "OtherHousesTotalValue"  # Total value of other houses
WAS_BTL_HOUSES_TOTAL_VALUE = "BTLHousesTotalValue"  # Total value of buy to let houses

### WAS Column maps ###

# Map of internal column constants to survey column names.
WAS_COLUMN_MAP = {
    WAVE_3_DATA: {
        WAS_WEIGHT: "w3xswgt",
        WAS_NET_ANNUAL_INCOME: "DVTotNIRw3",
        WAS_GROSS_ANNUAL_INCOME: "DVTotGIRw3",
        WAS_NET_ANNUAL_RENTAL_INCOME: "DVNetRentAmtAnnualw3_aggr",
        WAS_GROSS_ANNUAL_RENTAL_INCOME: "DVGrsRentAmtAnnualw3_aggr",
        "Age9": "HRPDVAge9W3",
        "Age15": "HRPDVAge15w3",
        WAS_GROSS_FINANCIAL_WEALTH: "HFINWW3_sum",
        WAS_NET_FINANCIAL_WEALTH: "HFINWNTw3_sum",
        WAS_NATIONAL_SAVINGS_VALUE: "DVFNSValW3_aggr",
        WAS_CHILD_TRUST_FUND_VALUE: "DVCACTvW3_aggr",
        WAS_CHILD_OTHER_SAVINGS_VALUE: "DVCASVVW3_aggr",
        WAS_SAVINGS_ACCOUNTS_VALUE: "DVSaValW3_aggr",
        WAS_CASH_ISA_VALUE: "DVCISAVW3_aggr",
        WAS_CURRENT_ACCOUNT_CREDIT_VALUE: "DVCaCrValW3_aggr",
        WAS_FORMAL_FINANCIAL_ASSETS: "DVFFAssetsW3_aggr",
        WAS_TOTAL_PROPERTY_WEALTH: "HPROPWW3",
        WAS_PROPERTY_VALUE_SUM: "DVPropertyW3",
        WAS_MAIN_RESIDENCE_VALUE: "DVHValueW3",
        WAS_OTHER_HOUSES_TOTAL_VALUE: "DVHseValW3_sum",
        WAS_BTL_HOUSES_TOTAL_VALUE: "DVBltValW3_sum",
    },
    ROUND_8_DATA: {
        WAS_WEIGHT: "R8xshhwgt",
        WAS_NET_ANNUAL_INCOME: "DVTotInc_BHCR8",
        WAS_GROSS_ANNUAL_INCOME: "DVTotGIRR8",
        WAS_NET_ANNUAL_RENTAL_INCOME: "DVNetRentAmtAnnualR8_aggr",
        WAS_GROSS_ANNUAL_RENTAL_INCOME: "DVGrsRentAmtAnnualR8_aggr",
        "Age8": "HRPDVAge8R8",
        WAS_GROSS_FINANCIAL_WEALTH: "HFINWR8_SUM",
        WAS_NET_FINANCIAL_WEALTH: "HFINWNTR8_Sum",
        WAS_NATIONAL_SAVINGS_VALUE: "DVFNSValR8_aggr",
        WAS_CHILD_TRUST_FUND_VALUE: "DVCACTvR8_aggr",
        WAS_CHILD_OTHER_SAVINGS_VALUE: "DVCASVVR8_aggr",
        WAS_SAVINGS_ACCOUNTS_VALUE: "DVSaValR8_aggr",
        WAS_CASH_ISA_VALUE: "DVCISAVR8_aggr",
        WAS_CURRENT_ACCOUNT_CREDIT_VALUE: "DVCaCrValR8_aggr",
        WAS_FORMAL_FINANCIAL_ASSETS: "DVFFAssetsR8_aggr",
        WAS_TOTAL_PROPERTY_WEALTH: "HPropWR8",
        WAS_PROPERTY_VALUE_SUM: "DVPropertyR8",
        WAS_MAIN_RESIDENCE_VALUE: "DVHValueR8",
        WAS_OTHER_HOUSES_TOTAL_VALUE: "DVHseValR8_sum",
        WAS_BTL_HOUSES_TOTAL_VALUE: "DVBltValR8_sum",
    },
}[WAS_DATASET]

# Bidirectional column map to rename from survey columns to internal constants and back.
WAS_COLUMN_RENAME_MAP = {
    **WAS_COLUMN_MAP,
    **{v: k for k, v in WAS_COLUMN_MAP.items()},
}

### WAS Age Maps ###

# Age of HRP or partner [0-15, 16-24, 25-34, 35-44, 45-54, 55-64, 65-74, 75+]
AGE_8_BUCKET_DATA = {
    "BIN_EDGES": [0, 15, 25, 35, 45, 55, 65, 75, 85],
    "TEXT_MAPPING": {
        "0-15": 7.5,
        "16-24": 20,
        "25-34": 30,
        "35-44": 40,
        "45-54": 50,
        "55-64": 60,
        "65-74": 70,
        "75+": 80,
    },
    "WAS_VALUE_MAPPING": {
        1: 7.5,
        2: 20,
        3: 30,
        4: 40,
        5: 50,
        6: 60,
        7: 70,
        8: 80,
    },
}

# Age of HRP or partner [0-15, 16-24, 25-34, 35-44, 45-54, 55-64, 65-74, 75-84, 85+]
AGE_9_BUCKET_DATA = {
    "BIN_EDGES": [0, 15, 25, 35, 45, 55, 65, 75, 85, 95],
    "TEXT_MAPPING": {
        "0-15": 7.5,
        "16-24": 20,
        "25-34": 30,
        "35-44": 40,
        "45-54": 50,
        "55-64": 60,
        "65-74": 70,
        "75-84": 80,
        "85+": 90,
    },
    "WAS_VALUE_MAPPING": {
        1: 7.5,
        2: 20,
        3: 30,
        4: 40,
        5: 50,
        6: 60,
        7: 70,
        8: 80,
        9: 90,
    },
}

# Age of HRP/Partner Banded (15) [0-16, 17-19, 20-24, 25-29, 30-34, 35-39, 40-44, 45-49, 50-54, 55-59, 60-64, 65-69, 70-74, 75-79, 80+]
AGE_15_BUCKET_DATA = {
    "BIN_EDGES": [0, 17, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85],
    "TEXT_MAPPING": {
        "0-16": 8.0,
        "17-19": 17.5,
        "20-24": 22.5,
        "25-29": 27.5,
        "30-34": 32.5,
        "35-39": 37.5,
        "40-44": 42.5,
        "45-49": 47.5,
        "50-54": 52.5,
        "55-59": 57.5,
        "60-64": 62.5,
        "65-69": 67.5,
        "70-74": 72.5,
        "75-79": 77.5,
        "80+": 82.5,
    },
    "WAS_VALUE_MAPPING": {
        1: 8.0,
        2: 17.5,
        3: 22.5,
        4: 27.5,
        5: 32.5,
        6: 37.5,
        7: 42.5,
        8: 47.5,
        9: 52.5,
        10: 57.5,
        11: 62.5,
        12: 67.5,
        13: 72.5,
        14: 77.5,
        15: 82.5,
    },
}


WAS_DATASET_AGE_BAND_MAPS = {
    WAVE_3_DATA: {
        "Age9": AGE_9_BUCKET_DATA,
        "Age15": AGE_15_BUCKET_DATA,
    },
    ROUND_8_DATA: {
        "Age8": AGE_8_BUCKET_DATA,
    },
}[WAS_DATASET]
