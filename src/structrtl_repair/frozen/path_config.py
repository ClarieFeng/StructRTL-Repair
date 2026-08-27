import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]


def extract_model_path_from_argv(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    for index, arg in enumerate(argv):
        if arg == "--model-path" and index + 1 < len(argv):
            return argv[index + 1]
        if arg.startswith("--model-path="):
            return arg.split("=", 1)[1]
    return None


def install_model_path_from_argv(argv=None):
    cli_path = extract_model_path_from_argv(argv)
    if cli_path:
        os.environ["MGEMMV_MODEL_PATH"] = str(Path(cli_path).expanduser())
    return cli_path


def resolve_model_path(explicit_path=None, require_exists=True):
    candidates = []

    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())

    cli_path = extract_model_path_from_argv()
    if cli_path:
        candidates.append(Path(cli_path).expanduser())

    env_path = os.getenv("MGEMMV_MODEL_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())

    checked = []
    for candidate in candidates:
        candidate = candidate.expanduser()
        if str(candidate) in checked:
            continue
        checked.append(str(candidate))
        if candidate.exists():
            return candidate

    if require_exists:
        checked_text = "\n".join(f"  - {item}" for item in checked) or "  - <none>"
        raise FileNotFoundError(
            "MGEMMV model directory not found. You must pass --model-path or set MGEMMV_MODEL_PATH.\n"
            f"Checked:\n{checked_text}"
        )

    return None
