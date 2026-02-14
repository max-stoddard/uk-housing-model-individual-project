#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calibrate PSD pure-direct parameters from 2024 long-format PSD datasets.

Latest experiment findings (run on February 13, 2026):
  - Quarterly dataset: private-datasets/psd/2024/psd-quarterly-2024.csv
  - Monthly diagnostics:
    - private-datasets/psd/2024/psd-monthly-2024-p1-sales-borrower.csv
    - private-datasets/psd/2024/psd-monthly-2024-p2-ltv-sales.csv
  - Downpayment method:
    - median_anchored_nonftb_independent
    - robust candidate selected from 32 combinations
  - Mortgage-duration method is intentionally user-selected via --term-method
    (decision gate after method-search results).
  - Interpretation:
    - 2024 quarterly PSD is sufficient for downpayment + term calibration,
      while LTI/affordability keys remain blocked without direct observables.

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.common.paths import ensure_output_dir
from scripts.python.helpers.psd.calibration_2024 import (
    ConsistencyCheckResult,
    SUPPORTED_DOWNPAYMENT_METHOD,
    SUPPORTED_TERM_METHODS,
    calibrate_downpayment_2024,
    calibrate_mortgage_duration_2024,
    compare_quarterly_monthly_consistency,
)
from scripts.python.helpers.psd.quarterly_long import (
    load_monthly_psd_rows,
    load_quarterly_psd_rows,
)


BLOCKED_KEYS = (
    "BANK_LTI_HARD_MAX_FTB",
    "BANK_LTI_HARD_MAX_HM",
    "BANK_AFFORDABILITY_HARD_MAX",
)
BLOCKED_RATIONALE = (
    "No direct LTI-bin or affordability-ratio observables are available in "
    "provided PSD 2024 files."
)


@dataclass(frozen=True)
class CalibrationRow:
    key: str
    value: str
    status: str
    method_id: str
    rationale: str


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate PSD pure-direct keys for 2024 from quarterly long-format data.",
    )
    parser.add_argument(
        "--quarterly-csv",
        default="private-datasets/psd/2024/psd-quarterly-2024.csv",
        help="Path to PSD 2024 quarterly CSV.",
    )
    parser.add_argument(
        "--monthly-p1-csv",
        default=None,
        help="Optional monthly borrower CSV for consistency diagnostics.",
    )
    parser.add_argument(
        "--monthly-p2-csv",
        default=None,
        help="Optional monthly LTV CSV for consistency diagnostics.",
    )
    parser.add_argument(
        "--target-year",
        type=int,
        default=2024,
        help="Target calendar year (default: 2024).",
    )
    parser.add_argument(
        "--downpayment-method",
        default=SUPPORTED_DOWNPAYMENT_METHOD,
        choices=[SUPPORTED_DOWNPAYMENT_METHOD],
        help="Downpayment method (default: median_anchored_nonftb_independent).",
    )
    parser.add_argument(
        "--term-method",
        required=True,
        choices=SUPPORTED_TERM_METHODS,
        help=(
            "Mortgage-duration method decision gate. Required in first implementation pass "
            "(choose from weighted_mean_round, weighted_median_round, modal_midpoint_round)."
        ),
    )
    parser.add_argument(
        "--term-open-top-year",
        type=int,
        default=45,
        help="Open-top assumption for >35 years term bin (default: 45).",
    )
    parser.add_argument(
        "--within-bin-points",
        type=int,
        default=11,
        help="Within-bin integration points for downpayment lognormal fitting (default: 11).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for CSV export.",
    )
    return parser


def _load_optional_monthly(path_value: str | None) -> list | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        raise ValueError(f"Missing optional monthly CSV: {path}")
    return load_monthly_psd_rows(path)


def _print_consistency_checks(checks: list[ConsistencyCheckResult]) -> None:
    print("Consistency diagnostics (quarterly vs monthly)")
    for check in checks:
        if not check.checked:
            print(f"- {check.name}: skipped (monthly file not provided)")
            continue
        print(
            f"- {check.name}: {'MATCH' if check.matches else 'DIFF'} "
            f"(total_difference={format_float(check.total_difference)})"
        )


def _build_rows(
    *,
    downpayment_result,
    mortgage_duration_result,
) -> list[CalibrationRow]:
    downpayment_method_id = (
        "median_anchored_nonftb_independent|"
        f"ltv_open={downpayment_result.ltv_open_upper}|"
        f"property_open_k={downpayment_result.property_open_upper_k}|"
        f"coupling={downpayment_result.coupling}"
    )
    term_method_id = (
        f"{mortgage_duration_result.method}|"
        f"open_top={mortgage_duration_result.open_top_year}"
    )

    rows = [
        CalibrationRow(
            key="DOWNPAYMENT_FTB_SCALE",
            value=format_float(downpayment_result.ftb_scale),
            status="estimated",
            method_id=downpayment_method_id,
            rationale="2024 robust central estimate over median-anchored tail grid.",
        ),
        CalibrationRow(
            key="DOWNPAYMENT_FTB_SHAPE",
            value=format_float(downpayment_result.ftb_shape),
            status="estimated",
            method_id=downpayment_method_id,
            rationale="2024 robust central estimate over median-anchored tail grid.",
        ),
        CalibrationRow(
            key="DOWNPAYMENT_OO_SCALE",
            value=format_float(downpayment_result.oo_scale),
            status="estimated",
            method_id=downpayment_method_id,
            rationale=(
                "Non-FTB proxy (all minus FTB) from 2024 bins; "
                "remortgagor contamination caveat applies."
            ),
        ),
        CalibrationRow(
            key="DOWNPAYMENT_OO_SHAPE",
            value=format_float(downpayment_result.oo_shape),
            status="estimated",
            method_id=downpayment_method_id,
            rationale=(
                "Non-FTB proxy (all minus FTB) from 2024 bins; "
                "remortgagor contamination caveat applies."
            ),
        ),
        CalibrationRow(
            key="MORTGAGE_DURATION_YEARS",
            value=str(mortgage_duration_result.estimate_rounded),
            status="estimated",
            method_id=term_method_id,
            rationale=(
                "Estimated from 2024 mortgage-term bands with selected method; "
                "unspecified band excluded."
            ),
        ),
    ]
    for key in BLOCKED_KEYS:
        rows.append(
            CalibrationRow(
                key=key,
                value="",
                status="blocked",
                method_id="blocked",
                rationale=BLOCKED_RATIONALE,
            )
        )
    return rows


def _write_csv(rows: list[CalibrationRow], output_dir: str) -> Path:
    output_root = ensure_output_dir(output_dir)
    output_path = output_root / "Psd2024PureDirectCalibration.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "value", "status", "method_id", "rationale"])
        for row in rows:
            writer.writerow([row.key, row.value, row.status, row.method_id, row.rationale])
    return output_path


def main() -> None:
    args = build_arg_parser().parse_args()
    quarterly_path = Path(args.quarterly_csv)
    if not quarterly_path.exists():
        raise SystemExit(f"Missing quarterly CSV: {quarterly_path}")

    if args.term_open_top_year <= 35:
        raise SystemExit("term-open-top-year must be > 35.")
    if args.within_bin_points <= 0:
        raise SystemExit("within-bin-points must be positive.")

    quarterly_rows = load_quarterly_psd_rows(quarterly_path)
    monthly_p1_rows = _load_optional_monthly(args.monthly_p1_csv)
    monthly_p2_rows = _load_optional_monthly(args.monthly_p2_csv)

    downpayment_result = calibrate_downpayment_2024(
        quarterly_rows,
        target_year=args.target_year,
        within_bin_points=args.within_bin_points,
        method_name=args.downpayment_method,
    )
    mortgage_duration_result = calibrate_mortgage_duration_2024(
        quarterly_rows,
        target_year=args.target_year,
        method_name=args.term_method,
        open_top_year=args.term_open_top_year,
    )
    consistency_checks = compare_quarterly_monthly_consistency(
        quarterly_rows,
        target_year=args.target_year,
        monthly_p1_rows=monthly_p1_rows,
        monthly_p2_rows=monthly_p2_rows,
    )
    rows = _build_rows(
        downpayment_result=downpayment_result,
        mortgage_duration_result=mortgage_duration_result,
    )

    print("PSD 2024 pure-direct calibration")
    print(f"Quarterly CSV: {args.quarterly_csv}")
    print(f"Target year: {args.target_year}")
    print(f"Downpayment method: {args.downpayment_method}")
    print(f"Term method: {args.term_method}")
    print(f"Term open-top year: {args.term_open_top_year}")
    print(f"Within-bin points: {args.within_bin_points}")
    print("")
    print("Downpayment diagnostics")
    print(
        f"- property-tail candidates (k GBP): "
        f"{', '.join(str(int(round(item))) for item in downpayment_result.property_tail_candidates_k)}"
    )
    print(
        f"- robust anchor property (k GBP): "
        f"{format_float(downpayment_result.robust_anchor_property_k)}"
    )
    print(f"- candidate count: {downpayment_result.candidate_count}")
    print(
        "- selected candidate: "
        f"ltv_open={format_float(downpayment_result.ltv_open_upper)}, "
        f"property_open_k={format_float(downpayment_result.property_open_upper_k)}, "
        f"coupling={downpayment_result.coupling}"
    )
    print("")
    print("Mortgage-duration diagnostics")
    print(f"- raw estimate: {format_float(mortgage_duration_result.estimate_raw)}")
    print(f"- rounded estimate: {mortgage_duration_result.estimate_rounded}")
    print(
        "- excluded unspecified term share: "
        f"{format_float(mortgage_duration_result.excluded_share * 100.0)}%"
    )
    print("")
    _print_consistency_checks(consistency_checks)
    print("")
    print("Config-ready values")
    for row in rows:
        if row.status == "estimated":
            print(f"{row.key} = {row.value}")
    print("")
    print("Blocked keys")
    for row in rows:
        if row.status == "blocked":
            print(f"{row.key}: {row.rationale}")

    if args.output_dir:
        output_path = _write_csv(rows, args.output_dir)
        print(f"\nWrote: {output_path}")


if __name__ == "__main__":
    main()
