# A800 Validation Sequence

Run these checks from the repository root in the original inference
environment.

## 1. Configure model paths

Generate the ignored local configuration from the common model root:

```bash
bash scripts/configure_model_paths.sh \
  --model-root ~/data/hp_llm/jiahui_models
```

The command validates all seven model directories before writing
`configs/model_paths.local.yaml`. The local file is excluded from release
checks and Git.

## 2. No model validation

```bash
bash scripts/validate_a800_no_model.sh
```

This command runs Python compile checks, boundary tests, regeneration of the
missing Author135 image, an Icarus Verilog smoke test, environment export,
checksum refresh, and repository validation.

## 3. Model smoke validation

```bash
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

bash scripts/validate_a800_model_smoke.sh \
  --model qwen3_vl_8b \
  --model-path /path/to/Qwen3-VL-8B-Instruct \
  --output-dir reproduced/smoke
```

The smoke run executes `origin`, `reflect_patch`, and
`reflect_rag_skeleton` on `Benchmark1 module02/test1`, audits public feedback,
checks the three result rows, and compares the persisted initial generation
for the two repair conditions.

## 4. Files to review

- `reproduced/validation_logs/no_model_*.log`
- `datasets/author135/public/module26/test4/image_provenance.json`
- `reproduced/smoke_eda.json`
- `environment/a800_lock/runtime_lock.json`
- `environment/a800_lock/model_revisions.json`
- `reproduced/smoke/public_feedback_audit.json`
- `reproduced/smoke/run_config.json`
- `reproduced/smoke/results.csv`
