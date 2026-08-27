# CPU Toy Demo

This example validates the StructRTL-Repair control loop without loading a
VLM. A deterministic replay backend supplies two candidate versions for one
released Benchmark1 task. The demo executes the public contract Gate, staged
Icarus Verilog verification, category based Error Library retrieval, family
Skeleton selection, bounded action routing, early stopping, and best candidate
selection.

The evaluator keeps simulation output inside the private boundary. The repair
controller receives only `functional_wrong_arithmetic`. This demo tests
framework integration and information flow. The A800 smoke command in the
main README provides the corresponding real model validation.
