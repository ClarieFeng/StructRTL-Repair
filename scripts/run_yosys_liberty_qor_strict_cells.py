#!/usr/bin/env python3
"""Run strict standard-cell mapped QoR analysis from generic QoR target CSVs.

This script is the Nangate45/SkyWater extension of run_yosys_generic_qor.py.
It intentionally consumes the already-filtered generic QoR outputs so that we
do not run expensive ABC mapping on every intermediate repair iteration.

Compared with run_yosys_liberty_qor.py, this strict variant avoids the fast
ABC script that can leave $lut cells in the mapped netlist. It is intended for
follow-up area proxy retries where a cell-level Liberty area is required.

Recommended inputs:
  - synth_qor_patch_vs_rag_paired.csv
  - synth_qor_newly_recovered.csv

Outputs:
  - liberty_qor_all.csv
  - liberty_qor_paired_area.csv
  - liberty_qor_newly_recovered_area.csv
  - liberty_qor_summary_zh.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import statistics
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any


CELL_LINE_RE = re.compile(r"^\s*(?P<count>\d+)\s+(?P<area>[0-9.]+)\s+(?P<cell>\S+)\s*$")
CHIP_AREA_RE = re.compile(r"Chip area for module '\\(?P<module>[^']+)':\s*(?P<area>[0-9.]+)")
SEQ_AREA_RE = re.compile(
    r"of which used for sequential elements:\s*(?P<area>[0-9.]+)\s*\((?P<ratio>[0-9.]+)%\)"
)


def read_csv(path: Path | None) -> list[dict[str, str]]:
    if not path or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "pass"}


def ratio(num: Any, den: Any) -> str:
    try:
        n = float(num)
        d = float(den)
    except Exception:
        return ""
    if d == 0:
        return ""
    return f"{n / d:.6f}"


def yosys_script(verilog_path: Path, liberty_path: Path, fast_abc: bool) -> str:
    abc_line = f'abc -liberty "{liberty_path.as_posix()}" -D 1000'
    if fast_abc:
        abc_line = f'abc -liberty "{liberty_path.as_posix()}" -D 1000'
    return "\n".join(
        [
            f'read_verilog "{verilog_path.resolve().as_posix()}"',
            "hierarchy -auto-top",
            "proc",
            "opt",
            "fsm",
            "opt",
            "memory",
            "opt",
            "techmap",
            "opt",
            f'dfflibmap -liberty "{liberty_path.as_posix()}"',
            abc_line,
            "clean -purge",
            "opt_clean -purge",
            f'stat -liberty "{liberty_path.as_posix()}"',
            "",
        ]
    )


def first_error(log_text: str, stderr: str) -> str:
    if "Area for cell type $lut is unknown" in log_text:
        return "liberty_area_missing_lut_cells"
    for line in log_text.splitlines():
        if "ERROR:" in line:
            return line.strip()[:500]
    for line in stderr.splitlines():
        if line.strip():
            return line.strip()[:500]
    return "yosys_liberty_failed"


def parse_log(log_text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "top_module": "",
        "mapped_cell_count": "",
        "chip_area": "",
        "sequential_area": "",
        "sequential_area_ratio_percent": "",
        "mapped_cell_histogram": "",
        "dff_cells": 0,
        "xor_cells": 0,
        "xnor_cells": 0,
        "inv_cells": 0,
        "buf_cells": 0,
        "mux_cells": 0,
    }
    histogram: Counter[str] = Counter()
    chip_area = ""
    top_module = ""
    for line in log_text.splitlines():
        m = CHIP_AREA_RE.search(line)
        if m:
            top_module = m.group("module")
            chip_area = m.group("area")
        m = SEQ_AREA_RE.search(line)
        if m:
            result["sequential_area"] = m.group("area")
            result["sequential_area_ratio_percent"] = m.group("ratio")
        m = CELL_LINE_RE.search(line)
        if not m:
            continue
        count = int(m.group("count"))
        cell = m.group("cell")
        histogram[cell] += count
    result["top_module"] = top_module
    result["chip_area"] = chip_area
    result["mapped_cell_count"] = sum(histogram.values()) if histogram else ""
    result["mapped_cell_histogram"] = ";".join(f"{k}:{v}" for k, v in sorted(histogram.items()))
    for cell, count in histogram.items():
        upper = cell.upper()
        if upper.startswith("DFF"):
            result["dff_cells"] += count
        elif upper.startswith("XOR"):
            result["xor_cells"] += count
        elif upper.startswith("XNOR"):
            result["xnor_cells"] += count
        elif upper.startswith("INV"):
            result["inv_cells"] += count
        elif upper.startswith("BUF"):
            result["buf_cells"] += count
        elif upper.startswith("MUX"):
            result["mux_cells"] += count
    return result


def run_yosys_liberty(
    yosys_bin: str,
    liberty_path: Path,
    verilog_path: Path,
    work_dir: Path,
    timeout: int,
    fast_abc: bool,
    keep_logs: bool,
) -> dict[str, Any]:
    tag = hashlib.sha1(f"{verilog_path}|{liberty_path}|{fast_abc}".encode("utf-8")).hexdigest()[:16]
    case_dir = (work_dir / tag).resolve()
    case_dir.mkdir(parents=True, exist_ok=True)
    script_path = (case_dir / "synth_liberty.ys").resolve()
    log_path = (case_dir / "yosys_liberty.log").resolve()
    script_path.write_text(yosys_script(verilog_path, liberty_path.resolve(), fast_abc), encoding="utf-8")
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [yosys_bin, "-q", "-l", str(log_path), str(script_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "liberty_synth_ok": False,
            "liberty_synth_error": f"timeout_after_{timeout}s",
            "elapsed_seconds": f"{time.perf_counter() - started:.3f}",
            "yosys_log": str(log_path) if keep_logs else "",
        }
    except FileNotFoundError:
        return {
            "liberty_synth_ok": False,
            "liberty_synth_error": f"yosys_not_found:{yosys_bin}",
            "elapsed_seconds": f"{time.perf_counter() - started:.3f}",
            "yosys_log": str(log_path) if keep_logs else "",
        }
    elapsed = time.perf_counter() - started
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    parsed = parse_log(log_text)
    ok = proc.returncode == 0 and "ERROR:" not in log_text and bool(parsed.get("chip_area"))
    result = {
        "liberty_synth_ok": ok,
        "liberty_synth_error": "" if ok else first_error(log_text, proc.stderr),
        "yosys_returncode": proc.returncode,
        "elapsed_seconds": f"{elapsed:.3f}",
        "yosys_log": str(log_path) if keep_logs else "",
    }
    result.update(parsed)
    return result


def collect_targets(
    paired_rows: list[dict[str, str]],
    recovered_rows: list[dict[str, str]],
    only_newly_recovered: bool,
    only_paired: bool,
) -> list[dict[str, Any]]:
    targets: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not only_newly_recovered:
        for row in paired_rows:
            if not (
                truthy(row.get("patch_functional_ok"))
                and truthy(row.get("rag_functional_ok"))
                and truthy(row.get("patch_synth_ok"))
                and truthy(row.get("rag_synth_ok"))
            ):
                continue
            for mode, path_key in [
                ("reflect_patch", "patch_verilog_path"),
                ("reflect_rag_skeleton", "rag_verilog_path"),
            ]:
                key = (row["case_id"], mode, "paired")
                targets[key] = {
                    "target_group": "paired",
                    "case_id": row["case_id"],
                    "module_id": row.get("module_id", ""),
                    "test_id": row.get("test_id", ""),
                    "family_group": row.get("family_group", ""),
                    "mode": mode,
                    "verilog_path": row.get(path_key, ""),
                }
    if not only_paired:
        for row in recovered_rows:
            if not (truthy(row.get("rag_functional_ok")) and truthy(row.get("rag_synth_ok"))):
                continue
            key = (row["case_id"], "reflect_rag_skeleton", "newly_recovered")
            targets[key] = {
                "target_group": "newly_recovered",
                "case_id": row["case_id"],
                "module_id": row.get("module_id", ""),
                "test_id": row.get("test_id", ""),
                "family_group": row.get("family_group", ""),
                "mode": "reflect_rag_skeleton",
                "verilog_path": row.get("rag_verilog_path", ""),
            }
    return list(targets.values())


def collect_retry_targets(rows: list[dict[str, str]], error_contains: str) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    needle = error_contains.strip().lower()
    for row in rows:
        if truthy(row.get("liberty_synth_ok")):
            continue
        error = row.get("liberty_synth_error", "")
        if needle and needle not in error.lower():
            continue
        targets.append(
            {
                "target_group": row.get("target_group", "retry"),
                "case_id": row.get("case_id", ""),
                "module_id": row.get("module_id", ""),
                "test_id": row.get("test_id", ""),
                "family_group": row.get("family_group", ""),
                "mode": row.get("mode", ""),
                "verilog_path": row.get("verilog_path", ""),
            }
        )
    return targets


def build_paired_area(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    paired_rows = [r for r in rows if r["target_group"] == "paired" and r.get("liberty_synth_ok") is True]
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in paired_rows:
        grouped.setdefault(row["case_id"], {})[row["mode"]] = row
    out: list[dict[str, Any]] = []
    for case_id, modes in sorted(grouped.items()):
        patch = modes.get("reflect_patch")
        rag = modes.get("reflect_rag_skeleton")
        if not patch or not rag:
            continue
        out.append(
            {
                "case_id": case_id,
                "module_id": patch.get("module_id", ""),
                "test_id": patch.get("test_id", ""),
                "family_group": patch.get("family_group", ""),
                "patch_chip_area": patch.get("chip_area", ""),
                "rag_chip_area": rag.get("chip_area", ""),
                "area_ratio_rag_over_patch": ratio(rag.get("chip_area"), patch.get("chip_area")),
                "patch_mapped_cell_count": patch.get("mapped_cell_count", ""),
                "rag_mapped_cell_count": rag.get("mapped_cell_count", ""),
                "cell_ratio_rag_over_patch": ratio(rag.get("mapped_cell_count"), patch.get("mapped_cell_count")),
                "patch_sequential_area": patch.get("sequential_area", ""),
                "rag_sequential_area": rag.get("sequential_area", ""),
                "patch_elapsed_seconds": patch.get("elapsed_seconds", ""),
                "rag_elapsed_seconds": rag.get("elapsed_seconds", ""),
                "patch_verilog_path": patch.get("verilog_path", ""),
                "rag_verilog_path": rag.get("verilog_path", ""),
            }
        )
    return out


def build_recovered_area(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if row["target_group"] != "newly_recovered":
            continue
        out.append(
            {
                "case_id": row.get("case_id", ""),
                "module_id": row.get("module_id", ""),
                "test_id": row.get("test_id", ""),
                "family_group": row.get("family_group", ""),
                "liberty_synth_ok": row.get("liberty_synth_ok", ""),
                "chip_area": row.get("chip_area", ""),
                "mapped_cell_count": row.get("mapped_cell_count", ""),
                "sequential_area": row.get("sequential_area", ""),
                "sequential_area_ratio_percent": row.get("sequential_area_ratio_percent", ""),
                "elapsed_seconds": row.get("elapsed_seconds", ""),
                "verilog_path": row.get("verilog_path", ""),
            }
        )
    return out


def floats(rows: list[dict[str, Any]], key: str) -> list[float]:
    out = []
    for row in rows:
        try:
            out.append(float(row.get(key, "")))
        except Exception:
            pass
    return out


def fmt_mean(values: list[float]) -> str:
    return f"{statistics.mean(values):.6f}" if values else "NA"


def fmt_median(values: list[float]) -> str:
    return f"{statistics.median(values):.6f}" if values else "NA"


def write_summary(
    path: Path,
    model: str,
    dataset: str,
    liberty: Path,
    rows: list[dict[str, Any]],
    paired: list[dict[str, Any]],
    recovered: list[dict[str, Any]],
) -> None:
    ok = [r for r in rows if r.get("liberty_synth_ok") is True]
    paired_ratios = floats(paired, "area_ratio_rag_over_patch")
    paired_cell_ratios = floats(paired, "cell_ratio_rag_over_patch")
    recovered_ok = [r for r in recovered if r.get("liberty_synth_ok") is True]
    area_less = sum(v < 1.0 for v in paired_ratios)
    area_equal = sum(abs(v - 1.0) < 1e-9 for v in paired_ratios)
    area_more = sum(v > 1.0 for v in paired_ratios)
    family_recovered = Counter(r.get("family_group", "") for r in recovered_ok)
    lines = [
        "# Nangate45-mapped Area Proxy 分析",
        "",
        f"- 模型：{model}",
        f"- 数据集：{dataset}",
        f"- Liberty：`{liberty}`",
        f"- 输入目标 RTL：{len(rows)}",
        f"- Nangate45 映射成功：{len(ok)}/{len(rows)}",
        "",
        "## Paired Area: RAG+Skeleton vs Patch",
        "",
        f"- paired mapped cases：{len(paired)}",
        f"- area ratio `rag / patch` 平均值：{fmt_mean(paired_ratios)}",
        f"- area ratio 中位数：{fmt_median(paired_ratios)}",
        f"- RAG+Skeleton area 更小 / 相同 / 更大：{area_less} / {area_equal} / {area_more}",
        f"- mapped cell ratio 平均值：{fmt_mean(paired_cell_ratios)}",
        "",
        "## Newly Recovered Cases",
        "",
        f"- newly recovered targets：{len(recovered)}",
        f"- newly recovered mapped OK：{len(recovered_ok)}/{len(recovered)}",
        "",
        "| family_group | mapped recovered cases |",
        "|---|---:|",
    ]
    for family, count in family_recovered.most_common():
        lines.append(f"| {family} | {count} |")
    lines += [
        "",
        "## 写作口径",
        "",
        "该实验是 Nangate45 标准单元映射后的 area proxy，不包含真实功耗分析，也没有完整时序约束。因此论文中应写为 standard-cell mapped area proxy，而不是完整 PPA。",
        "可用于补充说明：RAG+Skeleton 新救回的 RTL 不仅通过功能仿真和 generic synthesis，也能完成标准单元映射；同时在 paired successful cases 上没有系统性面积退化。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paired-csv", type=Path)
    parser.add_argument("--newly-recovered-csv", type=Path)
    parser.add_argument("--retry-all-csv", type=Path)
    parser.add_argument("--retry-error-contains", default="timeout")
    parser.add_argument("--liberty", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model", default="")
    parser.add_argument("--dataset", default="")
    parser.add_argument("--yosys-bin", default="yosys")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--fast-abc", action="store_true")
    parser.add_argument("--keep-logs", action="store_true")
    parser.add_argument("--only-newly-recovered", action="store_true")
    parser.add_argument("--only-paired", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = args.output_dir / "yosys_liberty_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if args.retry_all_csv:
        targets = collect_retry_targets(read_csv(args.retry_all_csv), args.retry_error_contains)
    else:
        paired_rows = read_csv(args.paired_csv)
        recovered_rows = read_csv(args.newly_recovered_csv)
        targets = collect_targets(
            paired_rows,
            recovered_rows,
            only_newly_recovered=args.only_newly_recovered,
            only_paired=args.only_paired,
        )
    if args.limit:
        targets = targets[: args.limit]

    rows = []
    for idx, target in enumerate(targets, start=1):
        verilog = Path(target["verilog_path"])
        result = run_yosys_liberty(
            args.yosys_bin,
            args.liberty,
            verilog,
            log_dir,
            args.timeout,
            args.fast_abc,
            args.keep_logs,
        )
        merged = dict(target)
        merged.update(result)
        merged["model"] = args.model
        merged["dataset"] = args.dataset
        rows.append(merged)
        print(
            f"[INFO] {idx}/{len(targets)} {target['target_group']} {target['case_id']} "
            f"{target['mode']} ok={result['liberty_synth_ok']} elapsed={result['elapsed_seconds']}s"
        )

    paired_area = build_paired_area(rows)
    recovered_area = build_recovered_area(rows)

    all_fields = [
        "model",
        "dataset",
        "target_group",
        "case_id",
        "module_id",
        "test_id",
        "family_group",
        "mode",
        "liberty_synth_ok",
        "liberty_synth_error",
        "top_module",
        "mapped_cell_count",
        "chip_area",
        "sequential_area",
        "sequential_area_ratio_percent",
        "dff_cells",
        "xor_cells",
        "xnor_cells",
        "inv_cells",
        "buf_cells",
        "mux_cells",
        "elapsed_seconds",
        "yosys_returncode",
        "yosys_log",
        "mapped_cell_histogram",
        "verilog_path",
    ]
    paired_fields = [
        "case_id",
        "module_id",
        "test_id",
        "family_group",
        "patch_chip_area",
        "rag_chip_area",
        "area_ratio_rag_over_patch",
        "patch_mapped_cell_count",
        "rag_mapped_cell_count",
        "cell_ratio_rag_over_patch",
        "patch_sequential_area",
        "rag_sequential_area",
        "patch_elapsed_seconds",
        "rag_elapsed_seconds",
        "patch_verilog_path",
        "rag_verilog_path",
    ]
    recovered_fields = [
        "case_id",
        "module_id",
        "test_id",
        "family_group",
        "liberty_synth_ok",
        "chip_area",
        "mapped_cell_count",
        "sequential_area",
        "sequential_area_ratio_percent",
        "elapsed_seconds",
        "verilog_path",
    ]

    write_csv(args.output_dir / "liberty_qor_all.csv", rows, all_fields)
    write_csv(args.output_dir / "liberty_qor_paired_area.csv", paired_area, paired_fields)
    write_csv(args.output_dir / "liberty_qor_newly_recovered_area.csv", recovered_area, recovered_fields)
    write_summary(
        args.output_dir / "liberty_qor_summary_zh.md",
        args.model,
        args.dataset,
        args.liberty,
        rows,
        paired_area,
        recovered_area,
    )
    print(f"Targets: {len(targets)}")
    print(f"Liberty mapped OK: {sum(r.get('liberty_synth_ok') is True for r in rows)}/{len(rows)}")
    print(f"Paired area rows: {len(paired_area)}")
    print(f"Newly recovered rows: {len(recovered_area)}")
    print(f"Output: {args.output_dir}")


if __name__ == "__main__":
    main()
