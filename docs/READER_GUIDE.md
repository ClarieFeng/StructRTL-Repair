# Reader Guide

This guide provides three entry paths through the StructRTL-Repair artifact.

## 1. Paper reviewer without model weights

Start with the following files:

1. `README.md` defines the artifact scope and the three reproduction levels.
2. `datasets/DATA_CARD.md` explains Author135, Benchmark1, and the separation between public tasks and evaluator assets.
3. `configs/frozen_protocol.json` records the model independent experimental settings.
4. `results/expected/` contains the table level values used by the manuscript.
5. `audit/validation/` contains sanitized A800 checks for the generic, MiniCPM, and InternVL adapter families.

Run the five minute control loop with real Icarus Verilog verification:

```bash
conda env create -f environment-demo.yml
conda activate structrtl-repair-demo
./run_demo.sh
```

The final lines should match `examples/toy_demo/expected_output.txt`. This demo validates framework control and EDA integration without measuring model quality.

## 2. Evidence and analysis reviewer

Install the analysis dependencies and regenerate the reported summaries from released case level records:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-analysis.txt
python scripts/reproduce_analysis.py \
  --reference-root results/reference \
  --output-dir reproduced/analysis \
  --strict
```

Validate dataset coverage, result counts, checksums, and path sanitation:

```bash
python scripts/validate_release.py \
  --repository-root . \
  --manifest audit/release_manifest.csv \
  --checksums audit/source_checksums.sha256 \
  --expected audit/expected_coverage.json \
  --strict
```

The analysis path requires no GPU. A successful strict run writes `reproduced/analysis/analysis_audit.json` with `status` set to `PASS`. `docs/RESULT_PROVENANCE.md` maps released evidence to its source experiment family.

## 3. Independent model reproduction

Read `docs/MODEL_SETUP.md`, obtain model weights from their providers, and create the ignored local path configuration:

```bash
bash scripts/configure_model_paths.sh --model-root /path/to/model-root
```

Begin with one case and the three principal modes:

```bash
bash scripts/validate_a800_model_smoke.sh \
  --model qwen3_vl_8b \
  --model-path /path/to/Qwen3-VL-8B-Instruct \
  --output-dir reproduced/smoke
```

After the smoke run passes, use `scripts/run_case.py` for a selected benchmark condition or the matrix launchers for the main, component, and seed studies. Each public runner enforces `evaluation_access=public_only`.

## Audit boundary

The model reads only `datasets/*/public/`. The verifier reads the isolated evaluator assets and releases permitted status or sanitized category evidence. `docs/INFORMATION_BOUNDARY.md` defines this boundary, while `scripts/audit_public_evaluation_run.py` checks reproduced histories and logs.

## Licensing and citation

The software uses Apache License 2.0. Author135 retains the upstream MGEMMV MIT License. Benchmark1 uses CC BY 4.0. Cite the artifact using `CITATION.cff` and preserve the dataset specific attribution described in `LICENSE_SCOPE.md`.
