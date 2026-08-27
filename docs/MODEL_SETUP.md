# Model Setup

Model weights are not redistributed. Download each model from its original provider and generate the ignored local configuration with:

```bash
bash scripts/configure_model_paths.sh --model-root /path/to/model-root
```

The command validates the expected folder names before writing
`configs/model_paths.local.yaml`.

The main matrix uses seven model identifiers:

- `mgemmv_qwen_7b`
- `mgemmv_llama_11b`
- `qwen2_5_vl_7b`
- `qwen3_vl_8b`
- `llama3_2_11b_vision`
- `minicpm_v_4_5_8b`
- `internvl3_5_8b`

The first five identifiers use the generic backend family in the frozen experiment code. MiniCPM and InternVL require their dedicated processor and model loading paths. The generic Qwen3 path and both dedicated paths pass public only model smoke validation. Sanitized package versions, CUDA details, model configuration hashes, and remote code hashes from the original A800 environment are stored in `environment/a800_lock/`.

All published commands must keep the model path outside logs, CSV files, and histories. A resolved run configuration should record the model identifier and immutable model revision without exposing a workstation path.
