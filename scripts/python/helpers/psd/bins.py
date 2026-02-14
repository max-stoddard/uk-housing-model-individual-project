"""Band/bin parsing helpers for PSD mortgage experiment tables."""

from __future__ import annotations

import re
from dataclasses import dataclass

from scripts.python.helpers.psd.tables import parse_numeric_cell

_RANGE_SPLIT_RE = re.compile(r"\s*(?:-|to)\s*", re.IGNORECASE)
_VALUE_TOKEN_RE = re.compile(
    r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d*\.?\d+)(?:[eE][-+]?\d+)?\s*[kKmM]?"
)


@dataclass(frozen=True)
class PsdBin:
    """A single weighted band from PSD tables."""

    label: str
    lower: float | None
    upper: float | None
    mass: float



def _clean_token(token: str) -> str:
    return (
        token.replace("£", "")
        .replace("�", "")
        .replace(",", "")
        .replace("%", "")
        .strip()
    )



def parse_value_token(token: str) -> float:
    """Parse values like 2.5, 60K, 1M into absolute numeric values."""
    cleaned = _clean_token(token)
    if not cleaned:
        raise ValueError("Empty numeric token")

    multiplier = 1.0
    suffix = cleaned[-1].lower()
    if suffix == "k":
        multiplier = 1_000.0
        cleaned = cleaned[:-1]
    elif suffix == "m":
        multiplier = 1_000_000.0
        cleaned = cleaned[:-1]

    return float(cleaned) * multiplier



def parse_band_label(label: str) -> tuple[float | None, float | None] | None:
    """Parse open/closed interval labels used in PSD bands.

    Examples:
      - < 2.5
      - 2.5 to 3.49
      - 95% +
      - £0K - £60K
      - £1M +
    """
    text = label.strip()
    lower_text = text.lower()
    if not text:
        return None
    if lower_text.startswith("total"):
        return None
    if "unknown" in lower_text:
        return None

    if text.startswith("<"):
        numeric_tokens = _VALUE_TOKEN_RE.findall(text[1:])
        if not numeric_tokens:
            return None
        return None, parse_value_token(numeric_tokens[0])
    if text.startswith(">"):
        range_tokens = _RANGE_SPLIT_RE.split(text)
        if len(range_tokens) == 2:
            left_tokens = _VALUE_TOKEN_RE.findall(range_tokens[0])
            right_tokens = _VALUE_TOKEN_RE.findall(range_tokens[1])
            if left_tokens and right_tokens:
                return parse_value_token(left_tokens[0]), parse_value_token(right_tokens[0])
        numeric_tokens = _VALUE_TOKEN_RE.findall(text[1:])
        if not numeric_tokens:
            return None
        return parse_value_token(numeric_tokens[0]), None

    if "+" in text:
        plus_base = text.replace("+", "")
        numeric_tokens = _VALUE_TOKEN_RE.findall(plus_base)
        if not numeric_tokens:
            return None
        return parse_value_token(numeric_tokens[0]), None

    range_tokens = _RANGE_SPLIT_RE.split(text)
    if len(range_tokens) == 2:
        left_tokens = _VALUE_TOKEN_RE.findall(range_tokens[0])
        right_tokens = _VALUE_TOKEN_RE.findall(range_tokens[1])
        if not left_tokens or not right_tokens:
            return None
        return parse_value_token(left_tokens[0]), parse_value_token(right_tokens[0])

    return None



def build_bins_from_category_masses(
    category_masses: dict[str, float],
    *,
    drop_nonpositive_mass: bool = True,
) -> list[PsdBin]:
    """Build weighted bins from pre-aggregated category -> mass mappings."""
    bins: list[PsdBin] = []
    for label, mass in category_masses.items():
        bounds = parse_band_label(label)
        if bounds is None:
            continue
        if drop_nonpositive_mass and mass <= 0.0:
            continue
        bins.append(PsdBin(label=label, lower=bounds[0], upper=bounds[1], mass=mass))
    return sort_bins_for_quantile(bins)


def build_bins_from_labeled_rows(
    labeled_rows: list[tuple[str, list[str]]],
    year_column: int,
    *,
    drop_nonpositive_mass: bool = True,
) -> list[PsdBin]:
    """Build weighted bins from section label rows for one target year column."""
    bins: list[PsdBin] = []
    for label, row in labeled_rows:
        bounds = parse_band_label(label)
        if bounds is None:
            continue
        mass = parse_numeric_cell(row, year_column)
        if mass is None:
            continue
        if drop_nonpositive_mass and mass <= 0.0:
            continue
        bins.append(PsdBin(label=label, lower=bounds[0], upper=bounds[1], mass=mass))
    return sort_bins_for_quantile(bins)



def sort_bins_for_quantile(bins: list[PsdBin]) -> list[PsdBin]:
    """Sort bins by lower bound, placing open-lower bins first."""
    return sorted(bins, key=lambda item: (-1.0 if item.lower is None else item.lower, item.label))



def combine_bin_masses(*bin_sets: list[PsdBin]) -> list[PsdBin]:
    """Combine multiple bin sets by exact label and interval identity."""
    combined: dict[tuple[str, float | None, float | None], float] = {}
    for bin_set in bin_sets:
        for item in bin_set:
            key = (item.label, item.lower, item.upper)
            combined[key] = combined.get(key, 0.0) + item.mass

    merged = [
        PsdBin(label=label, lower=lower, upper=upper, mass=mass)
        for (label, lower, upper), mass in combined.items()
        if mass > 0.0
    ]
    return sort_bins_for_quantile(merged)



def subtract_bin_masses(minuend: list[PsdBin], subtrahend: list[PsdBin]) -> list[PsdBin]:
    """Subtract one bin set from another by label + interval, clipping at zero."""
    sub_map: dict[tuple[str, float | None, float | None], float] = {}
    for item in subtrahend:
        key = (item.label, item.lower, item.upper)
        sub_map[key] = sub_map.get(key, 0.0) + item.mass

    result: list[PsdBin] = []
    for item in minuend:
        key = (item.label, item.lower, item.upper)
        remaining_mass = max(item.mass - sub_map.get(key, 0.0), 0.0)
        if remaining_mass > 0.0:
            result.append(
                PsdBin(
                    label=item.label,
                    lower=item.lower,
                    upper=item.upper,
                    mass=remaining_mass,
                )
            )
    return sort_bins_for_quantile(result)


__all__ = [
    "PsdBin",
    "build_bins_from_category_masses",
    "build_bins_from_labeled_rows",
    "combine_bin_masses",
    "parse_band_label",
    "parse_value_token",
    "sort_bins_for_quantile",
    "subtract_bin_masses",
]
