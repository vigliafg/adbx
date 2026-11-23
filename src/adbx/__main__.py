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
    parser.add_argument("--data", metavar="DIR",
                        help="cartella dati da mostrare all'avvio")
    parser.add_argument("--open", metavar="FILE",
                        help="database o set da aprire all'avvio")
    args = parser.parse_args(argv)

    if args.smoke:
        from .shell.controller import demo_controller

        buffer = demo_controller().view().buffer
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
    return run([sys.argv[0]], data=args.data, open_path=args.open)


if __name__ == "__main__":
    raise SystemExit(main())
