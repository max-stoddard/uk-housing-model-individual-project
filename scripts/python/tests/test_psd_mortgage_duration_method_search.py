from __future__ import annotations

import unittest

from scripts.python.helpers.psd.bins import PsdBin, parse_band_label
from scripts.python.helpers.psd.mortgage_duration import (
    estimate_duration_years,
    run_mortgage_duration_search,
)
from scripts.python.helpers.psd.quarterly_long import LongPsdRow, PsdPeriod


class TestPsdMortgageDurationMethodSearch(unittest.TestCase):
    def _rows(self) -> list[LongPsdRow]:
        rows: list[LongPsdRow] = []
        quarter_payload = {
            1: {"0 - 5 years": 100.0, ">20 - 25 years": 300.0, ">35 years": 100.0},
            2: {"0 - 5 years": 120.0, ">20 - 25 years": 330.0, ">35 years": 80.0},
            3: {"0 - 5 years": 90.0, ">20 - 25 years": 320.0, ">35 years": 110.0},
            4: {"0 - 5 years": 110.0, ">20 - 25 years": 310.0, ">35 years": 90.0},
        }
        for quarter, categories in quarter_payload.items():
            period = PsdPeriod(label=f"2024 Q{quarter}", year=2024, quarter=quarter, month=None)
            for category, sales in categories.items():
                rows.append(
                    LongPsdRow(
                        group="Number of sales by mortgage term",
                        category=category,
                        region="East Midlands",
                        period=period,
                        sales=sales,
                    )
                )
            rows.append(
                LongPsdRow(
                    group="Number of sales by mortgage term",
                    category="Mortgage Term Bands - Unspecified",
                    region="East Midlands",
                    period=period,
                    sales=10.0,
                )
            )
        return rows

    def test_term_band_parser_covers_open_and_range_labels(self) -> None:
        self.assertEqual(parse_band_label("0 - 5 years"), (0.0, 5.0))
        self.assertEqual(parse_band_label(">20 - 25 years"), (20.0, 25.0))
        self.assertEqual(parse_band_label(">35 years"), (35.0, None))

    def test_mean_median_mode_estimators(self) -> None:
        bins = [
            PsdBin(label="0 - 5 years", lower=0.0, upper=5.0, mass=10.0),
            PsdBin(label=">5 - 10 years", lower=5.0, upper=10.0, mass=10.0),
            PsdBin(label=">35 years", lower=35.0, upper=None, mass=10.0),
        ]
        self.assertAlmostEqual(
            estimate_duration_years(bins, method_name="weighted_mean", open_top_year=40),
            (2.5 + 7.5 + 37.5) / 3.0,
            places=10,
        )
        self.assertAlmostEqual(
            estimate_duration_years(bins, method_name="weighted_median", open_top_year=40),
            7.5,
            places=10,
        )
        self.assertAlmostEqual(
            estimate_duration_years(bins, method_name="modal_midpoint", open_top_year=40),
            2.5,
            places=10,
        )

    def test_sensitivity_and_ranking_are_stable(self) -> None:
        results, quarters = run_mortgage_duration_search(
            self._rows(),
            target_year=2024,
            top_open_years=(40, 50),
            methods=("weighted_mean", "weighted_median", "modal_midpoint"),
        )
        self.assertEqual(quarters, ("2024 Q1", "2024 Q2", "2024 Q3", "2024 Q4"))
        self.assertEqual(len(results), 6)

        ranking = [
            (
                item.quarter_std,
                item.sensitivity_range,
                item.method_id,
            )
            for item in results
        ]
        self.assertEqual(ranking, sorted(ranking))

        mean_entries = [item for item in results if item.method_name == "weighted_mean"]
        self.assertGreater(mean_entries[0].sensitivity_range, 0.0)

        first = results[0]
        self.assertTrue(hasattr(first, "method_id"))
        self.assertTrue(hasattr(first, "year_estimate_raw"))
        self.assertTrue(hasattr(first, "year_estimate_rounded"))
        self.assertTrue(hasattr(first, "open_top_assumption"))
        self.assertTrue(hasattr(first, "quarter_mean"))
        self.assertTrue(hasattr(first, "quarter_std"))
        self.assertTrue(hasattr(first, "sensitivity_range"))
        self.assertTrue(hasattr(first, "legacy_distance_to_25"))
        self.assertTrue(hasattr(first, "status"))


if __name__ == "__main__":
    unittest.main()
