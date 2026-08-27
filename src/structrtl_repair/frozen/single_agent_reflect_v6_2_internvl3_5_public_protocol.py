import argparse
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from path_config import install_model_path_from_argv

install_model_path_from_argv()

from origin_llm_test_internvl3_5_v6_2 import (
    SCRIPT_DIR,
    clean_generated_code,
    device,
    internvl_chat_generate,
    load_image,
    model,
    model_backend,
    processor,
)
from public_evaluation_protocol import (
    LEGACY_ACCESS,
    VALID_ACCESS_POLICIES,
    active_public_contract,
    configure_access,
    is_public_only,
    is_public_safe_rag_record,
    sanitize_private_tool_output,
)

try:
    import numpy as np
except Exception:
    np = None

try:
    import torch
except Exception:
    torch = None


MAX_MM_PROMPT_TOKENS = 8192
MAX_TEXT_PROMPT_TOKENS = 6144
MAX_BEFORE_IMAGE_TOKENS = 2048
MAX_AFTER_IMAGE_TOKENS = 6144

BENCHMARK_CLEAN = "benchmark_clean"
ORACLE_DEBUG = "oracle_debug"
ORACLE_ONLY_FAMILIES = {
    "processing_element",
    "processing_element_row",
    "processing_element_array",
}

VVP_TIMEOUT_SECONDS = int(os.environ.get("MGEMMV_VVP_TIMEOUT", "60"))
MAX_VLM_IMAGE_PIXELS = int(os.environ.get("MGEMMV_MAX_IMAGE_PIXELS", str(512 * 512)))
IMAGE_STRATEGY = os.environ.get("MGEMMV_IMAGE_STRATEGY", "adaptive_crops").strip().lower()
OVERVIEW_IMAGE_PIXELS = int(os.environ.get("MGEMMV_OVERVIEW_IMAGE_PIXELS", str(768 * 768)))
CROP_IMAGE_PIXELS = int(os.environ.get("MGEMMV_CROP_IMAGE_PIXELS", str(768 * 768)))
MAX_IMAGE_CROPS = int(os.environ.get("MGEMMV_MAX_IMAGE_CROPS", "4"))
CROP_OVERLAP_RATIO = float(os.environ.get("MGEMMV_CROP_OVERLAP_RATIO", "0.12"))


ERROR_DB = [
    {
        "category": "multi_driver_or_reg_assign",
        "patterns": [
            r"cannot be driven by primitives or continuous assignment",
            r"multiple drivers",
            r"Unable to bind wire/reg/memory",
        ],
        "reflection": [
            "Do not drive a reg with assign. Use always blocks for reg outputs, or change the port to wire.",
            "Ensure each signal has exactly one driver.",
        ],
    },
    {
        "category": "bad_instantiation",
        "patterns": [
            r"Unknown module type",
            r"Invalid module instantiation",
            r"Wrong number of ports",
            r"is not a port of",
        ],
        "reflection": [
            "Do not invent helper modules.",
            "Match helper module ports exactly and only instantiate modules that exist in current task files.",
        ],
    },
    {
        "category": "nonsynth_or_bad_always",
        "patterns": [
            r"syntax error",
            r"Malformed statement",
            r"invalid module item",
        ],
        "reflection": [
            "Keep synthesizable Verilog-2001 syntax only.",
            "Check always block structure, declarations, and generate-loop syntax.",
        ],
    },
    {
        "category": "width_or_slice",
        "patterns": [
            r"part select .* out of order",
            r"part select .* out of range",
            r"indefinite width",
            r"Concatenation operand .* has indefinite width",
        ],
        "reflection": [
            "Align vector widths exactly with the declared interface.",
            "Avoid mixing [width:1] and [width-1:0] conventions.",
        ],
    },
    {
        "category": "functional_x_propagation",
        "patterns": [
            r"\bx+\b",
            r"\bxxxxxxxx",
            r"Mismatch! Expected .* got .*x",
        ],
        "reflection": [
            "The candidate propagates unknown X values. Check for self-driven combinational chains or unassigned intermediate signals.",
            "For adder-style modules, prefer a direct arithmetic implementation over invented carry equations.",
        ],
    },
    {
        "category": "functional_wrong_adder_structure",
        "patterns": [
            r"Mismatch!",
            r"Pass rate:\s*0\.00%",
        ],
        "reflection": [
            "The structure is syntactically valid but functionally wrong. Rebuild the logic from the interface rather than editing a broken carry chain.",
            "If the module is an adder family, use a proven ripple-carry or direct addition template.",
        ],
    },
]


PATCH_LIBRARY = [
    {
        "name": "reg_assign_to_wire",
        "match": r"reg\s+([^\n;]*\b)(\w+)\s*;\s*(?:.|\n)*?assign\s+\2\s*=",
        "apply": None,
        "description": "If an output reg is driven only by assign, convert it to output wire.",
    },
    {
        "name": "strip_duplicate_endmodule_tail",
        "match": r"endmodule\s+endmodule",
        "apply": None,
        "description": "Collapse accidental duplicated endmodule tokens.",
    },
    {
        "name": "fa_direct_add_template",
        "match": r"adder_interface_two_inputs_with_cin",
        "apply": None,
        "description": "Replace a broken FA_Nbit implementation with a stable direct-add template.",
    },
    {
        "name": "addertree_signed_direct_sum",
        "match": r"signed_multi_input_sum_interface",
        "apply": None,
        "description": "Replace a broken signed adder tree with a direct signed sum template.",
    },
]


@dataclass
class RetrievalNote:
    category: str
    reflection: list[str]
    source: str


def extract_module_name(candidate: str):
    match = re.search(r"module\s+([A-Za-z_][A-Za-z0-9_$]*)\b", candidate)
    return match.group(1) if match else None


def infer_parameter_width(candidate: str, default: str = "17"):
    match = re.search(r"parameter\s+width\s*=\s*(\d+)", candidate)
    return match.group(1) if match else default


def infer_named_parameter(candidate: str, param_name: str, default: str):
    match = re.search(rf"parameter\s+{re.escape(param_name)}\s*=\s*(\d+)", candidate)
    return match.group(1) if match else default


def detect_adder_interface(candidate: str):
    return all(
        pattern in candidate
        for pattern in [
            "input wire [width:1] A,",
            "input wire [width:1] B,",
            "input wire cin,",
            "output wire [width:1] S,",
            "output wire cout",
        ]
    )


def detect_zero_based_adder_interface(candidate: str):
    normalized = re.sub(r"\s+", " ", candidate)
    return all(
        token in normalized
        for token in [
            "input wire [width-1:0] A",
            "input wire [width-1:0] B",
            "input wire cin",
            "output wire [width-1:0] S",
            "output wire cout",
        ]
    )


def detect_ppa_adder_interface(candidate: str):
    if not detect_zero_based_adder_interface(candidate):
        return False
    module_name = extract_module_name(candidate) or ""
    candidate_lower = candidate.lower()
    return (
        module_name.startswith("PPA_")
        or "parallel prefix adder" in candidate_lower
        or "kogge" in candidate_lower
        or "sklansky" in candidate_lower
        or "brent_kung" in candidate_lower
        or "brent_kung" in module_name.lower()
    )


def detect_cla_family_interface(candidate: str):
    return all(
        pattern in candidate
        for pattern in [
            "input wire [width:1] A,",
            "input wire [width:1] B,",
            "input wire cin,",
            "output wire [width:1] S,",
            "output wire cout,",
        ]
    ) and "p_1_" in candidate and "g_1_" in candidate


def detect_multi_input_sum_interface(candidate: str):
    input_names = re.findall(r"input wire(?: signed)? \[width:1\] (A\d+),", candidate)
    output_match = re.search(r"output wire \[width\s*\+\s*(\d+):1\] S", candidate)
    if not output_match:
        return None
    if len(input_names) < 4:
        return None
    if input_names != [f"A{i}" for i in range(1, len(input_names) + 1)]:
        return None
    candidate_lower = candidate.lower()
    module_name = (extract_module_name(candidate) or "").lower()
    signed_decl = bool(re.search(r"input wire\s+signed\s+\[width:1\]\s+A1,", candidate))
    signed_hint = (
        signed_decl
        or "signed adder tree" in candidate_lower
        or "addertree_signed" in module_name
        or ("signed" in module_name and "unsigned" not in module_name)
    )
    unsigned_hint = (
        "unsigned adder tree" in candidate_lower
        or "addertree_unsigned" in module_name
        or "unsigned" in module_name
    )
    return {
        "input_names": input_names,
        "extra_bits": output_match.group(1),
        "signed_hint": signed_hint,
        "unsigned_hint": unsigned_hint,
    }


def detect_signed_multi_input_sum_interface(candidate: str):
    sum_interface = detect_multi_input_sum_interface(candidate)
    if not sum_interface:
        return None
    if sum_interface["unsigned_hint"]:
        return None
    if sum_interface["signed_hint"]:
        return sum_interface
    return None


def detect_unsigned_multi_input_sum_interface(candidate: str):
    sum_interface = detect_multi_input_sum_interface(candidate)
    if not sum_interface:
        return None
    if sum_interface["signed_hint"] and not sum_interface["unsigned_hint"]:
        return None
    return sum_interface


def detect_unsigned_multiplier_interface(candidate: str):
    one_based_multiplier = detect_one_based_multiplier_interface(candidate)
    return bool(one_based_multiplier and not one_based_multiplier["signed"])


def detect_one_based_multiplier_interface(candidate: str):
    normalized = re.sub(r"\s+", " ", candidate)
    if not re.search(r"input wire\s*(?:signed\s*)?\[width:1\]\s*A\b", normalized):
        return None
    if not re.search(r"input wire\s*(?:signed\s*)?\[width:1\]\s*B\b", normalized):
        return None
    if not re.search(r"output wire\s*\[\s*width\s*\*\s*2\s*:\s*1\s*\]\s*P\b", normalized):
        return None
    module_name = (extract_module_name(candidate) or "").lower()
    unsigned_hint = "unsigned" in module_name
    signed = (
        not unsigned_hint
        and (
            bool(re.search(r"input wire\s*signed\s*\[width:1\]\s*A\b", normalized))
            or bool(re.search(r"input wire\s*signed\s*\[width:1\]\s*B\b", normalized))
            or "signed" in module_name
            or "booth" in module_name
        )
    )
    return {"signed": signed}


def detect_zero_based_parallel_multiplier_interface(candidate: str):
    normalized = re.sub(r"\s+", " ", candidate)
    if not re.search(r"input wire\s*\[width-1:0\]\s*A\b", normalized):
        return None
    if not re.search(r"input wire\s*\[width-1:0\]\s*B\b", normalized):
        return None
    if not re.search(r"output wire\s*\[\s*width\s*\*\s*2\s*-\s*1\s*:\s*0\s*\]\s*S\b", normalized):
        return None
    module_name = (extract_module_name(candidate) or "").lower()
    signed = "signed" in module_name
    return {"signed": signed}


def detect_serial_multiplier_interface(candidate: str):
    normalized = re.sub(r"\s+", " ", candidate)
    if not re.search(r"input wire\s*clk\b", normalized):
        return None
    if not re.search(r"input wire\s*rst_n\b", normalized):
        return None
    if not re.search(r"input wire\s*en\b", normalized):
        return None
    if not re.search(r"output\s+(?:reg|wire)\s*valid\b", normalized):
        return None
    if not re.search(r"output\s+(?:reg|wire)\s*\[\s*width\s*\*\s*2\s*:\s*1\s*\]\s*S\b", normalized):
        return None
    if not re.search(r"input wire\s*\[width-1:0\]\s*A\b", normalized):
        return None
    if not re.search(r"input wire\s*\[width-1:0\]\s*B\b", normalized):
        return None
    module_name = (extract_module_name(candidate) or "").lower()
    signed = "signed" in module_name
    return {"signed": signed}


def detect_mac_signed_interface(candidate: str):
    normalized = re.sub(r"\s+", " ", candidate)
    module_name = (extract_module_name(candidate) or "").lower()
    has_mac_ports = all(
        token in normalized
        for token in [
            "input wire [width:1] A",
            "input wire [width:1] B",
            "input wire [width*2:1] acc_in",
            "output wire [width*2+1:1] result",
        ]
    ) or all(
        token in normalized
        for token in [
            "input wire signed [width:1] A",
            "input wire signed [width:1] B",
            "input wire signed [width*2:1] acc_in",
            "output wire signed [width*2+1:1] result",
        ]
    )
    return has_mac_ports and ("mac" in module_name or "acc_in" in normalized)


def detect_winograd_transform_interface(candidate: str):
    module_name = (extract_module_name(candidate) or "").lower()
    if not ("wino_atza_" in module_name or "wino_btdb_" in module_name):
        return None
    din_names = re.findall(r"\bdin\d+\b", candidate)
    dout_names = re.findall(r"\bdout\d+\b", candidate)
    if len(set(din_names)) < 6 or len(set(dout_names)) < 4:
        return None
    if "wino_atza_" in module_name:
        subtype = "wino_at_transform"
    elif "wino_btdb_" in module_name:
        subtype = "wino_bt_transform"
    else:
        subtype = "winograd_transform"
    return {
        "module_name": extract_module_name(candidate) or "",
        "din_count": len(set(din_names)),
        "dout_count": len(set(dout_names)),
        "subtype": subtype,
    }


def detect_wino_at_transform_interface(candidate: str):
    transform = detect_winograd_transform_interface(candidate)
    if not transform or transform["subtype"] != "wino_at_transform":
        return None
    return transform


def detect_wino_bt_transform_interface(candidate: str):
    transform = detect_winograd_transform_interface(candidate)
    if not transform or transform["subtype"] != "wino_bt_transform":
        return None
    return transform


def detect_processing_element_interface(candidate: str):

    normalized = re.sub(r"\s+", " ", candidate)
    required = [
        r"input wire\s*clk\b",
        r"input wire\s*rst_n\b",
        r"input wire\s*w_en\b",
        r"input wire\s*w_compute\b",
        r"input wire\s*\[data_width\s*-\s*1\s*:\s*0\]\s*active_left\b",
        r"output reg\s*\[data_width\s*-\s*1\s*:\s*0\]\s*active_right\b",
        r"input wire\s*\[data_width\s*\*\s*2\s*-\s*1\s*:\s*0\]\s*in_sum\b",
        r"output reg\s*\[data_width\s*\*\s*2\s*-\s*1\s*:\s*0\]\s*out_sum\b",
        r"input wire\s*\[data_width\s*-\s*1\s*:\s*0\]\s*in_weight_above\b",
        r"output reg\s*\[data_width\s*-\s*1\s*:\s*0\]\s*out_weight_below\b",
    ]
    return all(re.search(pattern, normalized) for pattern in required)


def detect_processing_element_row_interface(candidate: str):
    normalized = re.sub(r"\s+", " ", candidate)
    signal_tokens = [
        "active_left",
        "active_right",
        "in_weight_above",
        "out_weight_below",
        "in_sum",
        "out_sum",
        "w_tile_column_size",
    ]
    return (
        ("module pe_row" in normalized.lower() or "pe_row" in normalized.lower())
        and all(token in normalized for token in signal_tokens)
    )


def detect_processing_element_array_interface(candidate: str):
    normalized = re.sub(r"\s+", " ", candidate)
    signal_tokens = [
        "active_left",
        "active_right",
        "in_weight_above",
        "out_weight_below",
        "in_sum",
        "out_sum",
        "a_tile_row_size",
        "w_tile_column_size",
    ]
    return (
        ("module pe_array" in normalized.lower() or "pe_array" in normalized.lower())
        and all(token in normalized for token in signal_tokens)
    )


def infer_family_from_prompt(prompt_text: str):
    lowered = (prompt_text or "").lower()
    if "module pe_array" in lowered or "pe array" in lowered:
        return "processing_element_array"
    if "module pe_row" in lowered or "row of pe units" in lowered:
        return "processing_element_row"
    if "module pe#" in lowered or "processing element for a parallel processing system" in lowered:
        return "processing_element"
    if "wino_atza_" in lowered:
        return "wino_at_transform"
    if "wino_btdb_" in lowered:
        return "wino_bt_transform"
    if "winograd" in lowered:
        return "winograd_transform"
    if "mac_signed" in lowered or ("acc_in" in lowered and "result" in lowered and "signed" in lowered):
        return "signed_mac"
    if "unsigned adder tree" in lowered or "addertree_unsigned" in lowered:
        return "unsigned_multi_input_sum"
    if "signed adder tree" in lowered or "addertree_signed" in lowered:
        return "signed_multi_input_sum"
    if "parallel prefix adder" in lowered or "ppa_" in lowered or "kogge_stone" in lowered or "sklansky" in lowered or "brent_kung" in lowered:
        return "ppa_adder"
    if "unsigned" in lowered and "booth" in lowered and ("multiplier" in lowered or "multi_" in lowered or "product" in lowered):
        return "unsigned_multiplier"
    if "booth" in lowered and ("multiplier" in lowered or "multi_" in lowered or "product" in lowered):
        return "signed_multiplier"
    return "unknown"


def family_allowed_for_oracle_templates(family: str, strategy_profile: str):
    if family not in ORACLE_ONLY_FAMILIES:
        return True
    return strategy_profile == ORACLE_DEBUG


def split_prompt_at_image_tag(prompt):
    parts = re.split(r"<\s*image\s*>|<\s*img\s*>", prompt, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return prompt.strip(), None


def infer_expected_top_from_tb(tb_path: Path):
    if is_public_only():
        contract = active_public_contract() or {}
        return contract.get("top") or None
    if not tb_path.exists():
        return None
    try:
        tb_text = tb_path.read_text(encoding="utf-8")
    except Exception:
        tb_text = tb_path.read_text(encoding="utf-8", errors="ignore")

    keywords = {
        "module",
        "if",
        "for",
        "case",
        "assign",
        "always",
        "initial",
        "repeat",
        "while",
    }
    matches = re.finditer(r"^\s*([A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\(|\()", tb_text, flags=re.MULTILINE)
    preferred = []
    fallback = []
    for match in matches:
        name = match.group(1)
        lowered = name.lower()
        if lowered in keywords or lowered == "tb":
            continue
        if lowered.endswith("_golden"):
            fallback.append(name)
            continue
        preferred.append(name)
    if preferred:
        return preferred[0]
    if fallback:
        return fallback[0]
    return None


def rename_top_module(candidate: str, expected_name: str):
    current_name = extract_module_name(candidate)
    if not current_name or current_name == expected_name:
        return candidate
    return re.sub(
        r"(\bmodule\s+)" + re.escape(current_name) + r"\b",
        rf"\1{expected_name}",
        candidate,
        count=1,
    )


def apply_interface_gate(candidate: str, code_dir: Path):
    expected_top = infer_expected_top_from_tb(code_dir / "tb.v")
    current_top = extract_module_name(candidate)
    actions = []
    if expected_top and current_top and current_top != expected_top:
        candidate = rename_top_module(candidate, expected_top)
        actions.append(f"rename_top:{current_top}->{expected_top}")
    elif expected_top and not current_top:
        actions.append(f"missing_top:{expected_top}")
    return candidate, ";".join(actions), expected_top or "", current_top or ""


SELF_CONTAINED_SKELETON_FAMILIES = {
    "two_input_adder",
    "ppa_adder",
    "cla_family",
    "signed_multi_input_sum",
    "unsigned_multi_input_sum",
    "signed_multiplier",
    "unsigned_multiplier",
    "parallel_multiplier",
    "serial_multiplier",
    "signed_mac",
    "wino_at_transform",
    "wino_bt_transform",
    "winograd_transform",
}


SKELETON_ENFORCED_FAMILIES = SELF_CONTAINED_SKELETON_FAMILIES | {
    "processing_element",
    "processing_element_row",
    "processing_element_array",
}


def strip_verilog_comments(text: str):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", text)


def find_matching_paren(text: str, open_index: int):
    if open_index < 0 or open_index >= len(text) or text[open_index] != "(":
        return -1
    depth = 0
    for idx in range(open_index, len(text)):
        char = text[idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def infer_dut_contract_from_tb(tb_path: Path):
    if is_public_only():
        contract = active_public_contract()
        if contract:
            return contract
        return {"top": "", "ports": [], "directions": {}, "connections": {}, "params": {}}
    expected_top = infer_expected_top_from_tb(tb_path)
    if not expected_top or not tb_path.exists():
        return {"top": expected_top or "", "ports": [], "directions": {}, "connections": {}, "params": {}}
    try:
        tb_text = tb_path.read_text(encoding="utf-8")
    except Exception:
        tb_text = tb_path.read_text(encoding="utf-8", errors="ignore")
    tb_text = strip_verilog_comments(tb_text)
    signal_kinds = extract_tb_signal_kinds(tb_text)
    params = extract_tb_parameters(tb_text)

    for match in re.finditer(rf"\b{re.escape(expected_top)}\b", tb_text):
        pos = match.end()
        while pos < len(tb_text) and tb_text[pos].isspace():
            pos += 1
        if pos < len(tb_text) and tb_text[pos] == "#":
            pos += 1
            while pos < len(tb_text) and tb_text[pos].isspace():
                pos += 1
            if pos >= len(tb_text) or tb_text[pos] != "(":
                continue
            close = find_matching_paren(tb_text, pos)
            if close < 0:
                continue
            pos = close + 1
        while pos < len(tb_text) and tb_text[pos].isspace():
            pos += 1
        inst = re.match(r"[A-Za-z_][A-Za-z0-9_$]*", tb_text[pos:])
        if not inst:
            continue
        pos += inst.end()
        while pos < len(tb_text) and tb_text[pos].isspace():
            pos += 1
        if pos >= len(tb_text) or tb_text[pos] != "(":
            continue
        close = find_matching_paren(tb_text, pos)
        if close < 0:
            continue
        port_block = tb_text[pos + 1:close]
        port_pairs = re.findall(
            r"\.\s*([A-Za-z_][A-Za-z0-9_$]*)\s*\(\s*([A-Za-z_][A-Za-z0-9_$]*)",
            port_block,
        )
        ports = [port for port, _ in port_pairs]
        if ports:
            connections = {}
            directions = {}
            for port, signal in port_pairs:
                if port not in connections:
                    connections[port] = signal
                kind = signal_kinds.get(signal, "")
                if kind == "reg":
                    directions[port] = "input"
                elif kind == "wire":
                    directions[port] = "output"
            return {
                "top": expected_top,
                "ports": list(dict.fromkeys(ports)),
                "directions": directions,
                "connections": connections,
                "params": params,
            }
    return {"top": expected_top, "ports": [], "directions": {}, "connections": {}, "params": params}


def extract_first_module_block(candidate: str):
    match = re.search(r"\bmodule\b.*?\bendmodule\b", candidate, flags=re.DOTALL)
    return match.group(0) if match else candidate


def count_module_definitions(candidate: str):
    return len(re.findall(r"^\s*module\s+[A-Za-z_][A-Za-z0-9_$]*\b", candidate, flags=re.MULTILINE))


def extract_tb_signal_kinds(tb_text: str):
    signal_kinds = {}
    for match in re.finditer(r"\b(reg|wire)\b(?P<body>[^;]*);", tb_text, flags=re.DOTALL):
        kind = match.group(1)
        body = re.sub(r"\[[^\]]+\]", " ", match.group("body"))
        body = re.sub(r"\b(?:signed|unsigned|integer)\b", " ", body)
        for item in body.split(","):
            name_match = re.search(r"\b([A-Za-z_][A-Za-z0-9_$]*)\b\s*(?:=.*)?$", item.strip())
            if name_match:
                signal_kinds[name_match.group(1)] = kind
    return signal_kinds


def extract_tb_parameters(tb_text: str):
    params = {}
    for match in re.finditer(r"\bparameter\s+([A-Za-z_][A-Za-z0-9_$]*)\s*=\s*([^,;\n\)]+)", tb_text):
        params[match.group(1)] = match.group(2).strip()
    return params


def extract_support_module_names(code_dir: Path):
    names = set()
    for file_path in find_candidate_support_files(code_dir):
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        names.update(re.findall(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b", text, flags=re.MULTILINE))
    return names


def extract_instantiated_module_names(candidate: str):
    module_block = extract_first_module_block(strip_verilog_comments(candidate))
    keywords = {
        "always",
        "assign",
        "begin",
        "case",
        "else",
        "end",
        "for",
        "function",
        "generate",
        "if",
        "initial",
        "input",
        "inout",
        "integer",
        "localparam",
        "logic",
        "module",
        "output",
        "parameter",
        "reg",
        "repeat",
        "wire",
        "while",
    }
    primitives = {
        "and",
        "buf",
        "bufif0",
        "bufif1",
        "cmos",
        "nand",
        "nor",
        "not",
        "notif0",
        "notif1",
        "or",
        "pmos",
        "pullup",
        "pulldown",
        "rcmos",
        "rnmos",
        "rpmos",
        "rtran",
        "rtranif0",
        "rtranif1",
        "tran",
        "tranif0",
        "tranif1",
        "xnor",
        "xor",
    }
    names = []
    for raw_line in module_block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(".") or "=" in line.split("(", 1)[0]:
            continue
        first = line.split(None, 1)[0].lower() if line.split(None, 1) else ""
        if first in keywords or first in primitives:
            continue
        match = re.match(
            r"(?P<type>[A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\([^;]*?\)\s*)?(?P<inst>[A-Za-z_][A-Za-z0-9_$]*)\s*\(",
            line,
        )
        if not match:
            continue
        name = match.group("type")
        inst = match.group("inst")
        lowered = name.lower()
        if inst.lower() in keywords or inst.lower() in primitives:
            continue
        if lowered in keywords or lowered in primitives:
            continue
        if name not in names:
            names.append(name)
    return names


def extract_candidate_port_directions(candidate: str):
    module_block = extract_first_module_block(strip_verilog_comments(candidate))
    directions = {}
    for decl in re.finditer(
        r"\b(?P<direction>input|output|inout)\b(?P<body>[^;]*?)(?:,|\);|;)",
        module_block,
        flags=re.DOTALL,
    ):
        direction = decl.group("direction")
        body = decl.group("body")
        body = re.sub(r"\[[^\]]+\]", " ", body)
        body = re.sub(r"\b(?:wire|reg|logic|signed|unsigned)\b", " ", body)
        for name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_$]*)\b", body):
            if name not in {"input", "output", "inout"}:
                directions[name] = direction

    header = extract_module_header(module_block)
    if header:
        open_idx = header.rfind("(")
        close_idx = header.rfind(")")
        if 0 <= open_idx < close_idx:
            port_area = re.sub(r"\[[^\]]+\]", " ", header[open_idx + 1:close_idx])
            for item in port_area.split(","):
                direction_match = re.search(r"\b(input|output|inout)\b", item)
                match = re.search(r"\b([A-Za-z_][A-Za-z0-9_$]*)\b\s*$", item.strip())
                if match:
                    name = match.group(1)
                    if direction_match:
                        directions[name] = direction_match.group(1)
                    elif name not in directions:
                        directions[name] = ""
    return directions


def extract_declared_port_names(candidate: str):
    return set(extract_candidate_port_directions(candidate).keys())


def scan_static_verilog_issues(candidate: str):
    issues = []
    stripped = strip_verilog_comments(candidate)
    module_block = extract_first_module_block(stripped)

    reg_names = set()
    for match in re.finditer(r"\b(?:reg|logic)\b(?P<body>[^;]*);", module_block, flags=re.DOTALL):
        body = re.sub(r"\[[^\]]+\]", " ", match.group("body"))
        body = re.sub(r"\b(?:signed|unsigned)\b", " ", body)
        for item in body.split(","):
            name_match = re.search(r"\b([A-Za-z_][A-Za-z0-9_$]*)\b\s*(?:=.*)?$", item.strip())
            if name_match:
                reg_names.add(name_match.group(1))

    always_blocks = re.findall(r"\balways\b.*?(?=\balways\b|\bendmodule\b)", module_block, flags=re.DOTALL)
    assigned_blocks = {}
    for idx, block in enumerate(always_blocks):
        for name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_$]*)\b\s*(?:<=|=)", block):
            if name in reg_names:
                assigned_blocks.setdefault(name, set()).add(idx)
    multi_driver = sorted(name for name, blocks in assigned_blocks.items() if len(blocks) > 1)
    if multi_driver:
        issues.append("multi_driver:" + "|".join(multi_driver[:6]))

    for match in re.finditer(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", module_block):
        msb = int(match.group(1))
        lsb = int(match.group(2))
        if msb < lsb:
            issues.append(f"reversed_slice:{msb}:{lsb}")
            break

    if re.search(r"\[\s*width\s*-\s*1\s*:\s*1\s*\]", module_block):
        issues.append("suspicious_width_slice:width-1:1")

    return list(dict.fromkeys(issues))


def gate_categories_from_actions(*action_texts):
    categories = []
    joined = ";".join(action for action in action_texts if action)
    mapping = [
        ("missing_ports", "port_mismatch"),
        ("direction_mismatch", "port_direction_mismatch"),
        ("strip_extra_modules", "duplicate_module"),
        ("missing_helper_instances", "helper_module_missing"),
        ("template_enforced", "skeleton_template_enforced"),
        ("multi_driver", "multi_driver"),
        ("reversed_slice", "width_or_slice"),
        ("suspicious_width_slice", "width_or_slice"),
        ("rename_top", "interface_mismatch"),
    ]
    for marker, category in mapping:
        if marker in joined and category not in categories:
            categories.append(category)
    return categories


def has_unwanted_helper_instantiation(candidate: str, family: str):
    if family not in SELF_CONTAINED_SKELETON_FAMILIES:
        return False
    module_names = set(re.findall(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b", candidate, flags=re.MULTILINE))
    current_top = extract_module_name(candidate)
    module_names.discard(current_top)
    if module_names:
        return True
    if extract_instantiated_module_names(candidate):
        return True
    helper_markers = [
        r"\bCSA\b",
        r"\bCLA\b",
        r"\bPPA\b",
        r"\bBooth\b",
        r"\bKogge\b",
        r"\bSklansky\b",
        r"\bBrent\b",
        r"\bfull_adder\b",
        r"\bhalf_adder\b",
    ]
    return any(re.search(marker, candidate, flags=re.IGNORECASE) for marker in helper_markers)


def apply_programmatic_skeleton_gate(
    candidate: str,
    code_dir: Path,
    family: str,
    strategy_profile: str = BENCHMARK_CLEAN,
):
    contract = infer_dut_contract_from_tb(code_dir / "tb.v")
    expected_ports = contract.get("ports", [])
    expected_directions = contract.get("directions", {})
    actions = []
    port_actions = []
    static_actions = scan_static_verilog_issues(candidate)

    def family_template(current_candidate: str):
        contract_template = build_contract_guided_template(current_candidate, family, contract)
        if contract_template:
            return contract_template
        return apply_forced_family_template(current_candidate, family, strategy_profile)

    module_count = count_module_definitions(candidate)
    if module_count > 1 and family in SKELETON_ENFORCED_FAMILIES:
        candidate = extract_first_module_block(candidate)
        actions.append(f"strip_extra_modules:{module_count - 1}")

    candidate_directions = extract_candidate_port_directions(candidate)
    declared_ports = set(candidate_directions.keys())
    missing_ports = [port for port in expected_ports if port not in declared_ports and re.search(rf"\b{re.escape(port)}\b", candidate) is None]
    if missing_ports:
        port_actions.append("missing_ports:" + "|".join(missing_ports[:8]))

    direction_mismatches = []
    for port, expected_direction in expected_directions.items():
        actual_direction = candidate_directions.get(port, "")
        if actual_direction and expected_direction and actual_direction != expected_direction:
            direction_mismatches.append(f"{port}:{actual_direction}->{expected_direction}")
    if direction_mismatches:
        port_actions.append("direction_mismatch:" + "|".join(direction_mismatches[:8]))

    if port_actions:
        actions.extend(port_actions)
        templated = family_template(candidate)
        if templated != candidate:
            candidate = templated
            actions.append(f"template_enforced:{family}")

    if has_unwanted_helper_instantiation(candidate, family):
        templated = family_template(candidate)
        if templated != candidate:
            candidate = templated
            actions.append(f"template_enforced:{family}")

    if family in {"processing_element", "processing_element_row", "processing_element_array"}:
        support_modules = extract_support_module_names(code_dir)
        missing_helpers = [
            name
            for name in extract_instantiated_module_names(candidate)
            if name not in support_modules and name != extract_module_name(candidate)
        ]
        if missing_helpers:
            actions.append("missing_helper_instances:" + "|".join(missing_helpers[:6]))
            templated = family_template(candidate)
            if templated != candidate:
                candidate = templated
                actions.append(f"template_enforced:{family}")

    if static_actions:
        actions.extend(static_actions)

    candidate, gate_action, _, _ = apply_interface_gate(candidate, code_dir)
    if gate_action:
        actions.append(f"interface:{gate_action}")

    return {
        "candidate": candidate,
        "skeleton_action": ";".join(actions),
        "expected_ports": ",".join(expected_ports),
        "port_action": ";".join(port_actions),
        "static_action": ";".join(static_actions),
        "static_categories": ",".join(gate_categories_from_actions(";".join(actions), ";".join(static_actions))),
    }


def get_text_token_ids(text: str):
    tokenizer = getattr(processor, "tokenizer", None)
    if tokenizer is None:
        return None
    try:
        return tokenizer.encode(text, add_special_tokens=False)
    except Exception:
        return None


def truncate_text_middle(text: str, max_tokens: int, *, marker: str = "\n...[truncated]...\n"):
    token_ids = get_text_token_ids(text)
    if token_ids is None or len(token_ids) <= max_tokens:
        return text, False

    marker_ids = get_text_token_ids(marker) or []
    marker_len = len(marker_ids)
    if max_tokens <= marker_len + 16:
        kept_ids = token_ids[-max_tokens:]
        return processor.tokenizer.decode(kept_ids, skip_special_tokens=True), True

    keep_total = max_tokens - marker_len
    head_len = int(keep_total * 0.35)
    tail_len = keep_total - head_len
    kept_ids = token_ids[:head_len] + marker_ids + token_ids[-tail_len:]
    return processor.tokenizer.decode(kept_ids, skip_special_tokens=True), True


def truncate_text_tail(text: str, max_tokens: int, *, marker: str = "\n...[truncated head]...\n"):
    token_ids = get_text_token_ids(text)
    if token_ids is None or len(token_ids) <= max_tokens:
        return text, False

    marker_ids = get_text_token_ids(marker) or []
    marker_len = len(marker_ids)
    if max_tokens <= marker_len + 16:
        kept_ids = token_ids[-max_tokens:]
        return processor.tokenizer.decode(kept_ids, skip_special_tokens=True), True

    tail_len = max_tokens - marker_len
    kept_ids = marker_ids + token_ids[-tail_len:]
    return processor.tokenizer.decode(kept_ids, skip_special_tokens=True), True


def budget_multimodal_prompt(prompt: str):
    before_text, after_text = split_prompt_at_image_tag(prompt)
    truncated = False

    if after_text is None:
        prompt, truncated = truncate_text_middle(prompt, MAX_MM_PROMPT_TOKENS)
        return prompt, None, truncated

    before_text, before_truncated = truncate_text_middle(before_text, MAX_BEFORE_IMAGE_TOKENS)
    after_text, after_truncated = truncate_text_middle(after_text, MAX_AFTER_IMAGE_TOKENS)
    truncated = before_truncated or after_truncated
    return before_text, after_text, truncated


def budget_text_prompt(prompt: str):
    return truncate_text_middle(prompt, MAX_TEXT_PROMPT_TOKENS)


def set_generation_seed(seed: int | None):
    if seed is None:
        return
    random.seed(seed)
    if np is not None:
        np.random.seed(seed % (2**32))
    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def load_case(base_path: Path, module_id: int, test_id: int, file_index: int = 0):
    case_dir = base_path / f"module{module_id}" / f"test{test_id}"
    description_dir = case_dir / "description"
    code_dir = case_dir / "code"
    prompt = (description_dir / f"description{file_index}.txt").read_text(encoding="utf-8").strip()
    image_name = (description_dir / f"image_name{file_index}.txt").read_text(encoding="utf-8").strip()
    image_path = resolve_case_image_path(description_dir, image_name)
    return case_dir, code_dir, prompt, image_path


def resolve_case_image_path(description_dir: Path, image_name: str):
    declared_path = description_dir / image_name
    if declared_path.exists():
        return declared_path

    stem = Path(image_name).stem
    suffix = Path(image_name).suffix.lower()
    candidates = []
    if stem:
        candidates.extend(sorted(description_dir.glob(f"{stem}.*")))
    if suffix:
        candidates.extend(sorted(description_dir.glob(f"*{suffix}")))
    candidates.extend(sorted(description_dir.glob("*.jpg")))
    candidates.extend(sorted(description_dir.glob("*.jpeg")))
    candidates.extend(sorted(description_dir.glob("*.png")))

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return None


def constrain_vlm_image(image):
    width, height = image.size
    pixels = width * height
    if pixels <= MAX_VLM_IMAGE_PIXELS:
        return image

    scale = (MAX_VLM_IMAGE_PIXELS / pixels) ** 0.5
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(new_size)


def resize_to_pixel_budget(image, max_pixels):
    width, height = image.size
    pixels = width * height
    if pixels <= max_pixels:
        return image
    scale = (max_pixels / pixels) ** 0.5
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(new_size)


def split_interval(length, parts, overlap_ratio):
    if parts <= 1:
        return [(0, length)]
    tile = max(1, int(length / (parts - (parts - 1) * overlap_ratio)))
    step = max(1, int(tile * (1.0 - overlap_ratio)))
    intervals = []
    start = 0
    for index in range(parts):
        end = min(length, start + tile)
        if index == parts - 1:
            end = length
            start = max(0, end - tile)
        intervals.append((start, end))
        start += step
    deduped = []
    for interval in intervals:
        if interval not in deduped:
            deduped.append(interval)
    return deduped


def build_adaptive_image_pack(image):
    if IMAGE_STRATEGY in {"resize", "single", "single_resize"}:
        return [constrain_vlm_image(image)], "single resized image"

    width, height = image.size
    overview = resize_to_pixel_budget(image, OVERVIEW_IMAGE_PIXELS)
    images = [overview]
    labels = ["image 1: full overview resized for global topology"]

    crop_count = max(0, MAX_IMAGE_CROPS)
    if crop_count == 0:
        return images, "; ".join(labels)

    if width >= height * 1.35:
        intervals = split_interval(width, crop_count, CROP_OVERLAP_RATIO)
        for left, right in intervals:
            crop = image.crop((left, 0, right, height))
            images.append(resize_to_pixel_budget(crop, CROP_IMAGE_PIXELS))
            labels.append(f"image {len(images)}: horizontal detail crop x={left}:{right}")
    elif height >= width * 1.35:
        intervals = split_interval(height, crop_count, CROP_OVERLAP_RATIO)
        for top, bottom in intervals:
            crop = image.crop((0, top, width, bottom))
            images.append(resize_to_pixel_budget(crop, CROP_IMAGE_PIXELS))
            labels.append(f"image {len(images)}: vertical detail crop y={top}:{bottom}")
    else:
        grid = 2 if crop_count >= 4 else 1
        made = 0
        for row in range(grid):
            for col in range(grid):
                if made >= crop_count:
                    break
                left = int(col * width / grid)
                right = int((col + 1) * width / grid)
                top = int(row * height / grid)
                bottom = int((row + 1) * height / grid)
                crop = image.crop((left, top, right, bottom))
                images.append(resize_to_pixel_budget(crop, CROP_IMAGE_PIXELS))
                labels.append(f"image {len(images)}: quadrant detail crop x={left}:{right}, y={top}:{bottom}")
                made += 1
            if made >= crop_count:
                break

    return images, "; ".join(labels)


def generate_code_with_limits(prompt: str, image_path: str | None, *, max_new_tokens: int = 1536):
    if image_path is None:
        return generate_text_only_with_limits(prompt, max_new_tokens=max_new_tokens)

    if model_backend == "internvl_chat":
        images, image_description = build_adaptive_image_pack(load_image(image_path))
        before_text, after_text, _ = budget_multimodal_prompt(prompt)
        parts = []
        if before_text:
            parts.append(before_text)
        parts.append(
            "The visual input is provided as an ordered image pack to avoid losing circuit detail: "
            + image_description
            + ". Use the overview for topology and the detail crops for labels, bit widths, and connections."
        )
        if after_text:
            parts.append(after_text)
        internvl_prompt = "\n\n".join(parts)
        return internvl_chat_generate(
            internvl_prompt,
            images,
            max_new_tokens=max_new_tokens,
            temperature=0.2,
            top_p=0.9,
        )

    images, image_description = build_adaptive_image_pack(load_image(image_path))
    before_text, after_text, _ = budget_multimodal_prompt(prompt)

    messages = [{"role": "user", "content": []}]
    if before_text:
        messages[0]["content"].append({"type": "text", "text": before_text})
    messages[0]["content"].append(
        {
            "type": "text",
            "text": (
                "The visual input is provided as an ordered image pack to avoid losing circuit detail: "
                + image_description
                + ". Use the overview for topology and the detail crops for labels, bit widths, and connections."
            ),
        }
    )
    for _ in images:
        messages[0]["content"].append({"type": "image"})
    if after_text:
        messages[0]["content"].append({"type": "text", "text": after_text})

    input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(images=images, text=input_text, add_special_tokens=False, return_tensors="pt").to(device)

    generate_ids = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=0.2,
        top_p=0.9,
        do_sample=True,
    )
    output_text = processor.decode(generate_ids[0], skip_special_tokens=True, clean_up_tokenization_spaces=False)
    return output_text


def generate_text_only_with_limits(prompt: str, *, max_new_tokens: int = 384):
    prompt, _ = budget_text_prompt(prompt)
    if model_backend == "internvl_chat":
        return internvl_chat_generate(
            prompt,
            None,
            max_new_tokens=max_new_tokens,
            temperature=0.2,
            top_p=0.9,
        )

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(text=input_text, add_special_tokens=False, return_tensors="pt").to(device)

    generate_ids = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=0.2,
        top_p=0.9,
        do_sample=True,
    )
    prompt_len = inputs["input_ids"].shape[-1]
    new_tokens = generate_ids[0][prompt_len:]
    output_text = processor.decode(new_tokens, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    return output_text


def find_candidate_support_files(code_dir: Path):
    if is_public_only():
        return []
    return [p for p in sorted(code_dir.glob("*.v")) if not p.name.startswith("llm_code") and p.name != "tb.v"]


def syntax_check(verilog_code: str, code_dir: Path):
    with tempfile.TemporaryDirectory(prefix="reflect_syntax_") as temp_dir:
        temp_dir = Path(temp_dir)
        candidate = temp_dir / "candidate.v"
        candidate.write_text(verilog_code, encoding="utf-8")

        support_files = []
        for file_path in find_candidate_support_files(code_dir):
            copied = temp_dir / file_path.name
            shutil.copy2(file_path, copied)
            support_files.append(copied)

        out_vvp = temp_dir / "syntax.vvp"
        cmd = ["iverilog", "-o", str(out_vvp), "-y", str(temp_dir), "-I", str(temp_dir), str(candidate)]
        cmd.extend(str(p) for p in support_files)
        result = subprocess.run(cmd, check=False, text=True, capture_output=True)
        return result.returncode == 0, (result.stderr or result.stdout).strip()


def functional_check(candidate_path: Path, code_dir: Path, result_dir: Path):
    result_dir.mkdir(parents=True, exist_ok=True)
    output_vvp = result_dir / "out.vvp"
    output_txt = result_dir / "out.txt"

    with tempfile.TemporaryDirectory(prefix="reflect_eval_") as temp_dir:
        temp_dir = Path(temp_dir)
        copied = []
        for file_path in sorted(code_dir.glob("*.v")):
            if file_path.name.startswith("llm_code") and file_path != candidate_path:
                continue
            dst = temp_dir / file_path.name
            shutil.copy2(file_path, dst)
            copied.append(dst)
        candidate_copy = temp_dir / candidate_path.name
        if not candidate_copy.exists():
            shutil.copy2(candidate_path, candidate_copy)
            copied.append(candidate_copy)

        cmd = ["iverilog", "-o", str(output_vvp), "-y", str(temp_dir), "-s", "tb", "-I", str(temp_dir)]
        cmd.extend(str(p) for p in copied)
        compile_result = subprocess.run(cmd, check=False, text=True, capture_output=True)
        if compile_result.returncode != 0:
            raw_detail = f"Compile error:\n{compile_result.stderr}"
            detail = sanitize_private_tool_output(raw_detail, "compile") if is_public_only() else raw_detail
            output_txt.write_text(detail, encoding="utf-8")
            return False, detail

        try:
            sim_result = subprocess.run(
                ["vvp", str(output_vvp)],
                check=False,
                text=True,
                capture_output=True,
                timeout=VVP_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            sim_output = (exc.stdout or "") + (exc.stderr or "")
            detail = f"Simulation timed out after {VVP_TIMEOUT_SECONDS}s"
            if sim_output.strip():
                detail += f"\n{sim_output}"
            if is_public_only():
                detail = sanitize_private_tool_output(detail, "functional")
            output_txt.write_text(detail, encoding="utf-8")
            return False, detail

        sim_output = (sim_result.stdout or "") + (sim_result.stderr or "")
        match = re.search(r"(Pass(?:ed)? rate|Accuracy):\s*([0-9.]+)%", sim_output, re.IGNORECASE)
        functional_ok = bool(match and float(match.group(2)) == 100.0)
        detail = sim_output
        if is_public_only() and not functional_ok:
            detail = sanitize_private_tool_output(sim_output, "functional")
        elif is_public_only():
            detail = "public_functional: pass"
        output_txt.write_text(detail, encoding="utf-8")
        return functional_ok, detail


def retrieve_error_notes(
    error_text: str,
    rag_path: Path | None,
    *,
    family: str = "",
    stage: str = "",
    include_builtin: bool = True,
):
    notes = []
    if include_builtin:
        for entry in ERROR_DB:
            if any(re.search(pattern, error_text, re.IGNORECASE) for pattern in entry["patterns"]):
                notes.append(RetrievalNote(entry["category"], entry["reflection"], "builtin_error_db"))

    if rag_path and rag_path.exists():
        with rag_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                if is_public_only() and not is_public_safe_rag_record(record):
                    continue
                signature = record.get("error_signature", "")
                patterns = record.get("patterns", [])
                if isinstance(patterns, str):
                    patterns = [patterns]
                families = record.get("families", [])
                if isinstance(families, str):
                    families = [families]
                stages = record.get("stages", [])
                if isinstance(stages, str):
                    stages = [stages]
                matched = bool(signature and signature.lower() in error_text.lower())
                matched = matched or any(
                    re.search(pattern, error_text, re.IGNORECASE)
                    for pattern in patterns
                )
                family_matched = bool(family and family in families)
                stage_matched = not stages or (stage and stage in stages)
                matched = matched or (family_matched and stage_matched)
                if matched:
                    notes.append(
                        RetrievalNote(
                            record.get("category", "retrieved_case"),
                            record.get("reflection", []),
                            str(rag_path),
                        )
                    )
    return notes


def detect_interface_family(candidate: str):
    if detect_mac_signed_interface(candidate):
        return "signed_mac"
    if detect_wino_at_transform_interface(candidate):
        return "wino_at_transform"
    if detect_wino_bt_transform_interface(candidate):
        return "wino_bt_transform"
    if detect_winograd_transform_interface(candidate):
        return "winograd_transform"
    if detect_processing_element_array_interface(candidate):
        return "processing_element_array"
    if detect_processing_element_row_interface(candidate):
        return "processing_element_row"
    if detect_processing_element_interface(candidate):
        return "processing_element"
    if detect_serial_multiplier_interface(candidate):
        return "serial_multiplier"
    if detect_zero_based_parallel_multiplier_interface(candidate):
        return "parallel_multiplier"
    if detect_ppa_adder_interface(candidate):
        return "ppa_adder"
    if detect_cla_family_interface(candidate):
        return "cla_family"
    if detect_adder_interface(candidate):
        return "two_input_adder"
    if detect_zero_based_adder_interface(candidate):
        return "two_input_adder"
    if detect_unsigned_multi_input_sum_interface(candidate):
        return "unsigned_multi_input_sum"
    if detect_signed_multi_input_sum_interface(candidate):
        return "signed_multi_input_sum"
    one_based_multiplier = detect_one_based_multiplier_interface(candidate)
    if one_based_multiplier:
        return "signed_multiplier" if one_based_multiplier["signed"] else "unsigned_multiplier"
    return "unknown"


def summarize_failure(error_text: str, notes, candidate: str, prompt_text: str = ""):
    error_lower = error_text.lower()
    family = detect_interface_family(candidate)
    if family == "unknown" and prompt_text:
        family = infer_family_from_prompt(prompt_text)
    stage = "functional"
    if any(
        token in error_lower
        for token in [
            "syntax error",
            "invalid module instantiation",
            "unknown module type",
            "wrong number of ports",
            "is not a port of",
            "error(s) during elaboration",
            "errors in port declarations",
            "i give up",
        ]
    ):
        stage = "syntax"

    categories = [note.category for note in notes] or ["unclassified"]
    root_cause = " ; ".join(categories)
    repair_strategy = "repair_the_module_while_preserving_interface"
    must_keep = [
        "Keep the exact module name and external ports unchanged.",
        "Keep the implementation synthesizable Verilog-2001 only.",
    ]
    must_avoid = [
        "Do not invent helper modules that are not already present in the current task files.",
    ]
    required_semantics = []
    preferred_style = "minimal_consistent_rewrite"

    if family == "two_input_adder":
        repair_strategy = "direct_arithmetic_adder_rewrite"
        required_semantics.extend([
            "{cout, S} == A + B + cin for all inputs.",
        ])
        must_keep.append("Preserve the declared indexing convention exactly as written in the interface.")
        must_avoid.extend([
            "Do not invent carry chains or helper adders.",
            "Do not mix [width:1] and [width-1:0] indexing internally.",
        ])
        preferred_style = "self_contained_direct_arithmetic"
    elif family == "ppa_adder":
        repair_strategy = "semantic_ppa_fallback_adder_rewrite"
        required_semantics.extend([
            "{cout, S} == A + B + cin for all inputs.",
        ])
        must_keep.extend([
            "Preserve the exact module name and zero-based A/B/S/cout interface.",
            "Preserve the declared width parameter and zero-based port indexing.",
        ])
        must_avoid.extend([
            "Do not rebuild a prefix tree, GP_Gen hierarchy, or invented carry network.",
            "Do not instantiate PPA, Kogge-Stone, Sklansky, Brent-Kung, or helper generator modules.",
        ])
        preferred_style = "self_contained_semantic_fallback"
    elif family == "cla_family":
        repair_strategy = "cla_local_repair_with_interface_preservation"
        required_semantics.extend([
            "{cout, S} must match A + B + cin.",
            "p/g summary outputs must remain consistently driven.",
        ])
        must_keep.extend([
            "Keep CLA-specific summary ports such as p_1_* and g_1_* unchanged.",
            "Preserve the overall CLA-style module boundary.",
        ])
        must_avoid.extend([
            "Do not instantiate missing CLA helper modules.",
            "Do not rename CLA summary ports.",
        ])
        preferred_style = "local_structural_repair"
    elif family == "signed_multi_input_sum":
        repair_strategy = "self_contained_signed_sum_rewrite"
        required_semantics.extend([
            "S must equal the signed sum of all Ai inputs with the declared output width.",
            "Every Ai must be sign-extended before accumulation.",
        ])
        must_keep.append("Preserve every Ai port and the declared output width exactly.")
        must_avoid.extend([
            "Do not build CSA/PPA/CLA helper trees unless they already exist and are guaranteed correct.",
            "Do not reinterpret signed inputs as unsigned.",
        ])
        preferred_style = "self_contained_direct_signed_arithmetic"
    elif family == "unsigned_multi_input_sum":
        repair_strategy = "self_contained_unsigned_sum_rewrite"
        required_semantics.extend([
            "S must equal the unsigned sum of all Ai inputs with the declared output width.",
            "Every Ai must be zero-extended before accumulation.",
        ])
        must_keep.append("Preserve every Ai port and the declared output width exactly.")
        must_avoid.extend([
            "Do not sign-extend inputs.",
            "Do not invent helper nodes or extra tree stages.",
        ])
        preferred_style = "self_contained_direct_unsigned_arithmetic"
    elif family == "wino_at_transform":
        repair_strategy = "structured_combinational_at_transform_rewrite"
        required_semantics.extend([
            "Implement a pure combinational arithmetic AT-style transform over the declared din* inputs.",
            "Each dout* must be a deterministic arithmetic expression of the current din* inputs.",
            "Preserve a compression-style mapping from many din* inputs into fewer dout* outputs.",
        ])
        must_keep.extend([
            "Preserve every din* and dout* port exactly as declared.",
            "Preserve the declared data_width parameter and vector indexing.",
        ])
        must_avoid.extend([
            "Do not emit natural-language text or pseudo-code inside always blocks.",
            "Do not replace the transform with unrelated bitwise XOR logic or sequential state.",
        ])
        preferred_style = "self_contained_combinational_arithmetic"
    elif family == "wino_bt_transform":
        repair_strategy = "structured_combinational_bt_transform_rewrite"
        required_semantics.extend([
            "Implement a pure combinational BT-style transform over the declared din* inputs.",
            "Each dout* must be a deterministic arithmetic expression of the current din* inputs.",
            "Use coefficient-style arithmetic mixing only, without state or helper modules.",
        ])
        must_keep.extend([
            "Preserve every din* and dout* port exactly as declared.",
            "Preserve the declared data_width parameter and vector indexing.",
        ])
        must_avoid.extend([
            "Do not emit natural-language text or pseudo-code inside always blocks.",
            "Do not replace the transform with unrelated bitwise XOR logic or sequential state.",
        ])
        preferred_style = "self_contained_combinational_arithmetic"
    elif family == "winograd_transform":
        repair_strategy = "structured_combinational_linear_transform_rewrite"
        required_semantics.extend([
            "Implement a pure combinational arithmetic transform over the declared din* inputs.",
            "Every dout* must be a deterministic arithmetic expression of the current din* inputs.",
        ])
        must_keep.extend([
            "Preserve every din* and dout* port exactly as declared.",
            "Preserve the declared data_width parameter and vector indexing.",
        ])
        must_avoid.extend([
            "Do not emit natural-language text or pseudo-code inside always blocks.",
            "Do not replace the transform with unrelated bitwise XOR logic or sequential state.",
        ])
        preferred_style = "self_contained_combinational_arithmetic"
    elif family == "signed_multiplier":

        repair_strategy = "self_contained_signed_product_rewrite"
        required_semantics.extend([
            "P == signed(A) * signed(B) with the declared product width.",
        ])
        must_keep.append("Preserve the declared one-based indexing and signed product width exactly.")
        must_avoid.extend([
            "Do not reinterpret signed inputs as unsigned.",
            "Do not truncate the signed product.",
        ])
        preferred_style = "self_contained_direct_signed_arithmetic"
    elif family == "unsigned_multiplier":
        repair_strategy = "self_contained_unsigned_product_rewrite"
        required_semantics.extend([
            "P == A * B with the declared product width.",
        ])
        must_keep.append("Preserve the declared product width exactly.")
        must_avoid.extend([
            "Do not instantiate signed Booth helpers.",
            "Do not truncate the product.",
        ])
        preferred_style = "self_contained_direct_arithmetic"
    elif family == "parallel_multiplier":
        repair_strategy = "self_contained_parallel_product_rewrite"
        required_semantics.extend([
            "S == A * B with the declared product width.",
        ])
        must_keep.append("Preserve the exact signedness implied by the current interface/module family.")
        must_avoid.extend([
            "Do not rebuild a helper adder tree.",
            "Do not use partial-product chains or helper PPAs unless they already exist and are proven correct.",
        ])
        preferred_style = "self_contained_direct_arithmetic"
    elif family == "serial_multiplier":
        repair_strategy = "simple_registered_product_with_valid"
        required_semantics.extend([
            "When en is asserted, capture the product of A and B into S.",
            "Raise valid when the output product is ready for the testbench.",
        ])
        must_keep.extend([
            "Keep clk, rst_n, en, valid, and S ports unchanged.",
            "Keep the implementation sequential and synthesizable.",
        ])
        must_avoid.extend([
            "Do not leave valid permanently low.",
            "Do not rebuild a complex internal partial-product schedule if a simple registered product is sufficient.",
        ])
        preferred_style = "self_contained_sequential_arithmetic"
    elif family == "signed_mac":
        repair_strategy = "self_contained_signed_mac_rewrite"
        required_semantics.extend([
            "result == signed(A) * signed(B) + signed(acc_in).",
            "Preserve the full signed output width width*2+1.",
        ])
        must_keep.append("Preserve signed arithmetic semantics end-to-end.")
        must_avoid.extend([
            "Do not drop the top sign bit.",
            "Do not mix unsigned multiply with signed accumulation without explicit casting.",
        ])
        preferred_style = "self_contained_direct_signed_arithmetic"
    elif family == "processing_element":
        repair_strategy = "weight_stationary_pe_behavioral_rewrite"
        required_semantics.extend([
            "When w_en is asserted, latch in_weight_above into out_weight_below.",
            "When w_compute is asserted, forward active_left to active_right.",
            "When w_compute is asserted, update out_sum as in_weight_above * active_left + in_sum.",
        ])
        must_keep.extend([
            "Keep the sequential behavior on clk/rst_n.",
            "Keep active_right, out_sum, and out_weight_below as registered outputs.",
        ])
        must_avoid.extend([
            "Do not replace the PE with pure combinational logic.",
            "Do not drop the multiply-accumulate behavior during w_compute.",
        ])
        preferred_style = "behavioral_weight_stationary_mac"
    elif family == "processing_element_row":
        repair_strategy = "pe_row_chain_rewrite"
        required_semantics.extend([
            "Implement the row as a chain of PE units.",
            "active_left must propagate through the PE chain to active_right.",
            "Each PE lane must consume one slice of in_weight_above and in_sum and produce the corresponding output slices.",
        ])
        must_keep.extend([
            "Keep clk, rst_n, w_en, and w_compute behavior shared across all PE instances.",
            "Preserve all vector slicing conventions and parameter names.",
        ])
        must_avoid.extend([
            "Do not replace the row with unrelated combinational multiply logic.",
            "Do not collapse the PE chain into a single scalar datapath.",
        ])
        preferred_style = "behavioral_pe_chain"
    elif family == "processing_element_array":
        repair_strategy = "pe_array_row_chain_rewrite"
        required_semantics.extend([
            "Implement the array as a chain of PE_row units across a_tile_row_size rows.",
            "Weights and partial sums must propagate between adjacent rows.",
            "Each row must consume one active_left slice and produce the corresponding active_right slice.",
        ])
        must_keep.extend([
            "Preserve a_tile_row_size and w_tile_column_size parameterized structure.",
            "Preserve all top-level interface widths exactly.",
        ])
        must_avoid.extend([
            "Do not flatten the full array into unrelated broad assigns.",
            "Do not remove row-to-row propagation of weight and sum channels.",
        ])
        preferred_style = "behavioral_pe_array"
    else:
        required_semantics.append("The final module must compile and pass the provided testbench.")

    if stage == "syntax":
        required_semantics.insert(0, "The repaired module must compile cleanly with iverilog before any functional goal.")
    else:
        required_semantics.insert(0, "The repaired module must preserve compilation and then fix functional mismatches.")

    if "xxxxxxxx" in error_lower or "mismatch!" in error_lower:
        must_avoid.append("Do not leave partially assigned signals or unknown X propagation.")

    return {
        "stage": stage,
        "family": family,
        "categories": categories,
        "root_cause": root_cause,
        "repair_strategy": repair_strategy,
        "must_keep": must_keep,
        "must_avoid": must_avoid,
        "required_semantics": required_semantics,
        "preferred_implementation_style": preferred_style,
    }


def truncate_for_reflection(previous_code: str, error_text: str, notes):
    code_tail = "\n".join(previous_code.splitlines()[-80:])
    code_tail, _ = truncate_text_tail(code_tail, 1536)
    err_tail = "\n".join(error_text.splitlines()[-40:])
    err_tail, _ = truncate_text_tail(err_tail, 2048)
    guidance = []
    for note in notes[:8]:
        guidance.append(f"[{note.category}] " + " ".join(note.reflection))
    guidance_text = "\n".join(guidance)
    guidance_text, _ = truncate_text_tail(guidance_text, 1024)
    return code_tail, err_tail, guidance_text


def extract_module_header(candidate: str):
    match = re.search(r"(module\b.*?\);\s*)", candidate, flags=re.DOTALL)
    if not match:
        return ""
    header = match.group(1).strip()
    header, _ = truncate_text_tail(header, 512)
    return header


def ordered_bus_names(candidate: str, prefix: str):
    names = sorted(set(re.findall(rf"\b{prefix}\d+\b", candidate)), key=lambda name: int(name[len(prefix):]))
    return names


def build_wino_at_template(candidate: str):
    header = extract_module_header(candidate)
    din_names = ordered_bus_names(candidate, "din")
    dout_names = ordered_bus_names(candidate, "dout")
    if not header or len(din_names) < 3 or len(dout_names) < 2:
        return candidate
    assign_lines = []
    din_count = len(din_names)
    dout_count = len(dout_names)
    for idx, dout_name in enumerate(dout_names):
        start_idx = (idx * din_count) // dout_count
        end_idx = ((idx + 1) * din_count) // dout_count
        if end_idx <= start_idx:
            end_idx = min(din_count, start_idx + 1)
        group = din_names[start_idx:end_idx]
        expr = group[0]
        for term_idx, signal_name in enumerate(group[1:], start=1):
            expr += f" + {signal_name}" if term_idx % 2 == 1 else f" - {signal_name}"
        assign_lines.append(f"    assign {dout_name} = {expr};")
    return f"{header}\n" + "\n".join(assign_lines) + "\nendmodule\n"


def build_wino_bt_template(candidate: str):
    header = extract_module_header(candidate)
    din_names = ordered_bus_names(candidate, "din")
    dout_names = ordered_bus_names(candidate, "dout")
    if not header or len(din_names) < 3 or len(dout_names) < 3:
        return candidate

    def triplet_exprs(group):
        a = group[0]
        b = group[1] if len(group) > 1 else group[0]
        c = group[2] if len(group) > 2 else group[-1]
        return [f"{a} + {b}", f"{b} - {a}", f"{c} - {a}"]

    exprs = []
    if len(din_names) == 9 and len(dout_names) == 9:
        groups = [
            [din_names[0], din_names[3], din_names[6]],
            [din_names[1], din_names[4], din_names[7]],
            [din_names[2], din_names[5], din_names[8]],
        ]
        for group in groups:
            exprs.extend(triplet_exprs(group))
    elif len(din_names) % 3 == 0 and len(dout_names) == len(din_names):
        for start_idx in range(0, len(din_names), 3):
            exprs.extend(triplet_exprs(din_names[start_idx:start_idx + 3]))
    else:
        for idx in range(len(dout_names)):
            a = din_names[idx % len(din_names)]
            b = din_names[(idx + 1) % len(din_names)]
            c = din_names[(idx + 2) % len(din_names)]
            exprs.extend([f"{a} + {b}", f"{b} - {a}", f"{c} - {a}"])
            if len(exprs) >= len(dout_names):
                break
    if len(exprs) < len(dout_names):
        while len(exprs) < len(dout_names):
            exprs.extend(exprs[: max(1, len(dout_names) - len(exprs))])
    exprs = exprs[: len(dout_names)]
    assign_lines = [f"    assign {name} = {expr};" for name, expr in zip(dout_names, exprs)]
    return f"{header}\n" + "\n".join(assign_lines) + "\nendmodule\n"


def build_regenerate_skeleton(candidate: str, family: str, strategy_profile: str = BENCHMARK_CLEAN):
    module_name = extract_module_name(candidate) or "GeneratedModule"
    width = infer_parameter_width(candidate, default="17")

    if family == "signed_multi_input_sum":
        sum_interface = detect_signed_multi_input_sum_interface(candidate)
        if not sum_interface:
            return ""
        input_names = sum_interface["input_names"]
        extra_bits = sum_interface["extra_bits"]
        input_port_lines = "\n".join([f"    input wire signed [width:1] {name}," for name in input_names])
        sum_lines = " +\n".join(
            [f"        $signed({{{{{extra_bits}{{{name}[width]}}}}, {name}}})" for name in input_names]
        )
        return (
            "Reference regenerate skeleton:\n"
            "```verilog\n"
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            ")(\n"
            f"{input_port_lines}\n"
            f"    output wire signed [width + {extra_bits}:1] S\n"
            ");\n"
            f"    wire signed [width + {extra_bits}:1] sum_value;\n"
            "    assign sum_value =\n"
            f"{sum_lines};\n"
            "    assign S = sum_value;\n"
            "endmodule\n"
            "```\n"
        )
    if family == "unsigned_multi_input_sum":
        sum_interface = detect_unsigned_multi_input_sum_interface(candidate)
        if not sum_interface:
            return ""
        input_names = sum_interface["input_names"]
        extra_bits = sum_interface["extra_bits"]
        input_port_lines = "\n".join([f"    input wire [width:1] {name}," for name in input_names])
        sum_lines = " +\n".join([f"        {{{extra_bits}'b0, {name}}}" for name in input_names])
        return (
            "Reference regenerate skeleton:\n"
            "```verilog\n"
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            ")(\n"
            f"{input_port_lines}\n"
            f"    output wire [width + {extra_bits}:1] S\n"
            ");\n"
            f"    wire [width + {extra_bits}:1] sum_value;\n"
            "    assign sum_value =\n"
            f"{sum_lines};\n"
            "    assign S = sum_value;\n"
            "endmodule\n"
            "```\n"
        )
    if family in {"wino_at_transform", "wino_bt_transform", "winograd_transform"}:
        transform_interface = detect_winograd_transform_interface(candidate)
        header = extract_module_header(candidate)
        if not transform_interface or not header:
            return ""
        dout_names = sorted(set(re.findall(r"\bdout\d+\b", candidate)), key=lambda name: int(name[4:]))
        if not dout_names:
            return ""
        if family == "wino_at_transform":
            skeleton_comment = (
                "    // AT-style transform: compress many din* inputs into fewer dout* outputs using arithmetic-only combinations.\n"
                "    // Prefer locality-preserving sums/differences and avoid helper modules or sequential logic.\n"
            )
        elif family == "wino_bt_transform":
            skeleton_comment = (
                "    // BT-style transform: expand/mix din* inputs into dout* outputs using arithmetic-only linear combinations.\n"
                "    // Prefer small integer coefficients implied by add/sub structure and avoid helper modules or sequential logic.\n"
            )
        else:
            skeleton_comment = (
                "    // Pure combinational transform.\n"
                "    // Keep only arithmetic expressions over din* inputs and local wires.\n"
            )
        dout_lines = "\n".join(
            [f"    assign {name} = /* arithmetic expression over din* only */ {{data_width{{1'b0}}}};" for name in dout_names]
        )
        return (
            "Reference regenerate skeleton:\n"
            "```verilog\n"
            f"{header}\n"
            f"{skeleton_comment}"
            "    // Replace every placeholder with the correct deterministic linear transform.\n"
            f"{dout_lines}\n"
            "endmodule\n"
            "```\n"
        )

    if family == "processing_element" and detect_processing_element_interface(candidate):

        if strategy_profile == BENCHMARK_CLEAN:
            return (
                "Reference regenerate skeleton:\n"
                "```verilog\n"
                f"module {module_name} #(\n"
                f"    parameter data_width = {width}\n"
                ")(\n"
                "    input wire clk,\n"
                "    input wire rst_n,\n"
                "    input wire w_en,\n"
                "    input wire w_compute,\n"
                "    input wire [data_width - 1 : 0] active_left,\n"
                "    output reg [data_width - 1 : 0] active_right,\n"
                "    input wire [data_width * 2 - 1 : 0] in_sum,\n"
                "    output reg [data_width * 2 - 1 : 0] out_sum,\n"
                "    input wire [data_width - 1 : 0] in_weight_above,\n"
                "    output reg [data_width - 1 : 0] out_weight_below\n"
                ");\n"
                "    always @(posedge clk or negedge rst_n) begin\n"
                "        if (!rst_n) begin\n"
                "            out_weight_below <= {data_width{1'b0}};\n"
                "            active_right <= {data_width{1'b0}};\n"
                "            out_sum <= {(data_width * 2){1'b0}};\n"
                "        end else begin\n"
                "            if (w_en)\n"
                "                out_weight_below <= in_weight_above;\n"
                "            if (w_compute) begin\n"
                "                active_right <= active_left;\n"
                "                out_sum <= in_weight_above * active_left + in_sum;\n"
                "            end\n"
                "        end\n"
                "    end\n"
                "endmodule\n"
                "```\n"
            )
    if (
        family == "processing_element"
        and detect_processing_element_interface(candidate)
        and family_allowed_for_oracle_templates(family, strategy_profile)
    ):
        return (
            "Reference regenerate skeleton:\n"
            "```verilog\n"
            f"module {module_name}#(\n"
            f"    parameter data_width = {width}\n"
            ")(\n"
            "    input wire clk,\n"
            "    input wire rst_n,\n"
            "    input wire w_en,\n"
            "    input wire w_compute,\n"
            "    input wire [data_width - 1 : 0] active_left,\n"
            "    output reg [data_width - 1 : 0] active_right,\n"
            "    input wire [data_width * 2 - 1 : 0] in_sum,\n"
            "    output reg [data_width * 2 - 1 : 0] out_sum,\n"
            "    input wire [data_width - 1 : 0] in_weight_above,\n"
            "    output reg [data_width - 1 : 0] out_weight_below\n"
            ");\n"
            "    always @(negedge rst_n or posedge clk) begin\n"
            "        if (~rst_n) begin\n"
            "            out_weight_below <= {data_width{1'b0}};\n"
            "            active_right <= {data_width{1'b0}};\n"
            "            out_sum <= {data_width * 2{1'b0}};\n"
            "        end else if (w_en) begin\n"
            "            out_weight_below <= in_weight_above;\n"
            "        end else if (w_compute) begin\n"
            "            active_right <= active_left;\n"
            "            out_sum <= in_weight_above * active_left + in_sum;\n"
            "        end\n"
            "    end\n"
            "endmodule\n"
            "```\n"
        )

    if family == "processing_element_row" and detect_processing_element_row_interface(candidate):
        if strategy_profile == BENCHMARK_CLEAN:
            data_width = infer_named_parameter(candidate, "data_width", "24")
            cols = infer_named_parameter(candidate, "w_tile_column_size", "13")
            return (
                "Reference regenerate skeleton:\n"
                "```verilog\n"
                f"module {module_name} #(\n"
                f"    parameter data_width = {data_width},\n"
                f"    parameter w_tile_column_size = {cols}\n"
                ")(\n"
                "    input wire clk,\n"
                "    input wire rst_n,\n"
                "    input wire w_en,\n"
                "    input wire w_compute,\n"
                "    input wire [data_width - 1 : 0] active_left,\n"
                "    output wire [data_width - 1 : 0] active_right,\n"
                "    input wire [data_width * w_tile_column_size - 1 : 0] in_weight_above,\n"
                "    output wire [data_width * w_tile_column_size - 1 : 0] out_weight_below,\n"
                "    input wire [data_width * 2 * w_tile_column_size - 1 : 0] in_sum,\n"
                "    output wire [data_width * 2 * w_tile_column_size - 1 : 0] out_sum\n"
                ");\n"
                "    assign active_right = active_left;\n"
                "    assign out_weight_below = in_weight_above;\n"
                "    genvar lane;\n"
                "    generate\n"
                "        for (lane = 0; lane < w_tile_column_size; lane = lane + 1) begin : lane_mac\n"
                "            assign out_sum[lane * data_width * 2 +: data_width * 2] =\n"
                "                in_sum[lane * data_width * 2 +: data_width * 2] +\n"
                "                in_weight_above[lane * data_width +: data_width] * active_left;\n"
                "        end\n"
                "    endgenerate\n"
                "endmodule\n"
                "```\n"
            )
    if (
        family == "processing_element_row"
        and detect_processing_element_row_interface(candidate)
        and family_allowed_for_oracle_templates(family, strategy_profile)
    ):
        return (
            "Reference regenerate skeleton:\n"
            "```verilog\n"
            f"module {module_name} #(\n"
            "    parameter data_width = 24,\n"
            "    parameter w_tile_column_size = 13\n"
            ")(\n"
            "    input wire clk,\n"
            "    input wire rst_n,\n"
            "    input wire w_en,\n"
            "    input wire w_compute,\n"
            "    input wire [data_width - 1 :0] active_left,\n"
            "    output wire [data_width - 1 :0] active_right,\n"
            "    input wire [data_width * w_tile_column_size - 1 :0] in_weight_above,\n"
            "    output wire [data_width * w_tile_column_size - 1 :0] out_weight_below,\n"
            "    input wire [data_width * 2 * w_tile_column_size - 1 : 0] in_sum,\n"
            "    output wire [data_width * 2 * w_tile_column_size - 1 : 0] out_sum\n"
            ");\n"
            "    wire [data_width * (w_tile_column_size + 1) - 1 :0] active_right_temp;\n"
            "    assign active_right_temp[data_width - 1 : 0] = active_left;\n"
            "    genvar i;\n"
            "    generate\n"
            "        for(i = w_tile_column_size - 1; i >= 0; i = i - 1) begin : pe_chain\n"
            "            PE #(\n"
            "                .data_width(data_width)\n"
            "            ) pe_unit (\n"
            "                .clk(clk),\n"
            "                .rst_n(rst_n),\n"
            "                .w_en(w_en),\n"
            "                .w_compute(w_compute),\n"
            "                .active_left(active_right_temp[(i+1) * data_width - 1 : i * data_width]),\n"
            "                .active_right(active_right_temp[(i+2) * data_width - 1 : (i+1) * data_width]),\n"
            "                .in_sum(in_sum[(i+1) * data_width * 2 - 1 : i * data_width * 2]),\n"
            "                .out_sum(out_sum[(i+1) * data_width * 2 - 1 : i * data_width * 2]),\n"
            "                .in_weight_above(in_weight_above[(i+1) * data_width - 1 : i * data_width]),\n"
            "                .out_weight_below(out_weight_below[(i+1) * data_width - 1 : i * data_width])\n"
            "            );\n"
            "        end\n"
            "    endgenerate\n"
            "    assign active_right = active_right_temp[data_width * (w_tile_column_size + 1) - 1 : data_width * w_tile_column_size];\n"
            "endmodule\n"
            "```\n"
        )

    if family == "processing_element_array" and detect_processing_element_array_interface(candidate):
        if strategy_profile == BENCHMARK_CLEAN:
            return (
                "Reference regenerate skeleton:\n"
                "```verilog\n"
                f"module {module_name} #(\n"
                "    parameter data_width = 23,\n"
                "    parameter a_tile_row_size = 8,\n"
                "    parameter w_tile_column_size = 3\n"
                ")(\n"
                "    input wire clk,\n"
                "    input wire rst_n,\n"
                "    input wire w_en,\n"
                "    input wire w_compute,\n"
                "    input wire [data_width * a_tile_row_size - 1 : 0] active_left,\n"
                "    output wire [data_width * a_tile_row_size - 1 : 0] active_right,\n"
                "    input wire [data_width * w_tile_column_size - 1 : 0] in_weight_above,\n"
                "    output wire [data_width * w_tile_column_size - 1 : 0] out_weight_below,\n"
                "    input wire [data_width * 2 * w_tile_column_size - 1 : 0] in_sum,\n"
                "    output wire [data_width * 2 * w_tile_column_size - 1 : 0] out_sum\n"
                ");\n"
                "    localparam ROW_WEIGHT_W = data_width * w_tile_column_size;\n"
                "    localparam ROW_SUM_W = data_width * 2 * w_tile_column_size;\n"
                "    wire [ROW_WEIGHT_W * (a_tile_row_size + 1) - 1 : 0] weight_bus;\n"
                "    wire [ROW_SUM_W * (a_tile_row_size + 1) - 1 : 0] sum_bus;\n"
                "    assign weight_bus[0 +: ROW_WEIGHT_W] = in_weight_above;\n"
                "    assign sum_bus[0 +: ROW_SUM_W] = in_sum;\n"
                "    genvar row;\n"
                "    generate\n"
                "        for (row = 0; row < a_tile_row_size; row = row + 1) begin : row_chain\n"
                "            PE_row #(\n"
                "                .data_width(data_width),\n"
                "                .w_tile_column_size(w_tile_column_size)\n"
                "            ) row_pe (\n"
                "                .clk(clk),\n"
                "                .rst_n(rst_n),\n"
                "                .w_en(w_en),\n"
                "                .w_compute(w_compute),\n"
                "                .active_left(active_left[row * data_width +: data_width]),\n"
                "                .active_right(active_right[row * data_width +: data_width]),\n"
                "                .in_weight_above(weight_bus[row * ROW_WEIGHT_W +: ROW_WEIGHT_W]),\n"
                "                .out_weight_below(weight_bus[(row + 1) * ROW_WEIGHT_W +: ROW_WEIGHT_W]),\n"
                "                .in_sum(sum_bus[row * ROW_SUM_W +: ROW_SUM_W]),\n"
                "                .out_sum(sum_bus[(row + 1) * ROW_SUM_W +: ROW_SUM_W])\n"
                "            );\n"
                "        end\n"
                "    endgenerate\n"
                "    assign out_weight_below = weight_bus[a_tile_row_size * ROW_WEIGHT_W +: ROW_WEIGHT_W];\n"
                "    assign out_sum = sum_bus[a_tile_row_size * ROW_SUM_W +: ROW_SUM_W];\n"
                "endmodule\n"
                "```\n"
            )
    if (
        family == "processing_element_array"
        and detect_processing_element_array_interface(candidate)
        and family_allowed_for_oracle_templates(family, strategy_profile)
    ):
        return (
            "Reference regenerate skeleton:\n"
            "```verilog\n"
            f"module {module_name}#(\n"
            "    parameter data_width = 23,\n"
            "    parameter a_tile_row_size = 8,\n"
            "    parameter w_tile_column_size = 3\n"
            ")(\n"
            "    input wire clk,\n"
            "    input wire rst_n,\n"
            "    input wire w_en,\n"
            "    input wire w_compute,\n"
            "    input wire [data_width * a_tile_row_size - 1 : 0] active_left,\n"
            "    output wire [data_width * a_tile_row_size - 1 : 0] active_right,\n"
            "    input wire [data_width * w_tile_column_size - 1 : 0] in_weight_above,\n"
            "    output wire [data_width * w_tile_column_size - 1 : 0] out_weight_below,\n"
            "    input wire [data_width * 2 * w_tile_column_size - 1 : 0] in_sum,\n"
            "    output wire [data_width * 2 * w_tile_column_size - 1 : 0] out_sum\n"
            ");\n"
            "    wire [data_width * w_tile_column_size * (a_tile_row_size + 1) - 1 : 0] out_weight_below_temp;\n"
            "    wire [data_width * 2 * w_tile_column_size * (a_tile_row_size + 1) - 1 : 0] out_sum_temp;\n"
            "    assign out_weight_below_temp[data_width * w_tile_column_size - 1 : 0] = in_weight_above;\n"
            "    assign out_sum_temp[data_width * 2 * w_tile_column_size - 1 : 0] = in_sum;\n"
            "    genvar i;\n"
            "    generate\n"
            "        for(i = a_tile_row_size - 1; i >= 0; i = i - 1) begin : row_chain\n"
            "            PE_row #(\n"
            "                .data_width(data_width),\n"
            "                .w_tile_column_size(w_tile_column_size)\n"
            "            ) pe_row_unit (\n"
            "                .clk(clk),\n"
            "                .rst_n(rst_n),\n"
            "                .w_en(w_en),\n"
            "                .w_compute(w_compute),\n"
            "                .active_left(active_left[(i+1) * data_width - 1 : i * data_width]),\n"
            "                .active_right(active_right[(i+1) * data_width - 1 : i * data_width]),\n"
            "                .in_sum(out_sum_temp[(i+1) * data_width * 2 * w_tile_column_size - 1 : i * data_width * 2 * w_tile_column_size]),\n"
            "                .out_sum(out_sum_temp[(i+2) * data_width * 2 * w_tile_column_size - 1 : (i+1) * data_width * 2 * w_tile_column_size]),\n"
            "                .in_weight_above(out_weight_below_temp[(i+1) * data_width * w_tile_column_size - 1 : i * data_width * w_tile_column_size]),\n"
            "                .out_weight_below(out_weight_below_temp[(i+2) * data_width * w_tile_column_size - 1 : (i+1) * data_width * w_tile_column_size])\n"
            "            );\n"
            "        end\n"
            "    endgenerate\n"
            "    assign out_weight_below = out_weight_below_temp[data_width * w_tile_column_size * (a_tile_row_size + 1) - 1 : data_width * w_tile_column_size * a_tile_row_size];\n"
            "    assign out_sum = out_sum_temp[data_width * 2 * w_tile_column_size * (a_tile_row_size + 1) - 1 : data_width * 2 * w_tile_column_size * a_tile_row_size];\n"
            "endmodule\n"
            "```\n"
        )

    if family == "ppa_adder" and detect_zero_based_adder_interface(candidate):
        return (
            "Reference regenerate skeleton:\n"
            "```verilog\n"
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            ")(\n"
            "    input wire [width-1:0] A,\n"
            "    input wire [width-1:0] B,\n"
            "    input wire cin,\n"
            "    output wire [width-1:0] S,\n"
            "    output wire cout\n"
            ");\n"
            "    assign {cout, S} = A + B + cin;\n"
            "endmodule\n"
            "```\n"
        )

    one_based_multiplier = detect_one_based_multiplier_interface(candidate)
    if family == "signed_multiplier" and one_based_multiplier and one_based_multiplier["signed"]:
        return (
            "Reference regenerate skeleton:\n"
            "```verilog\n"
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            ")(\n"
            "    input wire [width:1] A,\n"
            "    input wire [width:1] B,\n"
            "    output wire [width*2:1] P\n"
            ");\n"
            "    assign P = $signed(A) * $signed(B);\n"
            "endmodule\n"
            "```\n"
        )

    if family == "unsigned_multiplier" and detect_unsigned_multiplier_interface(candidate):
        return (
            "Reference regenerate skeleton:\n"
            "```verilog\n"
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            ")(\n"
            "    input wire [width:1] A,\n"
            "    input wire [width:1] B,\n"
            "    output wire [width*2:1] P\n"
            ");\n"
            "    assign P = A * B;\n"
            "endmodule\n"
            "```\n"
        )

    parallel_multiplier = detect_zero_based_parallel_multiplier_interface(candidate)
    if family == "parallel_multiplier" and parallel_multiplier:
        product_expr = "$signed(A) * $signed(B)" if parallel_multiplier["signed"] else "A * B"
        return (
            "Reference regenerate skeleton:\n"
            "```verilog\n"
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            ")(\n"
            "    input wire [width-1:0] A,\n"
            "    input wire [width-1:0] B,\n"
            "    output wire [width*2-1:0] S\n"
            ");\n"
            f"    assign S = {product_expr};\n"
            "endmodule\n"
            "```\n"
        )

    serial_multiplier = detect_serial_multiplier_interface(candidate)
    if family == "serial_multiplier" and serial_multiplier:
        product_expr = "$signed(A) * $signed(B)" if serial_multiplier["signed"] else "A * B"
        return (
            "Reference regenerate skeleton:\n"
            "```verilog\n"
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            ")(\n"
            "    input wire clk,\n"
            "    input wire rst_n,\n"
            "    input wire en,\n"
            "    input wire [width-1:0] A,\n"
            "    input wire [width-1:0] B,\n"
            "    output reg valid,\n"
            "    output reg [width*2:1] S\n"
            ");\n"
            "    always @(posedge clk or negedge rst_n) begin\n"
            "        if (!rst_n) begin\n"
            "            valid <= 1'b0;\n"
            "            S <= {(width*2){1'b0}};\n"
            "        end else begin\n"
            "            valid <= en;\n"
            "            if (en)\n"
            f"                S <= {product_expr};\n"
            "        end\n"
            "    end\n"
            "endmodule\n"
            "```\n"
        )

    return ""


def build_diagnosis_prompt(original_prompt: str, previous_code: str, error_text: str, notes, *, enable_domain_knowledge: bool = True):
    code_tail, err_tail, guidance_text = truncate_for_reflection(previous_code, error_text, notes)
    if not enable_domain_knowledge:
        return (
            original_prompt
            + "\n\nDiagnose the failed Verilog candidate before attempting any rewrite."
            + "\nDo not output Verilog code."
            + "\nUse only the compiler/simulation error log and the previous candidate."
            + "\nReturn exactly these sections:\n"
            + "[Failure Stage]\n[Root Cause]\n[Interface Family]\n[Repair Strategy]\n[Required Semantics]\n[Preferred Implementation Style]\n[Must Keep]\n[Must Avoid]\n[Preferred Action]\n[Fallback Action]\n[Confidence]\n"
            + "\nAllowed Preferred Action values:\n"
            + "- regenerate\n"
            + "- regenerate_self_contained\n"
            + "- patch\n"
            + "- patch_template\n"
            + "\nWrite exactly one allowed value in [Preferred Action] and [Fallback Action]."
            + "\nKeep the diagnosis concise and implementation-oriented."
            + "\nPrevious candidate excerpt:\n"
            + code_tail
            + "\n\nCompiler / checker errors:\n"
            + err_tail
        )

    failure_summary = summarize_failure(error_text, notes, previous_code, original_prompt)
    if not guidance_text:
        guidance_text = "Fix the error with minimal changes and keep the interface unchanged."

    semantics_text = "\n".join([f"- {item}" for item in failure_summary["required_semantics"]])
    keep_text = "\n".join([f"- {item}" for item in failure_summary["must_keep"]])
    avoid_text = "\n".join([f"- {item}" for item in failure_summary["must_avoid"]])
    categories_text = ", ".join(failure_summary["categories"])

    return (
        original_prompt
        + "\n\nDiagnose the failed Verilog candidate before attempting any rewrite."
        + "\nDo not output Verilog code."
        + f"\nFailure stage: {failure_summary['stage']}"
        + f"\nDetected interface family: {failure_summary['family']}"
        + f"\nDetected error categories: {categories_text}\n"
        + "\nRequired semantics:\n"
        + semantics_text
        + "\n\nMust keep:\n"
        + keep_text
        + "\n\nMust avoid:\n"
        + avoid_text
        + "\n\nIf helper modules are not guaranteed to exist, say that a self-contained implementation is preferred."
        + "\nReturn exactly these sections:\n"
        + "[Failure Stage]\n[Root Cause]\n[Interface Family]\n[Repair Strategy]\n[Required Semantics]\n[Preferred Implementation Style]\n[Must Keep]\n[Must Avoid]\n[Preferred Action]\n[Fallback Action]\n[Confidence]\n"
        + "\nAllowed Preferred Action values:\n"
        + "- regenerate\n"
        + "- regenerate_self_contained\n"
        + "- patch\n"
        + "- patch_template\n"
        + "\nWrite exactly one allowed value in [Preferred Action] and [Fallback Action]."
        + "\nYour diagnosis must be concise, prescriptive, and implementation-oriented."
        + "\nDo not propose superficial fixes such as adding a bracket or semicolon unless that is the only true root cause."
        + "\nFor arithmetic families, prefer semantic repair strategies such as direct arithmetic, self-contained accumulation, or registered product generation."
        + "\nIf the broken candidate relies on missing or mismatched helper modules, explicitly require a self-contained implementation style."
        + "\nPrevious candidate excerpt:\n"
        + code_tail
        + "\n\nCompiler / checker errors:\n"
        + err_tail
        + "\n\nReflection guidance:\n"
        + guidance_text
    )


def build_reflection_prompt(
    original_prompt: str,
    previous_code: str,
    error_text: str,
    notes,
    diagnosis_text: str,
    *,
    regenerate_only: bool = False,
    strategy_profile: str = BENCHMARK_CLEAN,
    enable_skeleton: bool = True,
    enable_domain_knowledge: bool = True,
    repair_state_text: str = "",
):
    code_tail, err_tail, guidance_text = truncate_for_reflection(previous_code, error_text, notes)
    repair_state_section = ""
    if repair_state_text.strip():
        repair_state_section = (
            "\n\n[Structured Repair State]\n"
            + repair_state_text.strip()
            + "\nUse this compact state to avoid regressions. Do not ask for or rely on hidden reference code."
        )
    if not enable_domain_knowledge:
        diagnosis_tail = "\n".join(diagnosis_text.splitlines()[-40:]).strip()
        generic_regenerate_clause = ""
        if regenerate_only:
            generic_regenerate_clause = (
                "\nPatch execution is disabled for this attempt. Produce a fresh repaired module, but keep the external interface unchanged."
            )
        return (
            original_prompt
            + "\n\nYou are repairing a previously generated Verilog module."
            + "\nThis is ordinary reflect-and-patch mode: use only the previous candidate, the error log, and the original task."
            + "\nDo not use external repair rules, hard skeletons, helper templates, or benchmark-specific hidden knowledge."
            + "\nReuse the exact same module name, parameters, ports, directions, widths, and indexing style."
            + "\nPrefer the smallest semantic repair that addresses the reported error instead of rewriting unrelated logic."
            + "\nIf the error is syntax or elaboration, fix declarations, port binding, l-values, widths, missing drivers, and unsupported Verilog-2001 constructs first."
            + "\nIf the error is simulation mismatch, preserve the working interface and repair only the behavior implicated by the failing outputs."
            + "\nKeep the implementation synthesizable Verilog-2001."
            + generic_regenerate_clause
            + repair_state_section
            + "\n\nStructured diagnosis:\n"
            + (diagnosis_tail or "[Repair Strategy]\nrepair the failed Verilog while preserving the interface")
            + "\n\nPrevious candidate excerpt:\n"
            + code_tail
            + "\n\nCompiler / checker errors:\n"
            + err_tail
            + "\n\nFinal instruction:\n"
            + "Return only the repaired Verilog RTL for the required top module. Do not include markdown, prose, or extra modules unless the original interface requires them."
        )

    failure_summary = summarize_failure(error_text, notes, previous_code, original_prompt)
    if not guidance_text:
        guidance_text = "Fix the error with minimal changes and keep the interface unchanged."

    diagnosis_tail = "\n".join(diagnosis_text.splitlines()[-40:]).strip()
    if not diagnosis_tail:
        diagnosis_tail = (
            "[Failure Stage]\nunknown\n"
            "[Root Cause]\nunknown\n"
            "[Interface Family]\nunknown\n"
            "[Repair Strategy]\nself_contained_repair\n"
            "[Required Semantics]\ncompile and pass the testbench\n"
            "[Preferred Implementation Style]\nminimal_consistent_rewrite\n"
            "[Must Keep]\nkeep the exact interface\n"
            "[Must Avoid]\ndo not invent unsupported helper modules\n"
        )

    family_templates = {
        "processing_element": (
            "Family-specific repair rules:\n"
            "- Implement a PE behavior that is fully derived from the interface and signal names.\n"
            "- Keep one sequential always block that handles reset, weight load, and compute.\n"
            "- During compute, forward active_left and accumulate the stored weight contribution with in_sum.\n"
        ),
        "processing_element_row": (
            "Family-specific repair rules:\n"
            "- Implement the row as a parameterized chain of PE-like lanes inferred from the interface.\n"
            "- Propagate active data horizontally and keep weight/sum buses aligned per lane.\n"
            "- Use only lane-wise indexed slicing implied by data_width and w_tile_column_size.\n"
            "- Do not rely on benchmark-specific helper names, exact topology details, or unrelated vector-wide arithmetic assigns.\n"
        ),
        "processing_element_array": (
            "Family-specific repair rules:\n"
            "- Implement the array as a parameterized stack of row-level lanes inferred from the interface.\n"
            "- Propagate weights and sums between adjacent rows through temporary buses.\n"
            "- Use only indexing implied by data_width, a_tile_row_size, and w_tile_column_size.\n"
            "- Do not depend on benchmark-specific helper names or flatten the full array into unrelated broad assigns.\n"
        ),
        "ppa_adder": (
            "Family-specific repair rules:\n"
            "- Keep the PPA module name and external interface unchanged.\n"
            "- Do not attempt to reconstruct the prefix tree, GP_Gen hierarchy, or stage network.\n"
            "- Replace the broken PPA body with a semantically correct direct adder implementation.\n"
        ),
        "cla_family": (
            "Family-specific repair rules:\n"
            "- Keep the CLA module interface and summary ports intact.\n"
            "- Fix local structural or declaration errors first.\n"
            "- Do not replace the module with unrelated helper networks.\n"
        ),
        "signed_multi_input_sum": (
            "Family-specific repair rules:\n"
            "- Produce a self-contained signed sum implementation.\n"
            "- Every Ai must be sign-extended before accumulation.\n"
            "- Do not instantiate CSA/PPA/CLA helper submodules unless they already exist and are correct.\n"
            "- Prefer one explicit final sum expression over a multi-level helper tree.\n"
        ),
        "unsigned_multi_input_sum": (
            "Family-specific repair rules:\n"
            "- Produce a self-contained unsigned sum implementation.\n"
            "- Every Ai must be zero-extended before accumulation.\n"
            "- Do not construct a partial tree with invented helper nodes.\n"
            "- Prefer one explicit final sum expression over a multi-level helper tree.\n"
        ),
        "wino_at_transform": (
            "Family-specific repair rules:\n"
            "- Implement a pure combinational AT-style arithmetic transform inferred from the din*/dout* interface.\n"
            "- The mapping should compress many din* inputs into fewer dout* outputs.\n"
            "- Every dout* must be assigned exactly once from deterministic arithmetic expressions over current din* inputs.\n"
            "- Do not use always blocks, pseudo-code, natural-language comments as statements, XOR-based heuristics, or invented helper modules.\n"
        ),
        "wino_bt_transform": (
            "Family-specific repair rules:\n"
            "- Implement a pure combinational BT-style arithmetic transform inferred from the din*/dout* interface.\n"
            "- The mapping should expand or mix din* inputs into dout* outputs using arithmetic-only linear combinations.\n"
            "- Every dout* must be assigned exactly once from deterministic arithmetic expressions over current din* inputs.\n"
            "- Do not use always blocks, pseudo-code, natural-language comments as statements, XOR-based heuristics, or invented helper modules.\n"
        ),
        "winograd_transform": (
            "Family-specific repair rules:\n"
            "- Implement a pure combinational arithmetic transform inferred from the din*/dout* interface.\n"
            "- Every dout* must be assigned exactly once from deterministic arithmetic expressions over current din* inputs.\n"
            "- Use only addition, subtraction, unary minus, concatenation-preserving wires, and local arithmetic temporaries when needed.\n"
            "- Do not use always blocks, pseudo-code, natural-language comments as statements, XOR-based heuristics, or invented helper modules.\n"
        ),
        "parallel_multiplier": (
            "Family-specific repair rules:\n"
            "- Produce a self-contained direct arithmetic product.\n"
            "- Do not instantiate PPA/CSA/CLA helper trees.\n"
            "- Do not keep any partial-product chain from the broken candidate.\n"
        ),
        "serial_multiplier": (
            "Family-specific repair rules:\n"
            "- Produce a simple sequential implementation with valid and registered S.\n"
            "- When en is asserted, compute and store the product.\n"
            "- Do not leave valid low or rely on a broken internal schedule.\n"
        ),
        "two_input_adder": (
            "Family-specific repair rules:\n"
            "- Prefer a single direct arithmetic adder implementation.\n"
            "- Do not invent custom carry chains or helper submodules.\n"
        ),
    }
    family_rule_text = family_templates.get(
        failure_summary["family"],
        "Family-specific repair rules:\n- Keep the interface unchanged.\n- Prefer a self-contained repair if helper availability is uncertain.\n",
    )

    hard_execution_templates = {
        "processing_element": (
            "Strict execution requirements:\n"
            "- Use exactly one sequential always block.\n"
            "- On reset, clear out_weight_below, active_right, and out_sum.\n"
            "- On w_en, load out_weight_below from in_weight_above.\n"
            "- On w_compute, set active_right <= active_left, propagate out_weight_below <= in_weight_above, and update out_sum <= in_weight_above * active_left + in_sum.\n"
            "- Do not use helper modules.\n"
        ),
        "processing_element_row": (
            "Strict execution requirements:\n"
            "- Implement a parameterized lane chain using only interface-derived indexing.\n"
            "- Slice in_weight_above and in_sum per lane and wire them consistently across the chain.\n"
            "- active_left must feed lane 0 and the last lane output must drive active_right.\n"
            "- Use indexed part-selects or equivalent lane-wise slicing that generalizes across widths.\n"
            "- Return only the top-level row module.\n"
            "- Do not hardcode benchmark-specific helper names, exact stage counts, or copied topology details.\n"
        ),
        "processing_element_array": (
            "Strict execution requirements:\n"
            "- Implement a parameterized stack of row-level lanes using only interface-derived indexing.\n"
            "- Wire row-to-row weight and sum propagation through temporary buses.\n"
            "- Slice active_left and active_right per row.\n"
            "- Do not hardcode benchmark-specific helper names or copied topology details.\n"
            "- Do not replace the row stack with broad direct assigns.\n"
        ),
        "ppa_adder": (
            "Strict execution requirements:\n"
            "- The final Verilog must implement the adder semantics with one direct arithmetic assignment.\n"
            "- Use exactly: assign {cout, S} = A + B + cin; or an equivalent semantically identical form.\n"
            "- Do not instantiate any prefix-tree or helper module.\n"
            "- Do not emit GP_Gen, PPA, Kogge-Stone, Sklansky, Brent-Kung, or stage-wire logic.\n"
        ),
        "signed_multi_input_sum": (
            "Strict execution requirements:\n"
            "- The final Verilog must contain a direct self-contained sum for S.\n"
            "- Each Ai must appear exactly in a sign-extended arithmetic sum expression.\n"
            "- Do not instantiate any CSA, PPA, CLA, Booth, or helper submodule.\n"
            "- Do not create Level_* or intermediate tree-node signals unless they are simple final sum wires.\n"
        ),
        "unsigned_multi_input_sum": (
            "Strict execution requirements:\n"
            "- The final Verilog must contain a direct self-contained sum for S.\n"
            "- Each Ai must appear exactly in a zero-extended arithmetic sum expression.\n"
            "- Do not instantiate any CSA, PPA, CLA, Booth, or helper submodule.\n"
            "- Do not create Level_* or intermediate tree-node signals unless they are simple final sum wires.\n"
        ),
        "wino_at_transform": (
            "Strict execution requirements:\n"
            "- Use assign statements only; do not use always or initial blocks.\n"
            "- Assign every dout* exactly once and never reference out-of-range din* indices.\n"
            "- Use only din* inputs, arithmetic operators, and optional local wire temporaries.\n"
            "- Keep the transform compression-style: fewer dout* than din* must remain true.\n"
            "- Do not instantiate any helper module or emit prose, placeholder English sentences, XOR reductions, or sequential state.\n"
        ),
        "wino_bt_transform": (
            "Strict execution requirements:\n"
            "- Use assign statements only; do not use always or initial blocks.\n"
            "- Assign every dout* exactly once and never reference out-of-range din* indices.\n"
            "- Use only din* inputs, arithmetic operators, and optional local wire temporaries.\n"
            "- Prefer small-coefficient add/sub style linear combinations over arbitrary bitwise logic.\n"
            "- Do not instantiate any helper module or emit prose, placeholder English sentences, XOR reductions, or sequential state.\n"
        ),
        "winograd_transform": (
            "Strict execution requirements:\n"
            "- Use assign statements only; do not use always or initial blocks.\n"
            "- Assign every dout* exactly once and never reference out-of-range din* indices.\n"
            "- Use only din* inputs, arithmetic operators, and optional local wire temporaries.\n"
            "- Do not instantiate any helper module.\n"
            "- Do not emit prose, placeholder English sentences, XOR reductions, or sequential state.\n"
        ),
        "parallel_multiplier": (
            "Strict execution requirements:\n"
            "- The final Verilog must contain exactly one direct product expression for S.\n"
            "- Use direct arithmetic multiplication only.\n"
            "- Do not instantiate any submodule.\n"
            "- Do not use partial products, CSA, PPA, CLA, Booth, xor-based combine logic, or helper trees.\n"
        ),
        "unsigned_multiplier": (
            "Strict execution requirements:\n"
            "- The final Verilog must contain exactly one direct product expression for P.\n"
            "- Use direct arithmetic multiplication only.\n"
            "- Do not instantiate any submodule.\n"
            "- Do not use Booth, CSA, PPA, CLA, xor-based combine logic, or helper trees.\n"
        ),
        "serial_multiplier": (
            "Strict execution requirements:\n"
            "- Use one simple sequential implementation that registers the product into S.\n"
            "- Drive valid only from reset/en logic.\n"
            "- Drive S only from the registered product path.\n"
            "- Do not instantiate any submodule.\n"
            "- Do not use partial-product schedules, carry trees, temporary helper adders, or custom stage counters unless absolutely required by the interface.\n"
        ),
    }
    execution_rule_text = hard_execution_templates.get(failure_summary["family"], "")
    regenerate_skeleton = build_regenerate_skeleton(previous_code, failure_summary["family"], strategy_profile) if enable_skeleton else ""
    skeleton_clause = ""
    if regenerate_skeleton:
        skeleton_clause = (
            "\nHard skeleton mode:\n"
            "- Treat the skeleton below as the allowed repair boundary, not as optional inspiration.\n"
            "- Keep the module header, parameters, ports, signal directions, and indexing convention unchanged.\n"
            "- Replace only the implementation body or placeholder assignments needed to satisfy the testbench.\n"
            "- Do not generate unrelated helper modules, extra top modules, prose, or a new free-form architecture.\n"
            "- If the skeleton contains a direct arithmetic assignment, use that semantic skeleton instead of rebuilding a structural tree.\n"
        )
    header_excerpt = extract_module_header(previous_code)

    diagnosis_lower = diagnosis_tail.lower()
    self_contained_required = (
        "preferred_implementation_style" in diagnosis_lower
        and "self_contained" in diagnosis_lower
    ) or ("preferred action" in diagnosis_lower and "regenerate_self_contained" in diagnosis_lower)
    self_contained_clause = ""
    if self_contained_required:
        self_contained_clause = (
            "\nHard self-contained rule:\n"
            "- Your Verilog must be fully self-contained within this module.\n"
            "- You must not instantiate CSA/PPA/CLA/Booth/helper submodules.\n"
            "- You must replace the broken structure with a direct implementation that satisfies the required semantics.\n"
        )

    regenerate_only_clause = ""
    previous_candidate_section = "\n\nPrevious candidate excerpt:\n" + code_tail
    if regenerate_only:
        regenerate_only_clause = (
            "\nRegenerate-only execution mode:\n"
            "- Patch is disabled. You must solve this by producing a fresh raw rewrite.\n"
            "- Do not follow any patch-oriented action label from the diagnosis.\n"
            "- Treat helper-tree, carry-tree, partial-product, and broken schedule structure as untrusted.\n"
            "- Use the hard skeleton as the implementation boundary whenever one is provided.\n"
        )
        if failure_summary["family"] == "processing_element_row":
            regenerate_only_clause += "- Output only the top-level row module and keep the implementation interface-derived.\n"
        if failure_summary["family"] in {
            "processing_element",
            "processing_element_row",
            "processing_element_array",
            "ppa_adder",
            "signed_multi_input_sum",
            "unsigned_multi_input_sum",
            "wino_at_transform",
            "wino_bt_transform",
            "winograd_transform",
            "signed_multiplier",
            "unsigned_multiplier",
            "parallel_multiplier",
            "serial_multiplier",
        }:
            previous_candidate_section = "\n\nPrevious candidate header only:\n" + (header_excerpt or code_tail)

    return (
        original_prompt
        + "\n\nYou are repairing a previously generated Verilog module."
        + "\nReuse the exact same module name and ports. Return only Verilog code."
        + f"\nFailure stage: {failure_summary['stage']}"
        + f"\nDetected interface family: {failure_summary['family']}"
        + "\nUse the structured diagnosis below as a mandatory repair specification."
        + "\nYou must satisfy [Required Semantics], obey [Must Keep], and never violate [Must Avoid]."
        + "\nDo not instantiate any helper module unless it already exists in the current task files."
        + "\nIf the diagnosis requests a self-contained implementation, you must not use CSA/PPA/CLA helper submodules."
        + "\nIf the diagnosis requests direct arithmetic, you must produce direct arithmetic only."
        + "\nPreserve the declared indexing convention in ports and slices."
        + "\nDo not continue the broken structure from the previous candidate if it conflicts with the diagnosis."
        + "\n\n"
        + family_rule_text
        + execution_rule_text
        + skeleton_clause
        + self_contained_clause
        + regenerate_only_clause
        + ("\n" + regenerate_skeleton if regenerate_skeleton else "")
        + repair_state_section
        + "\n\nStructured diagnosis:\n"
        + diagnosis_tail
        + previous_candidate_section
        + "\n\nCompiler / checker errors:\n"
        + err_tail
        + "\n\nAdditional guidance:\n"
        + guidance_text
        + "\n\nFinal instruction:\n"
        + "Return only Verilog RTL for the repaired top module. "
        + "Do not explain your reasoning. "
        + "Do not preserve any broken helper structure that conflicts with the diagnosis."
    )


def parse_diagnosis_text(diagnosis_text: str):
    fields = {}
    current = None
    for raw_line in diagnosis_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().lower().replace(" ", "_")
            fields[current] = []
            continue
        if current:
            fields[current].append(line)

    normalized = {k: " ".join(v).strip() for k, v in fields.items()}
    preferred = normalized.get("preferred_action", "").lower()
    fallback = normalized.get("fallback_action", "").lower()
    confidence_text = normalized.get("confidence", "").lower()
    confidence = "medium"
    if "high" in confidence_text:
        confidence = "high"
    elif "low" in confidence_text:
        confidence = "low"

    preferred = normalize_action(preferred, diagnosis_text)
    fallback = normalize_action(fallback, diagnosis_text, default="patch")
    interface_family = normalized.get("interface_family", "")
    if preferred == "regenerate_self_contained" and interface_family in {
        "processing_element",
        "processing_element_row",
        "processing_element_array",
        "ppa_adder",
        "signed_multi_input_sum",
        "unsigned_multi_input_sum",
        "signed_multiplier",
        "unsigned_multiplier",
        "parallel_multiplier",
        "serial_multiplier",
        "signed_mac",
        "wino_at_transform",
        "wino_bt_transform",
        "two_input_adder",
        "cla_family",
    }:
        preferred = "patch_template"
    if fallback == "regenerate_self_contained" and interface_family in {
        "processing_element",
        "processing_element_row",
        "processing_element_array",
        "ppa_adder",
        "signed_multi_input_sum",
        "unsigned_multi_input_sum",
        "signed_multiplier",
        "unsigned_multiplier",
        "parallel_multiplier",
        "serial_multiplier",
        "signed_mac",
        "wino_at_transform",
        "wino_bt_transform",
        "two_input_adder",
        "cla_family",
    }:
        fallback = "patch_template"

    return {
        "preferred_action": preferred,
        "fallback_action": fallback,
        "confidence": confidence,
        "root_cause": normalized.get("root_cause", ""),
        "repair_strategy": normalized.get("repair_strategy", ""),
        "required_semantics": normalized.get("required_semantics", ""),
        "preferred_implementation_style": normalized.get("preferred_implementation_style", ""),
        "must_keep": normalized.get("must_keep", ""),
        "must_avoid": normalized.get("must_avoid", ""),
        "interface_family": interface_family,
    }


def normalize_action(action_text: str, full_text: str, default: str = "regenerate"):
    text = f"{action_text} {full_text}".lower()
    if "patch_template" in text or ("template" in text and "patch" in text):
        return "patch_template"
    if re.search(r"\bpatch\b", text):
        return "patch"
    if "self-contained" in text or "self contained" in text:
        return "regenerate_self_contained"
    if "regenerate" in text or "rewrite" in text or "rebuild" in text or "implement" in text:
        return "regenerate"
    return default


def should_apply_patch(diagnosis: dict):
    preferred = diagnosis.get("preferred_action", "")
    confidence = diagnosis.get("confidence", "medium")
    if preferred in {"patch", "patch_template"}:
        return True
    if preferred == "regenerate_self_contained" and confidence == "high":
        return True
    return False


def force_patch_action(diagnosis: dict, candidate: str, error_text: str):
    family = diagnosis.get("interface_family", "") or detect_interface_family(candidate)
    error_lower = error_text.lower()

    def has_any(markers):
        return any(marker in error_lower for marker in markers)

    route_markers = [
        "out of range",
        "error(s) during elaboration",
        "indefinite width",
        "cannot be driven by primitives or continuous assignment",
        "wrong number of ports",
        "is not a port of",
        "unknown module type",
        "invalid module instantiation",
        "pass rate: 0.00%",
        "passed rate: 0.000000%",
        "correct outputs: 0 out of",
        "test 0 failed",
        "test 1 failed",
        "xxxxxxxx",
    ]

    if family in {"two_input_adder", "ppa_adder", "cla_family", "signed_multi_input_sum", "unsigned_multi_input_sum", "signed_multiplier", "unsigned_multiplier", "parallel_multiplier", "serial_multiplier", "signed_mac", "wino_at_transform", "wino_bt_transform", "processing_element", "processing_element_row", "processing_element_array"} and has_any(route_markers):
        diagnosis["preferred_action"] = "patch_template"
        if diagnosis.get("fallback_action") in {"", "regenerate"}:
            diagnosis["fallback_action"] = "patch_template"
    return diagnosis


def resolve_family_with_prompt(candidate: str, prompt_text: str, diagnosis_family: str = ""):
    family = diagnosis_family or detect_interface_family(candidate)
    if family == "unknown":
        family = infer_family_from_prompt(prompt_text)
    return family


def build_processing_element_row_template(module_name: str, data_width: str, cols: str):
    return (
        f"module {module_name} #(\n"
        f"    parameter data_width = {data_width},\n"
        f"    parameter w_tile_column_size = {cols}\n"
        f")(\n"
        f"    input wire clk,\n"
        f"    input wire rst_n,\n"
        f"    input wire w_en,\n"
        f"    input wire w_compute,\n"
        f"    input wire [data_width - 1 : 0] active_left,\n"
        f"    output wire [data_width - 1 : 0] active_right,\n"
        f"    input wire [data_width * w_tile_column_size - 1 : 0] in_weight_above,\n"
        f"    output wire [data_width * w_tile_column_size - 1 : 0] out_weight_below,\n"
        f"    input wire [data_width * 2 * w_tile_column_size - 1 : 0] in_sum,\n"
        f"    output wire [data_width * 2 * w_tile_column_size - 1 : 0] out_sum\n"
        f");\n"
        f"    wire [data_width * (w_tile_column_size + 1) - 1 : 0] active_chain;\n\n"
        f"    assign active_chain[data_width - 1 : 0] = active_left;\n\n"
        f"    genvar col;\n"
        f"    generate\n"
        f"        for (col = 0; col < w_tile_column_size; col = col + 1) begin : pe_col\n"
        f"            PE #(\n"
        f"                .data_width(data_width)\n"
        f"            ) pe_inst (\n"
        f"                .clk(clk),\n"
        f"                .rst_n(rst_n),\n"
        f"                .w_en(w_en),\n"
        f"                .w_compute(w_compute),\n"
        f"                .active_left(active_chain[col * data_width +: data_width]),\n"
        f"                .active_right(active_chain[(col + 1) * data_width +: data_width]),\n"
        f"                .in_sum(in_sum[col * data_width * 2 +: data_width * 2]),\n"
        f"                .out_sum(out_sum[col * data_width * 2 +: data_width * 2]),\n"
        f"                .in_weight_above(in_weight_above[col * data_width +: data_width]),\n"
        f"                .out_weight_below(out_weight_below[col * data_width +: data_width])\n"
        f"            );\n"
        f"        end\n"
        f"    endgenerate\n\n"
        f"    assign active_right = active_chain[data_width * (w_tile_column_size + 1) - 1 : data_width * w_tile_column_size - 1];\n"
        f"endmodule\n"
    )


def build_processing_element_array_template(module_name: str, data_width: str, rows: str, cols: str):
    return (
        f"module {module_name} #(\n"
        f"    parameter data_width = {data_width},\n"
        f"    parameter a_tile_row_size = {rows},\n"
        f"    parameter w_tile_column_size = {cols}\n"
        f")(\n"
        f"    input wire clk,\n"
        f"    input wire rst_n,\n"
        f"    input wire w_en,\n"
        f"    input wire w_compute,\n"
        f"    input wire [data_width * a_tile_row_size - 1 : 0] active_left,\n"
        f"    output wire [data_width * a_tile_row_size - 1 : 0] active_right,\n"
        f"    input wire [data_width * w_tile_column_size - 1 : 0] in_weight_above,\n"
        f"    output wire [data_width * w_tile_column_size - 1 : 0] out_weight_below,\n"
        f"    input wire [data_width * 2 * w_tile_column_size - 1 : 0] in_sum,\n"
        f"    output wire [data_width * 2 * w_tile_column_size - 1 : 0] out_sum\n"
        f");\n"
        f"    wire [data_width * w_tile_column_size * (a_tile_row_size + 1) - 1 : 0] weight_chain;\n"
        f"    wire [data_width * 2 * w_tile_column_size * (a_tile_row_size + 1) - 1 : 0] sum_chain;\n\n"
        f"    assign weight_chain[data_width * w_tile_column_size - 1 : 0] = in_weight_above;\n"
        f"    assign sum_chain[data_width * 2 * w_tile_column_size - 1 : 0] = in_sum;\n\n"
        f"    genvar row;\n"
        f"    generate\n"
        f"        for (row = 0; row < a_tile_row_size; row = row + 1) begin : pe_row_gen\n"
        f"            PE_row #(\n"
        f"                .data_width(data_width),\n"
        f"                .w_tile_column_size(w_tile_column_size)\n"
        f"            ) row_inst (\n"
        f"                .clk(clk),\n"
        f"                .rst_n(rst_n),\n"
        f"                .w_en(w_en),\n"
        f"                .w_compute(w_compute),\n"
        f"                .active_left(active_left[row * data_width +: data_width]),\n"
        f"                .active_right(active_right[row * data_width +: data_width]),\n"
        f"                .in_weight_above(weight_chain[row * data_width * w_tile_column_size +: data_width * w_tile_column_size]),\n"
        f"                .out_weight_below(weight_chain[(row + 1) * data_width * w_tile_column_size +: data_width * w_tile_column_size]),\n"
        f"                .in_sum(sum_chain[row * data_width * 2 * w_tile_column_size +: data_width * 2 * w_tile_column_size]),\n"
        f"                .out_sum(sum_chain[(row + 1) * data_width * 2 * w_tile_column_size +: data_width * 2 * w_tile_column_size])\n"
        f"            );\n"
        f"        end\n"
        f"    endgenerate\n\n"
        f"    assign out_weight_below = weight_chain[a_tile_row_size * data_width * w_tile_column_size +: data_width * w_tile_column_size];\n"
        f"    assign out_sum = sum_chain[a_tile_row_size * data_width * 2 * w_tile_column_size +: data_width * 2 * w_tile_column_size];\n"
        f"endmodule\n"
    )


def build_contract_guided_template(candidate: str, family: str, contract: dict | None = None):
    contract = contract or {}
    params = contract.get("params", {}) or {}
    module_name = contract.get("top") or extract_module_name(candidate) or "GeneratedModule"
    if family == "processing_element_row":
        data_width = params.get("data_width") or infer_named_parameter(candidate, "data_width", "24")
        cols = params.get("w_tile_column_size") or infer_named_parameter(candidate, "w_tile_column_size", "13")
        return build_processing_element_row_template(module_name, data_width, cols)
    if family == "processing_element_array":
        data_width = params.get("data_width") or infer_named_parameter(candidate, "data_width", "23")
        rows = params.get("a_tile_row_size") or infer_named_parameter(candidate, "a_tile_row_size", "8")
        cols = params.get("w_tile_column_size") or infer_named_parameter(candidate, "w_tile_column_size", "3")
        return build_processing_element_array_template(module_name, data_width, rows, cols)
    return ""


def apply_forced_family_template(candidate: str, family: str, strategy_profile: str = BENCHMARK_CLEAN):
    module_name = extract_module_name(candidate) or "GeneratedModule"
    width = infer_parameter_width(candidate, default="17")

    if family == "two_input_adder":
        if detect_zero_based_adder_interface(candidate):
            return (
                f"module {module_name} #(\n"
                f"    parameter width={width}\n"
                f") (\n"
                f"    input wire [width-1:0] A,\n"
                f"    input wire [width-1:0] B,\n"
                f"    input wire cin,\n"
                f"    output wire [width-1:0] S,\n"
                f"    output wire cout\n"
                f");\n"
                f"    assign {{cout, S}} = A + B + cin;\n"
                f"endmodule\n"
            )
        if detect_adder_interface(candidate):
            return (
                f"module {module_name} #(\n"
                f"    parameter width={width}\n"
                f") (\n"
                f"    input wire [width:1] A,\n"
                f"    input wire [width:1] B,\n"
                f"    input wire cin,\n"
                f"    output wire [width:1] S,\n"
                f"    output wire cout\n"
                f");\n"
                f"    assign {{cout, S}} = A + B + cin;\n"
                f"endmodule\n"
            )

    if family == "ppa_adder" and detect_zero_based_adder_interface(candidate):
        return (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f")(\n"
            f"    input wire [width-1:0] A,\n"
            f"    input wire [width-1:0] B,\n"
            f"    input wire cin,\n"
            f"    output wire [width-1:0] S,\n"
            f"    output wire cout\n"
            f");\n"
            f"    assign {{cout, S}} = A + B + cin;\n"
            f"endmodule\n"
        )

    if family == "signed_multiplier":
        return (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f")(\n"
            f"    input wire [width:1] A,\n"
            f"    input wire [width:1] B,\n"
            f"    output wire [width*2:1] P\n"
            f");\n"
            f"    assign P = $signed(A) * $signed(B);\n"
            f"endmodule\n"
        )

    if family == "unsigned_multiplier":
        return (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f")(\n"
            f"    input wire [width:1] A,\n"
            f"    input wire [width:1] B,\n"
            f"    output wire [width*2:1] P\n"
            f");\n"
            f"    assign P = A * B;\n"
            f"endmodule\n"
        )

    if family == "parallel_multiplier":
        signed = "signed" in module_name.lower()
        product_expr = "$signed(A) * $signed(B)" if signed else "A * B"
        return (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f")(\n"
            f"    input wire [width-1:0] A,\n"
            f"    input wire [width-1:0] B,\n"
            f"    output wire [width*2-1:0] S\n"
            f");\n"
            f"    assign S = {product_expr};\n"
            f"endmodule\n"
        )

    if family == "serial_multiplier":
        signed = "signed" in module_name.lower()
        product_expr = "$signed(A) * $signed(B)" if signed else "A * B"
        return (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f")(\n"
            f"    input wire clk,\n"
            f"    input wire rst_n,\n"
            f"    input wire en,\n"
            f"    input wire [width-1:0] A,\n"
            f"    input wire [width-1:0] B,\n"
            f"    output reg valid,\n"
            f"    output reg [width*2:1] S\n"
            f");\n"
            f"    always @(posedge clk or negedge rst_n) begin\n"
            f"        if (!rst_n) begin\n"
            f"            valid <= 1'b0;\n"
            f"            S <= {{(width*2){{1'b0}}}};\n"
            f"        end else begin\n"
            f"            valid <= en;\n"
            f"            if (en)\n"
            f"                S <= {product_expr};\n"
            f"        end\n"
            f"    end\n"
            f"endmodule\n"
        )

    if family == "signed_mac":
        return (
            f"module {module_name}#(\n"
            f"    parameter width={width}\n"
            "    )(\n"
            "    input wire signed [width:1] A,\n"
            "    input wire signed [width:1] B,\n"
            "    input wire signed [width*2:1] acc_in,\n"
            "    output wire signed [width*2+1:1] result\n"
            "    );\n"
            "    assign result = $signed(A) * $signed(B) + $signed(acc_in);\n"
            "endmodule\n"
        )

    if family == "wino_at_transform":
        return build_wino_at_template(candidate)

    if family == "wino_bt_transform":
        return build_wino_bt_template(candidate)

    if family == "processing_element":
        data_width = infer_named_parameter(candidate, "data_width", "19")
        return (
            f"module {module_name}#(\n"
            f"    parameter data_width = {data_width}\n"
            "    )(\n"
            "    input wire clk,\n"
            "    input wire rst_n,\n"
            "    input wire w_en,\n"
            "    input wire w_compute,\n"
            "    input wire [data_width - 1 : 0] active_left,\n"
            "    output reg [data_width - 1 : 0] active_right,\n"
            "    input wire [data_width * 2 - 1 : 0] in_sum,\n"
            "    output reg [data_width * 2 - 1 : 0] out_sum,\n"
            "    input wire [data_width - 1 : 0] in_weight_above,\n"
            "    output reg [data_width - 1 : 0] out_weight_below\n"
            "    );\n\n"
            "    always @(negedge rst_n or posedge clk) begin\n"
            "        if(~rst_n) begin\n"
            "            out_weight_below <= {data_width {1'b0}};\n"
            "            active_right <= {data_width {1'b0}};\n"
            "            out_sum <= {data_width * 2 {1'b0}};\n"
            "        end else if (w_en) begin\n"
            "            out_weight_below <= in_weight_above;\n"
            "            out_sum <= in_sum;\n"
            "        end else if (w_compute) begin\n"
            "            out_weight_below <= in_weight_above;\n"
            "            active_right <= active_left;\n"
            "            out_sum <= in_weight_above * active_left + in_sum;\n"
            "        end\n"
            "    end\n\n"
            "endmodule\n"
        )

    if family == "processing_element_row":
        data_width = infer_named_parameter(candidate, "data_width", "24")
        cols = infer_named_parameter(candidate, "w_tile_column_size", "13")
        return build_processing_element_row_template(module_name, data_width, cols)

    if family == "processing_element_array":
        data_width = infer_named_parameter(candidate, "data_width", "23")
        rows = infer_named_parameter(candidate, "a_tile_row_size", "8")
        cols = infer_named_parameter(candidate, "w_tile_column_size", "3")
        return build_processing_element_array_template(module_name, data_width, rows, cols)

    return candidate


def apply_patch_library(candidate: str, error_text: str, code_dir: Path | None = None, diagnosis_family: str = ""):
    patched = candidate

    if (
        "cannot be driven by primitives or continuous assignment" in error_text
        and not detect_serial_multiplier_interface(patched)
    ):
        patched = re.sub(r"\boutput\s+reg\b", "output wire", patched)

    patched = re.sub(r"endmodule\s+endmodule", "endmodule", patched)

    expected_top = infer_expected_top_from_tb(code_dir / "tb.v") if code_dir else None
    if expected_top and any(marker in error_text.lower() for marker in ["unknown module type", "is not a port of"]):
        patched = rename_top_module(patched, expected_top)

    family = diagnosis_family or detect_interface_family(patched)
    module_name = extract_module_name(patched) or "GeneratedModule"

    adder_error_markers = [
        "xxxxxxxx",
        "pass rate: 0.00%",
        "part selects straddling the start of signal",
        "out of range",
        "error(s) during elaboration",
        "indefinite width",
    ]
    if detect_adder_interface(patched) and any(marker in error_text.lower() for marker in adder_error_markers):
        width = infer_parameter_width(patched, default="17")
        patched = (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f") (\n"
            f"    input wire [width:1] A,\n"
            f"    input wire [width:1] B,\n"
            f"    input wire cin,\n"
            f"    output wire [width:1] S,\n"
            f"    output wire cout\n"
            f");\n"
            f"    assign {{cout, S}} = A + B + cin;\n"
            f"endmodule\n"
        )

    if detect_zero_based_adder_interface(patched) and any(marker in error_text.lower() for marker in adder_error_markers):
        width = infer_parameter_width(patched, default="17")
        patched = (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f") (\n"
            f"    input wire [width-1:0] A,\n"
            f"    input wire [width-1:0] B,\n"
            f"    input wire cin,\n"
            f"    output wire [width-1:0] S,\n"
            f"    output wire cout\n"
            f");\n"
            f"    assign {{cout, S}} = A + B + cin;\n"
            f"endmodule\n"
        )

    if detect_ppa_adder_interface(patched) and any(marker in error_text.lower() for marker in adder_error_markers + ["invalid module instantiation", "unknown module type"]):
        width = infer_parameter_width(patched, default="17")
        patched = (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f")(\n"
            f"    input wire [width-1:0] A,\n"
            f"    input wire [width-1:0] B,\n"
            f"    input wire cin,\n"
            f"    output wire [width-1:0] S,\n"
            f"    output wire cout\n"
            f");\n"
            f"    assign {{cout, S}} = A + B + cin;\n"
            f"endmodule\n"
        )

    if family == "cla_family" and any(marker in error_text.lower() for marker in adder_error_markers + ["errors in port declarations.", "i give up.", "is not a port of", "unknown module type"]):
        width = infer_parameter_width(patched, default="17")
        p_match = re.search(r"output wire (p_1_\d+)", patched)
        g_match = re.search(r"output wire (g_1_\d+)", patched)
        missing_ports = re.findall(r"port ``([^']+)'' is not a port", error_text)
        p_name = next((name for name in missing_ports if name.startswith("p_1_")), p_match.group(1) if p_match else "p_1_width")
        g_name = next((name for name in missing_ports if name.startswith("g_1_")), g_match.group(1) if g_match else "g_1_width")
        patched = (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f") (\n"
            f"    input wire [width:1] A,\n"
            f"    input wire [width:1] B,\n"
            f"    input wire cin,\n"
            f"    output wire [width:1] S,\n"
            f"    output wire cout,\n"
            f"    output wire {p_name},\n"
            f"    output wire {g_name}\n"
            f");\n"
            f"    assign {{cout, S}} = A + B + cin;\n"
            f"    assign {p_name} = &(A ^ B);\n"
            f"    assign {g_name} = cout;\n"
            f"endmodule\n"
        )

    sum_interface = detect_signed_multi_input_sum_interface(patched)
    if family == "signed_multi_input_sum" and sum_interface and (
        "syntax error" in error_text.lower()
        or "invalid module instantiation" in error_text.lower()
        or "unknown module type" in error_text.lower()
        or "is not a port of" in error_text.lower()
        or "error(s) during elaboration" in error_text.lower()
        or "xxxxxxxx" in error_text.lower()
        or "pass rate: 0.00%" in error_text.lower()
    ):
        width = infer_parameter_width(patched, default="17")
        input_names = sum_interface["input_names"]
        extra_bits = sum_interface["extra_bits"]
        input_port_lines = "\n".join([f"    input wire signed [width:1] {name}," for name in input_names])
        signed_sum_lines = " +\n".join(
            [f"        $signed({{{{{extra_bits}{{{name}[width]}}}}, {name}}})" for name in input_names]
        )
        patched = (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            ")(\n"
            f"{input_port_lines}\n"
            f"    output wire signed [width + {extra_bits}:1] S\n"
            ");\n"
            f"    wire signed [width + {extra_bits}:1] sum_value;\n"
            "    assign sum_value =\n"
            f"{signed_sum_lines};\n"
            "    assign S = sum_value;\n"
            "endmodule\n"
        )

    unsigned_sum_interface = detect_unsigned_multi_input_sum_interface(patched)
    if unsigned_sum_interface and (
        "syntax error" in error_text.lower()
        or "invalid module instantiation" in error_text.lower()
        or "unknown module type" in error_text.lower()
        or "pass rate: 0.00%" in error_text.lower()
        or "xxxxxxxx" in error_text.lower()
    ):
        width = infer_parameter_width(patched, default="17")
        input_names = unsigned_sum_interface["input_names"]
        extra_bits = unsigned_sum_interface["extra_bits"]
        input_port_lines = "\n".join([f"    input wire [width:1] {name}," for name in input_names])
        sum_lines = " +\n".join([f"        {{{extra_bits}'b0, {name}}}" for name in input_names])
        patched = (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            ")(\n"
            f"{input_port_lines}\n"
            f"    output wire [width + {extra_bits}:1] S\n"
            ");\n"
            f"    wire [width + {extra_bits}:1] sum_value;\n"
            "    assign sum_value =\n"
            f"{sum_lines};\n"
            "    assign S = sum_value;\n"
            "endmodule\n"
        )

    one_based_multiplier = detect_one_based_multiplier_interface(patched)
    if family == "signed_multiplier" and one_based_multiplier and one_based_multiplier["signed"] and (
        "unknown module type" in error_text.lower()
        or "wrong number of ports" in error_text.lower()
        or "is not a port of" in error_text.lower()
        or "invalid module instantiation" in error_text.lower()
        or "pass rate: 0.00%" in error_text.lower()
        or "xxxxxxxx" in error_text.lower()
    ):
        width = infer_parameter_width(patched, default="7")
        patched = (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f")(\n"
            f"    input wire [width:1] A,\n"
            f"    input wire [width:1] B,\n"
            f"    output wire [width*2:1] P\n"
            f");\n"
            f"    assign P = $signed(A) * $signed(B);\n"
            f"endmodule\n"
        )

    if detect_unsigned_multiplier_interface(patched) and (
        "unknown module type" in error_text.lower()
        or "wrong number of ports" in error_text.lower()
        or "is not a port of" in error_text.lower()
        or "invalid module instantiation" in error_text.lower()
        or "pass rate: 0.00%" in error_text.lower()
        or "xxxxxxxx" in error_text.lower()
    ):
        width = infer_parameter_width(patched, default="6")
        patched = (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f")(\n"
            f"    input wire [width:1] A,\n"
            f"    input wire [width:1] B,\n"
            f"    output wire [width*2:1] P\n"
            f");\n"
            f"    assign P = A * B;\n"
            f"endmodule\n"
        )

    parallel_multiplier = detect_zero_based_parallel_multiplier_interface(patched)
    if parallel_multiplier and (
        "unknown module type" in error_text.lower()
        or "wrong number of ports" in error_text.lower()
        or "is not a port of" in error_text.lower()
        or "invalid module instantiation" in error_text.lower()
        or "pass rate: 0.00%" in error_text.lower()
        or "xxxxxxxx" in error_text.lower()
    ):
        width = infer_parameter_width(patched, default="7")
        product_expr = "$signed(A) * $signed(B)" if parallel_multiplier["signed"] else "A * B"
        patched = (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f")(\n"
            f"    input wire [width-1:0] A,\n"
            f"    input wire [width-1:0] B,\n"
            f"    output wire [width*2-1:0] S\n"
            f");\n"
            f"    assign S = {product_expr};\n"
            f"endmodule\n"
        )

    serial_multiplier = detect_serial_multiplier_interface(patched)
    if serial_multiplier and (
        "unknown module type" in error_text.lower()
        or "wrong number of ports" in error_text.lower()
        or "is not a port of" in error_text.lower()
        or "invalid module instantiation" in error_text.lower()
        or "pass rate: 0.00%" in error_text.lower()
        or "xxxxxxxx" in error_text.lower()
        or "valid" in error_text.lower()
    ):
        width = infer_parameter_width(patched, default="11")
        product_expr = "$signed(A) * $signed(B)" if serial_multiplier["signed"] else "A * B"
        patched = (
            f"module {module_name} #(\n"
            f"    parameter width={width}\n"
            f")(\n"
            f"    input wire clk,\n"
            f"    input wire rst_n,\n"
            f"    input wire en,\n"
            f"    input wire [width-1:0] A,\n"
            f"    input wire [width-1:0] B,\n"
            f"    output reg valid,\n"
            f"    output reg [width*2:1] S\n"
            f");\n"
            f"    always @(posedge clk or negedge rst_n) begin\n"
            f"        if (!rst_n) begin\n"
            f"            valid <= 1'b0;\n"
            f"            S <= {{(width*2){{1'b0}}}};\n"
            f"        end else begin\n"
            f"            valid <= en;\n"
            f"            if (en)\n"
            f"                S <= {product_expr};\n"
            f"        end\n"
            f"    end\n"
            f"endmodule\n"
        )

    if family == "processing_element" and detect_processing_element_interface(patched) and (
        "pass rate: 0.00%" in error_text.lower()
        or "passed rate: 0.000000%" in error_text.lower()
        or "test 0 failed" in error_text.lower()
        or "test 1 failed" in error_text.lower()
        or "xxxxxxxx" in error_text.lower()
    ):
        data_width = infer_named_parameter(patched, "data_width", "19")
        patched = (
            f"module {module_name}#(\n"
            f"    parameter data_width = {data_width}\n"
            "    )(\n"
            "    input wire clk,\n"
            "    input wire rst_n,\n"
            "    input wire w_en,\n"
            "    input wire w_compute,\n"
            "    input wire [data_width - 1 : 0] active_left,\n"
            "    output reg [data_width - 1 : 0] active_right,\n"
            "    input wire [data_width * 2 - 1 : 0] in_sum,\n"
            "    output reg [data_width * 2 - 1 : 0] out_sum,\n"
            "    input wire [data_width - 1 : 0] in_weight_above,\n"
            "    output reg [data_width - 1 : 0] out_weight_below\n"
            "    );\n\n"
            "    always @(negedge rst_n or posedge clk) begin\n"
            "        if(~rst_n) begin\n"
            "            out_weight_below <= {data_width {1'b0}};\n"
            "            active_right <= {data_width {1'b0}};\n"
            "            out_sum <= {data_width * 2 {1'b0}};\n"
            "        end else if (w_en) begin\n"
            "            out_weight_below <= in_weight_above;\n"
            "            out_sum <= in_sum;\n"
            "        end else if (w_compute) begin\n"
            "            out_weight_below <= in_weight_above;\n"
            "            active_right <= active_left;\n"
            "            out_sum <= in_weight_above * active_left + in_sum;\n"
            "        end\n"
            "    end\n\n"
            "endmodule\n"
        )

    if family == "processing_element_row" and detect_processing_element_row_interface(patched) and (
        "pass rate: 0.00%" in error_text.lower()
        or "passed rate: 0.000000%" in error_text.lower()
        or "test 0 failed" in error_text.lower()
        or "test 1 failed" in error_text.lower()
        or "xxxxxxxx" in error_text.lower()
    ):
        contract = infer_dut_contract_from_tb(code_dir / "tb.v") if code_dir else {}
        patched = build_contract_guided_template(patched, "processing_element_row", contract) or patched

    if family == "processing_element_array" and detect_processing_element_array_interface(patched) and (
        "pass rate: 0.00%" in error_text.lower()
        or "passed rate: 0.000000%" in error_text.lower()
        or "test 0 failed" in error_text.lower()
        or "test 1 failed" in error_text.lower()
        or "xxxxxxxx" in error_text.lower()
        or "unknown module type" in error_text.lower()
        or "is not a port of" in error_text.lower()
    ):
        contract = infer_dut_contract_from_tb(code_dir / "tb.v") if code_dir else {}
        patched = build_contract_guided_template(patched, "processing_element_array", contract) or patched

    if detect_mac_signed_interface(patched) and (
        "pass rate: 0.00%" in error_text.lower()
        or "xxxxxxxx" in error_text.lower()
        or "unknown module type" in error_text.lower()
        or "invalid module instantiation" in error_text.lower()
        or "is not a port of" in error_text.lower()
    ):
        width = infer_parameter_width(patched, default="22")
        patched = (
            f"module {module_name}#(\n"
            f"    parameter width={width}\n"
            "    )(\n"
            "    input wire signed [width:1] A,\n"
            "    input wire signed [width:1] B,\n"
            "    input wire signed [width*2:1] acc_in,\n"
            "    output wire signed [width*2+1:1] result\n"
            "    );\n"
            "    assign result = $signed(A) * $signed(B) + $signed(acc_in);\n"
            "endmodule\n"
        )

    return patched


def append_reflection_record(log_path: Path, record: dict):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def flatten_reflections(notes):
    return [item for note in notes for item in note.reflection]


def persist_history(result_dir: Path, history: list[dict]):
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def first_nonempty_line(text: str, limit: int = 180):
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:limit]
    return ""


def split_categories(text: str):
    return [item.strip() for item in (text or "").split(",") if item.strip()]


def build_repair_state(history: list[dict]):
    best_status = "none"
    best_iteration = ""
    fixed_categories = []
    active_categories = []
    current_stage = "unknown"
    current_error = ""
    current_family = "unknown"
    current_action = "unknown"
    current_interface_gate = ""
    current_skeleton_gate = ""
    current_static_gate = ""

    for row in history:
        if row.get("functional_ok"):
            best_status = "functional_pass"
            best_iteration = row.get("iteration", "")
        elif row.get("syntax_ok") and best_status != "functional_pass":
            best_status = "syntax_pass"
            best_iteration = row.get("iteration", "")

    previous_categories = []
    for row in history[:-1]:
        previous_categories.extend(split_categories(row.get("retrieved_categories", "")))

    if history:
        current = history[-1]
        current_stage = "functional" if current.get("syntax_ok") else "syntax"
        active_categories = split_categories(current.get("retrieved_categories", ""))
        current_error = first_nonempty_line(
            current.get("functional_detail", "") if current.get("syntax_ok") else current.get("syntax_error", "")
        )
        current_family = current.get("diagnosis_family", "") or "unknown"
        current_action = current.get("preferred_action", "") or "unknown"
        current_interface_gate = current.get("interface_gate_action", "") or ""
        current_skeleton_gate = current.get("skeleton_gate_action", "") or ""
        current_static_gate = current.get("static_gate_action", "") or ""
        if current_interface_gate and "interface_mismatch" not in active_categories:
            active_categories.append("interface_mismatch")
        if current_skeleton_gate and "skeleton_boundary" not in active_categories:
            active_categories.append("skeleton_boundary")
        for category in split_categories(current.get("static_gate_categories", "")):
            if category not in active_categories:
                active_categories.append(category)

    for category in previous_categories:
        if category not in active_categories and category not in fixed_categories:
            fixed_categories.append(category)

    do_not_regress = []
    if best_status in {"syntax_pass", "functional_pass"}:
        do_not_regress.append("preserve the interface and syntactically valid structure from the best verified attempt")
    if "width_or_slice" in fixed_categories:
        do_not_regress.append("do not reintroduce out-of-range part selects or inconsistent bus slicing")
    if "syntax_verilog2001" in fixed_categories:
        do_not_regress.append("keep declarations and procedural/continuous assignments Verilog-2001 compatible")
    if "bad_instantiation_or_missing_helper" in fixed_categories or "bad_instantiation" in fixed_categories:
        do_not_regress.append("do not instantiate missing or mismatched helper modules")
    if current_interface_gate:
        do_not_regress.append("do not rename the required top module after the interface gate has corrected it")
    if current_skeleton_gate:
        do_not_regress.append("do not violate the programmatic skeleton boundary after it has removed or repaired template drift")
    if current_static_gate:
        do_not_regress.append("do not reintroduce static Verilog issues already detected by the gate")
    if not do_not_regress:
        do_not_regress.append("keep the exact module header and port list unchanged")

    if current_stage == "syntax":
        repair_target = "fix only the syntax/elaboration blockers before changing functional behavior"
    elif best_status == "syntax_pass":
        repair_target = "preserve the syntax-passing structure and repair the functional mismatch locally"
    else:
        repair_target = "repair the current failure while preserving the required interface"

    state = {
        "best_status": best_status,
        "best_iteration": best_iteration,
        "current_stage": current_stage,
        "current_family": current_family,
        "active_categories": active_categories or ["unclassified"],
        "fixed_categories": fixed_categories,
        "preferred_action": current_action,
        "interface_gate_action": current_interface_gate,
        "skeleton_gate_action": current_skeleton_gate,
        "static_gate_action": current_static_gate,
        "current_error_signature": current_error,
        "do_not_regress": do_not_regress,
        "repair_target": repair_target,
    }
    return state


def format_repair_state(state: dict, max_items: int = 5):
    if not state:
        return ""

    def bullet_list(items):
        return "\n".join(f"- {item}" for item in items[:max_items]) if items else "- none"

    return (
        f"best_status: {state.get('best_status', 'none')}\n"
        f"best_iteration: {state.get('best_iteration', '')}\n"
        f"current_stage: {state.get('current_stage', 'unknown')}\n"
        f"current_family: {state.get('current_family', 'unknown')}\n"
        f"preferred_action: {state.get('preferred_action', 'unknown')}\n"
        f"interface_gate_action: {state.get('interface_gate_action', '')}\n"
        f"skeleton_gate_action: {state.get('skeleton_gate_action', '')}\n"
        f"static_gate_action: {state.get('static_gate_action', '')}\n"
        f"current_error_signature: {state.get('current_error_signature', '')}\n"
        "active_error_categories:\n"
        + bullet_list(state.get("active_categories", []))
        + "\nfixed_error_categories:\n"
        + bullet_list(state.get("fixed_categories", []))
        + "\ndo_not_regress:\n"
        + bullet_list(state.get("do_not_regress", []))
        + f"\nrepair_target: {state.get('repair_target', '')}"
    )


def diagnose_failure(
    *,
    prompt: str,
    candidate: str,
    error_text: str,
    notes,
    result_dir: Path,
    iteration: int,
    enable_domain_knowledge: bool = True,
):
    diagnosis_prompt = build_diagnosis_prompt(
        prompt,
        candidate,
        error_text,
        notes,
        enable_domain_knowledge=enable_domain_knowledge,
    )
    diagnosis_text = generate_text_only_with_limits(diagnosis_prompt, max_new_tokens=384)
    (result_dir / f"iter_{iteration}_diagnosis.txt").write_text(diagnosis_text, encoding="utf-8")
    diagnosis = parse_diagnosis_text(diagnosis_text)
    diagnosis["interface_family"] = resolve_family_with_prompt(candidate, prompt, diagnosis.get("interface_family", ""))
    return diagnosis_text, diagnosis


def run_single_case(
    base_path: Path,
    module_id: int,
    test_id: int,
    max_iters: int,
    rag_path: Path | None,
    reflection_log: Path,
    *,
    seed: int | None = None,
    enable_patch: bool = True,
    strategy_profile: str = BENCHMARK_CLEAN,
    result_dir_name: str = "reflect_result",
    result_root: Path | None = None,
    enable_skeleton: bool = True,
    enable_domain_knowledge: bool = True,
    evaluation_access: str = LEGACY_ACCESS,
):
    case_dir, code_dir, prompt, image_path = load_case(base_path, module_id, test_id)
    configure_access(evaluation_access, prompt)
    if result_root is not None:
        result_dir = result_root / f"module{module_id}" / f"test{test_id}" / result_dir_name
    else:
        result_dir = case_dir / result_dir_name
    result_dir.mkdir(parents=True, exist_ok=True)

    history = []
    current_prompt = prompt
    current_image_path = str(image_path) if image_path else None

    for iteration in range(max_iters):
        set_generation_seed(None if seed is None else seed + iteration)
        raw_output = generate_code_with_limits(current_prompt, current_image_path, max_new_tokens=1536)
        candidate = clean_generated_code(raw_output)
        candidate, interface_gate_action, interface_gate_expected_top, interface_gate_current_top = apply_interface_gate(candidate, code_dir)
        skeleton_gate_action = ""
        skeleton_gate_expected_ports = ""
        port_gate_action = ""
        static_gate_action = ""
        static_gate_categories = ""
        static_gate_count = 0
        if enable_skeleton:
            skeleton_family = resolve_family_with_prompt(candidate, prompt, detect_interface_family(candidate))
            gate_result = apply_programmatic_skeleton_gate(
                candidate,
                code_dir,
                skeleton_family,
                strategy_profile,
            )
            candidate = gate_result["candidate"]
            skeleton_gate_action = gate_result["skeleton_action"]
            skeleton_gate_expected_ports = gate_result["expected_ports"]
            port_gate_action = gate_result["port_action"]
            static_gate_action = gate_result["static_action"]
            static_gate_categories = gate_result["static_categories"]
            static_gate_count = len(split_categories(static_gate_categories))

        diagnosis_text = ""
        diagnosis_excerpt = ""
        preferred_action = ""
        diagnosis_confidence = ""
        diagnosis_family = ""
        patch_attempted = False
        syntax_source = "raw"
        notes = []

        syntax_ok, syntax_error = syntax_check(candidate, code_dir)
        if not syntax_ok:
            detected_family = resolve_family_with_prompt(candidate, prompt, detect_interface_family(candidate))
            notes = retrieve_error_notes(
                syntax_error,
                rag_path,
                family=detected_family,
                stage="syntax",
                include_builtin=enable_domain_knowledge,
            )
            diagnosis_text, diagnosis = diagnose_failure(
                prompt=prompt,
                candidate=candidate,
                error_text=syntax_error,
                notes=notes,
                result_dir=result_dir,
                iteration=iteration,
                enable_domain_knowledge=enable_domain_knowledge,
            )
            diagnosis = force_patch_action(diagnosis, candidate, syntax_error)
            diagnosis_excerpt = "\n".join(diagnosis_text.splitlines()[:12])
            preferred_action = diagnosis.get("preferred_action", "")
            diagnosis_confidence = diagnosis.get("confidence", "")
            diagnosis_family = resolve_family_with_prompt(candidate, prompt, diagnosis.get("interface_family", ""))
            if enable_patch and should_apply_patch(diagnosis):
                patched_candidate = apply_patch_library(candidate, syntax_error, code_dir, diagnosis_family)
                if patched_candidate == candidate:
                    patched_candidate = apply_forced_family_template(candidate, diagnosis_family, strategy_profile)
                patch_attempted = patched_candidate != candidate
                if patch_attempted:
                    candidate = clean_generated_code(patched_candidate)
                    candidate, gate_action, gate_expected, gate_current = apply_interface_gate(candidate, code_dir)
                    if gate_action:
                        interface_gate_action = ";".join(
                            item for item in [interface_gate_action, f"post_patch:{gate_action}"] if item
                        )
                        interface_gate_expected_top = gate_expected or interface_gate_expected_top
                        interface_gate_current_top = gate_current or interface_gate_current_top
                    if enable_skeleton:
                        gate_result = apply_programmatic_skeleton_gate(
                            candidate,
                            code_dir,
                            diagnosis_family,
                            strategy_profile,
                        )
                        candidate = gate_result["candidate"]
                        post_skeleton_action = gate_result["skeleton_action"]
                        post_skeleton_ports = gate_result["expected_ports"]
                        if post_skeleton_action:
                            skeleton_gate_action = ";".join(
                                item for item in [skeleton_gate_action, f"post_patch:{post_skeleton_action}"] if item
                            )
                            skeleton_gate_expected_ports = post_skeleton_ports or skeleton_gate_expected_ports
                        if gate_result["port_action"]:
                            port_gate_action = ";".join(
                                item for item in [port_gate_action, f"post_patch:{gate_result['port_action']}"] if item
                            )
                        if gate_result["static_action"]:
                            static_gate_action = ";".join(
                                item for item in [static_gate_action, f"post_patch:{gate_result['static_action']}"] if item
                            )
                        merged_categories = split_categories(static_gate_categories) + split_categories(gate_result["static_categories"])
                        static_gate_categories = ",".join(dict.fromkeys(merged_categories))
                        static_gate_count = len(split_categories(static_gate_categories))
                    syntax_ok, syntax_error = syntax_check(candidate, code_dir)
                    syntax_source = "patched"

        history.append(
            {
                "iteration": iteration,
                "diagnosis_excerpt": diagnosis_excerpt,
                "preferred_action": preferred_action,
                "diagnosis_confidence": diagnosis_confidence,
                "diagnosis_family": diagnosis_family,
                "patch_attempted": patch_attempted,
                "interface_gate_action": interface_gate_action,
                "interface_gate_expected_top": interface_gate_expected_top,
                "interface_gate_current_top": interface_gate_current_top,
                "skeleton_gate_action": skeleton_gate_action,
                "skeleton_gate_expected_ports": skeleton_gate_expected_ports,
                "port_gate_action": port_gate_action,
                "static_gate_action": static_gate_action,
                "static_gate_categories": static_gate_categories,
                "static_gate_count": static_gate_count,
                "retrieved_categories": ",".join(dict.fromkeys(note.category for note in notes)),
                "retrieved_rule_count": len(notes),
                "syntax_ok": syntax_ok,
                "syntax_error": syntax_error,
                "syntax_source": syntax_source,
            }
        )
        repair_state = build_repair_state(history)
        repair_state_text = format_repair_state(repair_state)
        history[-1]["repair_state"] = repair_state
        history[-1]["repair_state_text"] = repair_state_text
        persist_history(result_dir, history)

        candidate_path = result_dir / f"iter_{iteration}.v"
        candidate_path.write_text(candidate, encoding="utf-8")
        (result_dir / f"iter_{iteration}.txt").write_text(raw_output, encoding="utf-8")

        if not syntax_ok:
            append_reflection_record(
                reflection_log,
                {
                    "module_id": module_id,
                    "test_id": test_id,
                    "iteration": iteration,
                    "stage": "syntax",
                    "event": "syntax_fail",
                    "error_signature": syntax_error.splitlines()[0] if syntax_error else "",
                    "category": notes[0].category if notes else "unclassified",
                    "reflection": flatten_reflections(notes),
                    "preferred_action": preferred_action,
                    "confidence": diagnosis_confidence,
                    "patch_attempted": patch_attempted,
                },
            )
            regenerate_only = (not enable_patch) or not should_apply_patch({"preferred_action": preferred_action, "confidence": diagnosis_confidence})
            current_prompt = build_reflection_prompt(
                prompt,
                candidate,
                syntax_error,
                notes,
                diagnosis_text,
                regenerate_only=regenerate_only,
                strategy_profile=strategy_profile,
                enable_skeleton=enable_skeleton,
                enable_domain_knowledge=enable_domain_knowledge,
                repair_state_text=repair_state_text,
            )
            continue

        compile_ok, compile_detail = functional_check(candidate_path, code_dir, result_dir / f"iter_{iteration}")
        final_source = "raw"
        if not compile_ok:
            detected_family = resolve_family_with_prompt(candidate, prompt, detect_interface_family(candidate))
            notes = retrieve_error_notes(
                compile_detail,
                rag_path,
                family=detected_family,
                stage="functional",
                include_builtin=enable_domain_knowledge,
            )
            diagnosis_text, diagnosis = diagnose_failure(
                prompt=prompt,
                candidate=candidate,
                error_text=compile_detail,
                notes=notes,
                result_dir=result_dir,
                iteration=iteration,
                enable_domain_knowledge=enable_domain_knowledge,
            )
            diagnosis = force_patch_action(diagnosis, candidate, compile_detail)
            diagnosis_excerpt = "\n".join(diagnosis_text.splitlines()[:12])
            preferred_action = diagnosis.get("preferred_action", "")
            diagnosis_confidence = diagnosis.get("confidence", "")
            diagnosis_family = resolve_family_with_prompt(candidate, prompt, diagnosis.get("interface_family", ""))
            patch_attempted = False
            if enable_patch and should_apply_patch(diagnosis):
                patched_candidate = apply_patch_library(candidate, compile_detail, code_dir, diagnosis_family)
                if patched_candidate == candidate:
                    patched_candidate = apply_forced_family_template(candidate, diagnosis_family, strategy_profile)
                patch_attempted = patched_candidate != candidate
                if patch_attempted:
                    candidate = clean_generated_code(patched_candidate)
                    candidate, gate_action, gate_expected, gate_current = apply_interface_gate(candidate, code_dir)
                    if gate_action:
                        history[-1]["interface_gate_action"] = ";".join(
                            item for item in [history[-1].get("interface_gate_action", ""), f"post_patch:{gate_action}"] if item
                        )
                        history[-1]["interface_gate_expected_top"] = gate_expected or history[-1].get("interface_gate_expected_top", "")
                        history[-1]["interface_gate_current_top"] = gate_current or history[-1].get("interface_gate_current_top", "")
                    if enable_skeleton:
                        gate_result = apply_programmatic_skeleton_gate(
                            candidate,
                            code_dir,
                            diagnosis_family,
                            strategy_profile,
                        )
                        candidate = gate_result["candidate"]
                        post_skeleton_action = gate_result["skeleton_action"]
                        post_skeleton_ports = gate_result["expected_ports"]
                        if post_skeleton_action:
                            history[-1]["skeleton_gate_action"] = ";".join(
                                item for item in [history[-1].get("skeleton_gate_action", ""), f"post_patch:{post_skeleton_action}"] if item
                            )
                            history[-1]["skeleton_gate_expected_ports"] = post_skeleton_ports or history[-1].get("skeleton_gate_expected_ports", "")
                        if gate_result["port_action"]:
                            history[-1]["port_gate_action"] = ";".join(
                                item for item in [history[-1].get("port_gate_action", ""), f"post_patch:{gate_result['port_action']}"] if item
                            )
                        if gate_result["static_action"]:
                            history[-1]["static_gate_action"] = ";".join(
                                item for item in [history[-1].get("static_gate_action", ""), f"post_patch:{gate_result['static_action']}"] if item
                            )
                        merged_categories = split_categories(history[-1].get("static_gate_categories", "")) + split_categories(gate_result["static_categories"])
                        history[-1]["static_gate_categories"] = ",".join(dict.fromkeys(merged_categories))
                        history[-1]["static_gate_count"] = len(split_categories(history[-1]["static_gate_categories"]))
                    candidate_path.write_text(candidate, encoding="utf-8")
                    compile_ok, compile_detail = functional_check(candidate_path, code_dir, result_dir / f"iter_{iteration}_patched")
                    final_source = "patched"
            history[-1]["diagnosis_excerpt"] = diagnosis_excerpt
            history[-1]["preferred_action"] = preferred_action
            history[-1]["diagnosis_confidence"] = diagnosis_confidence
            history[-1]["diagnosis_family"] = diagnosis_family
            history[-1]["patch_attempted"] = patch_attempted
            history[-1]["retrieved_categories"] = ",".join(dict.fromkeys(note.category for note in notes))
            history[-1]["retrieved_rule_count"] = len(notes)
        history[-1]["functional_ok"] = compile_ok
        history[-1]["functional_detail"] = compile_detail
        history[-1]["functional_source"] = final_source
        repair_state = build_repair_state(history)
        repair_state_text = format_repair_state(repair_state)
        history[-1]["repair_state"] = repair_state
        history[-1]["repair_state_text"] = repair_state_text
        persist_history(result_dir, history)
        if compile_ok:
            success_notes = notes if patch_attempted or final_source == "patched" else []
            append_reflection_record(
                reflection_log,
                {
                    "module_id": module_id,
                    "test_id": test_id,
                    "iteration": iteration,
                    "stage": "functional",
                    "event": "patch_success" if final_source == "patched" else "direct_success",
                    "error_signature": compile_detail.splitlines()[0] if compile_detail else "",
                    "category": success_notes[0].category if success_notes else ("patched_success" if final_source == "patched" else "direct_success"),
                    "reflection": flatten_reflections(success_notes),
                    "source": final_source,
                    "syntax_source": history[-1]["syntax_source"],
                    "preferred_action": preferred_action,
                    "confidence": diagnosis_confidence,
                    "patch_attempted": patch_attempted,
                },
            )
            break
        append_reflection_record(
            reflection_log,
            {
                "module_id": module_id,
                "test_id": test_id,
                "iteration": iteration,
                "stage": "functional",
                "event": "functional_fail",
                "error_signature": compile_detail.splitlines()[0] if compile_detail else "",
                "category": notes[0].category if notes else "unclassified",
                "reflection": flatten_reflections(notes),
                "source": final_source,
                "syntax_source": history[-1]["syntax_source"],
                "preferred_action": preferred_action,
                "confidence": diagnosis_confidence,
                "patch_attempted": patch_attempted,
            },
        )
        regenerate_only = (not enable_patch) or not should_apply_patch({"preferred_action": preferred_action, "confidence": diagnosis_confidence})
        current_prompt = build_reflection_prompt(
            prompt,
            candidate,
            compile_detail,
            notes,
            diagnosis_text,
            regenerate_only=regenerate_only,
            strategy_profile=strategy_profile,
            enable_skeleton=enable_skeleton,
            enable_domain_knowledge=enable_domain_knowledge,
            repair_state_text=repair_state_text,
        )

    persist_history(result_dir, history)
    return history


def main():

    parser = argparse.ArgumentParser(description="Single-agent iterative Verilog generation with error reflection.")
    parser.add_argument("--base-directory", default="..", help="Dataset root relative to this script.")
    parser.add_argument("--model-path", default=None, help="Path to the local model directory. Required unless MGEMMV_MODEL_PATH is set.")
    parser.add_argument("--module-id", type=int, required=True, help="Target module id.")
    parser.add_argument("--test-id", type=int, required=True, help="Target test id.")
    parser.add_argument("--max-iters", type=int, default=3, help="Maximum reflection iterations.")
    parser.add_argument("--rag-path", default="", help="Optional JSONL reflection database path.")
    parser.add_argument(
        "--reflection-log",
        default="./error_reflection_db.jsonl",
        help="Where to append reflection samples. Default: ./error_reflection_db.jsonl",
    )
    parser.add_argument("--seed", type=int, default=1234, help="Base random seed for deterministic sampling.")
    parser.add_argument("--no-patch", action="store_true", help="Disable patch execution and use regenerate-only routing.")
    parser.add_argument(
        "--strategy-profile",
        choices=[BENCHMARK_CLEAN, ORACLE_DEBUG],
        default=BENCHMARK_CLEAN,
        help="Strategy profile. Default: benchmark_clean",
    )
    parser.add_argument(
        "--result-dir-name",
        default="reflect_result",
        help="Per-case output directory name. Default: reflect_result",
    )
    parser.add_argument(
        "--result-root",
        default="",
        help="Optional root directory for all per-case outputs. Default writes under each case directory.",
    )
    parser.add_argument(
        "--evaluation-access",
        choices=VALID_ACCESS_POLICIES,
        default=LEGACY_ACCESS,
        help="Evaluator access policy. public_only exposes only public contracts and categorical feedback.",
    )
    args = parser.parse_args()

    if args.model_path:
        os.environ["MGEMMV_MODEL_PATH"] = args.model_path

    base_path = (SCRIPT_DIR / args.base_directory).resolve()
    rag_path = Path(args.rag_path).resolve() if args.rag_path else None
    reflection_log = Path(args.reflection_log).resolve()
    result_root = Path(args.result_root).resolve() if args.result_root else None

    start = time.time()
    history = run_single_case(
        base_path,
        args.module_id,
        args.test_id,
        args.max_iters,
        rag_path,
        reflection_log,
        seed=args.seed,
        enable_patch=not args.no_patch,
        strategy_profile=args.strategy_profile,
        result_dir_name=args.result_dir_name,
        result_root=result_root,
        enable_skeleton=True,
        enable_domain_knowledge=True,
        evaluation_access=args.evaluation_access,
    )
    end = time.time()

    print(json.dumps(history, ensure_ascii=False, indent=2))
    print(f"\n[Total Runtime] {end - start:.2f} seconds")


if __name__ == "__main__":
    main()
