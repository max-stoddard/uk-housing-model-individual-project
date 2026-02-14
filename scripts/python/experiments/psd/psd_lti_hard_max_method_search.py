#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Search PSD 2011 method variants to reproduce bank LTI hard maxima.

Latest experiment findings (run on February 13, 2026):
  - Config: src/main/resources/config.properties
  - Targets:
    - BANK_LTI_HARD_MAX_FTB = 5.4
    - BANK_LTI_HARD_MAX_HM = 5.6
  - Closest defensible default method:
    - FTB source = ftb_joint
    - HM source = hm_subtracted
    - quantile = 0.99
    - open-top upper = 6.0
    - interpolation = linear
    - Estimates (raw):
      - FTB ~= 5.3863
      - HM ~= 5.5934
    - Estimates (rounded to 1dp policy precision):
      - FTB = 5.4
      - HM = 5.6
  - Interpretation:
    - Joint-income FTB bins plus all-minus-FTB subtraction for HM reproduces policy thresholds at config precision.

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
    combine_bin_masses,
    subtract_bin_masses,
)
from scripts.python.helpers.psd.metrics import binned_weighted_quantile, euclidean_distance
from scripts.python.helpers.psd.tables import (
    get_labeled_section_rows,
    get_year_column,
    load_psd_table,
)

TARGET_FTB_KEY = "BANK_LTI_HARD_MAX_FTB"
TARGET_HM_KEY = "BANK_LTI_HARD_MAX_HM"

FTB_SOURCE_CHOICES = ("ftb_single", "ftb_joint", "ftb_combined", "all_combined")
HM_SOURCE_CHOICES = ("hm_subtracted", "single_all", "joint_all", "all_combined")
QUANTILE_CHOICES = (0.985, 0.99, 0.992, 0.995)
OPEN_TOP_CHOICES = (5.6, 5.8, 6.0, 6.5, 7.0, 8.0, 10.0)
INTERPOLATION_CHOICES = ("linear",)


@dataclass(frozen=True)
class LtiMethodSpec:
    ftb_source: str
    hm_source: str
    quantile: float
    open_top_upper: float
    interpolation: str

    @property
    def method_id(self) -> str:
        return (
            f"ftb={self.ftb_source}|hm={self.hm_source}|q={self.quantile}|"
            f"open={self.open_top_upper}|interp={self.interpolation}"
        )


DEFAULT_LTI_METHOD = LtiMethodSpec(
    ftb_source="ftb_joint",
    hm_source="hm_subtracted",
    quantile=0.99,
    open_top_upper=6.0,
    interpolation="linear",
)


@dataclass(frozen=True)
class LtiMethodResult:
    method: LtiMethodSpec
    ftb_estimate_raw: float
    hm_estimate_raw: float
    ftb_estimate_rounded: float
    hm_estimate_rounded: float
    distance_rounded: float
    distance_raw: float


@dataclass(frozen=True)
class LtiSearchOutput:
    results: list[LtiMethodResult]
    target_ftb: float
    target_hm: float



def _load_distributions(p3_csv: Path, p6_csv: Path, target_year: int) -> dict[str, list[PsdBin]]:
    p3_table = load_psd_table(p3_csv)
    p6_table = load_psd_table(p6_csv)

    p3_year = get_year_column(p3_table, target_year)
    p6_year = get_year_column(p6_table, target_year)

    all_single = build_bins_from_labeled_rows(get_labeled_section_rows(p3_table, "3.7.1"), p3_year)
    all_joint = build_bins_from_labeled_rows(get_labeled_section_rows(p3_table, "3.7.2"), p3_year)
    ftb_single = build_bins_from_labeled_rows(get_labeled_section_rows(p6_table, "6.1"), p6_year)
    ftb_joint = build_bins_from_labeled_rows(get_labeled_section_rows(p6_table, "6.2"), p6_year)

    all_combined = combine_bin_masses(all_single, all_joint)
    ftb_combined = combine_bin_masses(ftb_single, ftb_joint)
    hm_subtracted = subtract_bin_masses(all_combined, ftb_combined)

    return {
        "ftb_single": ftb_single,
        "ftb_joint": ftb_joint,
        "ftb_combined": ftb_combined,
        "all_combined": all_combined,
        "single_all": all_single,
        "joint_all": all_joint,
        "hm_subtracted": hm_subtracted,
    }



def run_lti_search(
    *,
    p3_csv: Path,
    p6_csv: Path,
    config_path: Path,
    target_year: int,
) -> LtiSearchOutput:
    props = read_properties(config_path)
    if TARGET_FTB_KEY not in props or TARGET_HM_KEY not in props:
        raise ValueError(
            f"Missing target keys in config: {TARGET_FTB_KEY}, {TARGET_HM_KEY}"
        )

    target_ftb = float(props[TARGET_FTB_KEY])
    target_hm = float(props[TARGET_HM_KEY])

    distributions = _load_distributions(p3_csv, p6_csv, target_year)

    results: list[LtiMethodResult] = []
    for ftb_source in FTB_SOURCE_CHOICES:
        for hm_source in HM_SOURCE_CHOICES:
            ftb_bins = distributions[ftb_source]
            hm_bins = distributions[hm_source]
            for quantile in QUANTILE_CHOICES:
                for open_upper in OPEN_TOP_CHOICES:
                    for interpolation in INTERPOLATION_CHOICES:
                        method = LtiMethodSpec(
                            ftb_source=ftb_source,
                            hm_source=hm_source,
                            quantile=quantile,
                            open_top_upper=open_upper,
                            interpolation=interpolation,
                        )
                        ftb_raw = binned_weighted_quantile(
                            ftb_bins,
                            quantile,
                            open_upper,
                            interpolation=interpolation,
                        )
                        hm_raw = binned_weighted_quantile(
                            hm_bins,
                            quantile,
                            open_upper,
                            interpolation=interpolation,
                        )
                        ftb_rounded = round(ftb_raw, 1)
                        hm_rounded = round(hm_raw, 1)

                        results.append(
                            LtiMethodResult(
                                method=method,
                                ftb_estimate_raw=ftb_raw,
                                hm_estimate_raw=hm_raw,
                                ftb_estimate_rounded=ftb_rounded,
                                hm_estimate_rounded=hm_rounded,
                                distance_rounded=euclidean_distance(
                                    (ftb_rounded, hm_rounded),
                                    (target_ftb, target_hm),
                                ),
                                distance_raw=euclidean_distance(
                                    (ftb_raw, hm_raw),
                                    (target_ftb, target_hm),
                                ),
                            )
                        )

    results.sort(
        key=lambda item: (
            item.distance_rounded,
            item.distance_raw,
            item.method.method_id,
        )
    )

    return LtiSearchOutput(results=results, target_ftb=target_ftb, target_hm=target_hm)



def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search PSD 2011 LTI hard-max methods by closeness to config targets."
    )
    parser.add_argument(
        "--p3-csv",
        default="private-datasets/psd/2005-2013/psd-mortgages-2005-2013-p3-loan-characteristic.csv",
        help="PSD p3 loan-characteristics CSV.",
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
        "--output-dir",
        default=None,
        help="Optional output directory for CSV export.",
    )
    return parser



def _write_csv(results: list[LtiMethodResult], output_dir: str) -> Path:
    output_root = ensure_output_dir(output_dir)
    output_path = output_root / "PsdLtiHardMaxMethodSearch.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank",
                "method_id",
                "ftb_raw",
                "hm_raw",
                "ftb_rounded",
                "hm_rounded",
                "distance_rounded",
                "distance_raw",
            ]
        )
        for rank, item in enumerate(results, start=1):
            writer.writerow(
                [
                    rank,
                    item.method.method_id,
                    item.ftb_estimate_raw,
                    item.hm_estimate_raw,
                    item.ftb_estimate_rounded,
                    item.hm_estimate_rounded,
                    item.distance_rounded,
                    item.distance_raw,
                ]
            )
    return output_path



def main() -> None:
    args = build_arg_parser().parse_args()

    output = run_lti_search(
        p3_csv=Path(args.p3_csv),
        p6_csv=Path(args.p6_csv),
        config_path=Path(args.config_path),
        target_year=args.target_year,
    )

    top_k = max(1, args.top_k)

    print("PSD LTI hard-max method search")
    print(f"P3: {args.p3_csv}")
    print(f"P6: {args.p6_csv}")
    print(f"Config: {args.config_path}")
    print(f"Target year: {args.target_year}")
    print(f"Target {TARGET_FTB_KEY} = {format_float(output.target_ftb)}")
    print(f"Target {TARGET_HM_KEY} = {format_float(output.target_hm)}")
    print("")
    print(
        "Rank\tDistanceRounded\tDistanceRaw\tFTB(raw)\tHM(raw)\t"
        "FTB(round1dp)\tHM(round1dp)\tMethod"
    )
    for rank, item in enumerate(output.results[:top_k], start=1):
        print(
            f"{rank}\t{format_float(item.distance_rounded)}\t{format_float(item.distance_raw)}\t"
            f"{format_float(item.ftb_estimate_raw)}\t{format_float(item.hm_estimate_raw)}\t"
            f"{format_float(item.ftb_estimate_rounded, decimals=1)}\t"
            f"{format_float(item.hm_estimate_rounded, decimals=1)}\t"
            f"{item.method.method_id}"
        )

    default_match = next(
        result for result in output.results if result.method == DEFAULT_LTI_METHOD
    )
    print("\nDefault method (decision record)")
    print(f"method: {default_match.method.method_id}")
    print(f"{TARGET_FTB_KEY} ~= {format_float(default_match.ftb_estimate_raw)}")
    print(f"{TARGET_HM_KEY} ~= {format_float(default_match.hm_estimate_raw)}")
    print(
        f"rounded: {format_float(default_match.ftb_estimate_rounded, decimals=1)}, "
        f"{format_float(default_match.hm_estimate_rounded, decimals=1)}"
    )

    if args.output_dir:
        output_path = _write_csv(output.results, args.output_dir)
        print(f"\nWrote: {output_path}")


if __name__ == "__main__":
    main()
