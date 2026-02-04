"""
Helpers for selecting and reloading WAS dataset-specific modules.

@author: Max Stoddard
"""

from __future__ import annotations

import importlib
import os
from typing import Sequence

from was import Config as was_config
from was import Constants as was_constants
from was import IO as was_io


def reload_was_modules(
    dataset: str,
    extra_modules: Sequence[object] | None = None,
) -> tuple[object, ...]:
    """Reload WAS modules so dataset-specific constants are refreshed."""
    if dataset not in (was_config.WAVE_3_DATA, was_config.ROUND_8_DATA):
        raise ValueError(
            "Dataset must be WAVE_3_DATA or ROUND_8_DATA, got {!r}".format(dataset)
        )
    os.environ["WAS_DATASET"] = dataset
    modules = [was_config, was_constants, was_io]
    if extra_modules:
        modules.extend(extra_modules)
    return tuple(importlib.reload(module) for module in modules)
