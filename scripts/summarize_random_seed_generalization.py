#!/usr/bin/env python3
"""Summarize small multi-seed V6.2 workflow probes.

The script accepts either raw ablation CSV files or mode-summary CSV files.
Raw CSVs are preferred because they also allow family-level fluctuation tables.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path


MODE_ORDER = ["origin", "reflect_patch", "reflect_rag_skeleton"]

MODULE_FAMILY = {
    1: "adder / PPA",
    2: "adder / PPA",
    3: "adder / PPA",
    4: "adder / PPA",
    17: "multiplier",
    20: "multiplier",
    24: "Winograd / transform / dataflow",
    25: "Winograd / transform / dataflow",
    26: "PE / PE-row / PE-array",
    27: "PE / PE-row / PE-array",
}


def parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "1.0", "true", "yes", "pass", "passed"}


def parse_int(value: str | None, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    return int(float(str(value).strip()))


def parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None or str(value).strip() == "":
        return default
    return float(str(value).strip())


def infer_seed(path: Path) -> str:
    match = re.search(r"seed(\d+)", path.name)
    return match.group(1) if match else "unknown"


def infer_dataset(path: Path) -> str:
    name = path.name.lower()
    if "author" in name or "135" in name:
        return "Author135"
    if "benchmark1" in name or "81clean" in name or "81" in name:
        return "Benchmark1"
    return "target_subset"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def is_mode_summary(rows: list[dict[str, str]]) -> bool:
    if not rows:
        return False
    fields = set(rows[0].keys())
    return {"mode", "total", "syntax", "functional"}.issubset(fields)


def summarize_raw(rows: list[dict[str, str]]) -> tuple[dict[str, dict], dict[tuple[str, str], dict]]:
    by_mode: dict[str, dict] = defaultdict(lambda: {"total": 0, "syntax": 0, "functional": 0, "iterations": []})
    by_family: dict[tuple[str, str], dict] = defaultdict(lambda: {"total": 0, "syntax": 0, "functional": 0})
    for row in rows:
        mode = row.get("mode", "").strip()
        if not mode:
            continue
        syntax_ok = parse_bool(row.get("syntax_ok") or row.get("syntax"))
        functional_ok = parse_bool(row.get("functional_ok") or row.get("functional"))
        iteration = parse_float(row.get("iterations") or row.get("avg_iterations"), 0.0)
        stats = by_mode[mode]
        stats["total"] += 1
        stats["syntax"] += int(syntax_ok)
        stats["functional"] += int(functional_ok)
        if iteration:
            stats["iterations"].append(iteration)

        module_id = parse_int(row.get("module_id"), 0)
        family = MODULE_FAMILY.get(module_id, row.get("family", "other/unknown") or "other/unknown")
        fstats = by_family[(family, mode)]
        fstats["total"] += 1
        fstats["syntax"] += int(syntax_ok)
        fstats["functional"] += int(functional_ok)
    return by_mode, by_family


def summarize_mode_summary(rows: list[dict[str, str]]) -> dict[str, dict]:
    by_mode: dict[str, dict] = {}
    for row in rows:
        mode = row.get("mode", "").strip()
        if not mode:
            continue
        by_mode[mode] = {
            "total": parse_int(row.get("total")),
            "syntax": parse_int(row.get("syntax")),
            "functional": parse_int(row.get("functional")),
            "iterations": [parse_float(row.get("avg_iterations"), 0.0)],
        }
    return by_mode


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def pstdev(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / len(values))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize V6.2 random-seed target subset probes.")
    parser.add_argument("--input-csv", action="append", required=True, help="Raw ablation CSV or mode_summary CSV.")
    parser.add_argument("--model-label", required=True)
    parser.add_argument("--subset-label", default="benchmark1_target12")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    per_seed_rows: list[dict] = []
    family_rows: list[dict] = []

    for item in args.input_csv:
        path = Path(item)
        rows = read_csv(path)
        seed = infer_seed(path)
        dataset = infer_dataset(path)
        if is_mode_summary(rows):
            by_mode = summarize_mode_summary(rows)
            by_family = {}
        else:
            by_mode, by_family = summarize_raw(rows)

        for mode in MODE_ORDER:
            if mode not in by_mode:
                continue
            stats = by_mode[mode]
            total = stats["total"]
            syntax = stats["syntax"]
            functional = stats["functional"]
            per_seed_rows.append(
                {
                    "model": args.model_label,
                    "dataset": dataset,
                    "subset": args.subset_label,
                    "seed": seed,
                    "mode": mode,
                    "total": total,
                    "syntax": syntax,
                    "functional": functional,
                    "syntax_rate": f"{syntax / total:.4f}" if total else "0.0000",
                    "functional_rate": f"{functional / total:.4f}" if total else "0.0000",
                    "avg_iterations": f"{mean(stats['iterations']):.4f}" if stats["iterations"] else "0.0000",
                    "source_csv": str(path),
                }
            )

        for (family, mode), stats in by_family.items():
            total = stats["total"]
            syntax = stats["syntax"]
            functional = stats["functional"]
            family_rows.append(
                {
                    "model": args.model_label,
                    "dataset": dataset,
                    "subset": args.subset_label,
                    "seed": seed,
                    "family_group": family,
                    "mode": mode,
                    "total": total,
                    "syntax": syntax,
                    "functional": functional,
                    "functional_rate": f"{functional / total:.4f}" if total else "0.0000",
                }
            )

    aggregate_rows: list[dict] = []
    by_mode_values: dict[str, list[int]] = defaultdict(list)
    by_mode_syntax: dict[str, list[int]] = defaultdict(list)
    for row in per_seed_rows:
        by_mode_values[row["mode"]].append(int(row["functional"]))
        by_mode_syntax[row["mode"]].append(int(row["syntax"]))

    for mode in MODE_ORDER:
        vals = by_mode_values.get(mode, [])
        syn_vals = by_mode_syntax.get(mode, [])
        if not vals:
            continue
        aggregate_rows.append(
            {
                "model": args.model_label,
                "subset": args.subset_label,
                "mode": mode,
                "num_seeds": len(vals),
                "mean_functional": f"{mean(vals):.4f}",
                "std_functional": f"{pstdev(vals):.4f}",
                "min_functional": min(vals),
                "max_functional": max(vals),
                "mean_syntax": f"{mean(syn_vals):.4f}",
                "std_syntax": f"{pstdev(syn_vals):.4f}",
                "min_syntax": min(syn_vals),
                "max_syntax": max(syn_vals),
            }
        )

    out = Path(args.output_dir)
    write_csv(
        out / "random_seed_by_seed_mode.csv",
        per_seed_rows,
        [
            "model",
            "dataset",
            "subset",
            "seed",
            "mode",
            "total",
            "syntax",
            "functional",
            "syntax_rate",
            "functional_rate",
            "avg_iterations",
            "source_csv",
        ],
    )
    write_csv(
        out / "random_seed_mode_aggregate.csv",
        aggregate_rows,
        [
            "model",
            "subset",
            "mode",
            "num_seeds",
            "mean_functional",
            "std_functional",
            "min_functional",
            "max_functional",
            "mean_syntax",
            "std_syntax",
            "min_syntax",
            "max_syntax",
        ],
    )
    if family_rows:
        write_csv(
            out / "random_seed_by_family_mode.csv",
            family_rows,
            [
                "model",
                "dataset",
                "subset",
                "seed",
                "family_group",
                "mode",
                "total",
                "syntax",
                "functional",
                "functional_rate",
            ],
        )
    print(f"Wrote: {out / 'random_seed_by_seed_mode.csv'}")
    print(f"Wrote: {out / 'random_seed_mode_aggregate.csv'}")
    if family_rows:
        print(f"Wrote: {out / 'random_seed_by_family_mode.csv'}")


if __name__ == "__main__":
    main()
