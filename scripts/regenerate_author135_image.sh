#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v netlistsvg >/dev/null || {
  echo "ERROR: netlistsvg is not available in PATH" >&2
  exit 2
}

python - <<'PY'
import importlib.util

required = ("PIL", "reportlab", "svglib")
missing = [name for name in required if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit("ERROR: missing Python packages: " + ", ".join(missing))
PY

python scripts/regenerate_author135_image.py --dpi 150

python - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path.cwd()
case = root / "datasets/author135/public/module26/test4"
image = case / "circuit.jpg"
provenance = json.loads((case / "image_provenance.json").read_text(encoding="utf-8"))
actual = hashlib.sha256(image.read_bytes()).hexdigest()
assert actual == provenance["image_sha256"], (actual, provenance["image_sha256"])
print("Author135 module26/test4 image validation: PASS")
print(f"image_sha256={actual}")
PY
