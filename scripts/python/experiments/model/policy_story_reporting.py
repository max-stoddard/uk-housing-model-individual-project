#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reporting helpers for the policy-story demo workflow.

@author: Max Stoddard
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scripts.python.experiments.model.policy_story_catalog import (
    BindingEvaluation,
    PolicyStoryDefinition,
    StoryMethodAudit,
    indicator_title,
    indicator_units,
)
from scripts.python.experiments.model.policy_story_evidence import StoryEvidenceReview, StoryRecommendation
from scripts.python.experiments.model.policy_story_scoring import StoryScore, resolve_story_versions
from scripts.python.helpers.common.abm_policy_sweep import AggregateStat, AggregatedStoryResults
from scripts.python.helpers.common.cli import format_float

V0_COLOR = "#4B5563"
V40_COLOR = "#0F766E"
ALIGNED_TITLE_SUFFIX = " (Aligned Bank + Central-Bank Limit)"
VERSION_LABELS = {
    "v0": "Pre-2012 Calibration",
    "v4.0": "Post-2022 Calibration",
    "v4.1": "Post-2022 Calibration",
}


def write_screen_summary_csv(path: Path, story_scores: Sequence[StoryScore], *, selection_policy: str) -> None:
    """Write the screening ranking table."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "selection_policy",
                "story_id",
                "title",
                "primary_indicator_id",
                "secondary_indicator_id",
                "primary_effect_score",
                "secondary_effect_score",
                "shape_score",
                "uncertainty_penalty",
                "narrative_weight",
                "total_score",
                "passes_minimum_robustness",
                "best_point_label",
                "primary_gap_at_best_point",
                "interpretation",
            ]
        )
        for score in sorted(story_scores, key=lambda item: item.total_score, reverse=True):
            writer.writerow(
                [
                    selection_policy,
                    score.story_id,
                    score.title,
                    score.primary_indicator_id,
                    score.secondary_indicator_id or "",
                    format_float(score.primary_effect_score, decimals=6),
                    format_float(score.secondary_effect_score, decimals=6),
                    format_float(score.shape_score, decimals=6),
                    format_float(score.uncertainty_penalty, decimals=6),
                    format_float(score.narrative_weight, decimals=6),
                    format_float(score.total_score, decimals=6),
                    "true" if score.passes_minimum_robustness else "false",
                    score.best_point_label,
                    format_float(score.primary_gap_at_best_point, decimals=6),
                    score.interpretation or "",
                ]
            )

def write_screen_summary_json(
    path: Path,
    story_scores: Sequence[StoryScore],
    binding_matrix: dict[str, dict[str, bool]],
    *,
    selection_policy: str,
) -> None:
    """Write screening scores with binding diagnostics."""

    payload = {
        "selection_policy": selection_policy,
        "binding_matrix": binding_matrix,
        "story_scores": [score.to_json() for score in sorted(story_scores, key=lambda item: item.total_score, reverse=True)],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_selected_stories_json(
    path: Path,
    selection_results: Mapping[str, Sequence[StoryScore]],
    *,
    selection_policy: str,
    canonical_policy: str,
) -> None:
    """Write the final selection result."""

    payload = {
        "selection_policy": selection_policy,
        "canonical_policy": canonical_policy,
        "selected_stories": [score.to_json() for score in selection_results[canonical_policy]],
        "selection_results": {
            policy: [score.to_json() for score in selected_scores]
            for policy, selected_scores in selection_results.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_binding_validation_csv(
    path: Path,
    *,
    stories: Sequence[PolicyStoryDefinition],
    binding_details: Mapping[str, Mapping[str, BindingEvaluation]],
    versions: Sequence[str],
) -> None:
    """Write the per-story binding audit table."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "story_id",
                "instrument_label",
                "swept_keys",
                f"{versions[0]}_binds",
                f"{versions[0]}_relevant_values",
                f"{versions[0]}_reason",
                f"{versions[1]}_binds",
                f"{versions[1]}_relevant_values",
                f"{versions[1]}_reason",
            ]
        )
        for story in stories:
            left = binding_details[story.story_id][versions[0]]
            right = binding_details[story.story_id][versions[1]]
            writer.writerow(
                [
                    story.story_id,
                    story.instrument_label,
                    ",".join(story.swept_keys),
                    "true" if left.binds else "false",
                    _format_mapping(left.relevant_values),
                    left.reason,
                    "true" if right.binds else "false",
                    _format_mapping(right.relevant_values),
                    right.reason,
                ]
            )


def write_binding_validation_json(
    path: Path,
    *,
    stories: Sequence[PolicyStoryDefinition],
    binding_details: Mapping[str, Mapping[str, BindingEvaluation]],
    versions: Sequence[str],
) -> None:
    """Write the per-story binding audit in JSON form."""

    payload = {
        "versions": list(versions),
        "stories": [
            {
                "story_id": story.story_id,
                "instrument_label": story.instrument_label,
                "swept_keys": list(story.swept_keys),
                "binding_by_version": {
                    version: binding_details[story.story_id][version].to_json()
                    for version in versions
                },
            }
            for story in stories
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_method_audit_csv(
    path: Path,
    *,
    method_audits: Mapping[str, StoryMethodAudit],
    versions: Sequence[str],
) -> None:
    """Write the story method-validity audit table."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "story_id",
                "title",
                "effective_rule",
                "linked_bank_keys",
                "shortlist_eligible",
                "resolution_summary",
                f"{versions[0]}_raw_has_conflict",
                f"{versions[0]}_aligned_resolves_conflict",
                f"{versions[0]}_note",
                f"{versions[1]}_raw_has_conflict",
                f"{versions[1]}_aligned_resolves_conflict",
                f"{versions[1]}_note",
            ]
        )
        for story_id, audit in method_audits.items():
            left = audit.versions[versions[0]]
            right = audit.versions[versions[1]]
            writer.writerow(
                [
                    story_id,
                    audit.title,
                    audit.effective_rule,
                    ",".join(audit.linked_bank_keys),
                    "true" if audit.shortlist_eligible else "false",
                    audit.resolution_summary,
                    "true" if left.raw_has_conflict else "false",
                    "true" if left.aligned_resolves_conflict else "false",
                    left.note,
                    "true" if right.raw_has_conflict else "false",
                    "true" if right.aligned_resolves_conflict else "false",
                    right.note,
                ]
            )


def write_method_audit_json(
    path: Path,
    *,
    method_audits: Mapping[str, StoryMethodAudit],
) -> None:
    """Write the story method-validity audit in JSON form."""

    payload = {
        "stories": [
            audit.to_json()
            for _, audit in sorted(method_audits.items())
        ]
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_method_audit_markdown(
    path: Path,
    *,
    method_audits: Mapping[str, StoryMethodAudit],
    versions: Sequence[str],
) -> None:
    """Write the human-readable method-validity audit."""

    lines = [
        "# BoE Policy Story Method Audit",
        "",
        "This audit checks raw parameter masking against the model's effective-rule logic and whether the aligned method resolves it.",
        "",
        "| story | rule | shortlist | "
        f"{versions[0]} raw conflict | {versions[0]} aligned ok | "
        f"{versions[1]} raw conflict | {versions[1]} aligned ok |",
        "|---|---|:---:|:---:|:---:|:---:|:---:|",
    ]
    for _, audit in sorted(method_audits.items()):
        left = audit.versions[versions[0]]
        right = audit.versions[versions[1]]
        lines.append(
            f"| {audit.story_id} | {audit.effective_rule} | "
            f"{'Y' if audit.shortlist_eligible else 'N'} | "
            f"{'Y' if left.raw_has_conflict else 'N'} | {'Y' if left.aligned_resolves_conflict else 'N'} | "
            f"{'Y' if right.raw_has_conflict else 'N'} | {'Y' if right.aligned_resolves_conflict else 'N'} |"
        )
        lines.append("")
        lines.append(f"## {audit.title}")
        lines.append("")
        lines.append(f"- Resolution summary: {audit.resolution_summary}")
        lines.append(f"- {versions[0]} note: {left.note}")
        lines.append(f"- {versions[1]} note: {right.note}")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_evidence_review_markdown(
    path: Path,
    *,
    story_scores: Sequence[StoryScore],
    stories: Mapping[str, PolicyStoryDefinition],
    evidence_reviews: Mapping[str, StoryEvidenceReview],
) -> None:
    """Write the official-source fit review for screened stories."""

    lines = [
        "# BoE Policy Story Evidence Review",
        "",
        "This review uses current public sources from the Bank of England, FCA, ONS, and GOV.UK / HM Treasury.",
        "",
    ]
    for score in sorted(story_scores, key=lambda item: item.total_score, reverse=True):
        story = stories[score.story_id]
        review = evidence_reviews.get(score.story_id)
        lines.extend(
            [
                f"## {story.title}",
                "",
                f"- Screening score: `{format_float(score.total_score, decimals=3)}`",
                f"- Robust in model screening: `{'yes' if score.passes_minimum_robustness else 'no'}`",
            ]
        )
        if review is None:
            lines.extend(
                [
                    "- Evidence fit: No official-source review available.",
                    "",
                ]
            )
            continue
        lines.extend(
            [
                f"- Evidence strength: `{format_float(review.evidence_strength, decimals=2)}`",
                f"- Fit summary: {review.fit_summary}",
                f"- Gap summary: {review.gap_summary}",
                "",
                "### Sources",
                "",
            ]
        )
        for source in review.sources:
            lines.append(
                f"- [{source.title}]({source.url}) ({source.publisher}, {source.published_on})"
            )
            lines.append(f"  Relevance: {source.relevance}")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_recommendation_markdown(
    path: Path,
    *,
    recommendation: StoryRecommendation,
    evidence_reviews: Mapping[str, StoryEvidenceReview],
    story_lookup: Mapping[str, PolicyStoryDefinition],
) -> None:
    """Write the single-story balanced recommendation."""

    story = story_lookup[recommendation.story_id]
    evidence = evidence_reviews.get(recommendation.story_id)
    lines = [
        "# BoE Policy Story Recommendation",
        "",
        f"## Recommended Story: {story.title}",
        "",
        f"- Story id: `{recommendation.story_id}`",
        f"- Blended score: `{format_float(recommendation.blended_score, decimals=3)}`",
        f"- Model score: `{format_float(recommendation.model_score, decimals=3)}`",
        f"- Normalized model score: `{format_float(recommendation.model_score_normalized, decimals=3)}`",
        f"- Evidence strength: `{format_float(recommendation.evidence_strength, decimals=2)}`",
        f"- Why this is the best balanced demo story: {recommendation.rationale}",
        f"- `v4.1` caveat: {recommendation.caveat}",
        "",
    ]
    if evidence is not None:
        lines.extend(
            [
                "## Official Sources",
                "",
            ]
        )
        for source in evidence.sources:
            lines.append(
                f"- [{source.title}]({source.url}) ({source.publisher}, {source.published_on})"
            )
            lines.append(f"  Relevance: {source.relevance}")
        lines.extend(
            [
                "",
                "## Evidence Gaps",
                "",
                f"- {evidence.gap_summary}",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_story_csv(
    path: Path,
    story: PolicyStoryDefinition,
    aggregated: AggregatedStoryResults,
) -> None:
    """Write one selected story's dense sweep summary in long format."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "story_id",
                "version",
                "point_id",
                "point_label",
                "x_value",
                "is_baseline",
                "indicator_id",
                "kpi_metric",
                "raw_mean",
                "raw_stdev",
                "raw_ci_low",
                "raw_ci_high",
                "raw_n",
                "delta_mean",
                "delta_stdev",
                "delta_ci_low",
                "delta_ci_high",
                "delta_n",
            ]
        )
        for version, points in aggregated.versions.items():
            for point in points:
                for indicator_id, indicator_bundle in point.indicators.items():
                    delta_bundle = point.delta_indicators[indicator_id]
                    for kpi_metric in ("mean", "cv", "annualised_trend", "range"):
                        raw_stat = getattr(indicator_bundle, kpi_metric)
                        delta_stat = getattr(delta_bundle, kpi_metric)
                        writer.writerow(
                            [
                                story.story_id,
                                version,
                                point.point_id,
                                point.label,
                                format_float(point.x_value),
                                "true" if point.is_baseline else "false",
                                indicator_id,
                                kpi_metric,
                                _fmt_stat(raw_stat, "mean"),
                                _fmt_stat(raw_stat, "stdev"),
                                _fmt_stat(raw_stat, "ci_low"),
                                _fmt_stat(raw_stat, "ci_high"),
                                _fmt_stat(raw_stat, "n"),
                                _fmt_stat(delta_stat, "mean"),
                                _fmt_stat(delta_stat, "stdev"),
                                _fmt_stat(delta_stat, "ci_low"),
                                _fmt_stat(delta_stat, "ci_high"),
                                _fmt_stat(delta_stat, "n"),
                            ]
                        )


def plot_story_figure(
    *,
    path: Path,
    story: PolicyStoryDefinition,
    aggregated: AggregatedStoryResults,
) -> None:
    """Render one selected story figure."""

    panel_indicator_ids = list(story.figure_indicator_ids)

    figure, axes = plt.subplots(len(panel_indicator_ids), 1, figsize=(9.5, 3.2 * len(panel_indicator_ids)), sharex=True)
    if len(panel_indicator_ids) == 1:
        axes = [axes]

    for axis, indicator_id in zip(axes, panel_indicator_ids, strict=True):
        _plot_indicator_panel(
            axis,
            aggregated,
            indicator_id,
        )

    axes[-1].set_xlabel(f"{story.axis_label} ({story.axis_units})")
    figure.suptitle(_figure_story_title(story.title))
    figure.text(
        0.013,
        0.985,
        "Deltas are relative to the story baseline; shaded bands show 95% CI across seeds.",
        fontsize=8,
        color="#4B5563",
        va="top",
    )
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def plot_story_split_figures(
    *,
    path_prefix: Path,
    story: PolicyStoryDefinition,
    aggregated: AggregatedStoryResults,
) -> None:
    """Render one single-panel figure per configured story panel."""

    for index, indicator_id in enumerate(story.figure_indicator_ids, start=1):
        figure, axis = plt.subplots(1, 1, figsize=(9.5, 3.6))
        _plot_indicator_panel(
            axis,
            aggregated,
            indicator_id,
        )
        axis.set_xlabel(f"{story.axis_label} ({story.axis_units})")
        figure.suptitle(f"{_figure_story_title(story.title)} - {indicator_title(indicator_id)}")
        figure.tight_layout()
        split_path = path_prefix.parent / f"{path_prefix.name}__panel_{index}_{indicator_id}.png"
        figure.savefig(split_path, dpi=180)
        plt.close(figure)


def write_report_markdown(
    path: Path,
    *,
    selected_scores: Sequence[StoryScore],
    selection_results: Mapping[str, Sequence[StoryScore]],
    story_lookup: dict[str, PolicyStoryDefinition],
    screening_scores: Sequence[StoryScore],
    versions: Sequence[str],
    selection_policy: str,
    canonical_policy: str,
    methodology_note: str,
) -> None:
    """Write the human-readable summary report."""

    lines = [
        "# BoE Policy Story Report",
        "",
        f"- Selection policy requested: `{selection_policy}`",
        f"- Canonical selected shortlist: `{canonical_policy}`",
        f"- Method note: {methodology_note}",
        "",
        "## Why These Stories Were Chosen",
        "",
    ]
    comparison_text = f"`{humanize_version_label(versions[0])}` vs `{humanize_version_label(versions[1])}`"
    for index, score in enumerate(selected_scores, start=1):
        story = story_lookup[score.story_id]
        lines.extend(
            [
                f"### Story {index}: {story.title}",
                "",
                f"- Instrument: `{story.instrument_label}`",
                f"- Primary response shown: `{indicator_title(score.primary_indicator_id)}`",
                f"- Secondary response shown: `{indicator_title(score.secondary_indicator_id)}`" if score.secondary_indicator_id else "- Secondary response shown: none",
                f"- Screening score: `{format_float(score.total_score, decimals=4)}`",
                f"- Interpretation: {_humanize_versions(score.interpretation)}",
                f"- Why this is plausible: {story.recalibration_summary}",
                f"- Panels shown: {', '.join(indicator_title(indicator_id) for indicator_id in story.figure_indicator_ids)}",
                f"- Comparison: {comparison_text}",
                "",
            ]
        )

    lines.extend(
        [
            "## Selection Results",
            "",
            "| policy | selected story ids |",
            "|---|---|",
        ]
    )
    for policy, scores in selection_results.items():
        lines.append(f"| {policy} | {', '.join(score.story_id for score in scores)} |")
    lines.extend(
        [
            "",
            "## Screening Ranking",
            "",
            "| rank | story | total | primary | secondary | shape | uncertainty | robust |",
            "|---:|---|---:|---:|---:|---:|---:|:---:|",
        ]
    )
    for index, score in enumerate(sorted(screening_scores, key=lambda item: item.total_score, reverse=True), start=1):
        lines.append(
            f"| {index} | {score.story_id} | {format_float(score.total_score, decimals=3)} | "
            f"{format_float(score.primary_effect_score, decimals=3)} | "
            f"{format_float(score.secondary_effect_score, decimals=3)} | "
            f"{format_float(score.shape_score, decimals=3)} | "
            f"{format_float(score.uncertainty_penalty, decimals=3)} | "
            f"{'Y' if score.passes_minimum_robustness else 'N'} |"
        )
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_sources_markdown(
    path: Path,
    *,
    selected_scores: Sequence[StoryScore],
    story_lookup: dict[str, PolicyStoryDefinition],
    selection_policy: str,
) -> None:
    """Write the official-source pack for the selected stories."""

    lines = [
        "# BoE Policy Story Sources",
        "",
        f"Selection policy: `{selection_policy}`",
        "",
    ]
    for score in selected_scores:
        story = story_lookup[score.story_id]
        lines.extend(
            [
                f"## {story.title}",
                "",
            ]
        )
        for source in story.sources:
            lines.append(f"- [{source.title}]({source.url})")
            lines.append(f"  Relevance: {source.note}")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _figure_story_title(title: str) -> str:
    """Return the chart-title variant for a story."""

    return title.removesuffix(ALIGNED_TITLE_SUFFIX)


def _panel_x_axis_ticks(aggregated: AggregatedStoryResults) -> tuple[list[float], list[str]]:
    """Return the actual dense sweep points that should appear on the x axis."""

    baseline_version, _ = resolve_story_versions(aggregated)
    points = aggregated.versions[baseline_version]
    return [point.x_value for point in points], [point.label for point in points]


def _configure_panel_x_axis(axis: plt.Axes, aggregated: AggregatedStoryResults) -> None:
    """Align x-axis ticks and grid lines to the exact sweep points."""

    x_values, labels = _panel_x_axis_ticks(aggregated)
    axis.set_xticks(x_values)
    axis.set_xticklabels(labels)

def _plot_indicator_panel(
    axis: plt.Axes,
    aggregated: AggregatedStoryResults,
    indicator_id: str,
    *,
    annotation: tuple[float, float, str] | None = None,
) -> None:
    baseline_version, modern_version = resolve_story_versions(aggregated)
    for version, color in ((baseline_version, V0_COLOR), (modern_version, V40_COLOR)):
        points = aggregated.versions[version]
        x_values = [point.x_value for point in points]
        stats = [point.delta_indicators[indicator_id].mean for point in points]
        y_values = [0.0 if stat is None else stat.mean for stat in stats]
        ci_lows = [0.0 if stat is None else stat.ci_low for stat in stats]
        ci_highs = [0.0 if stat is None else stat.ci_high for stat in stats]
        axis.plot(x_values, y_values, marker="o", linewidth=2, label=humanize_version_label(version), color=color)
        axis.fill_between(x_values, ci_lows, ci_highs, color=color, alpha=0.18)
    axis.axhline(0.0, color="#9CA3AF", linewidth=1, linestyle="--")
    axis.set_ylabel(f"{indicator_title(indicator_id)}\nDelta ({indicator_units(indicator_id)})")
    _configure_panel_x_axis(axis, aggregated)
    if annotation is not None:
        x_value, y_value, label = annotation
        axis.annotate(
            label,
            xy=(x_value, y_value),
            xytext=(10, 16),
            textcoords="offset points",
            fontsize=8,
            arrowprops={"arrowstyle": "->", "color": V40_COLOR},
        )
    axis.legend(loc="best")
    axis.grid(axis="both", alpha=0.2)


def find_headline_annotation(
    aggregated: AggregatedStoryResults,
    indicator_id: str,
) -> tuple[float, float, str] | None:
    """Find the cleanest inter-version separation point for a headline panel."""

    baseline_version, modern_version = resolve_story_versions(aggregated)
    best_candidate: tuple[float, float, float, str] | None = None
    for left, right in zip(aggregated.versions[baseline_version], aggregated.versions[modern_version], strict=True):
        if left.is_baseline:
            continue
        left_stat = left.delta_indicators[indicator_id].mean
        right_stat = right.delta_indicators[indicator_id].mean
        if left_stat is None or right_stat is None:
            continue
        if not ci_ranges_do_not_overlap(left_stat, right_stat):
            continue
        gap = abs(right_stat.mean - left_stat.mean)
        candidate = (gap, right.x_value, right_stat.mean, right.label)
        if best_candidate is None or candidate[0] > best_candidate[0]:
            best_candidate = candidate
    if best_candidate is None:
        return None
    _, x_value, y_value, label = best_candidate
    return x_value, y_value, f"Strongest non-overlap at {label}"


def ci_ranges_do_not_overlap(left: AggregateStat, right: AggregateStat) -> bool:
    """Return whether two confidence intervals do not overlap."""

    return left.ci_high < right.ci_low or right.ci_high < left.ci_low


def humanize_version_label(version: str) -> str:
    """Return the presentation label for a version id."""

    return VERSION_LABELS.get(version, version)


def _humanize_versions(text: str | None) -> str:
    if text is None:
        return ""
    humanized = text
    for version, label in VERSION_LABELS.items():
        humanized = humanized.replace(version, label)
    return humanized


def _fmt_stat(stat: object, field: str) -> str:
    if stat is None:
        return ""
    value = getattr(stat, field)
    if value is None:
        return ""
    if field == "n":
        return str(int(value))
    return format_float(value, decimals=6)


def _format_mapping(values: Mapping[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in values.items())
