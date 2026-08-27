# Frozen Protocol Provenance

## Decoding parameters

The principal StructRTL-Repair runs use `temperature=0.2` and `top_p=0.9`.
This value is fixed directly in the archived generation functions for the
generic, MiniCPM, and InternVL backends. The same value appears throughout the
copied A800 workflow sources, including the original V6.2 modules and their
public protocol variants.

The value `top_p=0.95` belongs to the later visual control study. Its command
line runner and `run_config.json` files record that separate setting. Those
visual controls are supplementary analyses and are not part of the principal
paired repair matrix.

Accordingly, `configs/frozen_protocol.json`, the repository README, and the
manuscript protocol table use `top_p=0.9` for the main and component studies.

## Evidence locations

- `src/structrtl_repair/frozen/single_agent_reflect_v6_2_public_protocol.py`
- `src/structrtl_repair/frozen/single_agent_reflect_v6_2_minicpm_public_protocol.py`
- `src/structrtl_repair/frozen/single_agent_reflect_v6_2_internvl3_5_public_protocol.py`
- `configs/frozen_protocol.json`

The exact package and remote code revisions are recorded separately by
`scripts/export_a800_environment.sh` before the release tag is created.
