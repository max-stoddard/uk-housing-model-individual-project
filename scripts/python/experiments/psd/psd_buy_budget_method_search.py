#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Search PSD/PPD method variants to reproduce BUY* parameters from 2011 targets.

Latest experiment findings (run on February 14, 2026):
  - Command:
    - python3 -m scripts.python.experiments.psd.psd_buy_budget_method_search
      --families psd_log_ols_residual,psd_log_ols_robust_mu
      --loan-to-income-couplings comonotonic
      --income-to-price-couplings comonotonic
      --loan-open-upper-k 500,550,600,650,700,800,900,1000
      --lti-open-upper 7,8,9,10
      --lti-open-lower 2,2.25,2.5
      --income-open-upper-k 60,80,100
      --property-open-upper-k 8000,9000,10000,11000,12000
      --trim-fractions 0
      --mu-upper-trim-fracs 0.0055,0.006,0.0063,0.0065,0.007
      --quantile-grid-size 4000
  - Best-ranked method (normalized reproduction-first):
    - family=psd_log_ols_robust_mu
    - loan_to_income=comonotonic
    - income_to_price=comonotonic
    - loan_open_k=500
    - lti_open=10
    - lti_floor=2.5
    - income_open_k=100
    - property_open_k=10000
    - trim=0
    - mu_hi_trim=0.0063
    - within_bin_points=11
    - grid=4000
    - Estimates:
      - BUY_SCALE ~= 43.0648
      - BUY_EXPONENT ~= 0.8116
      - BUY_MU ~= -0.0179
      - BUY_SIGMA ~= 0.4084
      - Distance(norm) ~= 0.02926
  - Interpretation:
    - Robust upper-tail trimming for BUY_MU materially improves 2011 reproduction.

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from scripts.python.helpers.common.cli import format_float
from scripts.python.helpers.common.paths import ensure_output_dir
from scripts.python.helpers.psd.buy_budget_methods import (
    COUPLING_CHOICES,
    METHOD_FAMILY_PSD_LOG_OLS_RESIDUAL,
    METHOD_FAMILY_PSD_LOG_OLS_ROBUST_MU,
    METHOD_FAMILY_CHOICES,
    BuyMethodResult,
    BuyMethodSpec,
    BuySearchOutput,
    method_specs_from_grid,
    run_legacy_2011_method_search,
)


def _parse_csv_floats(raw: str) -> tuple[float, ...]:
    out: list[float] = []
    for token in raw.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        out.append(float(stripped))
    if not out:
        raise ValueError("Expected at least one numeric value.")
    return tuple(out)


def _parse_csv_strings(raw: str, allowed: tuple[str, ...] | None = None) -> tuple[str, ...]:
    out: list[str] = []
    for token in raw.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        if allowed is not None and stripped not in allowed:
            raise ValueError(f"Unsupported value '{stripped}'. Allowed: {', '.join(allowed)}")
        out.append(stripped)
    if not out:
        raise ValueError("Expected at least one value.")
    return tuple(dict.fromkeys(out))


def _format_duration(seconds: float) -> str:
    if seconds < 0:
        return "unknown"
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _relative_error_percent(estimate: float, target: float) -> float:
    denominator = max(abs(target), 1e-12)
    return 100.0 * abs(estimate - target) / denominator


def _method_error_percents(
    item: BuyMethodResult,
    target_scale: float,
    target_exponent: float,
    target_mu: float,
    target_sigma: float,
) -> tuple[float, float, float, float]:
    return (
        _relative_error_percent(item.buy_scale, target_scale),
        _relative_error_percent(item.buy_exponent, target_exponent),
        _relative_error_percent(item.buy_mu, target_mu),
        _relative_error_percent(item.buy_sigma, target_sigma),
    )


def count_within_one_percent(
    results: list[BuyMethodResult],
    target_scale: float,
    target_exponent: float,
    target_mu: float,
    target_sigma: float,
) -> int:
    count = 0
    for item in results:
        err_scale, err_exponent, err_mu, err_sigma = _method_error_percents(
            item,
            target_scale,
            target_exponent,
            target_mu,
            target_sigma,
        )
        if (
            err_scale <= 1.0
            and err_exponent <= 1.0
            and err_mu <= 1.0
            and err_sigma <= 1.0
        ):
            count += 1
    return count


def validate_shard_args(shard_count: int, shard_index: int) -> None:
    if shard_count <= 0:
        raise ValueError("shard-count must be positive.")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError(
            f"shard-index must be in [0, shard-count). Got shard-index={shard_index}, shard-count={shard_count}."
        )


def select_shard_methods(
    methods: list[BuyMethodSpec],
    shard_count: int,
    shard_index: int,
) -> list[BuyMethodSpec]:
    validate_shard_args(shard_count, shard_index)
    ordered = sorted(methods, key=lambda item: item.method_id)
    return [method for idx, method in enumerate(ordered) if idx % shard_count == shard_index]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search BUY* method variants by closeness to legacy 2011 targets.",
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
        "--ppd-csv",
        default="private-datasets/ppd/pp-2011.csv",
        help="PPD CSV used for 2011 log-price moments.",
    )
    parser.add_argument(
        "--config-path",
        default="input-data-versions/v0/config.properties",
        help="Config path containing BUY* target values.",
    )
    parser.add_argument(
        "--target-year-psd",
        type=int,
        default=2011,
        help="Target year token for PSD annual columns (default: 2011).",
    )
    parser.add_argument(
        "--target-year-ppd",
        type=int,
        default=2011,
        help="Target transfer year for PPD filtering (default: 2011).",
    )
    parser.add_argument(
        "--families",
        default=",".join(
            (
                METHOD_FAMILY_PSD_LOG_OLS_RESIDUAL,
                METHOD_FAMILY_PSD_LOG_OLS_ROBUST_MU,
            )
        ),
        help="Comma-separated method families.",
    )
    parser.add_argument(
        "--loan-to-income-couplings",
        default="comonotonic,independent",
        help="Comma-separated coupling choices for loan->income synthesis.",
    )
    parser.add_argument(
        "--income-to-price-couplings",
        default="comonotonic,independent",
        help="Comma-separated coupling choices for income->price pairing.",
    )
    parser.add_argument(
        "--loan-open-upper-k",
        default="2000,3000",
        help="Comma-separated loan open-top assumptions in thousand GBP.",
    )
    parser.add_argument(
        "--lti-open-upper",
        default="6,8",
        help="Comma-separated LTI open-top assumptions.",
    )
    parser.add_argument(
        "--lti-open-lower",
        default="1.5,2.0",
        help="Comma-separated lower assumptions for open-lower LTI bins.",
    )
    parser.add_argument(
        "--income-open-upper-k",
        default="200",
        help="Comma-separated gross-income open-top assumptions in thousand GBP.",
    )
    parser.add_argument(
        "--property-open-upper-k",
        default="1200,2000,3000",
        help="Comma-separated property open-top assumptions in thousand GBP.",
    )
    parser.add_argument(
        "--trim-fractions",
        default="0,0.001",
        help="Comma-separated symmetric trim fractions in [0, 0.5).",
    )
    parser.add_argument(
        "--mu-upper-trim-fracs",
        default="0.0063",
        help="Comma-separated upper-tail trim fractions for robust BUY_MU estimation.",
    )
    parser.add_argument(
        "--within-bin-points",
        type=int,
        default=11,
        help="Within-bin midpoint integration points (default: 11).",
    )
    parser.add_argument(
        "--quantile-grid-size",
        type=int,
        default=2000,
        help="Quantile-grid size for deterministic synthetic pairing (default: 2000).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Number of top-ranked methods to print (default: 20).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=500,
        help="Print progress update every N processed methods (default: 500).",
    )
    parser.add_argument(
        "--progress-every-seconds",
        type=float,
        default=2.0,
        help="Print progress update at least every N seconds (default: 2.0).",
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=1,
        help="Total number of deterministic shards (default: 1).",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="Shard index to run in [0, shard-count) (default: 0).",
    )
    parser.add_argument(
        "--summary-json",
        default=None,
        help="Optional path to write run summary JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for CSV export.",
    )
    return parser


def _write_csv(output: BuySearchOutput, output_dir: str) -> Path:
    output_root = ensure_output_dir(output_dir)
    output_path = output_root / "PsdBuyBudgetMethodSearch.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank",
                "method_id",
                "family",
                "loan_to_income_coupling",
                "income_to_price_coupling",
                "loan_open_upper_k",
                "lti_open_upper",
                "lti_open_lower",
                "income_open_upper_k",
                "property_open_upper_k",
                "trim_fraction",
                "within_bin_points",
                "quantile_grid_size",
                "mu_upper_trim_fraction",
                "buy_scale",
                "buy_exponent",
                "buy_mu",
                "buy_sigma",
                "distance_norm",
                "abs_d_scale_norm",
                "abs_d_exponent_norm",
                "abs_d_mu_norm",
                "abs_d_sigma_norm",
                "err_pct_scale",
                "err_pct_exponent",
                "err_pct_mu",
                "err_pct_sigma",
                "within_1pct_all_keys",
                "paired_sample_size",
                "trimmed_each_side",
                "sigma2_clamped_to_zero",
                "mu_upper_trimmed_count",
            ]
        )
        for rank, item in enumerate(output.results, start=1):
            err_scale, err_exponent, err_mu, err_sigma = _method_error_percents(
                item,
                output.target_buy_scale,
                output.target_buy_exponent,
                output.target_buy_mu,
                output.target_buy_sigma,
            )
            within_1 = (
                err_scale <= 1.0
                and err_exponent <= 1.0
                and err_mu <= 1.0
                and err_sigma <= 1.0
            )
            writer.writerow(
                [
                    rank,
                    item.method.method_id,
                    item.method.family,
                    item.method.loan_to_income_coupling,
                    item.method.income_to_price_coupling,
                    item.method.loan_open_upper_k,
                    item.method.lti_open_upper,
                    item.method.lti_open_lower,
                    item.method.income_open_upper_k,
                    item.method.property_open_upper_k,
                    item.method.trim_fraction,
                    item.method.within_bin_points,
                    item.method.quantile_grid_size,
                    item.method.mu_upper_trim_fraction,
                    item.buy_scale,
                    item.buy_exponent,
                    item.buy_mu,
                    item.buy_sigma,
                    item.distance_norm,
                    item.abs_d_scale_norm,
                    item.abs_d_exponent_norm,
                    item.abs_d_mu_norm,
                    item.abs_d_sigma_norm,
                    err_scale,
                    err_exponent,
                    err_mu,
                    err_sigma,
                    str(within_1),
                    item.diagnostics.paired_sample_size,
                    item.diagnostics.trimmed_each_side,
                    str(item.diagnostics.sigma2_clamped_to_zero),
                    item.diagnostics.mu_upper_trimmed_count,
                ]
            )
    return output_path


def _write_summary_json(
    *,
    summary_path: str,
    output: BuySearchOutput,
    methods_generated: int,
    methods_in_shard: int,
    processed: int,
    elapsed_seconds: float,
    within_1_count: int,
) -> Path:
    best = output.results[0]
    err_scale, err_exponent, err_mu, err_sigma = _method_error_percents(
        best,
        output.target_buy_scale,
        output.target_buy_exponent,
        output.target_buy_mu,
        output.target_buy_sigma,
    )
    rate = processed / elapsed_seconds if elapsed_seconds > 0.0 else 0.0
    summary = {
        "methods_generated": methods_generated,
        "methods_in_shard": methods_in_shard,
        "processed": processed,
        "skipped": output.skipped_methods,
        "elapsed_seconds": elapsed_seconds,
        "throughput_methods_per_sec": rate,
        "within_1pct_all_keys_count": within_1_count,
        "targets": {
            "BUY_SCALE": output.target_buy_scale,
            "BUY_EXPONENT": output.target_buy_exponent,
            "BUY_MU": output.target_buy_mu,
            "BUY_SIGMA": output.target_buy_sigma,
        },
        "best": {
            "method_id": best.method.method_id,
            "buy_scale": best.buy_scale,
            "buy_exponent": best.buy_exponent,
            "buy_mu": best.buy_mu,
            "buy_sigma": best.buy_sigma,
            "distance_norm": best.distance_norm,
            "err_pct_scale": err_scale,
            "err_pct_exponent": err_exponent,
            "err_pct_mu": err_mu,
            "err_pct_sigma": err_sigma,
        },
    }
    path = Path(summary_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
    return path


def main() -> None:
    args = build_arg_parser().parse_args()

    p3_path = Path(args.p3_csv)
    p5_path = Path(args.p5_csv)
    ppd_path = Path(args.ppd_csv)
    config_path = Path(args.config_path)

    missing = [
        str(path)
        for path in (p3_path, p5_path, ppd_path, config_path)
        if not path.exists()
    ]
    if missing:
        raise SystemExit("Missing input file(s): " + ", ".join(missing))
    if args.within_bin_points <= 0:
        raise SystemExit("within-bin-points must be positive.")
    if args.quantile_grid_size <= 0:
        raise SystemExit("quantile-grid-size must be positive.")
    if args.top_k <= 0:
        raise SystemExit("top-k must be positive.")
    if args.progress_every <= 0:
        raise SystemExit("progress-every must be positive.")
    if args.progress_every_seconds <= 0.0:
        raise SystemExit("progress-every-seconds must be positive.")
    try:
        validate_shard_args(args.shard_count, args.shard_index)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    families = _parse_csv_strings(args.families, allowed=METHOD_FAMILY_CHOICES)
    loan_to_income_couplings = _parse_csv_strings(
        args.loan_to_income_couplings,
        allowed=COUPLING_CHOICES,
    )
    income_to_price_couplings = _parse_csv_strings(
        args.income_to_price_couplings,
        allowed=COUPLING_CHOICES,
    )

    methods = method_specs_from_grid(
        families=families,
        loan_to_income_couplings=loan_to_income_couplings,
        income_to_price_couplings=income_to_price_couplings,
        loan_open_upper_k_values=_parse_csv_floats(args.loan_open_upper_k),
        lti_open_upper_values=_parse_csv_floats(args.lti_open_upper),
        lti_open_lower_values=_parse_csv_floats(args.lti_open_lower),
        income_open_upper_k_values=_parse_csv_floats(args.income_open_upper_k),
        property_open_upper_k_values=_parse_csv_floats(args.property_open_upper_k),
        trim_fractions=_parse_csv_floats(args.trim_fractions),
        mu_upper_trim_fractions=_parse_csv_floats(args.mu_upper_trim_fracs),
        within_bin_points=args.within_bin_points,
        quantile_grid_size=args.quantile_grid_size,
    )
    methods_generated = len(methods)
    methods = select_shard_methods(methods, args.shard_count, args.shard_index)
    if not methods:
        raise SystemExit(
            f"No methods assigned to shard {args.shard_index}/{args.shard_count}."
        )

    start = time.monotonic()
    last_emit = start

    def progress_callback(processed: int, total: int, skipped: int) -> None:
        nonlocal last_emit
        now = time.monotonic()
        should_emit = (
            processed == total
            or processed % args.progress_every == 0
            or (now - last_emit) >= args.progress_every_seconds
        )
        if not should_emit:
            return
        elapsed = now - start
        rate = processed / elapsed if elapsed > 0.0 else 0.0
        remaining = max(total - processed, 0)
        eta = remaining / rate if rate > 0.0 else -1.0
        percent = (100.0 * processed / total) if total > 0 else 100.0
        print(
            "[progress] "
            f"{processed}/{total} ({percent:.2f}%) "
            f"skipped={skipped} "
            f"elapsed={_format_duration(elapsed)} "
            f"rate={rate:.2f}/s "
            f"eta={_format_duration(eta)}"
        )
        last_emit = now

    output = run_legacy_2011_method_search(
        p3_csv=p3_path,
        p5_csv=p5_path,
        ppd_csv=ppd_path,
        config_path=config_path,
        target_year_psd=args.target_year_psd,
        target_year_ppd=args.target_year_ppd,
        methods=methods,
        progress_callback=progress_callback,
    )
    elapsed = time.monotonic() - start
    processed = len(methods)
    best = output.results[0]
    within_1_count = count_within_one_percent(
        output.results,
        output.target_buy_scale,
        output.target_buy_exponent,
        output.target_buy_mu,
        output.target_buy_sigma,
    )
    best_err_scale, best_err_exponent, best_err_mu, best_err_sigma = _method_error_percents(
        best,
        output.target_buy_scale,
        output.target_buy_exponent,
        output.target_buy_mu,
        output.target_buy_sigma,
    )
    rate = processed / elapsed if elapsed > 0.0 else 0.0

    print("PSD BUY* method search (2011 reproduction)")
    print(f"PSD p3: {args.p3_csv}")
    print(f"PSD p5: {args.p5_csv}")
    print(f"PPD: {args.ppd_csv}")
    print(f"Config: {args.config_path}")
    print(f"Target year PSD: {args.target_year_psd}")
    print(f"Target year PPD: {args.target_year_ppd}")
    print(f"Methods generated: {methods_generated}")
    print(f"Methods in shard: {len(methods)}")
    print(f"Shard index/count: {args.shard_index}/{args.shard_count}")
    print(f"Methods evaluated: {processed}")
    print(f"Methods skipped: {output.skipped_methods}")
    print(f"Elapsed: {_format_duration(elapsed)}")
    print(f"Throughput: {rate:.2f} methods/s")
    print(f"Within 1% (all 4 BUY* keys): {within_1_count}")
    print("")
    print("Targets")
    print(f"BUY_SCALE = {format_float(output.target_buy_scale)}")
    print(f"BUY_EXPONENT = {format_float(output.target_buy_exponent)}")
    print(f"BUY_MU = {format_float(output.target_buy_mu)}")
    print(f"BUY_SIGMA = {format_float(output.target_buy_sigma)}")
    print("")
    print("Initial seed (deterministic 2011 baseline)")
    print(f"Method: {output.initial_seed.method_id}")
    print(f"Seed BUY_SCALE ~= {format_float(output.initial_seed.buy_scale)}")
    print(f"Seed BUY_EXPONENT ~= {format_float(output.initial_seed.buy_exponent)}")
    print(f"Seed BUY_MU ~= {format_float(output.initial_seed.buy_mu)}")
    print(f"Seed BUY_SIGMA ~= {format_float(output.initial_seed.buy_sigma)}")
    print("")
    print("PPD diagnostics")
    print(f"Rows total: {output.ppd_stats.rows_total}")
    print(f"Rows used: {output.ppd_stats.rows_used}")
    print(f"Mean log(price): {format_float(output.ppd_stats.mean_log_price)}")
    print(f"Var log(price): {format_float(output.ppd_stats.variance_log_price)}")
    print("")
    print("Legacy PSD diagnostics")
    for key in sorted(output.legacy_diagnostics.keys()):
        print(f"{key}: {format_float(output.legacy_diagnostics[key])}")
    print("")
    print(
        "Rank\tDistanceNorm\t|dScale|\t|dExponent|\t|dMu|\t|dSigma|\t"
        "Scale\tExponent\tMu\tSigma\tMethod"
    )
    for rank, item in enumerate(output.results[: args.top_k], start=1):
        print(
            f"{rank}\t{format_float(item.distance_norm)}\t"
            f"{format_float(item.abs_d_scale_norm)}\t"
            f"{format_float(item.abs_d_exponent_norm)}\t"
            f"{format_float(item.abs_d_mu_norm)}\t"
            f"{format_float(item.abs_d_sigma_norm)}\t"
            f"{format_float(item.buy_scale)}\t"
            f"{format_float(item.buy_exponent)}\t"
            f"{format_float(item.buy_mu)}\t"
            f"{format_float(item.buy_sigma)}\t"
            f"{item.method.method_id}"
        )

    print("\nBest method summary")
    print(f"Method: {best.method.method_id}")
    print(f"BUY_SCALE ~= {format_float(best.buy_scale)}")
    print(f"BUY_EXPONENT ~= {format_float(best.buy_exponent)}")
    print(f"BUY_MU ~= {format_float(best.buy_mu)}")
    print(f"BUY_SIGMA ~= {format_float(best.buy_sigma)}")
    print(f"Distance(norm) ~= {format_float(best.distance_norm)}")
    print(
        "Errors (%): "
        f"scale={format_float(best_err_scale)}, "
        f"exponent={format_float(best_err_exponent)}, "
        f"mu={format_float(best_err_mu)}, "
        f"sigma={format_float(best_err_sigma)}"
    )

    if args.output_dir is not None:
        output_path = _write_csv(output, args.output_dir)
        print(f"\nCSV output: {output_path}")
    if args.summary_json is not None:
        summary_path = _write_summary_json(
            summary_path=args.summary_json,
            output=output,
            methods_generated=methods_generated,
            methods_in_shard=len(methods),
            processed=processed,
            elapsed_seconds=elapsed,
            within_1_count=within_1_count,
        )
        print(f"Summary JSON: {summary_path}")


if __name__ == "__main__":
    main()
