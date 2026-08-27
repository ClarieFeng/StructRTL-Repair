# Redistribution Checklist

This checklist separates the repository code license from rights to benchmark
content. A release tag should be created only after every asset group below has
an explicit disposition.

| Asset group | Current provenance | Release action | Status |
|---|---|---|---|
| StructRTL-Repair workflow and release scripts | Project implementation | Release under Apache License 2.0 | Confirmed |
| Error Library and family Skeletons | Project generated repair knowledge | Include under Apache License 2.0 | Confirmed |
| Author135 public descriptions and diagrams | MGEMMV public repository | Retain upstream MIT License and attribution | Confirmed |
| Author135 evaluator files | MGEMMV public repository | Retain upstream MIT License and attribution | Confirmed |
| Benchmark1 public tasks and diagrams | Created by the StructRTL-Repair authors | Release under CC BY 4.0 | Confirmed |
| Benchmark1 evaluator and golden files | Created by the StructRTL-Repair authors | Release under CC BY 4.0 | Confirmed |
| Reference CSVs and sanitized logs | Outputs produced by this project | Release with the validated artifact | Confirmed |
| Model weights and provider code | Third party model providers | Do not redistribute weights. Record identifiers, revisions, and licenses | Excluded |
| Icarus Verilog, Yosys, OSS CAD Suite, and netlistsvg | Third party tools invoked externally | Do not bundle. Cite versions and upstream licenses | External dependencies |

## Required author decisions

1. Add the GitHub repository URL and archival DOI to `CITATION.cff` when available.

## Attribution requirement

The Author135 attribution and MIT notice must remain with redistributed copies.
Redistribution or adaptation of Benchmark1 must identify the creators, link to
CC BY 4.0, and indicate whether changes were made.
