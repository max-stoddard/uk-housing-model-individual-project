from __future__ import annotations

import math
import unittest

from scripts.python.experiments.psd.psd_downpayment_lognormal_method_search import (
    DownpaymentMethodResult,
    DownpaymentMethodSpec,
)
from scripts.python.experiments.psd.psd_lti_hard_max_method_search import (
    LtiMethodResult,
    LtiMethodSpec,
)
from scripts.python.experiments.psd.psd_pure_reproduction_report import build_report_rows
from scripts.python.helpers.psd.bins import PsdBin
from scripts.python.helpers.psd.metrics import lognormal_params_from_synthetic_downpayment


class TestPsdDownpaymentMethodSearch(unittest.TestCase):
    def test_synthetic_lognormal_fit_constant_distribution(self) -> None:
        ltv_bins = [PsdBin(label="50%-50%", lower=50.0, upper=50.0, mass=1.0)]
        property_bins = [
            PsdBin(label="200k-200k", lower=200_000.0, upper=200_000.0, mass=1.0)
        ]

        mu, sigma = lognormal_params_from_synthetic_downpayment(
            ltv_bins,
            property_bins,
            ltv_open_upper=100.0,
            property_open_upper_k=2_000.0,
            coupling="independent",
        )

        self.assertAlmostEqual(mu, math.log(100_000.0), places=10)
        self.assertAlmostEqual(sigma, 0.0, places=10)

    def test_coupling_variants_change_shape(self) -> None:
        ltv_bins = [
            PsdBin(label="10-20", lower=10.0, upper=20.0, mass=1.0),
            PsdBin(label="80-90", lower=80.0, upper=90.0, mass=1.0),
        ]
        property_bins = [
            PsdBin(label="100k-200k", lower=100_000.0, upper=200_000.0, mass=1.0),
            PsdBin(label="900k-1m", lower=900_000.0, upper=1_000_000.0, mass=1.0),
        ]

        _, sigma_ind = lognormal_params_from_synthetic_downpayment(
            ltv_bins,
            property_bins,
            ltv_open_upper=100.0,
            property_open_upper_k=2_000.0,
            coupling="independent",
        )
        _, sigma_comono = lognormal_params_from_synthetic_downpayment(
            ltv_bins,
            property_bins,
            ltv_open_upper=100.0,
            property_open_upper_k=2_000.0,
            coupling="comonotonic",
        )
        _, sigma_counter = lognormal_params_from_synthetic_downpayment(
            ltv_bins,
            property_bins,
            ltv_open_upper=100.0,
            property_open_upper_k=2_000.0,
            coupling="countermonotonic",
        )

        self.assertNotAlmostEqual(sigma_comono, sigma_counter, places=8)
        self.assertGreaterEqual(sigma_ind, min(sigma_comono, sigma_counter))
        self.assertLessEqual(sigma_ind, max(sigma_comono, sigma_counter))

    def test_report_schema_and_blocked_key_propagation(self) -> None:
        lti_result = LtiMethodResult(
            method=LtiMethodSpec(
                ftb_source="ftb_joint",
                hm_source="hm_subtracted",
                quantile=0.99,
                open_top_upper=6.0,
                interpolation="linear",
            ),
            ftb_estimate_raw=5.39,
            hm_estimate_raw=5.59,
            ftb_estimate_rounded=5.4,
            hm_estimate_rounded=5.6,
            distance_rounded=0.0,
            distance_raw=0.02,
        )
        downpayment_result = DownpaymentMethodResult(
            method=DownpaymentMethodSpec(
                oo_method="all_all",
                ltv_open_upper=100.0,
                property_open_upper_k=2000.0,
                coupling="independent",
            ),
            ftb_scale=10.47,
            ftb_shape=0.81,
            oo_scale=11.18,
            oo_shape=0.87,
            distance=0.17,
        )

        rows = build_report_rows(
            lti_default=lti_result,
            lti_targets=(5.4, 5.6),
            downpayment_default=downpayment_result,
            downpayment_targets=(10.35, 0.898, 11.15, 0.958),
        )

        keys = {row.key for row in rows}
        self.assertIn("MORTGAGE_DURATION_YEARS", keys)
        self.assertIn("BANK_AFFORDABILITY_HARD_MAX", keys)
        blocked_rows = [row for row in rows if row.status == "blocked"]
        self.assertEqual({row.key for row in blocked_rows}, {
            "MORTGAGE_DURATION_YEARS",
            "BANK_AFFORDABILITY_HARD_MAX",
        })

        for row in rows:
            self.assertTrue(hasattr(row, "key"))
            self.assertTrue(hasattr(row, "target"))
            self.assertTrue(hasattr(row, "estimate"))
            self.assertTrue(hasattr(row, "abs_error"))
            self.assertTrue(hasattr(row, "method_id"))
            self.assertTrue(hasattr(row, "status"))
            self.assertTrue(hasattr(row, "rationale"))


if __name__ == "__main__":
    unittest.main()
