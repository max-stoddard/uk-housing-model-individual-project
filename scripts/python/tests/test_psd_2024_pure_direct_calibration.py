from __future__ import annotations

import math
import unittest
from pathlib import Path

from scripts.python.calibration.psd.psd_2024_pure_direct_calibration import (
    BLOCKED_KEYS,
    _build_rows,
)
from scripts.python.helpers.psd.calibration_2024 import (
    calibrate_downpayment_2024,
    calibrate_mortgage_duration_2024,
    compare_quarterly_monthly_consistency,
)
from scripts.python.helpers.psd.quarterly_long import (
    load_monthly_psd_rows,
    load_quarterly_psd_rows,
)


class TestPsd2024PureDirectCalibration(unittest.TestCase):
    def test_output_schema_and_blocked_keys(self) -> None:
        quarterly_rows = load_quarterly_psd_rows(
            Path("private-datasets/psd/2024/psd-quarterly-2024.csv")
        )
        downpayment = calibrate_downpayment_2024(
            quarterly_rows,
            target_year=2024,
            within_bin_points=11,
            method_name="median_anchored_nonftb_independent",
        )
        mortgage_duration = calibrate_mortgage_duration_2024(
            quarterly_rows,
            target_year=2024,
            method_name="weighted_mean_round",
            open_top_year=45,
        )
        rows = _build_rows(
            downpayment_result=downpayment,
            mortgage_duration_result=mortgage_duration,
        )

        estimated_keys = {row.key for row in rows if row.status == "estimated"}
        self.assertEqual(
            estimated_keys,
            {
                "DOWNPAYMENT_FTB_SCALE",
                "DOWNPAYMENT_FTB_SHAPE",
                "DOWNPAYMENT_OO_SCALE",
                "DOWNPAYMENT_OO_SHAPE",
                "MORTGAGE_DURATION_YEARS",
            },
        )
        blocked_keys = {row.key for row in rows if row.status == "blocked"}
        self.assertEqual(blocked_keys, set(BLOCKED_KEYS))

        for row in rows:
            self.assertTrue(hasattr(row, "key"))
            self.assertTrue(hasattr(row, "value"))
            self.assertTrue(hasattr(row, "status"))
            self.assertTrue(hasattr(row, "method_id"))
            self.assertTrue(hasattr(row, "rationale"))

        self.assertTrue(math.isfinite(downpayment.ftb_scale))
        self.assertTrue(math.isfinite(downpayment.ftb_shape))
        self.assertTrue(math.isfinite(downpayment.oo_scale))
        self.assertTrue(math.isfinite(downpayment.oo_shape))
        self.assertGreaterEqual(mortgage_duration.estimate_rounded, 1)

    def test_monthly_quarterly_consistency_checks(self) -> None:
        quarterly_rows = load_quarterly_psd_rows(
            Path("private-datasets/psd/2024/psd-quarterly-2024.csv")
        )
        monthly_p1_rows = load_monthly_psd_rows(
            Path("private-datasets/psd/2024/psd-monthly-2024-p1-sales-borrower.csv")
        )
        monthly_p2_rows = load_monthly_psd_rows(
            Path("private-datasets/psd/2024/psd-monthly-2024-p2-ltv-sales.csv")
        )

        checks = compare_quarterly_monthly_consistency(
            quarterly_rows,
            target_year=2024,
            monthly_p1_rows=monthly_p1_rows,
            monthly_p2_rows=monthly_p2_rows,
        )
        self.assertEqual(len(checks), 2)
        self.assertTrue(checks[0].checked)
        self.assertTrue(checks[1].checked)
        self.assertTrue(checks[0].matches)
        self.assertTrue(checks[1].matches)
        self.assertAlmostEqual(checks[0].total_difference, 0.0, places=6)
        self.assertAlmostEqual(checks[1].total_difference, 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
