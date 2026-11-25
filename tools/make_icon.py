#!/usr/bin/env python3
"""Genera le icone dell'app (PNG, ICO, ICNS) in `packaging/icons/`.

Richiede Pillow. L'icona riprende il tema Newport di Alpha Four: campo blu,
bordo bianco a doppia linea e monogramma `A4` in DejaVu Sans Mono.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "packaging" / "icons"
FONT = ROOT / "src" / "adbx" / "data" / "fonts" / "DejaVuSansMono-Bold.ttf"

BLUE = (0, 0, 170)
WHITE = (255, 255, 255)
YELLOW = (255, 255, 85)
BLACK = (0, 0, 0)
BASE = 512


def draw_icon(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scale = size / BASE

    def box(x0: float, y0: float, x1: float, y1: float, radius: float,
            fill=None, outline=None, width: int = 0) -> None:
        draw.rounded_rectangle(
            (x0 * scale, y0 * scale, x1 * scale, y1 * scale),
            radius=radius * scale, fill=fill, outline=outline, width=width)

    # pannello blu con bordo bianco a doppia linea, come la finestra DOS
    box(6, 6, BASE - 6, BASE - 6, 72, fill=BLUE, outline=WHITE, width=10)
    box(28, 28, BASE - 28, BASE - 28, 56, outline=WHITE, width=4)

    font = ImageFont.truetype(str(FONT), int(220 * scale))
    text = "A4"
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(((size - (right - left)) / 2 - left, size * 0.30 - top),
              text, font=font, fill=WHITE)

    small = ImageFont.truetype(str(FONT), int(84 * scale))
    label = "80x25"
    left, top, right, bottom = draw.textbbox((0, 0), label, font=small)
    draw.text(((size - (right - left)) / 2 - left, size * 0.655 - top),
              label, font=small, fill=YELLOW)

    draw.line((size * 0.22, size * 0.615, size * 0.78, size * 0.615),
              fill=BLACK, width=max(1, int(6 * scale)))
    return image


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    png = draw_icon(512)
    png.save(OUT / "adbx-legacy.png")

    sizes = [16, 24, 32, 48, 64, 128, 256]
    png.save(OUT / "adbx-legacy.ico", sizes=[(s, s) for s in sizes])
    png.save(OUT / "adbx-legacy.icns")
    print(f"icone scritte in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
