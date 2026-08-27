"""Refresh the release file inventory and SHA256 checksum ledger."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", "__pycache__", "reproduced"}
EXCLUDED_FILES = {
    "audit/release_manifest.csv",
    "audit/source_checksums.sha256",
    "configs/model_paths.local.yaml",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def category(relative: Path) -> str:
    return relative.parts[0] if len(relative.parts) > 1 else "repository"


def redistribution_status(relative: Path) -> str:
    text = relative.as_posix()
    if text.startswith("datasets/author135/"):
        return "upstream_mit"
    if text.startswith("datasets/benchmark1/"):
        return "project_authored_data_license_pending"
    if text.startswith("results/reference/"):
        return "project_output"
    return "apache-2.0"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=str(REPO_ROOT))
    args = parser.parse_args()
    root = Path(args.repository_root).resolve()
    if not (root / "README.md").is_file() or not (root / "audit").is_dir():
        raise SystemExit(f"Not a StructRTL-Repair repository: {root}")

    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        relative_text = relative.as_posix()
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if relative_text in EXCLUDED_FILES or path.suffix == ".pyc":
            continue
        rows.append({
            "path": relative_text,
            "category": category(relative),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "redistribution_status": redistribution_status(relative),
        })

    manifest = root / "audit" / "release_manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    checksums = root / "audit" / "source_checksums.sha256"
    checksums.write_text(
        "".join(f"{row['sha256']}  {row['path']}\n" for row in rows),
        encoding="utf-8",
    )
    print(f"Release files: {len(rows)}")
    print(f"Manifest: {manifest}")
    print(f"Checksums: {checksums}")


if __name__ == "__main__":
    main()
