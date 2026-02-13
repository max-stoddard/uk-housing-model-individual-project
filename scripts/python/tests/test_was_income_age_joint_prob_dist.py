from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from scripts.python.calibration.was.income_age_joint_prob_dist import (
    _filter_income_rows,
    _resolve_age_bin_edges,
    _resolve_income_bounds,
)
from scripts.python.helpers.was import config as was_config


class TestWasIncomeAgeJointProbDist(unittest.TestCase):
    def test_filter_order_removes_low_positive_outlier(self) -> None:
        gross = [8.0] + [5000.0 + i * 10.0 for i in range(300)]
        net = [8.0] + [4800.0 + i * 10.0 for i in range(300)]
        weight = [1.0] * len(gross)
        chunk = pd.DataFrame(
            {
                "GrossNonRentIncome": gross,
                "NetNonRentIncome": net,
                "weight": weight,
            }
        )

        filtered = _filter_income_rows(
            chunk,
            gross_income_column="GrossNonRentIncome",
            net_income_column="NetNonRentIncome",
        )

        self.assertGreater(float(filtered["GrossNonRentIncome"].min()), 1000.0)
        self.assertGreater(float(filtered["NetNonRentIncome"].min()), 1000.0)

    def test_resolve_income_bounds_returns_positive_increasing_bounds(self) -> None:
        chunk = pd.DataFrame(
            {
                "GrossNonRentIncome": [5200.0, 6100.0, 7100.0],
                "NetNonRentIncome": [5000.0, 5900.0, 6900.0],
            }
        )

        min_net, max_gross = _resolve_income_bounds(
            chunk,
            gross_income_column="GrossNonRentIncome",
            net_income_column="NetNonRentIncome",
        )

        self.assertEqual(min_net, 5000.0)
        self.assertEqual(max_gross, 7100.0)

    def test_round8_age_bins_are_remapped_to_75_95(self) -> None:
        age_bucket_data = {"BIN_EDGES": [0, 15, 25, 35, 45, 55, 65, 75, 85]}
        age_edges = _resolve_age_bin_edges(age_bucket_data, was_config.ROUND_8_DATA)

        self.assertTrue(np.allclose(age_edges, np.asarray([0, 15, 25, 35, 45, 55, 65, 75, 95], dtype=float)))

    def test_non_round8_age_bins_are_unchanged(self) -> None:
        age_bucket_data = {"BIN_EDGES": [0, 15, 25, 35, 45, 55, 65, 75, 85, 95]}
        age_edges = _resolve_age_bin_edges(age_bucket_data, was_config.WAVE_3_DATA)

        self.assertTrue(np.allclose(age_edges, np.asarray(age_bucket_data["BIN_EDGES"], dtype=float)))


if __name__ == "__main__":
    unittest.main()
