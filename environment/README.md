# Environment Lock

`environment-demo.yml` at the repository root provides the minimal CPU demo
environment with Python 3.10.20 and Icarus Verilog 12.0. `environment.yml`
pins the core Python packages used by model inference and analysis.

Run `scripts/export_a800_environment.sh` inside the original A800 inference
environment to generate the complete machine lock. It records exact Python
packages, CUDA and EDA tool versions, GPU information, model configuration
metadata, and hashes of local remote code files. Local model paths are
represented only by directory names.

The validated A800 export is stored in `environment/a800_lock`. The final
export shell did not activate the separately bundled netlistsvg executable,
so `runtime_lock.json` records that command as unavailable. Image regeneration
was independently validated with netlistsvg 1.0.2 and is documented in
`audit/A800_VALIDATION_RESULT.md` and the image provenance record.
