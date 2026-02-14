from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.python.experiments.psd.psd_lti_hard_max_method_search import (
    TARGET_FTB_KEY,
    TARGET_HM_KEY,
    run_lti_search,
)
from scripts.python.helpers.psd.bins import parse_band_label
from scripts.python.helpers.psd.metrics import binned_weighted_quantile


class TestPsdLtiMethodSearch(unittest.TestCase):
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

    def _write_config(self, target_ftb: float = 5.4, target_hm: float = 5.6) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".properties", delete=False, encoding="utf-8")
        with handle:
            handle.write(f"{TARGET_FTB_KEY} = {target_ftb}\n")
            handle.write(f"{TARGET_HM_KEY} = {target_hm}\n")
        return Path(handle.name)

    def test_band_parser_supports_open_closed_forms(self) -> None:
        self.assertEqual(parse_band_label("< 2.5"), (None, 2.5))
        self.assertEqual(parse_band_label("2.5 to 3.49"), (2.5, 3.49))
        self.assertEqual(parse_band_label("95% +"), (95.0, None))

    def test_quantile_linear_interpolation(self) -> None:
        from scripts.python.helpers.psd.bins import PsdBin

        bins = [
            PsdBin(label="0-1", lower=0.0, upper=1.0, mass=1.0),
            PsdBin(label="1-2", lower=1.0, upper=2.0, mass=1.0),
        ]
        result = binned_weighted_quantile(bins, 0.75, open_upper=2.0, interpolation="linear")
        self.assertAlmostEqual(result, 1.5, places=10)

    def test_method_ranking_is_stable_and_schema_is_complete(self) -> None:
        p3_csv = self._write_csv(
            [
                ["", "PSD"],
                ["", "", "", "2010", "2011", "2012", "2011-Q1"],
                ["3.7.1", "single"],
                ["", "< 2.5", "", "10", "10", "10", "2"],
                ["", "2.5 to 3.49", "", "20", "20", "20", "3"],
                ["", ">5.5", "", "5", "5", "5", "1"],
                ["", "Total", "", "35", "35", "35", "6"],
                ["3.7.2", "joint"],
                ["", "< 2.5", "", "12", "12", "12", "2"],
                ["", "2.5 to 3.49", "", "21", "21", "21", "3"],
                ["", ">5.5", "", "6", "6", "6", "1"],
                ["", "Total", "", "39", "39", "39", "6"],
            ]
        )
        p6_csv = self._write_csv(
            [
                ["", "PSD"],
                ["", "", "", "2010", "2011", "2012", "2011-Q1"],
                ["6.1", "ftb single"],
                ["", "< 2.5", "", "2", "2", "2", "0.4"],
                ["", "2.5 to 3.49", "", "7", "7", "7", "1.0"],
                ["", ">5.5", "", "1", "1", "1", "0.2"],
                ["", "Total", "", "10", "10", "10", "1.6"],
                ["6.2", "ftb joint"],
                ["", "< 2.5", "", "1", "1", "1", "0.2"],
                ["", "2.5 to 3.49", "", "8", "8", "8", "1.1"],
                ["", ">5.5", "", "1", "1", "1", "0.2"],
                ["", "Total", "", "10", "10", "10", "1.5"],
            ]
        )
        config_path = self._write_config()

        try:
            output = run_lti_search(
                p3_csv=p3_csv,
                p6_csv=p6_csv,
                config_path=config_path,
                target_year=2011,
            )
        finally:
            p3_csv.unlink(missing_ok=True)
            p6_csv.unlink(missing_ok=True)
            config_path.unlink(missing_ok=True)

        self.assertGreater(len(output.results), 0)
        ranking = [
            (item.distance_rounded, item.distance_raw, item.method.method_id)
            for item in output.results
        ]
        self.assertEqual(ranking, sorted(ranking))

        first = output.results[0]
        self.assertIn("ftb=", first.method.method_id)
        self.assertIn("hm=", first.method.method_id)
        self.assertGreaterEqual(first.ftb_estimate_raw, 0.0)
        self.assertGreaterEqual(first.hm_estimate_raw, 0.0)


if __name__ == "__main__":
    unittest.main()
