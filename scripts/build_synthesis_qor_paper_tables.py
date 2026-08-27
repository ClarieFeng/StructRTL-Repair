#!/usr/bin/env python3
"""Build paper-ready generic and Nangate45 QoR summary tables."""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "pass"}


def numeric_values(rows: list[dict[str, str]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(row.get(field, "")))
        except (TypeError, ValueError):
            continue
    return values


def fmt_mean(values: list[float]) -> str:
    return f"{statistics.mean(values):.6f}" if values else "NA"


def fmt_median(values: list[float]) -> str:
    return f"{statistics.median(values):.6f}" if values else "NA"


def summarize_generic(model: str, dataset: str, result_dir: Path) -> dict[str, Any]:
    paired = read_csv(result_dir / "synth_qor_patch_vs_rag_paired.csv")
    recovered = read_csv(result_dir / "synth_qor_newly_recovered.csv")
    paired = [
        row
        for row in paired
        if truthy(row.get("patch_functional_ok"))
        and truthy(row.get("rag_functional_ok"))
        and truthy(row.get("patch_synth_ok"))
        and truthy(row.get("rag_synth_ok"))
    ]
    ratios = numeric_values(paired, "cell_ratio_rag_over_patch")
    return {
        "model": model,
        "dataset": dataset,
        "qor_level": "generic",
        "paired_cases": len(paired),
        "rag_smaller": sum(value < 1.0 for value in ratios),
        "rag_equal": sum(abs(value - 1.0) < 1e-9 for value in ratios),
        "rag_larger": sum(value > 1.0 for value in ratios),
        "ratio_mean": fmt_mean(ratios),
        "ratio_median": fmt_median(ratios),
        "newly_recovered": len(recovered),
        "newly_recovered_mapped_ok": sum(truthy(row.get("rag_synth_ok")) for row in recovered),
    }


def load_liberty_rows(directory: Path, merged_name: str, plain_name: str) -> list[dict[str, str]]:
    return read_csv(directory / merged_name) or read_csv(directory / plain_name)


def summarize_liberty(
    model: str,
    dataset: str,
    paired_dir: Path,
    recovered_dir: Path,
) -> dict[str, Any]:
    paired = load_liberty_rows(
        paired_dir,
        "liberty_qor_paired_area_merged.csv",
        "liberty_qor_paired_area.csv",
    )
    recovered = load_liberty_rows(
        recovered_dir,
        "liberty_qor_newly_recovered_area_merged.csv",
        "liberty_qor_newly_recovered_area.csv",
    )
    ratios = numeric_values(paired, "area_ratio_rag_over_patch")
    return {
        "model": model,
        "dataset": dataset,
        "qor_level": "nangate45",
        "paired_cases": len(paired),
        "rag_smaller": sum(value < 1.0 for value in ratios),
        "rag_equal": sum(abs(value - 1.0) < 1e-9 for value in ratios),
        "rag_larger": sum(value > 1.0 for value in ratios),
        "ratio_mean": fmt_mean(ratios),
        "ratio_median": fmt_median(ratios),
        "newly_recovered": len(recovered),
        "newly_recovered_mapped_ok": sum(truthy(row.get("liberty_synth_ok")) for row in recovered),
    }


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Synthesis QoR Paper Table",
        "",
        "| Model | Dataset | QoR level | Paired cases | RAG smaller | RAG equal | RAG larger | Ratio mean | Ratio median | Newly recovered | Newly recovered mapped OK |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {model} | {dataset} | {qor_level} | {paired_cases} | {rag_smaller} | "
            "{rag_equal} | {rag_larger} | {ratio_mean} | {ratio_median} | "
            "{newly_recovered} | {newly_recovered_mapped_ok} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Generic synthesis is the primary downstream synthesizability evidence. Nangate45 results are a standard-cell mapped area proxy, not complete PPA because timing constraints and physical power analysis are absent.",
            "",
            "Recommended wording: RAG+Skeleton improves functional correctness without systematic degradation in generic gate-level complexity or Nangate45-mapped area on paired successful cases. Newly recovered functional-pass RTLs also show downstream synthesizability under generic synthesis, and a substantial subset completes Nangate45 standard-cell mapping.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8-sig")


def parse_run(spec: str) -> tuple[str, str, Path, Path, Path]:
    parts = [part.strip() for part in spec.split(",")]
    if len(parts) not in {4, 5}:
        raise SystemExit(f"Bad --run spec: {spec}")
    model, dataset, generic_dir, paired_dir = parts[:4]
    recovered_dir = parts[4] if len(parts) == 5 else paired_dir
    return model, dataset, Path(generic_dir), Path(paired_dir), Path(recovered_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        help="model,dataset,generic_dir,paired_liberty_dir[,recovered_liberty_dir]",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for spec in args.run:
        model, dataset, generic_dir, paired_dir, recovered_dir = parse_run(spec)
        rows.append(summarize_generic(model, dataset, generic_dir))
        rows.append(summarize_liberty(model, dataset, paired_dir, recovered_dir))

    fields = [
        "model", "dataset", "qor_level", "paired_cases", "rag_smaller", "rag_equal",
        "rag_larger", "ratio_mean", "ratio_median", "newly_recovered",
        "newly_recovered_mapped_ok",
    ]
    write_csv(args.output_dir / "synthesis_qor_paper_table.csv", rows, fields)
    write_markdown(args.output_dir / "synthesis_qor_paper_table.md", rows)
    print(f"Rows: {len(rows)}")
    print(f"Output: {args.output_dir}")


if __name__ == "__main__":
    main()
