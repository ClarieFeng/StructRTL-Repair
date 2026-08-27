# Result Provenance

## Main matrix

`results/reference/main/run_manifest.csv` maps each standardized CSV to its original filename. The released matrix contains seven models on Author135 and Benchmark1. Each case records `origin`, `reflect_patch`, and `reflect_rag_skeleton`, producing 1,512 case evaluations per condition.

Reference totals are:

| Mode | Syntax passes | Functional passes |
|---|---:|---:|
| origin | 330 | 43 |
| reflect_patch | 829 | 406 |
| reflect_rag_skeleton | 1,232 | 986 |

## Mechanism, seed, runtime, and synthesis records

- `results/reference/component/` contains the unified Benchmark1 mechanism matrix and its summaries.
- `results/reference/seed/` contains aligned target subset runs for MiniCPM and Qwen3 under seeds 1234, 2234, and 3234.
- `results/reference/runtime/` contains case level elapsed time and executed round summaries.
- `results/reference/synthesis/` contains the limited Yosys follow up for Qwen3, Llama 3.2, and InternVL3.5.
- `results/reference/supplementary/` contains standalone baseline summaries, visual controls, the aligned SFT evaluation, and the LLaVA compact target subset.

Reference results support audit and analysis reproduction. A newly executed run belongs under `reproduced/` and must retain its resolved configuration, histories, public feedback audit, and source commit.
