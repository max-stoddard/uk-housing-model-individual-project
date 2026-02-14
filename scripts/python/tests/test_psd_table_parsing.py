from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.python.helpers.psd.tables import (
    get_labeled_section_rows,
    get_year_column,
    load_psd_table,
)


class TestPsdTableParsing(unittest.TestCase):
    def _write_csv(self, rows: list[list[object]]) -> Path:
        handle = tempfile.NamedTemporaryFile(
            "w",
            suffix=".csv",
            delete=False,
            newline="",
            encoding="utf-8",
        )
        with handle:
            writer = csv.writer(handle)
            writer.writerows(rows)
        return Path(handle.name)

    def test_section_detection_and_year_column_resolution(self) -> None:
        csv_path = self._write_csv(
            [
                ["", "PSD"],
                ["", "", "", "Reporting Periods"],
                ["", "", "", "2010", "2011", "2012", "2011-Q1"],
                ["3.7.1", "Single income bins"],
                ["", "< 2.5", "", "1.0", "2.0", "3.0", "0.4"],
                ["", "2.5 to 3.49", "", "3.0", "4.0", "5.0", "1.1"],
                ["3.7.2", "Joint income bins"],
                ["", "< 2.5", "", "9.0", "8.0", "7.0", "2.0"],
                ["", ">5.5", "", "5.0", "4.0", "3.0", "1.0"],
                ["6.3", "FTB LTV bins"],
                ["", "90% - 95%", "", "4.0", "5.0", "6.0", "1.5"],
                ["", "95% +", "", "2.0", "3.0", "4.0", "0.6"],
                ["6.4", "FTB property bins"],
                ["", "£0K - £60K", "", "1.0", "2.0", "3.0", "0.4"],
                ["", "£1M +", "", "0.1", "0.2", "0.3", "0.05"],
            ]
        )
        try:
            table = load_psd_table(csv_path)
            year_column = get_year_column(table, 2011)
            rows_371 = get_labeled_section_rows(table, "3.7.1")
            rows_372 = get_labeled_section_rows(table, "3.7.2")
            rows_63 = get_labeled_section_rows(table, "6.3")
            rows_64 = get_labeled_section_rows(table, "6.4")
        finally:
            csv_path.unlink(missing_ok=True)

        self.assertEqual(year_column, 4)
        self.assertEqual([label for label, _ in rows_371], ["< 2.5", "2.5 to 3.49"])
        self.assertEqual([label for label, _ in rows_372], ["< 2.5", ">5.5"])
        self.assertEqual([label for label, _ in rows_63], ["90% - 95%", "95% +"])
        self.assertEqual([label for label, _ in rows_64], ["£0K - £60K", "£1M +"])

    def test_missing_year_fails_fast(self) -> None:
        csv_path = self._write_csv(
            [
                ["", "PSD"],
                ["", "", "", "2010", "2012", "2012-Q1", "2012-Q2"],
                ["3.7.1", "Single income bins"],
                ["", "< 2.5", "", "1.0", "2.0", "0.5", "0.6"],
            ]
        )
        try:
            table = load_psd_table(csv_path)
            with self.assertRaises(ValueError):
                get_year_column(table, 2011)
        finally:
            csv_path.unlink(missing_ok=True)

    def test_missing_section_fails_fast(self) -> None:
        csv_path = self._write_csv(
            [
                ["", "PSD"],
                ["", "", "", "2011", "2012", "2011-Q1", "2011-Q2"],
                ["3.4", "LTV"],
                ["", "0% - 30%", "", "1.0", "2.0", "0.2", "0.3"],
            ]
        )
        try:
            table = load_psd_table(csv_path)
            with self.assertRaises(ValueError):
                get_labeled_section_rows(table, "3.7.1")
        finally:
            csv_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
