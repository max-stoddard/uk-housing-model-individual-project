#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Search PPD house-price lognormal method variants against legacy config targets.

Latest experiment findings (run on February 14, 2026):
  - Dataset: private-datasets/ppd/pp-2011.csv
  - Config: input-data-versions/v0/config.properties
  - Targets:
    - HOUSE_PRICES_SCALE = 12.1186367865
    - HOUSE_PRICES_SHAPE = 0.641448422215
  - Closest method:
    - category=all|status=a_only|year=all_rows|std=population|trim=0
    - Scale = 12.1189565725
    - Shape = 0.6420133316
    - Distance ~= 0.0006491423
  - Interpretation:
    - A narrow non-zero mismatch persists across focused method variants, indicating
      likely data-snapshot drift versus the original 2011 calibration input.

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.common.io_properties import read_properties
from scripts.python.helpers.common.paths import ensure_output_dir
from scripts.python.helpers.ppd.house_price_methods import (
    DEFAULT_TRIM_FRACTIONS,
    SearchOutput,
    load_ppd_rows,
    run_method_search,
)

TARGET_SCALE_KEY = "HOUSE_PRICES_SCALE"
TARGET_SHAPE_KEY = "HOUSE_PRICES_SHAPE"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search PPD house-price method variants by closeness to legacy config targets.",
    )
    parser.add_argument(
        "ppd_csv",
        help="Path to PPD CSV file (headerless).",
    )
    parser.add_argument(
        "--config-path",
        default="input-data-versions/v0/config.properties",
        help="Path to config.properties containing target keys (default: input-data-versions/v0/config.properties).",
    )
    parser.add_argument(
        "--target-scale-key",
        default=TARGET_SCALE_KEY,
        help=f"Config key for target scale (default: {TARGET_SCALE_KEY}).",
    )
    parser.add_argument(
        "--target-shape-key",
        default=TARGET_SHAPE_KEY,
        help=f"Config key for target shape (default: {TARGET_SHAPE_KEY}).",
    )
    parser.add_argument(
        "--target-scale",
        type=float,
        default=None,
        help="Optional explicit target scale override.",
    )
    parser.add_argument(
        "--target-shape",
        type=float,
        default=None,
        help="Optional explicit target shape override.",
    )
    parser.add_argument(
        "--target-year",
        type=int,
        default=2011,
        help="Target transfer year used by year-based methods (default: 2011).",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="CSV delimiter (default: ',').",
    )
    parser.add_argument(
        "--skip-rows",
        type=int,
        default=0,
        help="Rows to skip at top of file before parsing (default: 0).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Top ranked methods to print (default: 20).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for CSV export.",
    )
    return parser


def resolve_targets(
    *,
    config_path: Path,
    target_scale_key: str,
    target_shape_key: str,
    target_scale_override: float | None,
    target_shape_override: float | None,
) -> tuple[float, float]:
    props = read_properties(config_path)

    if target_scale_override is None:
        if target_scale_key not in props:
            raise ValueError(f"Missing target key in config: {target_scale_key}")
        target_scale = float(props[target_scale_key])
    else:
        target_scale = float(target_scale_override)

    if target_shape_override is None:
        if target_shape_key not in props:
            raise ValueError(f"Missing target key in config: {target_shape_key}")
        target_shape = float(props[target_shape_key])
    else:
        target_shape = float(target_shape_override)

    return target_scale, target_shape


def run_house_price_method_search(
    *,
    ppd_csv: Path,
    config_path: Path,
    target_scale_key: str,
    target_shape_key: str,
    target_scale_override: float | None,
    target_shape_override: float | None,
    target_year: int,
    delimiter: str,
    skip_rows: int,
) -> SearchOutput:
    if target_year <= 0:
        raise ValueError("target_year must be positive.")
    if skip_rows < 0:
        raise ValueError("skip_rows cannot be negative.")

    rows, parse_stats = load_ppd_rows(
        ppd_csv,
        delimiter=delimiter,
        skip_rows=skip_rows,
    )
    target_scale, target_shape = resolve_targets(
        config_path=config_path,
        target_scale_key=target_scale_key,
        target_shape_key=target_shape_key,
        target_scale_override=target_scale_override,
        target_shape_override=target_shape_override,
    )

    return run_method_search(
        rows,
        target_scale=target_scale,
        target_shape=target_shape,
        target_year=target_year,
        parse_stats=parse_stats,
        trim_fractions=DEFAULT_TRIM_FRACTIONS,
    )


def _write_csv(output: SearchOutput, output_dir: str) -> Path:
    output_root = ensure_output_dir(output_dir)
    output_path = output_root / "PpdHousePriceLognormalMethodSearch.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank",
                "method_id",
                "category_mode",
                "status_mode",
                "year_mode",
                "std_mode",
                "trim_fraction",
                "rows_after_category",
                "rows_after_status",
                "rows_after_year",
                "rows_used",
                "trimmed_each_side",
                "scale",
                "shape",
                "distance",
                "abs_d_scale",
                "abs_d_shape",
            ]
        )
        for rank, result in enumerate(output.results, start=1):
            writer.writerow(
                [
                    rank,
                    result.method.method_id,
                    result.method.category_mode,
                    result.method.status_mode,
                    result.method.year_mode,
                    result.method.std_mode,
                    result.method.trim_fraction,
                    result.rows_after_category,
                    result.rows_after_status,
                    result.rows_after_year,
                    result.rows_used,
                    result.trimmed_each_side,
                    result.mu,
                    result.sigma,
                    result.distance,
                    result.abs_d_mu,
                    result.abs_d_sigma,
                ]
            )
    return output_path


def main() -> None:
    args = build_arg_parser().parse_args()
    ppd_path = Path(args.ppd_csv)
    config_path = Path(args.config_path)
    if not ppd_path.exists():
        raise SystemExit(f"Missing PPD CSV: {ppd_path}")
    if not config_path.exists():
        raise SystemExit(f"Missing config file: {config_path}")
    if args.top_k <= 0:
        raise SystemExit("top-k must be positive.")

    output = run_house_price_method_search(
        ppd_csv=ppd_path,
        config_path=config_path,
        target_scale_key=args.target_scale_key,
        target_shape_key=args.target_shape_key,
        target_scale_override=args.target_scale,
        target_shape_override=args.target_shape,
        target_year=args.target_year,
        delimiter=args.delimiter,
        skip_rows=args.skip_rows,
    )
    best = output.results[0]

    print("PPD house-price lognormal method search")
    print(f"Dataset: {args.ppd_csv}")
    print(f"Config: {args.config_path}")
    print(f"Target year: {args.target_year}")
    print(f"Target {args.target_scale_key} = {format_float(output.target_scale)}")
    print(f"Target {args.target_shape_key} = {format_float(output.target_shape)}")
    print("")
    print("Parse diagnostics")
    print(f"Total rows read: {output.parse_stats.total_rows}")
    print(f"Rows skipped (cli): {output.parse_stats.skipped_rows}")
    print(f"Rows loaded: {output.parse_stats.rows_loaded}")
    print(f"Rows missing required fields: {output.parse_stats.rows_missing_required_fields}")
    print(f"Rows invalid price: {output.parse_stats.rows_invalid_price}")
    print(f"Rows non-positive price: {output.parse_stats.rows_non_positive_price}")
    print(f"Rows invalid transfer year: {output.parse_stats.rows_invalid_transfer_year}")
    print(f"Methods skipped (empty filtered sample): {output.skipped_methods}")
    print("")
    print(
        "Rank\tDistance\t|dScale|\t|dShape|\tRowsUsed\tScale\tShape\tMethod"
    )
    for rank, result in enumerate(output.results[: args.top_k], start=1):
        print(
            f"{rank}\t{format_float(result.distance)}\t"
            f"{format_float(result.abs_d_mu)}\t{format_float(result.abs_d_sigma)}\t"
            f"{result.rows_used}\t{format_float(result.mu)}\t{format_float(result.sigma)}\t"
            f"{result.method.method_id}"
        )

    print("")
    print("Best method summary")
    print(f"Method: {best.method.method_id}")
    print(f"Scale ~= {format_float(best.mu)}")
    print(f"Shape ~= {format_float(best.sigma)}")
    print(f"Distance ~= {format_float(best.distance)}")
    if best.distance <= 1e-12:
        print("Exact reproduction: yes")
    else:
        print("Exact reproduction: no")
        print(
            "No exact reproduction found in focused grid; this can indicate data-snapshot "
            "differences versus the original calibration input."
        )

    if args.output_dir is not None:
        output_path = _write_csv(output, args.output_dir)
        print(f"\nCSV output: {output_path}")


if __name__ == "__main__":
    main()
