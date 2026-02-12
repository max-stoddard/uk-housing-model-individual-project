"""Observation-building helpers shared across NMG desired-rent scripts."""

from __future__ import annotations

from collections.abc import Sequence

from scripts.python.helpers.nmg.band_mappings import (
    INCOME_BAND_LOWER,
    INCOME_BAND_MID,
    INCOME_BAND_UPPER,
    RENT_BAND_LOWER,
    RENT_BAND_MID,
    RENT_BAND_UPPER,
)
from scripts.python.helpers.nmg.parsing import parse_float, parse_int


def get_income_from_row(row: dict[str, str], source: str, columns: object) -> float | None:
    if source == "incomev2comb_upper":
        code = parse_int(row.get(columns.income_band))
        return INCOME_BAND_UPPER.get(code)
    if source == "incomev2comb_mid":
        code = parse_int(row.get(columns.income_band))
        return INCOME_BAND_MID.get(code)
    if source == "incomev2comb_lower":
        code = parse_int(row.get(columns.income_band))
        return INCOME_BAND_LOWER.get(code)
    if source == "sum_free_income":
        values = []
        for field in (columns.income_free_1, columns.income_free_2, columns.income_free_3):
            value = parse_float(row.get(field))
            if value is not None and value >= 0:
                values.append(value)
        if not values:
            return None
        return sum(values)
    if source == "self_free_income":
        value = parse_float(row.get(columns.income_free_1))
        if value is None or value < 0:
            return None
        return value
    raise ValueError(f"Unsupported income source: {source}")


def get_rent_from_row(
    row: dict[str, str],
    source: str,
    columns: object,
    rent_free_column: str | None,
) -> float | None:
    if source == "spq07_upper":
        code = parse_int(row.get(columns.rent_band))
        return RENT_BAND_UPPER.get(code)
    if source == "spq07_mid":
        code = parse_int(row.get(columns.rent_band))
        return RENT_BAND_MID.get(code)
    if source == "spq07_lower":
        code = parse_int(row.get(columns.rent_band))
        return RENT_BAND_LOWER.get(code)
    if source == "spq07_free":
        if rent_free_column is None:
            return None
        return parse_float(row.get(rent_free_column))
    if source == "spq07_free_or_upper":
        if rent_free_column is not None:
            value = parse_float(row.get(rent_free_column))
            if value is not None:
                return value
        code = parse_int(row.get(columns.rent_band))
        return RENT_BAND_UPPER.get(code)
    if source == "spq07_free_or_mid":
        if rent_free_column is not None:
            value = parse_float(row.get(rent_free_column))
            if value is not None:
                return value
        code = parse_int(row.get(columns.rent_band))
        return RENT_BAND_MID.get(code)
    if source == "spq07_free_or_lower":
        if rent_free_column is not None:
            value = parse_float(row.get(rent_free_column))
            if value is not None:
                return value
        code = parse_int(row.get(columns.rent_band))
        return RENT_BAND_LOWER.get(code)
    raise ValueError(f"Unsupported rent source: {source}")


def validate_required_desired_rent_columns(
    header: Sequence[str],
    columns: object,
    income_source: str,
    rent_source: str,
    rent_free_column: str | None,
) -> None:
    missing: list[str] = []
    lookup = set(header)

    for required in (columns.qhousing, columns.weight):
        if required not in lookup:
            missing.append(required)

    if income_source.startswith("incomev2comb_"):
        if columns.income_band not in lookup:
            missing.append(columns.income_band)
    elif income_source in {"sum_free_income", "self_free_income"}:
        for field in (columns.income_free_1, columns.income_free_2, columns.income_free_3):
            if field not in lookup and income_source == "sum_free_income":
                missing.append(field)
            if field == columns.income_free_1 and field not in lookup and income_source == "self_free_income":
                missing.append(field)
    else:
        raise ValueError(f"Unsupported income source: {income_source}")

    if rent_source in {"spq07_upper", "spq07_mid", "spq07_lower"}:
        if columns.rent_band not in lookup:
            missing.append(columns.rent_band)
    elif rent_source.startswith("spq07_free"):
        if rent_free_column is None and rent_source == "spq07_free":
            missing.append("SPQ07free_1|spq07free_1")
        if rent_source in {"spq07_free_or_upper", "spq07_free_or_mid", "spq07_free_or_lower"} and columns.rent_band not in lookup:
            missing.append(columns.rent_band)
    else:
        raise ValueError(f"Unsupported rent source: {rent_source}")

    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(set(missing))))
