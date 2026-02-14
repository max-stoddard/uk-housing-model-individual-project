#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calibrate BUY* parameters from modern PSD + PPD datasets.

Latest experiment findings (run on February 14, 2026):
  - Method default selected via 2011 reproduction-first search:
    psd_log_ols_robust_mu with comonotonic couplings and
    open-bin assumptions loan=500k, lti=[2.5,10], income=100k, property=10000k,
    quantile grid=4000, mu_hi_trim=0.0063.
  - 2011 reproduction evidence:
    - best normalized distance ~= 0.02926 against legacy BUY* targets
      from PSD 2011 + PPD 2011 method search.
  - Production inputs:
    - PSD: private-datasets/psd/2024/psd-quarterly-2024.csv
    - PPD: private-datasets/ppd/pp-2025.csv

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.common.paths import ensure_output_dir
from scripts.python.helpers.psd.buy_budget_methods import (
    DEFAULT_SELECTED_METHOD,
    parse_method_id,
    run_modern_calibration,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate BUY* values from modern PSD + PPD datasets.",
    )
    parser.add_argument(
        "--quarterly-csv",
        default="private-datasets/psd/2024/psd-quarterly-2024.csv",
        help="Path to PSD quarterly long-format CSV.",
    )
    parser.add_argument(
        "--ppd-csv",
        default="private-datasets/ppd/pp-2025.csv",
        help="Path to PPD CSV.",
    )
    parser.add_argument(
        "--target-year-psd",
        type=int,
        default=2024,
        help="Target year for modern PSD aggregates (default: 2024).",
    )
    parser.add_argument(
        "--target-year-ppd",
        type=int,
        default=2025,
        help="Target year for PPD moments (default: 2025).",
    )
    parser.add_argument(
        "--method",
        default=DEFAULT_SELECTED_METHOD.method_id,
        help="Method id (default fixed to selected production method).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for CSV export.",
    )
    return parser


def _write_csv(
    *,
    output_dir: str,
    key_values: list[tuple[str, str]],
    method_id: str,
    diagnostics: dict[str, str],
) -> Path:
    output_root = ensure_output_dir(output_dir)
    output_path = output_root / "PsdBuyBudgetCalibration.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "value", "method_id"])
        for key, value in key_values:
            writer.writerow([key, value, method_id])
        writer.writerow([])
        writer.writerow(["diagnostic", "value", ""])
        for key in sorted(diagnostics.keys()):
            writer.writerow([key, diagnostics[key], ""])
    return output_path


def main() -> None:
    args = build_arg_parser().parse_args()

    quarterly_path = Path(args.quarterly_csv)
    ppd_path = Path(args.ppd_csv)
    missing = [str(path) for path in (quarterly_path, ppd_path) if not path.exists()]
    if missing:
        raise SystemExit("Missing input file(s): " + ", ".join(missing))

    method = parse_method_id(args.method)

    output = run_modern_calibration(
        quarterly_csv=quarterly_path,
        ppd_csv=ppd_path,
        target_year_psd=args.target_year_psd,
        target_year_ppd=args.target_year_ppd,
        method=method,
    )

    key_values = [
        ("BUY_SCALE", format_float(output.buy_scale)),
        ("BUY_EXPONENT", format_float(output.buy_exponent)),
        ("BUY_MU", format_float(output.buy_mu)),
        ("BUY_SIGMA", format_float(output.buy_sigma)),
    ]

    print("PSD BUY* production calibration")
    print(f"Quarterly PSD: {args.quarterly_csv}")
    print(f"PPD: {args.ppd_csv}")
    print(f"Target year PSD: {args.target_year_psd}")
    print(f"Target year PPD: {args.target_year_ppd}")
    print(f"Method: {output.method.method_id}")
    print("")
    print("Computed BUY* parameters")
    for key, value in key_values:
        print(f"{key} = {value}")

    print("\nDiagnostics")
    print(f"PPD rows total: {output.ppd_stats.rows_total}")
    print(f"PPD rows used: {output.ppd_stats.rows_used}")
    print(f"PPD mean log(price): {format_float(output.ppd_stats.mean_log_price)}")
    print(f"PPD var log(price): {format_float(output.ppd_stats.variance_log_price)}")
    print(f"Paired sample size: {output.diagnostics.paired_sample_size}")
    print(f"Trimmed each side: {output.diagnostics.trimmed_each_side}")
    print(f"Sigma^2 clamped to zero: {output.diagnostics.sigma2_clamped_to_zero}")
    for key in sorted(output.modern_diagnostics.keys()):
        print(f"{key}: {format_float(output.modern_diagnostics[key])}")

    if args.output_dir is not None:
        diagnostics_map = {
            "ppd_rows_total": str(output.ppd_stats.rows_total),
            "ppd_rows_used": str(output.ppd_stats.rows_used),
            "ppd_mean_log_price": format_float(output.ppd_stats.mean_log_price),
            "ppd_var_log_price": format_float(output.ppd_stats.variance_log_price),
            "paired_sample_size": str(output.diagnostics.paired_sample_size),
            "trimmed_each_side": str(output.diagnostics.trimmed_each_side),
            "sigma2_clamped_to_zero": str(output.diagnostics.sigma2_clamped_to_zero),
        }
        for key in output.modern_diagnostics:
            diagnostics_map[f"modern_{key}"] = format_float(output.modern_diagnostics[key])
        output_path = _write_csv(
            output_dir=args.output_dir,
            key_values=key_values,
            method_id=output.method.method_id,
            diagnostics=diagnostics_map,
        )
        print(f"\nCSV output: {output_path}")


if __name__ == "__main__":
    main()
