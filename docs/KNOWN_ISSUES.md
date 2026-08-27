# Known Issues Before Public Release

## Runtime validation scope

The generic Qwen3 adapter and the dedicated MiniCPM and InternVL adapters pass one case public only smoke validation for all three principal modes. These runs validate adapter integration, the shared initial comparison, and the public feedback boundary. They are not included in the paper's effectiveness totals.

The CPU toy demo uses deterministic candidate replay with real Icarus Verilog verification. It validates the control loop and public evaluator boundary without representing VLM inference performance.

## Verified information boundary

All three frozen backends guard `infer_expected_top_from_tb` with `is_public_only()` and return the active public contract before filesystem access. `tests/test_public_contract_boundary.py` exercises this branch with a path object that raises on every read. The test passes in the A800 inference environment.

The decoding discrepancy is resolved. Archived workflow sources use `top_p=0.9`; `top_p=0.95` belongs to the separate visual control study. See `docs/PROTOCOL_PROVENANCE.md`.

## Release hygiene items

1. Add the GitHub repository URL and archival DOI to `CITATION.cff` when available.

## Completed staging controls

- Personal source paths were replaced in result CSVs, run logs, Yosys scripts, and netlist metadata.
- The current scan reports zero source usernames, Unix home prefixes, or Windows user paths.
- Raw manuscript files and `paper_evidence_private` are absent from the staged repository.
- Author135 `module26/test4` was regenerated from the released Yosys JSON with
  netlistsvg 1.0.2 and passed image hash validation.
- The A800 Icarus Verilog smoke test passed.
- The Qwen3 public only model smoke test passed. It produced three aligned mode rows, one shared initial candidate comparison, and no private feedback findings.
- The MiniCPM and InternVL public only model smoke tests passed under their dedicated adapters with the same three mode structure and no private feedback findings.
- Sanitized A800 environment exports and all returned validation evidence pass the final personal path scan.
