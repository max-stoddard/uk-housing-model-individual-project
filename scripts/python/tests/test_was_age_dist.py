from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.python.calibration.was.age_dist import _resolve_age_bin_edges, run_age_distribution
from scripts.python.helpers.was import config as was_config


class _DummyConfig:
    WAS_DATASET = was_config.ROUND_8_DATA
    WAS_DATA_ROOT = "/unused"


class _DummyConstants:
    WAS_WEIGHT = "weight"
    WAS_DATASET_AGE_BAND_MAPS = {
        "Age8": {
            "BIN_EDGES": [0, 15, 25, 35, 45, 55, 65, 75, 85],
            "TEXT_MAPPING": {},
            "WAS_VALUE_MAPPING": {
                1: 7.5,
                2: 20.0,
                3: 30.0,
                4: 40.0,
                5: 50.0,
                6: 60.0,
                7: 70.0,
                8: 80.0,
            },
        }
    }


class _DummyIoModule:
    @staticmethod
    def read_was_data(_data_root: str, _columns: list[str]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Age8": [1, 2, 3, 4, 5, 6, 7, 8],
                "weight": [1.0] * 8,
            }
        )


class TestWasAgeDist(unittest.TestCase):
    def test_resolve_age_bin_edges_round8_maps_last_edge_to_95(self) -> None:
        age_bucket_data = {"BIN_EDGES": [0, 15, 25, 35, 45, 55, 65, 75, 85]}
        age_edges = _resolve_age_bin_edges(age_bucket_data, was_config.ROUND_8_DATA)
        self.assertTrue(
            np.allclose(
                age_edges,
                np.asarray([0, 15, 25, 35, 45, 55, 65, 75, 95], dtype=float),
            )
        )

    def test_resolve_age_bin_edges_non_round8_is_unchanged(self) -> None:
        age_bucket_data = {"BIN_EDGES": [0, 15, 25, 35, 45, 55, 65, 75, 85, 95]}
        age_edges = _resolve_age_bin_edges(age_bucket_data, was_config.WAVE_3_DATA)
        self.assertTrue(
            np.allclose(age_edges, np.asarray(age_bucket_data["BIN_EDGES"], dtype=float))
        )

    def test_resolve_age_bin_edges_rejects_non_increasing_edges(self) -> None:
        age_bucket_data = {"BIN_EDGES": [0, 15, 15, 25]}
        with self.assertRaises(ValueError):
            _resolve_age_bin_edges(age_bucket_data, was_config.WAVE_3_DATA)

    def test_run_age_distribution_round8_writes_final_bin_to_95(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "scripts.python.calibration.was.age_dist.reload_was_modules",
                return_value=(_DummyConfig(), _DummyConstants(), _DummyIoModule()),
            ):
                outputs = run_age_distribution(
                    dataset=was_config.ROUND_8_DATA,
                    output_dir=tmpdir,
                )

            output_path = Path(outputs["output_files"]["Age8"])
            self.assertTrue(output_path.exists())

            lines = output_path.read_text(encoding="utf-8").strip().splitlines()
            last_line = lines[-1]
            lower_edge, upper_edge, _probability = [
                float(value.strip()) for value in last_line.split(",")
            ]
            self.assertAlmostEqual(lower_edge, 75.0)
            self.assertAlmostEqual(upper_edge, 95.0)


if __name__ == "__main__":
    unittest.main()
