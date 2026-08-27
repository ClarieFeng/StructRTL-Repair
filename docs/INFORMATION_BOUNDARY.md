# Evaluation Information Boundary

StructRTL-Repair separates model visible task data from evaluator only assets.

## Model visible inputs

- circuit image and adaptive crops
- public textual description
- structured interface contract
- current candidate RTL
- candidate local syntax diagnostics
- sanitized failure category
- selected Error Library entries
- active Skeleton and Gate constraints

## Evaluator only assets

- testbench source
- hidden vectors and expected values
- golden RTL and oracle data
- private helper implementations
- evaluator paths and temporary files

The verifier can compile and simulate with evaluator assets. Its output crosses the boundary only as pass status, candidate local syntax diagnostics, or an approved category level observation. Every public reproduction must set `evaluation_access=public_only` and pass the feedback audit.

The copied frozen implementation still contains one interface Gate path that infers the top module from `tb.v`. This is tracked in `KNOWN_ISSUES.md` and must be removed in the release wrapper before the end to end public protocol is declared valid.

