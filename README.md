# StructRTL-Repair

> **Validated release candidate.** Dataset, information boundary, image regeneration, EDA, environment sanitation, and real model smoke checks pass on the original A800 environment. Qwen3, MiniCPM, and InternVL each cover all three principal modes under the public only protocol. Remaining release metadata is tracked in `docs/KNOWN_ISSUES.md`.

StructRTL-Repair is a tool grounded single agent framework for repairing Verilog generated from circuit diagrams. It converts EDA observations into persistent repair state, selects failure and family knowledge through Error Library RAG, constrains revisions with family Skeletons, enforces mechanical invariants through deterministic Gates, and preserves the strongest verified candidate within a bounded workflow.

This repository accompanies:

> **StructRTL-Repair: A Tool-Grounded Single-Agent Framework for Verilog Generation from Circuit Diagrams**

## Reproducibility objective

The repository is organized for independent experimental reproduction. A reviewer should be able to follow the complete path below:

```text
public circuit task
  -> model adapter
  -> origin or repair condition
  -> Icarus Verilog verification
  -> case CSV and history.json
  -> paired statistics and mechanism summaries
  -> manuscript tables and figures
```

Three reproduction levels are supported.

1. **Smoke reproduction:** run one case through origin, generic patching, and the complete framework.
2. **End to end reproduction:** rerun a benchmark condition with local model weights and independently recompute syntax and functional outcomes.
3. **Analysis reproduction:** regenerate reported statistics, summaries, and figures from released case level reference results without model inference.

Model weights are not redistributed. Reviewers must obtain them from their original providers and accept the corresponding licenses.

## Reader guide

Choose the shortest path that matches your purpose:

1. **Understand the artifact:** read `docs/READER_GUIDE.md`, `datasets/DATA_CARD.md`, and `configs/frozen_protocol.json`.
2. **Check the framework without a model:** create the demo environment and run `./run_demo.sh`.
3. **Audit the reported evidence without a GPU:** inspect `results/expected/`, reproduce the analyses from `results/reference/`, and run the repository validator.
4. **Inspect the information boundary:** read `docs/INFORMATION_BOUNDARY.md` and the returned A800 evidence in `audit/validation/`.
5. **Rerun model inference:** configure local model paths, reproduce one case, and then launch the required experiment matrix.

## Repository contents

```text
StructRTL-Repair/
|-- README.md
|-- LICENSE
|-- LICENSE_SCOPE.md
|-- THIRD_PARTY_NOTICE.md
|-- AUTHORS.md
|-- licenses/
|   |-- MGEMMV-MIT.txt
|   `-- CC-BY-4.0.txt
|-- CITATION.cff
|-- environment.yml
|-- requirements-analysis.txt
|-- configs/
|   |-- frozen_protocol.json
|   |-- model_paths.example.yaml
|   |-- main_matrix.yaml
|   |-- component_matrix.yaml
|   `-- seed_subset.yaml
|-- datasets/
|   |-- author135/
|   |   |-- public/
|   |   |-- evaluator/
|   |   `-- manifest.csv
|   |-- benchmark1/
|   |   |-- public/
|   |   |-- evaluator/
|   |   `-- manifest.csv
|   `-- DATA_CARD.md
|-- src/structrtl_repair/
|   |-- frozen/
|   |-- adapters/
|   `-- knowledge/error_repair_library.jsonl
|-- scripts/
|   |-- run_case.py
|   |-- run_main_matrix.sh
|   |-- run_component_matrix.sh
|   |-- run_seed_study.sh
|   |-- reproduce_analysis.py
|   |-- analyze_paired_significance.py
|   |-- summarize_unified_mechanism_ablation.py
|   |-- summarize_random_seed_generalization.py
|   |-- runtime_iteration_cost_analysis.py
|   |-- run_yosys_generic_qor.py
|   |-- audit_public_evaluation_run.py
|   `-- validate_release.py
|-- results/
|   |-- reference/
|   |   |-- main/
|   |   |-- component/
|   |   |-- seed/
|   |   |-- runtime/
|   |   |-- synthesis/
|   |   `-- supplementary/
|   `-- expected/
|-- reproduced/
|-- docs/
|   |-- REPRODUCE.md
|   |-- MODEL_SETUP.md
|   |-- INFORMATION_BOUNDARY.md
|   `-- RESULT_PROVENANCE.md
`-- audit/
    |-- release_manifest.csv
    |-- source_checksums.sha256
    `-- expected_coverage.json
```

The `frozen/` directory preserves the implementation used by the experiment family. Public wrappers normalize paths and enforce the released protocol without changing repair behavior. Exploratory versions, caches, unrelated model outputs, and manuscript working files are excluded.

## Benchmarks

| Dataset | Modules | Cases per module | Total cases | Role |
|---|---:|---:|---:|---|
| Author135 | 27 | 5 | 135 | Author evaluation set used in the paired main study |
| Benchmark1 | 27 | 3 | 81 | Controlled extension used in the main and mechanism studies |

Each case has a stable identifier of the form `moduleXX/testY`.

### Public task files

The model visible directory contains only the circuit diagram, textual task description, interface contract, and public case metadata.

### Evaluator files

The evaluator directory contains the testbench, oracle or golden material, helper RTL required by the testbench, and synthesis metadata. These assets are released so reviewers can independently recompute functional outcomes.

Publishing evaluator files does not change the inference boundary. The model runner reads `datasets/*/public/`. Only the verifier reads `datasets/*/evaluator/`. The sanitizer converts private compilation and simulation observations into permitted status or category evidence before the workflow constructs a repair state.

Every case manifest records public files, evaluator files, SHA256 hashes, module identity, family label, and redistribution status. Generated candidates, historical outputs, `.vvp` files, and temporary results are excluded from the benchmark package.

## Evaluation information boundary

Every released paper command enforces:

```text
evaluation_access = public_only
```

The release wrapper rejects `legacy` access. Candidate local syntax diagnostics can enter the repair state. Testbench source, hidden vectors, expected outputs, golden RTL, evaluator paths, and private helper implementations are excluded from prompts, retrieved records, and model visible histories.

After each run, the public feedback audit scans archived histories and logs:

```bash
python scripts/audit_public_evaluation_run.py \
  --experiment-root reproduced/smoke \
  --output reproduced/smoke/public_feedback_audit.json
```

A valid paper reproduction reports zero prohibited findings.

## Models

| Model | Adapter |
|---|---|
| MGEMMV-Qwen-7B | generic VLM adapter |
| MGEMMV-Llama-11B | generic VLM adapter |
| Qwen2.5-VL-7B-Instruct | generic VLM adapter |
| Qwen3-VL-8B-Instruct | generic VLM adapter |
| Llama-3.2-11B-Vision-Instruct | generic VLM adapter |
| MiniCPM-V-4.5-8B | MiniCPM adapter |
| InternVL3.5-8B-Instruct | InternVL adapter |

LLaVA-NeXT-Mistral-7B is retained only in the standalone baseline results. Its compact target subset run is supplementary because its image and context limits differ from the main protocol.

Create the local model path file from a directory containing the seven model
folders. The generated file is ignored by Git.

```bash
bash scripts/configure_model_paths.sh --model-root /path/to/model-root
```

## Frozen protocol

| Item | Setting |
|---|---|
| GPU | One NVIDIA A800 80 GB |
| Precision | BF16 |
| Samples | One execution per case and condition |
| Decoding | temperature 0.2, top p 0.9 in the frozen generation functions |
| Initial and repair output limit | 1,536 new tokens |
| Structured diagnosis limit | 384 new tokens |
| Image preprocessing | one overview and at most four adaptive crops |
| Image pixel limit | 589,824 pixels per view |
| Workflow budget | three outer rounds including initial generation |
| Stopping | first functional pass or budget exhaustion |
| Main run seed | 1234 |
| Case seed | run seed plus deterministic case offset |
| Simulation timeout | 60 seconds |
| Verilog tools | Icarus Verilog 14.0 development build and `vvp` |
| Synthesis audit | Yosys 0.65+71 |

`configs/frozen_protocol.json` is the machine readable source for these values. Every run stores its resolved configuration.

## Installation

Three environment levels separate the lightweight demo, analysis, and model inference dependencies.

For the CPU toy demo on Linux or macOS:

```bash
conda env create -f environment-demo.yml
conda activate structrtl-repair-demo
```

This environment pins Python 3.10.20 and Icarus Verilog 12.0. The demo uses no third party Python package.

The original inference runs used Python 3.10 under Ubuntu. Install the reported Icarus Verilog and Yosys versions through OSS CAD Suite, then create the pinned core inference environment.

```bash
conda env create -f environment.yml
conda activate structrtl-repair
iverilog -V
vvp -V
yosys -V
```

For analysis without model inference:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-analysis.txt
```

`environment/a800_lock` contains the sanitized package export, CUDA runtime, EDA tools, and hashes of model remote code files returned from the validated A800 environment.

## Five minute CPU demo

Run the released one case control loop without downloading a model:

```bash
./run_demo.sh
```

The demo uses a deterministic candidate replay backend and the real Icarus Verilog evaluator. It exercises contract Gates, staged verification, Error Library retrieval, family Skeleton selection, action routing, early stopping, and candidate selection. Its output should match `examples/toy_demo/expected_output.txt` and end with:

```text
Selected: round 2, score 2
Public feedback audit: PASS
DEMO PASS
```

Generated artifacts are written to `reproduced/toy_demo/history.json` and `selected.v`. The replay backend makes this a framework integration test. It does not measure VLM generation quality.

## Real model smoke reproduction

The following command executes the three principal conditions on one Benchmark1 case with a shared initial candidate. This path passed with the generic Qwen3 adapter and the dedicated MiniCPM and InternVL adapters in the reported A800 environment.

```bash
bash scripts/validate_a800_model_smoke.sh \
  --model qwen3_vl_8b \
  --model-path /path/to/Qwen3-VL-8B-Instruct \
  --output-dir reproduced/smoke
```

Expected outputs:

```text
reproduced/smoke/
|-- results.csv
|-- run_config.json
|-- public_feedback_audit.json
`-- experiments/results/cases/module2/test1/
    |-- reflect_result_reflect_patch_*/history.json
    `-- reflect_result_reflect_rag_skeleton_*/history.json
```

Validate the run:

```bash
python scripts/validate_release.py \
  --run-dir reproduced/smoke \
  --expected-cases 1 \
  --require-shared-initial \
  --require-public-only
```

## Reproduce one full main condition

```bash
python scripts/run_case.py \
  --model qwen3_vl_8b \
  --model-path /path/to/Qwen3-VL-8B-Instruct \
  --dataset benchmark1 \
  --preset full \
  --modes origin,reflect_patch,reflect_rag_skeleton \
  --seed 1234 \
  --protocol configs/frozen_protocol.json \
  --evaluation-access public_only \
  --output-dir reproduced/main/qwen3_benchmark1 \
  --fresh
```

MiniCPM and InternVL select their dedicated adapters through the `--model` identifier.

## Reproduce the full main matrix

```bash
bash scripts/run_main_matrix.sh \
  --models configs/model_paths.local.yaml \
  --matrix configs/main_matrix.yaml \
  --output-dir reproduced/main
```

The matrix contains seven models and two datasets, producing fourteen paired runs. Jobs are serial by default on one GPU. Parallel execution is supported across separate GPUs without changing case seeds or within case pairing.

For every case, `origin`, `reflect_patch`, and `reflect_rag_skeleton` share the same initial candidate and differ only in subsequent repair.

## Reproduce RQ2 mechanism experiments

```bash
bash scripts/run_component_matrix.sh \
  --models configs/model_paths.local.yaml \
  --matrix configs/component_matrix.yaml \
  --dataset benchmark1 \
  --seed 1234 \
  --output-dir reproduced/component
```

The matrix records the exact enabled mechanisms for generic patching, RAG, structural constraints, the complete framework, external Error Library removal, and Gate removal.

```bash
python scripts/summarize_unified_mechanism_ablation.py \
  --manifest reproduced/component/run_manifest.csv \
  --expected-cases 81 \
  --output-dir reproduced/component/analysis
```

## Reproduce the seed study

The fixed target subset contains 12 Benchmark1 cases. MiniCPM and Qwen3 are evaluated under run seeds 1234, 2234, and 3234.

```bash
bash scripts/run_seed_study.sh \
  --models configs/model_paths.local.yaml \
  --subset configs/seed_subset.yaml \
  --seeds 1234,2234,3234 \
  --output-dir reproduced/seed
```

```bash
python scripts/summarize_random_seed_generalization.py \
  --manifest reproduced/seed/run_manifest.csv \
  --output-dir reproduced/seed/analysis
```

## Reproduce analysis without inference

```bash
python scripts/reproduce_analysis.py \
  --reference-root results/reference \
  --output-dir reproduced/analysis \
  --strict
```

The orchestrator checks the fourteen main runs, rebuilds the main effectiveness table and paired statistics, summarizes the seven model component study, regenerates both seed studies, and reconstructs the runtime ledger. Strict mode compares the principal regenerated tables with `results/expected/`. Family, error, and synthesis evidence can be inspected or regenerated with the dedicated scripts listed below.

## Paired significance

```bash
python scripts/analyze_paired_significance.py \
  --run qwen3_author135=results/reference/main/qwen3_author135.csv \
  --run qwen3_benchmark1=results/reference/main/qwen3_benchmark1.csv \
  --expected-cases qwen3_author135=135 \
  --expected-cases qwen3_benchmark1=81 \
  --comparison origin:reflect_patch \
  --comparison reflect_patch:reflect_rag_skeleton \
  --comparison origin:reflect_rag_skeleton \
  --bootstrap-samples 10000 \
  --seed 20260715 \
  --strict \
  --output-dir reproduced/analysis/qwen3_paired
```

## Runtime and workflow rounds

```bash
python scripts/runtime_iteration_cost_analysis.py \
  --manifest results/reference/main/run_manifest.csv \
  --history-root results/reference/main/histories \
  --output-dir reproduced/analysis/runtime
```

Round counts include initial generation. The report contains executed workflow rounds, elapsed seconds, successful round distribution, and functionally verified candidates per elapsed minute.

## Downstream synthesis audit

Synthesis runs after candidate selection and does not feed observations to the repair controller.

```bash
python scripts/run_yosys_generic_qor.py \
  --experiment-root reproduced/main/qwen3_benchmark1/cases \
  --ablation-csv reproduced/main/qwen3_benchmark1/results.csv \
  --output-dir reproduced/synthesis/qwen3_benchmark1 \
  --model qwen3_vl_8b \
  --dataset benchmark1 \
  --yosys-bin yosys \
  --timeout 60
```

The audit reports synthesizability, generic mapped cell count, and mapped area proxy. It is not a formal equivalence or complete PPA evaluation.

## Reference results

The main matrix contains 1,512 case evaluations per condition across seven models and two datasets.

| Condition | Functional pass@1 |
|---|---:|
| Origin | 2.8% |
| Generic patching | 26.9% |
| Complete framework | 65.2% |

Exact model and dataset values are stored in `results/expected/main_effectiveness_table.csv`. Model outputs may vary across hardware and library versions. Released seeds, shared initial hashes, resolved configurations, tool versions, and reference outcomes make differences auditable.

## Output schema

Each raw result row records the dataset, model, case, mode, run seed, case seed, syntax status, compilation status, functional status, executed workflow rounds, elapsed time, access policy, enabled mechanisms, and candidate hashes.

Each `history.json` records candidate versions, normalized observations, error categories, retrieved rules, active structural constraints, Gate actions, selected repair actions, verification outcomes, and best candidate updates. Release sanitization removes local paths and evaluator content while preserving state transitions.

## Provenance and integrity

`audit/release_manifest.csv` maps every released file to its role, source run identifier, checksum, and redistribution status. `docs/RESULT_PROVENANCE.md` maps each reported result to raw inputs and the command that regenerates it.

```bash
python scripts/validate_release.py \
  --repository-root . \
  --manifest audit/release_manifest.csv \
  --checksums audit/source_checksums.sha256 \
  --expected audit/expected_coverage.json \
  --strict
```

Validation fails on missing cases, duplicate mode rows, unsupported access policies, shared initial mismatches, leaked evaluator patterns, checksum differences, or aggregate count disagreement.

## Hardware and time requirements

- Analysis reproduction runs on CPU.
- Full inference was evaluated on one NVIDIA A800 80 GB GPU.
- A smoke case may require several minutes.
- A full 81 or 135 case run may require many GPU hours.
- The full fourteen run matrix is intended for scheduled batch execution.

Reference CSVs allow reviewers to verify every numerical claim without rerunning the complete inference matrix.

## Excluded material

- model weights and caches
- credentials, usernames, and absolute local paths
- compiler caches, Python bytecode, and `.vvp` build products
- obsolete versions and exploratory runs unrelated to the paper
- unrestricted logs that contain evaluator values
- manuscript drafts, review notes, and internal evidence folders

Evaluator source needed to recompute published metrics remains in the isolated evaluator package. Model visible logs are regenerated through the public sanitizer.

## Licenses and third party material

License scope:

- framework and analysis code: Apache License 2.0
- Benchmark1 tasks, evaluator assets, images, manifests, and metadata: CC BY 4.0
- Author135 assets: upstream MGEMMV MIT License
- model weights: original provider licenses
- external EDA tools: original provider licenses

StructRTL-Repair code is released under Apache License 2.0. Author135 retains the MIT License and attribution of the upstream MGEMMV repository. Benchmark1 was created by Wei Zheng, Jiahui Feng, and Peng Hu and is released under the Creative Commons Attribution 4.0 International License.

## Citation

```bibtex
@misc{structrtlrepair2026,
  title   = {StructRTL-Repair: A Tool-Grounded Single-Agent Framework for Verilog Generation from Circuit Diagrams},
  author  = {Zheng, Wei and Feng, Jiahui and Hu, Peng},
  year    = {2026},
  note    = {Software and replication package}
}
```

Citation metadata is also available in `CITATION.cff`. The journal, DOI, repository URL, and archival DOI will be added when assigned.

## Funding

This work was supported by Grant No. 2026CY-YBXM-008.

## Release acceptance checklist

- [x] Dataset manifests contain exactly 135 and 81 cases.
- [x] Public task and evaluator assets are physically separated.
- [x] Every paper runner forces `evaluation_access=public_only`.
- [x] All three adapter families accept and record the public access policy.
- [x] The smoke command succeeds in the original Ubuntu A800 environment.
- [ ] At least one full Benchmark1 condition is rerun from the release package.
- [x] All fourteen reference runs pass coverage and condition alignment checks.
- [x] Main, paired, component, seed, and runtime summaries regenerate from released inputs.
- [ ] The downstream synthesis summary is independently regenerated from released inputs.
- [x] Exact environment versions are exported from the A800 environment.
- [x] Model weights, personal paths, credentials, and manuscript drafts are absent from the current staging tree.
- [x] Public feedback audits for all released model smoke runs report zero findings.
- [x] Benchmark1 uses CC BY 4.0, and Author135 MIT attribution is documented.
- [x] SHA256 checksums cover every current staged file.
- [ ] A second clean machine reproduces the analysis and smoke workflows.

## Contact

Questions about the artifact may be directed to the corresponding author,
Jiahui Feng, at `fengjiahui@mail.nwpu.edu.cn`.
