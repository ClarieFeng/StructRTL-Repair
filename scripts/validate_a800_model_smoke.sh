#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL=""
MODEL_PATH=""
OUTPUT="reproduced/smoke"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --model-path) MODEL_PATH="$2"; shift 2 ;;
    --output-dir) OUTPUT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
if [[ -z "$MODEL" || -z "$MODEL_PATH" ]]; then
  echo "Usage: $0 --model MODEL_ID --model-path PATH [--output-dir DIR]" >&2
  exit 2
fi

mkdir -p "$OUTPUT/logs"
LOG="$OUTPUT/logs/model_smoke_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

python scripts/run_case.py \
  --model "$MODEL" \
  --model-path "$MODEL_PATH" \
  --dataset benchmark1 \
  --case module02/test1 \
  --modes origin,reflect_patch,reflect_rag_skeleton \
  --protocol configs/frozen_protocol.json \
  --evaluation-access public_only \
  --output-dir "$OUTPUT" \
  --fresh

python scripts/audit_public_evaluation_run.py \
  --experiment-root "$OUTPUT" \
  --output "$OUTPUT/public_feedback_audit.json"

python scripts/sanitize_artifact_paths.py --root "$OUTPUT"

python scripts/validate_release.py \
  --run-dir "$OUTPUT" \
  --expected-cases 1 \
  --require-shared-initial \
  --require-public-only

echo "Model smoke validation: PASS"
echo "Log: $LOG"
