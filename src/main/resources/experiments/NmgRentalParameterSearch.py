#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare NMG rental log-normal parameter variants against target config values.

Reads:
  - NMG CSV data (headered)
  - target values from a config.properties file

Computes:
  - mu = mean(log(rent))
  - sigma = std(log(rent))

Variants:
  - qhousing filters: {4}, {3,4}, {3,4,5}
  - weighted vs unweighted
  - std definition: population vs sample

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class ColumnNames:
    qhousing: str = "qhousing"
    rent: str = "SPQ07free_1"
    weight: str = "we_factor"


@dataclass(frozen=True)
class TargetKeys:
    scale: str = "RENTAL_PRICES_SCALE"
    shape: str = "RENTAL_PRICES_SHAPE"


@dataclass(frozen=True)
class Variant:
    name: str
    qhousing_set: frozenset[int]


@dataclass
class Record:
    qhousing: int | None
    log_rent: float | None
    weight: float | None


@dataclass
class ResultRow:
    variant: str
    n: int
    sum_w: float | None
    mu: float
    sigma: float
    distance: float


def parse_int(raw: str) -> int | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def parse_float(raw: str) -> float | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def read_properties(path: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("!"):
                continue
            if "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            props[key.strip()] = value.strip()
    return props


def resolve_indices(header: Sequence[str], columns: ColumnNames) -> dict[str, int]:
    lookup = {name: idx for idx, name in enumerate(header)}
    missing = [
        name
        for name in (columns.qhousing, columns.rent, columns.weight)
        if name not in lookup
    ]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Missing required columns: {missing_text}")
    return {
        "qhousing": lookup[columns.qhousing],
        "rent": lookup[columns.rent],
        "weight": lookup[columns.weight],
    }


def load_records(path: Path, delimiter: str, columns: ColumnNames) -> list[Record]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        header = next(reader)
        indices = resolve_indices(header, columns)

        records: list[Record] = []
        for row in reader:
            qhousing = None
            rent_log = None
            weight = None

            if len(row) > indices["qhousing"]:
                qhousing = parse_int(row[indices["qhousing"]])

            if len(row) > indices["rent"]:
                rent = parse_float(row[indices["rent"]])
                if rent is not None and rent > 0:
                    rent_log = math.log(rent)

            if len(row) > indices["weight"]:
                weight = parse_float(row[indices["weight"]])

            records.append(Record(qhousing=qhousing, log_rent=rent_log, weight=weight))

    return records


def compute_unweighted(records: Iterable[Record]) -> tuple[float, float, float, int]:
    values = [record.log_rent for record in records if record.log_rent is not None]
    if not values:
        raise ValueError("No valid rent values for unweighted computation.")
    n = len(values)
    mean = sum(values) / n
    var_pop = sum((v - mean) ** 2 for v in values) / n
    var_samp = sum((v - mean) ** 2 for v in values) / (n - 1) if n > 1 else 0.0
    return mean, math.sqrt(var_pop), math.sqrt(var_samp), n


def compute_weighted(
    records: Iterable[Record],
) -> tuple[float, float, float, int, float]:
    values = []
    weights = []
    for record in records:
        if record.log_rent is None:
            continue
        if record.weight is None or record.weight <= 0:
            continue
        values.append(record.log_rent)
        weights.append(record.weight)

    if not values:
        raise ValueError("No valid rent values for weighted computation.")

    sum_w = sum(weights)
    mean = sum(v * w for v, w in zip(values, weights)) / sum_w
    var_pop = sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / sum_w
    std_pop = math.sqrt(var_pop)
    std_sample = math.sqrt(var_pop * (sum_w / (sum_w - 1))) if sum_w > 1 else std_pop
    return mean, std_pop, std_sample, len(values), sum_w


def distance(mu: float, sigma: float, target_mu: float, target_sigma: float) -> float:
    return math.sqrt((mu - target_mu) ** 2 + (sigma - target_sigma) ** 2)


def format_float(value: float) -> str:
    return f"{value:.10f}"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search NMG rental parameter variants closest to config targets.",
    )
    parser.add_argument(
        "nmg_path",
        help="Relative path to NMG CSV file (e.g. private-datasets/nmg/nmg-2016.csv).",
    )
    parser.add_argument(
        "--config-path",
        default="input-data-versions/v0/config.properties",
        help="Path to config.properties with target values (default: input-data-versions/v0/config.properties).",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="CSV delimiter (default: ',').",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    nmg_path = Path(args.nmg_path)
    if not nmg_path.exists():
        parser.error(f"Missing NMG CSV: {nmg_path}")

    config_path = Path(args.config_path)
    if not config_path.exists():
        parser.error(f"Missing config.properties: {config_path}")

    columns = ColumnNames()
    target_keys = TargetKeys()

    props = read_properties(config_path)
    if target_keys.scale not in props or target_keys.shape not in props:
        raise SystemExit(
            "Target values not found in config.properties "
            f"(expected {target_keys.scale} and {target_keys.shape})."
        )

    target_mu = float(props[target_keys.scale])
    target_sigma = float(props[target_keys.shape])

    records = load_records(nmg_path, args.delimiter, columns)

    variants = [
        Variant("q4", frozenset({4})),
        Variant("q3q4", frozenset({3, 4})),
        Variant("q3q4q5", frozenset({3, 4, 5})),
    ]

    rows: list[ResultRow] = []

    for variant in variants:
        subset = [
            record for record in records if record.qhousing in variant.qhousing_set
        ]

        mu, std_pop, std_samp, n = compute_unweighted(subset)
        rows.append(
            ResultRow(
                variant=f"{variant.name}|unweighted|std=pop",
                n=n,
                sum_w=None,
                mu=mu,
                sigma=std_pop,
                distance=distance(mu, std_pop, target_mu, target_sigma),
            )
        )
        rows.append(
            ResultRow(
                variant=f"{variant.name}|unweighted|std=sample",
                n=n,
                sum_w=None,
                mu=mu,
                sigma=std_samp,
                distance=distance(mu, std_samp, target_mu, target_sigma),
            )
        )

        mu, std_pop, std_samp, n, sum_w = compute_weighted(subset)
        rows.append(
            ResultRow(
                variant=f"{variant.name}|weighted|std=pop",
                n=n,
                sum_w=sum_w,
                mu=mu,
                sigma=std_pop,
                distance=distance(mu, std_pop, target_mu, target_sigma),
            )
        )
        rows.append(
            ResultRow(
                variant=f"{variant.name}|weighted|std=sample",
                n=n,
                sum_w=sum_w,
                mu=mu,
                sigma=std_samp,
                distance=distance(mu, std_samp, target_mu, target_sigma),
            )
        )

    rows.sort(key=lambda r: r.distance)

    print(f"Targets from {config_path}:")
    print(f"{target_keys.scale} = {format_float(target_mu)}")
    print(f"{target_keys.shape} = {format_float(target_sigma)}")
    print("")
    print("Variant\tN\tSumW\tMu\tSigma\tDistance\t|dMu|\t|dSigma|")
    for row in rows:
        dmu = abs(row.mu - target_mu)
        dsigma = abs(row.sigma - target_sigma)
        sum_w_str = f"{row.sum_w:.6f}" if row.sum_w is not None else "-"
        print(
            f"{row.variant}\t{row.n}\t{sum_w_str}\t"
            f"{format_float(row.mu)}\t{format_float(row.sigma)}\t"
            f"{format_float(row.distance)}\t{format_float(dmu)}\t{format_float(dsigma)}"
        )

    best = rows[0]
    print("\nClosest variant:")
    print(
        f"{best.variant} | Mu={format_float(best.mu)} | Sigma={format_float(best.sigma)} | "
        f"Distance={format_float(best.distance)}"
    )


if __name__ == "__main__":
    main()
