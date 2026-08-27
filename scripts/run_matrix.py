"""Launch frozen main, component, or seed matrices from a YAML specification."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from release_common import BACKENDS, FROZEN_DIR, REPO_ROOT, materialize_legacy_dataset, resolve_model_paths


def load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("PyYAML is required for matrix execution.") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["kind", "model", "dataset", "seed", "output", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_command(command: list[str], log_path: Path, dry_run: bool) -> int:
    replacements = {str(REPO_ROOT): "<repo>", sys.executable: "<python>"}
    for flag, token in (("--model-path", "<model_path>"), ("--base-directory", "<runtime_dataset>"), ("--output-dir", "<output_dir>"), ("--output-csv", "<output_csv>")):
        if flag in command:
            index = command.index(flag)
            if index + 1 < len(command):
                replacements[command[index + 1]] = token

    def sanitize(text: str) -> str:
        for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
            text = text.replace(source, target)
        text = re.sub(r"/home/[^/\s]+", "<home>", text)
        text = re.sub(r"[A-Za-z]:\\Users\\[^\\\s]+", "<home>", text)
        return text

    print(sanitize(" ".join(command)), flush=True)
    if dry_run:
        return 0
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=os.environ.copy(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert process.stdout is not None
        for line in process.stdout:
            log.write(sanitize(line))
            log.flush()
        return process.wait()


def main_or_seed(
    kind: str,
    matrix: dict,
    model_paths: dict[str, str],
    output_dir: Path,
    fresh: bool,
    dry_run: bool,
) -> list[dict[str, str]]:
    rows = []
    datasets = [matrix["dataset"]] if "dataset" in matrix else list(matrix["datasets"])
    seeds = list(matrix.get("seeds", [matrix.get("seed", 1234)]))
    cases = list(matrix.get("cases", []))
    protocol = REPO_ROOT / matrix.get("protocol", "configs/frozen_protocol.json")
    for model in matrix["models"]:
        if model not in model_paths:
            raise SystemExit(f"Missing model path for {model}")
        for dataset in datasets:
            for seed in seeds:
                name = f"{model}_{dataset}" if kind == "main" else f"{model}_{dataset}_seed{seed}"
                run_dir = output_dir / name
                command = [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "run_case.py"),
                    "--model", model,
                    "--model-path", model_paths[model],
                    "--dataset", dataset,
                    "--modes", ",".join(matrix["modes"]),
                    "--seed", str(seed),
                    "--protocol", str(protocol),
                    "--evaluation-access", "public_only",
                    "--output-dir", str(run_dir),
                ]
                if cases:
                    for case_id in cases:
                        command.extend(["--case", case_id])
                else:
                    command.extend(["--preset", "full"])
                if fresh:
                    command.append("--fresh")
                if dry_run:
                    command.append("--dry-run")
                code = run_command(command, output_dir / "logs" / f"{name}.log", dry_run)
                rows.append({
                    "kind": kind,
                    "model": model,
                    "dataset": dataset,
                    "seed": str(seed),
                    "output": run_dir.relative_to(output_dir).as_posix(),
                    "status": "planned" if dry_run else ("complete" if code == 0 else "failed"),
                })
                write_manifest(output_dir / "run_manifest.csv", rows)
                if code:
                    raise SystemExit(code)
    return rows


def component(
    matrix: dict,
    model_paths: dict[str, str],
    output_dir: Path,
    fresh: bool,
    dry_run: bool,
) -> list[dict[str, str]]:
    dataset = matrix.get("dataset", "benchmark1")
    seed = int(matrix.get("seed", 1234))
    staged_root = (output_dir / "runtime_dataset").resolve()
    if staged_root.parent != output_dir:
        raise SystemExit(f"Unsafe runtime dataset path: {staged_root}")
    if staged_root.exists():
        shutil.rmtree(staged_root)
    materialize_legacy_dataset(dataset, staged_root)
    rows = []
    try:
        for model in matrix["models"]:
            if model not in model_paths:
                raise SystemExit(f"Missing model path for {model}")
            output_csv = output_dir / model / "results.csv"
            backend = Path(BACKENDS[model]).stem
            command = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "run_unified_mechanism_ablation.py"),
                "--runner-module", backend,
                "--runner-module-dir", str(FROZEN_DIR),
                "--model-path", model_paths[model],
                "--model-label", model,
                "--base-directory", str(staged_root),
                "--rag-path", str(REPO_ROOT / "src/structrtl_repair/knowledge/error_repair_library.jsonl"),
                "--output-csv", str(output_csv),
                "--preset", "full",
                "--seed", str(seed),
                "--strategy-profile", "benchmark_clean",
                "--evaluation-access", "public_only",
                "--origin-max-new-tokens", "1536",
            ]
            if fresh:
                command.append("--fresh")
            code = run_command(command, output_dir / "logs" / f"{model}_{dataset}.log", dry_run)
            rows.append({
                "kind": "component",
                "model": model,
                "dataset": dataset,
                "seed": str(seed),
                "output": output_csv.relative_to(output_dir).as_posix(),
                "status": "planned" if dry_run else ("complete" if code == 0 else "failed"),
            })
            write_manifest(output_dir / "run_manifest.csv", rows)
            if code:
                raise SystemExit(code)
    finally:
        if staged_root.exists() and staged_root.parent == output_dir:
            shutil.rmtree(staged_root)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", required=True, choices=("main", "component", "seed"))
    parser.add_argument("--models", required=True, help="Local model path YAML.")
    parser.add_argument("--matrix")
    parser.add_argument("--subset")
    parser.add_argument("--dataset")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--seeds")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    spec_path = Path(args.subset or args.matrix or "").expanduser().resolve()
    if not spec_path.is_file():
        raise SystemExit("A valid --matrix or --subset YAML is required.")
    matrix = load_yaml(spec_path)
    if args.dataset:
        matrix["dataset"] = args.dataset
    if args.seed is not None:
        matrix["seed"] = args.seed
    if args.seeds:
        matrix["seeds"] = [int(value) for value in args.seeds.split(",")]
    model_paths = resolve_model_paths(Path(args.models).expanduser().resolve())
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.kind == "component":
        component(matrix, model_paths, output_dir, args.fresh, args.dry_run)
    else:
        main_or_seed(args.kind, matrix, model_paths, output_dir, args.fresh, args.dry_run)


if __name__ == "__main__":
    main()
