"""Public-only evaluation access policy for iterative RTL repair.

The evaluator may internally execute a private testbench, but this module
ensures that an agent only receives (1) the public module contract embedded in
the task description and (2) categorical tool feedback.  It intentionally
never exposes test vectors, expected values, private helper names, or the
testbench source.
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass


LEGACY_ACCESS = "legacy"
PUBLIC_ONLY_ACCESS = "public_only"
VALID_ACCESS_POLICIES = (LEGACY_ACCESS, PUBLIC_ONLY_ACCESS)


@dataclass(frozen=True)
class PublicContract:
    top: str
    ports: tuple[str, ...]
    directions: dict[str, str]
    params: dict[str, str]

    def as_dict(self) -> dict:
        return {
            "top": self.top,
            "ports": list(self.ports),
            "directions": dict(self.directions),
            "connections": {},
            "params": dict(self.params),
            "source": "public_description",
        }


_ACTIVE_ACCESS_POLICY = LEGACY_ACCESS
_ACTIVE_PUBLIC_CONTRACT: dict | None = None
PRIVATE_RAG_MARKERS = re.compile(
    r"(?:mismatch!|\bexpected\b|\bgot\b|testbench|\btb\.v\b|\bgolden\b|"
    r"pass(?:ed)? rate|correct outputs|test summary|filelist\.txt)",
    flags=re.IGNORECASE,
)


def _strip_verilog_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", text)


def _matching_paren(text: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _last_identifier(declaration: str) -> str:
    declaration = re.sub(r"\[[^\]]*\]", " ", declaration)
    declaration = re.sub(r"=.*$", "", declaration)
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_$]*\b", declaration)
    ignored = {"input", "output", "inout", "wire", "reg", "logic", "signed", "unsigned"}
    tokens = [token for token in tokens if token.lower() not in ignored]
    return tokens[-1] if tokens else ""


def parse_public_contract(prompt: str) -> dict:
    """Parse the public ANSI-style Verilog header provided in a description."""
    text = _strip_verilog_comments(prompt)
    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b", text)
    if not match:
        raise ValueError("Public description does not contain a Verilog module header.")

    top = match.group(1)
    cursor = match.end()
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1

    params_text = ""
    if cursor < len(text) and text[cursor] == "#":
        cursor += 1
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text) or text[cursor] != "(":
            raise ValueError(f"Malformed public parameter list for module {top}.")
        params_close = _matching_paren(text, cursor)
        if params_close < 0:
            raise ValueError(f"Unclosed public parameter list for module {top}.")
        params_text = text[cursor + 1:params_close]
        cursor = params_close + 1

    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    if cursor >= len(text) or text[cursor] != "(":
        raise ValueError(f"Public description has no ANSI port list for module {top}.")
    ports_close = _matching_paren(text, cursor)
    if ports_close < 0:
        raise ValueError(f"Unclosed public port list for module {top}.")

    params = {
        name: value.strip()
        for name, value in re.findall(
            r"\bparameter\s+(?:[A-Za-z_][A-Za-z0-9_$]*\s+)?([A-Za-z_][A-Za-z0-9_$]*)\s*=\s*([^,\n\)]+)",
            params_text,
        )
    }
    directions: dict[str, str] = {}
    ports: list[str] = []
    for declaration in text[cursor + 1:ports_close].split(","):
        direction = re.search(r"\b(input|output|inout)\b", declaration, flags=re.IGNORECASE)
        name = _last_identifier(declaration)
        if direction and name:
            directions[name] = direction.group(1).lower()
            ports.append(name)

    if not ports:
        raise ValueError(f"No public ports parsed for module {top}.")
    return PublicContract(top, tuple(dict.fromkeys(ports)), directions, params).as_dict()


def configure_access(policy: str, prompt: str) -> dict | None:
    """Set process-local policy for one sequential evaluation case."""
    global _ACTIVE_ACCESS_POLICY, _ACTIVE_PUBLIC_CONTRACT
    if policy not in VALID_ACCESS_POLICIES:
        raise ValueError(f"Unknown evaluation access policy: {policy}")
    _ACTIVE_ACCESS_POLICY = policy
    _ACTIVE_PUBLIC_CONTRACT = parse_public_contract(prompt) if policy == PUBLIC_ONLY_ACCESS else None
    return _ACTIVE_PUBLIC_CONTRACT


def is_public_only() -> bool:
    return _ACTIVE_ACCESS_POLICY == PUBLIC_ONLY_ACCESS


def active_public_contract() -> dict | None:
    return _ACTIVE_PUBLIC_CONTRACT


def is_public_safe_rag_record(record: dict) -> bool:
    """Reject historical RAG entries that encode private evaluator information."""
    try:
        text = json.dumps(record, ensure_ascii=False)
    except (TypeError, ValueError):
        return False
    return not bool(PRIVATE_RAG_MARKERS.search(text))


def sanitize_private_tool_output(raw_output: str, stage: str) -> str:
    """Return a category-level observation that is safe to show the agent."""
    text = (raw_output or "").lower()
    if stage == "compile":
        if any(token in text for token in ("unknown module type", "invalid module instantiation")):
            return "public_compile: missing_or_mismatched_module. Rebuild a self-contained module from the public interface."
        if any(token in text for token in ("is not a port of", "wrong number of ports", "too many arguments", "too few arguments")):
            return "public_compile: port_contract_mismatch. Preserve the public module name, port list, directions, and widths."
        if any(token in text for token in ("out of range", "out of order", "indefinite width", "expects", "got")):
            return "public_compile: width_or_slice_mismatch. Recheck public bus indexing and parameter-derived widths."
        if "syntax error" in text:
            return "public_compile: syntax_verilog2001. Produce one self-contained synthesizable Verilog-2001 module."
        return "public_compile: elaboration_or_compilation_failure. Recheck the public module contract and remove unsupported helper dependencies."

    if "timed out" in text:
        return "public_functional: simulation_timeout. Simplify the implementation and avoid unintended combinational or sequential loops."
    return "public_functional: functional_mismatch. The private evaluator found behavior inconsistent with the public specification; no vectors, expected values, or testbench details are exposed."
