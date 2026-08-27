"""Collect a sanitized environment and local model revision lock."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from release_common import (
    REPO_ROOT,
    resolve_model_paths,
    sanitize_public_text,
    sanitize_public_value,
)


PACKAGES = (
    "torch",
    "torchvision",
    "transformers",
    "accelerate",
    "bitsandbytes",
    "numpy",
    "pandas",
    "scipy",
    "Pillow",
    "PyYAML",
    "sentencepiece",
    "timm",
    "einops",
    "reportlab",
    "svglib",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> dict[str, object]:
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=60,
        )
        return {
            "returncode": result.returncode,
            "output": sanitize_public_text(result.stdout.strip()),
        }
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"returncode": None, "output": type(exc).__name__}


def package_versions() -> dict[str, str]:
    versions = {}
    for package in PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    return versions


def torch_runtime() -> dict[str, object]:
    try:
        import torch
    except Exception as exc:
        return {"import_error": f"{type(exc).__name__}: {exc}"}
    cuda_available = torch.cuda.is_available()
    return {
        "torch_version": torch.__version__,
        "cuda_build": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(),
        "cuda_available": cuda_available,
        "device_count": torch.cuda.device_count() if cuda_available else 0,
        "devices": [torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())]
        if cuda_available
        else [],
    }


def snapshot_revision(path: Path) -> str:
    parts = list(path.resolve().parts)
    if "snapshots" in parts:
        index = parts.index("snapshots")
        if index + 1 < len(parts):
            return parts[index + 1]
    git_result = run(["git", "-C", str(path), "rev-parse", "HEAD"])
    if git_result["returncode"] == 0:
        return str(git_result["output"]).splitlines()[0]
    return "local_directory_no_revision_metadata"


def model_record(identifier: str, model_path: str) -> dict[str, object]:
    root = Path(model_path).expanduser().resolve()
    if not root.is_dir():
        return {"model": identifier, "directory_name": root.name, "status": "missing"}
    config_fields = {}
    config_path = root / "config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        for field in ("_name_or_path", "architectures", "model_type", "transformers_version", "auto_map"):
            if field in config:
                config_fields[field] = sanitize_public_value(config[field])
    tracked_names = {
        "config.json",
        "generation_config.json",
        "preprocessor_config.json",
        "processor_config.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
    }
    files = []
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        is_remote_code = path.suffix == ".py" and re.search(
            r"(?:configuration|modeling|processing|tokenization|conversation)", path.name
        )
        if path.name in tracked_names or is_remote_code:
            files.append({"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {
        "model": identifier,
        "directory_name": root.name,
        "status": "present",
        "revision": snapshot_revision(root),
        "config": config_fields,
        "tracked_files": files,
    }


def sanitize_conda_export(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith("prefix:"):
            continue
        if line.startswith("name:"):
            lines.append("name: structrtl-repair-a800")
            continue
        lines.append(line)
    return sanitize_public_text("\n".join(lines).rstrip()) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    model_paths = resolve_model_paths(Path(args.models).expanduser().resolve())

    system_tools = {
        "nvidia_smi": run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ]
        ),
        "nvcc": run(["nvcc", "--version"]),
        "iverilog": run(["iverilog", "-V"]),
        "vvp": run(["vvp", "-V"]),
        "yosys": run(["yosys", "-V"]),
        "netlistsvg": run(["netlistsvg", "--version"]),
    }
    runtime = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": package_versions(),
        "torch_runtime": torch_runtime(),
        "tools": system_tools,
        "repository_commit": run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
    }
    (output / "runtime_lock.json").write_text(json.dumps(runtime, indent=2) + "\n", encoding="utf-8")
    models = [model_record(identifier, path) for identifier, path in sorted(model_paths.items())]
    (output / "model_revisions.json").write_text(json.dumps(models, indent=2) + "\n", encoding="utf-8")

    freeze = run([sys.executable, "-m", "pip", "list", "--format=freeze"])
    (output / "pip_freeze.txt").write_text(str(freeze["output"]) + "\n", encoding="utf-8")
    conda_export = run(["conda", "env", "export", "--no-builds"])
    (output / "conda_environment.yml").write_text(
        sanitize_conda_export(str(conda_export["output"])), encoding="utf-8"
    )
    conda_explicit = run(["conda", "list", "--explicit"])
    (output / "conda_explicit.txt").write_text(str(conda_explicit["output"]) + "\n", encoding="utf-8")
    print(f"Environment lock: {output}")
    print(f"Models recorded: {len(models)}")


if __name__ == "__main__":
    main()
