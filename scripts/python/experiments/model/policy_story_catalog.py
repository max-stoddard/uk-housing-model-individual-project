#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Policy-story catalog for the Bank of England demo workflow.

@author: Max Stoddard
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from scripts.python.helpers.common.abm_policy_sweep import POLICY_INDICATORS, SweepPoint, build_sweep_points
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

    def build_points(self, stage_name: str) -> list[SweepPoint]:
        values = self.screen_values if stage_name == "screen" else self.final_values
        return build_sweep_points(
            values=values,
            baseline_value=self.baseline_value,
            fixed_updates=self.fixed_updates,
            swept_keys=self.swept_keys,
        )

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
        ),
        PolicyStoryDefinition(
            story_id="ftb_ltv_cap",
            title="First-Time Buyer LTV Cap",
            instrument_label="FTB hard LTV cap",
            description="Tighten or loosen the first-time-buyer hard LTV cap.",
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
        ),
        PolicyStoryDefinition(
            story_id="hm_ltv_cap",
            title="Home-Mover LTV Cap",
            instrument_label="home-mover hard LTV cap",
            description="Tighten or loosen the home-mover hard LTV cap.",
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
        ),
        PolicyStoryDefinition(
            story_id="affordability_cap",
            title="Affordability Cap",
            instrument_label="mortgage affordability cap",
            description="Tighten or loosen the cap on the income share spent on mortgage repayments.",
            axis_label="Maximum mortgage payment share of income",
            axis_units="fraction",
            fixed_updates={},
            swept_keys=("CENTRAL_BANK_AFFORDABILITY_HARD_MAX",),
            screen_values=(0.25, 0.325, 0.40),
            final_values=(0.25, 0.28, 0.31, 0.325, 0.34, 0.37, 0.40),
            baseline_value=0.325,
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
                "BANK_AFFORDABILITY_HARD_MAX", (0.25, 0.325, 0.40), props
            ),
            sources=(),
        ),
        PolicyStoryDefinition(
            story_id="btl_icr_cap",
            title="BTL ICR Cap",
            instrument_label="BTL interest coverage ratio cap",
            description="Raise or lower the minimum expected rental-cover ratio for BTL borrowing.",
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


def story_lookup(stories: Sequence[PolicyStoryDefinition]) -> dict[str, PolicyStoryDefinition]:
    """Build a story-id lookup."""

    return {story.story_id: story for story in stories}


def indicator_title(indicator_id: str) -> str:
    """Return a display title for an indicator."""

    return POLICY_INDICATORS[indicator_id].title


def indicator_units(indicator_id: str) -> str:
    """Return units for an indicator."""

    return POLICY_INDICATORS[indicator_id].units
