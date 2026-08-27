#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p reproduced/validation_logs
LOG="reproduced/validation_logs/no_model_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "[1/7] Python syntax"
python -m compileall -q scripts tests src/structrtl_repair/frozen

echo "[2/7] Boundary and release unit tests"
python -m unittest discover -s tests -v

echo "[3/7] Missing Author135 image regeneration"
bash scripts/regenerate_author135_image.sh

echo "[4/7] Icarus Verilog smoke test"
python scripts/smoke_eda.py \
  --dataset benchmark1 \
  --case module02/test1 \
  --output reproduced/smoke_eda.json

echo "[5/7] A800 environment lock"
bash scripts/export_a800_environment.sh \
  --models configs/model_paths.local.yaml \
  --output-dir environment/a800_lock

echo "[6/7] Refresh integrity ledger"
python scripts/refresh_integrity.py --repository-root .

echo "[7/7] Repository validation"
python scripts/validate_release.py \
  --repository-root . \
  --manifest audit/release_manifest.csv \
  --checksums audit/source_checksums.sha256 \
  --expected audit/expected_coverage.json

echo "No model A800 validation: PASS"
echo "Log: $LOG"
