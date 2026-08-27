#!/usr/bin/env bash
set -euo pipefail

ROOT=""
OUTPUT="configs/model_paths.local.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-root)
      ROOT="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$ROOT" ]]; then
  echo "Usage: bash scripts/configure_model_paths.sh --model-root MODEL_ROOT [--output PATH]" >&2
  exit 2
fi

ROOT="$(cd "$ROOT" && pwd)"

declare -A MODEL_DIRS=(
  [mgemmv_qwen_7b]="MGEMMV-Qwen-7b"
  [mgemmv_llama_11b]="MGEMMV-Llama-11b"
  [qwen2_5_vl_7b]="Qwen2.5-VL-7B-Instruct"
  [qwen3_vl_8b]="Qwen3-VL-8B-Instruct"
  [llama3_2_11b_vision]="Llama-3.2-11B-Vision-Instruct"
  [minicpm_v_4_5_8b]="MiniCPM-V-4_5-8B"
  [internvl3_5_8b]="InternVL3_5-8B-Instruct"
)

ORDER=(
  mgemmv_qwen_7b
  mgemmv_llama_11b
  qwen2_5_vl_7b
  qwen3_vl_8b
  llama3_2_11b_vision
  minicpm_v_4_5_8b
  internvl3_5_8b
)

mkdir -p "$(dirname "$OUTPUT")"
{
  echo "models:"
  for key in "${ORDER[@]}"; do
    path="$ROOT/${MODEL_DIRS[$key]}"
    if [[ ! -d "$path" ]]; then
      echo "Missing model directory: $path" >&2
      exit 1
    fi
    printf '  %s: %s\n' "$key" "$path"
  done
} > "$OUTPUT"

echo "Model path configuration: $OUTPUT"
echo "Validated model directories: ${#ORDER[@]}"
