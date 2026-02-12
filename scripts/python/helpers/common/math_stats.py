"""Common statistical helper functions."""

from __future__ import annotations

import math


def euclidean_distance_2d(x1: float, y1: float, x2: float, y2: float) -> float:
    """Euclidean distance in 2D."""
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
