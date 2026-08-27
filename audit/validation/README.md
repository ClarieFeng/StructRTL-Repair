# Runtime Validation Evidence

This directory contains sanitized summaries returned from the original A800
environment on 2026-08-23.

- `final_repository_validation.json` records dataset coverage, result row
  counts, checksum status, and the personal path scan.
- `qwen3_smoke_validation.json`, `minicpm_smoke_validation.json`, and
  `internvl_smoke_validation.json` record three row model smoke checks and
  shared initial candidate comparisons.
- The corresponding `*_public_feedback_audit.json` files record public only
  artifact audits with zero findings.
- The `*_smoke_results.csv` and `*_smoke_run_config.json` files provide the
  sanitized one case outcomes and resolved protocols.
- `a800_three_backend_repository_validation.json` records the repository
  validation after all three adapter runs.
- `toy_demo_history.json` and `toy_demo_selected.v` record the model free CPU
  demonstration validated with Icarus Verilog.

The toy demo validates framework control and EDA integration. The three smoke
records validate real VLM execution through the generic, MiniCPM, and InternVL
adapter families. None of these records is included in the paper's
effectiveness totals.

The returned InternVL configuration and public feedback audit recorded
`public_only`, while its CSV writer omitted the same metadata from individual
rows. The released CSV fills that metadata field from the immutable run
configuration. The adapter now records the field directly, and the release
validator requires agreement between the configuration and every result row.
