#!/usr/bin/env python3
"""Analyze best-candidate selection against a last-candidate counterfactual.

The workflow stores one JSON object per repair observation. This script treats
the recorded observations as an auditable repair trace and asks a conservative
counterfactual question: if the framework returned the last observed candidate
instead of the best verified candidate kept by the candidate manager, how often
would the selected verification rank decrease?
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


SUCCESS_EVENTS = {"direct_success", "functional_pass", "success"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiment-root",
        action="append",
        required=True,
        help="Experiment directory containing a logs/ folder with reflect_result_*.jsonl files. Can be repeated.",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--mode",
        action="append",
        default=None,
        help="Optional mode filter, e.g. reflect_patch or reflect_rag_skeleton. Can be repeated.",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def infer_mode(path: Path) -> str:
    name = path.stem
    m = re.match(r"reflect_result_(.+?)_seed\d+_m\d+_t\d+$", name)
    return m.group(1) if m else name.replace("reflect_result_", "")


def infer_run_label(root: Path) -> str:
    name = root.name
    if "minicpm" in name.lower():
        model = "MiniCPM-V-4.5-8B"
    elif "qwen" in name.lower():
        model = "MGEMMV-Qwen-7B"
    else:
        model = name
    if "benchmark1" in name.lower() or "81clean" in name.lower():
        dataset = "Benchmark1 81"
    elif "author" in name.lower():
        dataset = "Author Evaluation 135"
    else:
        dataset = "unknown"
    return model, dataset


def row_score(row: dict) -> tuple[int, bool, bool]:
    event = str(row.get("event", "")).lower()
    stage = str(row.get("stage", "")).lower()
    functional = event in SUCCESS_EVENTS or bool(row.get("functional_ok", False))
    syntax = functional or bool(row.get("syntax_ok", False)) or stage in {"functional", "compile", "compilation"}
    if functional:
        return 2, True, True
    if syntax:
        return 1, True, False
    return 0, False, False


def best_row(rows: list[dict]) -> dict:
    best = rows[0]
    best_key = (row_score(best)[0], -int(best.get("iteration", 0)))
    for row in rows[1:]:
        key = (row_score(row)[0], -int(row.get("iteration", 0)))
        if key > best_key:
            best = row
            best_key = key
    return best


def analyze_file(path: Path, root: Path, model: str, dataset: str) -> dict | None:
    rows = read_jsonl(path)
    if not rows:
        return None
    first = rows[0]
    last = rows[-1]
    best = best_row(rows)
    mode = infer_mode(path)
    best_score, best_syntax, best_functional = row_score(best)
    last_score, last_syntax, last_functional = row_score(last)
    return {
        "model": model,
        "dataset": dataset,
        "experiment": root.name,
        "mode": mode,
        "module_id": first.get("module_id", ""),
        "test_id": first.get("test_id", ""),
        "trace_rows": len(rows),
        "best_iteration": best.get("iteration", ""),
        "last_iteration": last.get("iteration", ""),
        "best_event": best.get("event", ""),
        "last_event": last.get("event", ""),
        "best_stage": best.get("stage", ""),
        "last_stage": last.get("stage", ""),
        "best_score": best_score,
        "last_score": last_score,
        "best_syntax": int(best_syntax),
        "last_syntax": int(last_syntax),
        "best_functional": int(best_functional),
        "last_functional": int(last_functional),
        "selection_regression": int(best_score > last_score),
        "functional_regression": int(best_functional and not last_functional),
        "syntax_regression": int(best_syntax and not last_syntax),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["model"], row["dataset"], row["mode"])].append(row)
    out: list[dict] = []
    for (model, dataset, mode), group in sorted(groups.items()):
        total = len(group)
        out.append(
            {
                "model": model,
                "dataset": dataset,
                "mode": mode,
                "cases": total,
                "best_syntax": sum(int(r["best_syntax"]) for r in group),
                "last_syntax": sum(int(r["last_syntax"]) for r in group),
                "best_functional": sum(int(r["best_functional"]) for r in group),
                "last_functional": sum(int(r["last_functional"]) for r in group),
                "selection_regressions_avoided": sum(int(r["selection_regression"]) for r in group),
                "functional_regressions_avoided": sum(int(r["functional_regression"]) for r in group),
                "syntax_regressions_avoided": sum(int(r["syntax_regression"]) for r in group),
            }
        )
    return out


def write_markdown(path: Path, summary_rows: list[dict]) -> None:
    lines = [
        "# 候选管理器反事实分析",
        "",
        "本分析比较 workflow 中的候选管理器与一个保守的反事实策略：如果不保留历史最高验证等级，而是直接返回同一条修复轨迹中的最后一个候选，最终选择会发生什么变化。",
        "",
        "验证等级定义为：functional pass = 2，syntax valid but not functional = 1，syntax failure = 0。该分析只读取已有 JSONL repair history，不重新调用模型。",
        "",
        "| Model | Dataset | Mode | Cases | Best syntax | Last syntax | Best functional | Last functional | Selection regressions avoided |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['model']} | {row['dataset']} | {row['mode']} | {row['cases']} | "
            f"{row['best_syntax']} | {row['last_syntax']} | "
            f"{row['best_functional']} | {row['last_functional']} | "
            f"{row['selection_regressions_avoided']} |"
        )
    lines.extend(
        [
            "",
            "论文写法：这组结果支持一个克制但重要的机制结论。候选管理器不是装饰性实现，它能防止后续失败修复覆盖已有的更高等级候选。在当前 component ablation 轨迹中，避免的主要是 syntax 等级回退，而不是 functional pass 被覆盖。因此正文中应将其表述为稳定选择和 do not regress 机制，而不应夸大为独立带来功能正确率提升。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    modes = set(args.mode or [])
    rows: list[dict] = []
    for root_text in args.experiment_root:
        root = Path(root_text)
        model, dataset = infer_run_label(root)
        for path in sorted((root / "logs").glob("reflect_result_*.jsonl")):
            mode = infer_mode(path)
            if modes and mode not in modes:
                continue
            row = analyze_file(path, root, model, dataset)
            if row:
                rows.append(row)
    summary_rows = summarize(rows)
    write_csv(out_dir / "candidate_selection_per_case.csv", rows)
    write_csv(out_dir / "candidate_selection_summary.csv", summary_rows)
    write_markdown(out_dir / "candidate_selection_summary_zh.md", summary_rows)
    print(f"Input traces: {len(rows)}")
    print(f"Summary rows: {len(summary_rows)}")
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()
