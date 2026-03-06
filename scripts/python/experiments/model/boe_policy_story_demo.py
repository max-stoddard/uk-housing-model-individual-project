#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screen, select, and visualise policy stories for the Bank of England demo.

Latest findings:
  - Cached rerun command: `scripts/model/run_boe_affordability_policy_story_demo.sh`
  - Re-aggregated `tmp/boe_policy_story_demo` from cached `v0` versus `v4.0` final runs using the fixed post-burn-in window covering periods `200:2000` (1800 observations).
  - Final selected stories in `tmp/boe_policy_story_demo` are `ftb_ltv_cap` and `affordability_cap`, labelled in outputs as `Pre-2012 Calibration` versus `Post-2022 Calibration`.
  - In the rebuilt final outputs, tightening the FTB LTV cap from `0.85` to `0.75` moved mortgage approvals by `-2898.614` in Post-2022 Calibration versus `-3752.817` in Pre-2012 Calibration, while tightening the affordability cap from `0.325` to `0.25` moved mortgage debt-to-income by `-13.480` versus `-7.324`.

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.python.experiments.model.policy_story_catalog import (
    PolicyStoryDefinition,
    eligible_stories_by_binding,
    get_policy_story_catalog,
    story_lookup,
)
from scripts.python.experiments.model.policy_story_reporting import (
    plot_story_figure,
    plot_story_split_figures,
    write_report_markdown,
    write_screen_summary_csv,
    write_screen_summary_json,
    write_selected_stories_json,
    write_sources_markdown,
    write_story_csv,
)
from scripts.python.experiments.model.policy_story_scoring import score_story_screening, select_stories
from scripts.python.helpers.common.abm_policy_sweep import AggregatedStoryResults, ensure_project_compiled, run_story_sweep
from scripts.python.helpers.common.paths import ensure_output_dir


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Policy-story sweep orchestrator for the BoE demo.",
    )
    parser.add_argument(
        "--versions",
        default="v0,v4.1",
        help="Comma-separated input-data versions to compare (default: v0,v4.1).",
    )
    parser.add_argument(
        "--screen-seeds",
        default="1,2,3,4",
        help="Comma-separated seeds used for story screening (default: 1,2,3,4).",
    )
    parser.add_argument(
        "--final-seeds",
        default="1,2,3,4,5,6,7,8",
        help="Comma-separated seeds used for final dense sweeps (default: 1,2,3,4,5,6,7,8).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Maximum parallel model runs (default: 8).",
    )
    parser.add_argument(
        "--output-dir",
        default="tmp/boe_policy_story_demo",
        help="Output directory for artifacts and temporary runs.",
    )
    parser.add_argument(
        "--story-ids",
        default=None,
        help="Optional comma-separated story ids to force, skipping automatic selection.",
    )
    parser.add_argument(
        "--screen-only",
        action="store_true",
        help="Run the screening stage only and stop after ranking candidates.",
    )
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help="Ignore cached run_metrics.json files and rerun model outputs.",
    )
    parser.add_argument(
        "--maven-bin",
        default="mvn",
        help="Maven executable to use (default: mvn).",
    )
    return parser


def parse_csv_list(raw: str) -> list[str]:
    values = [token.strip() for token in raw.split(",") if token.strip()]
    if not values:
        raise SystemExit("Expected a non-empty comma-separated list.")
    return values


def parse_seed_list(raw: str) -> list[int]:
    values = [int(token) for token in parse_csv_list(raw)]
    if any(value <= 0 for value in values):
        raise SystemExit("Seeds must be positive integers.")
    return values


def validate_versions(raw_versions: list[str]) -> list[str]:
    """Validate the fixed baseline-plus-modern comparison contract."""

    if len(raw_versions) != 2:
        raise SystemExit("This workflow requires exactly two versions: baseline `v0` and one modern snapshot.")
    if raw_versions[0] != "v0":
        raise SystemExit("This workflow requires `v0` as the first comparison version.")
    if raw_versions[1] == "v0":
        raise SystemExit("The second comparison version must be a modern snapshot, not `v0`.")
    return raw_versions


def select_catalog_subset(
    all_stories: list[PolicyStoryDefinition],
    requested_story_ids: list[str] | None,
) -> list[PolicyStoryDefinition]:
    if requested_story_ids is None:
        return all_stories
    lookup = story_lookup(all_stories)
    missing = [story_id for story_id in requested_story_ids if story_id not in lookup]
    if missing:
        raise SystemExit(f"Unknown story ids: {missing}")
    return [lookup[story_id] for story_id in requested_story_ids]


def run_screening_stage(
    *,
    repo_root: Path,
    screen_root: Path,
    stories: list[PolicyStoryDefinition],
    versions: list[str],
    screen_seeds: list[int],
    workers: int,
    force_rerun: bool,
    maven_bin: str,
) -> tuple[list[tuple[PolicyStoryDefinition, AggregatedStoryResults]], list]:
    screening_outputs: list[tuple[PolicyStoryDefinition, AggregatedStoryResults]] = []
    scores = []
    for story in stories:
        _, aggregated = run_story_sweep(
            repo_root=repo_root,
            output_root=screen_root,
            stage_name="screen",
            story_id=story.story_id,
            versions=versions,
            seeds=screen_seeds,
            points=story.build_points("screen"),
            indicator_ids=sorted(set((*story.primary_outputs, *story.secondary_outputs))),
            workers=workers,
            force_rerun=force_rerun,
            maven_bin=maven_bin,
        )
        screening_outputs.append((story, aggregated))
        scores.append(score_story_screening(story, aggregated))
    return screening_outputs, scores


def run_final_stage(
    *,
    repo_root: Path,
    final_root: Path,
    stories: list[PolicyStoryDefinition],
    versions: list[str],
    final_seeds: list[int],
    workers: int,
    force_rerun: bool,
    maven_bin: str,
) -> dict[str, AggregatedStoryResults]:
    """Run or reuse the dense final sweeps for the selected stories."""

    final_aggregated: dict[str, AggregatedStoryResults] = {}
    for story in stories:
        _, aggregated = run_story_sweep(
            repo_root=repo_root,
            output_root=final_root,
            stage_name="final",
            story_id=story.story_id,
            versions=versions,
            seeds=final_seeds,
            points=story.build_points("final"),
            indicator_ids=sorted(set((*story.primary_outputs, *story.secondary_outputs))),
            workers=workers,
            force_rerun=force_rerun,
            maven_bin=maven_bin,
        )
        final_aggregated[story.story_id] = aggregated
    return final_aggregated


def clear_previous_story_artifacts(output_dir: Path) -> None:
    """Remove stale top-level story files before writing a new final selection."""

    for pattern in ("story_[0-9]*.csv", "story_[0-9]*.png"):
        for path in output_dir.glob(pattern):
            if path.is_file():
                path.unlink()


def main() -> None:
    args = build_arg_parser().parse_args()
    repo_root = Path(__file__).resolve().parents[4]
    output_dir = ensure_output_dir(args.output_dir)
    screen_root = output_dir / "screen"
    final_root = output_dir / "final"

    versions = validate_versions(parse_csv_list(args.versions))
    screen_seeds = parse_seed_list(args.screen_seeds)
    final_seeds = parse_seed_list(args.final_seeds)
    requested_story_ids = parse_csv_list(args.story_ids) if args.story_ids else None

    all_stories = get_policy_story_catalog()
    candidate_stories = select_catalog_subset(all_stories, requested_story_ids)
    candidate_stories, binding_matrix = eligible_stories_by_binding(
        candidate_stories,
        repo_root=repo_root,
        versions=versions,
    )
    if not candidate_stories:
        raise SystemExit("No candidate stories remained after binding checks.")

    catalog_lookup = story_lookup(candidate_stories)
    skip_screening = requested_story_ids is not None and not args.screen_only

    if skip_screening:
        selected_story_order = [catalog_lookup[story_id] for story_id in requested_story_ids]
        final_aggregated = run_final_stage(
            repo_root=repo_root,
            final_root=final_root,
            stories=selected_story_order,
            versions=versions,
            final_seeds=final_seeds,
            workers=args.workers,
            force_rerun=args.force_rerun,
            maven_bin=args.maven_bin,
        )
        screen_scores = [score_story_screening(story, final_aggregated[story.story_id]) for story in selected_story_order]
        selected_scores = screen_scores
    else:
        ensure_project_compiled(repo_root, maven_bin=args.maven_bin)

        _, screen_scores = run_screening_stage(
            repo_root=repo_root,
            screen_root=screen_root,
            stories=candidate_stories,
            versions=versions,
            screen_seeds=screen_seeds,
            workers=args.workers,
            force_rerun=args.force_rerun,
            maven_bin=args.maven_bin,
        )
        if requested_story_ids is not None:
            selected_scores = [next(score for score in screen_scores if score.story_id == story_id) for story_id in requested_story_ids]
        else:
            selected_scores = select_stories(screen_scores, candidate_stories)

        if args.screen_only:
            write_screen_summary_csv(output_dir / "story_candidates_screen.csv", screen_scores)
            write_screen_summary_json(output_dir / "story_candidates_screen.json", screen_scores, binding_matrix)
            write_selected_stories_json(output_dir / "selected_stories.json", selected_scores)
            write_report_markdown(
                output_dir / "boe_policy_story_report.md",
                selected_scores=selected_scores,
                story_lookup=story_lookup(candidate_stories),
                screening_scores=screen_scores,
                versions=versions,
            )
            write_sources_markdown(
                output_dir / "boe_policy_story_sources.md",
                selected_scores=selected_scores,
                story_lookup=story_lookup(candidate_stories),
            )
            return

        final_aggregated = run_final_stage(
            repo_root=repo_root,
            final_root=final_root,
            stories=[catalog_lookup[score.story_id] for score in selected_scores],
            versions=versions,
            final_seeds=final_seeds,
            workers=args.workers,
            force_rerun=args.force_rerun,
            maven_bin=args.maven_bin,
        )

    write_screen_summary_csv(output_dir / "story_candidates_screen.csv", screen_scores)
    write_screen_summary_json(output_dir / "story_candidates_screen.json", screen_scores, binding_matrix)
    write_selected_stories_json(output_dir / "selected_stories.json", selected_scores)

    clear_previous_story_artifacts(output_dir)

    for index, score in enumerate(selected_scores, start=1):
        story = catalog_lookup[score.story_id]
        aggregated = final_aggregated[story.story_id]
        write_story_csv(output_dir / f"story_{index}_{story.story_id}.csv", story, aggregated)
        plot_story_figure(
            path=output_dir / f"story_{index}_{story.story_id}.png",
            story=story,
            aggregated=aggregated,
        )
        plot_story_split_figures(
            path_prefix=output_dir / f"story_{index}_{story.story_id}",
            story=story,
            aggregated=aggregated,
        )

    write_report_markdown(
        output_dir / "boe_policy_story_report.md",
        selected_scores=selected_scores,
        story_lookup=catalog_lookup,
        screening_scores=screen_scores,
        versions=versions,
    )
    write_sources_markdown(
        output_dir / "boe_policy_story_sources.md",
        selected_scores=selected_scores,
        story_lookup=catalog_lookup,
    )


if __name__ == "__main__":
    main()
