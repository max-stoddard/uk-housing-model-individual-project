"""
Runtime configuration for WAS data access and dataset selection.

@author: Max Stoddard
"""

from __future__ import annotations

import os


def _parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"{name} must be one of 1/0, true/false, yes/no, on/off; got {value!r}"
    )

# WAS wave/round identifiers.
WAVE_3_DATA = "W3"  # Wave 3 covers July 2010 to June 2012.
ROUND_8_DATA = "R8"  # Round 8 covers April 2020 to March 2022.

# Pick which WAS wave/round to dictate configuration.
# Must be either WAVE_3_DATA or ROUND_8_DATA.
WAS_DATASET = os.getenv("WAS_DATASET", ROUND_8_DATA)
if WAS_DATASET not in (WAVE_3_DATA, ROUND_8_DATA):
    raise ValueError(
        "WAS_DATASET must be WAVE_3_DATA or ROUND_8_DATA, got {!r}".format(WAS_DATASET)
    )

# Shared data and results roots
WAS_DATA_ROOT = os.getenv("WAS_DATA_ROOT", "")
WAS_RESULTS_ROOT = os.getenv("WAS_RESULTS_ROOT", "")
WAS_RESULTS_RUN_SUBDIR = os.getenv(
    "WAS_RESULTS_RUN_SUBDIR",
    "Results/v1-output",
)

# Toggle validation plotting (matplotlib). Default kept as True for backward compatibility;
# versioned validation wrappers set this explicitly.
WAS_VALIDATION_PLOTS = _parse_bool_env("WAS_VALIDATION_PLOTS", True)

# WAS dataset files and separators per wave.
WAS_DATA_FILENAME = {
    WAVE_3_DATA: "private-datasets/was/was_wave_3_hhold_eul_final.dta",
    ROUND_8_DATA: "private-datasets/was/was_round_8_hhold_eul_may_2025.privdata",
}[WAS_DATASET]

WAS_DATA_SEPARATOR = {
    WAVE_3_DATA: ",",
    ROUND_8_DATA: "\t",
}[WAS_DATASET]
