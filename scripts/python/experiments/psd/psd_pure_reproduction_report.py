#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a pure-PSD reproduction report for agreed direct keys.

Latest experiment findings (run on February 13, 2026):
  - In-scope estimated keys:
    - DOWNPAYMENT_FTB_SCALE ~= 10.4384
    - DOWNPAYMENT_FTB_SHAPE ~= 0.8793
    - DOWNPAYMENT_OO_SCALE ~= 11.1442
    - DOWNPAYMENT_OO_SHAPE ~= 0.9250
    - BANK_LTI_HARD_MAX_FTB ~= 5.4 (rounded policy estimate)
    - BANK_LTI_HARD_MAX_HM ~= 5.6 (rounded policy estimate)
  - Interpretation:
    - Uniform within-bin downpayment moments improve direct-target reproduction while
      term and affordability observables remain absent in reviewed sections.

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.common.paths import ensure_output_dir
from scripts.python.helpers.psd.config_targets import (
    PURE_BLOCKED_KEYS,
    PURE_DIRECT_KEYS,
)
from scripts.python.experiments.psd.psd_downpayment_lognormal_method_search import (
    DEFAULT_DOWNPAYMENT_METHOD,
    DownpaymentMethodResult,
    run_downpayment_search,
)
from scripts.python.experiments.psd.psd_lti_hard_max_method_search import (
    DEFAULT_LTI_METHOD,
    LtiMethodResult,
    run_lti_search,
)

BLOCKED_RATIONALE = (
    "No direct mortgage-term or DSR/affordability fields exist in reviewed PSD mortgage "
    "CSV sections (p2/p3/p5/p6)."
)


@dataclass(frozen=True)
class ReportRow:
    key: str
    target: float
    estimate: float | None
    abs_error: float | None
    method_id: str
    status: str
    rationale: str


def _find_default_lti_result(results: list[LtiMethodResult]) -> LtiMethodResult:
    for result in results:
        if result.method == DEFAULT_LTI_METHOD:
            return result
    raise ValueError("Default LTI method not found in search results.")


def _find_default_downpayment_result(
    results: list[DownpaymentMethodResult],
) -> DownpaymentMethodResult:
    for result in results:
        if result.method == DEFAULT_DOWNPAYMENT_METHOD:
            return result
    raise ValueError("Default downpayment method not found in search results.")


def build_report_rows(
    *,
    lti_default: LtiMethodResult,
    lti_targets: tuple[float, float],
    downpayment_default: DownpaymentMethodResult,
    downpayment_targets: tuple[float, float, float, float],
) -> list[ReportRow]:
    rows: list[ReportRow] = []

    target_lti_ftb, target_lti_hm = lti_targets
    target_ftb_scale, target_ftb_shape, target_oo_scale, target_oo_shape = (
        downpayment_targets
    )

    lti_method_id = lti_default.method.method_id
    down_method_id = downpayment_default.method.method_id

    rows.extend(
        [
            ReportRow(
                key="DOWNPAYMENT_FTB_SCALE",
                target=target_ftb_scale,
                estimate=downpayment_default.ftb_scale,
                abs_error=abs(downpayment_default.ftb_scale - target_ftb_scale),
                method_id=down_method_id,
                status="estimated",
                rationale="Closest defensible method from downpayment search.",
            ),
            ReportRow(
                key="DOWNPAYMENT_FTB_SHAPE",
                target=target_ftb_shape,
                estimate=downpayment_default.ftb_shape,
                abs_error=abs(downpayment_default.ftb_shape - target_ftb_shape),
                method_id=down_method_id,
                status="estimated",
                rationale="Closest defensible method from downpayment search.",
            ),
            ReportRow(
                key="DOWNPAYMENT_OO_SCALE",
                target=target_oo_scale,
                estimate=downpayment_default.oo_scale,
                abs_error=abs(downpayment_default.oo_scale - target_oo_scale),
                method_id=down_method_id,
                status="estimated",
                rationale="Closest defensible method from downpayment search.",
            ),
            ReportRow(
                key="DOWNPAYMENT_OO_SHAPE",
                target=target_oo_shape,
                estimate=downpayment_default.oo_shape,
                abs_error=abs(downpayment_default.oo_shape - target_oo_shape),
                method_id=down_method_id,
                status="estimated",
                rationale="Closest defensible method from downpayment search.",
            ),
            ReportRow(
                key="BANK_LTI_HARD_MAX_FTB",
                target=target_lti_ftb,
                estimate=lti_default.ftb_estimate_rounded,
                abs_error=abs(lti_default.ftb_estimate_rounded - target_lti_ftb),
                method_id=lti_method_id,
                status="estimated",
                rationale="Rounded to 1dp policy precision after method search.",
            ),
            ReportRow(
                key="BANK_LTI_HARD_MAX_HM",
                target=target_lti_hm,
                estimate=lti_default.hm_estimate_rounded,
                abs_error=abs(lti_default.hm_estimate_rounded - target_lti_hm),
                method_id=lti_method_id,
                status="estimated",
                rationale="Rounded to 1dp policy precision after method search.",
            ),
        ]
    )

    rows.extend(
        [
            ReportRow(
                key="MORTGAGE_DURATION_YEARS",
                target=float("nan"),
                estimate=None,
                abs_error=None,
                method_id="blocked",
                status="blocked",
                rationale=BLOCKED_RATIONALE,
            ),
            ReportRow(
                key="BANK_AFFORDABILITY_HARD_MAX",
                target=float("nan"),
                estimate=None,
                abs_error=None,
                method_id="blocked",
                status="blocked",
                rationale=BLOCKED_RATIONALE,
            ),
        ]
    )

    return rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run pure-PSD experiments and emit a consolidated reproduction report."
    )
    parser.add_argument(
        "--p3-csv",
        default="private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p3-loan-characteristic.csv",
        help="PSD p3 loan-characteristics CSV.",
    )
    parser.add_argument(
        "--p5-csv",
        default="private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p5-property-characteristic.csv",
        help="PSD p5 property-characteristics CSV.",
    )
    parser.add_argument(
        "--p6-csv",
        default="private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p6-ftbs.csv",
        help="PSD p6 first-time-buyers CSV.",
    )
    parser.add_argument(
        "--config-path",
        default="src/main/resources/config.properties",
        help="Path to config.properties with target values.",
    )
    parser.add_argument(
        "--target-year",
        type=int,
        default=2011,
        help="Annual PSD column token (default: 2011).",
    )
    parser.add_argument(
        "--within-bin-points",
        type=int,
        default=11,
        help=(
            "Number of equal-mass midpoint samples per non-degenerate bin "
            "for downpayment lognormal-moment estimation (default: 11)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for CSV export.",
    )
    return parser


def _print_rows(rows: list[ReportRow]) -> None:
    print("key\ttarget\testimate\tabs_error\tstatus\tmethod_id\trationale")
    for row in rows:
        target = "n/a" if row.target != row.target else format_float(row.target)
        estimate = "n/a" if row.estimate is None else format_float(row.estimate)
        error = "n/a" if row.abs_error is None else format_float(row.abs_error)
        print(
            f"{row.key}\t{target}\t{estimate}\t{error}\t{row.status}\t"
            f"{row.method_id}\t{row.rationale}"
        )


def _write_csv(rows: list[ReportRow], output_dir: str) -> Path:
    output_root = ensure_output_dir(output_dir)
    output_path = output_root / "PsdPureReproductionReport.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "key",
                "target",
                "estimate",
                "abs_error",
                "method_id",
                "status",
                "rationale",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.key,
                    "" if row.target != row.target else row.target,
                    "" if row.estimate is None else row.estimate,
                    "" if row.abs_error is None else row.abs_error,
                    row.method_id,
                    row.status,
                    row.rationale,
                ]
            )
    return output_path


def main() -> None:
    args = build_arg_parser().parse_args()

    lti_output = run_lti_search(
        p3_csv=Path(args.p3_csv),
        p6_csv=Path(args.p6_csv),
        config_path=Path(args.config_path),
        target_year=args.target_year,
    )
    down_output = run_downpayment_search(
        p3_csv=Path(args.p3_csv),
        p5_csv=Path(args.p5_csv),
        p6_csv=Path(args.p6_csv),
        config_path=Path(args.config_path),
        target_year=args.target_year,
        within_bin_points=args.within_bin_points,
    )

    lti_default = _find_default_lti_result(lti_output.results)
    down_default = _find_default_downpayment_result(down_output.results)

    report_rows = build_report_rows(
        lti_default=lti_default,
        lti_targets=(lti_output.target_ftb, lti_output.target_hm),
        downpayment_default=down_default,
        downpayment_targets=(
            down_output.target_ftb_scale,
            down_output.target_ftb_shape,
            down_output.target_oo_scale,
            down_output.target_oo_shape,
        ),
    )

    print("PSD pure-direct reproduction report")
    print(f"Config: {args.config_path}")
    print(f"Target year: {args.target_year}")
    print(f"Pure direct keys expected: {len(PURE_DIRECT_KEYS)}")
    print(f"Pure blocked keys expected: {len(PURE_BLOCKED_KEYS)}")
    print("")
    _print_rows(report_rows)

    if args.output_dir:
        output_path = _write_csv(report_rows, args.output_dir)
        print(f"\nWrote: {output_path}")


if __name__ == "__main__":
    main()
