# A800 Validation Result

Validation date: 2026-08-23

## Environment

- GPU: NVIDIA A800 80GB PCIe
- Python: 3.10.20
- PyTorch: 2.8.0+cu128
- Transformers: 4.57.6
- Icarus Verilog: 14.0 devel, revision s20260301-172-g311c22e4d-dirty
- Yosys: 0.65+71, revision e56c6a954
- netlistsvg: 1.0.2

## No model validation

The public contract boundary tests, Author135 image regeneration, Icarus
Verilog smoke test, environment sanitation, integrity ledger, and repository
validator passed. The repository validator reported 135 Author135 cases, 81
Benchmark1 cases, 4,536 principal result rows, no checksum mismatch, and no
personal path finding.

## Model smoke validation

The public runners executed Benchmark1 `module02/test1` with seed 1234 under
the frozen image and generation protocol. Qwen3 exercised the generic adapter.
MiniCPM and InternVL exercised their dedicated adapters. Every run produced
one row for each principal condition and passed the shared initial candidate,
public feedback, and artifact path audits.

| Adapter | Origin | Generic patching | Complete framework |
|---|---|---|---|
| Qwen3 | syntax pass, functional fail | syntax pass, functional fail | functional pass |
| MiniCPM | syntax fail | functional pass | functional pass |
| InternVL | syntax fail | functional pass | functional pass |

These records validate released execution paths and the public only
information boundary. They serve as integration checks and are excluded from
the paper's effectiveness totals. MiniCPM used the available attention backend
because FlashAttention2 was not installed. This changes execution efficiency,
not the frozen task contract or verification policy.

Returned smoke archive SHA256:
`d33e833a11237541717eeff6f055392bd0fe506dc3cab2ad43e5eb5e373e56d6`.

Returned three adapter validation archive SHA256:
`1695e063ad5adbabea7cc66c300f1e416b147573c725461d82649a5ddeed1ce9`.
