"""Parsing helpers for semi-structured PSD mortgage CSV tables."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

SECTION_ID_RE = re.compile(r"^\d+\.\d+(?:\.\d+)?$")
PERIOD_TOKEN_RE = re.compile(r"^\d{4}(?:-Q[1-4])?$")


@dataclass(frozen=True)
class PsdTable:
    """A loaded PSD table with a detected period-header row."""

    path: Path
    rows: list[list[str]]
    period_row_index: int
    period_columns: dict[str, int]



def _normalise_cell(value: str) -> str:
    return value.strip()



def _detect_period_row(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    for row_index, row in enumerate(rows):
        period_columns: dict[str, int] = {}
        for column_index, raw in enumerate(row):
            token = _normalise_cell(raw)
            if PERIOD_TOKEN_RE.match(token):
                period_columns.setdefault(token, column_index)
        if len(period_columns) >= 4:
            return row_index, period_columns
    raise ValueError("Could not detect PSD period header row.")



def load_psd_table(path: Path | str) -> PsdTable:
    """Load a PSD CSV table and detect the period-header row."""
    csv_path = Path(path)
    if not csv_path.exists():
        raise ValueError(f"Missing PSD CSV: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="", errors="replace") as handle:
        rows = list(csv.reader(handle))

    if not rows:
        raise ValueError(f"PSD CSV has no rows: {csv_path}")

    period_row_index, period_columns = _detect_period_row(rows)
    return PsdTable(
        path=csv_path,
        rows=rows,
        period_row_index=period_row_index,
        period_columns=period_columns,
    )



def get_year_column(table: PsdTable, target_year: int | str) -> int:
    """Resolve the annual-column index for a given year token."""
    year_token = str(target_year)
    if year_token not in table.period_columns:
        available = ", ".join(sorted(table.period_columns.keys()))
        raise ValueError(
            f"Year {year_token} not found in period row for {table.path}. "
            f"Available period tokens: {available}"
        )
    return table.period_columns[year_token]



def _find_section_index(table: PsdTable, section_id: str) -> int:
    for row_index, row in enumerate(table.rows):
        if not row:
            continue
        token = _normalise_cell(row[0]) if len(row) > 0 else ""
        if token == section_id:
            return row_index
    raise ValueError(f"Section {section_id} not found in {table.path}")



def iter_section_rows(table: PsdTable, section_id: str) -> list[list[str]]:
    """Return raw rows contained inside one numeric PSD section."""
    start_index = _find_section_index(table, section_id) + 1
    output: list[list[str]] = []
    for row in table.rows[start_index:]:
        section_token = _normalise_cell(row[0]) if len(row) > 0 else ""
        if section_token and SECTION_ID_RE.match(section_token):
            break
        output.append(row)
    return output



def get_labeled_section_rows(table: PsdTable, section_id: str) -> list[tuple[str, list[str]]]:
    """Return non-empty label rows for a given section.

    Labels are read from column index 1 in PSD tables.
    """
    labeled_rows: list[tuple[str, list[str]]] = []
    for row in iter_section_rows(table, section_id):
        label = _normalise_cell(row[1]) if len(row) > 1 else ""
        if label:
            labeled_rows.append((label, row))
    return labeled_rows



def parse_numeric_cell(row: list[str], column_index: int) -> float | None:
    """Parse a numeric value from one row cell, returning None when missing."""
    if column_index >= len(row):
        return None
    raw = _normalise_cell(row[column_index])
    if not raw or raw == "N/A":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


__all__ = [
    "PsdTable",
    "get_labeled_section_rows",
    "get_year_column",
    "iter_section_rows",
    "load_psd_table",
    "parse_numeric_cell",
]
