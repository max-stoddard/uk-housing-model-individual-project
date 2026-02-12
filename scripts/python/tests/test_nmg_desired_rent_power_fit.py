from __future__ import annotations

import csv
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.python.calibration.nmg.nmg_desired_rent_power_fit import build_arg_parser
from scripts.python.helpers.nmg.columns import DesiredRentColumnNames
from scripts.python.helpers.nmg.fitting import HAVE_SCIPY, fit_log_weighted
from scripts.python.helpers.nmg.observations import get_income_from_row, get_rent_from_row


class TestNmgDesiredRentPowerFit(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.module_name = "scripts.python.calibration.nmg.nmg_desired_rent_power_fit"
        cls.columns = DesiredRentColumnNames()

    def _run_script(self, csv_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
        command = ["python3", "-m", self.module_name, str(csv_path), *args]
        return subprocess.run(
            command,
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def _write_csv(self, header: list[str], rows: list[list[object]]) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8")
        with handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return Path(handle.name)

    def test_parser_defaults(self) -> None:
        args = build_arg_parser().parse_args(["dummy.csv"])
        self.assertEqual(args.qhousing_values, "3,4,5")
        self.assertEqual(args.income_source, "incomev2comb_mid")
        self.assertEqual(args.rent_source, "spq07_mid")
        self.assertEqual(args.fit_method, "log_weighted")

    def test_midpoint_mapping(self) -> None:
        row = {"incomev2comb": "11", "spq07": "11", "SPQ07free_1": ""}
        income = get_income_from_row(row, "incomev2comb_mid", self.columns)
        rent = get_rent_from_row(row, "spq07_mid", self.columns, "SPQ07free_1")
        self.assertEqual(income, 21250.0)
        self.assertEqual(rent, 575.0)

    def test_log_weighted_fit_recovers_exact_power_law(self) -> None:
        scale_true = 12.5
        exponent_true = 0.42
        x = np.asarray([12000.0, 22000.0, 34000.0, 48000.0], dtype=float)
        y = scale_true * np.power(x, exponent_true)
        w = np.asarray([1.0, 1.5, 0.8, 2.0], dtype=float)
        scale, exponent = fit_log_weighted(x, y, w)
        self.assertAlmostEqual(scale, scale_true, places=10)
        self.assertAlmostEqual(exponent, exponent_true, places=10)

    @unittest.skipUnless(HAVE_SCIPY, "nls_weighted requires SciPy")
    def test_explicit_old_mode_still_works_and_prints_schema(self) -> None:
        csv_path = self._write_csv(
            ["qhousing", "we_factor", "incomev2comb", "spq07"],
            [
                [3, 1.0, 11, 11],
                [4, 1.0, 12, 12],
                [5, 1.0, 13, 13],
                [4, 1.0, 14, 14],
            ],
        )
        try:
            result = self._run_script(
                csv_path,
                "--qhousing-values",
                "3,4,5",
                "--income-source",
                "incomev2comb_upper",
                "--rent-source",
                "spq07_upper",
                "--fit-method",
                "nls_weighted",
            )
        finally:
            csv_path.unlink(missing_ok=True)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("DESIRED_RENT_SCALE =", result.stdout)
        self.assertIn("DESIRED_RENT_EXPONENT =", result.stdout)

    @unittest.skipUnless(HAVE_SCIPY, "nls_weighted requires SciPy")
    def test_nls_mode_prints_level_space_warning(self) -> None:
        csv_path = self._write_csv(
            ["qhousing", "we_factor", "incomev2comb", "spq07"],
            [
                [3, 1.0, 11, 11],
                [4, 1.0, 12, 12],
                [5, 1.0, 13, 13],
                [4, 1.0, 14, 14],
            ],
        )
        try:
            result = self._run_script(csv_path, "--fit-method", "nls_weighted")
        finally:
            csv_path.unlink(missing_ok=True)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("fit objective: weighted level-space NLS", result.stdout)
        self.assertIn("can overweight high-rent observations", result.stdout)

    def test_missing_required_columns_fails_fast(self) -> None:
        csv_path = self._write_csv(["foo", "bar"], [[1, 2], [3, 4], [5, 6]])
        try:
            result = self._run_script(csv_path)
        finally:
            csv_path.unlink(missing_ok=True)

        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertIn("Missing required columns", combined)


if __name__ == "__main__":
    unittest.main()
