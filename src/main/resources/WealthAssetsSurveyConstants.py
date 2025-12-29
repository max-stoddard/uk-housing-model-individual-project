"""
Constants for using the Wealth and Assets Survey dataset.
Datasets used can be found at: https://datacatalogue.ukdataservice.ac.uk/studies/study/7215

@author: Max Stoddard
"""

# Pick which WAS wave/round to dictate constants.
# Must be either "W3" (wave 3) or "R8" (round 8).
WAS_DATASET = "W3"

# All WAS columns used
WAS_WEIGHT = "Weight"  # Household Weight
WAS_NET_ANNUAL_INCOME = "NetTotalIncome"  # Household Gross Annual (regular) income
WAS_GROSS_ANNUAL_INCOME = "GrossTotalIncome"  # Household Net Annual (regular) income
WAS_NET_ANNUAL_RENTAL_INCOME = (
    "NetRentalIncome"  # Household Gross Annual income from rent
)
WAS_GROSS_ANNUAL_RENTAL_INCOME = (
    "GrossRentalIncome"  # Household Net Annual income from rent
)

WAS_DATA_FILENAME = {
    "W3": "was_wave_3_hhold_eul_final.dta",
    "R8": "was_round_8_hhold_eul_may_2025.privdata",
}[WAS_DATASET]

WAS_DATA_SEPARATOR = {
    "W3": ",",
    "R8": "\t",
}[WAS_DATASET]

# Map of internal column constants to survey column names.
WAS_COLUMN_MAP = {
    "W3": {
        WAS_WEIGHT: "w3xswgt",
        WAS_NET_ANNUAL_INCOME: "DVTotNIRw3",
        WAS_GROSS_ANNUAL_INCOME: "DVTotGIRw3",
        WAS_NET_ANNUAL_RENTAL_INCOME: "DVNetRentAmtAnnualw3_aggr",
        WAS_GROSS_ANNUAL_RENTAL_INCOME: "DVGrsRentAmtAnnualw3_aggr",
        "Age9": "HRPDVAge9W3",
        "Age15": "HRPDVAge15w3",
    },
    "R8": {
        WAS_WEIGHT: "R8xshhwgt",
        WAS_NET_ANNUAL_INCOME: "DVTotInc_BHCR8",
        WAS_GROSS_ANNUAL_INCOME: "DVTotGIRR8",
        WAS_NET_ANNUAL_RENTAL_INCOME: "DVNetRentAmtAnnualR8_aggr",
        WAS_GROSS_ANNUAL_RENTAL_INCOME: "DVGrsRentAmtAnnualR8_aggr",
        "Age8": "HRPDVAge8R8",
    },
}[WAS_DATASET]

# Bidirectional column map to rename from survey columns to internal constants and back.
WAS_COLUMN_RENAME_MAP = {
    **WAS_COLUMN_MAP,
    **{v: k for k, v in WAS_COLUMN_MAP.items()},
}

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
    "W3": {
        "Age9": AGE_9_BUCKET_DATA,
        "Age15": AGE_15_BUCKET_DATA,
    },
    "R8": {
        "Age8": AGE_8_BUCKET_DATA,
    },
}[WAS_DATASET]
