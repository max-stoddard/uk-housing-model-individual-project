#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Policy-story catalog for the Bank of England demo workflow.

@author: Max Stoddard
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from scripts.python.helpers.common.abm_policy_sweep import POLICY_INDICATORS, SweepPoint
from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.common.io_properties import read_properties


def _binding_upper_than_bank_values(bank_key: str, values: Sequence[float], props: Mapping[str, str]) -> bool:
    bank_value = float(props[bank_key])
    return min(values) < bank_value - 1e-9


def _binding_lower_than_bank_values(bank_key: str, values: Sequence[float], props: Mapping[str, str]) -> bool:
    bank_value = float(props[bank_key])
    return max(values) > bank_value + 1e-9


def _binding_lti_flow(props: Mapping[str, str]) -> bool:
    ftb_hard = float(props["BANK_LTI_HARD_MAX_FTB"])
    hm_hard = float(props["BANK_LTI_HARD_MAX_HM"])
    return 4.5 < ftb_hard - 1e-9 and 4.5 < hm_hard - 1e-9


def _always_binding(_: Mapping[str, str]) -> bool:
    return True


@dataclass(frozen=True)
class StorySource:
    """One external source attached to a policy story."""

    title: str
    url: str
    note: str


@dataclass(frozen=True)
class BindingEvaluation:
    """Binding status and context for one story under one version."""

    binds: bool
    relevant_values: dict[str, str]
    reason: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MethodPointAudit:
    """Raw-versus-aligned effectiveness for one sweep point."""

    point_id: str
    label: str
    x_value: float
    raw_effective: bool
    aligned_effective: bool
    raw_updates: dict[str, str]
    aligned_updates: dict[str, str]
    raw_reason: str
    aligned_reason: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StoryVersionMethodAudit:
    """Method audit for one story under one version."""

    screen_points: tuple[MethodPointAudit, ...]
    final_points: tuple[MethodPointAudit, ...]
    raw_has_conflict: bool
    aligned_resolves_conflict: bool
    note: str

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["screen_points"] = [point.to_json() for point in self.screen_points]
        payload["final_points"] = [point.to_json() for point in self.final_points]
        return payload


@dataclass(frozen=True)
class StoryMethodAudit:
    """Method-validity audit for one policy story across versions."""

    story_id: str
    title: str
    effective_rule: str
    linked_bank_keys: tuple[str, ...]
    shortlist_eligible: bool
    resolution_summary: str
    versions: dict[str, StoryVersionMethodAudit]

    def to_json(self) -> dict[str, object]:
        return {
            "story_id": self.story_id,
            "title": self.title,
            "effective_rule": self.effective_rule,
            "linked_bank_keys": list(self.linked_bank_keys),
            "shortlist_eligible": self.shortlist_eligible,
            "resolution_summary": self.resolution_summary,
            "versions": {
                version: audit.to_json()
                for version, audit in self.versions.items()
            },
        }


@dataclass(frozen=True)
class PolicyStoryDefinition:
    """Configuration for one candidate policy story."""

    story_id: str
    title: str
    instrument_label: str
    description: str
    axis_label: str
    axis_units: str
    fixed_updates: dict[str, str]
    swept_keys: tuple[str, ...]
    screen_values: tuple[float, ...]
    final_values: tuple[float, ...]
    baseline_value: float
    primary_outputs: tuple[str, ...]
    secondary_outputs: tuple[str, ...]
    figure_indicator_ids: tuple[str, ...]
    figure_headline_indicator_id: str
    expected_primary_direction: int
    policy_relevance_weight: float
    calibration_link_weight: float
    fallback_rank: int
    mechanism_summary: str
    recalibration_summary: str
    binding_checker: Callable[[Mapping[str, str]], bool]
    sources: tuple[StorySource, ...]
    appendix_only: bool = False
    effective_rule: str = "none"
    linked_bank_keys: tuple[str, ...] = ()

    def build_points(self, stage_name: str, *, aligned: bool = False) -> list[SweepPoint]:
        values = self.screen_values if stage_name == "screen" else self.final_values
        points: list[SweepPoint] = []
        for index, value in enumerate(values):
            updates = dict(self.fixed_updates)
            formatted_value = format_float(value)
            for key in self.swept_keys:
                updates[key] = formatted_value
            if aligned and self.effective_rule in {"min_cap", "max_floor"}:
                for key in self.linked_bank_keys:
                    updates[key] = formatted_value
            safe_label = formatted_value.replace("-", "m").replace(".", "p")
            points.append(
                SweepPoint(
                    point_id=f"point_{index:02d}_{safe_label}",
                    point_index=index,
                    label=formatted_value,
                    x_value=value,
                    updates=updates,
                    is_baseline=abs(value - self.baseline_value) < 1e-9,
                )
            )
        if not any(point.is_baseline for point in points):
            raise RuntimeError(f"Baseline value {self.baseline_value} was not present in the sweep grid.")
        return points

    @property
    def narrative_weight(self) -> float:
        return 0.5 * (self.policy_relevance_weight + self.calibration_link_weight)


def get_policy_story_catalog() -> list[PolicyStoryDefinition]:
    """Return the fixed candidate story catalog."""

    return [
        PolicyStoryDefinition(
            story_id="lti_flow_limit_bundle",
            title="Shared High-LTI Flow Limit",
            instrument_label="shared over-soft LTI quota",
            description=(
                "BoE-style high-LTI flow limit bundle with a shared soft cap of 4.5x income "
                "and varying allowance for lending above the soft limit."
            ),
            axis_label="Share of mortgages allowed above 4.5x income",
            axis_units="fraction",
            fixed_updates={
                "CENTRAL_BANK_LTI_SOFT_MAX_FTB": "4.5",
                "CENTRAL_BANK_LTI_SOFT_MAX_HM": "4.5",
            },
            swept_keys=(
                "CENTRAL_BANK_LTI_MAX_FRAC_OVER_SOFT_MAX_FTB",
                "CENTRAL_BANK_LTI_MAX_FRAC_OVER_SOFT_MAX_HM",
            ),
            screen_values=(0.00, 0.15, 0.30),
            final_values=(0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30),
            baseline_value=0.15,
            primary_outputs=("core_mortgageApprovals", "core_debtToIncome"),
            secondary_outputs=("core_advancesToFTB", "core_priceToIncome"),
            figure_indicator_ids=("core_debtToIncome", "core_mortgageApprovals", "core_advancesToFTB"),
            figure_headline_indicator_id="core_debtToIncome",
            expected_primary_direction=1,
            policy_relevance_weight=1.0,
            calibration_link_weight=1.0,
            fallback_rank=0,
            mechanism_summary=(
                "more borrowers are clustered near the regulatory LTI boundary after the modern recalibration"
            ),
            recalibration_summary=(
                "The newer model changes purchase budgets, price scale, and deposit behaviour, "
                "which plausibly shifts more borrowers towards the LTI constraint."
            ),
            binding_checker=_binding_lti_flow,
            sources=(
                StorySource(
                    title="Financial Stability Report - December 2025 | Bank of England",
                    url="https://www.bankofengland.co.uk/financial-stability-report/2025/december-2025",
                    note="Frames current mortgage-market risk and macroprudential relevance of high-LTI lending.",
                ),
                StorySource(
                    title="Mortgage Lenders and Administrators Statistics - 2025 Q3 | Bank of England",
                    url="https://www.bankofengland.co.uk/statistics/mortgage-lenders-and-administrators/2025/2025-q3",
                    note="Provides recent mortgage lending composition and borrower risk context.",
                ),
                StorySource(
                    title="FCA sets out plans to help build mortgage market of the future",
                    url="https://www.fca.org.uk/news/press-releases/fca-sets-out-plans-help-build-mortgage-market-future",
                    note="Supports current policy discussion around mortgage market flexibility and constraint design.",
                ),
                StorySource(
                    title="Mortgage rule review | FCA",
                    url="https://www.fca.org.uk/firms/mortgage-rule-review",
                    note="Sets the regulatory backdrop for borrower-level mortgage constraint policy.",
                ),
            ),
            effective_rule="soft_vs_hard_quota",
            linked_bank_keys=("BANK_LTI_HARD_MAX_FTB", "BANK_LTI_HARD_MAX_HM"),
        ),
        PolicyStoryDefinition(
            story_id="ftb_ltv_cap",
            title="First-Time Buyer LTV Cap (Aligned Bank + Central-Bank Limit)",
            instrument_label="aligned FTB bank + central-bank hard LTV cap",
            description="Tighten or loosen the aligned first-time-buyer hard LTV cap.",
            axis_label="First-time buyer hard LTV cap",
            axis_units="ratio",
            fixed_updates={},
            swept_keys=("CENTRAL_BANK_LTV_HARD_MAX_FTB",),
            screen_values=(0.75, 0.85, 0.95),
            final_values=(0.75, 0.80, 0.85, 0.90, 0.95),
            baseline_value=0.85,
            primary_outputs=("core_advancesToFTB", "core_mortgageApprovals"),
            secondary_outputs=("core_debtToIncome", "core_priceToIncome"),
            figure_indicator_ids=("core_advancesToFTB", "core_priceToIncome", "core_mortgageApprovals"),
            figure_headline_indicator_id="core_advancesToFTB",
            expected_primary_direction=1,
            policy_relevance_weight=0.95,
            calibration_link_weight=1.0,
            fallback_rank=1,
            mechanism_summary=(
                "tighter deposit requirements matter more once deposit distributions and price levels are calibrated to modern UK evidence"
            ),
            recalibration_summary=(
                "The newer model materially updates downpayment distributions, mortgage duration, "
                "purchase budgets, and house prices, all of which affect deposit-constrained FTBs."
            ),
            binding_checker=lambda props: _binding_upper_than_bank_values(
                "BANK_LTV_HARD_MAX_FTB", (0.75, 0.85, 0.95), props
            ),
            sources=(
                StorySource(
                    title="Mortgage Lenders and Administrators Statistics - 2025 Q3 | Bank of England",
                    url="https://www.bankofengland.co.uk/statistics/mortgage-lenders-and-administrators/2025/2025-q3",
                    note="Recent evidence on borrower mix and high-LTV mortgage activity.",
                ),
                StorySource(
                    title="Mortgage Lenders and Administrators Statistics - 2025 Q1 | Bank of England",
                    url="https://www.bankofengland.co.uk/statistics/mortgage-lenders-and-administrators/2025/2025-q1",
                    note="Additional official context for mortgage approvals and borrower characteristics.",
                ),
                StorySource(
                    title="Financial Stability Report - December 2025 | Bank of England",
                    url="https://www.bankofengland.co.uk/financial-stability-report/2025/december-2025",
                    note="Explains why leverage-sensitive borrower segments matter for financial stability.",
                ),
                StorySource(
                    title="Private rent and house prices, UK: February 2026 | ONS",
                    url="https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/privaterentandhousepricesuk/february2026",
                    note="Supports the high-price/high-deposit backdrop for contemporary first-time buyers.",
                ),
            ),
            effective_rule="min_cap",
            linked_bank_keys=("BANK_LTV_HARD_MAX_FTB",),
        ),
        PolicyStoryDefinition(
            story_id="hm_ltv_cap",
            title="Home-Mover LTV Cap (Aligned Bank + Central-Bank Limit)",
            instrument_label="aligned home-mover bank + central-bank hard LTV cap",
            description="Tighten or loosen the aligned home-mover hard LTV cap.",
            axis_label="Home-mover hard LTV cap",
            axis_units="ratio",
            fixed_updates={},
            swept_keys=("CENTRAL_BANK_LTV_HARD_MAX_HM",),
            screen_values=(0.70, 0.80, 0.90),
            final_values=(0.70, 0.75, 0.80, 0.85, 0.90),
            baseline_value=0.80,
            primary_outputs=("core_advancesToHM", "core_mortgageApprovals"),
            secondary_outputs=("core_debtToIncome", "core_priceToIncome"),
            figure_indicator_ids=("core_advancesToHM", "core_priceToIncome", "core_mortgageApprovals"),
            figure_headline_indicator_id="core_advancesToHM",
            expected_primary_direction=1,
            policy_relevance_weight=0.75,
            calibration_link_weight=0.8,
            fallback_rank=2,
            mechanism_summary=(
                "newer price and income calibration changes how much leverage home movers need to transact"
            ),
            recalibration_summary=(
                "The updated house-price and purchase-budget calibration changes how often home movers need to rely on leverage."
            ),
            binding_checker=lambda props: _binding_upper_than_bank_values(
                "BANK_LTV_HARD_MAX_HM", (0.70, 0.80, 0.90), props
            ),
            sources=(),
            effective_rule="min_cap",
            linked_bank_keys=("BANK_LTV_HARD_MAX_HM",),
        ),
        PolicyStoryDefinition(
            story_id="affordability_cap",
            title="Affordability Cap (Aligned Bank + Central-Bank Limit)",
            instrument_label="aligned bank + central-bank affordability cap",
            description="Tighten or loosen the aligned cap on the income share spent on mortgage repayments.",
            axis_label="Maximum mortgage payment share of income",
            axis_units="fraction",
            fixed_updates={},
            swept_keys=("CENTRAL_BANK_AFFORDABILITY_HARD_MAX",),
            screen_values=(0.25, 0.32, 0.40),
            final_values=(0.26, 0.28, 0.30, 0.32, 0.34, 0.36, 0.38),
            baseline_value=0.32,
            primary_outputs=("core_mortgageApprovals", "core_debtToIncome"),
            secondary_outputs=("core_priceToIncome",),
            figure_indicator_ids=("core_debtToIncome", "core_priceToIncome", "core_mortgageApprovals"),
            figure_headline_indicator_id="core_debtToIncome",
            expected_primary_direction=1,
            policy_relevance_weight=0.8,
            calibration_link_weight=0.7,
            fallback_rank=3,
            mechanism_summary=(
                "repayment-burden constraints bind more often once prices and borrowing terms better match contemporary conditions"
            ),
            recalibration_summary=(
                "Updated prices, mortgage term, and purchase budgets can change how often affordability rather than leverage becomes the binding constraint."
            ),
            binding_checker=lambda props: _binding_upper_than_bank_values(
                "BANK_AFFORDABILITY_HARD_MAX", (0.25, 0.32, 0.40), props
            ),
            sources=(),
            effective_rule="min_cap",
            linked_bank_keys=("BANK_AFFORDABILITY_HARD_MAX",),
        ),
        PolicyStoryDefinition(
            story_id="btl_icr_cap",
            title="BTL ICR Cap (Aligned Bank + Central-Bank Floor)",
            instrument_label="aligned bank + central-bank BTL ICR floor",
            description="Raise or lower the aligned minimum expected rental-cover ratio for BTL borrowing.",
            axis_label="Minimum ICR",
            axis_units="ratio",
            fixed_updates={},
            swept_keys=("CENTRAL_BANK_ICR_HARD_MIN",),
            screen_values=(1.20, 1.40, 1.60),
            final_values=(1.20, 1.30, 1.40, 1.50, 1.60),
            baseline_value=1.40,
            primary_outputs=("core_advancesToBTL", "core_priceToIncome"),
            secondary_outputs=("core_debtToIncome",),
            figure_indicator_ids=("core_advancesToBTL", "core_priceToIncome", "core_debtToIncome"),
            figure_headline_indicator_id="core_advancesToBTL",
            expected_primary_direction=-1,
            policy_relevance_weight=0.65,
            calibration_link_weight=0.45,
            fallback_rank=4,
            mechanism_summary=(
                "coverage constraints tighten BTL credit only if rental yield expectations and investor incentives place borrowing close to the ICR threshold"
            ),
            recalibration_summary=(
                "Only part of the modern recalibration touches investor demand directly, so this story is weaker than owner-occupier instruments."
            ),
            binding_checker=lambda props: _binding_lower_than_bank_values(
                "BANK_ICR_HARD_MIN", (1.20, 1.40, 1.60), props
            ),
            sources=(),
            effective_rule="max_floor",
            linked_bank_keys=("BANK_ICR_HARD_MIN",),
        ),
        PolicyStoryDefinition(
            story_id="base_rate",
            title="Initial Base Rate",
            instrument_label="initial base rate",
            description="Move the central bank base rate through a small stress range.",
            axis_label="Initial base rate",
            axis_units="fraction",
            fixed_updates={},
            swept_keys=("CENTRAL_BANK_INITIAL_BASE_RATE",),
            screen_values=(0.0025, 0.0050, 0.0125),
            final_values=(0.0025, 0.0050, 0.0075, 0.0100, 0.0125),
            baseline_value=0.0050,
            primary_outputs=("core_mortgageApprovals", "core_priceToIncome"),
            secondary_outputs=("core_debtToIncome",),
            figure_indicator_ids=("core_mortgageApprovals", "core_priceToIncome", "core_debtToIncome"),
            figure_headline_indicator_id="core_mortgageApprovals",
            expected_primary_direction=-1,
            policy_relevance_weight=0.5,
            calibration_link_weight=0.3,
            fallback_rank=5,
            mechanism_summary=(
                "the monetary channel is weaker than the macroprudential channel in this model"
            ),
            recalibration_summary=(
                "The modern calibration changes are more structural and macroprudential than monetary, so rate stories are expected to be weaker."
            ),
            binding_checker=_always_binding,
            sources=(
                StorySource(
                    title="Money and Credit - December 2025 | Bank of England",
                    url="https://www.bankofengland.co.uk/statistics/money-and-credit/2025/december-2025",
                    note="Provides recent official bank-rate and credit-market context.",
                ),
                StorySource(
                    title="Interest rate ‘stress test’ rule – application of MCOB 11.6.18R | FCA",
                    url="https://www.fca.org.uk/firms/interest-rate-stress-test-rule",
                    note="Explains current treatment of mortgage rate stress-testing in regulation.",
                ),
            ),
            appendix_only=True,
            effective_rule="structurally_weak",
            linked_bank_keys=("BANK_INITIAL_RATE",),
        ),
    ]


def load_version_properties(repo_root: Path, version: str) -> dict[str, str]:
    """Read one version snapshot config."""

    config_path = repo_root / "input-data-versions" / version / "config.properties"
    return read_properties(config_path)


def story_binding_by_version(
    story: PolicyStoryDefinition,
    *,
    repo_root: Path,
    versions: Sequence[str],
) -> dict[str, bool]:
    """Evaluate whether a story has a binding grid in each version."""

    return {
        version: story.binding_checker(load_version_properties(repo_root, version))
        for version in versions
    }


def eligible_stories_by_binding(
    stories: Sequence[PolicyStoryDefinition],
    *,
    repo_root: Path,
    versions: Sequence[str],
) -> tuple[list[PolicyStoryDefinition], dict[str, dict[str, bool]]]:
    """Return stories that bind in all requested versions."""

    binding_matrix = {
        story.story_id: story_binding_by_version(story, repo_root=repo_root, versions=versions)
        for story in stories
    }
    eligible = [
        story
        for story in stories
        if all(binding_matrix[story.story_id].values())
    ]
    return eligible, binding_matrix


def story_binding_details(
    story: PolicyStoryDefinition,
    *,
    repo_root: Path,
    versions: Sequence[str],
) -> dict[str, BindingEvaluation]:
    """Return binding diagnostics for each requested version."""

    details: dict[str, BindingEvaluation] = {}
    for version in versions:
        props = load_version_properties(repo_root, version)
        details[version] = BindingEvaluation(
            binds=story.binding_checker(props),
            relevant_values=relevant_policy_values(story, props),
            reason=binding_reason(story, props),
        )
    return details


def relevant_policy_values(story: PolicyStoryDefinition, props: Mapping[str, str]) -> dict[str, str]:
    """Return the key baseline policy values that matter for a story."""

    key_map = {
        "lti_flow_limit_bundle": (
            "CENTRAL_BANK_LTI_SOFT_MAX_FTB",
            "CENTRAL_BANK_LTI_SOFT_MAX_HM",
            "CENTRAL_BANK_LTI_MAX_FRAC_OVER_SOFT_MAX_FTB",
            "CENTRAL_BANK_LTI_MAX_FRAC_OVER_SOFT_MAX_HM",
            "BANK_LTI_HARD_MAX_FTB",
            "BANK_LTI_HARD_MAX_HM",
        ),
        "ftb_ltv_cap": (
            "CENTRAL_BANK_LTV_HARD_MAX_FTB",
            "BANK_LTV_HARD_MAX_FTB",
        ),
        "hm_ltv_cap": (
            "CENTRAL_BANK_LTV_HARD_MAX_HM",
            "BANK_LTV_HARD_MAX_HM",
        ),
        "affordability_cap": (
            "CENTRAL_BANK_AFFORDABILITY_HARD_MAX",
            "BANK_AFFORDABILITY_HARD_MAX",
        ),
        "btl_icr_cap": (
            "CENTRAL_BANK_ICR_HARD_MIN",
            "BANK_ICR_HARD_MIN",
        ),
        "base_rate": (
            "CENTRAL_BANK_INITIAL_BASE_RATE",
            "BANK_INITIAL_RATE",
        ),
    }
    return {
        key: props[key]
        for key in key_map.get(story.story_id, ())
    }


def binding_reason(story: PolicyStoryDefinition, props: Mapping[str, str]) -> str:
    """Return a human-readable explanation of why the screening grid does or does not bind."""

    story_id = story.story_id
    binds = story.binding_checker(props)
    if story_id == "lti_flow_limit_bundle":
        ftb_hard = float(props["BANK_LTI_HARD_MAX_FTB"])
        hm_hard = float(props["BANK_LTI_HARD_MAX_HM"])
        if binds:
            return (
                "Binding because both representative-bank hard LTI ceilings "
                f"({ftb_hard:.1f} FTB, {hm_hard:.1f} HM) sit above the shared 4.5x soft cap."
            )
        return (
            "Not binding because at least one representative-bank hard LTI ceiling "
            "is already at or below the shared 4.5x soft cap."
        )
    if story_id == "ftb_ltv_cap":
        bank_value = float(props["BANK_LTV_HARD_MAX_FTB"])
        if binds:
            return f"Binding because the screen tightens below the representative-bank FTB hard LTV cap of {bank_value:.2f}."
        return f"Not binding because the screen never tightens below the representative-bank FTB hard LTV cap of {bank_value:.2f}."
    if story_id == "hm_ltv_cap":
        bank_value = float(props["BANK_LTV_HARD_MAX_HM"])
        if binds:
            return f"Binding because the screen tightens below the representative-bank home-mover hard LTV cap of {bank_value:.2f}."
        return f"Not binding because the screen never tightens below the representative-bank home-mover hard LTV cap of {bank_value:.2f}."
    if story_id == "affordability_cap":
        bank_value = float(props["BANK_AFFORDABILITY_HARD_MAX"])
        if binds:
            return f"Binding because the screen tightens below the representative-bank affordability cap of {bank_value:.3f}."
        return f"Not binding because the screen never tightens below the representative-bank affordability cap of {bank_value:.3f}."
    if story_id == "btl_icr_cap":
        bank_value = float(props["BANK_ICR_HARD_MIN"])
        if binds:
            return f"Binding because the screen raises the minimum ICR above the representative-bank floor of {bank_value:.2f}."
        return f"Not binding because the screen never raises the minimum ICR above the representative-bank floor of {bank_value:.2f}."
    if story_id == "base_rate":
        return (
            "Binding by construction because the sweep directly changes the central-bank base rate; "
            "no representative-bank ceiling prevents the experiment from operating."
        )
    return "Binding status follows the configured story-specific checker."


def story_lookup(stories: Sequence[PolicyStoryDefinition]) -> dict[str, PolicyStoryDefinition]:
    """Build a story-id lookup."""

    return {story.story_id: story for story in stories}


def build_story_method_audits(
    stories: Sequence[PolicyStoryDefinition],
    *,
    repo_root: Path,
    versions: Sequence[str],
) -> dict[str, StoryMethodAudit]:
    """Audit each story for raw masking and aligned-method validity."""

    return {
        story.story_id: story_method_audit(
            story,
            repo_root=repo_root,
            versions=versions,
        )
        for story in stories
    }


def story_method_audit(
    story: PolicyStoryDefinition,
    *,
    repo_root: Path,
    versions: Sequence[str],
) -> StoryMethodAudit:
    """Build the raw-versus-aligned method audit for one story."""

    version_audits: dict[str, StoryVersionMethodAudit] = {}
    for version in versions:
        props = load_version_properties(repo_root, version)
        aligned_screen_lookup = {
            point.point_id: point.updates
            for point in story.build_points("screen", aligned=True)
        }
        aligned_final_lookup = {
            point.point_id: point.updates
            for point in story.build_points("final", aligned=True)
        }
        screen_points = tuple(
            evaluate_story_point_effectiveness(
                story,
                point,
                props,
                aligned_updates=aligned_screen_lookup[point.point_id],
            )
            for point in story.build_points("screen", aligned=False)
        )
        final_points = tuple(
            evaluate_story_point_effectiveness(
                story,
                point,
                props,
                aligned_updates=aligned_final_lookup[point.point_id],
            )
            for point in story.build_points("final", aligned=False)
        )
        raw_has_conflict = any(
            not point.raw_effective
            for point in (*screen_points, *final_points)
        )
        aligned_resolves_conflict = all(
            point.aligned_effective
            for point in (*screen_points, *final_points)
        )
        note = build_story_method_note(story, props)
        version_audits[version] = StoryVersionMethodAudit(
            screen_points=screen_points,
            final_points=final_points,
            raw_has_conflict=raw_has_conflict,
            aligned_resolves_conflict=aligned_resolves_conflict,
            note=note,
        )

    shortlist_eligible = (
        story.effective_rule != "structurally_weak"
        and all(audit.aligned_resolves_conflict for audit in version_audits.values())
    )
    return StoryMethodAudit(
        story_id=story.story_id,
        title=story.title,
        effective_rule=story.effective_rule,
        linked_bank_keys=story.linked_bank_keys,
        shortlist_eligible=shortlist_eligible,
        resolution_summary=build_story_resolution_summary(story, version_audits, shortlist_eligible),
        versions=version_audits,
    )


def evaluate_story_point_effectiveness(
    story: PolicyStoryDefinition,
    point: SweepPoint,
    props: Mapping[str, str],
    *,
    aligned_updates: Mapping[str, str],
) -> MethodPointAudit:
    """Evaluate whether a raw or aligned point is effective under the model rule."""

    raw_effective, raw_reason = point_effectiveness(story, point.x_value, props, aligned=False)
    aligned_effective, aligned_reason = point_effectiveness(story, point.x_value, props, aligned=True)
    return MethodPointAudit(
        point_id=point.point_id,
        label=point.label,
        x_value=point.x_value,
        raw_effective=raw_effective,
        aligned_effective=aligned_effective,
        raw_updates=point.updates,
        aligned_updates=dict(aligned_updates),
        raw_reason=raw_reason,
        aligned_reason=aligned_reason,
    )


def point_effectiveness(
    story: PolicyStoryDefinition,
    x_value: float,
    props: Mapping[str, str],
    *,
    aligned: bool,
) -> tuple[bool, str]:
    """Return whether a given point is effective under raw or aligned semantics."""

    if story.effective_rule == "structurally_weak":
        return (
            False,
            "Structurally weak: `BANK_INITIAL_RATE` initialization offsets the central-bank base-rate change at startup."
            if not aligned
            else "Still structurally weak after alignment; this story is audited but excluded from shortlist selection.",
        )
    if story.effective_rule == "soft_vs_hard_quota":
        if story.story_id != "lti_flow_limit_bundle":
            return True, "Soft-vs-hard quota story remains valid."
        ftb_bank = float(props["BANK_LTI_HARD_MAX_FTB"])
        hm_bank = float(props["BANK_LTI_HARD_MAX_HM"])
        effective = 4.5 < ftb_bank - 1e-9 and 4.5 < hm_bank - 1e-9
        reason = (
            f"Valid because the 4.5x soft cap stays below both bank hard LTIs ({ftb_bank:.1f}, {hm_bank:.1f})."
            if effective
            else "Invalid because the 4.5x soft cap is not below both bank hard LTIs."
        )
        return effective, reason
    if story.effective_rule == "min_cap":
        bank_values = [
            x_value if aligned else float(props[key])
            for key in story.linked_bank_keys
        ]
        effective = all(x_value <= bank_value + 1e-9 for bank_value in bank_values)
        if effective:
            return True, (
                "Aligned point is active because BANK and CENTRAL_BANK are co-moved to the same cap."
                if aligned
                else "Raw point is active because the central-bank cap is at or below the bank cap."
            )
        return False, "Raw point is masked because the bank cap is tighter than the central-bank cap."
    if story.effective_rule == "max_floor":
        bank_values = [
            x_value if aligned else float(props[key])
            for key in story.linked_bank_keys
        ]
        effective = all(x_value >= bank_value - 1e-9 for bank_value in bank_values)
        if effective:
            return True, (
                "Aligned point is active because BANK and CENTRAL_BANK are co-moved to the same floor."
                if aligned
                else "Raw point is active because the central-bank floor is at or above the bank floor."
            )
        return False, "Raw point is masked because the bank floor is already tighter than the central-bank floor."
    return True, "No bank-level masking rule applies to this story."


def build_story_method_note(story: PolicyStoryDefinition, props: Mapping[str, str]) -> str:
    """Return the per-version method note for a story."""

    if story.effective_rule == "min_cap":
        bank_values = ", ".join(f"{key}={props[key]}" for key in story.linked_bank_keys)
        return f"Effective cap uses min(BANK, CENTRAL_BANK); raw masking is possible when BANK is tighter ({bank_values})."
    if story.effective_rule == "max_floor":
        bank_values = ", ".join(f"{key}={props[key]}" for key in story.linked_bank_keys)
        return f"Effective floor uses max(BANK, CENTRAL_BANK); raw masking is possible when BANK is already tighter ({bank_values})."
    if story.effective_rule == "soft_vs_hard_quota":
        return "Valid only while the 4.5x soft cap remains below the representative-bank hard LTIs."
    if story.effective_rule == "structurally_weak":
        return "Audited but excluded from shortlist selection because the central-bank base-rate sweep does not cleanly propagate through the initial bank-rate setup."
    return "No bank-level method conflict detected."


def build_story_resolution_summary(
    story: PolicyStoryDefinition,
    version_audits: Mapping[str, StoryVersionMethodAudit],
    shortlist_eligible: bool,
) -> str:
    """Summarize whether alignment resolved method conflicts for a story."""

    if story.effective_rule == "structurally_weak":
        return "Excluded from shortlist selection due to structural weakness in the current bank-rate setup."
    if shortlist_eligible and any(audit.raw_has_conflict for audit in version_audits.values()):
        return "Raw masking exists, but the aligned bank + central-bank method resolves it in every audited version."
    if shortlist_eligible:
        return "No unresolved method conflict remains after audit."
    return "Story remains method-conflicted and is excluded from shortlist selection."


def indicator_title(indicator_id: str) -> str:
    """Return a display title for an indicator."""

    return POLICY_INDICATORS[indicator_id].title


def indicator_units(indicator_id: str) -> str:
    """Return units for an indicator."""

    return POLICY_INDICATORS[indicator_id].units
