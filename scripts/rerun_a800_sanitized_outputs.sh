#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p reproduced/validation_logs
LOG="reproduced/validation_logs/sanitized_outputs_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "[1/5] Boundary and release unit tests"
python -m unittest discover -s tests -v

echo "[2/5] Sanitized Icarus Verilog smoke report"
python scripts/smoke_eda.py \
  --dataset benchmark1 \
  --case module02/test1 \
  --output reproduced/smoke_eda.json

echo "[3/5] Sanitized A800 environment lock"
bash scripts/export_a800_environment.sh \
  --models configs/model_paths.local.yaml \
  --output-dir environment/a800_lock

echo "[4/5] Refresh integrity ledger"
python scripts/refresh_integrity.py --repository-root .

echo "[5/5] Repository validation"
python scripts/validate_release.py \
  --repository-root . \
  --manifest audit/release_manifest.csv \
  --checksums audit/source_checksums.sha256 \
  --expected audit/expected_coverage.json

echo "Sanitized A800 output validation: PASS"
echo "Log: $LOG"
