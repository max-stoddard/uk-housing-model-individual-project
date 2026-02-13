from __future__ import annotations

import csv
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.python.calibration.was.wealth_income_joint_prob_dist import (
    _filter_income_rows,
    _resolve_income_bounds,
    run_wealth_income_joint_prob_dist,
)
from scripts.python.helpers.was.distributions import log_histogram2d


class _DummyConfig:
    WAS_DATASET = "R8"


class _DummyConstants:
    WAS_WEIGHT = "weight"
    WAS_GROSS_FINANCIAL_WEALTH = "gross_wealth"
    WAS_NET_FINANCIAL_WEALTH = "net_wealth"


class _DummyDerived:
    GROSS_NON_RENT_INCOME = "gross_income"
    NET_NON_RENT_INCOME = "net_income"
    LIQ_FINANCIAL_WEALTH = "liq_wealth"


class TestWasWealthIncomeJointProbDist(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.module_name = "scripts.python.calibration.was.wealth_income_joint_prob_dist"

    def _run_help(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "-m", self.module_name, "--help"],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def _build_synthetic_chunk(self) -> pd.DataFrame:
        gross_income = np.concatenate(([8.0], np.linspace(5000.0, 120000.0, 800)))
        net_income = np.concatenate(([8.0], np.linspace(4800.0, 115000.0, 800)))
        net_wealth = np.linspace(1.0, 2_000_000.0, gross_income.size)
        gross_wealth = net_wealth + 10_000.0
        liq_wealth = net_wealth + 5_000.0
        weight = np.ones(gross_income.size, dtype=float)
        return pd.DataFrame(
            {
                "gross_income": gross_income,
                "net_income": net_income,
                "gross_wealth": gross_wealth,
                "net_wealth": net_wealth,
                "liq_wealth": liq_wealth,
                "weight": weight,
            }
        )

    def test_cli_help_runs(self) -> None:
        result = self._run_help()
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Generate joint income/wealth distributions for WAS", result.stdout)

    def test_filter_order_removes_low_income_outlier(self) -> None:
        chunk = self._build_synthetic_chunk()
        filtered = _filter_income_rows(
            chunk,
            gross_income_column="gross_income",
            net_income_column="net_income",
        )
        self.assertGreater(float(filtered["gross_income"].min()), 1000.0)
        self.assertGreater(float(filtered["net_income"].min()), 1000.0)

    def test_resolve_income_bounds_returns_positive_increasing_bounds(self) -> None:
        chunk = pd.DataFrame(
            {
                "gross_income": [5100.0, 6100.0, 7100.0],
                "net_income": [5000.0, 5900.0, 6900.0],
            }
        )
        min_net, max_gross = _resolve_income_bounds(
            chunk,
            gross_income_column="gross_income",
            net_income_column="net_income",
        )
        self.assertEqual(min_net, 5000.0)
        self.assertEqual(max_gross, 7100.0)

    def test_synthetic_histogram_has_no_zero_income_rows(self) -> None:
        chunk = self._build_synthetic_chunk()
        filtered = _filter_income_rows(
            chunk,
            gross_income_column="gross_income",
            net_income_column="net_income",
        )
        min_net, max_gross = _resolve_income_bounds(
            filtered,
            gross_income_column="gross_income",
            net_income_column="net_income",
        )
        income_edges = np.linspace(np.log(min_net), np.log(max_gross), 26)
        wealth_edges = np.linspace(
            np.log(float(filtered["net_wealth"].min())),
            np.log(float(filtered["net_wealth"].max())),
            21,
        )
        frequency, _, _ = log_histogram2d(
            filtered["gross_income"],
            filtered["net_wealth"],
            income_edges,
            wealth_edges,
            filtered["weight"],
        )
        row_sums = frequency.sum(axis=1)
        self.assertTrue(np.all(row_sums > 0.0))

    def test_output_keys_and_files_are_stable(self) -> None:
        chunk = self._build_synthetic_chunk()
        chunk = _filter_income_rows(
            chunk,
            gross_income_column="gross_income",
            net_income_column="net_income",
        )
        expected_keys = {
            "gross_gross",
            "gross_net",
            "gross_liq",
            "net_gross",
            "net_net",
            "net_liq",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "scripts.python.calibration.was.wealth_income_joint_prob_dist._load_income_wealth_chunk",
                return_value=(chunk, _DummyConfig(), _DummyConstants(), _DummyDerived()),
            ):
                outputs = run_wealth_income_joint_prob_dist(
                    dataset="R8",
                    output_dir=tmpdir,
                )
            self.assertEqual(set(outputs["output_files"].keys()), expected_keys)
            for file_path in outputs["output_files"].values():
                self.assertTrue(Path(file_path).exists())

            # Gross-income / net-wealth file should have no empty normalized income rows.
            gross_net = Path(outputs["output_files"]["gross_net"])
            sums_by_income: dict[tuple[float, float], float] = {}
            with gross_net.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle, skipinitialspace=True)
                next(reader)
                for x0, x1, _, _, prob in reader:
                    key = (float(x0), float(x1))
                    sums_by_income[key] = sums_by_income.get(key, 0.0) + float(prob)
            self.assertTrue(all(total > 0.0 for total in sums_by_income.values()))


if __name__ == "__main__":
    unittest.main()
