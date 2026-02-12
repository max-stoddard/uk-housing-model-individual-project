"""Common CLI formatting helpers."""

from __future__ import annotations


def format_float(value: float, decimals: int = 10) -> str:
    """Format floats consistently for CLI output."""
    return f"{value:.{decimals}f}".rstrip("0").rstrip(".")
