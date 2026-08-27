"""Validate a staged repository or a newly reproduced StructRTL-Repair run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


PRINCIPAL_MODES = {"origin", "reflect_patch", "reflect_rag_skeleton"}
LOCAL_ONLY_FILES = {"configs/model_paths.local.yaml"}
PERSONAL_PATH = re.compile(r"(?:/home/[A-Za-z0-9._-]+|[A-Za-z]:\\Users\\[^\\]+)")
TEXT_SUFFIXES = {".json", ".jsonl", ".csv", ".log", ".md", ".txt", ".py", ".sh", ".yaml", ".yml"}


def find_personal_paths(root: Path, ignored: set[str] | None = None) -> list[str]:
    ignored = ignored or set()
    findings = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        if relative in ignored:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if PERSONAL_PATH.search(text):
            findings.append(relative)
    return findings


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_run(args: argparse.Namespace) -> dict:
    root = Path(args.run_dir).resolve()
    findings: list[str] = []
    config_path = root / "run_config.json"
    result_path = root / "results.csv"
    if not config_path.is_file():
        findings.append("missing run_config.json")
        config = {}
    else:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    if not result_path.is_file():
        findings.append("missing results.csv")
        rows: list[dict[str, str]] = []
    else:
        rows = csv_rows(result_path)

    if args.require_public_only and config.get("evaluation_access") != "public_only":
        findings.append("run did not enforce public_only")
    if args.require_public_only:
        non_public_rows = [
            row for row in rows
            if row.get("evaluation_access") != "public_only"
        ]
        if non_public_rows:
            findings.append(
                f"result rows without public_only metadata: {len(non_public_rows)}"
            )
        audit_path = root / "public_feedback_audit.json"
        if not audit_path.is_file():
            findings.append("missing public_feedback_audit.json")
        else:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            if audit.get("status") != "PASS":
                findings.append("public feedback audit did not pass")
    keys = [(row.get("mode"), row.get("module_id"), row.get("test_id")) for row in rows]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    if duplicates:
        findings.append(f"duplicate mode/case rows: {len(duplicates)}")
    observed_modes = {row.get("mode") for row in rows}
    if rows and observed_modes != PRINCIPAL_MODES:
        findings.append(f"unexpected principal modes: {sorted(observed_modes)}")
    if args.expected_cases is not None:
        expected_rows = args.expected_cases * len(PRINCIPAL_MODES)
        if len(rows) != expected_rows:
            findings.append(f"results rows {len(rows)} != expected {expected_rows}")

    shared_checks = 0
    shared_mismatches = 0
    if args.require_shared_initial:
        experiment = root / "experiments" / "results" / "cases"
        for module_dir in sorted(experiment.glob("module*")):
            for test_dir in sorted(module_dir.glob("test*")):
                raw_files = {}
                for mode in ("reflect_patch", "reflect_rag_skeleton"):
                    candidates = list(test_dir.glob(f"reflect_result_{mode}_*/iter_0.txt"))
                    if len(candidates) == 1:
                        raw_files[mode] = candidates[0]
                if len(raw_files) == 2:
                    shared_checks += 1
                    if sha256(raw_files["reflect_patch"]) != sha256(raw_files["reflect_rag_skeleton"]):
                        shared_mismatches += 1
        if shared_checks == 0:
            findings.append("no paired initial generation artifacts found")
        if shared_mismatches:
            findings.append(f"shared initial mismatches: {shared_mismatches}")

    path_findings = find_personal_paths(root)
    if path_findings:
        findings.append(f"personal path findings: {len(path_findings)}")

    return {
        "kind": "run",
        "status": "PASS" if not findings else "FAIL",
        "rows": len(rows),
        "shared_initial_checks": shared_checks,
        "path_findings": path_findings,
        "findings": findings,
    }


def parse_checksum_file(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split(maxsplit=1)
        values[relative.strip().replace("\\", "/")] = digest.lower()
    return values


def validate_repository(args: argparse.Namespace) -> dict:
    root = Path(args.repository_root).resolve()
    expected = json.loads((root / args.expected).read_text(encoding="utf-8"))
    findings: list[str] = []
    dataset_summary = {}
    for dataset, wanted in expected["datasets"].items():
        rows = csv_rows(root / "datasets" / dataset / "manifest.csv")
        modules = {row["module_id"] for row in rows}
        image_count = 0
        for row in rows:
            for key in ("description", "interface_contract", "testbench"):
                if not (root / "datasets" / dataset / row[key]).is_file():
                    findings.append(f"missing {dataset} {row['case_id']} {key}")
            image_value = row.get("circuit_image", "").strip()
            if image_value and (root / "datasets" / dataset / image_value).is_file():
                image_count += 1
        if len(rows) != int(wanted["cases"]):
            findings.append(f"{dataset} cases {len(rows)} != {wanted['cases']}")
        if len(modules) != int(wanted["modules"]):
            findings.append(f"{dataset} modules {len(modules)} != {wanted['modules']}")
        if image_count != int(wanted["public_images_expected"]):
            findings.append(
                f"{dataset} public images {image_count} != {wanted['public_images_expected']}"
            )
        dataset_summary[dataset] = {"cases": len(rows), "modules": len(modules), "images": image_count}

    main_files = sorted((root / "results" / "reference" / "main").glob("*.csv"))
    main_rows = [
        row
        for path in main_files
        for row in csv_rows(path)
        if row.get("mode") in PRINCIPAL_MODES
    ]
    main_expected = expected["main_results"]
    if len(main_rows) != int(main_expected["expected_rows"]):
        findings.append(f"main rows {len(main_rows)} != {main_expected['expected_rows']}")
    mode_counts = Counter(row.get("mode") for row in main_rows)
    for mode in PRINCIPAL_MODES:
        if mode_counts[mode] != int(main_expected["case_evaluations_per_mode"]):
            findings.append(f"main mode {mode} has {mode_counts[mode]} rows")

    checksum_path = root / args.checksums
    checksum_mismatches = []
    if checksum_path.is_file():
        for relative, wanted_hash in parse_checksum_file(checksum_path).items():
            file_path = root / relative
            if not file_path.is_file() or sha256(file_path) != wanted_hash:
                checksum_mismatches.append(relative)
        if checksum_mismatches:
            findings.append(f"checksum mismatches: {len(checksum_mismatches)}")
    else:
        findings.append("missing checksum file")

    manifest_path = root / args.manifest
    manifest_rows = csv_rows(manifest_path) if manifest_path.is_file() else []
    if not manifest_rows:
        findings.append("missing or empty release manifest")
    else:
        manifest_mismatches = 0
        for row in manifest_rows:
            file_path = root / row["path"]
            if not file_path.is_file() or sha256(file_path) != row["sha256"].lower():
                manifest_mismatches += 1
        if manifest_mismatches:
            findings.append(f"release manifest mismatches: {manifest_mismatches}")

    path_findings = find_personal_paths(root, LOCAL_ONLY_FILES)
    if path_findings:
        findings.append(f"personal path findings: {len(path_findings)}")

    if args.strict:
        if (root / "LICENSE_SELECTION_REQUIRED.md").exists() or not (root / "LICENSE").is_file():
            findings.append("repository license is not finalized")
        benchmark_license = root / "datasets" / "benchmark1" / "LICENSE"
        cc_by_legal_code = root / "licenses" / "CC-BY-4.0.txt"
        if not benchmark_license.is_file() or "CC BY 4.0" not in benchmark_license.read_text(
            encoding="utf-8", errors="ignore"
        ):
            findings.append("Benchmark1 CC BY 4.0 license is not finalized")
        if not cc_by_legal_code.is_file():
            findings.append("CC BY 4.0 legal code is missing")
        if not (root / "CITATION.cff").is_file():
            findings.append("CITATION.cff is not finalized")

    return {
        "kind": "repository",
        "status": "PASS" if not findings else "FAIL",
        "datasets": dataset_summary,
        "main_rows": len(main_rows),
        "mode_counts": dict(mode_counts),
        "checksum_mismatches": checksum_mismatches,
        "path_findings": path_findings,
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--run-dir")
    scope.add_argument("--repository-root")
    parser.add_argument("--expected-cases", type=int)
    parser.add_argument("--require-shared-initial", action="store_true")
    parser.add_argument("--require-public-only", action="store_true")
    parser.add_argument("--manifest", default="audit/release_manifest.csv")
    parser.add_argument("--checksums", default="audit/source_checksums.sha256")
    parser.add_argument("--expected", default="audit/expected_coverage.json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    report = validate_run(args) if args.run_dir else validate_repository(args)
    serialized = json.dumps(report, indent=2)
    print(serialized)
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized + "\n", encoding="utf-8")
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
