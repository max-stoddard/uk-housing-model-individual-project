#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the BoE policy-story demo workflow.

@author: Max Stoddard
"""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from scripts.python.experiments.model.policy_story_catalog import (
    PolicyStoryDefinition,
    StorySource,
    get_policy_story_catalog,
    story_binding_by_version,
)
from scripts.python.experiments.model.boe_policy_story_demo import clear_previous_story_artifacts
from scripts.python.experiments.model.policy_story_reporting import (
    VERSION_LABELS,
    ci_ranges_do_not_overlap,
    find_headline_annotation,
    plot_story_figure,
    plot_story_split_figures,
)
from scripts.python.experiments.model.policy_story_scoring import (
    SeriesDiagnostics,
    StoryScore,
    compute_series_diagnostics,
    compute_shape_score,
    resolve_story_versions,
    select_stories,
)
from scripts.python.helpers.common.abm_policy_sweep import (
    AggregateStat,
    AggregatedIndicator,
    AggregatedPoint,
    AggregatedStoryResults,
    SLIM_RECORDING_OVERRIDES,
    build_snapshot_local_config_text,
    compute_indicator_kpis,
    rewrite_version_resource_paths,
    select_post_burn_in_window,
)


class TestBoePolicyShift(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[3]

    def test_rewrite_version_resource_paths_only_updates_existing_snapshot_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            version_dir = Path(tmp_dir)
            existing = version_dir / "Age9-Weighted.csv"
            existing.write_text("header\n1\n", encoding="utf-8")
            config_text = (
                'DATA_AGE_DISTRIBUTION = "src/main/resources/Age9-Weighted.csv"\n'
                'DATA_UNKNOWN = "src/main/resources/Missing.csv"\n'
            )

            rewritten = rewrite_version_resource_paths(config_text, version_dir)

            self.assertIn(f'"{existing}"', rewritten)
            self.assertIn('"src/main/resources/Missing.csv"', rewritten)

    def test_build_snapshot_local_config_slims_outputs_and_rewrites_known_paths(self) -> None:
        version_checks = {
            "v0": (
                "Age9-Weighted.csv",
                "BTLProbabilityPerIncomePercentileBin.csv",
                "InitialSaleMarkUpDist.csv",
                "InitialRentMarkUpDist.csv",
                "TaxRates.csv",
                "NationalInsuranceRates.csv",
            ),
            "v4.0": (
                "Age8-R8-Weighted.csv",
                "BTLProbabilityPerIncomePercentileBin-R8.csv",
                "InitialSaleMarkUpDist.csv",
                "InitialRentMarkUpDist.csv",
                "TaxRates.csv",
                "NationalInsuranceRates.csv",
            ),
            "v4.1": (
                "Age8-R8-Weighted.csv",
                "BTLProbabilityPerIncomePercentileBin-R8.csv",
                "InitialSaleMarkUpDist.csv",
                "InitialRentMarkUpDist.csv",
                "TaxRates.csv",
                "NationalInsuranceRates.csv",
            ),
        }

        for version, file_names in version_checks.items():
            config_path = self.repo_root / "input-data-versions" / version / "config.properties"
            rendered = build_snapshot_local_config_text(config_path, {})
            version_dir = config_path.parent

            for file_name in file_names:
                self.assertIn(f'"{version_dir / file_name}"', rendered)

            for key, value in SLIM_RECORDING_OVERRIDES.items():
                self.assertIn(f"{key} = {value}", rendered)

    def test_select_post_burn_in_window_uses_periods_200_to_2000(self) -> None:
        values = list(range(1, 2001))
        self.assertEqual(select_post_burn_in_window(values), values[200:2000])

    def test_compute_indicator_kpis_matches_post_burn_in_1800_math(self) -> None:
        values = list(range(1, 2001))
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            indicator_path = output_dir / "coreIndicator-priceToIncome.csv"
            indicator_path.write_text(";\n".join(str(value) for value in values) + "\n", encoding="utf-8")

            kpis = compute_indicator_kpis(output_dir, ["core_priceToIncome"])["core_priceToIncome"]

        selected_values = values[200:2000]
        expected_mean = sum(selected_values) / len(selected_values)
        expected_variance = sum((value - expected_mean) ** 2 for value in selected_values) / len(selected_values)
        expected_stdev = math.sqrt(expected_variance)
        expected_cv = expected_stdev / expected_mean
        expected_annualised_trend = 12.0
        expected_range = 1910.05 - 290.95

        self.assertIsNotNone(kpis.mean)
        self.assertIsNotNone(kpis.cv)
        self.assertIsNotNone(kpis.annualised_trend)
        self.assertIsNotNone(kpis.range)
        self.assertAlmostEqual(kpis.mean, expected_mean, places=9)
        self.assertAlmostEqual(kpis.cv, expected_cv, places=9)
        self.assertAlmostEqual(kpis.annualised_trend, expected_annualised_trend, places=9)
        self.assertAlmostEqual(kpis.range, expected_range, places=9)

    def test_candidate_grids_bind_in_v0_and_v41(self) -> None:
        for story in get_policy_story_catalog():
            binding = story_binding_by_version(
                story,
                repo_root=self.repo_root,
                versions=("v0", "v4.1"),
            )
            self.assertTrue(binding["v0"], msg=f"{story.story_id} should bind in v0")
            self.assertTrue(binding["v4.1"], msg=f"{story.story_id} should bind in v4.1")

    def test_curve_diagnostics_distinguish_linear_and_kinked_responses(self) -> None:
        x_values = [0.0, 1.0, 2.0, 3.0, 4.0]
        linear = compute_series_diagnostics(
            x_values=x_values,
            y_values=[0.0, 1.0, 2.0, 3.0, 4.0],
            expected_sign=1,
        )
        kinked = compute_series_diagnostics(
            x_values=x_values,
            y_values=[0.0, 1.0, 2.0, 5.5, 9.0],
            expected_sign=1,
        )

        self.assertGreater(linear.linear_r2, kinked.linear_r2)
        self.assertGreater(kinked.max_slope_jump, linear.max_slope_jump)
        self.assertGreater(compute_shape_score(linear, kinked), 1.0)

    def test_story_selector_hard_includes_affordability_before_fallback(self) -> None:
        catalog = {story.story_id: story for story in get_policy_story_catalog()}
        placeholder = SeriesDiagnostics(monotonicity=1.0, linear_r2=0.95, max_slope_jump=0.1, kink_index=None)

        def make_score(
            story_id: str,
            *,
            total_score: float,
            passes_minimum_robustness: bool,
            interpretation: str | None,
        ) -> StoryScore:
            story = catalog[story_id]
            return StoryScore(
                story_id=story.story_id,
                title=story.title,
                primary_indicator_id=story.primary_outputs[0],
                secondary_indicator_id=story.secondary_outputs[0] if story.secondary_outputs else None,
                primary_effect_score=3.0,
                secondary_effect_score=2.0,
                shape_score=1.0,
                uncertainty_penalty=0.9 if not passes_minimum_robustness else 0.2,
                narrative_weight=story.narrative_weight,
                total_score=total_score,
                passes_minimum_robustness=passes_minimum_robustness,
                interpretation=interpretation,
                primary_gap_at_best_point=2.0,
                best_point_label="0.15",
                diagnostics_v0=placeholder,
                diagnostics_v4=placeholder,
            )

        scores = [
            make_score(
                "affordability_cap",
                total_score=2.0,
                passes_minimum_robustness=True,
                interpretation="Robust affordability story.",
            ),
            make_score(
                "ftb_ltv_cap",
                total_score=0.4,
                passes_minimum_robustness=False,
                interpretation=None,
            ),
            make_score(
                "base_rate",
                total_score=9.0,
                passes_minimum_robustness=False,
                interpretation=None,
            ),
        ]

        selected = select_stories(scores, list(catalog.values()))

        self.assertEqual([score.story_id for score in selected], ["affordability_cap", "ftb_ltv_cap"])

    def test_version_labels_and_ci_non_overlap_annotation_are_human_facing(self) -> None:
        self.assertEqual(VERSION_LABELS["v0"], "Pre-2012 Calibration")
        self.assertEqual(VERSION_LABELS["v4.0"], "Post-2022 Calibration")
        self.assertEqual(VERSION_LABELS["v4.1"], "Post-2022 Calibration")

        left = AggregateStat(mean=-2.0, stdev=0.5, ci_low=-2.5, ci_high=-1.5, n=8)
        right = AggregateStat(mean=2.0, stdev=0.5, ci_low=1.5, ci_high=2.5, n=8)
        self.assertTrue(ci_ranges_do_not_overlap(left, right))

    def test_resolve_story_versions_supports_v41_as_modern_side(self) -> None:
        aggregated = self._build_synthetic_aggregated_results()
        self.assertEqual(resolve_story_versions(aggregated), ("v0", "v4.1"))

    def test_plotting_writes_combined_and_split_figures(self) -> None:
        story = PolicyStoryDefinition(
            story_id="synthetic_story",
            title="Synthetic Story",
            instrument_label="synthetic cap",
            description="Synthetic story used for chart tests.",
            axis_label="Synthetic axis",
            axis_units="ratio",
            fixed_updates={},
            swept_keys=("SYNTHETIC_KEY",),
            screen_values=(0.75, 0.85, 0.95),
            final_values=(0.75, 0.85, 0.95),
            baseline_value=0.85,
            primary_outputs=("core_advancesToFTB",),
            secondary_outputs=("core_priceToIncome",),
            figure_indicator_ids=("core_advancesToFTB", "core_priceToIncome", "core_mortgageApprovals"),
            figure_headline_indicator_id="core_advancesToFTB",
            expected_primary_direction=1,
            policy_relevance_weight=1.0,
            calibration_link_weight=1.0,
            fallback_rank=0,
            mechanism_summary="synthetic mechanism",
            recalibration_summary="synthetic recalibration",
            binding_checker=lambda _: True,
            sources=(StorySource(title="Synthetic", url="https://example.com", note="synthetic"),),
        )
        aggregated = self._build_synthetic_aggregated_results()
        annotation = find_headline_annotation(aggregated, "core_advancesToFTB")
        self.assertIsNotNone(annotation)
        self.assertEqual(annotation[2], "Strongest non-overlap at 0.75")

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            combined_path = output_dir / "story_1_synthetic_story.png"
            plot_story_figure(path=combined_path, story=story, aggregated=aggregated)
            plot_story_split_figures(
                path_prefix=output_dir / "story_1_synthetic_story",
                story=story,
                aggregated=aggregated,
            )

            self.assertTrue(combined_path.exists())
            self.assertTrue((output_dir / "story_1_synthetic_story__panel_1_core_advancesToFTB.png").exists())
            self.assertTrue((output_dir / "story_1_synthetic_story__panel_2_core_priceToIncome.png").exists())
            self.assertTrue((output_dir / "story_1_synthetic_story__panel_3_core_mortgageApprovals.png").exists())

    def test_clear_previous_story_artifacts_only_removes_top_level_story_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            removable = [
                output_dir / "story_1_lti_flow_limit_bundle.csv",
                output_dir / "story_1_lti_flow_limit_bundle.png",
                output_dir / "story_1_lti_flow_limit_bundle__panel_1_core_debtToIncome.png",
            ]
            keeper = [
                output_dir / "story_candidates_screen.csv",
                output_dir / "selected_stories.json",
                output_dir / "screen" / "lti_flow_limit_bundle" / "runs" / "cached.txt",
            ]
            for path in removable + keeper:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x\n", encoding="utf-8")

            clear_previous_story_artifacts(output_dir)

            for path in removable:
                self.assertFalse(path.exists())
            for path in keeper:
                self.assertTrue(path.exists())

    def _build_synthetic_aggregated_results(self) -> AggregatedStoryResults:
        return AggregatedStoryResults(
            stage_name="final",
            story_id="synthetic_story",
            versions={
                "v0": [
                    self._make_point("0.75", 0.75, False, -1.0, -0.4, -0.8),
                    self._make_point("0.85", 0.85, True, 0.0, 0.0, 0.0),
                    self._make_point("0.95", 0.95, False, 0.6, 0.2, 0.3),
                ],
                "v4.1": [
                    self._make_point("0.75", 0.75, False, -4.0, -0.2, -2.5),
                    self._make_point("0.85", 0.85, True, 0.0, 0.0, 0.0),
                    self._make_point("0.95", 0.95, False, 0.8, 0.5, 0.1),
                ],
            },
        )

    def _make_point(
        self,
        label: str,
        x_value: float,
        is_baseline: bool,
        ftb_delta: float,
        pti_delta: float,
        approvals_delta: float,
    ) -> AggregatedPoint:
        return AggregatedPoint(
            point_id=f"point_{label}",
            point_index=int(round(x_value * 100)),
            label=label,
            x_value=x_value,
            updates={"SYNTHETIC_KEY": label},
            is_baseline=is_baseline,
            indicators={
                "core_advancesToFTB": self._indicator_bundle(ftb_delta),
                "core_priceToIncome": self._indicator_bundle(pti_delta),
                "core_mortgageApprovals": self._indicator_bundle(approvals_delta),
            },
            delta_indicators={
                "core_advancesToFTB": self._indicator_bundle(ftb_delta),
                "core_priceToIncome": self._indicator_bundle(pti_delta),
                "core_mortgageApprovals": self._indicator_bundle(approvals_delta),
            },
        )

    def _indicator_bundle(self, mean_value: float) -> AggregatedIndicator:
        stat = AggregateStat(
            mean=mean_value,
            stdev=0.2,
            ci_low=mean_value - 0.4,
            ci_high=mean_value + 0.4,
            n=8,
        )
        return AggregatedIndicator(mean=stat, cv=None, annualised_trend=None, range=None)


if __name__ == "__main__":
    unittest.main()
