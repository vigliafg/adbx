"""Avvio di adbx."""

from __future__ import annotations

import argparse
import hashlib
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="adbx", description="Alpha Four v3 clone")
    parser.add_argument("--version", action="version", version=f"adbx {__version__}")
    parser.add_argument("--smoke", action="store_true",
                        help="avvio headless: costruisce la schermata e stampa un digest")
    parser.add_argument("--dump", action="store_true",
                        help="con --smoke stampa il dump completo della griglia")
    args = parser.parse_args(argv)

    if args.smoke:
        from .screen.demo import demo_buffer

        buffer = demo_buffer()
        dump = buffer.dump()
        digest = hashlib.sha256(dump.encode("utf-8")).hexdigest()[:16]
        if args.dump:
            sys.stdout.write(dump)
        print(f"adbx {__version__}: griglia {buffer.width}x{buffer.height}, "
              f"digest {digest}")
        return 0

    try:
        from .app import run
    except ImportError as exc:  # pragma: no cover
        print(f"PyQt6 non disponibile: {exc}", file=sys.stderr)
        return 2
    return run(sys.argv if argv is None else [sys.argv[0], *argv])


if __name__ == "__main__":
    raise SystemExit(main())
