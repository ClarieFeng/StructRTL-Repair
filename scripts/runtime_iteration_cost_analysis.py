#!/usr/bin/env python3
"""Analyze runtime and iteration cost for V6.2 workflow runs.

Inputs:
- one or more raw ablation CSV files, containing mode/module_id/test_id/num_iterations;
- optional execution logs containing lines like:
  [CASE 1/12] module2/test1 seed=3234
  [START] reflect_patch
  [DONE] reflect_patch syntax_ok=True functional_ok=True elapsed=228.8s

Outputs:
- runtime_cost_by_mode.csv
- iteration_distribution_success.csv
- iteration_distribution_failure.csv
- runtime_cost_by_family.csv
- runtime_cost_case_detail.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


MODE_ORDER = ["origin", "reflect_patch", "reflect_rag_skeleton"]

MODULE_FAMILY = {
    1: "adder / PPA",
    2: "adder / PPA",
    3: "adder / PPA",
    4: "adder / PPA",
    5: "adder / PPA",
    6: "adder / PPA",
    7: "adder / PPA",
    8: "adder / PPA",
    9: "adder / PPA",
    10: "MAC / arithmetic accumulation",
    11: "MAC / arithmetic accumulation",
    12: "MAC / arithmetic accumulation",
    13: "multiplier",
    14: "multiplier",
    15: "multiplier",
    16: "multiplier",
    17: "multiplier",
    18: "multiplier",
    19: "multiplier",
    20: "multiplier",
    21: "MAC / arithmetic accumulation",
    22: "Winograd / transform / dataflow",
    23: "Winograd / transform / dataflow",
    24: "Winograd / transform / dataflow",
    25: "Winograd / transform / dataflow",
    26: "PE / PE-row / PE-array",
    27: "PE / PE-row / PE-array",
}


CASE_RE = re.compile(r"\[CASE\s+\d+/\d+\]\s+module(\d+)/test(\d+)")
DONE_RE = re.compile(
    r"\[DONE\]\s+(\S+)\s+syntax_ok=(True|False)\s+functional_ok=(True|False)\s+elapsed=([0-9.]+)s"
)


def parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "1.0", "yes", "pass", "passed"}


def parse_int(value: str | None, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    return int(float(str(value).strip()))


def parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None or str(value).strip() == "":
        return default
    return float(str(value).strip())


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def pstdev(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    rank = max(1, math.ceil(q * len(xs)))
    return xs[rank - 1]


def infer_model(path: Path) -> str:
    name = path.name.lower()
    mapping = [
        ("internvl3", "InternVL3.5-8B-Instruct"),
        ("llama3_2", "Llama-3.2-11B-Vision-Instruct"),
        ("llava", "LLaVA-v1.6-Mistral-7B"),
        ("minicpm", "MiniCPM-V-4.5-8B"),
        ("qwen3", "Qwen3-VL-8B-Instruct"),
        ("qwen2_5", "Qwen2.5-VL-7B-Instruct"),
        ("qwen25", "Qwen2.5-VL-7B-Instruct"),
        ("qwen_vl", "Qwen2.5-VL-7B-Instruct"),
        ("mgemmv_qwen", "MGEMMV-Qwen-7B"),
        ("qwen_7b", "MGEMMV-Qwen-7B"),
        ("mgemmv_llama", "MGEMMV-Llama-11B"),
        ("llama_11b", "MGEMMV-Llama-11B"),
    ]
    for key, label in mapping:
        if key in name:
            return label
    return "unknown"


def infer_dataset(path: Path) -> str:
    name = path.name.lower()
    if "author" in name or "135" in name:
        return "Author135"
    if "benchmark1" in name or "81clean" in name or "81_clean" in name or "81" in name:
        return "Benchmark1"
    return "unknown"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_logs(log_paths: list[Path]) -> dict[tuple[str, str, int, int, str], list[float]]:
    elapsed: dict[tuple[str, str, int, int, str], list[float]] = defaultdict(list)
    for path in log_paths:
        if not path.exists():
            continue
        model = infer_model(path)
        dataset = infer_dataset(path)
        current_case: tuple[int, int] | None = None
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "[INFO] Total cases: 135" in line:
                    dataset = "Author135"
                    continue
                if "[INFO] Total cases: 81" in line:
                    dataset = "Benchmark1"
                    continue
                case_match = CASE_RE.search(line)
                if case_match:
                    current_case = (int(case_match.group(1)), int(case_match.group(2)))
                    continue
                done_match = DONE_RE.search(line)
                if done_match and current_case:
                    mode = done_match.group(1)
                    seconds = float(done_match.group(4))
                    elapsed[(model, dataset, current_case[0], current_case[1], mode)].append(seconds)
    return elapsed


def load_records(
    csv_paths: list[Path],
    elapsed_map: dict[tuple[str, str, int, int, str], list[float]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    elapsed_cursor: Counter[tuple[str, str, int, int, str]] = Counter()
    for path in csv_paths:
        model = infer_model(path)
        dataset = infer_dataset(path)
        for row in read_csv(path):
            mode = row.get("mode", "").strip()
            if not mode:
                continue
            module_id = parse_int(row.get("module_id"))
            test_id = parse_int(row.get("test_id"))
            key = (model, dataset, module_id, test_id, mode)
            elapsed_values = elapsed_map.get(key, [])
            cursor = elapsed_cursor[key]
            elapsed_seconds: float | None = None
            if cursor < len(elapsed_values):
                elapsed_seconds = elapsed_values[cursor]
                elapsed_cursor[key] += 1
            records.append(
                {
                    "model": model,
                    "dataset": dataset,
                    "source_csv": str(path),
                    "mode": mode,
                    "module_id": module_id,
                    "test_id": test_id,
                    "case_id": f"module{module_id}/test{test_id}",
                    "family_group": MODULE_FAMILY.get(module_id, "other / unknown"),
                    "num_iterations": parse_int(row.get("num_iterations"), 1),
                    "final_iteration": parse_int(row.get("final_iteration"), parse_int(row.get("num_iterations"), 1)),
                    "syntax_ok": parse_bool(row.get("syntax_ok")),
                    "functional_ok": parse_bool(row.get("functional_ok")),
                    "elapsed_seconds": elapsed_seconds,
                    "selection_reason": row.get("selection_reason", ""),
                    "final_source": row.get("final_source", ""),
                    "detail": row.get("detail", ""),
                }
            )
    return records


def summarize_by_mode(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        groups[(r["model"], r["dataset"], r["mode"])].append(r)
    rows: list[dict[str, Any]] = []
    for (model, dataset, mode), items in sorted(groups.items()):
        total = len(items)
        syntax = sum(1 for r in items if r["syntax_ok"])
        functional = sum(1 for r in items if r["functional_ok"])
        iterations = [float(r["num_iterations"]) for r in items]
        elapsed = [float(r["elapsed_seconds"]) for r in items if r["elapsed_seconds"] is not None]
        rows.append(
            {
                "model": model,
                "dataset": dataset,
                "mode": mode,
                "total_cases": total,
                "syntax_pass": syntax,
                "functional_pass": functional,
                "syntax_rate": f"{syntax / total:.4f}" if total else "0.0000",
                "functional_rate": f"{functional / total:.4f}" if total else "0.0000",
                "avg_iterations": f"{mean(iterations):.4f}",
                "median_iterations": f"{percentile(iterations, 0.5):.4f}",
                "max_iterations": max(iterations) if iterations else 0,
                "avg_elapsed_seconds": f"{mean(elapsed):.4f}" if elapsed else "",
                "median_elapsed_seconds": f"{percentile(elapsed, 0.5):.4f}" if elapsed else "",
                "p90_elapsed_seconds": f"{percentile(elapsed, 0.9):.4f}" if elapsed else "",
                "std_elapsed_seconds": f"{pstdev(elapsed):.4f}" if elapsed else "",
                "elapsed_coverage": f"{len(elapsed)}/{total}",
                "functional_per_minute": f"{functional / (sum(elapsed) / 60):.4f}" if elapsed and sum(elapsed) > 0 else "",
            }
        )
    return rows


def summarize_iteration_distribution(records: list[dict[str, Any]], success: bool) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        if r["functional_ok"] == success:
            groups[(r["model"], r["dataset"], r["mode"])].append(r)
    rows: list[dict[str, Any]] = []
    prefix = "success" if success else "failure"
    for (model, dataset, mode), items in sorted(groups.items()):
        counts = Counter(int(r["num_iterations"]) for r in items)
        total = len(items)
        rows.append(
            {
                "model": model,
                "dataset": dataset,
                "mode": mode,
                f"{prefix}_total": total,
                f"{prefix}_iter1": counts.get(1, 0),
                f"{prefix}_iter2": counts.get(2, 0),
                f"{prefix}_iter3": counts.get(3, 0),
                f"{prefix}_iter_gt3": sum(v for k, v in counts.items() if k > 3),
                "avg_iterations": f"{mean([float(r['num_iterations']) for r in items]):.4f}" if items else "0.0000",
            }
        )
    return rows


def summarize_by_family(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        groups[(r["model"], r["dataset"], r["family_group"], r["mode"])].append(r)
    rows: list[dict[str, Any]] = []
    for (model, dataset, family, mode), items in sorted(groups.items()):
        total = len(items)
        syntax = sum(1 for r in items if r["syntax_ok"])
        functional = sum(1 for r in items if r["functional_ok"])
        elapsed = [float(r["elapsed_seconds"]) for r in items if r["elapsed_seconds"] is not None]
        rows.append(
            {
                "model": model,
                "dataset": dataset,
                "family_group": family,
                "mode": mode,
                "total_cases": total,
                "syntax_pass": syntax,
                "functional_pass": functional,
                "functional_rate": f"{functional / total:.4f}" if total else "0.0000",
                "avg_iterations": f"{mean([float(r['num_iterations']) for r in items]):.4f}" if items else "0.0000",
                "avg_elapsed_seconds": f"{mean(elapsed):.4f}" if elapsed else "",
                "elapsed_coverage": f"{len(elapsed)}/{total}",
            }
        )
    return rows


def detail_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in records:
        rows.append(
            {
                "model": r["model"],
                "dataset": r["dataset"],
                "mode": r["mode"],
                "case_id": r["case_id"],
                "family_group": r["family_group"],
                "syntax_ok": int(r["syntax_ok"]),
                "functional_ok": int(r["functional_ok"]),
                "num_iterations": r["num_iterations"],
                "final_iteration": r["final_iteration"],
                "elapsed_seconds": "" if r["elapsed_seconds"] is None else f"{r['elapsed_seconds']:.4f}",
                "selection_reason": r["selection_reason"],
                "final_source": r["final_source"],
                "source_csv": r["source_csv"],
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze runtime and iteration cost for V6.2 ablation runs.")
    parser.add_argument("--input-csv", action="append", required=True, help="Raw V6.2 ablation CSV. Can be repeated.")
    parser.add_argument("--log", action="append", default=[], help="Optional execution log containing elapsed=...s lines.")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    csv_paths = [Path(p) for p in args.input_csv]
    log_paths = [Path(p) for p in args.log]
    elapsed_map = parse_logs(log_paths)
    records = load_records(csv_paths, elapsed_map)

    out = Path(args.output_dir)
    outputs = {
        "runtime_cost_by_mode.csv": summarize_by_mode(records),
        "iteration_distribution_success.csv": summarize_iteration_distribution(records, True),
        "iteration_distribution_failure.csv": summarize_iteration_distribution(records, False),
        "runtime_cost_by_family.csv": summarize_by_family(records),
        "runtime_cost_case_detail.csv": detail_rows(records),
    }
    for name, rows in outputs.items():
        write_csv(out / name, rows)
        print(f"Wrote: {out / name}")


if __name__ == "__main__":
    main()
