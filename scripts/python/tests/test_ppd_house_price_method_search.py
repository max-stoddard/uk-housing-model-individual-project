from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from scripts.python.experiments.ppd.ppd_house_price_lognormal_method_search import (
    build_arg_parser,
    resolve_targets,
)
from scripts.python.helpers.ppd.house_price_methods import (
    MethodResult,
    MethodSpec,
    PpdParseStats,
    PpdRow,
    evaluate_method,
    rank_method_results,
    run_method_search,
)


class TestPpdHousePriceMethodSearch(unittest.TestCase):
    def _write_file(self, content: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            "w",
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        )
        with handle:
            handle.write(content)
        return Path(handle.name)

    def test_parser_defaults(self) -> None:
        args = build_arg_parser().parse_args(["dummy.csv"])
        self.assertEqual(args.config_path, "input-data-versions/v0/config.properties")
        self.assertEqual(args.target_scale_key, "HOUSE_PRICES_SCALE")
        self.assertEqual(args.target_shape_key, "HOUSE_PRICES_SHAPE")
        self.assertEqual(args.target_year, 2011)
        self.assertEqual(args.top_k, 20)
        self.assertEqual(args.delimiter, ",")
        self.assertEqual(args.skip_rows, 0)

    def test_missing_target_keys_fails_fast(self) -> None:
        config_path = self._write_file("FOO = 1\nBAR = 2\n")
        try:
            with self.assertRaisesRegex(ValueError, "Missing target key"):
                resolve_targets(
                    config_path=config_path,
                    target_scale_key="HOUSE_PRICES_SCALE",
                    target_shape_key="HOUSE_PRICES_SHAPE",
                    target_scale_override=None,
                    target_shape_override=None,
                )
        finally:
            config_path.unlink(missing_ok=True)

    def test_no_rows_after_filters_fails_fast(self) -> None:
        rows = [
            PpdRow(price=120000.0, transfer_year=2011, ppd_category_type="B", record_status="A"),
            PpdRow(price=150000.0, transfer_year=2011, ppd_category_type="B", record_status="A"),
        ]
        method = MethodSpec(
            category_mode="a_only",
            status_mode="a_only",
            year_mode="transfer_year_equals_target",
            std_mode="sample",
            trim_fraction=0.0,
        )
        with self.assertRaisesRegex(ValueError, "No rows remain after filters"):
            evaluate_method(
                rows,
                method=method,
                target_scale=12.0,
                target_shape=0.6,
                target_year=2011,
            )

    def test_std_mode_population_vs_sample(self) -> None:
        rows = [
            PpdRow(price=100.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=200.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=400.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
        ]
        pop_method = MethodSpec(
            category_mode="all",
            status_mode="all",
            year_mode="all_rows",
            std_mode="population",
            trim_fraction=0.0,
        )
        sample_method = MethodSpec(
            category_mode="all",
            status_mode="all",
            year_mode="all_rows",
            std_mode="sample",
            trim_fraction=0.0,
        )
        pop_result = evaluate_method(
            rows,
            method=pop_method,
            target_scale=0.0,
            target_shape=0.0,
            target_year=2011,
        )
        sample_result = evaluate_method(
            rows,
            method=sample_method,
            target_scale=0.0,
            target_shape=0.0,
            target_year=2011,
        )

        log_values = [math.log(100.0), math.log(200.0), math.log(400.0)]
        mean = sum(log_values) / len(log_values)
        expected_pop = math.sqrt(sum((value - mean) ** 2 for value in log_values) / len(log_values))
        expected_sample = math.sqrt(
            sum((value - mean) ** 2 for value in log_values) / (len(log_values) - 1)
        )

        self.assertAlmostEqual(pop_result.sigma, expected_pop, places=12)
        self.assertAlmostEqual(sample_result.sigma, expected_sample, places=12)
        self.assertGreater(sample_result.sigma, pop_result.sigma)

    def test_ranking_tie_break_uses_method_id(self) -> None:
        method_a = MethodSpec(
            category_mode="a_only",
            status_mode="all",
            year_mode="all_rows",
            std_mode="sample",
            trim_fraction=0.0,
        )
        method_b = MethodSpec(
            category_mode="all",
            status_mode="all",
            year_mode="all_rows",
            std_mode="sample",
            trim_fraction=0.0,
        )
        row_a = MethodResult(
            method=method_a,
            mu=12.0,
            sigma=0.6,
            distance=0.01,
            abs_d_mu=0.005,
            abs_d_sigma=0.005,
            rows_after_category=10,
            rows_after_status=10,
            rows_after_year=10,
            rows_used=10,
            trimmed_each_side=0,
        )
        row_b = MethodResult(
            method=method_b,
            mu=12.0,
            sigma=0.6,
            distance=0.01,
            abs_d_mu=0.005,
            abs_d_sigma=0.005,
            rows_after_category=10,
            rows_after_status=10,
            rows_after_year=10,
            rows_used=10,
            trimmed_each_side=0,
        )
        ranked = rank_method_results([row_b, row_a])
        self.assertEqual(ranked[0].method.method_id, min(method_a.method_id, method_b.method_id))
        self.assertEqual(ranked[1].method.method_id, max(method_a.method_id, method_b.method_id))

    def test_filter_logic_counts_rows(self) -> None:
        rows = [
            PpdRow(price=100000.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=150000.0, transfer_year=2012, ppd_category_type="B", record_status="A"),
            PpdRow(price=200000.0, transfer_year=2011, ppd_category_type="A", record_status="D"),
        ]
        method = MethodSpec(
            category_mode="a_only",
            status_mode="a_only",
            year_mode="transfer_year_equals_target",
            std_mode="sample",
            trim_fraction=0.0,
        )
        result = evaluate_method(
            rows,
            method=method,
            target_scale=0.0,
            target_shape=0.0,
            target_year=2011,
        )
        self.assertEqual(result.rows_after_category, 2)
        self.assertEqual(result.rows_after_status, 1)
        self.assertEqual(result.rows_after_year, 1)
        self.assertEqual(result.rows_used, 1)
        self.assertAlmostEqual(result.sigma, 0.0, places=12)

    def test_run_method_search_fails_when_no_results(self) -> None:
        with self.assertRaisesRegex(ValueError, "No method produced a valid estimate"):
            run_method_search(
                [],
                target_scale=12.0,
                target_shape=0.6,
                target_year=2011,
                parse_stats=PpdParseStats(),
            )

    def test_trim_fraction_removes_symmetric_tails(self) -> None:
        rows = [
            PpdRow(price=10.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=20.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=30.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=40.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=50.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=60.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=70.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=80.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=90.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
            PpdRow(price=100.0, transfer_year=2011, ppd_category_type="A", record_status="A"),
        ]
        method = MethodSpec(
            category_mode="all",
            status_mode="all",
            year_mode="all_rows",
            std_mode="population",
            trim_fraction=0.1,
        )
        result = evaluate_method(
            rows,
            method=method,
            target_scale=0.0,
            target_shape=0.0,
            target_year=2011,
        )
        self.assertEqual(result.trimmed_each_side, 1)
        self.assertEqual(result.rows_used, 8)


if __name__ == "__main__":
    unittest.main()
