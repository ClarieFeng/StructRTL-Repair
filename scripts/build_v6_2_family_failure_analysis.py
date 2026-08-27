#!/usr/bin/env python3
"""Build paper-ready V6.2 family gain/failure analysis tables."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def as_int(row: dict[str, str], key: str) -> int:
    value = row.get(key, "")
    return int(float(value)) if value not in ("", None) else 0


def rate(num: int, den: int) -> float:
    return round(num / den, 3) if den else 0.0


def classify_row(origin_func_rate: float, patch_func_rate: float, rag_func_rate: float) -> str:
    if rag_func_rate >= 0.9:
        return "ceiling_after_rag_skeleton"
    if rag_func_rate < 0.5:
        return "persistent_functional_failure"
    if patch_func_rate - origin_func_rate >= 0.35 and rag_func_rate - patch_func_rate < 0.1:
        return "patch_already_strong"
    if rag_func_rate - patch_func_rate >= 0.35:
        return "rag_skeleton_major_gain"
    if rag_func_rate > patch_func_rate:
        return "rag_skeleton_incremental_gain"
    if rag_func_rate == patch_func_rate:
        return "rag_skeleton_tie"
    return "rag_skeleton_regression"


def build_family_tables(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    detail_rows: list[dict[str, Any]] = []
    aggregate: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in rows:
        total = as_int(row, "total")
        origin_syntax = as_int(row, "origin_syntax")
        patch_syntax = as_int(row, "patch_syntax")
        rag_syntax = as_int(row, "rag_skeleton_syntax")
        origin_func = as_int(row, "origin_functional")
        patch_func = as_int(row, "patch_functional")
        rag_func = as_int(row, "rag_skeleton_functional")

        origin_func_rate = rate(origin_func, total)
        patch_func_rate = rate(patch_func, total)
        rag_func_rate = rate(rag_func, total)

        detail = {
            "dataset": row["dataset"],
            "model": row["model"],
            "family": row["family"],
            "total": total,
            "origin_syntax": origin_syntax,
            "patch_syntax": patch_syntax,
            "rag_skeleton_syntax": rag_syntax,
            "origin_functional": origin_func,
            "patch_functional": patch_func,
            "rag_skeleton_functional": rag_func,
            "origin_functional_rate": origin_func_rate,
            "patch_functional_rate": patch_func_rate,
            "rag_skeleton_functional_rate": rag_func_rate,
            "patch_gain_over_origin": patch_func - origin_func,
            "rag_gain_over_patch": rag_func - patch_func,
            "rag_gain_over_origin": rag_func - origin_func,
            "residual_functional_failures": total - rag_func,
            "diagnosis_label": classify_row(origin_func_rate, patch_func_rate, rag_func_rate),
        }
        detail_rows.append(detail)

        key = (row["dataset"], row["model"])
        agg = aggregate[key]
        for name, value in detail.items():
            if name in {
                "total",
                "origin_syntax",
                "patch_syntax",
                "rag_skeleton_syntax",
                "origin_functional",
                "patch_functional",
                "rag_skeleton_functional",
                "patch_gain_over_origin",
                "rag_gain_over_patch",
                "rag_gain_over_origin",
                "residual_functional_failures",
            }:
                agg[name] += int(value)
        agg[f"label:{detail['diagnosis_label']}"] += 1

    summary_rows = []
    for (dataset, model), agg in sorted(aggregate.items()):
        total = agg["total"]
        label_counts = {k.replace("label:", ""): v for k, v in agg.items() if k.startswith("label:")}
        summary_rows.append(
            {
                "dataset": dataset,
                "model": model,
                "total": total,
                "origin_functional": agg["origin_functional"],
                "patch_functional": agg["patch_functional"],
                "rag_skeleton_functional": agg["rag_skeleton_functional"],
                "origin_functional_rate": rate(agg["origin_functional"], total),
                "patch_functional_rate": rate(agg["patch_functional"], total),
                "rag_skeleton_functional_rate": rate(agg["rag_skeleton_functional"], total),
                "patch_gain_over_origin": agg["patch_gain_over_origin"],
                "rag_gain_over_patch": agg["rag_gain_over_patch"],
                "rag_gain_over_origin": agg["rag_gain_over_origin"],
                "residual_functional_failures": agg["residual_functional_failures"],
                "family_label_counts": json.dumps(label_counts, ensure_ascii=False, sort_keys=True),
            }
        )
    return detail_rows, summary_rows


def parse_overview_from_inspect(path: Path, model_label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if '"kind":"table"' not in line or '"sheet":"Overview"' not in line:
                continue
            obj = json.loads(line)
            values = obj.get("values") or []
            if len(values) < 4:
                continue
            header = values[2]
            for item in values[3:]:
                if not item or not item[0]:
                    continue
                record = dict(zip(header, item))
                rows.append(
                    {
                        "model": model_label,
                        "dataset": record.get("Dataset", ""),
                        "problems": record.get("Problems", 0),
                        "syntax_pass": record.get("Syntax Pass", 0),
                        "compile_pass": record.get("Compile Pass", 0),
                        "functional_pass": record.get("Functional Pass", 0),
                        "syntax_rate": round(float(record.get("Syntax Rate") or 0), 3),
                        "compile_rate": round(float(record.get("Compile Rate") or 0), 3),
                        "functional_rate": round(float(record.get("Functional Rate") or 0), 3),
                        "source": path.name,
                    }
                )
            break
    return rows


def write_markdown(path: Path, detail: list[dict[str, Any]], summary: list[dict[str, Any]], baseline: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top_gains = sorted(detail, key=lambda r: (r["rag_gain_over_patch"], r["rag_gain_over_origin"]), reverse=True)[:12]
    residual = sorted(detail, key=lambda r: (r["residual_functional_failures"], -r["rag_skeleton_functional"]), reverse=True)[:12]

    lines = [
        "# V6.2 Family-Level 增益与失败分析",
        "",
        "## 1. V6.2 总体增益摘要",
        "",
        "| dataset | model | origin func | patch func | rag+skeleton func | patch gain | rag gain over patch | residual fails |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['dataset']} | {row['model']} | {row['origin_functional']}/{row['total']} | "
            f"{row['patch_functional']}/{row['total']} | {row['rag_skeleton_functional']}/{row['total']} | "
            f"{row['patch_gain_over_origin']} | {row['rag_gain_over_patch']} | {row['residual_functional_failures']} |"
        )

    lines += [
        "",
        "## 2. RAG+Skeleton 增益最大的 family",
        "",
        "| dataset | model | family | total | patch func | rag+skeleton func | gain over patch | diagnosis |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in top_gains:
        lines.append(
            f"| {row['dataset']} | {row['model']} | {row['family']} | {row['total']} | "
            f"{row['patch_functional']} | {row['rag_skeleton_functional']} | {row['rag_gain_over_patch']} | {row['diagnosis_label']} |"
        )

    lines += [
        "",
        "## 3. RAG+Skeleton 后仍然失败集中的 family",
        "",
        "| dataset | model | family | total | rag+skeleton func | residual fails | diagnosis |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in residual:
        lines.append(
            f"| {row['dataset']} | {row['model']} | {row['family']} | {row['total']} | "
            f"{row['rag_skeleton_functional']} | {row['residual_functional_failures']} | {row['diagnosis_label']} |"
        )

    if baseline:
        lines += [
            "",
            "## 4. 通用 VLM Pass@1 baseline 索引",
            "",
            "| model | dataset | problems | syntax | compile | functional | syntax_rate | functional_rate |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for row in baseline:
            lines.append(
                f"| {row['model']} | {row['dataset']} | {row['problems']} | {row['syntax_pass']} | "
                f"{row['compile_pass']} | {row['functional_pass']} | {row['syntax_rate']} | {row['functional_rate']} |"
            )

    lines += [
        "",
        "## 5. 论文可用结论",
        "",
        "- V6.2 的主要价值不是普通反思，而是把 CAD error、Error Library RAG、Skeleton 硬约束和 patch/gate 串成结构化修复流程。",
        "- Llama 上 `reflect_patch` 增益很弱，但 `reflect_rag_skeleton` 显著提升，说明领域约束是关键变量。",
        "- Qwen 上普通 `reflect_patch` 已经较强，因此 RAG+Skeleton 的相对增益被压缩；但最终 functional pass 仍有提升。",
        "- persistent failure families 应作为 case study 和 future work，而不是继续用小规模 LoRA 强行追分。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--qwen25-inspect", default="")
    parser.add_argument("--llava-inspect", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = Path(args.output_dir).expanduser().resolve()
    rows = read_csv(Path(args.family_csv).expanduser().resolve())
    detail, summary = build_family_tables(rows)

    detail_fields = [
        "dataset",
        "model",
        "family",
        "total",
        "origin_syntax",
        "patch_syntax",
        "rag_skeleton_syntax",
        "origin_functional",
        "patch_functional",
        "rag_skeleton_functional",
        "origin_functional_rate",
        "patch_functional_rate",
        "rag_skeleton_functional_rate",
        "patch_gain_over_origin",
        "rag_gain_over_patch",
        "rag_gain_over_origin",
        "residual_functional_failures",
        "diagnosis_label",
    ]
    summary_fields = [
        "dataset",
        "model",
        "total",
        "origin_functional",
        "patch_functional",
        "rag_skeleton_functional",
        "origin_functional_rate",
        "patch_functional_rate",
        "rag_skeleton_functional_rate",
        "patch_gain_over_origin",
        "rag_gain_over_patch",
        "rag_gain_over_origin",
        "residual_functional_failures",
        "family_label_counts",
    ]

    baseline = []
    if args.qwen25_inspect:
        baseline.extend(parse_overview_from_inspect(Path(args.qwen25_inspect), "Qwen2.5-VL-7B-Instruct"))
    if args.llava_inspect:
        baseline.extend(parse_overview_from_inspect(Path(args.llava_inspect), "LLaVA-NeXT-Mistral-7B"))

    write_csv(out / "v6_2_family_gain_failure_detail.csv", detail, detail_fields)
    write_csv(out / "v6_2_family_gain_failure_summary.csv", summary, summary_fields)
    if baseline:
        write_csv(
            out / "general_vlm_baseline_overview.csv",
            baseline,
            [
                "model",
                "dataset",
                "problems",
                "syntax_pass",
                "compile_pass",
                "functional_pass",
                "syntax_rate",
                "compile_rate",
                "functional_rate",
                "source",
            ],
        )
    write_markdown(out / "V6_2_family_gain_failure_analysis.md", detail, summary, baseline)

    print(f"detail={out / 'v6_2_family_gain_failure_detail.csv'}")
    print(f"summary={out / 'v6_2_family_gain_failure_summary.csv'}")
    if baseline:
        print(f"baseline={out / 'general_vlm_baseline_overview.csv'}")
    print(f"markdown={out / 'V6_2_family_gain_failure_analysis.md'}")


if __name__ == "__main__":
    main()
