"""Renderer: disegna un `CellBuffer` con la tabella bitmap CP437."""

from __future__ import annotations

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QImage, QPainter

from ..cell.attrs import DOS_PALETTE, bright, resolve_color
from ..cell.buffer import CellBuffer
from ..cell.cp437 import to_byte
from ..cell.font import GLYPH_H, GLYPH_W, BitmapFont


class CellRenderer:
    """Disegna celle su un `QPainter`; nessuna conoscenza di form o report."""

    def __init__(self, font: BitmapFont | None = None,
                 palette: tuple[tuple[int, int, int], ...] = DOS_PALETTE,
                 scale: int = 2) -> None:
        self.font = font or BitmapFont.load_default()
        self.palette = palette
        self.scale = max(1, int(scale))
        self.cell_w = GLYPH_W * self.scale
        self.cell_h = GLYPH_H * self.scale
        self._atlases: dict[int, QImage] = {}

    # -- risorse ---------------------------------------------------------
    def atlas(self, color: int) -> QImage:
        color = resolve_color(color)
        cached = self._atlases.get(color)
        if cached is not None:
            return cached
        image = QImage(GLYPH_W * 256, GLYPH_H, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        rgb = QColor(*self.palette[color])
        for byte in range(256):
            rows = self.font.rows(byte)
            for y, bits in enumerate(rows):
                if not bits:
                    continue
                base = byte * GLYPH_W
                for x in range(GLYPH_W):
                    if bits & (1 << (GLYPH_W - 1 - x)):
                        image.setPixelColor(base + x, y, rgb)
        self._atlases[color] = image
        return image

    def size(self, buffer: CellBuffer) -> tuple[int, int]:
        return buffer.width * self.cell_w, buffer.height * self.cell_h

    # -- disegno ---------------------------------------------------------
    def paint(self, painter: QPainter, buffer: CellBuffer, *,
              blink_on: bool = True, row_offset: int = 0, col_offset: int = 0) -> None:
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        cell_w, cell_h = self.cell_w, self.cell_h
        glyph_src = QRect(0, 0, GLYPH_W, GLYPH_H)
        for row in range(buffer.height):
            y = (row + row_offset) * cell_h
            for col in range(buffer.width):
                cell = buffer.get(row, col)
                x = (col + col_offset) * cell_w
                painter.fillRect(x, y, cell_w, cell_h,
                                 QColor(*self.palette[resolve_color(cell.bg)]))
                if cell.ch == " " or (cell.blink and not blink_on):
                    continue
                fg = bright(cell.fg) if cell.bold else resolve_color(cell.fg)
                glyph_src.moveLeft(to_byte(cell.ch) * GLYPH_W)
                painter.drawImage(
                    QRect(x, y, cell_w, cell_h), self.atlas(fg), glyph_src
                )

    def to_image(self, buffer: CellBuffer, *, blink_on: bool = True) -> QImage:
        width, height = self.size(buffer)
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.black)
        painter = QPainter(image)
        try:
            self.paint(painter, buffer, blink_on=blink_on)
        finally:
            painter.end()
        return image
