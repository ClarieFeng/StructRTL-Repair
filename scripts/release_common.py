"""Shared utilities for public reproduction entry points."""

from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_DIR = REPO_ROOT / "src" / "structrtl_repair" / "frozen"

BACKENDS = {
    "mgemmv_qwen_7b": "ablation_v6_2_public_protocol.py",
    "mgemmv_llama_11b": "ablation_v6_2_public_protocol.py",
    "qwen2_5_vl_7b": "ablation_v6_2_public_protocol.py",
    "qwen3_vl_8b": "ablation_v6_2_public_protocol.py",
    "llama3_2_11b_vision": "ablation_v6_2_public_protocol.py",
    "minicpm_v_4_5_8b": "ablation_v6_2_minicpm_public_protocol.py",
    "internvl3_5_8b": "ablation_v6_2_internvl3_5_public_protocol.py",
}

PERSONAL_PATH_PATTERNS = (
    re.compile(r"/home/[A-Za-z0-9._-]+"),
    re.compile(r"[A-Za-z]:\\Users\\[^\\/\s\"']+"),
)


def sanitize_public_text(value: str) -> str:
    """Replace workstation home prefixes while retaining diagnostic context."""
    sanitized = value
    for pattern in PERSONAL_PATH_PATTERNS:
        sanitized = pattern.sub("<HOME>", sanitized)
    return sanitized


def sanitize_public_value(value):
    if isinstance(value, str):
        return sanitize_public_text(value)
    if isinstance(value, list):
        return [sanitize_public_value(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_public_value(item) for key, item in value.items()}
    return value


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_case_id(case_id: str) -> tuple[int, int]:
    normalized = case_id.strip().replace("\\", "/")
    try:
        module_text, test_text = normalized.split("/", 1)
        return int(module_text.removeprefix("module")), int(test_text.removeprefix("test"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid case identifier: {case_id!r}") from exc


def read_manifest(dataset: str) -> list[dict[str, str]]:
    path = REPO_ROOT / "datasets" / dataset / "manifest.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown dataset or missing manifest: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def selected_rows(dataset: str, case_ids: list[str] | None) -> list[dict[str, str]]:
    rows = read_manifest(dataset)
    if not case_ids:
        return rows
    wanted = {case_id.replace("\\", "/") for case_id in case_ids}
    selected = [row for row in rows if row["case_id"] in wanted]
    missing = sorted(wanted - {row["case_id"] for row in selected})
    if missing:
        raise ValueError("Cases absent from manifest: " + ", ".join(missing))
    return selected


def materialize_legacy_dataset(
    dataset: str,
    destination: Path,
    case_ids: list[str] | None = None,
) -> list[str]:
    """Create the layout expected by the frozen runner without changing source data."""
    dataset_root = REPO_ROOT / "datasets" / dataset
    rows = selected_rows(dataset, case_ids)
    staged: list[str] = []
    for row in rows:
        module_id, test_id = parse_case_id(row["case_id"])
        public_case = dataset_root / "public" / f"module{module_id:02d}" / f"test{test_id}"
        evaluator_case = dataset_root / "evaluator" / f"module{module_id:02d}" / f"test{test_id}"
        if not public_case.is_dir() or not evaluator_case.is_dir():
            raise FileNotFoundError(f"Incomplete split case: {row['case_id']}")

        case_dir = destination / f"module{module_id}" / f"test{test_id}"
        description_dir = case_dir / "description"
        code_dir = case_dir / "code"
        description_dir.mkdir(parents=True, exist_ok=True)
        code_dir.mkdir(parents=True, exist_ok=True)

        description = dataset_root / row["description"]
        image_value = row.get("circuit_image", "").strip()
        if not image_value:
            raise FileNotFoundError(f"No public circuit image declared for {row['case_id']}")
        image = dataset_root / image_value
        if not description.is_file() or not image.is_file():
            raise FileNotFoundError(f"Missing public task artifact for {row['case_id']}")
        shutil.copy2(description, description_dir / "description0.txt")
        shutil.copy2(image, description_dir / image.name)
        (description_dir / "image_name0.txt").write_text(image.name + "\n", encoding="utf-8")

        for source in evaluator_case.glob("*.v"):
            shutil.copy2(source, code_dir / source.name)
        if not (code_dir / "tb.v").is_file():
            raise FileNotFoundError(f"Missing evaluator testbench for {row['case_id']}")
        staged.append(row["case_id"])
    return staged


def resolve_model_paths(path: Path) -> dict[str, str]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to read model path configuration.") from exc
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(key): str(value) for key, value in (payload.get("models") or {}).items()}
