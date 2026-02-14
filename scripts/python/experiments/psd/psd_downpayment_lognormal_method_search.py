#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Search PSD 2011 method variants to reproduce downpayment lognormal parameters.

Latest experiment findings (run on February 13, 2026):
  - Config: src/main/resources/config.properties
  - Targets:
    - DOWNPAYMENT_FTB_SCALE = 10.35
    - DOWNPAYMENT_FTB_SHAPE = 0.898
    - DOWNPAYMENT_OO_SCALE = 11.15
    - DOWNPAYMENT_OO_SHAPE = 0.958
  - Closest method in the expanded search:
    - FTB marginals = p6:6.3 (LTV) + p6:6.4 (property)
    - OO marginals = all_all (p3:3.4 + p5:5.1)
    - LTV open upper = 100
    - Property open upper = 4000K
    - Coupling = independent
    - within-bin points = 11
    - Estimates:
      - FTB (scale, shape) ~= (10.4399, 0.8835)
      - OO (scale, shape) ~= (11.1505, 0.9407)
    - Distance ~= 0.0927
  - Decision-record default method (kept stable):
    - all_all, ltv_open=100, property_open_k=2000, coupling=independent
    - Estimates:
      - FTB (scale, shape) ~= (10.4384, 0.8793)
      - OO (scale, shape) ~= (11.1442, 0.9250)
  - Interpretation:
    - Uniform within-bin integration plus wider open-tail bounds materially improves reproduction versus midpoint-only estimation.

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.common.io_properties import read_properties
from scripts.python.helpers.common.paths import ensure_output_dir
from scripts.python.helpers.psd.bins import (
    PsdBin,
    build_bins_from_labeled_rows,
    subtract_bin_masses,
)
from scripts.python.helpers.psd.metrics import (
    euclidean_distance,
    lognormal_params_from_synthetic_downpayment,
)
from scripts.python.helpers.psd.tables import (
    get_labeled_section_rows,
    get_year_column,
    load_psd_table,
)

TARGET_FTB_SCALE_KEY = "DOWNPAYMENT_FTB_SCALE"
TARGET_FTB_SHAPE_KEY = "DOWNPAYMENT_FTB_SHAPE"
TARGET_OO_SCALE_KEY = "DOWNPAYMENT_OO_SCALE"
TARGET_OO_SHAPE_KEY = "DOWNPAYMENT_OO_SHAPE"

OO_METHOD_CHOICES = ("all_all", "hm_sub", "hm_ltv_all_prop", "all_ltv_hm_prop")
LTV_OPEN_CHOICES = (98.0, 99.0, 100.0, 102.0, 105.0, 110.0, 120.0, 130.0)
PROPERTY_OPEN_CHOICES_K = (1000.0, 1100.0, 1200.0, 1500.0, 2000.0, 2500.0, 3000.0, 4000.0)
COUPLING_CHOICES = ("independent", "comonotonic", "countermonotonic")


@dataclass(frozen=True)
class DownpaymentMethodSpec:
    oo_method: str
    ltv_open_upper: float
    property_open_upper_k: float
    coupling: str

    @property
    def method_id(self) -> str:
        return (
            f"oo={self.oo_method}|ltv_open={self.ltv_open_upper}|"
            f"property_open_k={self.property_open_upper_k}|coupling={self.coupling}"
        )


DEFAULT_DOWNPAYMENT_METHOD = DownpaymentMethodSpec(
    oo_method="all_all",
    ltv_open_upper=100.0,
    property_open_upper_k=2000.0,
    coupling="independent",
)


@dataclass(frozen=True)
class DownpaymentMethodResult:
    method: DownpaymentMethodSpec
    ftb_scale: float
    ftb_shape: float
    oo_scale: float
    oo_shape: float
    distance: float


@dataclass(frozen=True)
class DownpaymentSearchOutput:
    results: list[DownpaymentMethodResult]
    target_ftb_scale: float
    target_ftb_shape: float
    target_oo_scale: float
    target_oo_shape: float



def _load_downpayment_distributions(
    p3_csv: Path,
    p5_csv: Path,
    p6_csv: Path,
    target_year: int,
) -> tuple[list[PsdBin], list[PsdBin], dict[str, tuple[list[PsdBin], list[PsdBin]]]]:
    p3_table = load_psd_table(p3_csv)
    p5_table = load_psd_table(p5_csv)
    p6_table = load_psd_table(p6_csv)

    p3_year = get_year_column(p3_table, target_year)
    p5_year = get_year_column(p5_table, target_year)
    p6_year = get_year_column(p6_table, target_year)

    ftb_ltv = build_bins_from_labeled_rows(get_labeled_section_rows(p6_table, "6.3"), p6_year)
    ftb_property = build_bins_from_labeled_rows(get_labeled_section_rows(p6_table, "6.4"), p6_year)

    all_ltv = build_bins_from_labeled_rows(get_labeled_section_rows(p3_table, "3.4"), p3_year)
    all_property = build_bins_from_labeled_rows(get_labeled_section_rows(p5_table, "5.1"), p5_year)

    hm_ltv = subtract_bin_masses(all_ltv, ftb_ltv)
    hm_property = subtract_bin_masses(all_property, ftb_property)

    oo_methods: dict[str, tuple[list[PsdBin], list[PsdBin]]] = {
        "all_all": (all_ltv, all_property),
        "hm_sub": (hm_ltv, hm_property),
        "hm_ltv_all_prop": (hm_ltv, all_property),
        "all_ltv_hm_prop": (all_ltv, hm_property),
    }

    return ftb_ltv, ftb_property, oo_methods



def run_downpayment_search(
    *,
    p3_csv: Path,
    p5_csv: Path,
    p6_csv: Path,
    config_path: Path,
    target_year: int,
    within_bin_points: int,
) -> DownpaymentSearchOutput:
    props = read_properties(config_path)
    required_keys = (
        TARGET_FTB_SCALE_KEY,
        TARGET_FTB_SHAPE_KEY,
        TARGET_OO_SCALE_KEY,
        TARGET_OO_SHAPE_KEY,
    )
    missing = [key for key in required_keys if key not in props]
    if missing:
        raise ValueError("Missing target keys in config: " + ", ".join(missing))

    target_ftb_scale = float(props[TARGET_FTB_SCALE_KEY])
    target_ftb_shape = float(props[TARGET_FTB_SHAPE_KEY])
    target_oo_scale = float(props[TARGET_OO_SCALE_KEY])
    target_oo_shape = float(props[TARGET_OO_SHAPE_KEY])

    ftb_ltv, ftb_property, oo_methods = _load_downpayment_distributions(
        p3_csv,
        p5_csv,
        p6_csv,
        target_year,
    )

    results: list[DownpaymentMethodResult] = []
    for oo_method in OO_METHOD_CHOICES:
        oo_ltv, oo_property = oo_methods[oo_method]
        for ltv_open_upper in LTV_OPEN_CHOICES:
            for property_open_upper_k in PROPERTY_OPEN_CHOICES_K:
                for coupling in COUPLING_CHOICES:
                    method = DownpaymentMethodSpec(
                        oo_method=oo_method,
                        ltv_open_upper=ltv_open_upper,
                        property_open_upper_k=property_open_upper_k,
                        coupling=coupling,
                    )

                    ftb_scale, ftb_shape = lognormal_params_from_synthetic_downpayment(
                        ftb_ltv,
                        ftb_property,
                        ltv_open_upper=ltv_open_upper,
                        property_open_upper_k=property_open_upper_k,
                        coupling=coupling,
                        within_bin_points=within_bin_points,
                    )
                    oo_scale, oo_shape = lognormal_params_from_synthetic_downpayment(
                        oo_ltv,
                        oo_property,
                        ltv_open_upper=ltv_open_upper,
                        property_open_upper_k=property_open_upper_k,
                        coupling=coupling,
                        within_bin_points=within_bin_points,
                    )

                    distance = euclidean_distance(
                        (ftb_scale, ftb_shape, oo_scale, oo_shape),
                        (target_ftb_scale, target_ftb_shape, target_oo_scale, target_oo_shape),
                    )
                    results.append(
                        DownpaymentMethodResult(
                            method=method,
                            ftb_scale=ftb_scale,
                            ftb_shape=ftb_shape,
                            oo_scale=oo_scale,
                            oo_shape=oo_shape,
                            distance=distance,
                        )
                    )

    results.sort(key=lambda item: (item.distance, item.method.method_id))

    return DownpaymentSearchOutput(
        results=results,
        target_ftb_scale=target_ftb_scale,
        target_ftb_shape=target_ftb_shape,
        target_oo_scale=target_oo_scale,
        target_oo_shape=target_oo_shape,
    )



def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search PSD 2011 downpayment lognormal methods by closeness to config targets."
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
        "--top-k",
        type=int,
        default=20,
        help="Number of top-ranked methods to print (default: 20).",
    )
    parser.add_argument(
        "--within-bin-points",
        type=int,
        default=11,
        help=(
            "Number of equal-mass midpoint samples per non-degenerate bin "
            "for lognormal-moment estimation (default: 11)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for CSV export.",
    )
    return parser



def _write_csv(results: list[DownpaymentMethodResult], output_dir: str) -> Path:
    output_root = ensure_output_dir(output_dir)
    output_path = output_root / "PsdDownpaymentLognormalMethodSearch.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank",
                "method_id",
                "ftb_scale",
                "ftb_shape",
                "oo_scale",
                "oo_shape",
                "distance",
            ]
        )
        for rank, item in enumerate(results, start=1):
            writer.writerow(
                [
                    rank,
                    item.method.method_id,
                    item.ftb_scale,
                    item.ftb_shape,
                    item.oo_scale,
                    item.oo_shape,
                    item.distance,
                ]
            )
    return output_path



def main() -> None:
    args = build_arg_parser().parse_args()
    output = run_downpayment_search(
        p3_csv=Path(args.p3_csv),
        p5_csv=Path(args.p5_csv),
        p6_csv=Path(args.p6_csv),
        config_path=Path(args.config_path),
        target_year=args.target_year,
        within_bin_points=args.within_bin_points,
    )

    top_k = max(1, args.top_k)

    print("PSD downpayment lognormal method search")
    print(f"P3: {args.p3_csv}")
    print(f"P5: {args.p5_csv}")
    print(f"P6: {args.p6_csv}")
    print(f"Config: {args.config_path}")
    print(f"Target year: {args.target_year}")
    print(f"Target {TARGET_FTB_SCALE_KEY} = {format_float(output.target_ftb_scale)}")
    print(f"Target {TARGET_FTB_SHAPE_KEY} = {format_float(output.target_ftb_shape)}")
    print(f"Target {TARGET_OO_SCALE_KEY} = {format_float(output.target_oo_scale)}")
    print(f"Target {TARGET_OO_SHAPE_KEY} = {format_float(output.target_oo_shape)}")
    print(f"Within-bin points: {args.within_bin_points}")
    print("")
    print(
        "Rank\tDistance\tFTB(scale)\tFTB(shape)\tOO(scale)\tOO(shape)\tMethod"
    )
    for rank, item in enumerate(output.results[:top_k], start=1):
        print(
            f"{rank}\t{format_float(item.distance)}\t{format_float(item.ftb_scale)}\t"
            f"{format_float(item.ftb_shape)}\t{format_float(item.oo_scale)}\t"
            f"{format_float(item.oo_shape)}\t{item.method.method_id}"
        )

    default_match = next(
        result for result in output.results if result.method == DEFAULT_DOWNPAYMENT_METHOD
    )
    print("\nDefault method (decision record)")
    print(f"method: {default_match.method.method_id}")
    print(
        f"FTB ~= ({format_float(default_match.ftb_scale)}, "
        f"{format_float(default_match.ftb_shape)})"
    )
    print(
        f"OO ~= ({format_float(default_match.oo_scale)}, "
        f"{format_float(default_match.oo_shape)})"
    )

    if args.output_dir:
        output_path = _write_csv(output.results, args.output_dir)
        print(f"\nWrote: {output_path}")


if __name__ == "__main__":
    main()
