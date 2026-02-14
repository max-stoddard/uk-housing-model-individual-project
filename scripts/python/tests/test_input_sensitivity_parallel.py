from __future__ import annotations

import unittest

from scripts.python.experiments.was.input_sensitivity_parallel import (
    build_stage_a_scenarios,
    choose_workers,
    deterministic_parse_check,
    extract_single_param_value,
    is_recoverable_resource_error,
    make_stage_c_scenarios,
    parse_validation_diffs,
    retry_path_check,
)


class TestInputSensitivityParallel(unittest.TestCase):
    def test_stage_a_builds_expected_two_point_matrix(self) -> None:
        scenarios = build_stage_a_scenarios()
        self.assertEqual(len(scenarios), 18)
        ids = {scenario.scenario_id for scenario in scenarios}
        self.assertEqual(len(ids), 18)

    def test_worker_formula_matches_expected_example(self) -> None:
        result = choose_workers(
            nproc=20,
            mem_available_gib=12.0,
            rss_probe_gib=0.49,
            cpu_reserve=2,
            mem_reserve_gib=3.0,
            rss_multiplier=1.8,
            max_workers_cap=12,
        )
        self.assertEqual(result["cpu_cap"], 18)
        self.assertEqual(result["mem_cap"], 10)
        self.assertEqual(result["workers"], 10)

    def test_validation_parsing_is_deterministic(self) -> None:
        text = (
            "Income total diff: 6.615492 %\n"
            "Housing wealth total diff: 26.760137 %\n"
            "Financial wealth total diff: 11.890496 %\n"
        )
        parsed = parse_validation_diffs(text)
        self.assertEqual(parsed["income_diff"], 6.615492)
        self.assertEqual(parsed["housing_diff"], 26.760137)
        self.assertEqual(parsed["financial_diff"], 11.890496)
        self.assertTrue(deterministic_parse_check())

    def test_retry_classifier_recognises_resource_failures(self) -> None:
        self.assertTrue(is_recoverable_resource_error("java.lang.OutOfMemoryError: Java heap space"))
        self.assertTrue(is_recoverable_resource_error("Process killed with exit code 137"))
        self.assertFalse(is_recoverable_resource_error("Validation parsing failed"))
        self.assertTrue(retry_path_check())

    def test_stage_c_uses_raw_values_not_key_value_tokens(self) -> None:
        rows = [
            {
                "status": "success",
                "parameter": "BUY_EXPONENT",
                "housing_diff": 17.0,
                "direction": "high",
                "updated_value": "BUY_EXPONENT=0.86808645",
            },
            {
                "status": "success",
                "parameter": "BUY_EXPONENT",
                "housing_diff": 71.0,
                "direction": "low",
                "updated_value": "BUY_EXPONENT=0.71025255",
            },
            {
                "status": "success",
                "parameter": "HPA_EXPECTATION_FACTOR",
                "housing_diff": 26.0,
                "direction": "high",
                "updated_value": "HPA_EXPECTATION_FACTOR=0.528",
            },
            {
                "status": "success",
                "parameter": "HPA_EXPECTATION_FACTOR",
                "housing_diff": 36.0,
                "direction": "low",
                "updated_value": "HPA_EXPECTATION_FACTOR=0.352",
            },
        ]
        value = extract_single_param_value(rows[0], "BUY_EXPONENT")
        self.assertEqual(value, "0.86808645")

        scenarios = make_stage_c_scenarios(["BUY_EXPONENT", "HPA_EXPECTATION_FACTOR"], rows)
        self.assertEqual(scenarios[0].updates["BUY_EXPONENT"], "0.86808645")
        self.assertEqual(scenarios[0].updates["HPA_EXPECTATION_FACTOR"], "0.528")
        self.assertEqual(scenarios[1].updates["BUY_EXPONENT"], "0.71025255")
        self.assertEqual(scenarios[1].updates["HPA_EXPECTATION_FACTOR"], "0.352")


if __name__ == "__main__":
    unittest.main()
