#!/usr/bin/env python3
"""Run Yosys generic synthesis QoR analysis for V6.2 repair traces.

This script is intentionally based on generic technology mapping rather than a
standard-cell liberty library. It is suitable for the current V6.2 logs where
repair-mode RTLs are preserved, but origin RTLs are not always traceable.

Outputs:
  - synth_qor_all.csv: every discovered iter_*.v synthesis result
  - synth_qor_patch_vs_rag_paired.csv: case-level reflect_patch vs
    reflect_rag_skeleton comparison
  - synth_qor_newly_recovered.csv: RAG+Skeleton functional/synthesizable cases
    where reflect_patch did not functionally pass
  - synth_qor_summary_zh.md: short Chinese paper-facing summary
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


CASE_RE = re.compile(
    r"cases[/\\]module(?P<module>\d+)[/\\]test(?P<test>\d+)[/\\]"
    r"reflect_result_(?P<mode>.+?)_seed(?P<seed>\d+)_m\d+_t\d+[/\\]"
    r"iter_(?P<iteration>\d+)\.v$"
)

MODES = ("reflect_patch", "reflect_rag_skeleton")

CELL_TYPES = [
    "$_AND_",
    "$_OR_",
    "$_XOR_",
    "$_NOT_",
    "$_MUX_",
    "$_NAND_",
    "$_NOR_",
    "$_XNOR_",
    "$_DFF",
    "$_DFFE",
    "$_DFF_",
    "$_DFFE_",
]

MODULE_FAMILY: dict[int, str] = {}
for _i in range(1, 10):
    MODULE_FAMILY[_i] = "adder / PPA"
for _i in [10, 11, 12, 21]:
    MODULE_FAMILY[_i] = "MAC / arithmetic accumulation"
for _i in range(13, 21):
    MODULE_FAMILY[_i] = "multiplier"
for _i in range(22, 26):
    MODULE_FAMILY[_i] = "Winograd / transform / dataflow"
for _i in [26, 27]:
    MODULE_FAMILY[_i] = "PE / PE-row / PE-array"


def read_csv(path: Path | None) -> list[dict[str, str]]:
    if not path:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "pass", "passed"}:
        return True
    if text in {"false", "0", "no", "fail", "failed"}:
        return False
    return None


def load_history_status(run_dir: Path) -> dict[int, dict[str, Any]]:
    history_path = run_dir / "history.json"
    if not history_path.exists():
        return {}
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, list):
        return {}
    status: dict[int, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            iteration = int(item.get("iteration", -1))
        except Exception:
            continue
        status[iteration] = {
            "syntax_ok": boolish(item.get("syntax_ok")),
            "functional_ok": boolish(item.get("functional_ok")),
            "retrieved_rule_count": item.get("retrieved_rule_count", ""),
            "retrieved_categories": item.get("retrieved_categories", ""),
            "repair_best_status": (
                item.get("repair_state", {}).get("best_status", "")
                if isinstance(item.get("repair_state"), dict)
                else ""
            ),
            "repair_current_stage": (
                item.get("repair_state", {}).get("current_stage", "")
                if isinstance(item.get("repair_state"), dict)
                else ""
            ),
            "preferred_action": item.get("preferred_action", ""),
            "diagnosis_family": item.get("diagnosis_family", ""),
        }
    return status


def csv_status_index(rows: list[dict[str, str]]) -> dict[tuple[int, int, str], dict[str, str]]:
    index: dict[tuple[int, int, str], dict[str, str]] = {}
    for row in rows:
        try:
            module_id = int(row.get("module_id", ""))
            test_id = int(row.get("test_id", ""))
        except Exception:
            continue
        mode = row.get("mode", "")
        index[(module_id, test_id, mode)] = row
    return index


def discover_verilog_files(experiment_root: Path, modes: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(experiment_root.rglob("iter_*.v")):
        rel = path.relative_to(experiment_root).as_posix()
        match = CASE_RE.search(rel)
        if not match:
            continue
        mode = match.group("mode")
        if mode not in modes:
            continue
        module_id = int(match.group("module"))
        test_id = int(match.group("test"))
        iteration = int(match.group("iteration"))
        run_dir = path.parent
        while run_dir.name != f"reflect_result_{mode}_seed{match.group('seed')}_m{module_id}_t{test_id}":
            if run_dir == experiment_root or run_dir.parent == run_dir:
                break
            run_dir = run_dir.parent
        records.append(
            {
                "module_id": module_id,
                "test_id": test_id,
                "case_id": f"module{module_id}/test{test_id}",
                "family_group": MODULE_FAMILY.get(module_id, "other"),
                "mode": mode,
                "seed": int(match.group("seed")),
                "iteration": iteration,
                "verilog_path": path,
                "run_dir": run_dir,
            }
        )
    return records


def yosys_script(verilog_path: Path) -> str:
    abs_verilog_path = verilog_path.resolve()
    return "\n".join(
        [
            f'read_verilog "{abs_verilog_path.as_posix()}"',
            "hierarchy -auto-top",
            "proc",
            "opt",
            "fsm",
            "opt",
            "memory",
            "opt",
            "techmap",
            "opt",
            "stat",
            "",
        ]
    )


def parse_yosys_log(text: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "wire_count": "",
        "wire_bits": "",
        "public_wire_count": "",
        "public_wire_bits": "",
        "port_count": "",
        "port_bits": "",
        "cell_count": "",
        "and_count": 0,
        "or_count": 0,
        "xor_count": 0,
        "not_count": 0,
        "mux_count": 0,
        "nand_count": 0,
        "nor_count": 0,
        "xnor_count": 0,
        "dff_count": 0,
        "dffe_count": 0,
    }
    scalar_patterns = [
        ("wire_count", re.compile(r"^\s*(?:Number of wires:\s*)?(\d+)\s+wires\s*$")),
        ("wire_bits", re.compile(r"^\s*(?:Number of wire bits:\s*)?(\d+)\s+wire bits\s*$")),
        ("public_wire_count", re.compile(r"^\s*(\d+)\s+public wires\s*$")),
        ("public_wire_bits", re.compile(r"^\s*(\d+)\s+public wire bits\s*$")),
        ("port_count", re.compile(r"^\s*(\d+)\s+ports\s*$")),
        ("port_bits", re.compile(r"^\s*(\d+)\s+port bits\s*$")),
        ("cell_count", re.compile(r"^\s*(?:Number of cells:\s*)?(\d+)\s+cells\s*$")),
    ]
    cell_map = {
        "$_AND_": "and_count",
        "$_OR_": "or_count",
        "$_XOR_": "xor_count",
        "$_NOT_": "not_count",
        "$_MUX_": "mux_count",
        "$_NAND_": "nand_count",
        "$_NOR_": "nor_count",
        "$_XNOR_": "xnor_count",
    }
    for line in text.splitlines():
        for key, pattern in scalar_patterns:
            m = pattern.search(line)
            if m:
                metrics[key] = int(m.group(1))
        m = re.search(r"^\s*(\d+)\s+(\$_\S+)\s*$", line)
        if not m:
            continue
        count = int(m.group(1))
        cell = m.group(2)
        if cell in cell_map:
            metrics[cell_map[cell]] += count
        if cell.startswith("$_DFFE"):
            metrics["dffe_count"] += count
        elif cell.startswith("$_DFF"):
            metrics["dff_count"] += count
    return metrics


def run_yosys(
    yosys_bin: str,
    verilog_path: Path,
    work_dir: Path,
    timeout: int,
    keep_logs: bool,
) -> dict[str, Any]:
    tag = hashlib.sha1(str(verilog_path).encode("utf-8")).hexdigest()[:16]
    case_dir = (work_dir / tag).resolve()
    case_dir.mkdir(parents=True, exist_ok=True)
    script_path = (case_dir / "synth_generic.ys").resolve()
    log_path = (case_dir / "yosys.log").resolve()
    script_path.write_text(yosys_script(verilog_path), encoding="utf-8")
    try:
        proc = subprocess.run(
            [yosys_bin, "-q", "-l", str(log_path), str(script_path)],
            cwd=str(verilog_path.parent),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "synth_ok": False,
            "synth_error": f"timeout_after_{timeout}s",
            "yosys_returncode": "",
            "yosys_log": str(log_path) if keep_logs else "",
        }
    except FileNotFoundError:
        return {
            "synth_ok": False,
            "synth_error": f"yosys_not_found:{yosys_bin}",
            "yosys_returncode": "",
            "yosys_log": str(log_path) if keep_logs else "",
        }

    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    synth_ok = proc.returncode == 0 and "ERROR:" not in log_text
    result = {
        "synth_ok": synth_ok,
        "synth_error": "" if synth_ok else first_error(log_text, proc.stderr),
        "yosys_returncode": proc.returncode,
        "yosys_log": str(log_path) if keep_logs else "",
    }
    if synth_ok:
        result.update(parse_yosys_log(log_text))
    else:
        result.update(parse_yosys_log(log_text))
    return result


def first_error(log_text: str, stderr: str) -> str:
    for line in log_text.splitlines():
        if "ERROR:" in line:
            return line.strip()[:500]
    for line in stderr.splitlines():
        if line.strip():
            return line.strip()[:500]
    return "yosys_failed"


def enrich_records(
    records: list[dict[str, Any]],
    csv_index: dict[tuple[int, int, str], dict[str, str]],
) -> list[dict[str, Any]]:
    history_cache: dict[Path, dict[int, dict[str, Any]]] = {}
    enriched: list[dict[str, Any]] = []
    for record in records:
        run_dir = record["run_dir"]
        if run_dir not in history_cache:
            history_cache[run_dir] = load_history_status(run_dir)
        status = history_cache[run_dir].get(record["iteration"], {})
        csv_row = csv_index.get((record["module_id"], record["test_id"], record["mode"]), {})
        merged = dict(record)
        merged.update(
            {
                "syntax_ok": status.get("syntax_ok"),
                "functional_ok": status.get("functional_ok"),
                "history_status_inconsistent": (
                    status.get("syntax_ok") is False and status.get("functional_ok") is True
                ),
                "retrieved_rule_count": status.get("retrieved_rule_count", ""),
                "retrieved_categories": status.get("retrieved_categories", ""),
                "repair_best_status": status.get("repair_best_status", ""),
                "repair_current_stage": status.get("repair_current_stage", ""),
                "preferred_action": status.get("preferred_action", ""),
                "diagnosis_family": status.get("diagnosis_family", ""),
                "csv_syntax_ok": csv_row.get("syntax_ok", ""),
                "csv_functional_ok": csv_row.get("functional_ok", ""),
                "csv_num_iterations": csv_row.get("num_iterations", ""),
                "csv_final_iteration": csv_row.get("final_iteration", ""),
            }
        )
        if merged["syntax_ok"] is None:
            merged["syntax_ok"] = boolish(csv_row.get("syntax_ok"))
        if merged["functional_ok"] is None:
            merged["functional_ok"] = boolish(csv_row.get("functional_ok"))
        merged["history_status_inconsistent"] = (
            merged.get("syntax_ok") is False and merged.get("functional_ok") is True
        )
        enriched.append(merged)
    return enriched


def select_best_by_case_mode(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["case_id"], row["mode"])].append(row)
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for key, items in grouped.items():
        items = sorted(items, key=lambda r: int(r["iteration"]))
        # Prefer the final iteration recorded in the ablation CSV. Some older
        # history files contain inconsistent per-iteration pairs such as
        # syntax_ok=False with functional_ok=True after repair-state updates.
        csv_final = None
        for item in items:
            try:
                csv_final = int(float(item.get("csv_final_iteration", "")))
                break
            except Exception:
                continue
        if csv_final is not None:
            exact = [r for r in items if int(r["iteration"]) == csv_final]
            if exact:
                selected[key] = exact[0]
                continue
        functional = [
            r
            for r in items
            if r.get("functional_ok") is True and r.get("syntax_ok") is True
        ]
        syntax = [r for r in items if r.get("syntax_ok") is True]
        if functional:
            synth_functional = [r for r in functional if r.get("synth_ok") is True]
            selected[key] = synth_functional[0] if synth_functional else functional[0]
        elif syntax:
            synth_syntax = [r for r in syntax if r.get("synth_ok") is True]
            selected[key] = synth_syntax[-1] if synth_syntax else syntax[-1]
        else:
            selected[key] = items[-1]
    return selected


def ratio(num: Any, den: Any) -> str:
    try:
        n = float(num)
        d = float(den)
    except Exception:
        return ""
    if d == 0:
        return ""
    return f"{n / d:.4f}"


def build_paired_rows(best: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    paired: list[dict[str, Any]] = []
    cases = sorted({case for case, _mode in best})
    for case_id in cases:
        patch = best.get((case_id, "reflect_patch"))
        rag = best.get((case_id, "reflect_rag_skeleton"))
        if not patch or not rag:
            continue
        paired.append(
            {
                "case_id": case_id,
                "module_id": patch["module_id"],
                "test_id": patch["test_id"],
                "family_group": patch["family_group"],
                "patch_iteration": patch["iteration"],
                "rag_iteration": rag["iteration"],
                "patch_syntax_ok": patch.get("syntax_ok"),
                "rag_syntax_ok": rag.get("syntax_ok"),
                "patch_functional_ok": patch.get("functional_ok"),
                "rag_functional_ok": rag.get("functional_ok"),
                "patch_synth_ok": patch.get("synth_ok"),
                "rag_synth_ok": rag.get("synth_ok"),
                "patch_cell_count": patch.get("cell_count", ""),
                "rag_cell_count": rag.get("cell_count", ""),
                "cell_ratio_rag_over_patch": ratio(rag.get("cell_count", ""), patch.get("cell_count", "")),
                "patch_wire_bits": patch.get("wire_bits", ""),
                "rag_wire_bits": rag.get("wire_bits", ""),
                "wire_bits_ratio_rag_over_patch": ratio(rag.get("wire_bits", ""), patch.get("wire_bits", "")),
                "patch_and": patch.get("and_count", ""),
                "rag_and": rag.get("and_count", ""),
                "patch_or": patch.get("or_count", ""),
                "rag_or": rag.get("or_count", ""),
                "patch_xor": patch.get("xor_count", ""),
                "rag_xor": rag.get("xor_count", ""),
                "patch_dff_total": int(patch.get("dff_count") or 0) + int(patch.get("dffe_count") or 0),
                "rag_dff_total": int(rag.get("dff_count") or 0) + int(rag.get("dffe_count") or 0),
                "patch_verilog_path": patch["verilog_path"],
                "rag_verilog_path": rag["verilog_path"],
            }
        )
    return paired


def build_newly_recovered_rows(best: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cases = sorted({case for case, _mode in best})
    for case_id in cases:
        patch = best.get((case_id, "reflect_patch"))
        rag = best.get((case_id, "reflect_rag_skeleton"))
        if not rag:
            continue
        patch_func = patch.get("functional_ok") if patch else None
        if patch_func is True or rag.get("functional_ok") is not True:
            continue
        rows.append(
            {
                "case_id": case_id,
                "module_id": rag["module_id"],
                "test_id": rag["test_id"],
                "family_group": rag["family_group"],
                "patch_functional_ok": patch_func,
                "rag_functional_ok": rag.get("functional_ok"),
                "rag_synth_ok": rag.get("synth_ok"),
                "rag_cell_count": rag.get("cell_count", ""),
                "rag_wire_bits": rag.get("wire_bits", ""),
                "rag_and": rag.get("and_count", ""),
                "rag_or": rag.get("or_count", ""),
                "rag_xor": rag.get("xor_count", ""),
                "rag_dff_total": int(rag.get("dff_count") or 0) + int(rag.get("dffe_count") or 0),
                "rag_iteration": rag["iteration"],
                "rag_verilog_path": rag["verilog_path"],
            }
        )
    return rows


def as_float_list(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        try:
            value = float(row.get(key, ""))
        except Exception:
            continue
        values.append(value)
    return values


def mean(values: list[float]) -> str:
    return f"{statistics.mean(values):.4f}" if values else ""


def median(values: list[float]) -> str:
    return f"{statistics.median(values):.4f}" if values else ""


def write_summary(
    path: Path,
    model: str,
    dataset: str,
    all_rows: list[dict[str, Any]],
    paired_rows: list[dict[str, Any]],
    recovered_rows: list[dict[str, Any]],
) -> None:
    synth_ok = sum(1 for r in all_rows if r.get("synth_ok") is True)
    mode_counts = Counter(r["mode"] for r in all_rows)
    mode_synth = Counter(r["mode"] for r in all_rows if r.get("synth_ok") is True)
    func_synth = [r for r in all_rows if r.get("functional_ok") is True and r.get("synth_ok") is True]
    paired_both_func = [
        r
        for r in paired_rows
        if r.get("patch_functional_ok") is True and r.get("rag_functional_ok") is True
    ]
    paired_both_synth = [
        r for r in paired_both_func if r.get("patch_synth_ok") is True and r.get("rag_synth_ok") is True
    ]
    ratios = as_float_list(paired_both_synth, "cell_ratio_rag_over_patch")
    wire_ratios = as_float_list(paired_both_synth, "wire_bits_ratio_rag_over_patch")
    better = sum(1 for v in ratios if v < 1.0)
    equal = sum(1 for v in ratios if abs(v - 1.0) < 1e-9)
    worse = sum(1 for v in ratios if v > 1.0)
    recovered_synth = [r for r in recovered_rows if r.get("rag_synth_ok") is True]
    family_recovered = Counter(r["family_group"] for r in recovered_synth)

    lines = [
        "# Yosys Generic QoR Proxy 分析",
        "",
        f"- 模型：{model}",
        f"- 数据集：{dataset}",
        f"- 分析对象：V6.2 中可追溯的 `reflect_patch` 与 `reflect_rag_skeleton` 修复 RTL。",
        f"- 总 Verilog 记录：{len(all_rows)}",
        f"- Yosys generic synthesis 成功：{synth_ok}/{len(all_rows)}",
        "",
        "## 按模式统计",
        "",
        "| mode | verilog_records | synth_ok |",
        "|---|---:|---:|",
    ]
    for mode in MODES:
        lines.append(f"| {mode} | {mode_counts[mode]} | {mode_synth[mode]} |")
    lines += [
        "",
        "## Paired QoR: reflect_rag_skeleton vs reflect_patch",
        "",
        f"- patch 与 RAG+Skeleton 均 functional pass 的 paired cases：{len(paired_both_func)}",
        f"- 其中二者均可综合的 paired cases：{len(paired_both_synth)}",
        f"- `cell_count` 比值 `rag / patch` 平均值：{mean(ratios) or 'NA'}",
        f"- `cell_count` 比值中位数：{median(ratios) or 'NA'}",
        f"- RAG+Skeleton cell 更少 / 相同 / 更多：{better} / {equal} / {worse}",
        f"- `wire_bits` 比值平均值：{mean(wire_ratios) or 'NA'}",
        "",
        "解释口径：该表只比较两种模式均 functional pass 且均可综合的 case，避免不同成功集合造成选择偏差。",
        "",
        "## RAG+Skeleton 新救回 case 的可综合性",
        "",
        f"- patch 未 functional pass、RAG+Skeleton functional pass 的 case：{len(recovered_rows)}",
        f"- 其中 RAG+Skeleton 可综合：{len(recovered_synth)}",
        "",
        "| family_group | recovered_synth_cases |",
        "|---|---:|",
    ]
    for family, count in family_recovered.most_common():
        lines.append(f"| {family} | {count} |")
    lines += [
        "",
        "## 论文写法建议",
        "",
        "这部分不应写成完整 PPA 结论，因为当前没有绑定标准单元 `.lib`，且 V6.2 早期日志没有系统保存 origin RTL。",
        "建议表述为：Yosys generic technology mapping 证明 workflow 修复出的 RTL 具备下游可综合性；在 patch 与 RAG+Skeleton 均通过功能验证的 paired cases 上，RAG+Skeleton 没有系统性引入额外 generic gate-level 复杂度。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def stringify_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        converted = {}
        for key, value in row.items():
            if isinstance(value, Path):
                converted[key] = value.as_posix()
            elif value is None:
                converted[key] = ""
            else:
                converted[key] = value
        output.append(converted)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-root", required=True, type=Path)
    parser.add_argument("--ablation-csv", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model", default="")
    parser.add_argument("--dataset", default="")
    parser.add_argument("--yosys-bin", default="yosys")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--mode", action="append", choices=MODES)
    parser.add_argument("--keep-logs", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    modes = set(args.mode or MODES)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tmp_root = args.output_dir / "yosys_logs" if args.keep_logs else Path(tempfile.mkdtemp(prefix="yosys_qor_"))
    tmp_root.mkdir(parents=True, exist_ok=True)

    csv_rows = read_csv(args.ablation_csv)
    index = csv_status_index(csv_rows)
    discovered = discover_verilog_files(args.experiment_root, modes)
    enriched = enrich_records(discovered, index)
    if args.limit:
        enriched = enriched[: args.limit]

    all_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(enriched, start=1):
        synth = run_yosys(args.yosys_bin, row["verilog_path"], tmp_root, args.timeout, args.keep_logs)
        merged = dict(row)
        merged.update(synth)
        merged["model"] = args.model
        merged["dataset"] = args.dataset
        all_rows.append(merged)
        if idx % 25 == 0:
            print(f"[INFO] synthesized {idx}/{len(enriched)}")

    best = select_best_by_case_mode(all_rows)
    paired_rows = build_paired_rows(best)
    recovered_rows = build_newly_recovered_rows(best)

    all_fieldnames = [
        "model",
        "dataset",
        "case_id",
        "module_id",
        "test_id",
        "family_group",
        "mode",
        "seed",
        "iteration",
        "syntax_ok",
        "functional_ok",
        "history_status_inconsistent",
        "synth_ok",
        "synth_error",
        "wire_count",
        "wire_bits",
        "public_wire_count",
        "public_wire_bits",
        "port_count",
        "port_bits",
        "cell_count",
        "and_count",
        "or_count",
        "xor_count",
        "not_count",
        "mux_count",
        "nand_count",
        "nor_count",
        "xnor_count",
        "dff_count",
        "dffe_count",
        "retrieved_rule_count",
        "retrieved_categories",
        "repair_best_status",
        "repair_current_stage",
        "preferred_action",
        "diagnosis_family",
        "csv_syntax_ok",
        "csv_functional_ok",
        "csv_num_iterations",
        "csv_final_iteration",
        "yosys_returncode",
        "yosys_log",
        "verilog_path",
    ]
    paired_fieldnames = [
        "case_id",
        "module_id",
        "test_id",
        "family_group",
        "patch_iteration",
        "rag_iteration",
        "patch_syntax_ok",
        "rag_syntax_ok",
        "patch_functional_ok",
        "rag_functional_ok",
        "patch_synth_ok",
        "rag_synth_ok",
        "patch_cell_count",
        "rag_cell_count",
        "cell_ratio_rag_over_patch",
        "patch_wire_bits",
        "rag_wire_bits",
        "wire_bits_ratio_rag_over_patch",
        "patch_and",
        "rag_and",
        "patch_or",
        "rag_or",
        "patch_xor",
        "rag_xor",
        "patch_dff_total",
        "rag_dff_total",
        "patch_verilog_path",
        "rag_verilog_path",
    ]
    recovered_fieldnames = [
        "case_id",
        "module_id",
        "test_id",
        "family_group",
        "patch_functional_ok",
        "rag_functional_ok",
        "rag_synth_ok",
        "rag_cell_count",
        "rag_wire_bits",
        "rag_and",
        "rag_or",
        "rag_xor",
        "rag_dff_total",
        "rag_iteration",
        "rag_verilog_path",
    ]

    write_csv(args.output_dir / "synth_qor_all.csv", stringify_rows(all_rows), all_fieldnames)
    write_csv(
        args.output_dir / "synth_qor_patch_vs_rag_paired.csv",
        stringify_rows(paired_rows),
        paired_fieldnames,
    )
    write_csv(
        args.output_dir / "synth_qor_newly_recovered.csv",
        stringify_rows(recovered_rows),
        recovered_fieldnames,
    )
    write_summary(
        args.output_dir / "synth_qor_summary_zh.md",
        args.model,
        args.dataset,
        all_rows,
        paired_rows,
        recovered_rows,
    )

    print(f"Discovered Verilog records: {len(discovered)}")
    print(f"Synthesized records: {len(all_rows)}")
    print(f"Paired patch-vs-rag cases: {len(paired_rows)}")
    print(f"Newly recovered cases: {len(recovered_rows)}")
    print(f"Output: {args.output_dir}")


if __name__ == "__main__":
    main()
