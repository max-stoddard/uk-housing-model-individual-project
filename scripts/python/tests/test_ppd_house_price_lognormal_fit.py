from __future__ import annotations

import csv
import math
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.python.calibration.ppd.house_price_lognormal_fit import (
    METHOD_FOCUSED_REPRO_DEFAULT,
    METHOD_LEGACY_SAMPLE_ALL,
    build_arg_parser,
    compute_parameters,
)


class TestPpdHousePriceLognormalFit(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.module_name = "scripts.python.calibration.ppd.house_price_lognormal_fit"

    def _run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = ["python3", "-m", self.module_name, *args]
        return subprocess.run(
            command,
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def _write_ppd_csv(self, rows: list[list[object]]) -> Path:
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

    def test_parser_defaults(self) -> None:
        args = build_arg_parser().parse_args(["dummy.csv"])
        self.assertEqual(args.method, METHOD_FOCUSED_REPRO_DEFAULT)
        self.assertEqual(args.target_year, 2024)
        self.assertEqual(args.price_index, 1)
        self.assertEqual(args.skip_rows, 0)

    def test_legacy_sample_all_reproduces_old_path(self) -> None:
        csv_path = self._write_ppd_csv(
            [
                ["id1", "100", "2011-01-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
                ["id2", "200", "2011-01-02 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "D"],
                ["id3", "400", "2011-01-03 00:00", "", "", "", "", "", "", "", "", "", "", "", "B", "A"],
            ]
        )
        try:
            stats, parse_stats = compute_parameters(
                [csv_path],
                price_index=1,
                delimiter=",",
                skip_rows=0,
                method=METHOD_LEGACY_SAMPLE_ALL,
                target_year=2024,
            )
        finally:
            csv_path.unlink(missing_ok=True)

        self.assertEqual(parse_stats.used_rows, 3)
        expected_logs = [math.log(100.0), math.log(200.0), math.log(400.0)]
        mean = sum(expected_logs) / 3
        sigma_sample = math.sqrt(sum((x - mean) ** 2 for x in expected_logs) / 2)
        self.assertAlmostEqual(stats.mean, mean, places=12)
        self.assertAlmostEqual(stats.std(std_mode="sample"), sigma_sample, places=12)

    def test_focused_default_filters_non_a_status(self) -> None:
        csv_path = self._write_ppd_csv(
            [
                ["id1", "100", "2024-01-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
                ["id2", "200", "2024-01-02 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "D"],
                ["id3", "400", "2024-01-03 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
            ]
        )
        try:
            stats, parse_stats = compute_parameters(
                [csv_path],
                price_index=1,
                delimiter=",",
                skip_rows=0,
                method=METHOD_FOCUSED_REPRO_DEFAULT,
                target_year=2024,
            )
        finally:
            csv_path.unlink(missing_ok=True)

        self.assertEqual(parse_stats.valid_price_rows, 3)
        self.assertEqual(parse_stats.filtered_non_a_status_rows, 1)
        self.assertEqual(parse_stats.used_rows, 2)
        expected_logs = [math.log(100.0), math.log(400.0)]
        mean = sum(expected_logs) / 2
        sigma_pop = math.sqrt(sum((x - mean) ** 2 for x in expected_logs) / 2)
        self.assertAlmostEqual(stats.mean, mean, places=12)
        self.assertAlmostEqual(stats.std(std_mode="population"), sigma_pop, places=12)

    def test_population_vs_sample_std_difference(self) -> None:
        csv_path = self._write_ppd_csv(
            [
                ["id1", "100", "2024-01-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
                ["id2", "200", "2024-01-02 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
                ["id3", "400", "2024-01-03 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
            ]
        )
        try:
            stats, _ = compute_parameters(
                [csv_path],
                price_index=1,
                delimiter=",",
                skip_rows=0,
                method=METHOD_FOCUSED_REPRO_DEFAULT,
                target_year=2024,
            )
        finally:
            csv_path.unlink(missing_ok=True)

        sigma_pop = stats.std(std_mode="population")
        sigma_sample = stats.std(std_mode="sample")
        self.assertGreater(sigma_sample, sigma_pop)

    def test_missing_file_fails_fast(self) -> None:
        result = self._run_script("/tmp/definitely-not-there-ppd.csv")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing files", result.stderr + result.stdout)

    def test_empty_valid_sample_fails_fast(self) -> None:
        csv_path = self._write_ppd_csv(
            [
                ["id1", "100", "2024-01-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "D"],
                ["id2", "200", "2024-01-02 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "D"],
            ]
        )
        try:
            result = self._run_script(str(csv_path))
        finally:
            csv_path.unlink(missing_ok=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No valid prices found", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
