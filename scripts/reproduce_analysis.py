#!/usr/bin/env python3
"""Reproduce the principal analysis tables from released case level records."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODE_ORDER = ("origin", "reflect_patch", "reflect_rag_skeleton")
MODEL_ORDER = (
    "mgemmv_llama_11b",
    "mgemmv_qwen_7b",
    "minicpm_v_4_5_8b",
    "qwen2_5_vl_7b",
    "qwen3_vl_8b",
    "llama3_2_11b_vision",
    "internvl3_5_8b",
)
COMPONENT_ORDER = (
    "mgemmv_qwen_7b",
    "mgemmv_llama_11b",
    "minicpm_v_4_5_8b",
    "qwen3_vl_8b",
    "llama3_2_11b_vision",
    "qwen2_5_vl_7b",
    "internvl3_5_8b",
)
MODEL_LABELS = {
    "mgemmv_llama_11b": "MGEMMV-Llama-11B",
    "mgemmv_qwen_7b": "MGEMMV-Qwen-7B",
    "minicpm_v_4_5_8b": "MiniCPM-V-4.5-8B",
    "qwen2_5_vl_7b": "Qwen2.5-VL-7B",
    "qwen3_vl_8b": "Qwen3-VL-8B",
    "llama3_2_11b_vision": "Llama-3.2-11B-Vision",
    "internvl3_5_8b": "InternVL3.5-8B",
}
DATASET_LABELS = {"author135": "Author135", "benchmark1": "Benchmark1"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write an empty table: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def run(command: list[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def equivalent(left: str, right: str, tolerance: float = 1e-9) -> bool:
    if left == right:
        return True
    try:
        return math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance)
    except ValueError:
        return False


def compare_csv(actual: Path, expected: Path) -> list[str]:
    actual_rows = read_csv(actual)
    expected_rows = read_csv(expected)
    findings: list[str] = []
    if len(actual_rows) != len(expected_rows):
        return [f"{actual.name}: row count {len(actual_rows)} != {len(expected_rows)}"]
    if actual_rows and expected_rows and list(actual_rows[0]) != list(expected_rows[0]):
        findings.append(f"{actual.name}: column order differs from {expected.name}")
    for index, (observed, wanted) in enumerate(zip(actual_rows, expected_rows), start=1):
        for field, wanted_value in wanted.items():
            observed_value = observed.get(field, "")
            if not equivalent(observed_value, wanted_value):
                findings.append(
                    f"{actual.name}: row {index} field {field}: "
                    f"{observed_value!r} != {wanted_value!r}"
                )
                if len(findings) >= 20:
                    return findings
    return findings


def build_main_table(reference_root: Path, output_dir: Path) -> tuple[Path, list[Path]]:
    manifest = read_csv(reference_root / "main" / "run_manifest.csv")
    indexed = {(row["model"], row["dataset"]): row for row in manifest}
    if len(indexed) != 14:
        raise ValueError(f"Expected 14 main runs, found {len(indexed)}")

    output_rows: list[dict[str, object]] = []
    source_paths: list[Path] = []
    totals = {mode: {"syntax": 0, "functional": 0} for mode in MODE_ORDER}
    total_cases = 0
    for model in MODEL_ORDER:
        for dataset in ("author135", "benchmark1"):
            entry = indexed[(model, dataset)]
            path = reference_root / entry["reference_csv"]
            rows = read_csv(path)
            expected_cases = int(entry["cases"])
            if len(rows) != expected_cases * len(MODE_ORDER):
                raise ValueError(f"{path.name}: unexpected row count {len(rows)}")
            by_mode = {}
            for mode in MODE_ORDER:
                selected = [row for row in rows if row["mode"] == mode]
                if len(selected) != expected_cases:
                    raise ValueError(f"{path.name}: mode {mode} has {len(selected)} rows")
                syntax = sum(as_bool(row["syntax_ok"]) for row in selected)
                functional = sum(as_bool(row["functional_ok"]) for row in selected)
                by_mode[mode] = (syntax, functional)
                totals[mode]["syntax"] += syntax
                totals[mode]["functional"] += functional
            origin_syntax, origin_functional = by_mode["origin"]
            patch_syntax, patch_functional = by_mode["reflect_patch"]
            full_syntax, full_functional = by_mode["reflect_rag_skeleton"]
            output_rows.append(
                {
                    "model": MODEL_LABELS[model],
                    "dataset": DATASET_LABELS[dataset],
                    "n": expected_cases,
                    "origin_syntax": origin_syntax,
                    "origin_functional": origin_functional,
                    "patch_syntax": patch_syntax,
                    "patch_functional": patch_functional,
                    "full_syntax": full_syntax,
                    "full_functional": full_functional,
                    "delta_origin_pp": f"{100 * (full_functional - origin_functional) / expected_cases:.1f}",
                    "delta_patch_pp": f"{100 * (full_functional - patch_functional) / expected_cases:.1f}",
                }
            )
            total_cases += expected_cases
            source_paths.append(path)

    output_rows.append(
        {
            "model": "ALL",
            "dataset": "Both",
            "n": total_cases,
            "origin_syntax": totals["origin"]["syntax"],
            "origin_functional": totals["origin"]["functional"],
            "patch_syntax": totals["reflect_patch"]["syntax"],
            "patch_functional": totals["reflect_patch"]["functional"],
            "full_syntax": totals["reflect_rag_skeleton"]["syntax"],
            "full_functional": totals["reflect_rag_skeleton"]["functional"],
            "delta_origin_pp": f"{100 * (totals['reflect_rag_skeleton']['functional'] - totals['origin']['functional']) / total_cases:.1f}",
            "delta_patch_pp": f"{100 * (totals['reflect_rag_skeleton']['functional'] - totals['reflect_patch']['functional']) / total_cases:.1f}",
        }
    )
    output = output_dir / "main_effectiveness_table.csv"
    write_csv(output, output_rows)
    return output, source_paths


def reproduce_component(reference_root: Path, output_dir: Path) -> Path:
    component_dir = reference_root / "component"
    command = [sys.executable, "scripts/summarize_unified_mechanism_ablation.py"]
    for model in COMPONENT_ORDER:
        path = component_dir / f"{model}_unified_mechanism_benchmark1_seed1234.csv"
        command.extend(["--input", f"{model}={path}"])
    target = output_dir / "component"
    command.extend(["--expected-cases", "81", "--output-dir", str(target)])
    run(command)
    return target


def reproduce_paired(main_paths: list[Path], output_dir: Path) -> None:
    command = [sys.executable, "scripts/analyze_paired_significance.py"]
    for path in main_paths:
        command.extend(["--run", f"{path.stem}={path}"])
    command.extend(
        [
            "--bootstrap-samples", "10000",
            "--seed", "20260715",
            "--output-dir", str(output_dir / "paired_main"),
        ]
    )
    run(command)


def reproduce_seed(reference_root: Path, output_dir: Path) -> None:
    for directory, label in (
        ("minicpm_v6_2_target12_20260706_1015", "MiniCPM-V-4.5-8B"),
        ("qwen3_v6_2_target12_20260706_1009", "Qwen3-VL-8B"),
    ):
        root = reference_root / "seed" / directory
        raw = [
            path for path in sorted(root.glob("reflect_ablation_*seed*.csv"))
            if re.search(r"seed\d+\.csv$", path.name)
        ]
        if len(raw) != 3:
            raise ValueError(f"{directory}: expected three raw seed files, found {len(raw)}")
        command = [sys.executable, "scripts/summarize_random_seed_generalization.py"]
        for path in raw:
            command.extend(["--input-csv", str(path)])
        command.extend(
            [
                "--model-label", label,
                "--output-dir", str(output_dir / "seed" / directory),
            ]
        )
        run(command)


def reproduce_runtime(reference_root: Path, main_paths: list[Path], output_dir: Path) -> Path:
    command = [sys.executable, "scripts/runtime_iteration_cost_analysis.py"]
    for path in main_paths:
        command.extend(["--input-csv", str(path)])
    log_root = reference_root / "runtime"
    for row in read_csv(log_root / "log_manifest.csv"):
        command.extend(["--log", str(log_root / row["released_log"])])
    target = output_dir / "runtime"
    command.extend(["--output-dir", str(target)])
    run(command)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", default="results/reference")
    parser.add_argument("--output-dir", default="reproduced/analysis")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    reference_root = Path(args.reference_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    expected_root = REPO_ROOT / "results" / "expected"
    output_dir.mkdir(parents=True, exist_ok=True)

    main_table, main_paths = build_main_table(reference_root, output_dir)
    reproduce_paired(main_paths, output_dir)
    component_dir = reproduce_component(reference_root, output_dir)
    reproduce_seed(reference_root, output_dir)
    runtime_dir = reproduce_runtime(reference_root, main_paths, output_dir)

    comparisons = (
        (main_table, expected_root / "main_effectiveness_table.csv"),
        (component_dir / "unified_mode_summary.csv", expected_root / "component_mode_summary.csv"),
        (component_dir / "unified_paired_significance.csv", expected_root / "component_paired_significance.csv"),
        (runtime_dir / "runtime_cost_by_mode.csv", expected_root / "runtime_cost_by_mode.csv"),
    )
    findings = [finding for actual, expected in comparisons for finding in compare_csv(actual, expected)]
    audit = {
        "status": "PASS" if not findings else "FAIL",
        "main_runs": len(main_paths),
        "component_models": len(COMPONENT_ORDER),
        "seed_models": 2,
        "comparisons": [actual.relative_to(output_dir).as_posix() for actual, _ in comparisons],
        "findings": findings,
    }
    (output_dir / "analysis_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))
    if args.strict and findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
