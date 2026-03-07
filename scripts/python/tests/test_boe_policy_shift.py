#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the BoE policy-story demo workflow.

@author: Max Stoddard
"""

from __future__ import annotations

import json
import math
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.python.experiments.model.policy_story_catalog import (
    PolicyStoryDefinition,
    StorySource,
    get_policy_story_catalog,
    story_binding_by_version,
    story_binding_details,
    story_method_audit,
)
from scripts.python.experiments.model.boe_policy_story_demo import (
    build_arg_parser,
    build_reproduce_command,
    clear_previous_story_artifacts,
    finalize_output_dir,
    load_story_ids_from_smoke_selection,
    resolve_run_output_dir,
    seed_final_run_caches_from_previous_output,
)
from scripts.python.experiments.model.policy_story_evidence import StoryRecommendation
from scripts.python.experiments.model.policy_story_reporting import (
    _configure_panel_x_axis,
    _figure_story_title,
    VERSION_LABELS,
    ci_ranges_do_not_overlap,
    find_headline_annotation,
    plot_story_figure,
    plot_story_split_figures,
    write_binding_validation_json,
)
from scripts.python.experiments.model.policy_story_scoring import (
    SeriesDiagnostics,
    StoryScore,
    build_selection_results,
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
    run_story_sweep,
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

    def test_aligned_points_co_move_linked_bank_constraints(self) -> None:
        catalog = {story.story_id: story for story in get_policy_story_catalog()}
        expectations = {
            "ftb_ltv_cap": "BANK_LTV_HARD_MAX_FTB",
            "hm_ltv_cap": "BANK_LTV_HARD_MAX_HM",
            "affordability_cap": "BANK_AFFORDABILITY_HARD_MAX",
            "btl_icr_cap": "BANK_ICR_HARD_MIN",
        }

        for story_id, bank_key in expectations.items():
            story = catalog[story_id]
            for point in story.build_points("final", aligned=True):
                self.assertEqual(point.updates[story.swept_keys[0]], point.updates[bank_key])

    def test_affordability_story_uses_revised_screen_and_final_grids(self) -> None:
        story = {
            item.story_id: item for item in get_policy_story_catalog()
        }["affordability_cap"]

        screen_points = story.build_points("screen", aligned=True)
        final_points = story.build_points("final", aligned=True)

        self.assertEqual([point.label for point in screen_points], ["0.25", "0.32", "0.4"])
        self.assertEqual(
            [point.label for point in final_points],
            ["0.26", "0.28", "0.3", "0.32", "0.34", "0.36", "0.38"],
        )
        self.assertEqual([point.label for point in final_points if point.is_baseline], ["0.32"])

    def test_cli_defaults_match_dense_v41_contract(self) -> None:
        args = build_arg_parser().parse_args([])

        self.assertEqual(args.final_seeds, "1,2,3,4,5,6")
        self.assertEqual(args.workers, 20)
        self.assertEqual(args.output_dir, "tmp/boe_policy_story_demo_v41")
        self.assertEqual(args.reuse_output_dir, [])
        self.assertEqual(args.selection_policy, "ranking_only")
        self.assertEqual(
            args.smoke_selection,
            "tmp/boe_policy_story_demo_v41_smoke/selected_stories.json",
        )

    def test_cli_accepts_repeated_reuse_output_dirs(self) -> None:
        args = build_arg_parser().parse_args(
            [
                "--reuse-output-dir",
                "tmp/boe_policy_story_demo_v41_2",
                "--reuse-output-dir",
                "tmp/boe_policy_story_demo_v41",
            ]
        )

        self.assertEqual(
            args.reuse_output_dir,
            ["tmp/boe_policy_story_demo_v41_2", "tmp/boe_policy_story_demo_v41"],
        )

    def test_build_reproduce_command_includes_reuse_output_dir_and_story_ids(self) -> None:
        args = build_arg_parser().parse_args(
            [
                "--output-dir",
                "tmp/boe_policy_story_demo_v41_2",
                "--reuse-output-dir",
                "tmp/boe_policy_story_demo_v41_2",
                "--reuse-output-dir",
                "tmp/boe_policy_story_demo_v41",
                "--story-ids",
                "affordability_cap,lti_flow_limit_bundle",
                "--versions",
                "v0,v4.1",
                "--final-seeds",
                "1,2,3,4,5,6",
                "--workers",
                "20",
            ]
        )

        self.assertEqual(
            build_reproduce_command(args),
            "python3 -m scripts.python.experiments.model.boe_policy_story_demo \\\n"
            "  --output-dir tmp/boe_policy_story_demo_v41_2 \\\n"
            "  --reuse-output-dir tmp/boe_policy_story_demo_v41_2 \\\n"
            "  --reuse-output-dir tmp/boe_policy_story_demo_v41 \\\n"
            "  --story-ids affordability_cap,lti_flow_limit_bundle \\\n"
            "  --versions v0,v4.1 \\\n"
            "  --final-seeds 1,2,3,4,5,6 \\\n"
            "  --workers 20\n",
        )

    def test_resolve_run_output_dir_uses_staging_when_output_is_reuse_source(self) -> None:
        runtime_output_dir, uses_staging = resolve_run_output_dir(
            Path("tmp/boe_policy_story_demo_v41_2"),
            [
                Path("tmp/boe_policy_story_demo_v41_2"),
                Path("tmp/boe_policy_story_demo_v41"),
            ],
        )

        self.assertTrue(uses_staging)
        self.assertEqual(runtime_output_dir, Path("tmp/boe_policy_story_demo_v41_2__staging"))

    def test_finalize_output_dir_swaps_staging_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            requested_output_dir = root / "boe_policy_story_demo_v41_2"
            runtime_output_dir = root / "boe_policy_story_demo_v41_2__staging"
            requested_output_dir.mkdir()
            runtime_output_dir.mkdir()
            (requested_output_dir / "old.txt").write_text("old\n", encoding="utf-8")
            (runtime_output_dir / "new.txt").write_text("new\n", encoding="utf-8")

            finalize_output_dir(
                requested_output_dir=requested_output_dir,
                runtime_output_dir=runtime_output_dir,
                used_staging=True,
            )

            self.assertTrue((requested_output_dir / "new.txt").exists())
            self.assertFalse((requested_output_dir / "old.txt").exists())
            self.assertFalse(runtime_output_dir.exists())

    def test_load_story_ids_from_smoke_selection_uses_canonical_shortlist(self) -> None:
        payload = {
            "canonical_policy": "ranking_only",
            "selected_stories": [
                {"story_id": "ftb_ltv_cap"},
                {"story_id": "affordability_cap"},
            ],
            "selection_results": {
                "ranking_only": [
                    {"story_id": "ftb_ltv_cap"},
                    {"story_id": "affordability_cap"},
                ]
            },
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            selection_path = Path(tmp_dir) / "selected_stories.json"
            selection_path.write_text(json.dumps(payload), encoding="utf-8")

            story_ids = load_story_ids_from_smoke_selection(selection_path)

        self.assertEqual(story_ids, ["ftb_ltv_cap", "affordability_cap"])

    def test_story_method_audit_flags_raw_ftb_masking_and_base_rate_exclusion(self) -> None:
        catalog = {story.story_id: story for story in get_policy_story_catalog()}

        ftb_audit = story_method_audit(
            catalog["ftb_ltv_cap"],
            repo_root=self.repo_root,
            versions=("v0", "v4.1"),
        )
        base_rate_audit = story_method_audit(
            catalog["base_rate"],
            repo_root=self.repo_root,
            versions=("v0", "v4.1"),
        )

        self.assertTrue(ftb_audit.versions["v0"].raw_has_conflict)
        self.assertTrue(ftb_audit.versions["v0"].aligned_resolves_conflict)
        self.assertTrue(ftb_audit.shortlist_eligible)
        self.assertFalse(base_rate_audit.shortlist_eligible)
        self.assertEqual(base_rate_audit.effective_rule, "structurally_weak")

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

    def test_ranking_only_selector_does_not_hard_include_affordability(self) -> None:
        catalog = {story.story_id: story for story in get_policy_story_catalog()}
        placeholder = SeriesDiagnostics(monotonicity=1.0, linear_r2=0.95, max_slope_jump=0.1, kink_index=None)

        def make_score(story_id: str, total_score: float) -> StoryScore:
            story = catalog[story_id]
            return StoryScore(
                story_id=story.story_id,
                title=story.title,
                primary_indicator_id=story.primary_outputs[0],
                secondary_indicator_id=story.secondary_outputs[0] if story.secondary_outputs else None,
                primary_effect_score=3.0,
                secondary_effect_score=2.0,
                shape_score=1.0,
                uncertainty_penalty=0.2,
                narrative_weight=story.narrative_weight,
                total_score=total_score,
                passes_minimum_robustness=True,
                interpretation="ranking-only test",
                primary_gap_at_best_point=2.0,
                best_point_label="0.15",
                diagnostics_v0=placeholder,
                diagnostics_v4=placeholder,
            )

        scores = [
            make_score("lti_flow_limit_bundle", 9.0),
            make_score("ftb_ltv_cap", 8.0),
            make_score("affordability_cap", 1.5),
        ]

        selected = select_stories(scores, list(catalog.values()), policy="ranking_only")

        self.assertEqual([score.story_id for score in selected], ["lti_flow_limit_bundle", "ftb_ltv_cap"])

    def test_build_selection_results_compare_both_includes_legacy_and_ranking_outputs(self) -> None:
        catalog = list(get_policy_story_catalog())
        placeholder = SeriesDiagnostics(monotonicity=1.0, linear_r2=0.95, max_slope_jump=0.1, kink_index=None)

        def make_score(story_id: str, total_score: float) -> StoryScore:
            story = next(item for item in catalog if item.story_id == story_id)
            return StoryScore(
                story_id=story.story_id,
                title=story.title,
                primary_indicator_id=story.primary_outputs[0],
                secondary_indicator_id=story.secondary_outputs[0] if story.secondary_outputs else None,
                primary_effect_score=3.0,
                secondary_effect_score=2.0,
                shape_score=1.0,
                uncertainty_penalty=0.2,
                narrative_weight=story.narrative_weight,
                total_score=total_score,
                passes_minimum_robustness=True,
                interpretation="compare-both test",
                primary_gap_at_best_point=2.0,
                best_point_label="0.15",
                diagnostics_v0=placeholder,
                diagnostics_v4=placeholder,
            )

        scores = [
            make_score("lti_flow_limit_bundle", 9.0),
            make_score("ftb_ltv_cap", 8.0),
            make_score("affordability_cap", 7.0),
        ]

        selection_results = build_selection_results(scores, catalog, selection_policy="compare_both")

        self.assertEqual(set(selection_results.keys()), {"demo_legacy", "ranking_only"})
        self.assertEqual(selection_results["demo_legacy"][0].story_id, "affordability_cap")
        self.assertEqual(selection_results["ranking_only"][0].story_id, "lti_flow_limit_bundle")

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
            title="Synthetic Story (Aligned Bank + Central-Bank Limit)",
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
        self.assertEqual(_figure_story_title(story.title), "Synthetic Story")

        axis = mock.Mock()
        _configure_panel_x_axis(axis, aggregated)
        axis.set_xticks.assert_called_once_with([0.75, 0.85, 0.95])
        axis.set_xticklabels.assert_called_once_with(["0.75", "0.85", "0.95"])

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            combined_path = output_dir / "story_1_synthetic_story.png"
            with mock.patch(
                "matplotlib.axes._axes.Axes.annotate",
                side_effect=AssertionError("annotate should not be called"),
            ):
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

    def test_seed_final_run_caches_from_previous_output_prefers_first_source_and_falls_back_to_second(self) -> None:
        story = {
            item.story_id: item for item in get_policy_story_catalog()
        }["affordability_cap"]
        preferred_point = next(
            point for point in story.build_points("final", aligned=True) if point.label == "0.34"
        )
        fallback_point = next(
            point for point in story.build_points("final", aligned=True) if point.label == "0.26"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            preferred_output_dir = repo_root / "preferred_output"
            fallback_output_dir = repo_root / "fallback_output"
            final_root = repo_root / "new_output" / "final"

            self._write_reusable_run_cache(
                output_dir=preferred_output_dir,
                story_id=story.story_id,
                version="v4.1",
                seed=1,
                point_id="point_04_0p34",
                point_label="0.34",
                point_index=4,
                x_value=0.34,
                is_baseline=False,
                marker="preferred\n",
            )
            self._write_reusable_run_cache(
                output_dir=fallback_output_dir,
                story_id=story.story_id,
                version="v4.1",
                seed=1,
                point_id="point_04_0p34",
                point_label="0.34",
                point_index=4,
                x_value=0.34,
                is_baseline=False,
                marker="fallback-overlap\n",
            )
            self._write_reusable_run_cache(
                output_dir=fallback_output_dir,
                story_id=story.story_id,
                version="v4.1",
                seed=1,
                point_id="point_00_0p26",
                point_label="0.26",
                point_index=0,
                x_value=0.26,
                is_baseline=False,
                marker="fallback-only\n",
            )

            reused = seed_final_run_caches_from_previous_output(
                repo_root=repo_root,
                reuse_output_dirs=[preferred_output_dir, fallback_output_dir],
                final_root=final_root,
                stories=[story],
                versions=["v4.1"],
                final_seeds=[1],
            )

            preferred_target_run_dir = (
                final_root
                / story.story_id
                / "runs"
                / "final"
                / "v4.1"
                / "seed-1"
                / preferred_point.point_id
            )
            preferred_target_config_path = (
                final_root
                / story.story_id
                / "configs"
                / "final"
                / "v4.1"
                / f"{preferred_point.point_id}-seed-1.properties"
            )
            fallback_target_run_dir = (
                final_root
                / story.story_id
                / "runs"
                / "final"
                / "v4.1"
                / "seed-1"
                / fallback_point.point_id
            )
            payload = json.loads(
                (preferred_target_run_dir / "run_metrics.json").read_text(encoding="utf-8")
            )

            self.assertEqual(reused, 2)
            self.assertTrue(preferred_target_run_dir.exists())
            self.assertTrue(preferred_target_config_path.exists())
            self.assertTrue(fallback_target_run_dir.exists())
            self.assertEqual(payload["point_id"], preferred_point.point_id)
            self.assertEqual(payload["point_index"], preferred_point.point_index)
            self.assertEqual(payload["point_label"], preferred_point.label)
            self.assertEqual(payload["x_value"], preferred_point.x_value)
            self.assertEqual(payload["updates"], preferred_point.updates)
            self.assertEqual(payload["output_dir"], str(preferred_target_run_dir))
            self.assertEqual(payload["config_path"], str(preferred_target_config_path))
            self.assertEqual(
                (preferred_target_run_dir / "Output-run1.csv").read_text(encoding="utf-8"),
                "preferred\n",
            )
            self.assertEqual(
                (fallback_target_run_dir / "Output-run1.csv").read_text(encoding="utf-8"),
                "fallback-only\n",
            )

    def test_binding_validation_json_contains_story_binding_by_version(self) -> None:
        stories = get_policy_story_catalog()
        binding_details = {
            story.story_id: story_binding_details(
                story,
                repo_root=self.repo_root,
                versions=("v0", "v4.1"),
            )
            for story in stories
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "story_binding_validation.json"
            write_binding_validation_json(
                output_path,
                stories=stories,
                binding_details=binding_details,
                versions=("v0", "v4.1"),
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["versions"], ["v0", "v4.1"])
        self.assertEqual(len(payload["stories"]), len(stories))
        self.assertIn("binding_by_version", payload["stories"][0])
        self.assertIn("v4.1", payload["stories"][0]["binding_by_version"])

    def test_run_story_sweep_prints_progress_and_eta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            output_root = repo_root / "out"
            points = [
                mock.Mock(point_id="point_00", point_index=0, label="0.75", x_value=0.75, updates={}, is_baseline=False),
                mock.Mock(point_id="point_01", point_index=1, label="0.85", x_value=0.85, updates={}, is_baseline=True),
            ]
            fake_results = [
                mock.Mock(version="v0", seed=1, point_index=0, point_label="0.75", cached=False),
                mock.Mock(version="v0", seed=1, point_index=1, point_label="0.85", cached=True),
            ]
            fake_aggregated = mock.Mock()

            with mock.patch(
                "scripts.python.helpers.common.abm_policy_sweep._execute_run_request",
                side_effect=fake_results,
            ), mock.patch(
                "scripts.python.helpers.common.abm_policy_sweep.aggregate_story_results",
                return_value=fake_aggregated,
            ), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                run_results, aggregated = run_story_sweep(
                    repo_root=repo_root,
                    output_root=output_root,
                    stage_name="screen",
                    story_id="ftb_ltv_cap",
                    versions=("v0",),
                    seeds=(1,),
                    points=points,
                    indicator_ids=("core_advancesToFTB",),
                    workers=1,
                    force_rerun=False,
                )

            output = stdout.getvalue()
        self.assertEqual(len(run_results), 2)
        self.assertIs(aggregated, fake_aggregated)
        self.assertIn("[policy-sweep] start stage=screen story=ftb_ltv_cap", output)
        self.assertIn("progress=1/2 (50.0%)", output)
        self.assertIn("eta=", output)
        self.assertIn("[cached]", output)
        self.assertIn("[policy-sweep] done stage=screen story=ftb_ltv_cap", output)

    def test_main_screen_only_ranking_only_does_not_run_final_stage(self) -> None:
        catalog = get_policy_story_catalog()
        placeholder = SeriesDiagnostics(monotonicity=1.0, linear_r2=0.95, max_slope_jump=0.1, kink_index=None)

        def make_score(story: PolicyStoryDefinition, total_score: float) -> StoryScore:
            return StoryScore(
                story_id=story.story_id,
                title=story.title,
                primary_indicator_id=story.primary_outputs[0],
                secondary_indicator_id=story.secondary_outputs[0] if story.secondary_outputs else None,
                primary_effect_score=3.0,
                secondary_effect_score=2.0,
                shape_score=1.0,
                uncertainty_penalty=0.2,
                narrative_weight=story.narrative_weight,
                total_score=total_score,
                passes_minimum_robustness=True,
                interpretation=f"{story.title} test interpretation.",
                primary_gap_at_best_point=2.0,
                best_point_label="0.15",
                diagnostics_v0=placeholder,
                diagnostics_v4=placeholder,
            )

        fake_scores = [make_score(story, float(index + 1)) for index, story in enumerate(catalog)]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "screen_only"
            with mock.patch("scripts.python.experiments.model.boe_policy_story_demo.ensure_project_compiled"), mock.patch(
                "scripts.python.experiments.model.boe_policy_story_demo.run_screening_stage",
                return_value=([], fake_scores),
            ), mock.patch(
                "scripts.python.experiments.model.boe_policy_story_demo.run_final_stage",
                side_effect=AssertionError("run_final_stage should not be called for --screen-only"),
            ), mock.patch(
                "scripts.python.experiments.model.boe_policy_story_demo.recommend_story",
                return_value=StoryRecommendation(
                    story_id="ftb_ltv_cap",
                    title="First-Time Buyer LTV Cap",
                    blended_score=0.9,
                    model_score=2.0,
                    model_score_normalized=1.0,
                    evidence_strength=0.95,
                    rationale="test recommendation",
                    caveat="test caveat",
                ),
            ), mock.patch.object(
                sys,
                "argv",
                [
                    "boe_policy_story_demo.py",
                    "--screen-only",
                    "--selection-policy",
                    "ranking_only",
                    "--output-dir",
                    str(output_dir),
                ],
            ):
                from scripts.python.experiments.model import boe_policy_story_demo

                boe_policy_story_demo.main()

            self.assertTrue((output_dir / "selected_stories.json").exists())
            self.assertTrue((output_dir / "story_method_audit.json").exists())
            self.assertTrue((output_dir / "story_binding_validation.json").exists())
            self.assertTrue((output_dir / "story_evidence_review.md").exists())
            self.assertTrue((output_dir / "story_recommendation.md").exists())
            self.assertFalse((output_dir / "final").exists())
            selected_payload = json.loads((output_dir / "selected_stories.json").read_text(encoding="utf-8"))
            selected_ids = [item["story_id"] for item in selected_payload["selected_stories"]]
            self.assertNotIn("base_rate", selected_ids)

    def test_main_dense_run_uses_smoke_selection_without_screening(self) -> None:
        fake_aggregated = {
            "ftb_ltv_cap": self._build_story_specific_aggregated_results(
                "ftb_ltv_cap",
                primary_indicator="core_advancesToFTB",
                secondary_indicator="core_debtToIncome",
            ),
            "affordability_cap": self._build_story_specific_aggregated_results(
                "affordability_cap",
                primary_indicator="core_debtToIncome",
                secondary_indicator="core_priceToIncome",
            ),
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            smoke_selection = tmp_path / "selected_stories.json"
            smoke_selection.write_text(
                json.dumps(
                    {
                        "canonical_policy": "ranking_only",
                        "selected_stories": [
                            {"story_id": "ftb_ltv_cap"},
                            {"story_id": "affordability_cap"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            output_dir = tmp_path / "dense"
            output_dir.mkdir()
            (output_dir / "old.txt").write_text("old\n", encoding="utf-8")
            fallback_output_dir = tmp_path / "old_output"

            with mock.patch("scripts.python.experiments.model.boe_policy_story_demo.ensure_project_compiled") as compile_mock, mock.patch(
                "scripts.python.experiments.model.boe_policy_story_demo.run_screening_stage",
                side_effect=AssertionError("run_screening_stage should not be called when smoke selection is supplied"),
            ), mock.patch(
                "scripts.python.experiments.model.boe_policy_story_demo.run_final_stage",
                return_value=fake_aggregated,
            ) as run_final_mock, mock.patch(
                "scripts.python.experiments.model.boe_policy_story_demo.seed_final_run_caches_from_previous_output",
                return_value=3,
            ) as reuse_mock, mock.patch.object(
                sys,
                "argv",
                [
                    "boe_policy_story_demo.py",
                    "--output-dir",
                    str(output_dir),
                    "--reuse-output-dir",
                    str(output_dir),
                    "--reuse-output-dir",
                    str(fallback_output_dir),
                    "--smoke-selection",
                    str(smoke_selection),
                ],
            ):
                from scripts.python.experiments.model import boe_policy_story_demo

                boe_policy_story_demo.main()

            compile_mock.assert_called_once()
            run_final_mock.assert_called_once()
            reuse_mock.assert_called_once()
            reproduce_command = (output_dir / "reproduce_command.txt").read_text(
                encoding="utf-8"
            )
            self.assertIn("--reuse-output-dir", reproduce_command)
            self.assertIn(f"--reuse-output-dir {output_dir}", reproduce_command)
            self.assertIn(f"--reuse-output-dir {fallback_output_dir}", reproduce_command)
            self.assertIn("--story-ids ftb_ltv_cap,affordability_cap", reproduce_command)
            self.assertFalse((output_dir / "old.txt").exists())
            self.assertFalse((tmp_path / "dense__staging").exists())

            selected_payload = json.loads((output_dir / "selected_stories.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [item["story_id"] for item in selected_payload["selected_stories"]],
                ["ftb_ltv_cap", "affordability_cap"],
            )

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

    def _build_story_specific_aggregated_results(
        self,
        story_id: str,
        *,
        primary_indicator: str,
        secondary_indicator: str,
    ) -> AggregatedStoryResults:
        return AggregatedStoryResults(
            stage_name="final",
            story_id=story_id,
            versions={
                "v0": [
                    self._make_story_specific_point(
                        "0.75",
                        0.75,
                        False,
                        primary_indicator,
                        -1.0,
                        secondary_indicator,
                        -0.4,
                    ),
                    self._make_story_specific_point(
                        "0.85",
                        0.85,
                        True,
                        primary_indicator,
                        0.0,
                        secondary_indicator,
                        0.0,
                    ),
                    self._make_story_specific_point(
                        "0.95",
                        0.95,
                        False,
                        primary_indicator,
                        0.6,
                        secondary_indicator,
                        0.2,
                    ),
                ],
                "v4.1": [
                    self._make_story_specific_point(
                        "0.75",
                        0.75,
                        False,
                        primary_indicator,
                        -4.0,
                        secondary_indicator,
                        -0.2,
                    ),
                    self._make_story_specific_point(
                        "0.85",
                        0.85,
                        True,
                        primary_indicator,
                        0.0,
                        secondary_indicator,
                        0.0,
                    ),
                    self._make_story_specific_point(
                        "0.95",
                        0.95,
                        False,
                        primary_indicator,
                        0.8,
                        secondary_indicator,
                        0.5,
                    ),
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

    def _make_story_specific_point(
        self,
        label: str,
        x_value: float,
        is_baseline: bool,
        primary_indicator: str,
        primary_delta: float,
        secondary_indicator: str,
        secondary_delta: float,
    ) -> AggregatedPoint:
        indicators = {
            primary_indicator: self._indicator_bundle(primary_delta),
            secondary_indicator: self._indicator_bundle(secondary_delta),
        }
        if "core_mortgageApprovals" not in indicators:
            indicators["core_mortgageApprovals"] = self._indicator_bundle(0.1)
        if "core_priceToIncome" not in indicators:
            indicators["core_priceToIncome"] = self._indicator_bundle(0.2)
        if "core_debtToIncome" not in indicators:
            indicators["core_debtToIncome"] = self._indicator_bundle(0.3)
        if "core_advancesToFTB" not in indicators:
            indicators["core_advancesToFTB"] = self._indicator_bundle(0.4)

        return AggregatedPoint(
            point_id=f"point_{label}",
            point_index=int(round(x_value * 100)),
            label=label,
            x_value=x_value,
            updates={"SYNTHETIC_KEY": label},
            is_baseline=is_baseline,
            indicators=indicators,
            delta_indicators=indicators,
        )

    def _write_reusable_run_cache(
        self,
        *,
        output_dir: Path,
        story_id: str,
        version: str,
        seed: int,
        point_id: str,
        point_label: str,
        point_index: int,
        x_value: float,
        is_baseline: bool,
        marker: str,
    ) -> None:
        story_root = output_dir / "final" / story_id
        run_dir = story_root / "runs" / "final" / version / f"seed-{seed}" / point_id
        config_path = story_root / "configs" / "final" / version / f"{point_id}-seed-{seed}.properties"
        run_dir.mkdir(parents=True, exist_ok=True)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        (run_dir / "Output-run1.csv").write_text(marker, encoding="utf-8")
        config_path.write_text("SEED = 1\n", encoding="utf-8")
        payload = {
            "stage_name": "final",
            "story_id": story_id,
            "version": version,
            "seed": seed,
            "point_id": point_id,
            "point_index": point_index,
            "point_label": point_label,
            "x_value": x_value,
            "updates": {"TEST_KEY": point_label},
            "is_baseline": is_baseline,
            "output_dir": str(run_dir),
            "config_path": str(config_path),
            "cached": False,
            "indicators": {
                "core_debtToIncome": {
                    "mean": 1.0,
                    "cv": None,
                    "annualised_trend": None,
                    "range": None,
                }
            },
            "kpi_window": {
                "mode": "post_burn_in_slice",
                "start_index": 200,
                "end_index": 2000,
            },
        }
        (run_dir / "run_metrics.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
