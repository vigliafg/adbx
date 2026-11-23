"""Font bitmap CP437 8x16 incorporato nel pacchetto."""

from __future__ import annotations

from importlib import resources

GLYPH_W = 8
GLYPH_H = 16
GLYPH_COUNT = 256
FONT_BYTES = GLYPH_COUNT * GLYPH_H


class BitmapFont:
    """Tabella di 256 glifi; ogni glifo e' 16 byte, MSB a sinistra."""

    __slots__ = ("data",)

    def __init__(self, data: bytes) -> None:
        if len(data) != FONT_BYTES:
            raise ValueError(f"tabella font di {len(data)} byte, attesi {FONT_BYTES}")
        self.data = data

    @classmethod
    def from_bytes(cls, data: bytes) -> "BitmapFont":
        return cls(data)

    @classmethod
    def load_default(cls) -> "BitmapFont":
        resource = resources.files("adbx").joinpath("data/cp437_8x16.bin")
        return cls(resource.read_bytes())

    def rows(self, byte: int) -> bytes:
        start = (byte % GLYPH_COUNT) * GLYPH_H
        return self.data[start:start + GLYPH_H]

    def pixel(self, byte: int, x: int, y: int) -> bool:
        if not (0 <= x < GLYPH_W and 0 <= y < GLYPH_H):
            return False
        return bool(self.rows(byte)[y] & (1 << (GLYPH_W - 1 - x)))
