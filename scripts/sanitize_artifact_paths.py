"""Remove personal absolute paths from generated text artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from release_common import sanitize_public_text
from validate_release import TEXT_SUFFIXES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    checked = 0
    changed = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        checked += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        sanitized = sanitize_public_text(text)
        if sanitized != text:
            path.write_text(sanitized, encoding="utf-8")
            changed += 1
    print(f"Artifact path sanitation: checked={checked}, changed={changed}")
    print(f"Root: {root.name}")


if __name__ == "__main__":
    main()
