# Reproduction Status

The local archive supports dataset inspection, analysis from reference CSVs, and path independent public execution entry points. End to end model smoke execution has been validated with Qwen3, MiniCPM, and InternVL in the original A800 environment.

## Available now

1. Run the model free CPU demo with `./run_demo.sh`.
2. Inspect 216 public tasks and their separated evaluator assets.
3. Recompute aggregate statistics from the standardized main, component, seed, runtime, and synthesis CSVs.
4. Inspect the frozen workflow modules and Error Library.

## Validated on A800

1. One Benchmark1 case runs in all three principal modes.
2. The reproduced run contains three aligned result rows and a shared initial candidate comparison.
3. Public feedback, path leakage, coverage, and checksum audits pass.
4. The sanitized inference environment lock records the model and tool environment without absolute model paths.

The public wrappers force `public_only` for every backend. The A800 EDA smoke
test and the Qwen3, MiniCPM, and InternVL model smoke tests pass. These checks
cover the generic adapter and both dedicated adapter families.
