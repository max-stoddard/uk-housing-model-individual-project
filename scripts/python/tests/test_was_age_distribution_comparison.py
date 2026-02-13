from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from scripts.python.experiments.was.age_distribution_comparison import (
    _split_final_bin_uniform,
)


class TestWasAgeDistributionComparison(unittest.TestCase):
    def test_legacy_round8_final_bin_75_85_is_split_to_95(self) -> None:
        distribution = pd.DataFrame(
            [
                {"lower_edge": 65.0, "upper_edge": 75.0, "probability": 0.2},
                {"lower_edge": 75.0, "upper_edge": 85.0, "probability": 0.1},
            ]
        )

        actual = _split_final_bin_uniform(distribution)
        expected = pd.DataFrame(
            [
                {"lower_edge": 65.0, "upper_edge": 75.0, "probability": 0.2},
                {"lower_edge": 75.0, "upper_edge": 85.0, "probability": 0.05},
                {"lower_edge": 85.0, "upper_edge": 95.0, "probability": 0.05},
            ]
        )
        assert_frame_equal(actual.reset_index(drop=True), expected)

    def test_new_round8_final_bin_75_95_is_left_unchanged(self) -> None:
        distribution = pd.DataFrame(
            [
                {"lower_edge": 65.0, "upper_edge": 75.0, "probability": 0.2},
                {"lower_edge": 75.0, "upper_edge": 95.0, "probability": 0.1},
            ]
        )

        actual = _split_final_bin_uniform(distribution)
        assert_frame_equal(actual.reset_index(drop=True), distribution)


if __name__ == "__main__":
    unittest.main()
