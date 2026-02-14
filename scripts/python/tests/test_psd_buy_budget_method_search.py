from __future__ import annotations

import csv
import math
import tempfile
import unittest
from pathlib import Path

from scripts.python.experiments.psd.psd_buy_budget_method_search import (
    build_arg_parser,
    count_within_one_percent,
    select_shard_methods,
    validate_shard_args,
)
from scripts.python.helpers.psd.buy_budget_methods import (
    METHOD_FAMILY_PSD_LOG_OLS_ROBUST_MU,
    BuyMethodResult,
    BuyMethodSpec,
    MethodDiagnostics,
    compute_initial_seed_2011,
    method_specs_from_grid,
    parse_method_id,
    rank_method_results,
    run_legacy_2011_method_search,
)


class TestPsdBuyBudgetMethodSearch(unittest.TestCase):
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

    def _write_properties(self, text: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            "w",
            suffix=".properties",
            delete=False,
            encoding="utf-8",
        )
        with handle:
            handle.write(text)
        return Path(handle.name)

    def _synthetic_p3(self) -> Path:
        return self._write_csv(
            [
                ["", "PSD"],
                ["", "", "", "2010", "2011", "2012", "2011-Q1"],
                ["3.1", "loan amount"],
                ["", "£0K - £50K", "", "5", "10", "5", "2"],
                ["", "£50K - £120K", "", "5", "15", "5", "2"],
                ["", "£120K - £250K", "", "5", "20", "5", "2"],
                ["", "£250K +", "", "5", "10", "5", "2"],
                ["", "Total", "", "20", "55", "20", "8"],
                ["3.7.1", "lti single"],
                ["", "< 2.5", "", "3", "5", "3", "1"],
                ["", "2.5 to 3.49", "", "3", "10", "3", "1"],
                ["", "3.5 to 4.49", "", "3", "12", "3", "1"],
                ["", ">5.5", "", "3", "5", "3", "1"],
                ["", "Total", "", "12", "32", "12", "4"],
                ["3.7.2", "lti joint"],
                ["", "< 2.5", "", "3", "4", "3", "1"],
                ["", "2.5 to 3.49", "", "3", "8", "3", "1"],
                ["", "3.5 to 4.49", "", "3", "10", "3", "1"],
                ["", ">5.5", "", "3", "4", "3", "1"],
                ["", "Total", "", "12", "26", "12", "4"],
            ]
        )

    def _synthetic_p5(self) -> Path:
        return self._write_csv(
            [
                ["", "PSD"],
                ["", "", "", "2010", "2011", "2012", "2011-Q1"],
                ["5.1", "property"],
                ["", "£0K - £60K", "", "5", "10", "5", "2"],
                ["", "£60K - £120K", "", "5", "15", "5", "2"],
                ["", "£120K - £250K", "", "5", "20", "5", "2"],
                ["", "£250K +", "", "5", "10", "5", "2"],
                ["", "Unknown value", "", "1", "1", "1", "0"],
                ["", "Total", "", "21", "56", "21", "8"],
            ]
        )

    def _synthetic_ppd(self) -> Path:
        return self._write_csv(
            [
                ["id1", "100000", "2011-01-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
                ["id2", "200000", "2011-02-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
                ["id3", "300000", "2011-03-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
                ["id4", "400000", "2011-04-01 00:00", "", "", "", "", "", "", "", "", "", "", "", "A", "A"],
            ]
        )

    def test_parser_defaults(self) -> None:
        args = build_arg_parser().parse_args([])
        self.assertEqual(args.config_path, "input-data-versions/v0/config.properties")
        self.assertEqual(args.target_year_psd, 2011)
        self.assertEqual(args.target_year_ppd, 2011)
        self.assertEqual(args.top_k, 20)
        self.assertEqual(args.within_bin_points, 11)
        self.assertEqual(args.quantile_grid_size, 2000)
        self.assertEqual(
            args.families,
            "psd_log_ols_residual,psd_log_ols_robust_mu",
        )
        self.assertEqual(args.mu_upper_trim_fracs, "0.0063")
        self.assertEqual(args.progress_every, 500)
        self.assertEqual(args.progress_every_seconds, 2.0)
        self.assertEqual(args.shard_count, 1)
        self.assertEqual(args.shard_index, 0)
        self.assertIsNone(args.summary_json)

    def test_method_id_roundtrip(self) -> None:
        method = BuyMethodSpec(
            family="psd_log_ols_residual",
            loan_to_income_coupling="comonotonic",
            income_to_price_coupling="independent",
            loan_open_upper_k=3000.0,
            lti_open_upper=6.0,
            lti_open_lower=2.0,
            income_open_upper_k=200.0,
            property_open_upper_k=1200.0,
            trim_fraction=0.0,
            within_bin_points=11,
            quantile_grid_size=2000,
            mu_upper_trim_fraction=0.0063,
        )
        parsed = parse_method_id(method.method_id)
        self.assertEqual(parsed, method)

    def test_parse_legacy_method_id_without_mu_trim(self) -> None:
        legacy = (
            "family=psd_log_ols_residual|"
            "loan_to_income=comonotonic|"
            "income_to_price=independent|"
            "loan_open_k=3000|"
            "lti_open=6|"
            "lti_floor=2|"
            "income_open_k=200|"
            "property_open_k=1200|"
            "trim=0|"
            "within_bin_points=11|"
            "grid=2000"
        )
        parsed = parse_method_id(legacy)
        self.assertEqual(parsed.mu_upper_trim_fraction, 0.0)

    def test_ranking_tie_break_uses_method_id(self) -> None:
        method_a = BuyMethodSpec(
            family="psd_log_ols_residual",
            loan_to_income_coupling="independent",
            income_to_price_coupling="independent",
            loan_open_upper_k=2000.0,
            lti_open_upper=6.0,
            lti_open_lower=2.0,
            income_open_upper_k=200.0,
            property_open_upper_k=1200.0,
            trim_fraction=0.0,
            within_bin_points=11,
            quantile_grid_size=2000,
            mu_upper_trim_fraction=0.0,
        )
        method_b = BuyMethodSpec(
            family="psd_log_ols_residual",
            loan_to_income_coupling="comonotonic",
            income_to_price_coupling="comonotonic",
            loan_open_upper_k=2000.0,
            lti_open_upper=6.0,
            lti_open_lower=2.0,
            income_open_upper_k=200.0,
            property_open_upper_k=1200.0,
            trim_fraction=0.0,
            within_bin_points=11,
            quantile_grid_size=2000,
            mu_upper_trim_fraction=0.0,
        )
        diagnostics = MethodDiagnostics(1.0, 1.0, 10, 0, 10, False)
        row_a = BuyMethodResult(
            method=method_a,
            buy_scale=1.0,
            buy_exponent=1.0,
            buy_mu=0.0,
            buy_sigma=1.0,
            distance_norm=0.1,
            abs_d_scale_norm=0.1,
            abs_d_exponent_norm=0.1,
            abs_d_mu_norm=0.1,
            abs_d_sigma_norm=0.1,
            diagnostics=diagnostics,
        )
        row_b = BuyMethodResult(
            method=method_b,
            buy_scale=1.0,
            buy_exponent=1.0,
            buy_mu=0.0,
            buy_sigma=1.0,
            distance_norm=0.1,
            abs_d_scale_norm=0.1,
            abs_d_exponent_norm=0.1,
            abs_d_mu_norm=0.1,
            abs_d_sigma_norm=0.1,
            diagnostics=diagnostics,
        )
        ranked = rank_method_results([row_a, row_b])
        self.assertEqual(ranked[0].method.method_id, min(method_a.method_id, method_b.method_id))

    def test_initial_seed_computation_returns_finite_values(self) -> None:
        p3_path = self._synthetic_p3()
        p5_path = self._synthetic_p5()
        ppd_path = self._synthetic_ppd()
        try:
            seed, ppd_stats, diagnostics = compute_initial_seed_2011(
                p3_csv=p3_path,
                p5_csv=p5_path,
                ppd_csv=ppd_path,
                target_year_psd=2011,
                target_year_ppd=2011,
            )
        finally:
            p3_path.unlink(missing_ok=True)
            p5_path.unlink(missing_ok=True)
            ppd_path.unlink(missing_ok=True)

        self.assertTrue(math.isfinite(seed.buy_scale))
        self.assertTrue(math.isfinite(seed.buy_exponent))
        self.assertTrue(math.isfinite(seed.buy_mu))
        self.assertTrue(math.isfinite(seed.buy_sigma))
        self.assertEqual(ppd_stats.rows_used, 4)
        self.assertIn("loan_bins", diagnostics)

    def test_run_search_fail_fast_on_missing_target_keys(self) -> None:
        p3_path = self._synthetic_p3()
        p5_path = self._synthetic_p5()
        ppd_path = self._synthetic_ppd()
        bad_config = self._write_properties("FOO = 1\n")

        methods = method_specs_from_grid(
            families=["psd_log_ols_residual"],
            loan_to_income_couplings=["comonotonic"],
            income_to_price_couplings=["comonotonic"],
            loan_open_upper_k_values=[3000.0],
            lti_open_upper_values=[6.0],
            lti_open_lower_values=[2.0],
            income_open_upper_k_values=[200.0],
            property_open_upper_k_values=[1200.0],
            trim_fractions=[0.0],
            within_bin_points=11,
            quantile_grid_size=2000,
        )

        try:
            with self.assertRaisesRegex(ValueError, "Missing target keys"):
                run_legacy_2011_method_search(
                    p3_csv=p3_path,
                    p5_csv=p5_path,
                    ppd_csv=ppd_path,
                    config_path=bad_config,
                    target_year_psd=2011,
                    target_year_ppd=2011,
                    methods=methods,
                )
        finally:
            p3_path.unlink(missing_ok=True)
            p5_path.unlink(missing_ok=True)
            ppd_path.unlink(missing_ok=True)
            bad_config.unlink(missing_ok=True)

    def test_shard_union_and_disjointness(self) -> None:
        methods = method_specs_from_grid(
            families=["psd_log_ols_residual", METHOD_FAMILY_PSD_LOG_OLS_ROBUST_MU],
            loan_to_income_couplings=["comonotonic"],
            income_to_price_couplings=["comonotonic"],
            loan_open_upper_k_values=[600.0, 800.0],
            lti_open_upper_values=[8.0],
            lti_open_lower_values=[2.0],
            income_open_upper_k_values=[80.0],
            property_open_upper_k_values=[10000.0],
            trim_fractions=[0.0],
            mu_upper_trim_fractions=[0.0, 0.0063],
            within_bin_points=11,
            quantile_grid_size=2000,
        )
        shard0 = select_shard_methods(methods, shard_count=2, shard_index=0)
        shard1 = select_shard_methods(methods, shard_count=2, shard_index=1)
        ids_all = sorted(method.method_id for method in methods)
        ids_union = sorted([method.method_id for method in shard0] + [method.method_id for method in shard1])
        self.assertEqual(ids_union, ids_all)
        self.assertTrue(set(method.method_id for method in shard0).isdisjoint(method.method_id for method in shard1))

    def test_validate_shard_args_fail_fast(self) -> None:
        with self.assertRaisesRegex(ValueError, "shard-count must be positive"):
            validate_shard_args(shard_count=0, shard_index=0)
        with self.assertRaisesRegex(ValueError, "shard-index must be in \\[0, shard-count\\)"):
            validate_shard_args(shard_count=4, shard_index=4)

    def test_robust_family_produces_nonzero_mu(self) -> None:
        p3_path = self._synthetic_p3()
        p5_path = self._synthetic_p5()
        ppd_path = self._synthetic_ppd()
        config = self._write_properties(
            "\n".join(
                [
                    "BUY_SCALE = 42.90361",
                    "BUY_EXPONENT = 0.7891695",
                    "BUY_MU = -0.0176871",
                    "BUY_SIGMA = 0.4103773",
                    "",
                ]
            )
        )

        methods = method_specs_from_grid(
            families=[METHOD_FAMILY_PSD_LOG_OLS_ROBUST_MU],
            loan_to_income_couplings=["comonotonic"],
            income_to_price_couplings=["comonotonic"],
            loan_open_upper_k_values=[600.0],
            lti_open_upper_values=[10.0],
            lti_open_lower_values=[2.0],
            income_open_upper_k_values=[80.0],
            property_open_upper_k_values=[10000.0],
            trim_fractions=[0.0],
            mu_upper_trim_fractions=[0.0063],
            within_bin_points=11,
            quantile_grid_size=2000,
        )
        try:
            output = run_legacy_2011_method_search(
                p3_csv=p3_path,
                p5_csv=p5_path,
                ppd_csv=ppd_path,
                config_path=config,
                target_year_psd=2011,
                target_year_ppd=2011,
                methods=methods,
            )
        finally:
            p3_path.unlink(missing_ok=True)
            p5_path.unlink(missing_ok=True)
            ppd_path.unlink(missing_ok=True)
            config.unlink(missing_ok=True)

        self.assertTrue(math.isfinite(output.results[0].buy_mu))
        self.assertNotEqual(output.results[0].buy_mu, 0.0)

    def test_within_one_percent_count(self) -> None:
        diagnostics = MethodDiagnostics(1.0, 1.0, 10, 0, 10, False)
        target = (100.0, 1.0, -0.1, 0.2)
        close = BuyMethodResult(
            method=BuyMethodSpec(
                family="psd_log_ols_residual",
                loan_to_income_coupling="comonotonic",
                income_to_price_coupling="comonotonic",
                loan_open_upper_k=500.0,
                lti_open_upper=8.0,
                lti_open_lower=2.0,
                income_open_upper_k=60.0,
                property_open_upper_k=10000.0,
                trim_fraction=0.0,
                within_bin_points=11,
                quantile_grid_size=2000,
                mu_upper_trim_fraction=0.0,
            ),
            buy_scale=100.5,
            buy_exponent=0.995,
            buy_mu=-0.1009,
            buy_sigma=0.199,
            distance_norm=0.0,
            abs_d_scale_norm=0.0,
            abs_d_exponent_norm=0.0,
            abs_d_mu_norm=0.0,
            abs_d_sigma_norm=0.0,
            diagnostics=diagnostics,
        )
        far = BuyMethodResult(
            method=BuyMethodSpec(
                family="psd_log_ols_residual",
                loan_to_income_coupling="independent",
                income_to_price_coupling="independent",
                loan_open_upper_k=500.0,
                lti_open_upper=8.0,
                lti_open_lower=2.0,
                income_open_upper_k=60.0,
                property_open_upper_k=10000.0,
                trim_fraction=0.0,
                within_bin_points=11,
                quantile_grid_size=2000,
                mu_upper_trim_fraction=0.0,
            ),
            buy_scale=110.0,
            buy_exponent=1.05,
            buy_mu=-0.08,
            buy_sigma=0.25,
            distance_norm=0.0,
            abs_d_scale_norm=0.0,
            abs_d_exponent_norm=0.0,
            abs_d_mu_norm=0.0,
            abs_d_sigma_norm=0.0,
            diagnostics=diagnostics,
        )
        count = count_within_one_percent([close, far], *target)
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
