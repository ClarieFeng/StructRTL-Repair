"""Run the unified StructRTL-Repair mechanism ablation with paired initials.

This runner reuses a frozen model-specific ablation backend and changes only
the mechanism switches around it.  Every repair condition receives the exact
same initial model output for a case.  The independently regenerated initial
output is hashed as an audit check before the persisted shared output is used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import inspect
import json
import os
import shutil
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable, Iterator


@dataclass(frozen=True)
class MechanismConfig:
    mode: str
    label: str
    rag: bool
    skeleton: bool
    gate: bool
    external_library: bool


CONFIGS = (
    MechanismConfig("reflect_patch", "Patch", False, False, False, False),
    MechanismConfig("reflect_patch_rag", "Patch + RAG", True, False, False, True),
    MechanismConfig(
        "reflect_patch_rag_skeleton_nogate",
        "Patch + RAG + Skeleton",
        True,
        True,
        False,
        True,
    ),
    MechanismConfig("reflect_full", "Full", True, True, True, True),
    MechanismConfig(
        "reflect_constraint_only",
        "Patch + Skeleton + Gate",
        False,
        True,
        True,
        False,
    ),
    MechanismConfig(
        "reflect_builtin_skeleton_gate",
        "Full without external library",
        True,
        True,
        True,
        False,
    ),
)

AUDIT_FIELDS = [
    "model_label",
    "backend_module",
    "configuration_label",
    "mechanism_rag",
    "mechanism_skeleton",
    "mechanism_gate",
    "external_library",
    "run_seed",
    "case_seed",
    "shared_initial_hash",
    "replay_initial_hash",
    "natural_replay_match",
    "shared_initial_match",
    "mode_elapsed_seconds",
]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def load_backend(name: str, module_dir: str) -> ModuleType:
    resolved = str(Path(module_dir).resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    backend = importlib.import_module(name)
    required = (
        "CSV_FIELDS",
        "SCRIPT_DIR",
        "clean_generated_code",
        "generate_code_with_limits",
        "get_experiment_root",
        "parse_cases",
        "run_agent_case",
        "run_origin_case",
        "run_single_case",
    )
    missing = [item for item in required if not hasattr(backend, item)]
    if missing:
        raise AttributeError(f"Backend {name!r} lacks: {', '.join(missing)}")
    return backend


def install_minicpm_signature_compat(backend: ModuleType) -> None:
    """Allow frozen MiniCPM backends to call an older agent signature."""
    run_case = backend.run_single_case
    if "evaluation_access" in inspect.signature(run_case).parameters:
        return
    if "evaluation_access" not in inspect.signature(backend.run_agent_case).parameters:
        return

    def run_case_compat(*args, evaluation_access=None, **kwargs):
        return run_case(*args, **kwargs)

    backend.run_single_case = run_case_compat
    print("[INFO] Enabled legacy MiniCPM signature compatibility.", flush=True)


def get_agent_module(backend: ModuleType) -> ModuleType:
    module_name = backend.run_single_case.__module__
    if module_name not in sys.modules:
        importlib.import_module(module_name)
    return sys.modules[module_name]


@contextmanager
def patched_attribute(module: ModuleType, name: str, value: object) -> Iterator[None]:
    original = getattr(module, name)
    setattr(module, name, value)
    try:
        yield
    finally:
        setattr(module, name, original)


@contextmanager
def gate_policy(agent: ModuleType, enabled: bool) -> Iterator[None]:
    if enabled:
        yield
        return

    def no_interface_gate(candidate, code_dir):
        return candidate, "disabled_for_ablation", "", agent.extract_module_name(candidate)

    def no_programmatic_gate(candidate, code_dir, family, strategy_profile=None):
        return {
            "candidate": candidate,
            "skeleton_action": "disabled_for_ablation",
            "expected_ports": "",
            "port_action": "",
            "static_action": "",
            "static_categories": "",
        }

    with patched_attribute(agent, "apply_interface_gate", no_interface_gate):
        with patched_attribute(
            agent, "apply_programmatic_skeleton_gate", no_programmatic_gate
        ):
            yield


def capture_origin(
    backend: ModuleType,
    function: Callable[[], dict],
) -> tuple[dict, str, str]:
    real_generate = backend.generate_code_with_limits
    captured: list[str] = []

    def capture(*args, **kwargs):
        raw = real_generate(*args, **kwargs)
        captured.append(raw)
        return raw

    with patched_attribute(backend, "generate_code_with_limits", capture):
        row = function()
    if len(captured) != 1:
        raise RuntimeError(f"Expected one origin generation, observed {len(captured)}")
    raw = captured[0]
    candidate = backend.clean_generated_code(raw)
    return row, raw, sha256_text(candidate)


@contextmanager
def replay_shared_initial(
    backend: ModuleType,
    agent: ModuleType,
    shared_raw: str,
    shared_hash: str,
    replay_audit: dict[str, object],
) -> Iterator[None]:
    real_generate = agent.generate_code_with_limits
    calls = 0

    def replay(*args, **kwargs):
        nonlocal calls
        calls += 1
        generated = real_generate(*args, **kwargs)
        if calls != 1:
            return generated
        replay_hash = sha256_text(backend.clean_generated_code(generated))
        replay_audit["replay_initial_hash"] = replay_hash
        replay_audit["natural_replay_match"] = replay_hash == shared_hash
        replay_audit["shared_initial_match"] = True
        return shared_raw

    with patched_attribute(agent, "generate_code_with_limits", replay):
        yield
    if calls < 1:
        raise RuntimeError("Repair mode did not generate an initial candidate")


def shared_paths(experiment_root: Path, module_id: int, test_id: int) -> tuple[Path, Path, Path]:
    root = experiment_root / "shared_initials" / f"module{module_id:02d}_test{test_id:02d}"
    return root / "raw.txt", root / "candidate.v", root / "metadata.json"


def persist_shared_initial(
    backend: ModuleType,
    raw: str,
    shared_hash: str,
    raw_path: Path,
    candidate_path: Path,
    metadata_path: Path,
    metadata: dict[str, object],
) -> None:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw, encoding="utf-8")
    candidate_path.write_text(backend.clean_generated_code(raw), encoding="utf-8")
    metadata_path.write_text(
        json.dumps({**metadata, "shared_initial_hash": shared_hash}, indent=2),
        encoding="utf-8",
    )


def load_rows(path: Path) -> tuple[list[dict[str, object]], set[tuple[str, int, int]]]:
    if not path.exists():
        return [], set()
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    completed = {
        (str(row["mode"]), int(row["module_id"]), int(row["test_id"]))
        for row in rows
    }
    return rows, completed


def append_row(path: Path, fields: list[str], row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    clean = {field: row.get(field, "") for field in fields}
    if "detail" in clean:
        clean["detail"] = str(clean["detail"])[:4000]
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if write_header:
            writer.writeheader()
        writer.writerow(clean)


def write_run_config(path: Path, args: argparse.Namespace, cases: list[tuple[int, int]]) -> None:
    rag_hash = ""
    if args.rag_path:
        rag_hash = hashlib.sha256(Path(args.rag_path).read_bytes()).hexdigest()
    payload = {
        "model_label": args.model_label,
        "model_path": str(Path(args.model_path).resolve()),
        "backend_module": args.runner_module,
        "base_directory": str(Path(args.base_directory).resolve()),
        "rag_path": str(Path(args.rag_path).resolve()) if args.rag_path else "",
        "rag_sha256": rag_hash,
        "seed": args.seed,
        "case_seed_formula": "run_seed + 100 * zero_based_case_index",
        "origin_max_new_tokens": args.origin_max_new_tokens,
        "strategy_profile": args.strategy_profile,
        "evaluation_access": args.evaluation_access,
        "cases": [f"{module}:{test}" for module, test in cases],
        "configurations": [config.__dict__ for config in CONFIGS],
        "environment": {
            key: os.environ.get(key, "")
            for key in (
                "CUDA_VISIBLE_DEVICES",
                "PYTORCH_CUDA_ALLOC_CONF",
                "MGEMMV_IMAGE_STRATEGY",
                "MGEMMV_OVERVIEW_IMAGE_PIXELS",
                "MGEMMV_CROP_IMAGE_PIXELS",
                "MGEMMV_MAX_IMAGE_CROPS",
            )
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner-module", default="ablation_v6_2")
    parser.add_argument("--runner-module-dir", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-label", required=True)
    parser.add_argument("--base-directory", required=True)
    parser.add_argument("--rag-path", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--cases", default="")
    parser.add_argument("--preset", choices=["small", "expanded", "full"], default="full")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--strategy-profile", default="benchmark_clean")
    parser.add_argument(
        "--evaluation-access", choices=["legacy", "public_only"], default="public_only"
    )
    parser.add_argument("--origin-max-new-tokens", type=int, default=1536)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--list-configurations", action="store_true")
    args = parser.parse_args()

    if args.list_configurations:
        for config in CONFIGS:
            print(json.dumps(config.__dict__, sort_keys=True))
        return

    os.environ["MGEMMV_MODEL_PATH"] = args.model_path
    backend = load_backend(args.runner_module, args.runner_module_dir)
    agent = get_agent_module(backend)
    install_minicpm_signature_compat(backend)

    base_path = Path(args.base_directory).resolve()
    rag_path = Path(args.rag_path).resolve()
    output_csv = Path(args.output_csv).resolve()
    if not rag_path.is_file():
        raise FileNotFoundError(rag_path)
    experiment_root = backend.get_experiment_root(output_csv)
    cases = backend.parse_cases(args.cases, args.preset, base_path)

    if args.fresh:
        if output_csv.exists():
            output_csv.unlink()
        if experiment_root.exists():
            shutil.rmtree(experiment_root)
    experiment_root.mkdir(parents=True, exist_ok=True)
    (experiment_root / "logs").mkdir(exist_ok=True)
    (experiment_root / "cases").mkdir(exist_ok=True)
    write_run_config(experiment_root / "run_config.json", args, cases)

    rows, completed = load_rows(output_csv)
    fields = list(dict.fromkeys(list(backend.CSV_FIELDS) + AUDIT_FIELDS))
    print(f"[INFO] Model: {args.model_label}", flush=True)
    print(f"[INFO] Backend: {args.runner_module}", flush=True)
    print(f"[INFO] Cases: {len(cases)}; repair configurations: {len(CONFIGS)}", flush=True)
    print(f"[INFO] Output: {output_csv}", flush=True)

    start = time.time()
    for case_index, (module_id, test_id) in enumerate(cases):
        case_seed = args.seed + case_index * 100
        raw_path, candidate_path, metadata_path = shared_paths(
            experiment_root, module_id, test_id
        )
        origin_key = ("origin_shared", module_id, test_id)
        print(
            f"\n[CASE {case_index + 1}/{len(cases)}] "
            f"module{module_id}/test{test_id} seed={case_seed}",
            flush=True,
        )

        if origin_key not in completed:
            mode_start = time.time()
            print("  [START] origin_shared", flush=True)
            origin_kwargs = {}
            if "evaluation_access" in inspect.signature(
                backend.run_origin_case
            ).parameters:
                origin_kwargs["evaluation_access"] = args.evaluation_access
            origin_row, shared_raw, shared_hash = capture_origin(
                backend,
                lambda: backend.run_origin_case(
                    base_path,
                    module_id,
                    test_id,
                    case_seed,
                    args.origin_max_new_tokens,
                    **origin_kwargs,
                ),
            )
            persist_shared_initial(
                backend,
                shared_raw,
                shared_hash,
                raw_path,
                candidate_path,
                metadata_path,
                {
                    "model_label": args.model_label,
                    "module_id": module_id,
                    "test_id": test_id,
                    "run_seed": args.seed,
                    "case_seed": case_seed,
                },
            )
            origin_row.update(
                {
                    "mode": "origin_shared",
                    "model_label": args.model_label,
                    "backend_module": args.runner_module,
                    "configuration_label": "Shared origin",
                    "evaluation_access": args.evaluation_access,
                    "mechanism_rag": False,
                    "mechanism_skeleton": False,
                    "mechanism_gate": False,
                    "external_library": False,
                    "run_seed": args.seed,
                    "case_seed": case_seed,
                    "shared_initial_hash": shared_hash,
                    "replay_initial_hash": shared_hash,
                    "natural_replay_match": True,
                    "shared_initial_match": True,
                    "mode_elapsed_seconds": round(time.time() - mode_start, 3),
                }
            )
            append_row(output_csv, fields, origin_row)
            rows.append(origin_row)
            completed.add(origin_key)
            print(
                f"  [DONE] origin_shared syntax={origin_row['syntax_ok']} "
                f"functional={origin_row['functional_ok']} hash={shared_hash[:12]}",
                flush=True,
            )
        else:
            if not (raw_path.is_file() and metadata_path.is_file()):
                raise RuntimeError(
                    f"Cannot resume module{module_id}/test{test_id}: shared initial artifact missing"
                )
            shared_raw = raw_path.read_text(encoding="utf-8")
            shared_hash = json.loads(metadata_path.read_text(encoding="utf-8"))[
                "shared_initial_hash"
            ]
            if sha256_text(backend.clean_generated_code(shared_raw)) != shared_hash:
                raise RuntimeError(f"Shared initial hash mismatch: {raw_path}")
            print(f"  [LOAD] origin_shared hash={shared_hash[:12]}", flush=True)

        for config in CONFIGS:
            key = (config.mode, module_id, test_id)
            if key in completed:
                print(f"  [SKIP] {config.mode}", flush=True)
                continue
            mode_start = time.time()
            replay_audit: dict[str, object] = {}
            print(f"  [START] {config.mode}", flush=True)
            selected_rag = rag_path if config.external_library else None
            with gate_policy(agent, config.gate):
                with replay_shared_initial(
                    backend, agent, shared_raw, shared_hash, replay_audit
                ):
                    kwargs = dict(
                        mode=config.mode,
                        enable_patch=True,
                        enable_skeleton=config.skeleton,
                        enable_domain_knowledge=config.rag,
                        seed=case_seed,
                        rag_path=selected_rag,
                        experiment_root=experiment_root,
                        strategy_profile=args.strategy_profile,
                    )
                    if "evaluation_access" in inspect.signature(
                        backend.run_agent_case
                    ).parameters:
                        kwargs["evaluation_access"] = args.evaluation_access
                    row = backend.run_agent_case(
                        base_path, module_id, test_id, **kwargs
                    )
            row.update(
                {
                    "model_label": args.model_label,
                    "backend_module": args.runner_module,
                    "configuration_label": config.label,
                    "evaluation_access": args.evaluation_access,
                    "mechanism_rag": config.rag,
                    "mechanism_skeleton": config.skeleton,
                    "mechanism_gate": config.gate,
                    "external_library": config.external_library,
                    "run_seed": args.seed,
                    "case_seed": case_seed,
                    "shared_initial_hash": shared_hash,
                    "replay_initial_hash": replay_audit.get("replay_initial_hash", ""),
                    "natural_replay_match": replay_audit.get("natural_replay_match", False),
                    "shared_initial_match": replay_audit.get("shared_initial_match", False),
                    "mode_elapsed_seconds": round(time.time() - mode_start, 3),
                }
            )
            append_row(output_csv, fields, row)
            rows.append(row)
            completed.add(key)
            print(
                f"  [DONE] {config.mode} syntax={row['syntax_ok']} "
                f"functional={row['functional_ok']} "
                f"shared_match={row['shared_initial_match']} "
                f"natural_replay={row['natural_replay_match']} "
                f"elapsed={row['mode_elapsed_seconds']:.1f}s",
                flush=True,
            )

    print("\nUnified Mechanism Ablation Summary")
    print("==================================")
    for mode in ("origin_shared",) + tuple(config.mode for config in CONFIGS):
        selected = [row for row in rows if row.get("mode") == mode]
        syntax = sum(parse_bool(row.get("syntax_ok")) for row in selected)
        functional = sum(parse_bool(row.get("functional_ok")) for row in selected)
        print(f"{mode:<40} total={len(selected)} syntax={syntax} functional={functional}")
    print(f"CSV saved to {output_csv}")
    print(f"Elapsed: {time.time() - start:.2f}s")


if __name__ == "__main__":
    main()
