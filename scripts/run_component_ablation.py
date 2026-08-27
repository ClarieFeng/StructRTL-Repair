"""Run the five-mode StructRTL-Repair component ablation.

The selected backend module must expose the stable ablation API implemented by
the frozen model-specific runners: parse_cases, run_origin_case,
run_agent_case, append_csv_row, load_existing_rows, summarize, SCRIPT_DIR,
BENCHMARK_CLEAN, and ORACLE_DEBUG.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import time
from pathlib import Path
from types import ModuleType


def load_backend(name: str, module_dir: str) -> ModuleType:
    if module_dir:
        import sys

        resolved = str(Path(module_dir).resolve())
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
    backend = importlib.import_module(name)
    required = (
        "SCRIPT_DIR",
        "BENCHMARK_CLEAN",
        "ORACLE_DEBUG",
        "append_csv_row",
        "get_experiment_root",
        "load_existing_rows",
        "parse_cases",
        "run_agent_case",
        "run_origin_case",
        "summarize",
    )
    missing = [attribute for attribute in required if not hasattr(backend, attribute)]
    if missing:
        raise AttributeError(f"Backend {name!r} lacks: {', '.join(missing)}")
    return backend


def planned_modes(
    backend: ModuleType,
    base_path: Path,
    module_id: int,
    test_id: int,
    case_seed: int,
    args: argparse.Namespace,
    rag_path: Path | None,
    experiment_root: Path,
):
    def agent(
        mode: str,
        *,
        skeleton: bool,
        domain_knowledge: bool,
    ):
        return lambda: backend.run_agent_case(
            base_path,
            module_id,
            test_id,
            mode=mode,
            enable_patch=True,
            enable_skeleton=skeleton,
            enable_domain_knowledge=domain_knowledge,
            seed=case_seed,
            rag_path=rag_path if domain_knowledge else None,
            experiment_root=experiment_root,
            strategy_profile=args.strategy_profile,
        )

    return [
        (
            "origin",
            lambda: backend.run_origin_case(
                base_path,
                module_id,
                test_id,
                case_seed,
                args.origin_max_new_tokens,
            ),
        ),
        (
            "reflect_patch",
            agent("reflect_patch", skeleton=False, domain_knowledge=False),
        ),
        (
            "reflect_patch_rag",
            agent("reflect_patch_rag", skeleton=False, domain_knowledge=True),
        ),
        (
            "reflect_patch_skeleton",
            agent("reflect_patch_skeleton", skeleton=True, domain_knowledge=False),
        ),
        (
            "reflect_rag_skeleton",
            agent("reflect_rag_skeleton", skeleton=True, domain_knowledge=True),
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runner-module",
        default="ablation_v6_2",
        help="Frozen backend module, e.g. ablation_v6_2_minicpm.",
    )
    parser.add_argument(
        "--runner-module-dir",
        default="",
        help="Directory containing the frozen backend module.",
    )
    parser.add_argument("--base-directory", required=True)
    parser.add_argument("--model-path", default="")
    parser.add_argument("--cases", default="")
    parser.add_argument(
        "--preset", choices=["small", "expanded", "full"], default="small"
    )
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument(
        "--strategy-profile",
        choices=["benchmark_clean", "oracle_debug"],
        default="benchmark_clean",
    )
    parser.add_argument("--rag-path", default="")
    parser.add_argument("--origin-max-new-tokens", type=int, default=1536)
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()

    if args.model_path:
        os.environ["MGEMMV_MODEL_PATH"] = args.model_path
    backend = load_backend(args.runner_module, args.runner_module_dir)

    base_path = Path(args.base_directory).resolve()
    output_csv = Path(args.output_csv).resolve()
    experiment_root = backend.get_experiment_root(output_csv)
    rag_path = Path(args.rag_path).resolve() if args.rag_path else None
    if rag_path and not rag_path.is_file():
        raise FileNotFoundError(rag_path)
    cases = backend.parse_cases(args.cases, args.preset, base_path)

    if args.fresh:
        if output_csv.exists():
            output_csv.unlink()
        if experiment_root.exists():
            shutil.rmtree(experiment_root)

    rows, completed = backend.load_existing_rows(output_csv)
    print(f"[INFO] Backend: {args.runner_module}", flush=True)
    print(f"[INFO] Base path: {base_path}", flush=True)
    print(f"[INFO] Output CSV: {output_csv}", flush=True)
    print(f"[INFO] Cases: {len(cases)}", flush=True)

    start = time.time()
    for case_index, (module_id, test_id) in enumerate(cases):
        case_seed = args.seed + case_index * 100
        print(
            f"\n[CASE {case_index + 1}/{len(cases)}] "
            f"module{module_id}/test{test_id} seed={case_seed}",
            flush=True,
        )
        for mode, function in planned_modes(
            backend,
            base_path,
            module_id,
            test_id,
            case_seed,
            args,
            rag_path,
            experiment_root,
        ):
            key = (mode, module_id, test_id)
            if key in completed:
                print(f"  [SKIP] {mode}", flush=True)
                continue
            mode_start = time.time()
            print(f"  [START] {mode}", flush=True)
            row = function()
            rows.append(row)
            backend.append_csv_row(row, output_csv)
            completed.add(key)
            print(
                f"  [DONE] {mode} syntax_ok={row['syntax_ok']} "
                f"functional_ok={row['functional_ok']} "
                f"elapsed={time.time() - mode_start:.1f}s",
                flush=True,
            )

    print("Component Ablation Summary")
    print("==========================")
    for mode, stats in backend.summarize(rows).items():
        print(
            f"{mode:<24} total={stats['total']} "
            f"syntax={stats['syntax']} functional={stats['functional']}"
        )
    print(f"CSV saved to {output_csv}")
    print(f"Elapsed: {time.time() - start:.2f}s")


if __name__ == "__main__":
    main()
