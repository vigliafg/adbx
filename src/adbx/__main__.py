"""Avvio di adbx."""

from __future__ import annotations

import argparse
import hashlib
import sys

from . import __version__


def prepare_frozen_environment() -> bool:
    """Adatta stdio e cartella dati quando gira un eseguibile pacchettizzato.

    L'eseguibile finestrato di Windows non ha console: `sys.stdout` è `None` e
    un `print` farebbe fallire anche `--version` o `--smoke`. Inoltre la
    cartella di installazione può essere in sola lettura, quindi la
    configurazione va nella cartella utente. Restituisce True se l'app è
    pacchettizzata.
    """
    import os

    if not getattr(sys, "frozen", False):
        return False
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    if "ADBX_DATA" not in os.environ:
        from .config.paths import user_data_dir

        os.environ["ADBX_DATA"] = str(user_data_dir())
    return True


def main(argv: list[str] | None = None) -> int:
    prepare_frozen_environment()
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
    parser.add_argument("--app", metavar="NAME",
                        help="applicazione da avviare")
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
        from .app.window import run
    except ImportError as exc:  # pragma: no cover
        print(f"PyQt6 non disponibile: {exc}", file=sys.stderr)
        return 2
    return run([sys.argv[0]], data=args.data, open_path=args.open,
               application=args.app)


if __name__ == "__main__":
    raise SystemExit(main())
