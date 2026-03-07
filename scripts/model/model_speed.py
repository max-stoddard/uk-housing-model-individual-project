#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Snapshot-local helpers for model-speed benchmarking, regression, and profiling.

@author: Max Stoddard
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import statistics
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOURCE_PATH_PATTERN = re.compile(r'"src/main/resources/([^"]+)"')
NUMERIC_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
PAUSE_PATTERN = re.compile(r"Pause.*? ([0-9]+(?:\.[0-9]+)?)(us|ms|s)\b")

MODELSTEP_PHASE_LINES: tuple[tuple[int, str], ...] = (
    (185, "demographics.step()"),
    (187, "construction.step()"),
    (189, "household loop"),
    (191, "creditSupply.preClearingResetCounters()"),
    (193, "housingMarketStats.preClearingRecord()"),
    (195, "houseSaleMarket.clearMarket()"),
    (197, "housingMarketStats.postClearingRecord()"),
    (199, "rentalMarketStats.preClearingRecord()"),
    (201, "houseRentalMarket.clearMarket()"),
    (203, "rentalMarketStats.postClearingRecord()"),
    (205, "householdStats.record()"),
    (207, "creditSupply.postClearingRecord()"),
    (209, "bank.step()"),
    (211, "centralBank.step()"),
)
MODELSTEP_PHASE_MAP = dict(MODELSTEP_PHASE_LINES)
MODELSTEP_METHOD_NAME = "housing.Model.modelStep"
FLAMEGRAPH_WIDTH = 3200
FLAMEGRAPH_FRAME_HEIGHT = 18
FLAMEGRAPH_TOP_PADDING = 52
FLAMEGRAPH_SIDE_PADDING = 10
FLAMEGRAPH_FONT_SIZE = 12
METHOD_TABLE_LIMIT = 20


@dataclass(frozen=True)
class ExecutionSample:
    """ExecutionSample data extracted from JFR."""

    whole_stack: tuple[str, ...]
    leaf_method: str
    modelstep_stack: tuple[str, ...] | None
    modelstep_phase_line: int | None


@dataclass(frozen=True)
class MethodRow:
    """One ranked method entry."""

    method: str
    samples: int
    percent: float
    rank: int


@dataclass(frozen=True)
class PhaseRow:
    """One direct-child modelStep phase entry."""

    line_number: int
    phase: str
    samples: int
    percent: float


@dataclass(frozen=True)
class JfrAnalysis:
    """Aggregated JFR execution-sample analysis."""

    label: str
    jfr_path: str
    total_samples: int
    modelstep_samples: int
    whole_run_methods: tuple[MethodRow, ...]
    modelstep_methods: tuple[MethodRow, ...]
    modelstep_phases: tuple[PhaseRow, ...]
    modelstep_stacks: tuple[tuple[str, ...], ...]


def parse_properties(path: Path) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        overrides[key.strip()] = value.strip().strip('"').strip("'")
    return overrides


def format_method_name(method: dict[str, object]) -> str:
    type_name = str(method["type"]["name"]).replace("/", ".")
    return f"{type_name}.{method['name']}"


def load_execution_samples(jfr_path: Path) -> list[ExecutionSample]:
    raw = subprocess.check_output(
        ["jfr", "print", "--events", "jdk.ExecutionSample", "--json", "--stack-depth", "96", str(jfr_path)],
        text=True,
    )
    data = json.loads(raw)
    samples: list[ExecutionSample] = []
    for event in data["recording"]["events"]:
        frames = event["values"]["stackTrace"]["frames"]
        whole_stack = tuple(format_method_name(frame["method"]) for frame in reversed(frames))
        leaf_method = format_method_name(frames[0]["method"])
        modelstep_stack: tuple[str, ...] | None = None
        modelstep_phase_line: int | None = None
        for index, frame in enumerate(frames):
            if format_method_name(frame["method"]) == MODELSTEP_METHOD_NAME:
                modelstep_phase_line = int(frame["lineNumber"])
                modelstep_stack = tuple(
                    format_method_name(truncated["method"]) for truncated in reversed(frames[: index + 1])
                )
                break
        samples.append(
            ExecutionSample(
                whole_stack=whole_stack,
                leaf_method=leaf_method,
                modelstep_stack=modelstep_stack,
                modelstep_phase_line=modelstep_phase_line,
            )
        )
    return samples


def ranked_method_rows(counter: Counter[str], total_samples: int) -> tuple[MethodRow, ...]:
    rows: list[MethodRow] = []
    for rank, (method, samples) in enumerate(
        sorted(counter.items(), key=lambda item: (-item[1], item[0])),
        start=1,
    ):
        percent = 0.0 if total_samples == 0 else (samples / total_samples) * 100.0
        rows.append(MethodRow(method=method, samples=samples, percent=percent, rank=rank))
    return tuple(rows)


def phase_rows(counter: Counter[int], total_samples: int) -> tuple[PhaseRow, ...]:
    rows: list[PhaseRow] = []
    for line_number, phase in MODELSTEP_PHASE_LINES:
        samples = counter.get(line_number, 0)
        percent = 0.0 if total_samples == 0 else (samples / total_samples) * 100.0
        rows.append(PhaseRow(line_number=line_number, phase=phase, samples=samples, percent=percent))
    for line_number in sorted(set(counter) - set(MODELSTEP_PHASE_MAP)):
        samples = counter[line_number]
        percent = 0.0 if total_samples == 0 else (samples / total_samples) * 100.0
        rows.append(PhaseRow(line_number=line_number, phase=f"line {line_number}", samples=samples, percent=percent))
    return tuple(rows)


def analyze_execution_samples(
    *,
    label: str,
    jfr_path: Path,
    expected_total_samples: int | None = None,
    expected_modelstep_samples: int | None = None,
) -> JfrAnalysis:
    samples = load_execution_samples(jfr_path)
    total_samples = len(samples)
    if expected_total_samples is not None and total_samples != expected_total_samples:
        raise SystemExit(
            f"{label}: expected {expected_total_samples} ExecutionSample events, got {total_samples} from {jfr_path}"
        )

    whole_run_counter: Counter[str] = Counter()
    modelstep_counter: Counter[str] = Counter()
    phase_counter: Counter[int] = Counter()
    modelstep_stacks: list[tuple[str, ...]] = []
    modelstep_samples = 0

    for sample in samples:
        whole_run_counter[sample.leaf_method] += 1
        if sample.modelstep_stack is not None and sample.modelstep_phase_line is not None:
            modelstep_samples += 1
            modelstep_counter[sample.leaf_method] += 1
            phase_counter[sample.modelstep_phase_line] += 1
            modelstep_stacks.append(sample.modelstep_stack)

    if expected_modelstep_samples is not None and modelstep_samples != expected_modelstep_samples:
        raise SystemExit(
            f"{label}: expected {expected_modelstep_samples} modelStep samples, got {modelstep_samples} from {jfr_path}"
        )

    return JfrAnalysis(
        label=label,
        jfr_path=str(jfr_path),
        total_samples=total_samples,
        modelstep_samples=modelstep_samples,
        whole_run_methods=ranked_method_rows(whole_run_counter, total_samples),
        modelstep_methods=ranked_method_rows(modelstep_counter, modelstep_samples),
        modelstep_phases=phase_rows(phase_counter, modelstep_samples),
        modelstep_stacks=tuple(modelstep_stacks),
    )


def short_profile_title(label: str) -> str:
    return label.replace("-", " ").title()


def rows_with_other(rows: tuple[MethodRow, ...], total_samples: int, limit: int = METHOD_TABLE_LIMIT) -> list[MethodRow]:
    if len(rows) <= limit:
        return list(rows)
    top_rows = list(rows[:limit])
    other_samples = sum(row.samples for row in rows[limit:])
    other_percent = 0.0 if total_samples == 0 else (other_samples / total_samples) * 100.0
    top_rows.append(MethodRow(method="Other", samples=other_samples, percent=other_percent, rank=limit + 1))
    return top_rows


def write_methods_csv(output_path: Path, label: str, whole_rows: tuple[MethodRow, ...], modelstep_rows: tuple[MethodRow, ...]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["profile_id", "view", "rank", "method", "samples", "percent"])
        for view, rows in (("whole-run", whole_rows), ("modelStep-only", modelstep_rows)):
            for row in rows:
                writer.writerow([label, view, row.rank, row.method, row.samples, f"{row.percent:.6f}"])


def analysis_to_json_payload(analysis: JfrAnalysis) -> dict[str, object]:
    return {
        "profile_id": analysis.label,
        "jfr_path": analysis.jfr_path,
        "total_samples": analysis.total_samples,
        "modelstep_samples": analysis.modelstep_samples,
        "whole_run_methods": [
            {"rank": row.rank, "method": row.method, "samples": row.samples, "percent": round(row.percent, 6)}
            for row in analysis.whole_run_methods
        ],
        "modelstep_methods": [
            {"rank": row.rank, "method": row.method, "samples": row.samples, "percent": round(row.percent, 6)}
            for row in analysis.modelstep_methods
        ],
        "modelstep_phases": [
            {
                "line_number": row.line_number,
                "phase": row.phase,
                "samples": row.samples,
                "percent": round(row.percent, 6),
            }
            for row in analysis.modelstep_phases
        ],
    }


def markdown_table_for_methods(rows: list[MethodRow]) -> list[str]:
    lines = [
        "| Rank | Method | Samples | Percent |",
        "| ---: | --- | ---: | ---: |",
    ]
    for row in rows:
        lines.append(f"| {row.rank} | `{row.method}` | {row.samples} | {row.percent:.2f}% |")
    return lines


def markdown_table_for_phases(rows: tuple[PhaseRow, ...]) -> list[str]:
    lines = [
        "| modelStep line | Phase | Samples | Percent |",
        "| ---: | --- | ---: | ---: |",
    ]
    for row in rows:
        lines.append(f"| {row.line_number} | `{row.phase}` | {row.samples} | {row.percent:.2f}% |")
    return lines


def interpretation_lines(analysis: JfrAnalysis) -> list[str]:
    top_phase = max(analysis.modelstep_phases, key=lambda row: row.samples)
    second_phase = sorted(analysis.modelstep_phases, key=lambda row: (-row.samples, row.line_number))[1]
    top_method = analysis.modelstep_methods[0]
    return [
        f"- Dominant `modelStep()` phase: `{top_phase.phase}` at {top_phase.percent:.1f}% of modelStep samples.",
        f"- Second-largest `modelStep()` phase: `{second_phase.phase}` at {second_phase.percent:.1f}% of modelStep samples.",
        f"- Dominant sampled hot method inside this view: `{top_method.method}` at {top_method.percent:.1f}% of modelStep samples.",
    ]


def jfr_method_report(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    analyses: list[JfrAnalysis] = []
    for profile_id, jfr_path, expected_total, expected_modelstep in args.profile:
        analysis = analyze_execution_samples(
            label=profile_id,
            jfr_path=Path(jfr_path),
            expected_total_samples=int(expected_total),
            expected_modelstep_samples=int(expected_modelstep),
        )
        analyses.append(analysis)
        json_path = output_dir / f"{profile_id}-methods.json"
        csv_path = output_dir / f"{profile_id}-methods.csv"
        json_path.write_text(json.dumps(analysis_to_json_payload(analysis), indent=2) + "\n", encoding="utf-8")
        write_methods_csv(csv_path, profile_id, analysis.whole_run_methods, analysis.modelstep_methods)

    lines = [
        "# JFR Method Breakdown",
        "Author: Max Stoddard",
        "",
        "This report is derived from existing JFR `jdk.ExecutionSample` recordings.",
        "Percentages are sample-share estimates, not exact stopwatch timings.",
        "",
    ]

    for analysis in analyses:
        title = short_profile_title(analysis.label)
        whole_rows = rows_with_other(analysis.whole_run_methods, analysis.total_samples)
        modelstep_rows = rows_with_other(analysis.modelstep_methods, analysis.modelstep_samples)
        lines.extend(
            [
                f"## {title}",
                "",
                f"- Profile id: `{analysis.label}`",
                f"- JFR source: `{analysis.jfr_path}`",
                f"- Whole-run `ExecutionSample` count: `{analysis.total_samples}`",
                f"- `modelStep()`-anchored sample count: `{analysis.modelstep_samples}`",
                f"- JSON companion: `{analysis.label}-methods.json`",
                f"- CSV companion: `{analysis.label}-methods.csv`",
                "",
                "### Whole-Run Hot Methods",
                "",
            ]
        )
        lines.extend(markdown_table_for_methods(whole_rows))
        lines.extend(
            [
                "",
                "### `modelStep()`-Only Hot Methods",
                "",
            ]
        )
        lines.extend(markdown_table_for_methods(modelstep_rows))
        lines.extend(
            [
                "",
                "### Direct `modelStep()` Child Breakdown",
                "",
            ]
        )
        lines.extend(markdown_table_for_phases(analysis.modelstep_phases))
        lines.extend(
            [
                "",
                "### Interpretation",
                "",
            ]
        )
        lines.extend(interpretation_lines(analysis))
        lines.append("")

    markdown_path = Path(args.output_markdown)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return 0


def build_folded_stacks(stacks: tuple[tuple[str, ...], ...]) -> dict[tuple[str, ...], int]:
    folded: Counter[tuple[str, ...]] = Counter()
    for stack in stacks:
        if stack:
            folded[stack] += 1
    return dict(folded)


def frame_fill_color(name: str) -> str:
    hue = int(hashlib.sha1(name.encode("utf-8")).hexdigest()[:8], 16) % 360
    return f"hsl({hue},70%,70%)"


def escape_text(value: str) -> str:
    return html.escape(value, quote=True)


def truncate_label(label: str, width_px: float) -> str:
    max_chars = max(int(width_px / 7), 0)
    if max_chars <= 3:
        return ""
    if len(label) <= max_chars:
        return label
    return label[: max_chars - 1] + "…"


def build_flamegraph_svg(
    *,
    title: str,
    subtitle: str,
    sample_count: int,
    stacks: tuple[tuple[str, ...], ...],
) -> str:
    folded = build_folded_stacks(stacks)
    if not folded:
        raise SystemExit("No stacks available to render flame graph.")

    tree: dict[str, dict[str, object]] = {"name": "root", "value": sample_count, "children": {}}
    max_depth = 0
    for stack, count in folded.items():
        node = tree
        max_depth = max(max_depth, len(stack))
        for frame in stack:
            children = node["children"]
            if frame not in children:
                children[frame] = {"name": frame, "value": 0, "children": {}}
            child = children[frame]
            child["value"] += count
            node = child

    svg_height = FLAMEGRAPH_TOP_PADDING + (max_depth * FLAMEGRAPH_FRAME_HEIGHT) + 30
    canvas_width = FLAMEGRAPH_WIDTH - (2 * FLAMEGRAPH_SIDE_PADDING)
    unit_width = canvas_width / sample_count
    elements: list[str] = []

    def render_children(node: dict[str, object], depth: int, x_offset: float) -> None:
        children = list(node["children"].values())
        current_x = x_offset
        for child in children:
            width = float(child["value"]) * unit_width
            if width <= 0:
                continue
            y = svg_height - ((depth + 1) * FLAMEGRAPH_FRAME_HEIGHT) - 10
            rect_x = FLAMEGRAPH_SIDE_PADDING + current_x
            rect_y = y
            label = str(child["name"])
            truncated = truncate_label(label, width - 4)
            elements.append(
                (
                    f'<g>'
                    f'<title>{escape_text(label)} ({child["value"]} samples, {(child["value"] / sample_count) * 100:.2f}%)</title>'
                    f'<rect x="{rect_x:.3f}" y="{rect_y:.3f}" width="{width:.3f}" height="{FLAMEGRAPH_FRAME_HEIGHT - 1}" '
                    f'fill="{frame_fill_color(label)}" stroke="#ffffff" stroke-width="0.5" />'
                )
            )
            if truncated:
                text_y = rect_y + FLAMEGRAPH_FRAME_HEIGHT - 5
                elements.append(
                    f'<text x="{rect_x + 3:.3f}" y="{text_y:.3f}" font-size="{FLAMEGRAPH_FONT_SIZE}" fill="#111111">{escape_text(truncated)}</text>'
                )
            elements.append("</g>")
            render_children(child, depth + 1, current_x)
            current_x += width

    render_children(tree, 0, 0.0)
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{FLAMEGRAPH_WIDTH}" height="{svg_height}" viewBox="0 0 {FLAMEGRAPH_WIDTH} {svg_height}">',
            '<style>text { font-family: "DejaVu Sans Mono", monospace; }</style>',
            f'<text x="{FLAMEGRAPH_SIDE_PADDING}" y="20" font-size="20" font-weight="bold" fill="#111111">{escape_text(title)}</text>',
            f'<text x="{FLAMEGRAPH_SIDE_PADDING}" y="38" font-size="12" fill="#444444">{escape_text(subtitle)}</text>',
            f'<text x="{FLAMEGRAPH_SIDE_PADDING}" y="{svg_height - 2}" font-size="11" fill="#444444">Samples: {sample_count} | View: modelStep()-only | Root: housing.Model.modelStep()</text>',
            *elements,
            "</svg>",
        ]
    )


def jfr_flamegraph(args: argparse.Namespace) -> int:
    analysis = analyze_execution_samples(
        label=args.profile_id,
        jfr_path=Path(args.jfr),
        expected_total_samples=args.expected_total_samples,
        expected_modelstep_samples=args.expected_modelstep_samples,
    )
    svg = build_flamegraph_svg(
        title=args.title,
        subtitle=f"Source: {analysis.jfr_path}",
        sample_count=analysis.modelstep_samples,
        stacks=analysis.modelstep_stacks,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg + "\n", encoding="utf-8")
    return 0


def rewrite_version_resource_paths(config_text: str, version_dir: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        candidate = version_dir / match.group(1)
        if candidate.exists():
            return f'"{candidate.relative_to(REPO_ROOT).as_posix()}"'
        return match.group(0)

    return RESOURCE_PATH_PATTERN.sub(replace, config_text)


def apply_property_overrides(config_text: str, overrides: dict[str, str]) -> str:
    lines = config_text.splitlines()
    output: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in overrides:
            output.append(f"{key} = {overrides[key]}")
            seen.add(key)
        else:
            output.append(line)
    missing = sorted(set(overrides) - seen)
    if missing:
        raise RuntimeError(f"Missing override keys in config: {missing}")
    return "\n".join(output) + "\n"


def materialize_config(args: argparse.Namespace) -> int:
    version_dir = REPO_ROOT / "input-data-versions" / args.snapshot
    version_config_path = version_dir / "config.properties"
    if not version_config_path.exists():
        raise SystemExit(f"Missing snapshot config: {version_config_path}")
    config_text = version_config_path.read_text(encoding="utf-8")
    config_text = rewrite_version_resource_paths(config_text, version_dir)
    overrides = parse_properties(Path(args.mode_file))
    for item in args.override:
        if "=" not in item:
            raise SystemExit(f"Invalid override '{item}'; expected KEY=VALUE")
        key, value = item.split("=", 1)
        overrides[key.strip()] = value.strip()
    config_text = apply_property_overrides(config_text, overrides)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(config_text, encoding="utf-8")
    return 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest_path)
    files = sorted(path for path in output_dir.rglob("*") if path.is_file())
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        for path in files:
            rel_path = path.relative_to(output_dir).as_posix()
            handle.write(f"{sha256_file(path)}  {rel_path}\n")
    return 0


def load_manifest(path: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "  " in stripped:
            digest, rel_path = stripped.split("  ", 1)
        else:
            digest, rel_path = stripped.split(maxsplit=1)
        manifest[rel_path] = digest
    return manifest


def exact_compare(args: argparse.Namespace) -> int:
    baseline = load_manifest(Path(args.baseline_manifest))
    candidate = load_manifest(Path(args.candidate_manifest))
    missing = sorted(set(baseline) - set(candidate))
    extra = sorted(set(candidate) - set(baseline))
    mismatched = sorted(
        rel_path
        for rel_path in baseline
        if rel_path in candidate and baseline[rel_path] != candidate[rel_path]
    )
    lines = [
        "# Exact Regression Report",
        f"baseline_manifest: {args.baseline_manifest}",
        f"candidate_manifest: {args.candidate_manifest}",
        f"status: {'PASS' if not (missing or extra or mismatched) else 'FAIL'}",
        "",
    ]
    if missing:
        lines.append("Missing files:")
        lines.extend(f"- {item}" for item in missing)
        lines.append("")
    if extra:
        lines.append("Extra files:")
        lines.extend(f"- {item}" for item in extra)
        lines.append("")
    if mismatched:
        lines.append("Hash mismatches:")
        for item in mismatched:
            lines.append(f"- {item}")
            lines.append(f"  baseline:  {baseline[item]}")
            lines.append(f"  candidate: {candidate[item]}")
        lines.append("")
    if not (missing or extra or mismatched):
        lines.append("All files matched exactly.")
        lines.append("")
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return 0 if not (missing or extra or mismatched) else 1


def is_numeric_token(token: str) -> bool:
    return bool(NUMERIC_PATTERN.fullmatch(token.strip()))


def compare_csv_files(
    baseline_path: Path,
    candidate_path: Path,
    *,
    abs_tol: float,
    rel_tol: float,
    failures: list[str],
    rel_path: str,
) -> None:
    baseline_lines = baseline_path.read_text(encoding="utf-8").splitlines()
    candidate_lines = candidate_path.read_text(encoding="utf-8").splitlines()
    if len(baseline_lines) != len(candidate_lines):
        failures.append(
            f"{rel_path}: line-count mismatch baseline={len(baseline_lines)} candidate={len(candidate_lines)}"
        )
        return
    for line_no, (baseline_line, candidate_line) in enumerate(zip(baseline_lines, candidate_lines), start=1):
        baseline_tokens = [token.strip() for token in baseline_line.split(";")]
        candidate_tokens = [token.strip() for token in candidate_line.split(";")]
        if len(baseline_tokens) != len(candidate_tokens):
            failures.append(
                f"{rel_path}: line {line_no} column-count mismatch baseline={len(baseline_tokens)} candidate={len(candidate_tokens)}"
            )
            continue
        for col_idx, (baseline_token, candidate_token) in enumerate(zip(baseline_tokens, candidate_tokens), start=1):
            if is_numeric_token(baseline_token) and is_numeric_token(candidate_token):
                baseline_value = float(baseline_token)
                candidate_value = float(candidate_token)
                if not math.isclose(candidate_value, baseline_value, rel_tol=rel_tol, abs_tol=abs_tol):
                    failures.append(
                        f"{rel_path}: line {line_no} col {col_idx} numeric mismatch baseline={baseline_value} candidate={candidate_value}"
                    )
            elif baseline_token != candidate_token:
                failures.append(
                    f"{rel_path}: line {line_no} col {col_idx} text mismatch baseline={baseline_token!r} candidate={candidate_token!r}"
                )


def tolerance_compare(args: argparse.Namespace) -> int:
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    baseline_dir = Path(spec["baseline_dir"])
    candidate_dir = Path(args.candidate_dir)
    abs_tol = float(spec.get("abs_tol", 0.0))
    rel_tol = float(spec.get("rel_tol", 0.0))
    ignore_files = set(spec.get("ignore_files", []))

    baseline_files = {
        path.relative_to(baseline_dir).as_posix(): path
        for path in baseline_dir.rglob("*")
        if path.is_file() and path.relative_to(baseline_dir).as_posix() not in ignore_files
    }
    candidate_files = {
        path.relative_to(candidate_dir).as_posix(): path
        for path in candidate_dir.rglob("*")
        if path.is_file() and path.relative_to(candidate_dir).as_posix() not in ignore_files
    }

    missing = sorted(set(baseline_files) - set(candidate_files))
    extra = sorted(set(candidate_files) - set(baseline_files))
    failures: list[str] = []
    for rel_path in sorted(set(baseline_files) & set(candidate_files)):
        baseline_path = baseline_files[rel_path]
        candidate_path = candidate_files[rel_path]
        if baseline_path.suffix.lower() == ".csv":
            compare_csv_files(
                baseline_path,
                candidate_path,
                abs_tol=abs_tol,
                rel_tol=rel_tol,
                failures=failures,
                rel_path=rel_path,
            )
        elif baseline_path.read_bytes() != candidate_path.read_bytes():
            failures.append(f"{rel_path}: non-CSV file mismatch")

    lines = [
        "# Tolerance Regression Report",
        f"spec: {args.spec}",
        f"candidate_dir: {args.candidate_dir}",
        f"status: {'PASS' if not (missing or extra or failures) else 'FAIL'}",
        "",
    ]
    if missing:
        lines.append("Missing files:")
        lines.extend(f"- {item}" for item in missing)
        lines.append("")
    if extra:
        lines.append("Extra files:")
        lines.extend(f"- {item}" for item in extra)
        lines.append("")
    if failures:
        lines.append("Mismatches:")
        lines.extend(f"- {item}" for item in failures[:200])
        if len(failures) > 200:
            lines.append(f"- ... truncated after 200 mismatches (total={len(failures)})")
        lines.append("")
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return 0 if not (missing or extra or failures) else 1


def gc_summary(args: argparse.Namespace) -> int:
    gc_log = Path(args.gc_log)
    pause_count = 0
    young_pause_count = 0
    full_pause_count = 0
    pause_time_ms_total = 0.0
    line_count = 0
    if gc_log.exists():
        for raw_line in gc_log.read_text(encoding="utf-8", errors="replace").splitlines():
            line_count += 1
            pause_match = PAUSE_PATTERN.search(raw_line)
            if pause_match:
                value = float(pause_match.group(1))
                unit = pause_match.group(2)
                if unit == "s":
                    value *= 1000.0
                elif unit == "us":
                    value /= 1000.0
                pause_count += 1
                pause_time_ms_total += value
                if "Pause Young" in raw_line:
                    young_pause_count += 1
                if "Pause Full" in raw_line:
                    full_pause_count += 1
    output = {
        "gc_log": str(gc_log),
        "line_count": line_count,
        "pause_count": pause_count,
        "young_pause_count": young_pause_count,
        "full_pause_count": full_pause_count,
        "pause_time_ms_total": round(pause_time_ms_total, 6),
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return 0


def benchmark_summary(args: argparse.Namespace) -> int:
    rows: list[dict[str, object]] = []
    with Path(args.runs_tsv).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            parsed = dict(row)
            for key in (
                "wall_clock_seconds",
                "model_computing_seconds",
                "seconds_per_household_month",
                "output_bytes",
                "max_rss_kb",
                "user_cpu_seconds",
                "system_cpu_seconds",
                "gc_pause_count",
                "gc_pause_time_ms_total",
            ):
                value = parsed.get(key, "")
                if value in ("", None):
                    parsed[key] = None
                elif key in ("output_bytes", "max_rss_kb", "gc_pause_count"):
                    parsed[key] = int(float(str(value)))
                else:
                    parsed[key] = float(str(value))
            rows.append(parsed)
    if not rows:
        raise SystemExit("No measured runs found in TSV.")

    metric_summary: dict[str, dict[str, object]] = {}
    numeric_keys = (
        "wall_clock_seconds",
        "model_computing_seconds",
        "seconds_per_household_month",
        "output_bytes",
        "max_rss_kb",
        "user_cpu_seconds",
        "system_cpu_seconds",
        "gc_pause_count",
        "gc_pause_time_ms_total",
    )
    for key in numeric_keys:
        values = [float(row[key]) for row in rows if row[key] is not None]
        if values:
            metric_summary[key] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
            }
        else:
            metric_summary[key] = {
                "count": 0,
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
                "stdev": None,
            }

    median_sorted_rows = sorted(rows, key=lambda item: float(item["wall_clock_seconds"]))
    median_row = median_sorted_rows[(len(median_sorted_rows) - 1) // 2]
    summary = {
        "run_count": len(rows),
        "median_run_id": median_row["run_id"],
        "best_run_id": min(rows, key=lambda item: float(item["wall_clock_seconds"]))["run_id"],
        "metric_summary": metric_summary,
        "runs": rows,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Model-speed helper CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    materialize = subparsers.add_parser("materialize-config", help="Write a full snapshot-local config.")
    materialize.add_argument("--snapshot", required=True)
    materialize.add_argument("--mode-file", required=True)
    materialize.add_argument("--output", required=True)
    materialize.add_argument("--override", action="append", default=[])
    materialize.set_defaults(func=materialize_config)

    manifest = subparsers.add_parser("manifest", help="Write a SHA-256 manifest for an output directory.")
    manifest.add_argument("--output-dir", required=True)
    manifest.add_argument("--manifest-path", required=True)
    manifest.set_defaults(func=write_manifest)

    exact = subparsers.add_parser("exact-compare", help="Compare two exact manifests.")
    exact.add_argument("--baseline-manifest", required=True)
    exact.add_argument("--candidate-manifest", required=True)
    exact.add_argument("--report-path", required=True)
    exact.set_defaults(func=exact_compare)

    tolerance = subparsers.add_parser("tolerance-compare", help="Compare outputs using a tolerance spec.")
    tolerance.add_argument("--spec", required=True)
    tolerance.add_argument("--candidate-dir", required=True)
    tolerance.add_argument("--report-path", required=True)
    tolerance.set_defaults(func=tolerance_compare)

    gc = subparsers.add_parser("gc-summary", help="Summarise a GC log.")
    gc.add_argument("--gc-log", required=True)
    gc.add_argument("--output", required=True)
    gc.set_defaults(func=gc_summary)

    summary = subparsers.add_parser("benchmark-summary", help="Summarise benchmark TSV rows.")
    summary.add_argument("--runs-tsv", required=True)
    summary.add_argument("--output", required=True)
    summary.set_defaults(func=benchmark_summary)

    flamegraph = subparsers.add_parser("jfr-flamegraph", help="Render a modelStep-focused flame graph SVG from JFR.")
    flamegraph.add_argument("--profile-id", required=True)
    flamegraph.add_argument("--jfr", required=True)
    flamegraph.add_argument("--title", required=True)
    flamegraph.add_argument("--output", required=True)
    flamegraph.add_argument("--expected-total-samples", type=int)
    flamegraph.add_argument("--expected-modelstep-samples", type=int)
    flamegraph.set_defaults(func=jfr_flamegraph)

    method_report = subparsers.add_parser(
        "jfr-method-report",
        help="Emit Markdown, CSV, and JSON method-share reports from JFR execution samples.",
    )
    method_report.add_argument(
        "--profile",
        action="append",
        nargs=4,
        metavar=("PROFILE_ID", "JFR_PATH", "EXPECTED_TOTAL", "EXPECTED_MODELSTEP"),
        required=True,
    )
    method_report.add_argument("--output-dir", required=True)
    method_report.add_argument("--output-markdown", required=True)
    method_report.set_defaults(func=jfr_method_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
