#!/usr/bin/env python3
"""Stampa le note di release di una versione, estratte da docs/CHANGELOG.md.

    python tools/release_notes.py 0.10.0 > release-notes.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "docs" / "CHANGELOG.md"


def section(text: str, version: str) -> str:
    pattern = re.compile(
        r"^##\s+" + re.escape(version) + r"\s*$\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    version = args[0]
    body = section(CHANGELOG.read_text(encoding="utf-8"), version)
    if not body:
        print(f"versione {version} assente in {CHANGELOG}", file=sys.stderr)
        return 1
    print(f"# adbx-legacy {version}\n")
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
