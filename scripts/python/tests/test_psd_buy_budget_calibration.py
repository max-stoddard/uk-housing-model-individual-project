from __future__ import annotations

import csv
import math
import tempfile
import unittest
from pathlib import Path

from scripts.python.calibration.psd.psd_buy_budget_calibration import build_arg_parser
from scripts.python.helpers.psd.buy_budget_methods import (
    DEFAULT_SELECTED_METHOD,
    run_modern_calibration,
)


class TestPsdBuyBudgetCalibration(unittest.TestCase):
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

    def _synthetic_quarterly(self) -> Path:
        header = ["Mortgages Grouped By", "Category", "Postcode Region", "Date", "Number of Sales"]
        rows = [
            ["Number of sales by gross income bands", "£0 - £50,000", "East Midlands", "2024 Q1", "120"],
            ["Number of sales by gross income bands", "£50,001 - £100,000", "East Midlands", "2024 Q1", "80"],
            ["Number of sales by gross income bands", "£100,001 +", "East Midlands", "2024 Q1", "20"],
            ["Number of sales by property value bands", "£0 - £120,000", "East Midlands", "2024 Q1", "70"],
            ["Number of sales by property value bands", "£120,001 - £250,000", "East Midlands", "2024 Q1", "90"],
            ["Number of sales by property value bands", "£250,001 +", "East Midlands", "2024 Q1", "60"],
            ["Number of sales by loan amount bands", "£0 - £50,000", "East Midlands", "2024 Q1", "50"],
            ["Number of sales by loan-to-value (LTV) ratio", ">90% - <=95%", "East Midlands", "2024 Q1", "10"],
            ["Number of sales by type of borrower", "First time buyer", "East Midlands", "2024 Q1", "90"],
        ]
        return self._write_csv([header, *rows])

    def _synthetic_ppd(self) -> Path:
        return self._write_csv(
            [
                ["id1", "180000", "2025-01-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
                ["id2", "220000", "2025-02-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
                ["id3", "350000", "2025-03-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
                ["id4", "500000", "2025-04-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
            ]
        )

    def test_parser_defaults(self) -> None:
        args = build_arg_parser().parse_args([])
        self.assertEqual(args.target_year_psd, 2024)
        self.assertEqual(args.target_year_ppd, 2025)
        self.assertEqual(args.method, DEFAULT_SELECTED_METHOD.method_id)
        self.assertIn("family=psd_log_ols_robust_mu", args.method)
        self.assertIn("mu_hi_trim=0.0063", args.method)

    def test_modern_calibration_with_synthetic_rows(self) -> None:
        quarterly_path = self._synthetic_quarterly()
        ppd_path = self._synthetic_ppd()
        try:
            output = run_modern_calibration(
                quarterly_csv=quarterly_path,
                ppd_csv=ppd_path,
                target_year_psd=2024,
                target_year_ppd=2025,
                method=DEFAULT_SELECTED_METHOD,
            )
        finally:
            quarterly_path.unlink(missing_ok=True)
            ppd_path.unlink(missing_ok=True)

        self.assertTrue(math.isfinite(output.buy_scale))
        self.assertTrue(math.isfinite(output.buy_exponent))
        self.assertTrue(math.isfinite(output.buy_mu))
        self.assertTrue(math.isfinite(output.buy_sigma))
        self.assertGreater(output.diagnostics.paired_sample_size, 0)
        self.assertIn("income_bins", output.modern_diagnostics)
        self.assertIn("property_bins", output.modern_diagnostics)

    def test_fail_fast_when_modern_income_group_missing(self) -> None:
        quarterly_path = self._write_csv(
            [
                ["Mortgages Grouped By", "Category", "Postcode Region", "Date", "Number of Sales"],
                ["Number of sales by property value bands", "£0 - £120,000", "East Midlands", "2024 Q1", "10"],
            ]
        )
        ppd_path = self._synthetic_ppd()
        try:
            with self.assertRaisesRegex(ValueError, "Missing modern income group"):
                run_modern_calibration(
                    quarterly_csv=quarterly_path,
                    ppd_csv=ppd_path,
                    target_year_psd=2024,
                    target_year_ppd=2025,
                    method=DEFAULT_SELECTED_METHOD,
                )
        finally:
            quarterly_path.unlink(missing_ok=True)
            ppd_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
