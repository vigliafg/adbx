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
from adbx.screen.demo import build_demo_scene, demo_buffer  # noqa: E402


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

    shots = {
        "01-main-menu": demo_buffer(show_popup=False),
        "02-popup": demo_buffer(show_popup=True),
    }
    for name, buffer in shots.items():
        image = renderer.to_image(buffer)
        path = out / f"{name}.png"
        image.save(str(path))
        print(f"{path.relative_to(ROOT)} {image.width()}x{image.height()}")

    scene = build_demo_scene(selected=3)
    print(f"scene: {len(scene.layers)} strati")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
