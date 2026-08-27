#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
SMOKE_DIR="${1:-reproduced/smoke_qwen3_vl_8b}"

echo "[1/6] Public feedback audit"
python scripts/audit_public_evaluation_run.py \
  --experiment-root "$SMOKE_DIR" \
  --output "$SMOKE_DIR/public_feedback_audit.json"

echo "[2/6] Generated artifact path sanitation"
python scripts/sanitize_artifact_paths.py --root reproduced

echo "[3/6] Model smoke validation"
python scripts/validate_release.py \
  --run-dir "$SMOKE_DIR" \
  --expected-cases 1 \
  --require-shared-initial \
  --require-public-only

echo "[4/6] Stable A800 environment lock"
bash scripts/export_a800_environment.sh \
  --models configs/model_paths.local.yaml \
  --output-dir environment/a800_lock

echo "[5/6] Refresh integrity ledger"
python scripts/refresh_integrity.py --repository-root .

echo "[6/6] Repository validation"
python scripts/validate_release.py \
  --repository-root . \
  --manifest audit/release_manifest.csv \
  --checksums audit/source_checksums.sha256 \
  --expected audit/expected_coverage.json

echo "Final A800 validation: PASS"
