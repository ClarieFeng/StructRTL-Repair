# Frozen Implementation Snapshot

These modules were copied from the A800 experiment archive and preserve the implementation lineage used by the reported runs. They are not yet a path independent public API.

The release wrapper will call this logic through model adapters, force `evaluation_access=public_only`, and map the separated `public/` and `evaluator/` dataset views into the expected verifier interface. Any release correction must be documented and tested against this snapshot.

