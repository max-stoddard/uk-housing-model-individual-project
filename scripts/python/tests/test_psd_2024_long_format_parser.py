from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.python.helpers.psd.quarterly_long import (
    load_long_psd_rows,
    parse_period_token,
)


class TestPsd2024LongFormatParser(unittest.TestCase):
    def _write_csv(self, header: list[str], rows: list[list[object]]) -> Path:
        handle = tempfile.NamedTemporaryFile(
            "w",
            suffix=".csv",
            delete=False,
            newline="",
            encoding="utf-8",
        )
        with handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return Path(handle.name)

    def test_trimmed_headers_and_currency_normalization(self) -> None:
        csv_path = self._write_csv(
            ["Mortgages Grouped By", "Category", "Postcode Region", "Date", "Number of Sales "],
            [
                ["Number of sales by loan amount bands", "�0 - �50,000", "East Midlands", "2024 Q1", "10"],
                ["Number of sales by loan amount bands", "�50,001 - �120,000", "East Midlands", "2024 Q1", "20"],
                ["", "", "", "", ""],
            ],
        )
        try:
            rows = load_long_psd_rows(
                csv_path,
                group_column="Mortgages Grouped By",
                category_column="Category",
                period_column="Date",
                sales_column="Number of Sales",
                region_column="Postcode Region",
            )
        finally:
            csv_path.unlink(missing_ok=True)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].category, "£0 - £50,000")
        self.assertEqual(rows[0].sales, 10.0)

    def test_malformed_tail_rows_are_ignored(self) -> None:
        csv_path = self._write_csv(
            ["Category", "Account Open Date", "Number of Sales "],
            [
                ["First time buyer", "January 2024", "100"],
                ["", "", ""],
                ["Home movers/second or subsequent buyers", "nonsense", "200"],
                ["Other", "February 2024", "not-a-number"],
            ],
        )
        try:
            rows = load_long_psd_rows(
                csv_path,
                group_column=None,
                category_column="Category",
                period_column="Account Open Date",
                sales_column="Number of Sales",
                region_column=None,
            )
        finally:
            csv_path.unlink(missing_ok=True)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].category, "First time buyer")
        self.assertEqual(rows[0].period.month, 1)

    def test_missing_required_column_fails_fast(self) -> None:
        csv_path = self._write_csv(
            ["Category", "Date", "Number of Sales"],
            [["x", "2024 Q1", "1"]],
        )
        try:
            with self.assertRaises(ValueError):
                load_long_psd_rows(
                    csv_path,
                    group_column="Mortgages Grouped By",
                    category_column="Category",
                    period_column="Date",
                    sales_column="Number of Sales",
                    region_column="Postcode Region",
                )
        finally:
            csv_path.unlink(missing_ok=True)

    def test_period_parser_supports_quarter_and_month_tokens(self) -> None:
        quarter = parse_period_token("2024 Q4")
        month = parse_period_token("September 2024")
        self.assertEqual((quarter.year, quarter.quarter, quarter.month), (2024, 4, None))
        self.assertEqual((month.year, month.quarter, month.month), (2024, None, 9))


if __name__ == "__main__":
    unittest.main()
