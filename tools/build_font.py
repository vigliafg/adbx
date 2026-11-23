"""Genera la tabella bitmap CP437 8x16 usata dal motore a celle.

Il font derivato è DejaVu Sans Mono (licenza Bitstream Vera): il file
prodotto, `src/adbx/data/cp437_8x16.bin`, contiene 256 glifi da 16 byte,
uno per riga, bit piu' significativo a sinistra.

Uso:
    python tools/build_font.py            # scrive il .bin e l'anteprima
    python tools/build_font.py --art A    # stampa un glifo in ASCII art
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GLYPH_W = 8
GLYPH_H = 16
FONT_SIZE = 13
BASELINE = 13
THRESHOLD = 96

ROOT = Path(__file__).resolve().parents[1]
OUT_BIN = ROOT / "src" / "adbx" / "data" / "cp437_8x16.bin"
OUT_PREVIEW = ROOT / "docs" / "render" / "font-cp437.png"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "/System/Library/Fonts/Menlo.ttc",
]


def find_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise SystemExit("font monospaziato non trovato: installa DejaVu Sans Mono")


def cp437_chars() -> list[str]:
    """256 caratteri CP437; i codici di controllo restano vuoti."""
    chars = []
    for byte in range(256):
        if byte < 0x20:
            chars.append(" ")
        else:
            chars.append(bytes([byte]).decode("cp437"))
    return chars


# -- glifi grafici disegnati a mano ---------------------------------------
# I caratteri di cornice non si prendono dal font tipografico: si disegnano
# sulla griglia 8x16, altrimenti le linee non sono continue tra celle adiacenti.

VX = {1: (3,), 2: (2, 4)}   # colonne della linea verticale
HY = {1: (7,), 2: (6, 8)}   # righe della linea orizzontale

# byte -> (su, giu, sinistra, destra); 0 assente, 1 singola, 2 doppia
ARMS: dict[int, tuple[int, int, int, int]] = {
    0xB3: (1, 1, 0, 0), 0xB4: (1, 1, 1, 0), 0xB5: (2, 2, 2, 0),
    0xB6: (2, 2, 0, 2), 0xB7: (0, 1, 2, 0), 0xB8: (1, 0, 2, 0),
    0xB9: (2, 2, 2, 0), 0xBA: (2, 2, 0, 0), 0xBB: (0, 2, 2, 0),
    0xBC: (2, 0, 2, 0), 0xBD: (1, 0, 2, 0), 0xBE: (1, 0, 0, 2),
    0xBF: (0, 1, 1, 0), 0xC0: (1, 0, 0, 1), 0xC1: (1, 0, 1, 1),
    0xC2: (0, 1, 1, 1), 0xC3: (1, 1, 0, 1), 0xC4: (0, 0, 1, 1),
    0xC5: (1, 1, 1, 1), 0xC6: (2, 2, 0, 1), 0xC7: (2, 2, 1, 0),
    0xC8: (2, 0, 0, 2), 0xC9: (0, 2, 0, 2), 0xCA: (2, 0, 2, 2),
    0xCB: (0, 2, 2, 2), 0xCC: (2, 2, 0, 2), 0xCD: (0, 0, 2, 2),
    0xCE: (2, 2, 2, 2), 0xCF: (2, 0, 2, 2), 0xD0: (2, 0, 2, 2),
    0xD1: (0, 2, 2, 2), 0xD2: (0, 2, 2, 2), 0xD3: (1, 0, 0, 2),
    0xD4: (1, 0, 0, 2), 0xD5: (2, 0, 0, 1), 0xD6: (0, 2, 0, 1),
    0xD7: (2, 2, 2, 2), 0xD8: (2, 2, 2, 2), 0xD9: (1, 0, 1, 0),
    0xDA: (0, 1, 0, 1),
}

SHADES = {0xB0: 0, 0xB1: 1, 0xB2: 2}
BLOCKS = {0xDB: "full", 0xDC: "bottom", 0xDD: "left", 0xDE: "right", 0xDF: "top"}


def _arms_pixels(arms: tuple[int, int, int, int]) -> set[tuple[int, int]]:
    up, down, left, right = arms
    pixels: set[tuple[int, int]] = set()
    if up:
        for x in VX[up]:
            for y in range(0, 8):
                pixels.add((x, y))
    if down:
        for x in VX[down]:
            for y in range(7, GLYPH_H):
                pixels.add((x, y))
    if left:
        for y in HY[left]:
            for x in range(0, 4):
                pixels.add((x, y))
    if right:
        for y in HY[right]:
            for x in range(3, GLYPH_W):
                pixels.add((x, y))
    return pixels


def _shade_pixels(level: int) -> set[tuple[int, int]]:
    if level == 0:
        return {(x, y) for y in range(GLYPH_H) for x in range(GLYPH_W)
                if x % 2 == 0 and y % 2 == 0}
    if level == 1:
        return {(x, y) for y in range(GLYPH_H) for x in range(GLYPH_W)
                if (x + y) % 2 == 0}
    return {(x, y) for y in range(GLYPH_H) for x in range(GLYPH_W)
            if not (x % 2 == 0 and y % 2 == 0)}


def _block_pixels(kind: str) -> set[tuple[int, int]]:
    if kind == "full":
        return {(x, y) for y in range(GLYPH_H) for x in range(GLYPH_W)}
    if kind == "bottom":
        return {(x, y) for y in range(GLYPH_H // 2, GLYPH_H) for x in range(GLYPH_W)}
    if kind == "top":
        return {(x, y) for y in range(GLYPH_H // 2) for x in range(GLYPH_W)}
    if kind == "left":
        return {(x, y) for y in range(GLYPH_H) for x in range(GLYPH_W // 2)}
    return {(x, y) for y in range(GLYPH_H) for x in range(GLYPH_W // 2, GLYPH_W)}


def procedural_glyph(byte: int) -> bytes | None:
    if byte in ARMS:
        pixels = _arms_pixels(ARMS[byte])
    elif byte in SHADES:
        pixels = _shade_pixels(SHADES[byte])
    elif byte in BLOCKS:
        pixels = _block_pixels(BLOCKS[byte])
    else:
        return None
    rows = []
    for y in range(GLYPH_H):
        value = 0
        for x in range(GLYPH_W):
            if (x, y) in pixels:
                value |= 1 << (7 - x)
        rows.append(value)
    return bytes(rows)



def render_glyph(font: ImageFont.FreeTypeFont, ch: str, byte: int) -> bytes:
    override = procedural_glyph(byte)
    if override is not None:
        return override
    img = Image.new("L", (GLYPH_W, GLYPH_H), 0)
    if ch != " ":
        draw = ImageDraw.Draw(img)
        draw.text((0, BASELINE), ch, font=font, fill=255, anchor="ls")
    rows = []
    for y in range(GLYPH_H):
        value = 0
        for x in range(GLYPH_W):
            if img.getpixel((x, y)) > THRESHOLD:
                value |= 1 << (7 - x)
        rows.append(value)
    return bytes(rows)


def glyph_art(data: bytes, index: int) -> str:
    rows = data[index * GLYPH_H : (index + 1) * GLYPH_H]
    lines = []
    for row in rows:
        lines.append("".join("#" if row & (1 << (7 - x)) else "." for x in range(GLYPH_W)))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--art", help="stampa il glifo del carattere indicato")
    args = parser.parse_args(argv)

    font_path = find_font()
    font = ImageFont.truetype(font_path, FONT_SIZE)
    chars = cp437_chars()

    if args.art:
        if len(args.art) == 1:
            (index,) = [i for i, ch in enumerate(chars) if ch == args.art] or [ord(args.art)]
        else:
            index = int(args.art, 0)
        if index < 0 or index > 255:
            raise SystemExit("indice fuori intervallo")
        data = b"".join(render_glyph(font, ch, i) for i, ch in enumerate(chars))
        print(f"glifo 0x{index:02X} {chars[index]!r}\n{glyph_art(data, index)}")
        return 0

    data = b"".join(render_glyph(font, ch, i) for i, ch in enumerate(chars))
    assert len(data) == 256 * GLYPH_H, len(data)
    OUT_BIN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BIN.write_bytes(data)

    preview = Image.new("RGB", (16 * GLYPH_W, 16 * (GLYPH_H + 2)), (0, 0, 0))
    for byte in range(256):
        cx = (byte % 16) * GLYPH_W
        cy = (byte // 16) * (GLYPH_H + 2)
        for y in range(GLYPH_H):
            row = data[byte * GLYPH_H + y]
            for x in range(GLYPH_W):
                if row & (1 << (7 - x)):
                    preview.putpixel((cx + x, cy + y), (230, 230, 230))
    OUT_PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    preview.save(OUT_PREVIEW)
    print(f"scritti {OUT_BIN.relative_to(ROOT)} ({len(data)} byte) e {OUT_PREVIEW.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
