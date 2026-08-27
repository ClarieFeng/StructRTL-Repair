"""Run one case or one dataset condition through the frozen public protocol."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from release_common import BACKENDS, FROZEN_DIR, REPO_ROOT, materialize_legacy_dataset, parse_case_id, read_json


PRINCIPAL_MODES = ("origin", "reflect_patch", "reflect_rag_skeleton")


def sanitize_text(text: str, replacements: dict[str, str]) -> str:
    sanitized = text
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if source:
            sanitized = sanitized.replace(source, target)
    sanitized = re.sub(r"/home/[^/\s]+", "<home>", sanitized)
    sanitized = re.sub(r"[A-Za-z]:\\Users\\[^\\\s]+", "<home>", sanitized)
    return sanitized


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=sorted(BACKENDS))
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--dataset", required=True, choices=("author135", "benchmark1"))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", action="append", dest="cases")
    group.add_argument("--preset", choices=("full",))
    parser.add_argument("--modes", default=",".join(PRINCIPAL_MODES))
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--protocol", default=str(REPO_ROOT / "configs" / "frozen_protocol.json"))
    parser.add_argument("--evaluation-access", default="public_only", choices=("public_only",))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    modes = tuple(item.strip() for item in args.modes.split(",") if item.strip())
    if modes != PRINCIPAL_MODES:
        raise SystemExit("The frozen paired runner requires modes: " + ",".join(PRINCIPAL_MODES))

    protocol_path = Path(args.protocol).expanduser().resolve()
    protocol = read_json(protocol_path)
    if protocol.get("evaluation_access") != "public_only":
        raise SystemExit("Released runs require evaluation_access=public_only in the protocol.")
    if int(protocol["workflow"]["max_outer_rounds"]) != 3:
        raise SystemExit("Frozen workflow requires exactly three outer rounds.")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_cases = args.cases or None
    if selected_cases:
        for case_id in selected_cases:
            parse_case_id(case_id)

    staged_root = (output_dir / "runtime_dataset").resolve()
    if staged_root.parent != output_dir:
        raise SystemExit(f"Unsafe runtime dataset path: {staged_root}")
    if staged_root.exists():
        import shutil
        shutil.rmtree(staged_root)
    try:
        staged = materialize_legacy_dataset(args.dataset, staged_root, selected_cases)
        cases_arg = ",".join(f"{m}:{t}" for m, t in map(parse_case_id, staged))
        output_csv = output_dir / "results.csv"
        backend = FROZEN_DIR / BACKENDS[args.model]
        rag_path = REPO_ROOT / "src" / "structrtl_repair" / "knowledge" / "error_repair_library.jsonl"
        command = [
            sys.executable,
            str(backend),
            "--base-directory",
            str(staged_root),
            "--model-path",
            str(Path(args.model_path).expanduser()),
            "--cases",
            cases_arg,
            "--output-csv",
            str(output_csv),
            "--seed",
            str(args.seed),
            "--strategy-profile",
            "benchmark_clean",
            "--evaluation-access",
            "public_only",
            "--rag-path",
            str(rag_path),
            "--origin-max-new-tokens",
            str(protocol["generation"]["initial_max_new_tokens"]),
        ]
        if args.fresh:
            command.append("--fresh")

        replacements = {
            str(REPO_ROOT): "<repo>",
            str(staged_root): "<runtime_dataset>",
            str(output_dir): "<output_dir>",
            str(Path(args.model_path).expanduser()): "<model_path>",
            sys.executable: "<python>",
        }
        display_command = [sanitize_text(item, replacements) for item in command]

        run_config = {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "model": args.model,
            "model_path_basename": Path(args.model_path).expanduser().name,
            "dataset": args.dataset,
            "cases": staged,
            "modes": list(modes),
            "seed": args.seed,
            "evaluation_access": "public_only",
            "protocol": protocol,
            "backend": backend.name,
            "command": display_command,
            "status": "planned" if args.dry_run else "running",
        }
        config_path = output_dir / "run_config.json"
        config_path.write_text(json.dumps(run_config, indent=2) + "\n", encoding="utf-8")
        print(" ".join(display_command), flush=True)
        if args.dry_run:
            return

        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(FROZEN_DIR) + os.pathsep + environment.get("PYTHONPATH", "")
        process = subprocess.Popen(
            command,
            cwd=FROZEN_DIR,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(sanitize_text(line.rstrip("\n"), replacements), flush=True)
        returncode = process.wait()
        run_config["status"] = "complete" if returncode == 0 else "failed"
        run_config["returncode"] = returncode
        config_path.write_text(json.dumps(run_config, indent=2) + "\n", encoding="utf-8")
        if returncode:
            raise SystemExit(returncode)
    finally:
        if staged_root.exists() and staged_root.parent == output_dir:
            import shutil
            shutil.rmtree(staged_root)


if __name__ == "__main__":
    main()
