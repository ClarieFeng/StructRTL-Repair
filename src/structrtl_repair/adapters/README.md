# Public Model Adapters

The public wrapper selects one of three frozen backend families: generic VLM,
MiniCPM, or InternVL. Model identifiers and backend mappings are defined in
`scripts/release_common.py`. Local weight paths are supplied through the CLI or
`configs/model_paths.local.yaml` and are never stored in released run records.

Adapter behavior remains in `../frozen/` so the release layer does not modify
model loading or generation semantics. End to end adapter validation is
performed by `scripts/validate_a800_model_smoke.sh`.
