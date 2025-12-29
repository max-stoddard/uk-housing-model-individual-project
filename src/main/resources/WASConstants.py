"""
Constants for using the Wealth and Assets Survey dataset.
Datasets used can be found at: https://datacatalogue.ukdataservice.ac.uk/studies/study/7215

@author: Max Stoddard
"""

# Pick which WAS wave/round to dictate constants.
# Must be either "W3" (wave 3) or "R8" (round 8).
WAS_DATASET = "R8"

# All WAS columns used
WAS_WEIGHT = "Weight"                                   # Household Weight
WAS_NET_ANNUAL_INCOME = "NetTotalIncome"                # Household Gross Annual (regular) income
WAS_GROSS_ANNUAL_INCOME = "GrossTotalIncome"            # Household Net Annual (regular) income
WAS_NET_ANNUAL_RENTAL_INCOME = "NetRentalIncome"        # Household Gross Annual income from rent
WAS_GROSS_ANNUAL_RENTAL_INCOME = "GrossRentalIncome"    # Household Net Annual income from rent

WAS_DATA_FILENAME = {
    "W3" : "was_wave_3_hhold_eul_final.dta",
    "R8" : "was_round_8_hhold_eul_may_2025.privdata",
}[WAS_DATASET]

WAS_DATA_SEPARATOR = {
    "W3" : ",",
    "R8" : "\t",
}[WAS_DATASET]

# Map of internal column constants to survey column names.
WAS_COLUMN_MAP = {
    "W3" : {
        WAS_WEIGHT : "w3xswgt",
        WAS_NET_ANNUAL_INCOME : "DVTotNIRw3",
        WAS_GROSS_ANNUAL_INCOME : "DVTotGIRw3",
        WAS_NET_ANNUAL_RENTAL_INCOME : "DVNetRentAmtAnnualw3_aggr",
        WAS_GROSS_ANNUAL_RENTAL_INCOME : "DVGrsRentAmtAnnualw3_aggr",
    },
    "R8" : {
        WAS_WEIGHT : "R8xshhwgt",
        WAS_NET_ANNUAL_INCOME : "DVTotInc_BHCR8",
        WAS_GROSS_ANNUAL_INCOME : "DVTotGIRR8",
        WAS_NET_ANNUAL_RENTAL_INCOME : "DVNetRentAmtAnnualR8_aggr",
        WAS_GROSS_ANNUAL_RENTAL_INCOME : "DVGrsRentAmtAnnualR8_aggr",
    },
}[WAS_DATASET]

# Bidirectional column map to rename from survey columns to internal constants and back.
WAS_COLUMN_RENAME_MAP = {
    **WAS_COLUMN_MAP,
    **{v: k for k, v in WAS_COLUMN_MAP.items()},
}
