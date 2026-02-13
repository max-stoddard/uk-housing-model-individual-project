"""Shared BTL-strategy parsing and aggregation helpers for NMG scripts.

@author: Max Stoddard
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from scripts.python.helpers.nmg.parsing import parse_float, parse_int

LEGACY_WEIGHTED = "legacy_weighted"
LEGACY_UNWEIGHTED = "legacy_unweighted"
SIMPLE_SEMANTIC_WEIGHTED = "simple_semantic_weighted"
SIMPLE_SEMANTIC_UNWEIGHTED = "simple_semantic_unweighted"

METHOD_CHOICES = (
    LEGACY_WEIGHTED,
    LEGACY_UNWEIGHTED,
    SIMPLE_SEMANTIC_WEIGHTED,
    SIMPLE_SEMANTIC_UNWEIGHTED,
)

LEGACY_DATA_SCHEMA = "legacy_boe72_boe77"
PROXY_DATA_SCHEMA_2024 = "proxy_qbe22b_be22bb"

_VALID_BOE72_CODES = frozenset({1, 2, 3, 4, 5, 6, 7, 8})
_PROXY_CONCERN_INCLUDE = frozenset({1, 2})


@dataclass(frozen=True)
class MethodSpec:
    method_name: str
    weighted: bool
    classifier: str


@dataclass
class ParseStats:
    total_rows: int = 0
    rows_missing_required: int = 0
    rows_invalid_screen: int = 0
    rows_filtered_screen: int = 0
    rows_invalid_flags: int = 0
    rows_invalid_weight: int = 0
    rows_used: int = 0


@dataclass
class AggregationResult:
    method_name: str
    weighted: bool
    classifier: str
    data_schema: str
    denominator_rows: int
    denominator_weight: float
    income_probability: float
    capital_probability: float
    mixed_probability: float
    income_rows: int
    capital_rows: int
    mixed_rows: int
    income_weight: float
    capital_weight: float
    mixed_weight: float
    parse_stats: ParseStats


METHOD_SPECS: dict[str, MethodSpec] = {
    LEGACY_WEIGHTED: MethodSpec(
        method_name=LEGACY_WEIGHTED,
        weighted=True,
        classifier="legacy",
    ),
    LEGACY_UNWEIGHTED: MethodSpec(
        method_name=LEGACY_UNWEIGHTED,
        weighted=False,
        classifier="legacy",
    ),
    SIMPLE_SEMANTIC_WEIGHTED: MethodSpec(
        method_name=SIMPLE_SEMANTIC_WEIGHTED,
        weighted=True,
        classifier="simple_semantic",
    ),
    SIMPLE_SEMANTIC_UNWEIGHTED: MethodSpec(
        method_name=SIMPLE_SEMANTIC_UNWEIGHTED,
        weighted=False,
        classifier="simple_semantic",
    ),
}


def method_uses_weights(method_name: str) -> bool:
    """Return whether a method uses survey weights."""
    return get_method_spec(method_name).weighted


def get_method_spec(method_name: str) -> MethodSpec:
    """Return method metadata or fail with a clear error."""
    spec = METHOD_SPECS.get(method_name)
    if spec is None:
        choices = ", ".join(METHOD_CHOICES)
        raise ValueError(f"Unsupported method: {method_name}. Choices: {choices}.")
    return spec


def _has_legacy_schema(header: Sequence[str], columns: object) -> bool:
    lookup = set(header)
    if columns.weight not in lookup:
        return False
    if columns.btl_owner_screen not in lookup:
        return False
    return all(name in lookup for name in columns.boe77_option_columns)


def _has_proxy_schema(header: Sequence[str], columns: object) -> bool:
    lookup = set(header)
    if columns.weight not in lookup:
        return False
    if columns.proxy_concern_column not in lookup:
        return False
    return all(name in lookup for name in columns.proxy_reason_columns)


def detect_data_schema(header: Sequence[str], columns: object) -> str:
    """Detect supported BTL strategy schema from CSV header."""
    if _has_legacy_schema(header, columns):
        return LEGACY_DATA_SCHEMA
    if _has_proxy_schema(header, columns):
        return PROXY_DATA_SCHEMA_2024

    legacy_requirements = [columns.weight, columns.btl_owner_screen, *columns.boe77_option_columns]
    proxy_requirements = [columns.weight, columns.proxy_concern_column, *columns.proxy_reason_columns]
    raise ValueError(
        "Missing required columns for known BTL strategy schemas. "
        f"Legacy requires: {', '.join(legacy_requirements)}. "
        f"2024 proxy requires: {', '.join(proxy_requirements)}."
    )


def validate_required_columns(header: Sequence[str], columns: object) -> None:
    """Validate that at least one supported schema exists in the input header."""
    detect_data_schema(header, columns)


def _parse_binary_flags(
    row: dict[str, str],
    column_names: Sequence[str],
) -> dict[int, bool] | None:
    flags: dict[int, bool] = {}
    for idx, name in enumerate(column_names, start=1):
        value = parse_int(row.get(name))
        if value not in {0, 1}:
            return None
        flags[idx] = bool(value)
    return flags


def _classify_legacy(flags: dict[int, bool]) -> str:
    is_capital = flags[1] and not any(flags[idx] for idx in (2, 3, 4, 5, 6, 7))
    if is_capital:
        return "capital"

    is_income = (flags[4] or flags[5]) and (not flags[1]) and (not flags[3])
    if is_income:
        return "income"

    return "mixed"


def _classify_simple_semantic_legacy(flags: dict[int, bool]) -> str:
    if flags[4] and (not flags[1]):
        return "income"
    if flags[1] and (not flags[4]):
        return "capital"
    return "mixed"


def _classify_proxy_legacy_style(flags: dict[int, bool]) -> str:
    # 2024 proxy for strategy using debt-concern reason flags.
    # income proxy: current/income-related repayment pressure.
    # capital proxy: concern about repayment increases from interest-rate changes.
    income_signal = flags[1] or flags[2] or flags[4]
    capital_signal = flags[3]

    if capital_signal and (not income_signal):
        return "capital"
    if income_signal and (not capital_signal):
        return "income"
    return "mixed"


def _classify_proxy_simple_semantic(flags: dict[int, bool]) -> str:
    if flags[1] and (not flags[3]):
        return "income"
    if flags[3] and (not flags[1]):
        return "capital"
    return "mixed"


def classify_row(flags: dict[int, bool], classifier: str, data_schema: str = LEGACY_DATA_SCHEMA) -> str:
    """Classify one respondent as income/capital/mixed."""
    if data_schema == LEGACY_DATA_SCHEMA:
        if classifier == "legacy":
            return _classify_legacy(flags)
        if classifier == "simple_semantic":
            return _classify_simple_semantic_legacy(flags)
    elif data_schema == PROXY_DATA_SCHEMA_2024:
        if classifier == "legacy":
            return _classify_proxy_legacy_style(flags)
        if classifier == "simple_semantic":
            return _classify_proxy_simple_semantic(flags)

    raise ValueError(f"Unsupported classifier/schema combination: {classifier}/{data_schema}")


def aggregate_probabilities(
    rows: Sequence[dict[str, str]],
    columns: object,
    method_name: str,
) -> AggregationResult:
    """Aggregate BTL strategy probabilities for a selected method."""
    if not rows:
        raise ValueError("Input rows are empty; cannot calibrate strategy probabilities.")

    spec = get_method_spec(method_name)
    data_schema = detect_data_schema(list(rows[0].keys()), columns)
    parse_stats = ParseStats()

    denominator_rows = 0
    denominator_weight = 0.0

    income_rows = 0
    capital_rows = 0
    mixed_rows = 0
    income_weight = 0.0
    capital_weight = 0.0
    mixed_weight = 0.0

    for row in rows:
        parse_stats.total_rows += 1

        if columns.weight not in row:
            parse_stats.rows_missing_required += 1
            continue

        if data_schema == LEGACY_DATA_SCHEMA:
            if columns.btl_owner_screen not in row or any(
                name not in row for name in columns.boe77_option_columns
            ):
                parse_stats.rows_missing_required += 1
                continue

            boe72 = parse_int(row.get(columns.btl_owner_screen))
            if boe72 not in _VALID_BOE72_CODES:
                parse_stats.rows_invalid_screen += 1
                continue

            flags = _parse_binary_flags(row, columns.boe77_option_columns)
            if flags is None:
                parse_stats.rows_invalid_flags += 1
                continue
        else:
            if columns.proxy_concern_column not in row or any(
                name not in row for name in columns.proxy_reason_columns
            ):
                parse_stats.rows_missing_required += 1
                continue

            concern = parse_int(row.get(columns.proxy_concern_column))
            if concern not in _PROXY_CONCERN_INCLUDE:
                parse_stats.rows_filtered_screen += 1
                continue

            flags = _parse_binary_flags(row, columns.proxy_reason_columns)
            if flags is None:
                parse_stats.rows_invalid_flags += 1
                continue

        weight = parse_float(row.get(columns.weight))
        if spec.weighted:
            if weight is None or weight <= 0:
                parse_stats.rows_invalid_weight += 1
                continue
            observation_weight = weight
        else:
            observation_weight = 1.0

        label = classify_row(flags, spec.classifier, data_schema=data_schema)
        if label == "income":
            income_rows += 1
            income_weight += observation_weight
        elif label == "capital":
            capital_rows += 1
            capital_weight += observation_weight
        else:
            mixed_rows += 1
            mixed_weight += observation_weight

        parse_stats.rows_used += 1
        denominator_rows += 1
        denominator_weight += observation_weight

    if denominator_weight <= 0:
        raise ValueError(
            "No valid rows for selected method. Check required columns and filters."
        )

    income_probability = income_weight / denominator_weight
    capital_probability = capital_weight / denominator_weight
    mixed_probability = mixed_weight / denominator_weight

    return AggregationResult(
        method_name=spec.method_name,
        weighted=spec.weighted,
        classifier=spec.classifier,
        data_schema=data_schema,
        denominator_rows=denominator_rows,
        denominator_weight=denominator_weight,
        income_probability=income_probability,
        capital_probability=capital_probability,
        mixed_probability=mixed_probability,
        income_rows=income_rows,
        capital_rows=capital_rows,
        mixed_rows=mixed_rows,
        income_weight=income_weight,
        capital_weight=capital_weight,
        mixed_weight=mixed_weight,
        parse_stats=parse_stats,
    )


__all__ = [
    "AggregationResult",
    "LEGACY_DATA_SCHEMA",
    "LEGACY_UNWEIGHTED",
    "LEGACY_WEIGHTED",
    "METHOD_CHOICES",
    "METHOD_SPECS",
    "PROXY_DATA_SCHEMA_2024",
    "ParseStats",
    "SIMPLE_SEMANTIC_UNWEIGHTED",
    "SIMPLE_SEMANTIC_WEIGHTED",
    "aggregate_probabilities",
    "classify_row",
    "detect_data_schema",
    "get_method_spec",
    "method_uses_weights",
    "validate_required_columns",
]
