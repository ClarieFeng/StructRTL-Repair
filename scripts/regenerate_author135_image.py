"""Regenerate the missing Author135 module26/test4 circuit image with provenance."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "module26/test4"
SOURCE_JSON = (
    REPO_ROOT
    / "datasets"
    / "author135"
    / "evaluator"
    / "module26"
    / "test4"
    / "PE_row_16_22bit.json"
)
PUBLIC_CASE = (
    REPO_ROOT
    / "datasets"
    / "author135"
    / "public"
    / "module26"
    / "test4"
)
MANIFEST = REPO_ROOT / "datasets" / "author135" / "manifest.csv"
EXPECTED_COVERAGE = REPO_ROOT / "audit" / "expected_coverage.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_version(command: str) -> str:
    executable = shutil.which(command)
    if not executable:
        return "unavailable"
    for flag in ("--version", "-V"):
        result = subprocess.run(
            [executable, flag],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        output = result.stdout.strip()
        if output:
            return output.splitlines()[0]
    return "version_not_reported"


def render_jpeg(svg_path: Path, jpg_path: Path, dpi: int) -> None:
    try:
        from reportlab.graphics import renderPM
        from svglib.svglib import svg2rlg
    except ImportError as exc:
        raise SystemExit(
            "JPEG conversion requires svglib and reportlab. "
            "Install the frozen environment before rerunning."
        ) from exc

    drawing = svg2rlg(str(svg_path))
    if drawing is None:
        raise RuntimeError(f"Could not parse generated SVG: {svg_path}")
    renderPM.drawToFile(drawing, str(jpg_path), fmt="JPEG", dpi=dpi)


def update_manifest(image_path: str) -> None:
    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"Empty manifest: {MANIFEST}")
    columns = list(rows[0])
    matched = False
    for row in rows:
        if row["case_id"] == CASE_ID:
            row["circuit_image"] = image_path
            matched = True
    if not matched:
        raise RuntimeError(f"Case absent from manifest: {CASE_ID}")
    with MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netlistsvg", default="netlistsvg")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--keep-svg", action="store_true")
    args = parser.parse_args()

    if not SOURCE_JSON.is_file():
        raise SystemExit(f"Missing source netlist: {SOURCE_JSON}")
    executable = shutil.which(args.netlistsvg)
    if not executable:
        raise SystemExit(f"netlistsvg executable not found: {args.netlistsvg}")

    PUBLIC_CASE.mkdir(parents=True, exist_ok=True)
    svg_path = PUBLIC_CASE / "circuit.svg"
    jpg_path = PUBLIC_CASE / "circuit.jpg"
    subprocess.run(
        [executable, str(SOURCE_JSON), "-o", str(svg_path)],
        check=True,
    )
    render_jpeg(svg_path, jpg_path, args.dpi)

    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("Image validation requires Pillow.") from exc
    with Image.open(jpg_path) as image:
        width, height = image.size
        image.verify()

    provenance = {
        "case_id": CASE_ID,
        "status": "regenerated_from_released_yosys_json",
        "source": "datasets/author135/evaluator/module26/test4/PE_row_16_22bit.json",
        "source_sha256": sha256(SOURCE_JSON),
        "renderer": "netlistsvg",
        "renderer_version": command_version(args.netlistsvg),
        "conversion": "svglib.svg2rlg + reportlab.renderPM JPEG",
        "dpi": args.dpi,
        "width": width,
        "height": height,
        "image": "datasets/author135/public/module26/test4/circuit.jpg",
        "image_sha256": sha256(jpg_path),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    provenance_path = PUBLIC_CASE / "image_provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    update_manifest("public/module26/test4/circuit.jpg")
    expected = json.loads(EXPECTED_COVERAGE.read_text(encoding="utf-8"))
    expected["datasets"]["author135"]["public_images_current"] = 135
    EXPECTED_COVERAGE.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")

    missing_marker = PUBLIC_CASE / "missing_image.json"
    if missing_marker.exists():
        missing_marker.unlink()
    if not args.keep_svg:
        svg_path.unlink(missing_ok=True)

    print(f"Image: {jpg_path}")
    print(f"SHA256: {provenance['image_sha256']}")
    print(f"Dimensions: {width}x{height}")
    print(f"Provenance: {provenance_path}")


if __name__ == "__main__":
    main()
