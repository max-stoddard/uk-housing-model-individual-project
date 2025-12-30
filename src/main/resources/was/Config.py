"""
Runtime configuration for WAS data access and dataset selection.

@author: Max Stoddard
"""

from __future__ import annotations

import os

# WAS wave/round identifiers.
WAVE_3_DATA = "W3"  # Wave 3 covers July 2010 to June 2012.
ROUND_8_DATA = "R8"  # Round 8 covers April 2020 to March 2022.

# Pick which WAS wave/round to dictate configuration.
# Must be either WAVE_3_DATA or ROUND_8_DATA.
WAS_DATASET = WAVE_3_DATA

# Shared data and results roots (optional overrides).
WAS_DATA_ROOT = os.getenv("WAS_DATA_ROOT", "")
WAS_RESULTS_ROOT = os.getenv("WAS_RESULTS_ROOT", "")

# WAS dataset files and separators per wave.
WAS_DATA_FILENAME = {
    WAVE_3_DATA: "was_wave_3_hhold_eul_final.dta",
    ROUND_8_DATA: "was_round_8_hhold_eul_may_2025.privdata",
}[WAS_DATASET]

WAS_DATA_SEPARATOR = {
    WAVE_3_DATA: ",",
    ROUND_8_DATA: "\t",
}[WAS_DATASET]
