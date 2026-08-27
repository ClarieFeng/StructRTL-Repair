# Source Inventory

This file records where the local staging repository was assembled from. It is a release engineering record, not a runtime dependency.

| Release area | Local source | Notes |
|---|---|---|
| Frozen workflow | A800 archive `evaluation/TestSet/python` | Public protocol variants and model adapters |
| Error Library | A800 archive `evaluation/TestSet/python/error_repair_library.jsonl` | JSONL repair knowledge |
| Author135 | A800 archive `evaluation/TestSet` | Repacked into public and evaluator views |
| Benchmark1 | A800 archive `benchmark_clean_expansion/results/staged_eval_dataset_81_clean` | Repacked into public and evaluator views |
| Main reference results | `hp_tmp/4ablation-sum` and A800 InternVL results | Fourteen model and dataset runs, sanitized CSV copies |
| Component results | A800 archive `results/rq2_unified_mechanism/20260807_1234` | Seven Benchmark1 model runs |
| Seed results | A800 archive `results/random_seed_generalization` | MiniCPM and Qwen3 target subset |
| Runtime summaries | Current project `results/runtime_iteration_cost_analysis_with_time` | Derived from run logs and histories |
| Synthesis audit | A800 archive `results/synthesis_qor_followup` | Three Benchmark1 model audits |
| Standalone baselines | Current project `results/baselines` | CSV and workbook summaries only |
| Visual controls | A800 archive `results/rq1_multimodal` | Single pass analysis and MiniCPM target subset workflow |
| Aligned SFT | A800 archive `results/sft_internalization/qwen25_aligned_author_holdout_test1_20260730_2122` | Case CSVs, split audits, and derived summaries without adapter weights |
| LLaVA compact | A800 archive `results/llava_v6_2_compact` | Final target subset CSV and log |

Local archiving utilities are stored outside this repository in `paper_single_agent_workflow/release_build_tools`. They contain workstation specific source locations and must not be uploaded.
