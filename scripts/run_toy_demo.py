"""Run a model free, tool grounded StructRTL-Repair demonstration."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from release_common import REPO_ROOT


CASE = "benchmark1/module02/test1"
PRIVATE_MARKERS = re.compile(
    r"(?:mismatch!|expected\s*[{:=]|pass(?:ed)? rate:|starting testbench|golden_result)",
    re.IGNORECASE,
)


def candidate_gate(source: str, contract: dict) -> tuple[bool, list[str]]:
    module = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)", source)
    violations = []
    if not module or module.group(1) != contract["top_module"]:
        violations.append("top_module")
    header = source.split(");", 1)[0]
    for port in ("A", "B", "cin", "S", "cout"):
        if not re.search(rf"\b{re.escape(port)}\b", header):
            violations.append(f"missing_port:{port}")
    return not violations, violations


def run_command(command: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )


def verify(source: str, evaluator: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="structrtl_demo_") as temp:
        root = Path(temp)
        candidate = root / "candidate.v"
        candidate.write_text(source, encoding="utf-8")
        syntax = run_command(["iverilog", "-g2012", "-tnull", str(candidate)])
        if syntax.returncode:
            return {
                "stage": "syntax",
                "syntax": False,
                "functional": False,
                "public_observation": "syntax_verilog2001",
            }
        executable = root / "out.vvp"
        compile_result = run_command(
            ["iverilog", "-g2012", "-s", "tb", "-o", str(executable), str(evaluator), str(candidate)]
        )
        if compile_result.returncode:
            return {
                "stage": "compile",
                "syntax": True,
                "functional": False,
                "public_observation": "compilation_failure",
            }
        simulation = run_command(["vvp", str(executable)])
        match = re.search(r"Pass rate:\s*([0-9.]+)%", simulation.stdout, re.IGNORECASE)
        functional = bool(simulation.returncode == 0 and match and float(match.group(1)) == 100.0)
        return {
            "stage": "functional",
            "syntax": True,
            "functional": functional,
            "public_observation": "pass" if functional else "functional_wrong_arithmetic",
        }


def retrieve_rule(category: str) -> dict:
    library = REPO_ROOT / "src" / "structrtl_repair" / "knowledge" / "error_repair_library.jsonl"
    for line in library.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("category") == category:
            return record
    raise KeyError(category)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="reproduced/toy_demo")
    args = parser.parse_args()

    for tool in ("iverilog", "vvp"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} is required. Create environment-demo.yml first.")

    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    public = REPO_ROOT / "datasets" / "benchmark1" / "public" / "module02" / "test1"
    evaluator = REPO_ROOT / "datasets" / "benchmark1" / "evaluator" / "module02" / "test1" / "tb.v"
    fixtures = REPO_ROOT / "examples" / "toy_demo" / "candidates"
    contract = json.loads((public / "interface_contract.json").read_text(encoding="utf-8"))
    image_hash = hashlib.sha256((public / "circuit.jpg").read_bytes()).hexdigest()
    candidates = [(fixtures / "round0.v").read_text(encoding="utf-8"), (fixtures / "round1.v").read_text(encoding="utf-8")]

    print("StructRTL-Repair CPU toy demo")
    print(f"Case: {CASE}")
    print("Backend: deterministic candidate replay")
    history = []
    best = {"score": 0, "round": 0, "source": ""}
    for index, source in enumerate(candidates, start=1):
        gate_ok, violations = candidate_gate(source, contract)
        result = verify(source, evaluator) if gate_ok else {
            "stage": "gate",
            "syntax": False,
            "functional": False,
            "public_observation": "interface_violation",
        }
        score = 2 if result["functional"] else 1 if result["syntax"] else 0
        if score > best["score"]:
            best = {"score": score, "round": index, "source": source}
        entry = {
            "round": index,
            "gate": "pass" if gate_ok else "fail",
            "gate_violations": violations,
            "stage": result["stage"],
            "syntax": bool(result["syntax"]),
            "functional": bool(result["functional"]),
            "public_observation": result["public_observation"],
        }
        print(
            f"Round {index}: gate={entry['gate']} "
            f"syntax={'pass' if entry['syntax'] else 'fail'} "
            f"functional={'pass' if entry['functional'] else 'fail'}"
        )
        if result["functional"]:
            entry["action"] = "early_stop"
            history.append(entry)
            break
        rule = retrieve_rule(str(result["public_observation"]))
        entry.update(
            {
                "retrieved_category": rule["category"],
                "family_skeleton": "self_contained_ppa_adder",
                "action": "regenerate_self_contained",
            }
        )
        history.append(entry)
        print(f"  evidence={rule['category']} action=regenerate_self_contained")

    (output / "selected.v").write_text(str(best["source"]), encoding="utf-8")
    report = {
        "schema_version": 1,
        "demo_scope": "model_free_control_loop_with_real_eda",
        "case": CASE,
        "public_image_sha256": image_hash,
        "max_rounds": 3,
        "executed_rounds": len(history),
        "selected_round": best["round"],
        "selected_score": best["score"],
        "functional_pass": best["score"] == 2,
        "history": history,
    }
    serialized = json.dumps(report, indent=2) + "\n"
    if PRIVATE_MARKERS.search(serialized):
        raise SystemExit("Public feedback audit: FAIL")
    (output / "history.json").write_text(serialized, encoding="utf-8")
    print(f"Selected: round {best['round']}, score {best['score']}")
    print("Public feedback audit: PASS")
    if best["score"] != 2:
        raise SystemExit("DEMO FAIL")
    print("DEMO PASS")


if __name__ == "__main__":
    main()
