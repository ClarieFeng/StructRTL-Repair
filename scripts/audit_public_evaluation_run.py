"""Audit public only run artifacts for accidental private feedback leakage."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from release_common import sanitize_public_text


PRIVATE_MARKERS = re.compile(
    # A bare "expected" is legitimate in public interface fields such as
    # interface_gate_expected_top. Flag only value-bearing expected output.
    r"(?:mismatch!|\bexpected\s*(?:[:=]|\d|\d+'[bdho])|\bgot\b|starting testbench|test summary|correct outputs:|"
    r"passed tests:|failed tests:|pass(?:ed)? rate:|\btb\.v\b|\bgolden\b)",
    flags=re.IGNORECASE,
)


def text_files(root: Path):
    for pattern in ("history.json", "out.txt", "*.jsonl"):
        yield from root.rglob(pattern)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    root = Path(args.experiment_root).resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    findings: list[dict] = []
    checked = 0
    for path in text_files(root):
        checked += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in PRIVATE_MARKERS.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                {
                    "file": path.relative_to(root).as_posix(),
                    "line": line,
                    "marker": match.group(0),
                }
            )

    report = {
        "protocol": "public_only_artifact_audit_v1",
        "experiment_root": root.name,
        "files_checked": checked,
        "findings": findings,
        "status": "PASS" if not findings else "FAIL",
    }
    output = Path(args.output).resolve() if args.output else root / "public_feedback_audit.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Public feedback audit: {report['status']}")
    print(f"Files checked: {checked}; findings: {len(findings)}")
    print(f"Report: {sanitize_public_text(str(output))}")
    if findings:
        for finding in findings[:20]:
            print(f"  {finding['file']}:{finding['line']} {finding['marker']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
