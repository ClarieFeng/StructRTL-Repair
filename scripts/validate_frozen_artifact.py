"""Validate frozen case-level data against the manuscript effectiveness table."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


MODEL_ALIASES = {
    "Qwen2.5-VL-7B-Instruct": "Qwen2.5-VL-7B",
    "Qwen3-VL-8B-Instruct": "Qwen3-VL-8B",
    "Llama-3.2-11B-Vision-Instruct": "Llama-3.2-11B-Vision",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def truth(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "pass"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--main-table", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    root = Path(args.artifact_root).resolve()
    main_table = Path(args.main_table).resolve()
    expected: dict[tuple[str, str], dict[str, tuple[int, int]]] = {}
    for row in read_csv(main_table):
        if row["model"] == "ALL":
            continue
        expected[(row["model"], row["dataset"])] = {
            "origin": (int(row["origin_syntax"]), int(row["origin_functional"])),
            "reflect_patch": (int(row["patch_syntax"]), int(row["patch_functional"])),
            "reflect_rag_skeleton": (
                int(row["full_syntax"]),
                int(row["full_functional"]),
            ),
        }

    errors: list[dict[str, object]] = []
    main_files = sorted((root / "data/RQ1_main_paired").glob("*.csv"))
    seen: set[tuple[str, str]] = set()
    for path in main_files:
        rows = read_csv(path)
        if not rows:
            errors.append({"file": path.name, "error": "empty"})
            continue
        key = (
            MODEL_ALIASES.get(rows[0]["model"], rows[0]["model"]),
            rows[0]["dataset"],
        )
        seen.add(key)
        if key not in expected:
            errors.append({"file": path.name, "error": f"unexpected run {key}"})
            continue
        for mode, wanted in expected[key].items():
            selected = [row for row in rows if row["mode"] == mode]
            observed = (
                sum(truth(row["syntax_ok"]) for row in selected),
                sum(truth(row["functional_ok"]) for row in selected),
            )
            if observed != wanted:
                errors.append(
                    {
                        "file": path.name,
                        "mode": mode,
                        "observed": observed,
                        "expected": wanted,
                    }
                )
    for key in sorted(set(expected) - seen):
        errors.append({"error": f"missing run {key}"})

    component: list[dict[str, object]] = []
    for path in sorted((root / "data/RQ2_component_ablation").glob("*.csv")):
        rows = read_csv(path)
        component.append(
            {
                "file": path.name,
                "rows": len(rows),
                "cases": len({(row["module_id"], row["test_id"]) for row in rows}),
                "mode_counts": dict(Counter(row["mode"] for row in rows)),
            }
        )

    seed_runs: list[dict[str, object]] = []
    for path in sorted((root / "data/RQ3_random_seed").glob("*.csv")):
        rows = read_csv(path)
        seed_runs.append(
            {
                "file": path.name,
                "rows": len(rows),
                "cases": len({(row["module_id"], row["test_id"]) for row in rows}),
                "mode_counts": dict(Counter(row["mode"] for row in rows)),
            }
        )
        if len(rows) != 36:
            errors.append({"file": path.name, "error": "seed run is not 36 rows"})

    report = {
        "protocol": "frozen_artifact_consistency_v1",
        "status": "PASS" if not errors else "FAIL",
        "main_files": len(main_files),
        "expected_main_runs": len(expected),
        "errors": errors,
        "component_runs": component,
        "random_seed_runs": seed_runs,
    }
    output = Path(args.output_json).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Frozen artifact consistency: {report['status']}")
    print(f"Main files: {len(main_files)}; errors: {len(errors)}")
    print(f"Report: {output}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
