# Dataset Card

## Scope

The release contains two circuit diagram to Verilog evaluation sets organized under the same 27 module taxonomy.

| Dataset | Modules | Cases | Primary role |
|---|---:|---:|---|
| Author135 | 27 | 135 | Paired main evaluation with five cases per module |
| Benchmark1 | 27 | 81 | Controlled extension and mechanism analysis with three cases per module |

The taxonomy covers arithmetic units, parallel prefix adders, multiplier variants, accumulation structures, processing elements, Winograd transforms, and data reorganization modules. The manifests provide the stable `moduleXX/testY` identifier and family label used by the analysis scripts.

## Public task representation

Each `public/` case contains the model visible task material:

- `circuit.*`: circuit diagram used by the multimodal model
- `description.txt`: public behavioral specification
- `interface_contract.json`: top module, ports, directions, widths, and public constraints extracted from the task
- `case_metadata.json`: released Benchmark1 metadata when available

## Evaluator representation

Each `evaluator/` case contains the executable verification assets, including `tb.v`, required support RTL, file lists, and available synthesis or golden metadata. The model runner must never add this directory to prompts, retrieval documents, model histories, or public diagnostic text. The verifier may read these files and return only the status and sanitized observation permitted by the public protocol.

## Integrity

The manifests cover all 216 cases. Benchmark1 has complete public images. The missing Author135 image for `module26/test4` was regenerated from the released Yosys JSON with netlistsvg 1.0.2. Its source, hash, dimensions, and rendering provenance are recorded with the case and pass the release validator.

## Redistribution review

Author135 originates from MGEMMV and retains its upstream MIT License and attribution. Benchmark1 descriptions, RTL, testbenches, rendered images, manifests, and case metadata were created by Wei Zheng, Jiahui Feng, and Peng Hu and are released under CC BY 4.0. Model weights are not included.
