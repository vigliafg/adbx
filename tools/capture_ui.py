"""Genera i rendering canonici della griglia di celle.

Uso:
    python tools/capture_ui.py                     # docs/render/
    python tools/capture_ui.py --pixel-size 24 --out /tmp/adbx
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PyQt6.QtGui import QGuiApplication  # noqa: E402

from adbx.render.qt_renderer import CellRenderer  # noqa: E402
from adbx.shell import screens  # noqa: E402
from adbx.shell.state import demo_state  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "docs" / "render"))
    parser.add_argument("--pixel-size", type=int, default=18,
                        help="altezza del font in pixel; la cella ne deriva")
    args = parser.parse_args(argv)

    app = QGuiApplication(sys.argv[:1])  # noqa: F841
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    renderer = CellRenderer(pixel_size=args.pixel_size)
    renderer.use_natural_size(args.pixel_size, dpr=1.0)
    print(f"font {renderer.family}, corpo {args.pixel_size}px, "
          f"cella {renderer.cell_w:.2f}x{renderer.cell_h:.2f}")

    state = demo_state()
    menu = screens.main_menu(state, selected=0)
    directory = screens.directory(
        state, cursor=0,
        input_text=state.listing.entries[0].selectable_text,
        input_cursor=len(state.listing.entries[0].selectable_text))
    help_view, _spans, _positions = screens.help_overlay(
        screens.main_menu(state, selected=5), "choose")
    structure = screens.structure(state)
    status = screens.status_screen(state)

    shots = {
        "01-main-menu": menu,
        "02-directory": directory,
        "03-help": help_view,
        "04-structure": structure,
        "05-status": status,
    }
    for name, view in shots.items():
        image = renderer.to_image(view.buffer)
        path = out / f"{name}.png"
        image.save(str(path))
        print(f"{path.relative_to(ROOT)} {image.width()}x{image.height()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
