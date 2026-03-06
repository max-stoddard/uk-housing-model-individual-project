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
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scripts.python.experiments.model.policy_story_catalog import PolicyStoryDefinition, indicator_title, indicator_units
from scripts.python.experiments.model.policy_story_scoring import StoryScore, resolve_story_versions
from scripts.python.helpers.common.abm_policy_sweep import AggregateStat, AggregatedStoryResults
from scripts.python.helpers.common.cli import format_float

V0_COLOR = "#4B5563"
V40_COLOR = "#0F766E"
VERSION_LABELS = {
    "v0": "Pre-2012 Calibration",
    "v4.0": "Post-2022 Calibration",
    "v4.1": "Post-2022 Calibration",
}


def write_screen_summary_csv(path: Path, story_scores: Sequence[StoryScore]) -> None:
    """Write the screening ranking table."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
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


def write_screen_summary_json(path: Path, story_scores: Sequence[StoryScore], binding_matrix: dict[str, dict[str, bool]]) -> None:
    """Write screening scores with binding diagnostics."""

    payload = {
        "binding_matrix": binding_matrix,
        "story_scores": [score.to_json() for score in sorted(story_scores, key=lambda item: item.total_score, reverse=True)],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_selected_stories_json(path: Path, selected_scores: Sequence[StoryScore]) -> None:
    """Write the final selection result."""

    payload = {"selected_stories": [score.to_json() for score in selected_scores]}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
    annotation = find_headline_annotation(aggregated, story.figure_headline_indicator_id)

    figure, axes = plt.subplots(len(panel_indicator_ids), 1, figsize=(9.5, 3.2 * len(panel_indicator_ids)), sharex=True)
    if len(panel_indicator_ids) == 1:
        axes = [axes]

    for axis, indicator_id in zip(axes, panel_indicator_ids, strict=True):
        _plot_indicator_panel(
            axis,
            aggregated,
            indicator_id,
            annotation=annotation if indicator_id == story.figure_headline_indicator_id else None,
        )

    axes[-1].set_xlabel(f"{story.axis_label} ({story.axis_units})")
    figure.suptitle(story.title)
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

    annotation = find_headline_annotation(aggregated, story.figure_headline_indicator_id)
    for index, indicator_id in enumerate(story.figure_indicator_ids, start=1):
        figure, axis = plt.subplots(1, 1, figsize=(9.5, 3.6))
        _plot_indicator_panel(
            axis,
            aggregated,
            indicator_id,
            annotation=annotation if indicator_id == story.figure_headline_indicator_id else None,
        )
        axis.set_xlabel(f"{story.axis_label} ({story.axis_units})")
        figure.suptitle(f"{story.title} - {indicator_title(indicator_id)}")
        figure.tight_layout()
        split_path = path_prefix.parent / f"{path_prefix.name}__panel_{index}_{indicator_id}.png"
        figure.savefig(split_path, dpi=180)
        plt.close(figure)


def write_report_markdown(
    path: Path,
    *,
    selected_scores: Sequence[StoryScore],
    story_lookup: dict[str, PolicyStoryDefinition],
    screening_scores: Sequence[StoryScore],
    versions: Sequence[str],
) -> None:
    """Write the human-readable summary report."""

    lines = [
        "# BoE Policy Story Report",
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
) -> None:
    """Write the official-source pack for the selected stories."""

    lines = [
        "# BoE Policy Story Sources",
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
    axis.grid(alpha=0.2)


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
