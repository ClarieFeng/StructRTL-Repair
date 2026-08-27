import argparse
import csv
import sys
import random
import shutil
import tempfile
import time
from pathlib import Path

from path_config import install_model_path_from_argv

install_model_path_from_argv()

from origin_llm_test_internvl3_5_v6_2 import SCRIPT_DIR, clean_generated_code
from single_agent_reflect_v6_2_internvl3_5_public_protocol import (
    BENCHMARK_CLEAN,
    ORACLE_DEBUG,
    functional_check,
    generate_code_with_limits,
    load_case,
    run_single_case,
    syntax_check,
)
from public_evaluation_protocol import LEGACY_ACCESS, VALID_ACCESS_POLICIES, configure_access

try:
    import numpy as np
except Exception:
    np = None

try:
    import torch
except Exception:
    torch = None


DEFAULT_CASES = [
    (1, 1),
    (1, 2),
    (5, 1),
    (6, 1),
    (8, 1),
    (10, 1),
]

EXPANDED_CASES = [
    (1, 1),
    (1, 2),
    (5, 1),
    (5, 2),
    (6, 1),
    (6, 2),
    (7, 1),
    (7, 2),
    (8, 1),
    (8, 2),
    (9, 1),
    (10, 1),
    (11, 1),
    (13, 1),
    (22, 1),
    (24, 1),
]


def build_full_cases(base_path: Path):
    cases = []
    for module_dir in sorted(base_path.glob("module*"), key=lambda p: int(p.name.replace("module", ""))):
        if not module_dir.is_dir():
            continue
        module_id = int(module_dir.name.replace("module", ""))
        for test_dir in sorted(module_dir.glob("test*"), key=lambda p: int(p.name.replace("test", ""))):
            if not test_dir.is_dir():
                continue
            test_id = int(test_dir.name.replace("test", ""))
            cases.append((module_id, test_id))
    return cases


def set_generation_seed(seed: int | None):
    if seed is None:
        return
    random.seed(seed)
    if np is not None:
        np.random.seed(seed % (2**32))
    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def parse_cases(case_text: str, preset: str, base_path: Path):
    if not case_text.strip():
        if preset == "expanded":
            return EXPANDED_CASES
        if preset == "full":
            return build_full_cases(base_path)
        return DEFAULT_CASES
    cases = []
    for item in case_text.split(","):
        module_id, test_id = item.strip().split(":")
        cases.append((int(module_id), int(test_id)))
    return cases


def mode_result_dir(mode: str, seed: int, module_id: int, test_id: int):
    return f"reflect_result_{mode}_seed{seed}_m{module_id}_t{test_id}"


def get_experiment_root(output_csv: Path):
    return output_csv.parent / "experiments" / output_csv.stem


def run_origin_case(
    base_path: Path,
    module_id: int,
    test_id: int,
    seed: int | None,
    origin_max_new_tokens: int,
    evaluation_access: str = LEGACY_ACCESS,
):
    case_dir, code_dir, prompt, image_path = load_case(base_path, module_id, test_id)
    configure_access(evaluation_access, prompt)
    set_generation_seed(seed)
    raw_output = generate_code_with_limits(prompt, image_path, max_new_tokens=origin_max_new_tokens)
    candidate = clean_generated_code(raw_output)
    syntax_ok, syntax_error = syntax_check(candidate, code_dir)
    functional_ok = False
    functional_detail = ""

    with tempfile.TemporaryDirectory(prefix="ablation_origin_") as temp_dir:
        candidate_path = Path(temp_dir) / "candidate.v"
        candidate_path.write_text(candidate, encoding="utf-8")
        if syntax_ok:
            functional_ok, functional_detail = functional_check(candidate_path, code_dir, case_dir / f"ablation_origin_result_seed{seed}")

    return {
        "mode": "origin",
        "module_id": module_id,
        "test_id": test_id,
        "num_iterations": 1,
        "final_iteration": 0,
        "selection_reason": "origin",
        "syntax_ok": syntax_ok,
        "functional_ok": functional_ok,
        "final_source": "raw",
        "reflection_categories": "",
        "retrieved_rule_count": 0,
        "preferred_action": "",
        "diagnosis_family": "",
        "detail": functional_detail if functional_detail else syntax_error,
    }


def run_agent_case(
    base_path: Path,
    module_id: int,
    test_id: int,
    *,
    mode: str,
    enable_patch: bool,
    enable_skeleton: bool,
    enable_domain_knowledge: bool,
    seed: int | None,
    rag_path: Path | None,
    experiment_root: Path,
    strategy_profile: str,
    evaluation_access: str = LEGACY_ACCESS,
):
    def select_submission_record(history_rows):
        if not history_rows:
            return {}, ""
        functional_rows = [row for row in history_rows if bool(row.get("functional_ok", False))]
        if functional_rows:
            return functional_rows[-1], "best_functional"
        syntax_rows = [row for row in history_rows if bool(row.get("syntax_ok", False))]
        if syntax_rows:
            return syntax_rows[-1], "best_syntax"
        return history_rows[-1], "last_attempt"

    def latest_repair_state(history_rows):
        for row in reversed(history_rows):
            state = row.get("repair_state", {}) or {}
            if state:
                return state
        return {}

    result_dir_name = mode_result_dir(mode, seed or 0, module_id, test_id)
    reflection_log = experiment_root / "logs" / f"{result_dir_name}.jsonl"
    history = run_single_case(
        base_path,
        module_id,
        test_id,
        max_iters=3,
        rag_path=rag_path,
        reflection_log=reflection_log.resolve(),
        seed=seed,
        enable_patch=enable_patch,
        enable_skeleton=enable_skeleton,
        enable_domain_knowledge=enable_domain_knowledge,
        evaluation_access=evaluation_access,
        result_dir_name=result_dir_name,
        result_root=experiment_root / "cases",
        strategy_profile=strategy_profile,
    )
    selected, selection_reason = select_submission_record(history)
    detail = selected.get("functional_detail") or selected.get("syntax_error", "")
    repair_state = selected.get("repair_state", {}) or latest_repair_state(history)
    return {
        "mode": mode,
        "module_id": module_id,
        "test_id": test_id,
        "num_iterations": len(history),
        "final_iteration": selected.get("iteration", ""),
        "selection_reason": selection_reason,
        "syntax_ok": bool(selected.get("syntax_ok", False)),
        "functional_ok": bool(selected.get("functional_ok", False)),
        "final_source": selected.get("functional_source", selected.get("syntax_source", "raw")),
        "reflection_categories": selected.get("retrieved_categories", ""),
        "retrieved_rule_count": selected.get("retrieved_rule_count", 0),
        "repair_best_status": repair_state.get("best_status", ""),
        "repair_current_stage": repair_state.get("current_stage", ""),
        "repair_active_categories": ",".join(repair_state.get("active_categories", [])),
        "interface_gate_action": selected.get("interface_gate_action", ""),
        "interface_gate_expected_top": selected.get("interface_gate_expected_top", ""),
        "skeleton_gate_action": selected.get("skeleton_gate_action", ""),
        "skeleton_gate_expected_ports": selected.get("skeleton_gate_expected_ports", ""),
        "port_gate_action": selected.get("port_gate_action", ""),
        "static_gate_action": selected.get("static_gate_action", ""),
        "static_gate_categories": selected.get("static_gate_categories", ""),
        "static_gate_count": selected.get("static_gate_count", 0),
        "preferred_action": selected.get("preferred_action", ""),
        "diagnosis_family": selected.get("diagnosis_family", ""),
        "detail": detail,
    }


CSV_FIELDS = [
    "evaluation_access",
    "mode",
    "module_id",
    "test_id",
    "num_iterations",
    "final_iteration",
    "selection_reason",
    "syntax_ok",
    "functional_ok",
    "final_source",
    "reflection_categories",
    "retrieved_rule_count",
    "repair_best_status",
    "repair_current_stage",
    "repair_active_categories",
    "interface_gate_action",
    "interface_gate_expected_top",
    "skeleton_gate_action",
    "skeleton_gate_expected_ports",
    "port_gate_action",
    "static_gate_action",
    "static_gate_categories",
    "static_gate_count",
    "preferred_action",
    "diagnosis_family",
    "detail",
]


MAX_DETAIL_CHARS = 4000


csv.field_size_limit(min(sys.maxsize, 10**7))


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def truncate_detail(text: str):
    text = text or ""
    if len(text) <= MAX_DETAIL_CHARS:
        return text
    keep_head = MAX_DETAIL_CHARS // 2
    keep_tail = MAX_DETAIL_CHARS - keep_head - len("\n...[truncated]...\n")
    return text[:keep_head] + "\n...[truncated]...\n" + text[-keep_tail:]


def normalize_row(row):
    normalized = dict(row)
    normalized["detail"] = truncate_detail(normalized.get("detail", ""))
    return normalized


def write_csv(rows, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(normalize_row(row) for row in rows)


def append_csv_row(row, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = output_path.exists()
    with output_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(normalize_row(row))


def load_existing_rows(output_path: Path):
    if not output_path.exists():
        return [], set()
    with output_path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    keys = {
        (row["mode"], int(row["module_id"]), int(row["test_id"]))
        for row in rows
    }
    return rows, keys


def summarize(rows):
    summary = {}
    for row in rows:
        mode = row["mode"]
        summary.setdefault(mode, {"total": 0, "syntax": 0, "functional": 0})
        summary[mode]["total"] += 1
        summary[mode]["syntax"] += int(parse_bool(row["syntax_ok"]))
        summary[mode]["functional"] += int(parse_bool(row["functional_ok"]))
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Run ablation over origin / ordinary reflect+patch / reflect+RAG+hard-skeleton."
    )
    parser.add_argument("--base-directory", default="..", help="Dataset root relative to this script.")
    parser.add_argument("--model-path", default=None, help="Path to the local model directory. Required unless MGEMMV_MODEL_PATH is set.")
    parser.add_argument(
        "--cases",
        default="",
        help="Comma-separated module:test list, e.g. '1:1,5:1,8:1'. Default uses a small preset.",
    )
    parser.add_argument(
        "--preset",
        choices=["small", "expanded", "full"],
        default="small",
        help="Choose a built-in case preset when --cases is empty.",
    )
    parser.add_argument(
        "--output-csv",
        default="../reflect_ablation.csv",
        help="Output CSV path. Default: ../reflect_ablation.csv",
    )
    parser.add_argument("--seed", type=int, default=1234, help="Base random seed for reproducible sampling.")
    parser.add_argument(
        "--strategy-profile",
        choices=[BENCHMARK_CLEAN, ORACLE_DEBUG],
        default=BENCHMARK_CLEAN,
        help="Reflection strategy profile. Default: benchmark_clean",
    )
    parser.add_argument(
        "--evaluation-access",
        choices=VALID_ACCESS_POLICIES,
        default=LEGACY_ACCESS,
        help="Evaluator access policy. public_only exposes public contracts and sanitized category feedback.",
    )
    parser.add_argument(
        "--rag-path",
        default="./error_repair_library.jsonl",
        help="JSONL error-repair library used as RAG guidance. Default: ./error_repair_library.jsonl",
    )
    parser.add_argument(
        "--origin-max-new-tokens",
        type=int,
        default=1536,
        help="Generation cap for the origin baseline branch. Default: 1536",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Delete the existing CSV and experiment directory before running, forcing a full rerun.",
    )
    args = parser.parse_args()

    if args.model_path:
        import os
        os.environ["MGEMMV_MODEL_PATH"] = args.model_path

    base_path = (SCRIPT_DIR / args.base_directory).resolve()
    output_csv = (SCRIPT_DIR / args.output_csv).resolve()
    experiment_root = get_experiment_root(output_csv)
    rag_path = (SCRIPT_DIR / args.rag_path).resolve() if args.rag_path else None
    if rag_path and not rag_path.exists():
        print(f"[WARN] RAG library not found, continuing with builtin rules only: {rag_path}", flush=True)
        rag_path = None
    cases = parse_cases(args.cases, args.preset, base_path)

    if args.fresh:
        if output_csv.exists():
            output_csv.unlink()
        if experiment_root.exists():
            shutil.rmtree(experiment_root)

    rows, completed = load_existing_rows(output_csv)
    print(f"[INFO] Base path: {base_path}", flush=True)
    print(f"[INFO] Output CSV: {output_csv}", flush=True)
    print(f"[INFO] Experiment root: {experiment_root}", flush=True)
    print(f"[INFO] RAG library: {rag_path if rag_path else 'builtin_error_db only'}", flush=True)
    print(f"[INFO] Total cases: {len(cases)}", flush=True)
    start = time.time()
    for case_idx, (module_id, test_id) in enumerate(cases):
        case_seed = args.seed + case_idx * 100
        print(f"\n[CASE {case_idx + 1}/{len(cases)}] module{module_id}/test{test_id} seed={case_seed}", flush=True)
        planned = [
            (
                "origin",
                lambda: run_origin_case(
                    base_path,
                    module_id,
                    test_id,
                    case_seed,
                    args.origin_max_new_tokens,
                    args.evaluation_access,
                ),
            ),
            (
                "reflect_patch",
                lambda: run_agent_case(
                    base_path,
                    module_id,
                    test_id,
                    mode="reflect_patch",
                    enable_patch=True,
                    enable_skeleton=False,
                    enable_domain_knowledge=False,
                    seed=case_seed,
                    rag_path=None,
                    experiment_root=experiment_root,
                    strategy_profile=args.strategy_profile,
                    evaluation_access=args.evaluation_access,
                ),
            ),
            (
                "reflect_rag_skeleton",
                lambda: run_agent_case(
                    base_path,
                    module_id,
                    test_id,
                    mode="reflect_rag_skeleton",
                    enable_patch=True,
                    enable_skeleton=True,
                    enable_domain_knowledge=True,
                    seed=case_seed,
                    rag_path=rag_path,
                    experiment_root=experiment_root,
                    strategy_profile=args.strategy_profile,
                    evaluation_access=args.evaluation_access,
                ),
            ),
        ]
        for mode, fn in planned:
            key = (mode, module_id, test_id)
            if key in completed:
                print(f"  [SKIP] {mode} already completed", flush=True)
                continue
            mode_start = time.time()
            print(f"  [START] {mode}", flush=True)
            row = fn()
            row["evaluation_access"] = args.evaluation_access
            rows.append(row)
            append_csv_row(row, output_csv)
            completed.add(key)
            elapsed = time.time() - mode_start
            print(
                f"  [DONE] {mode} syntax_ok={row['syntax_ok']} functional_ok={row['functional_ok']} elapsed={elapsed:.1f}s",
                flush=True,
            )
    end = time.time()
    summary = summarize(rows)

    print("Reflect Ablation Summary")
    print("========================")
    for mode, stats in summary.items():
        print(
            f"{mode:<18} total={stats['total']} "
            f"syntax={stats['syntax']} functional={stats['functional']}"
        )
    print(f"\nCSV saved to {output_csv}")
    print(f"Elapsed: {end - start:.2f}s")


if __name__ == "__main__":
    main()
