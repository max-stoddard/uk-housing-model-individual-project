#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic story scoring and selection for policy-story sweeps.

@author: Max Stoddard
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Sequence

from scripts.python.experiments.model.policy_story_catalog import PolicyStoryDefinition, indicator_title
from scripts.python.helpers.common.abm_policy_sweep import AggregatedPoint, AggregatedStoryResults
from scripts.python.helpers.common.cli import format_float


@dataclass(frozen=True)
class SeriesDiagnostics:
    """Shape diagnostics for one response curve."""

    monotonicity: float
    linear_r2: float
    max_slope_jump: float
    kink_index: int | None


@dataclass(frozen=True)
class StoryScore:
    """Scored screening result for one policy story."""

    story_id: str
    title: str
    primary_indicator_id: str
    secondary_indicator_id: str | None
    primary_effect_score: float
    secondary_effect_score: float
    shape_score: float
    uncertainty_penalty: float
    narrative_weight: float
    total_score: float
    passes_minimum_robustness: bool
    interpretation: str | None
    primary_gap_at_best_point: float
    best_point_label: str
    diagnostics_v0: SeriesDiagnostics
    diagnostics_v4: SeriesDiagnostics

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["diagnostics_v0"] = asdict(self.diagnostics_v0)
        payload["diagnostics_v4"] = asdict(self.diagnostics_v4)
        return payload


def score_story_screening(
    story: PolicyStoryDefinition,
    aggregated: AggregatedStoryResults,
) -> StoryScore:
    """Score one screening sweep for story selection."""

    primary_indicator_id, primary_effect_score, primary_gap, best_point = _select_best_indicator(
        story.primary_outputs,
        aggregated,
    )
    secondary_indicator_id, secondary_effect_score, _, _ = _select_best_indicator(
        story.secondary_outputs,
        aggregated,
        allow_missing=True,
    )

    _, modern_version = resolve_story_versions(aggregated)
    v0_points = aggregated.versions["v0"]
    v4_points = aggregated.versions[modern_version]
    diagnostics_v0 = compute_series_diagnostics(
        x_values=[point.x_value for point in v0_points],
        y_values=[_indicator_delta_mean(point, primary_indicator_id) for point in v0_points],
        expected_sign=story.expected_primary_direction,
    )
    diagnostics_v4 = compute_series_diagnostics(
        x_values=[point.x_value for point in v4_points],
        y_values=[_indicator_delta_mean(point, primary_indicator_id) for point in v4_points],
        expected_sign=story.expected_primary_direction,
    )

    shape_score = compute_shape_score(diagnostics_v0, diagnostics_v4)
    uncertainty_penalty = compute_uncertainty_penalty(aggregated, primary_indicator_id, secondary_indicator_id)
    interpretation = build_story_interpretation(story, aggregated, primary_indicator_id)
    passes_minimum_robustness = (
        primary_effect_score >= 1.0
        and primary_gap > 0.25
        and uncertainty_penalty < 1.0
        and interpretation is not None
    )
    total_score = (
        0.35 * primary_effect_score
        + 0.20 * secondary_effect_score
        + 0.20 * shape_score
        + 0.15 * story.narrative_weight
        - 0.10 * uncertainty_penalty
    )
    return StoryScore(
        story_id=story.story_id,
        title=story.title,
        primary_indicator_id=primary_indicator_id,
        secondary_indicator_id=secondary_indicator_id,
        primary_effect_score=primary_effect_score,
        secondary_effect_score=secondary_effect_score,
        shape_score=shape_score,
        uncertainty_penalty=uncertainty_penalty,
        narrative_weight=story.narrative_weight,
        total_score=total_score,
        passes_minimum_robustness=passes_minimum_robustness,
        interpretation=interpretation,
        primary_gap_at_best_point=primary_gap,
        best_point_label=best_point.label,
        diagnostics_v0=diagnostics_v0,
        diagnostics_v4=diagnostics_v4,
    )


def compute_series_diagnostics(
    *,
    x_values: Sequence[float],
    y_values: Sequence[float],
    expected_sign: int,
) -> SeriesDiagnostics:
    """Compute monotonicity, linearity, and kink diagnostics for a curve."""

    if len(x_values) != len(y_values):
        raise ValueError("x_values and y_values must have the same length")
    if len(x_values) < 2:
        return SeriesDiagnostics(monotonicity=1.0, linear_r2=1.0, max_slope_jump=0.0, kink_index=None)

    slopes: list[float] = []
    aligned_steps = 0
    for index in range(len(x_values) - 1):
        dx = x_values[index + 1] - x_values[index]
        dy = y_values[index + 1] - y_values[index]
        slope = 0.0 if abs(dx) < 1e-12 else dy / dx
        slopes.append(slope)
        if math.isclose(dy, 0.0, abs_tol=1e-12) or math.copysign(1.0, dy) == math.copysign(1.0, expected_sign):
            aligned_steps += 1
    monotonicity = aligned_steps / max(1, len(slopes))

    max_slope_jump = 0.0
    kink_index: int | None = None
    for index in range(len(slopes) - 1):
        slope_jump = abs(slopes[index + 1] - slopes[index])
        if slope_jump > max_slope_jump:
            max_slope_jump = slope_jump
            kink_index = index + 1

    linear_r2 = _linear_r2(x_values, y_values)
    return SeriesDiagnostics(
        monotonicity=monotonicity,
        linear_r2=linear_r2,
        max_slope_jump=max_slope_jump,
        kink_index=kink_index,
    )


def compute_shape_score(v0: SeriesDiagnostics, v4: SeriesDiagnostics) -> float:
    """Reward policy-consistent monotonicity and stronger v4 nonlinearities."""

    monotonicity_reward = max(0.0, v4.monotonicity)
    v4_nonlinearity = max(0.0, 1.0 - v4.linear_r2) + max(0.0, v4.max_slope_jump)
    v0_nonlinearity = max(0.0, 1.0 - v0.linear_r2) + max(0.0, v0.max_slope_jump)
    relative_kink = max(0.0, v4_nonlinearity - v0_nonlinearity)
    return monotonicity_reward + min(relative_kink, 1.5)


def compute_uncertainty_penalty(
    aggregated: AggregatedStoryResults,
    primary_indicator_id: str,
    secondary_indicator_id: str | None,
) -> float:
    """Penalty for curves where uncertainty dominates the inter-version gap."""

    _, modern_version = resolve_story_versions(aggregated)
    indicators = [primary_indicator_id]
    if secondary_indicator_id is not None:
        indicators.append(secondary_indicator_id)

    penalties: list[float] = []
    for indicator_id in indicators:
        v0_points = aggregated.versions["v0"]
        v4_points = aggregated.versions[modern_version]
        noisy_points = 0
        total_points = 0
        for left, right in zip(v0_points, v4_points, strict=True):
            if left.is_baseline:
                continue
            left_stat = left.delta_indicators[indicator_id].mean
            right_stat = right.delta_indicators[indicator_id].mean
            if left_stat is None or right_stat is None:
                continue
            gap = abs(right_stat.mean - left_stat.mean)
            pooled_std = math.sqrt((left_stat.stdev ** 2 + right_stat.stdev ** 2) / 2.0)
            if pooled_std > gap:
                noisy_points += 1
            total_points += 1
        penalties.append(noisy_points / total_points if total_points else 1.0)
    return sum(penalties) / len(penalties)


def build_story_interpretation(
    story: PolicyStoryDefinition,
    aggregated: AggregatedStoryResults,
    primary_indicator_id: str,
) -> str | None:
    """Build a one-sentence economic interpretation from the diagnostics."""

    _, modern_version = resolve_story_versions(aggregated)
    v0_points = aggregated.versions["v0"]
    v4_points = aggregated.versions[modern_version]
    baseline_point = next(point for point in v4_points if point.is_baseline)
    candidate_triplets: list[tuple[float, AggregatedPoint, AggregatedPoint]] = []
    for left, right in zip(v0_points, v4_points, strict=True):
        if left.is_baseline:
            continue
        left_stat = left.delta_indicators[primary_indicator_id].mean
        right_stat = right.delta_indicators[primary_indicator_id].mean
        if left_stat is None or right_stat is None:
            continue
        candidate_triplets.append((abs(right_stat.mean - left_stat.mean), left, right))
    if not candidate_triplets:
        return None
    _, best_left, best_right = max(candidate_triplets, key=lambda item: item[0])
    left_delta = best_left.delta_indicators[primary_indicator_id].mean
    right_delta = best_right.delta_indicators[primary_indicator_id].mean
    if left_delta is None or right_delta is None:
        return None

    baseline_value = baseline_point.x_value
    if math.isclose(best_right.x_value, baseline_value, abs_tol=1e-9):
        return None
    if abs(right_delta.mean) < 0.05 and abs(left_delta.mean) < 0.05:
        return None

    action = _policy_action_label(
        x_value=best_right.x_value,
        baseline_value=baseline_value,
        expected_sign=story.expected_primary_direction,
    )
    return (
        f"{action.capitalize()} {story.instrument_label} from {format_float(baseline_value)} to "
        f"{format_float(best_right.x_value)} moves {indicator_title(primary_indicator_id)} by "
        f"{_format_effect(right_delta.mean)} in {modern_version} versus {_format_effect(left_delta.mean)} in v0, "
        f"consistent with {story.mechanism_summary}."
    )


def select_stories(
    story_scores: Sequence[StoryScore],
    stories: Sequence[PolicyStoryDefinition],
) -> list[StoryScore]:
    """Select the two final stories using deterministic inclusion and fallback rules."""

    story_by_id = {story.story_id: story for story in stories}
    score_by_id = {score.story_id: score for score in story_scores}
    selected: list[StoryScore] = []

    affordability_score = score_by_id.get("affordability_cap")
    if affordability_score is not None and affordability_score.passes_minimum_robustness:
        selected.append(affordability_score)

    ranked = sorted(
        story_scores,
        key=lambda item: (
            item.passes_minimum_robustness,
            item.total_score,
            -story_by_id[item.story_id].fallback_rank,
        ),
        reverse=True,
    )
    for score in ranked:
        if score.story_id in {item.story_id for item in selected}:
            continue
        if score.passes_minimum_robustness:
            selected.append(score)
            if len(selected) == 2:
                return selected

    fallback_order = [
        "ftb_ltv_cap",
        "affordability_cap",
        "lti_flow_limit_bundle",
        "hm_ltv_cap",
        "btl_icr_cap",
        "base_rate",
    ]
    for story_id in fallback_order:
        if story_id in {item.story_id for item in selected}:
            continue
        if story_id in score_by_id:
            selected.append(score_by_id[story_id])
            if len(selected) == 2:
                return selected
    return selected[:2]


def _select_best_indicator(
    indicator_ids: Sequence[str],
    aggregated: AggregatedStoryResults,
    *,
    allow_missing: bool = False,
) -> tuple[str | None, float, float, AggregatedPoint]:
    _, modern_version = resolve_story_versions(aggregated)
    if not indicator_ids:
        return None, 0.0, 0.0, aggregated.versions[modern_version][0]
    scored: list[tuple[float, float, str, AggregatedPoint]] = []
    for indicator_id in indicator_ids:
        best_score = 0.0
        best_gap = 0.0
        best_point = aggregated.versions[modern_version][0]
        for left, right in zip(aggregated.versions["v0"], aggregated.versions[modern_version], strict=True):
            if left.is_baseline:
                continue
            left_stat = left.delta_indicators[indicator_id].mean
            right_stat = right.delta_indicators[indicator_id].mean
            if left_stat is None or right_stat is None:
                continue
            gap = abs(right_stat.mean - left_stat.mean)
            pooled_std = math.sqrt((left_stat.stdev ** 2 + right_stat.stdev ** 2) / 2.0)
            score = gap / max(pooled_std, 1e-9)
            if score > best_score:
                best_score = score
                best_gap = gap
                best_point = right
        scored.append((best_score, best_gap, indicator_id, best_point))
    if not scored and allow_missing:
        return None, 0.0, 0.0, aggregated.versions[modern_version][0]
    best_score, best_gap, indicator_id, best_point = max(scored, key=lambda item: (item[0], item[1], item[2]))
    return indicator_id, best_score, best_gap, best_point


def resolve_story_versions(aggregated: AggregatedStoryResults) -> tuple[str, str]:
    """Return the fixed baseline and modern version ids for a story result."""

    if "v0" not in aggregated.versions:
        raise RuntimeError("Policy-story comparisons require `v0` as the baseline version.")
    modern_versions = [version for version in aggregated.versions if version != "v0"]
    if len(modern_versions) != 1:
        raise RuntimeError("Policy-story comparisons require exactly one modern comparison version.")
    return "v0", modern_versions[0]


def _indicator_delta_mean(point: AggregatedPoint, indicator_id: str) -> float:
    stat = point.delta_indicators[indicator_id].mean
    if stat is None:
        return 0.0
    return stat.mean


def _linear_r2(x_values: Sequence[float], y_values: Sequence[float]) -> float:
    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(y_values) / len(y_values)
    sxx = sum((value - mean_x) ** 2 for value in x_values)
    if abs(sxx) < 1e-12:
        return 1.0
    sxy = sum((x_value - mean_x) * (y_value - mean_y) for x_value, y_value in zip(x_values, y_values, strict=True))
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    predicted = [intercept + slope * value for value in x_values]
    ss_res = sum((actual - fitted) ** 2 for actual, fitted in zip(y_values, predicted, strict=True))
    ss_tot = sum((actual - mean_y) ** 2 for actual in y_values)
    if abs(ss_tot) < 1e-12:
        return 1.0
    return max(0.0, 1.0 - ss_res / ss_tot)


def _policy_action_label(*, x_value: float, baseline_value: float, expected_sign: int) -> str:
    if expected_sign > 0:
        return "loosening" if x_value > baseline_value else "tightening"
    return "tightening" if x_value > baseline_value else "loosening"


def _format_effect(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}{format_float(abs(value), decimals=3)}"
