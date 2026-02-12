"""Parsing helpers shared across NMG calibration and experiment scripts."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from scripts.python.helpers.common.io_properties import read_properties


def parse_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(raw: str | None) -> int | None:
    value = parse_float(raw)
    if value is None:
        return None
    return int(value)


def parse_positive_float(raw: str | None) -> float | None:
    value = parse_float(raw)
    if value is None or value <= 0:
        return None
    return value


def parse_qhousing_values(raw: str) -> set[int]:
    values: set[int] = set()
    for token in raw.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        try:
            values.add(int(stripped))
        except ValueError as exc:
            raise ValueError(f"Invalid qhousing value: {stripped}") from exc
    if not values:
        raise ValueError("qhousing values cannot be empty.")
    return values


def resolve_optional_column(header: Sequence[str], candidates: Sequence[str]) -> str | None:
    lookup = set(header)
    for name in candidates:
        if name in lookup:
            return name
    return None


__all__ = [
    "parse_float",
    "parse_int",
    "parse_positive_float",
    "parse_qhousing_values",
    "resolve_optional_column",
    "read_properties",
    "Path",
]
