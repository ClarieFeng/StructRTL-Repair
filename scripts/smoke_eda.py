"""Run a no-model Icarus Verilog smoke test with a released golden candidate."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from release_common import REPO_ROOT, parse_case_id, read_manifest, sanitize_public_text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="benchmark1", choices=("author135", "benchmark1"))
    parser.add_argument("--case", default="module02/test1")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--output", default="reproduced/smoke_eda.json")
    args = parser.parse_args()

    if not shutil.which("iverilog") or not shutil.which("vvp"):
        raise SystemExit("iverilog and vvp must be available in PATH")
    row = next((item for item in read_manifest(args.dataset) if item["case_id"] == args.case), None)
    if row is None:
        raise SystemExit(f"Unknown case: {args.case}")
    dataset_root = REPO_ROOT / "datasets" / args.dataset
    evaluator = dataset_root / "evaluator" / f"module{int(row['module_id']):02d}" / f"test{row['test_id']}"
    golden = [dataset_root / value for value in row.get("golden_files", "").split(";") if value.endswith("primary.v")]
    if len(golden) != 1 or not golden[0].is_file():
        raise SystemExit(f"Case does not expose one golden primary.v: {args.case}")

    with tempfile.TemporaryDirectory(prefix="structrtl_eda_smoke_") as temp:
        temp_root = Path(temp)
        sources = []
        for source in evaluator.glob("*.v"):
            destination = temp_root / source.name
            shutil.copy2(source, destination)
            sources.append(destination)
        candidate = temp_root / "candidate.v"
        shutil.copy2(golden[0], candidate)
        sources.append(candidate)
        executable = temp_root / "out.vvp"
        compile_result = subprocess.run(
            ["iverilog", "-o", str(executable), "-y", str(temp_root), "-s", "tb", "-I", str(temp_root)]
            + [str(path) for path in sources],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        simulation_output = ""
        simulation_returncode = None
        if compile_result.returncode == 0:
            simulation = subprocess.run(
                ["vvp", str(executable)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=args.timeout,
            )
            simulation_output = simulation.stdout
            simulation_returncode = simulation.returncode
        match = re.search(r"(?:Pass(?:ed)? rate|Accuracy):\s*([0-9.]+)%", simulation_output, re.I)
        functional_pass = bool(match and float(match.group(1)) == 100.0)

    report = {
        "schema_version": 1,
        "dataset": args.dataset,
        "case": args.case,
        "candidate": "released golden primary.v",
        "compile_returncode": compile_result.returncode,
        "simulation_returncode": simulation_returncode,
        "functional_pass": functional_pass,
        "compile_output": sanitize_public_text(compile_result.stdout),
        "simulation_summary": "functional_pass" if functional_pass else "functional_fail",
    }
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"EDA smoke: {'PASS' if functional_pass else 'FAIL'}")
    print(f"Report: {output}")
    if not functional_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
