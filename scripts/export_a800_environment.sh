#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODELS="configs/model_paths.local.yaml"
OUTPUT="environment/a800_lock"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --models) MODELS="$2"; shift 2 ;;
    --output-dir) OUTPUT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

python scripts/collect_environment.py --models "$MODELS" --output-dir "$OUTPUT"
echo "Review the generated files before committing them. Absolute model paths are excluded."
