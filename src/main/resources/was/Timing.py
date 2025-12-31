"""
Timing helpers for WAS calibration and validation scripts.

@author: Max Stoddard
"""

from __future__ import annotations

import time

START_TAG = "[SCRIPT-START]"
END_TAG = "[SCRIPT-END]"


def start_timer(script_name: str, script_type: str) -> float:
    """Print a tagged start message and return the start time."""
    print(f"{START_TAG} Running {script_name} {script_type} script")
    return time.time()


def end_timer(start_time: float) -> None:
    """Print a tagged finish message with elapsed time."""
    elapsed = time.time() - start_time
    print(f"{END_TAG} Finished execution in {elapsed:.2f}s")
