#!/usr/bin/env python3
"""Baseline vs refactor regression harness for WAS+NMG script refactor."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

RTOL = 1e-9
ATOL = 1e-12


@dataclass
class RunResult:
    name: str
    command: list[str]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str


def run_cmd(name: str, command: list[str], cwd: Path, env: dict[str, str]) -> RunResult:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return RunResult(
        name=name,
        command=command,
        cwd=cwd,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def compare_csv(a: Path, b: Path) -> tuple[bool, str]:
    if not a.exists() or not b.exists():
        return False, "missing file"
    try:
        da = pd.read_csv(a, comment="#")
        db = pd.read_csv(b, comment="#")
    except Exception as exc:
        return False, f"csv read error: {exc}"

    if list(da.columns) != list(db.columns):
        return False, f"column mismatch: {list(da.columns)} != {list(db.columns)}"
    if len(da.index) != len(db.index):
        return False, f"row mismatch: {len(da.index)} != {len(db.index)}"

    for col in da.columns:
        sa = da[col]
        sb = db[col]
        if pd.api.types.is_numeric_dtype(sa) and pd.api.types.is_numeric_dtype(sb):
            if not ((sa - sb).abs() <= (ATOL + RTOL * sb.abs())).all():
                diff = (sa - sb).abs().max()
                return False, f"numeric mismatch in {col}, max_abs_diff={diff}"
        else:
            if not sa.astype(str).str.strip().equals(sb.astype(str).str.strip()):
                return False, f"text mismatch in {col}"

    return True, "ok"


def extract_float(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text)
    if not m:
        return None
    return float(m.group(1))


def compare_scalar(name: str, a: float | None, b: float | None) -> tuple[bool, str]:
    if a is None or b is None:
        return False, f"missing scalar for {name}"
    ok = abs(a - b) <= (ATOL + RTOL * abs(b))
    if ok:
        return True, "ok"
    return False, f"{name} mismatch {a} vs {b}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run baseline/refactor regression checks.")
    parser.add_argument(
        "--results-subdir",
        default="Results/v1-output",
        help="Results subdir for validation scripts.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    tmp_root = repo_root / "tmp" / "regression"
    baseline_root = tmp_root / "baseline"
    refactor_root = tmp_root / "refactor"
    report_json = tmp_root / "report.json"
    report_md = tmp_root / "REPORT.md"

    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    baseline_root.mkdir(parents=True)
    refactor_root.mkdir(parents=True)

    common_env = os.environ.copy()
    common_env.update(
        {
            "MPLBACKEND": "Agg",
            "WAS_DATA_ROOT": str(repo_root),
            "WAS_RESULTS_ROOT": str(repo_root),
            "WAS_RESULTS_RUN_SUBDIR": args.results_subdir,
            "WAS_DATASET": "R8",
        }
    )

    legacy_anchor = repo_root / "src/main/resources/calibration-code/AgeDist.py"
    if not legacy_anchor.exists():
        raise SystemExit(
            "Legacy baseline scripts are no longer present in src/main/resources. "
            "Use the captured evidence in tmp/regression/report.json and tmp/regression/REPORT.md."
        )

    # Run baseline scripts.
    baseline_runs: list[RunResult] = []
    baseline_calibration_dir = baseline_root / "was_calibration"
    baseline_calibration_dir.mkdir(parents=True)

    baseline_cmds = [
        ("base_personal_allowance", ["python3", str(repo_root / "src/main/resources/calibration-code/PersonalAllowance.py")], baseline_calibration_dir),
        ("base_age_dist", ["python3", str(repo_root / "src/main/resources/calibration-code/AgeDist.py")], baseline_calibration_dir),
        ("base_wealth_income", ["python3", str(repo_root / "src/main/resources/calibration-code/WealthIncomeJointProbDist.py")], baseline_calibration_dir),
        ("base_income_age", ["python3", str(repo_root / "src/main/resources/calibration-code/IncomeAgeJointProbDist.py")], baseline_calibration_dir),
        ("base_btl_prob", ["python3", str(repo_root / "src/main/resources/calibration-code/BTLProbabilityPerIncomePercentileBin.py")], baseline_calibration_dir),
        ("base_total_wealth", ["python3", str(repo_root / "src/main/resources/calibration-code/TotalWealthDist.py")], baseline_calibration_dir),
        ("base_nmg_rental", ["python3", "src/main/resources/calibration-code/nmg/NmgRentalLogNormalFit.py", "private-datasets/nmg/nmg-2016.csv"], repo_root),
        ("base_nmg_desired", ["python3", "src/main/resources/calibration-code/nmg/NmgDesiredRentPowerFit.py", "private-datasets/nmg/nmg-2016.csv"], repo_root),
        ("base_nmg_param_search", ["python3", "src/main/resources/experiments/nmg/NmgRentalParameterSearch.py", "private-datasets/nmg/nmg-2016.csv", "--config-path", "input-data-versions/v0/config.properties"], repo_root),
        ("base_nmg_method_search", ["python3", "src/main/resources/experiments/nmg/NmgDesiredRentMethodSearch.py", "private-datasets/nmg/nmg-2016.csv", "--config-path", "src/main/resources/config.properties", "--top-k", "20"], repo_root),
        ("base_valid_income", ["python3", "src/main/resources/validation-code/IncomeDist.py"], repo_root),
        ("base_valid_housing", ["python3", "src/main/resources/validation-code/HousingWealthDist.py"], repo_root),
        ("base_valid_financial", ["python3", "src/main/resources/validation-code/FinancialWealthDist.py"], repo_root),
        ("base_exp_age", ["python3", "src/main/resources/experiments/AgeDistributionComparison.py"], repo_root),
        ("base_exp_btl", ["python3", "src/main/resources/experiments/BTLProbabilityPerIncomePercentileComparison.py"], repo_root),
        ("base_exp_age_income", ["python3", "src/main/resources/experiments/AgeGrossIncomeJointDistComparison.py"], repo_root),
        ("base_exp_income_wealth", ["python3", "src/main/resources/experiments/GrossIncomeNetWealthJointDistComparison.py"], repo_root),
        ("base_exp_total_wealth", ["python3", "src/main/resources/experiments/TotalWealthDistComparison.py"], repo_root),
    ]

    for name, cmd, cwd in baseline_cmds:
        res = run_cmd(name, cmd, cwd, common_env)
        baseline_runs.append(res)
        write_text(baseline_root / "stdout" / f"{name}.out", res.stdout)
        write_text(baseline_root / "stderr" / f"{name}.err", res.stderr)

    # Capture baseline outputs.
    baseline_exp_dir = baseline_root / "was_experiments"
    baseline_exp_dir.mkdir(parents=True)
    for file_name in [
        "AgeDistributionStats.csv",
        "BTLProbabilityPerIncomePercentileStats.csv",
        "AgeGrossIncomeJointDistStats.csv",
        "GrossIncomeNetWealthJointDistStats.csv",
        "TotalWealthDistStats.csv",
    ]:
        src = repo_root / "src/main/resources/experiments/outputs" / file_name
        if src.exists():
            shutil.copy2(src, baseline_exp_dir / file_name)

    for file_name in [
        "BTLProbabilityPerIncomePercentileBin-W3.csv",
        "BTLProbabilityPerIncomePercentileBin-R8.csv",
    ]:
        src = repo_root / file_name
        if src.exists():
            shutil.copy2(src, baseline_exp_dir / file_name)

    # Run refactored scripts.
    refactor_runs: list[RunResult] = []
    refactor_calibration_dir = refactor_root / "was_calibration"
    refactor_calibration_dir.mkdir(parents=True)
    refactor_exp_dir = refactor_root / "was_experiments"
    refactor_exp_dir.mkdir(parents=True)

    refactor_cmds = [
        ("new_personal_allowance", ["python3", "-m", "scripts.python.experiments.was.personal_allowance"], repo_root),
        ("new_age_dist", ["python3", "-m", "scripts.python.calibration.was.age_dist", "--output-dir", str(refactor_calibration_dir)], repo_root),
        ("new_wealth_income", ["python3", "-m", "scripts.python.calibration.was.wealth_income_joint_prob_dist", "--output-dir", str(refactor_calibration_dir)], repo_root),
        ("new_income_age", ["python3", "-m", "scripts.python.calibration.was.income_age_joint_prob_dist", "--output-dir", str(refactor_calibration_dir)], repo_root),
        ("new_btl_prob", ["python3", "-m", "scripts.python.calibration.was.btl_probability_per_income_percentile_bin", "--output-dir", str(refactor_calibration_dir)], repo_root),
        ("new_total_wealth", ["python3", "-m", "scripts.python.calibration.legacy.total_wealth_dist", "--output-dir", str(refactor_calibration_dir)], repo_root),
        ("new_nmg_rental", ["python3", "-m", "scripts.python.calibration.nmg.nmg_rental_lognormal_fit", "private-datasets/nmg/nmg-2016.csv"], repo_root),
        ("new_nmg_desired", ["python3", "-m", "scripts.python.calibration.nmg.nmg_desired_rent_power_fit", "private-datasets/nmg/nmg-2016.csv"], repo_root),
        ("new_nmg_param_search", ["python3", "-m", "scripts.python.experiments.nmg.nmg_rental_parameter_search", "private-datasets/nmg/nmg-2016.csv", "--config-path", "input-data-versions/v0/config.properties"], repo_root),
        ("new_nmg_method_search", ["python3", "-m", "scripts.python.experiments.nmg.nmg_desired_rent_method_search", "private-datasets/nmg/nmg-2016.csv", "--config-path", "src/main/resources/config.properties", "--top-k", "20"], repo_root),
        ("new_valid_income", ["python3", "-m", "scripts.python.validation.was.income_dist"], repo_root),
        ("new_valid_housing", ["python3", "-m", "scripts.python.validation.was.housing_wealth_dist"], repo_root),
        ("new_valid_financial", ["python3", "-m", "scripts.python.validation.was.financial_wealth_dist"], repo_root),
        ("new_exp_age", ["python3", "-m", "scripts.python.experiments.was.age_distribution_comparison", "--output-dir", str(refactor_exp_dir)], repo_root),
        ("new_exp_btl", ["python3", "-m", "scripts.python.experiments.was.btl_probability_per_income_percentile_comparison", "--output-dir", str(refactor_exp_dir)], repo_root),
        ("new_exp_age_income", ["python3", "-m", "scripts.python.experiments.was.age_gross_income_joint_dist_comparison", "--output-dir", str(refactor_exp_dir)], repo_root),
        ("new_exp_income_wealth", ["python3", "-m", "scripts.python.experiments.was.gross_income_net_wealth_joint_dist_comparison", "--output-dir", str(refactor_exp_dir)], repo_root),
        ("new_exp_total_wealth", ["python3", "-m", "scripts.python.experiments.was.total_wealth_dist_comparison", "--output-dir", str(refactor_exp_dir)], repo_root),
    ]

    for name, cmd, cwd in refactor_cmds:
        res = run_cmd(name, cmd, cwd, common_env)
        refactor_runs.append(res)
        write_text(refactor_root / "stdout" / f"{name}.out", res.stdout)
        write_text(refactor_root / "stderr" / f"{name}.err", res.stderr)

    # Comparisons.
    comparisons: list[dict[str, str | bool]] = []

    # Command status.
    for run in baseline_runs + refactor_runs:
        comparisons.append(
            {
                "name": f"command::{run.name}",
                "ok": run.returncode == 0,
                "detail": f"returncode={run.returncode}",
            }
        )

    # Calibration CSV outputs.
    for baseline_file in sorted(baseline_calibration_dir.glob("*.csv")):
        target = refactor_calibration_dir / baseline_file.name
        ok, detail = compare_csv(baseline_file, target)
        comparisons.append(
            {
                "name": f"calibration_csv::{baseline_file.name}",
                "ok": ok,
                "detail": detail,
            }
        )

    # Experiment stats outputs.
    for baseline_file in sorted(baseline_exp_dir.glob("*.csv")):
        target = refactor_exp_dir / baseline_file.name
        ok, detail = compare_csv(baseline_file, target)
        comparisons.append(
            {
                "name": f"experiment_csv::{baseline_file.name}",
                "ok": ok,
                "detail": detail,
            }
        )

    # Scalar stdout comparisons for key scripts.
    scalar_specs = [
        (
            "nmg_rental_scale",
            baseline_root / "stdout/base_nmg_rental.out",
            refactor_root / "stdout/new_nmg_rental.out",
            r"RENTAL_PRICES_SCALE\s*=\s*([\-0-9.eE]+)",
        ),
        (
            "nmg_rental_shape",
            baseline_root / "stdout/base_nmg_rental.out",
            refactor_root / "stdout/new_nmg_rental.out",
            r"RENTAL_PRICES_SHAPE\s*=\s*([\-0-9.eE]+)",
        ),
        (
            "nmg_desired_scale",
            baseline_root / "stdout/base_nmg_desired.out",
            refactor_root / "stdout/new_nmg_desired.out",
            r"DESIRED_RENT_SCALE\s*=\s*([\-0-9.eE]+)",
        ),
        (
            "nmg_desired_exponent",
            baseline_root / "stdout/base_nmg_desired.out",
            refactor_root / "stdout/new_nmg_desired.out",
            r"DESIRED_RENT_EXPONENT\s*=\s*([\-0-9.eE]+)",
        ),
        (
            "nmg_method_best_scale",
            baseline_root / "stdout/base_nmg_method_search.out",
            refactor_root / "stdout/new_nmg_method_search.out",
            r"DESIRED_RENT_SCALE\s*~=\s*([\-0-9.eE]+)",
        ),
        (
            "nmg_method_best_exp",
            baseline_root / "stdout/base_nmg_method_search.out",
            refactor_root / "stdout/new_nmg_method_search.out",
            r"DESIRED_RENT_EXPONENT\s*~=\s*([\-0-9.eE]+)",
        ),
        (
            "personal_allowance_single",
            baseline_root / "stdout/base_personal_allowance.out",
            refactor_root / "stdout/new_personal_allowance.out",
            r"single personal allowance\s+([\-0-9.eE]+)",
        ),
        (
            "personal_allowance_double",
            baseline_root / "stdout/base_personal_allowance.out",
            refactor_root / "stdout/new_personal_allowance.out",
            r"double personal allowance\s+([\-0-9.eE]+)",
        ),
        (
            "validation_income_diff",
            baseline_root / "stdout/base_valid_income.out",
            refactor_root / "stdout/new_valid_income.out",
            r"Income total diff:\s*([\-0-9.eE]+)",
        ),
        (
            "validation_housing_diff",
            baseline_root / "stdout/base_valid_housing.out",
            refactor_root / "stdout/new_valid_housing.out",
            r"Housing wealth total diff:\s*([\-0-9.eE]+)",
        ),
        (
            "validation_financial_diff",
            baseline_root / "stdout/base_valid_financial.out",
            refactor_root / "stdout/new_valid_financial.out",
            r"Financial wealth total diff:\s*([\-0-9.eE]+)",
        ),
    ]

    for metric, a_path, b_path, pattern in scalar_specs:
        a_text = a_path.read_text(encoding="utf-8") if a_path.exists() else ""
        b_text = b_path.read_text(encoding="utf-8") if b_path.exists() else ""
        ok, detail = compare_scalar(metric, extract_float(pattern, a_text), extract_float(pattern, b_text))
        comparisons.append({"name": f"scalar::{metric}", "ok": ok, "detail": detail})

    pass_count = sum(1 for item in comparisons if item["ok"])
    fail_count = len(comparisons) - pass_count

    report = {
        "rtol": RTOL,
        "atol": ATOL,
        "total_checks": len(comparisons),
        "pass": pass_count,
        "fail": fail_count,
        "checks": comparisons,
    }
    report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Regression Report",
        "",
        f"- Total checks: {len(comparisons)}",
        f"- Pass: {pass_count}",
        f"- Fail: {fail_count}",
        f"- Tolerances: rtol={RTOL}, atol={ATOL}",
        "",
        "## Failed Checks",
    ]
    failed = [item for item in comparisons if not item["ok"]]
    if not failed:
        lines.append("- None")
    else:
        for item in failed:
            lines.append(f"- `{item['name']}`: {item['detail']}")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if fail_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
