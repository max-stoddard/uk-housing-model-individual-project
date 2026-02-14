#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enumerate config keys whose calibration comments reference PSD.

Latest experiment findings (run on February 13, 2026):
  - Config: src/main/resources/config.properties
  - PSD-tagged keys detected: 16
  - Classification breakdown:
    - pure_direct: 6
    - pure_blocked: 2
    - hybrid: 8
  - Interpretation:
    - The agreed pure-direct scope is a strict subset of all PSD-linked keys.

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from scripts.python.helpers.common.paths import ensure_output_dir
from scripts.python.helpers.psd.config_targets import PsdInventoryRow, read_psd_inventory


FIELDS = ["key", "value", "comment", "classification", "status"]



def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enumerate PSD-linked parameters from config.properties.")
    parser.add_argument(
        "--config-path",
        default="src/main/resources/config.properties",
        help="Path to config.properties (default: src/main/resources/config.properties).",
    )
    parser.add_argument(
        "--emit-format",
        choices=["table", "csv"],
        default="table",
        help="Terminal output format (default: table).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for CSV export.",
    )
    return parser



def _to_row(item: PsdInventoryRow) -> dict[str, str]:
    return {
        "key": item.key,
        "value": item.value,
        "comment": item.comment,
        "classification": item.classification,
        "status": item.status,
    }



def _print_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("No PSD-linked keys found.")
        return

    widths: dict[str, int] = {}
    for field in FIELDS:
        widths[field] = max(len(field), max(len(row[field]) for row in rows))

    header = " | ".join(field.ljust(widths[field]) for field in FIELDS)
    divider = "-+-".join("-" * widths[field] for field in FIELDS)
    print(header)
    print(divider)
    for row in rows:
        print(" | ".join(row[field].ljust(widths[field]) for field in FIELDS))



def _print_csv(rows: list[dict[str, str]]) -> None:
    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)



def _write_csv(rows: list[dict[str, str]], output_dir: str) -> Path:
    output_root = ensure_output_dir(output_dir)
    output_path = output_root / "PsdParameterInventory.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return output_path



def main() -> None:
    args = build_arg_parser().parse_args()
    inventory = read_psd_inventory(Path(args.config_path))
    rows = [_to_row(item) for item in inventory]

    print("PSD parameter inventory")
    print(f"Config: {args.config_path}")
    print(f"Count: {len(rows)}")
    counts = Counter(item.classification for item in inventory)
    print(
        "Classifications: "
        + ", ".join(
            f"{name}={counts.get(name, 0)}"
            for name in ("pure_direct", "pure_blocked", "hybrid")
        )
    )
    print("")

    if args.emit_format == "table":
        _print_table(rows)
    else:
        _print_csv(rows)

    if args.output_dir:
        output_path = _write_csv(rows, args.output_dir)
        print(f"\nWrote: {output_path}")


if __name__ == "__main__":
    main()
