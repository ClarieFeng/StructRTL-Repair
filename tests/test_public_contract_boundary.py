"""Source-level boundary tests that do not import a model backend."""

from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN = REPO_ROOT / "src" / "structrtl_repair" / "frozen"
BACKENDS = (
    "single_agent_reflect_v6_2_public_protocol.py",
    "single_agent_reflect_v6_2_minicpm_public_protocol.py",
    "single_agent_reflect_v6_2_internvl3_5_public_protocol.py",
)
ABLATION_BACKENDS = (
    "ablation_v6_2_public_protocol.py",
    "ablation_v6_2_minicpm_public_protocol.py",
    "ablation_v6_2_internvl3_5_public_protocol.py",
)


class PoisonPath:
    """Fail if a public-only code path attempts filesystem access."""

    def __truediv__(self, _name: str) -> "PoisonPath":
        return self

    def exists(self) -> bool:
        raise AssertionError("public_only attempted to inspect an evaluator path")

    def read_text(self, *args, **kwargs) -> str:
        raise AssertionError("public_only attempted to read an evaluator path")


def load_public_protocol():
    path = FROZEN / "public_evaluation_protocol.py"
    spec = importlib.util.spec_from_file_location("public_evaluation_protocol_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def extract_function(path: Path, function_name: str, namespace: dict):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == function_name
    )
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(path), "exec"), namespace)
    return namespace[function_name]


class PublicContractBoundaryTest(unittest.TestCase):
    def test_contract_parser_extracts_public_top(self):
        protocol = load_public_protocol()
        prompt = "module public_top(input wire a, output wire y);"
        contract = protocol.configure_access(protocol.PUBLIC_ONLY_ACCESS, prompt)
        self.assertEqual(contract["top"], "public_top")
        self.assertEqual(contract["ports"], ["a", "y"])

    def test_all_backends_resolve_top_without_evaluator_access(self):
        for filename in BACKENDS:
            with self.subTest(backend=filename):
                namespace = {
                    "Path": Path,
                    "is_public_only": lambda: True,
                    "active_public_contract": lambda: {"top": "public_top"},
                }
                resolver = extract_function(
                    FROZEN / filename,
                    "infer_expected_top_from_tb",
                    namespace,
                )
                self.assertEqual(resolver(PoisonPath()), "public_top")

    def test_all_ablation_clis_forward_public_access(self):
        for filename in ABLATION_BACKENDS:
            with self.subTest(backend=filename):
                source = (FROZEN / filename).read_text(encoding="utf-8")
                self.assertIn('"--evaluation-access"', source)
                self.assertGreaterEqual(source.count("evaluation_access=args.evaluation_access"), 2)
                self.assertIn('row["evaluation_access"] = args.evaluation_access', source)


if __name__ == "__main__":
    unittest.main()
