"""Helpers for parsing long-format PSD CSV extracts (quarterly/monthly)."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


_SPACE_RE = re.compile(r"\s+")
_QUARTER_RE = re.compile(r"^(\d{4})\s*Q([1-4])$")
_MONTH_RE = re.compile(r"^([A-Za-z]+)\s+(\d{4})$")
_MONTH_INDEX = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass(frozen=True)
class PsdPeriod:
    """Parsed period token from long-format PSD files."""

    label: str
    year: int
    quarter: int | None
    month: int | None

    @property
    def sort_key(self) -> tuple[int, int]:
        if self.quarter is not None:
            return self.year, self.quarter
        if self.month is not None:
            return self.year, self.month
        return self.year, 0


@dataclass(frozen=True)
class LongPsdRow:
    """One normalized row from a long-format PSD CSV."""

    group: str
    category: str
    region: str
    period: PsdPeriod
    sales: float


def normalise_text(value: str | None) -> str:
    if value is None:
        return ""
    text = value.replace("\ufeff", "").replace("�", "£").strip()
    return _SPACE_RE.sub(" ", text)


def parse_period_token(token: str) -> PsdPeriod:
    text = normalise_text(token)
    quarter_match = _QUARTER_RE.match(text)
    if quarter_match:
        return PsdPeriod(
            label=text,
            year=int(quarter_match.group(1)),
            quarter=int(quarter_match.group(2)),
            month=None,
        )

    month_match = _MONTH_RE.match(text)
    if month_match:
        month_name = month_match.group(1).lower()
        if month_name not in _MONTH_INDEX:
            raise ValueError(f"Unrecognized month token: {text}")
        return PsdPeriod(
            label=text,
            year=int(month_match.group(2)),
            quarter=None,
            month=_MONTH_INDEX[month_name],
        )

    raise ValueError(f"Unsupported period token: {token!r}")


def _resolve_column(header_map: dict[str, str], required_name: str | None) -> str | None:
    if required_name is None:
        return None
    normalized_name = normalise_text(required_name)
    if normalized_name not in header_map:
        available = ", ".join(sorted(header_map.keys()))
        raise ValueError(
            f"Missing required column '{required_name}'. "
            f"Available columns: {available}"
        )
    return header_map[normalized_name]


def load_long_psd_rows(
    path: Path | str,
    *,
    group_column: str | None,
    category_column: str,
    period_column: str,
    sales_column: str,
    region_column: str | None,
) -> list[LongPsdRow]:
    """Load long-format PSD rows with normalized headers and text fields."""
    csv_path = Path(path)
    if not csv_path.exists():
        raise ValueError(f"Missing PSD CSV: {csv_path}")

    rows: list[LongPsdRow] = []
    with csv_path.open("r", encoding="utf-8", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Input CSV has no header row: {csv_path}")

        header_map = {
            normalise_text(field): field
            for field in reader.fieldnames
            if field is not None
        }
        group_key = _resolve_column(header_map, group_column)
        category_key = _resolve_column(header_map, category_column)
        period_key = _resolve_column(header_map, period_column)
        sales_key = _resolve_column(header_map, sales_column)
        region_key = _resolve_column(header_map, region_column)
        assert category_key is not None
        assert period_key is not None
        assert sales_key is not None

        for raw_row in reader:
            normalized_row = {
                normalise_text(key): normalise_text(value)
                for key, value in raw_row.items()
                if key is not None
            }
            if not any(normalized_row.values()):
                continue

            group_value = normalized_row.get(normalise_text(group_key), "") if group_key else ""
            category_value = normalized_row.get(normalise_text(category_key), "")
            period_value = normalized_row.get(normalise_text(period_key), "")
            sales_value = normalized_row.get(normalise_text(sales_key), "")
            region_value = (
                normalized_row.get(normalise_text(region_key), "ALL")
                if region_key
                else "ALL"
            )

            if not category_value or not period_value or not sales_value:
                continue

            try:
                period = parse_period_token(period_value)
            except ValueError:
                continue

            try:
                sales = float(sales_value)
            except ValueError:
                continue

            rows.append(
                LongPsdRow(
                    group=group_value,
                    category=category_value,
                    region=region_value if region_value else "ALL",
                    period=period,
                    sales=sales,
                )
            )

    if not rows:
        raise ValueError(f"No usable rows parsed from: {csv_path}")
    return rows


def load_quarterly_psd_rows(path: Path | str) -> list[LongPsdRow]:
    return load_long_psd_rows(
        path,
        group_column="Mortgages Grouped By",
        category_column="Category",
        period_column="Date",
        sales_column="Number of Sales",
        region_column="Postcode Region",
    )


def load_monthly_psd_rows(path: Path | str) -> list[LongPsdRow]:
    return load_long_psd_rows(
        path,
        group_column=None,
        category_column="Category",
        period_column="Account Open Date",
        sales_column="Number of Sales",
        region_column=None,
    )


def aggregate_category_sales(
    rows: list[LongPsdRow],
    *,
    group: str,
    year: int,
    quarter: int | None = None,
) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        if row.group != group:
            continue
        if row.period.year != year:
            continue
        if quarter is not None and row.period.quarter != quarter:
            continue
        totals[row.category] = totals.get(row.category, 0.0) + row.sales
    return totals


def aggregate_category_sales_by_period(
    rows: list[LongPsdRow],
    *,
    group: str,
    year: int,
) -> dict[str, dict[str, float]]:
    by_period: dict[str, dict[str, float]] = {}
    for row in rows:
        if row.group != group:
            continue
        if row.period.year != year:
            continue
        period_map = by_period.setdefault(row.period.label, {})
        period_map[row.category] = period_map.get(row.category, 0.0) + row.sales
    return by_period


def sum_category_sales(category_sales: dict[str, float]) -> float:
    return sum(category_sales.values())


__all__ = [
    "LongPsdRow",
    "PsdPeriod",
    "aggregate_category_sales",
    "aggregate_category_sales_by_period",
    "load_long_psd_rows",
    "load_monthly_psd_rows",
    "load_quarterly_psd_rows",
    "normalise_text",
    "parse_period_token",
    "sum_category_sales",
]
