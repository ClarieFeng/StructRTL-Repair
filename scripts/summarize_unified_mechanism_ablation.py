"""Validate and summarize unified StructRTL-Repair mechanism ablations."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


MODE_ORDER = (
    "origin_shared",
    "reflect_patch",
    "reflect_patch_rag",
    "reflect_patch_rag_skeleton_nogate",
    "reflect_full",
    "reflect_constraint_only",
    "reflect_builtin_skeleton_gate",
)

CONTRASTS = (
    ("rag_over_patch", "reflect_patch", "reflect_patch_rag"),
    (
        "skeleton_over_rag",
        "reflect_patch_rag",
        "reflect_patch_rag_skeleton_nogate",
    ),
    (
        "gate_over_rag_skeleton",
        "reflect_patch_rag_skeleton_nogate",
        "reflect_full",
    ),
    ("constraint_over_patch", "reflect_patch", "reflect_constraint_only"),
    (
        "external_library_over_builtin",
        "reflect_builtin_skeleton_gate",
        "reflect_full",
    ),
)


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def exact_two_sided_mcnemar(gain: int, loss: int) -> float:
    discordant = gain + loss
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, k) for k in range(0, min(gain, loss) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def holm_adjust(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=p_values.__getitem__)
    adjusted = [1.0] * len(p_values)
    running = 0.0
    count = len(p_values)
    for rank, index in enumerate(order):
        value = min(1.0, (count - rank) * p_values[index])
        running = max(running, value)
        adjusted[index] = running
    return adjusted


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, help="MODEL=CSV")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-cases", type=int, default=81)
    args = parser.parse_args()

    inputs: list[tuple[str, Path]] = []
    for value in args.input:
        if "=" not in value:
            raise ValueError(f"Expected MODEL=CSV, received: {value}")
        model, filename = value.split("=", 1)
        inputs.append((model, Path(filename).resolve()))

    output_dir = Path(args.output_dir).resolve()
    all_rows: dict[str, list[dict[str, str]]] = {}
    audit_findings: list[str] = []
    audit_warnings: list[str] = []
    mode_summary: list[dict[str, object]] = []
    profile_rows: list[dict[str, object]] = []
    significance_rows: list[dict[str, object]] = []

    for model, path in inputs:
        rows = read_rows(path)
        all_rows[model] = rows
        keyed: dict[tuple[int, int, str], dict[str, str]] = {}
        hashes: dict[tuple[int, int], set[str]] = defaultdict(set)
        for row in rows:
            case = (int(row["module_id"]), int(row["test_id"]))
            key = (*case, row["mode"])
            if key in keyed:
                audit_findings.append(f"{model}: duplicate row {key}")
            keyed[key] = row
            hashes[case].add(row.get("shared_initial_hash", ""))
            if row["mode"] != "origin_shared" and not as_bool(
                row.get("shared_initial_match", "")
            ):
                audit_findings.append(f"{model}: initial replay mismatch {key}")
            if row["mode"] != "origin_shared" and not as_bool(
                row.get("natural_replay_match", "")
            ):
                audit_warnings.append(f"{model}: nondeterministic natural replay {key}")

        case_set = {(module, test) for module, test, _ in keyed}
        if len(case_set) != args.expected_cases:
            audit_findings.append(
                f"{model}: expected {args.expected_cases} cases, found {len(case_set)}"
            )
        for case, values in hashes.items():
            if len(values) != 1 or "" in values:
                audit_findings.append(f"{model}: inconsistent initial hash {case}")
        for mode in MODE_ORDER:
            selected = [row for row in rows if row["mode"] == mode]
            if len(selected) != args.expected_cases:
                audit_findings.append(
                    f"{model}: mode {mode} has {len(selected)} rows"
                )
            total = len(selected)
            syntax = sum(as_bool(row["syntax_ok"]) for row in selected)
            functional = sum(as_bool(row["functional_ok"]) for row in selected)
            rounds = [float(row["num_iterations"]) for row in selected if row["num_iterations"]]
            mode_summary.append(
                {
                    "model": model,
                    "mode": mode,
                    "total": total,
                    "syntax_pass": syntax,
                    "syntax_rate": syntax / total if total else 0.0,
                    "functional_pass": functional,
                    "functional_rate": functional / total if total else 0.0,
                    "avg_iterations": sum(rounds) / len(rounds) if rounds else 0.0,
                }
            )

        functional_by_mode = {
            mode: sum(
                as_bool(row["functional_ok"]) for row in rows if row["mode"] == mode
            )
            for mode in MODE_ORDER
        }
        profile_rows.append(
            {
                "model": model,
                "n": len(case_set),
                "patch_functional": functional_by_mode["reflect_patch"],
                "rag_functional": functional_by_mode["reflect_patch_rag"],
                "rag_delta": functional_by_mode["reflect_patch_rag"]
                - functional_by_mode["reflect_patch"],
                "rag_skeleton_functional": functional_by_mode[
                    "reflect_patch_rag_skeleton_nogate"
                ],
                "skeleton_delta": functional_by_mode[
                    "reflect_patch_rag_skeleton_nogate"
                ]
                - functional_by_mode["reflect_patch_rag"],
                "full_functional": functional_by_mode["reflect_full"],
                "gate_delta": functional_by_mode["reflect_full"]
                - functional_by_mode["reflect_patch_rag_skeleton_nogate"],
                "constraint_only_functional": functional_by_mode[
                    "reflect_constraint_only"
                ],
                "constraint_delta": functional_by_mode["reflect_constraint_only"]
                - functional_by_mode["reflect_patch"],
                "builtin_only_functional": functional_by_mode[
                    "reflect_builtin_skeleton_gate"
                ],
                "external_library_delta": functional_by_mode["reflect_full"]
                - functional_by_mode["reflect_builtin_skeleton_gate"],
            }
        )

        raw_stats: list[dict[str, object]] = []
        for contrast, baseline_mode, treatment_mode in CONTRASTS:
            gain = loss = tied_pass = tied_fail = 0
            for case in case_set:
                baseline = as_bool(keyed[(*case, baseline_mode)]["functional_ok"])
                treatment = as_bool(keyed[(*case, treatment_mode)]["functional_ok"])
                if treatment and not baseline:
                    gain += 1
                elif baseline and not treatment:
                    loss += 1
                elif treatment:
                    tied_pass += 1
                else:
                    tied_fail += 1
            raw_stats.append(
                {
                    "model": model,
                    "contrast": contrast,
                    "baseline_mode": baseline_mode,
                    "treatment_mode": treatment_mode,
                    "gain": gain,
                    "loss": loss,
                    "tied_pass": tied_pass,
                    "tied_fail": tied_fail,
                    "net_gain": gain - loss,
                    "p_exact": exact_two_sided_mcnemar(gain, loss),
                }
            )
        adjusted = holm_adjust([float(row["p_exact"]) for row in raw_stats])
        for row, p_holm in zip(raw_stats, adjusted):
            row["p_holm_within_model"] = p_holm
            significance_rows.append(row)

    write_csv(output_dir / "unified_mode_summary.csv", mode_summary)
    write_csv(output_dir / "unified_mechanism_profile.csv", profile_rows)
    write_csv(output_dir / "unified_paired_significance.csv", significance_rows)
    audit = {
        "status": "PASS" if not audit_findings else "FAIL",
        "models": len(inputs),
        "expected_cases_per_model": args.expected_cases,
        "findings": audit_findings,
        "warnings": audit_warnings,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "unified_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(f"Audit: {audit['status']}; findings: {len(audit_findings)}")
    print(f"Natural replay warnings: {len(audit_warnings)}")
    print(f"Models: {len(inputs)}")
    print(f"Output: {output_dir}")
    if audit_findings:
        for finding in audit_findings[:20]:
            print(f"  {finding}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
