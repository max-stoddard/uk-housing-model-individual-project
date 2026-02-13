from __future__ import annotations

import csv
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.python.calibration.nmg.nmg_btl_strategy_probabilities import (
    build_arg_parser,
)
from scripts.python.helpers.nmg.btl_strategy import (
    LEGACY_WEIGHTED,
    aggregate_probabilities,
)
from scripts.python.helpers.nmg.columns import (
    BtlStrategyColumnNames,
    BtlStrategyTargetKeys,
)


class TestNmgBtlStrategyProbabilities(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.module_name = "scripts.python.calibration.nmg.nmg_btl_strategy_probabilities"
        cls.columns = BtlStrategyColumnNames()
        cls.target_keys = BtlStrategyTargetKeys()

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

    def test_parser_defaults(self) -> None:
        args = build_arg_parser().parse_args(["dummy.csv"])
        self.assertEqual(args.method, LEGACY_WEIGHTED)
        self.assertEqual(args.target_year, 2024)

    def test_legacy_classification_weighted_vs_unweighted(self) -> None:
        rows = [
            # income-driven in legacy mapping
            {"we_factor": "2.0", "boe72": "1", "boe77_1": "0", "boe77_2": "0", "boe77_3": "0", "boe77_4": "1", "boe77_5": "0", "boe77_6": "0", "boe77_7": "0"},
            # capital-driven in legacy mapping
            {"we_factor": "1.0", "boe72": "2", "boe77_1": "1", "boe77_2": "0", "boe77_3": "0", "boe77_4": "0", "boe77_5": "0", "boe77_6": "0", "boe77_7": "0"},
            # mixed
            {"we_factor": "3.0", "boe72": "3", "boe77_1": "0", "boe77_2": "1", "boe77_3": "0", "boe77_4": "0", "boe77_5": "0", "boe77_6": "0", "boe77_7": "0"},
        ]
        weighted = aggregate_probabilities(
            rows=rows,
            columns=self.columns,
            method_name="legacy_weighted",
        )
        unweighted = aggregate_probabilities(
            rows=rows,
            columns=self.columns,
            method_name="legacy_unweighted",
        )
        self.assertAlmostEqual(weighted.income_probability, 2.0 / 6.0, places=10)
        self.assertAlmostEqual(weighted.capital_probability, 1.0 / 6.0, places=10)
        self.assertAlmostEqual(weighted.mixed_probability, 3.0 / 6.0, places=10)
        self.assertAlmostEqual(unweighted.income_probability, 1.0 / 3.0, places=10)
        self.assertAlmostEqual(unweighted.capital_probability, 1.0 / 3.0, places=10)
        self.assertAlmostEqual(unweighted.mixed_probability, 1.0 / 3.0, places=10)

    def test_simple_semantic_classification(self) -> None:
        rows = [
            # income (sell, not self-fund)
            {"we_factor": "1.0", "boe72": "1", "boe77_1": "0", "boe77_2": "0", "boe77_3": "0", "boe77_4": "1", "boe77_5": "0", "boe77_6": "0", "boe77_7": "0"},
            # capital (self-fund, not sell)
            {"we_factor": "1.0", "boe72": "1", "boe77_1": "1", "boe77_2": "0", "boe77_3": "0", "boe77_4": "0", "boe77_5": "0", "boe77_6": "0", "boe77_7": "0"},
            # mixed (both selected)
            {"we_factor": "1.0", "boe72": "1", "boe77_1": "1", "boe77_2": "0", "boe77_3": "0", "boe77_4": "1", "boe77_5": "0", "boe77_6": "0", "boe77_7": "0"},
        ]
        result = aggregate_probabilities(
            rows=rows,
            columns=self.columns,
            method_name="simple_semantic_unweighted",
        )
        self.assertAlmostEqual(result.income_probability, 1.0 / 3.0, places=10)
        self.assertAlmostEqual(result.capital_probability, 1.0 / 3.0, places=10)
        self.assertAlmostEqual(result.mixed_probability, 1.0 / 3.0, places=10)

    def test_proxy_2024_schema_is_supported(self) -> None:
        rows = [
            # income proxy signal
            {
                "we_factor": "2.0",
                "qbe22b": "1",
                "be22bb_1": "1",
                "be22bb_2": "0",
                "be22bb_3": "0",
                "be22bb_4": "0",
                "be22bb_5": "0",
                "be22bb_6": "0",
                "be22bb_7": "0",
                "be22bb_8": "0",
                "be22bb_9": "0",
            },
            # capital proxy signal
            {
                "we_factor": "1.0",
                "qbe22b": "2",
                "be22bb_1": "0",
                "be22bb_2": "0",
                "be22bb_3": "1",
                "be22bb_4": "0",
                "be22bb_5": "0",
                "be22bb_6": "0",
                "be22bb_7": "0",
                "be22bb_8": "0",
                "be22bb_9": "0",
            },
            # filtered out (not concerned)
            {
                "we_factor": "5.0",
                "qbe22b": "3",
                "be22bb_1": "0",
                "be22bb_2": "0",
                "be22bb_3": "0",
                "be22bb_4": "0",
                "be22bb_5": "0",
                "be22bb_6": "0",
                "be22bb_7": "0",
                "be22bb_8": "0",
                "be22bb_9": "0",
            },
        ]
        result = aggregate_probabilities(
            rows=rows,
            columns=self.columns,
            method_name="legacy_weighted",
        )
        self.assertEqual(result.data_schema, "proxy_qbe22b_be22bb")
        self.assertAlmostEqual(result.income_probability, 2.0 / 3.0, places=10)
        self.assertAlmostEqual(result.capital_probability, 1.0 / 3.0, places=10)
        self.assertAlmostEqual(result.mixed_probability, 0.0, places=10)

    def test_missing_required_columns_fails_fast(self) -> None:
        csv_path = self._write_csv(["foo", "bar"], [[1, 2], [3, 4]])
        try:
            result = self._run_script(csv_path)
        finally:
            csv_path.unlink(missing_ok=True)
        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertIn("Missing required columns", combined)

    def test_cli_output_contains_expected_keys(self) -> None:
        csv_path = self._write_csv(
            [
                "we_factor",
                "boe72",
                "boe77_1",
                "boe77_2",
                "boe77_3",
                "boe77_4",
                "boe77_5",
                "boe77_6",
                "boe77_7",
            ],
            [
                [1.0, 1, 0, 0, 0, 1, 0, 0, 0],
                [1.0, 1, 1, 0, 0, 0, 0, 0, 0],
                [1.0, 1, 0, 1, 0, 0, 0, 0, 0],
            ],
        )
        try:
            result = self._run_script(csv_path)
        finally:
            csv_path.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn(f"{self.target_keys.income} =", result.stdout)
        self.assertIn(f"{self.target_keys.capital} =", result.stdout)
        self.assertIn("Target year: 2024", result.stdout)


if __name__ == "__main__":
    unittest.main()
