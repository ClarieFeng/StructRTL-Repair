#!/usr/bin/env python3
"""Rebuild family-level manuscript evidence from frozen family summaries."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


MODES = ("origin", "reflect_patch", "reflect_rag_skeleton")

MODEL_ORDER = [
    "MGEMMV-Llama-11B",
    "MGEMMV-Qwen-7B",
    "MiniCPM-V-4.5-9B",
    "Qwen2.5-VL-7B-Instruct",
    "Qwen3-VL-8B-Instruct",
    "Llama-3.2-11B-Vision-Instruct",
    "InternVL3.5-8B-Instruct",
]

DATASET_ORDER = ["Author135", "Benchmark1-81"]

FAMILY_GROUPS = {
    "adder / PPA": {
        "adder_fa",
        "carry_select_adder",
        "carry_skip_adder",
        "cla_adder",
        "ppa_adder",
    },
    "multiplier": {
        "parallel_multiplier",
        "serial_multiplier",
        "signed_booth_multiplier",
        "signed_multiplier",
        "unsigned_booth_multiplier",
        "unsigned_multiplier",
    },
    "MAC / arithmetic accumulation": {
        "signed_adder_tree",
        "signed_mac",
        "unsigned_adder_tree",
    },
    "PE / PE-row / PE-array": {
        "processing_element",
        "processing_element_array",
        "processing_element_row",
    },
    "Winograd / transform / dataflow": {
        "systolic_dataflow",
        "winograd_transform",
    },
}

GROUP_MODULE_COUNTS = {
    "adder / PPA": 7,
    "multiplier": 9,
    "MAC / arithmetic accumulation": 5,
    "PE / PE-row / PE-array": 3,
    "Winograd / transform / dataflow": 3,
}

DETAIL_FIELDS = [
    "source_file",
    "model",
    "dataset",
    "family",
    "total",
    "origin_syntax",
    "patch_syntax",
    "rag_skeleton_syntax",
    "patch_syntax_gain",
    "rag_skeleton_syntax_gain",
    "total_syntax_gain",
    "origin_functional",
    "patch_functional",
    "rag_skeleton_functional",
    "patch_functional_gain",
    "rag_skeleton_functional_gain",
    "total_functional_gain",
    "residual_functional_fail",
]

RUN_FIELDS = [
    "source_file",
    "model",
    "dataset",
    "total",
    "origin_syntax",
    "patch_syntax",
    "rag_skeleton_syntax",
    "origin_functional",
    "patch_functional",
    "rag_skeleton_functional",
    "patch_syntax_gain",
    "rag_skeleton_syntax_gain",
    "total_syntax_gain",
    "patch_functional_gain",
    "rag_skeleton_functional_gain",
    "total_functional_gain",
    "residual_functional_fail",
]

GROUP_FIELDS = [
    "hardware_family_group",
    "model",
    "dataset",
    "total",
    "origin_syntax",
    "patch_syntax",
    "rag_skeleton_syntax",
    "patch_syntax_gain",
    "rag_skeleton_syntax_gain",
    "total_syntax_gain",
    "origin_functional",
    "patch_functional",
    "rag_skeleton_functional",
    "patch_gain",
    "rag_skeleton_gain",
    "total_gain",
    "residual_fail",
    "functional_origin_rate",
    "functional_patch_rate",
    "functional_rag_skeleton_rate",
    "fine_families",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def infer_model(filename: str) -> str:
    name = filename.lower()
    patterns = [
        ("internvl3_5", "InternVL3.5-8B-Instruct"),
        ("llama3_2", "Llama-3.2-11B-Vision-Instruct"),
        ("mgemmv_llama", "MGEMMV-Llama-11B"),
        ("mgemmv_qwen", "MGEMMV-Qwen-7B"),
        ("minicpm", "MiniCPM-V-4.5-9B"),
        ("qwen3_vl", "Qwen3-VL-8B-Instruct"),
        ("qwen25_vl", "Qwen2.5-VL-7B-Instruct"),
        ("qwen_vl", "Qwen2.5-VL-7B-Instruct"),
    ]
    for pattern, model in patterns:
        if pattern in name:
            return model
    raise ValueError(f"Cannot infer model from {filename}")


def infer_dataset(filename: str) -> str:
    name = filename.lower()
    if "benchmark1" in name or "81clean" in name or "_81_" in name:
        return "Benchmark1-81"
    if "author135" in name or "seed1234" in name:
        return "Author135"
    raise ValueError(f"Cannot infer dataset from {filename}")


def model_rank(model: str) -> int:
    return MODEL_ORDER.index(model)


def dataset_rank(dataset: str) -> int:
    return DATASET_ORDER.index(dataset)


def summarize_run(rows: list[dict[str, object]], include_source: bool = True) -> dict[str, object]:
    output: dict[str, object] = {}
    if include_source:
        output["source_file"] = rows[0]["source_file"]
    output["model"] = rows[0]["model"]
    output["dataset"] = rows[0]["dataset"]
    for field in (
        "total",
        "origin_syntax",
        "patch_syntax",
        "rag_skeleton_syntax",
        "origin_functional",
        "patch_functional",
        "rag_skeleton_functional",
    ):
        output[field] = sum(int(row[field]) for row in rows)
    output["patch_syntax_gain"] = output["patch_syntax"] - output["origin_syntax"]
    output["rag_skeleton_syntax_gain"] = output["rag_skeleton_syntax"] - output["patch_syntax"]
    output["total_syntax_gain"] = output["rag_skeleton_syntax"] - output["origin_syntax"]
    output["patch_functional_gain"] = output["patch_functional"] - output["origin_functional"]
    output["rag_skeleton_functional_gain"] = output["rag_skeleton_functional"] - output["patch_functional"]
    output["total_functional_gain"] = output["rag_skeleton_functional"] - output["origin_functional"]
    output["residual_functional_fail"] = output["total"] - output["rag_skeleton_functional"]
    return output


def build_detail(input_dir: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    detail: list[dict[str, object]] = []
    index: list[dict[str, object]] = []
    seen_runs: set[tuple[str, str]] = set()
    expected_families = set().union(*FAMILY_GROUPS.values())

    for path in sorted(input_dir.glob("*_family_summary.csv")):
        model = infer_model(path.name)
        dataset = infer_dataset(path.name)
        key = (model, dataset)
        if key in seen_runs:
            raise ValueError(f"Duplicate model/dataset input: {key}")
        seen_runs.add(key)

        raw = read_csv(path)
        by_family: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
        for row in raw:
            family = row["family"].strip()
            mode = row["mode"].strip()
            if mode not in MODES:
                raise ValueError(f"Unexpected mode {mode!r} in {path.name}")
            by_family[family][mode] = row

        if set(by_family) != expected_families:
            missing = sorted(expected_families - set(by_family))
            extra = sorted(set(by_family) - expected_families)
            raise ValueError(f"Family mismatch in {path.name}: missing={missing}, extra={extra}")

        for family in sorted(by_family):
            modes = by_family[family]
            if set(modes) != set(MODES):
                raise ValueError(f"Mode mismatch for {family} in {path.name}")
            totals = {int(modes[mode]["total"]) for mode in MODES}
            if len(totals) != 1:
                raise ValueError(f"Inconsistent totals for {family} in {path.name}: {totals}")
            total = totals.pop()
            origin_syntax = int(modes["origin"]["syntax"])
            patch_syntax = int(modes["reflect_patch"]["syntax"])
            full_syntax = int(modes["reflect_rag_skeleton"]["syntax"])
            origin_functional = int(modes["origin"]["functional"])
            patch_functional = int(modes["reflect_patch"]["functional"])
            full_functional = int(modes["reflect_rag_skeleton"]["functional"])
            detail.append(
                {
                    "source_file": path.name,
                    "model": model,
                    "dataset": dataset,
                    "family": family,
                    "total": total,
                    "origin_syntax": origin_syntax,
                    "patch_syntax": patch_syntax,
                    "rag_skeleton_syntax": full_syntax,
                    "patch_syntax_gain": patch_syntax - origin_syntax,
                    "rag_skeleton_syntax_gain": full_syntax - patch_syntax,
                    "total_syntax_gain": full_syntax - origin_syntax,
                    "origin_functional": origin_functional,
                    "patch_functional": patch_functional,
                    "rag_skeleton_functional": full_functional,
                    "patch_functional_gain": patch_functional - origin_functional,
                    "rag_skeleton_functional_gain": full_functional - patch_functional,
                    "total_functional_gain": full_functional - origin_functional,
                    "residual_functional_fail": total - full_functional,
                }
            )

        run_total = sum(int(row["total"]) for row in detail if row["source_file"] == path.name)
        expected_total = 135 if dataset == "Author135" else 81
        if run_total != expected_total:
            raise ValueError(f"Expected {expected_total} cases in {path.name}, found {run_total}")
        index.append(
            {
                "source_file": path.name,
                "model": model,
                "dataset": dataset,
                "total": run_total,
                "families": len(by_family),
            }
        )

    expected_runs = {(model, dataset) for model in MODEL_ORDER for dataset in DATASET_ORDER}
    if seen_runs != expected_runs:
        missing = sorted(expected_runs - seen_runs)
        extra = sorted(seen_runs - expected_runs)
        raise ValueError(f"Run coverage mismatch: missing={missing}, extra={extra}")

    detail.sort(key=lambda row: (model_rank(str(row["model"])), dataset_rank(str(row["dataset"])), str(row["family"])))
    index.sort(key=lambda row: (model_rank(str(row["model"])), dataset_rank(str(row["dataset"]))))
    return detail, index


def build_group_rows(detail: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: list[dict[str, object]] = []
    by_run = defaultdict(list)
    for row in detail:
        by_run[(row["model"], row["dataset"])].append(row)
    for model in MODEL_ORDER:
        for dataset in DATASET_ORDER:
            run_rows = by_run[(model, dataset)]
            for group, families in FAMILY_GROUPS.items():
                rows = [row for row in run_rows if row["family"] in families]
                summary = summarize_run(rows, include_source=False)
                total = int(summary["total"])
                grouped.append(
                    {
                        "hardware_family_group": group,
                        "model": model,
                        "dataset": dataset,
                        "total": total,
                        "origin_syntax": summary["origin_syntax"],
                        "patch_syntax": summary["patch_syntax"],
                        "rag_skeleton_syntax": summary["rag_skeleton_syntax"],
                        "patch_syntax_gain": summary["patch_syntax_gain"],
                        "rag_skeleton_syntax_gain": summary["rag_skeleton_syntax_gain"],
                        "total_syntax_gain": summary["total_syntax_gain"],
                        "origin_functional": summary["origin_functional"],
                        "patch_functional": summary["patch_functional"],
                        "rag_skeleton_functional": summary["rag_skeleton_functional"],
                        "patch_gain": summary["patch_functional_gain"],
                        "rag_skeleton_gain": summary["rag_skeleton_functional_gain"],
                        "total_gain": summary["total_functional_gain"],
                        "residual_fail": summary["residual_functional_fail"],
                        "functional_origin_rate": f"{int(summary['origin_functional']) / total:.3f}",
                        "functional_patch_rate": f"{int(summary['patch_functional']) / total:.3f}",
                        "functional_rag_skeleton_rate": f"{int(summary['rag_skeleton_functional']) / total:.3f}",
                        "fine_families": "; ".join(sorted(families)),
                    }
                )
    return grouped


def build_pooled_rows(grouped: list[dict[str, object]]) -> list[dict[str, object]]:
    fields = [
        "hardware_family_group",
        "module_count",
        "total",
        "origin_functional",
        "patch_functional",
        "rag_skeleton_functional",
        "origin_rate",
        "patch_net_gain_pp",
        "structured_net_gain_pp",
        "residual_failure_rate",
    ]
    output: list[dict[str, object]] = []
    for group in FAMILY_GROUPS:
        rows = [row for row in grouped if row["hardware_family_group"] == group]
        total = sum(int(row["total"]) for row in rows)
        origin = sum(int(row["origin_functional"]) for row in rows)
        patch = sum(int(row["patch_functional"]) for row in rows)
        full = sum(int(row["rag_skeleton_functional"]) for row in rows)
        output.append(
            {
                "hardware_family_group": group,
                "module_count": GROUP_MODULE_COUNTS[group],
                "total": total,
                "origin_functional": origin,
                "patch_functional": patch,
                "rag_skeleton_functional": full,
                "origin_rate": f"{origin / total:.6f}",
                "patch_net_gain_pp": f"{100.0 * (patch - origin) / total:.6f}",
                "structured_net_gain_pp": f"{100.0 * (full - patch) / total:.6f}",
                "residual_failure_rate": f"{100.0 * (total - full) / total:.6f}",
            }
        )
    return output, fields


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    detail, index = build_detail(input_dir)
    grouped = build_group_rows(detail)

    by_source = defaultdict(list)
    for row in detail:
        by_source[row["source_file"]].append(row)
    run_rows = [summarize_run(rows) for rows in by_source.values()]
    run_rows.sort(key=lambda row: (model_rank(str(row["model"])), dataset_rank(str(row["dataset"]))))

    write_csv(output_dir / "family_gain_table.csv", detail, DETAIL_FIELDS)
    write_csv(output_dir / "family_gain_file_index.csv", index, ["source_file", "model", "dataset", "total", "families"])
    write_csv(output_dir / "run_gain_summary.csv", run_rows, RUN_FIELDS)
    write_csv(output_dir / "model_dataset_gain_summary.csv", [{key: row[key] for key in RUN_FIELDS if key != "source_file"} for row in run_rows], RUN_FIELDS[1:])
    write_csv(output_dir / "model_dataset_file_coverage.csv", [{"model": row["model"], "dataset": row["dataset"], "num_files": 1, "source_files": row["source_file"]} for row in index], ["model", "dataset", "num_files", "source_files"])
    write_csv(output_dir / "family_generalization_group_table.csv", grouped, GROUP_FIELDS)
    pooled, pooled_fields = build_pooled_rows(grouped)
    write_csv(output_dir / "family_pooled_overview_14runs.csv", pooled, pooled_fields)

    sort_outputs = {
        "top_patch_functional_gain.csv": "patch_functional_gain",
        "top_patch_syntax_gain.csv": "patch_syntax_gain",
        "top_rag_skeleton_functional_gain.csv": "rag_skeleton_functional_gain",
        "top_rag_skeleton_syntax_gain.csv": "rag_skeleton_syntax_gain",
        "top_residual_functional_fail.csv": "residual_functional_fail",
        "top_total_functional_gain.csv": "total_functional_gain",
    }
    for filename, field in sort_outputs.items():
        rows = sorted(detail, key=lambda row: (-int(row[field]), model_rank(str(row["model"])), dataset_rank(str(row["dataset"])), str(row["family"])))
        write_csv(output_dir / filename, rows, DETAIL_FIELDS)

    print(f"Inputs: {len(index)} runs")
    print(f"Family rows: {len(detail)}")
    print(f"Model-case observations per mode: {sum(int(row['total']) for row in run_rows)}")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
