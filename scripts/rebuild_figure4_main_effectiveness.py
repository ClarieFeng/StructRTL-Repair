"""Rebuild the frozen Figure 4 effectiveness table from case-level runs."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


MODES = ("origin", "reflect_patch", "reflect_rag_skeleton")


@dataclass(frozen=True)
class RunSpec:
    model: str
    dataset: str
    expected_cases: int
    relative_path: str


RUNS = (
    RunSpec("MGEMMV-Llama-11B", "Author135", 135, "raw_main_runs/reflect_ablation_mgemmv_llama_11b_v6_2_seed1234_20260610_2333.csv"),
    RunSpec("MGEMMV-Llama-11B", "Benchmark1", 81, "raw_main_runs/reflect_ablation_mgemmv_llama_11b_v6_2_81clean_seed1234_20260611_1240.csv"),
    RunSpec("MGEMMV-Qwen-7B", "Author135", 135, "raw_main_runs/reflect_ablation_mgemmv_qwen_7b_v6_2_seed1234_20260610_0935.csv"),
    RunSpec("MGEMMV-Qwen-7B", "Benchmark1", 81, "raw_main_runs/reflect_ablation_mgemmv_qwen_7b_v6_2_81clean_seed1234_20260611_1240.csv"),
    RunSpec("MiniCPM-V-4.5-8B", "Author135", 135, "raw_main_runs/reflect_ablation_minicpm_v_4_5_8b_v6_2_author135_seed1234_20260629_2306.csv"),
    RunSpec("MiniCPM-V-4.5-8B", "Benchmark1", 81, "raw_main_runs/reflect_ablation_minicpm_v_4_5_8b_v6_2_benchmark1_81_seed1234_20260629_2306.csv"),
    RunSpec("Qwen2.5-VL-7B", "Author135", 135, "reconstructed_main_runs/qwen25_author135_reconstructed_from_histories.csv"),
    RunSpec("Qwen2.5-VL-7B", "Benchmark1", 81, "raw_main_runs/reflect_ablation_qwen2_5_vl_7b_v6_2_nolora_81clean_seed1234_20260629_0942.csv"),
    RunSpec("Qwen3-VL-8B", "Author135", 135, "raw_main_runs/reflect_ablation_qwen3_vl_8b_v6_2_author135_seed1234_20260630_1116.csv"),
    RunSpec("Qwen3-VL-8B", "Benchmark1", 81, "raw_main_runs/reflect_ablation_qwen3_vl_8b_v6_2_benchmark1_81_seed1234_20260630_1116.csv"),
    RunSpec("Llama-3.2-11B-Vision", "Author135", 135, "raw_main_runs/reflect_ablation_llama3_2_11b_vision_instruct_v6_2_author135_seed1234_20260703_1452.csv"),
    RunSpec("Llama-3.2-11B-Vision", "Benchmark1", 81, "raw_main_runs/reflect_ablation_llama3_2_11b_vision_instruct_v6_2_benchmark1_81clean_seed1234_20260703_1452.csv"),
    RunSpec("InternVL3.5-8B", "Author135", 135, "raw_main_runs/reflect_ablation_internvl3_5_8b_v6_2_author135_seed1234_20260704_1206.csv"),
    RunSpec("InternVL3.5-8B", "Benchmark1", 81, "raw_main_runs/reflect_ablation_internvl3_5_8b_v6_2_benchmark1_81clean_seed1234_20260704_1206.csv"),
)


FIELDS = (
    "model",
    "dataset",
    "n",
    "origin_syntax",
    "origin_functional",
    "patch_syntax",
    "patch_functional",
    "full_syntax",
    "full_functional",
    "delta_origin_pp",
    "delta_patch_pp",
)


def parse_bool(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no", ""}:
        return False
    raise ValueError(f"Unrecognized Boolean value: {value!r}")


def summarize_run(root: Path, spec: RunSpec) -> dict[str, object]:
    path = root / spec.relative_path
    if not path.is_file():
        raise FileNotFoundError(path)

    by_mode: dict[str, dict[tuple[int, int], dict[str, str]]] = {mode: {} for mode in MODES}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            mode = row.get("mode", "").strip()
            if mode not in by_mode:
                continue
            case = (int(row["module_id"]), int(row["test_id"]))
            if case in by_mode[mode]:
                raise ValueError(f"Duplicate {mode} row for {case} in {path}")
            by_mode[mode][case] = row

    case_sets = [set(by_mode[mode]) for mode in MODES]
    if any(cases != case_sets[0] for cases in case_sets[1:]):
        raise ValueError(f"Mode case sets do not match in {path}")
    n = len(case_sets[0])
    if n != spec.expected_cases:
        raise ValueError(f"Expected {spec.expected_cases} cases in {path}, found {n}")

    def count(mode: str, field: str) -> int:
        return sum(parse_bool(row[field]) for row in by_mode[mode].values())

    origin_syntax = count("origin", "syntax_ok")
    origin_functional = count("origin", "functional_ok")
    patch_syntax = count("reflect_patch", "syntax_ok")
    patch_functional = count("reflect_patch", "functional_ok")
    full_syntax = count("reflect_rag_skeleton", "syntax_ok")
    full_functional = count("reflect_rag_skeleton", "functional_ok")

    return {
        "model": spec.model,
        "dataset": spec.dataset,
        "n": n,
        "origin_syntax": origin_syntax,
        "origin_functional": origin_functional,
        "patch_syntax": patch_syntax,
        "patch_functional": patch_functional,
        "full_syntax": full_syntax,
        "full_functional": full_functional,
        "delta_origin_pp": f"{100.0 * (full_functional - origin_functional) / n:.1f}",
        "delta_patch_pp": f"{100.0 * (full_functional - patch_functional) / n:.1f}",
    }


def aggregate(rows: list[dict[str, object]]) -> dict[str, object]:
    total = sum(int(row["n"]) for row in rows)
    result: dict[str, object] = {"model": "ALL", "dataset": "Both", "n": total}
    for field in (
        "origin_syntax",
        "origin_functional",
        "patch_syntax",
        "patch_functional",
        "full_syntax",
        "full_functional",
    ):
        result[field] = sum(int(row[field]) for row in rows)
    result["delta_origin_pp"] = f"{100.0 * (int(result['full_functional']) - int(result['origin_functional'])) / total:.1f}"
    result["delta_patch_pp"] = f"{100.0 * (int(result['full_functional']) - int(result['patch_functional'])) / total:.1f}"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rq1-root",
        type=Path,
        required=True,
        help="Directory containing raw_main_runs and reconstructed_main_runs.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.rq1_root.resolve()
    rows = [summarize_run(root, spec) for spec in RUNS]
    rows.append(aggregate(rows))

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Runs: {len(RUNS)}")
    print(f"Model-case observations per mode: {sum(int(row['n']) for row in rows[:-1])}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
