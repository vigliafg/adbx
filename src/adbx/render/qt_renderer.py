"""Renderer Qt del motore a celle: font TrueType, atlante, simboli geometrici."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFontMetricsF, QImage, QPainter

from ..cell.attrs import DOS_PALETTE, bright, resolve_color
from ..cell.buffer import CellBuffer
from ..cell.cp437 import to_byte
from .fonts import make_font, monospace_family
from .glyphs import draw_geometric, is_geometric

MAX_PIXEL_SIZE = 72
MIN_PIXEL_SIZE = 7


class CellRenderer:
    """Disegna un `CellBuffer` su un `QPainter`; non conosce form o report."""

    def __init__(self, *, pixel_size: int = 16, family: str | None = None,
                 palette: tuple[tuple[int, int, int], ...] = DOS_PALETTE) -> None:
        self.family = family or monospace_family()
        self.palette = palette
        self.dpr = 1.0
        self.base_pixel_size = MIN_PIXEL_SIZE
        self.best_pixel_size = MIN_PIXEL_SIZE
        self.zoom_limited = False
        self._pixel_size_dev = 0
        self._atlases: dict[tuple[int, bool], QImage] = {}
        self._prepare(max(MIN_PIXEL_SIZE, int(pixel_size)))
        self.cell_w = float(self.advance)
        self.cell_h = float(self.line_height)

    # -- metriche --------------------------------------------------------
    def _prepare(self, pixel_size_dev: int) -> None:
        """Costruisce font e metriche per un corpo in pixel di dispositivo."""
        pixel_size_dev = max(MIN_PIXEL_SIZE, int(pixel_size_dev))
        if pixel_size_dev == self._pixel_size_dev:
            return
        self._pixel_size_dev = pixel_size_dev
        self._atlases.clear()
        self._font = make_font(pixel_size_dev, family=self.family)
        self._bold_font = make_font(pixel_size_dev, bold=True, family=self.family)
        metrics = QFontMetricsF(self._font)
        self.advance = max(1, round(metrics.horizontalAdvance("M")))
        self.ascent = max(1, round(metrics.ascent()))
        self.descent = max(0, round(metrics.descent()))
        self.line_height = max(1, self.ascent + self.descent)

    @property
    def pixel_size(self) -> int:
        return self._pixel_size_dev

    def _fits(self, width: float, height: float, cols: int, rows: int) -> bool:
        return (self.advance * cols <= width * self.dpr
                and self.line_height * rows <= height * self.dpr)

    def fit(self, width: float, height: float, cols: int, rows: int,
            dpr: float = 1.0, *, ceiling: float | None = None,
            zoom: float = 1.0) -> None:
        """Sceglie il corpo che fa stare la griglia nella finestra.

        Le celle derivano dalle metriche del font, non da un fattore di scala:
        il testo non viene mai stirato.

        `ceiling` limita il corpo naturale (in pixel di dispositivo) per
        lasciare margini su schermi molto grandi; `zoom` è un fattore
        applicato a quel corpo, ma non supera mai il massimo che entra nella
        finestra: la griglia non viene mai tagliata.
        """
        self.dpr = max(0.5, float(dpr))
        width = max(1.0, width)
        height = max(1.0, height)
        best = MIN_PIXEL_SIZE
        for candidate in range(MIN_PIXEL_SIZE, MAX_PIXEL_SIZE + 1):
            self._prepare(candidate)
            if self._fits(width, height, cols, rows):
                best = candidate
            elif candidate > MIN_PIXEL_SIZE:
                break
        base = best
        if ceiling is not None:
            base = max(MIN_PIXEL_SIZE, min(best, round(ceiling)))
        requested = round(base * max(0.1, float(zoom)))
        target = max(MIN_PIXEL_SIZE, min(best, requested))
        self.best_pixel_size = best
        self.base_pixel_size = base
        self.zoom_limited = requested > best
        self._prepare(target)
        self.cell_w = self.advance / self.dpr
        self.cell_h = self.line_height / self.dpr

    def measure(self, pixel_size: int) -> tuple[float, float]:
        """Cella (larghezza, altezza) per un corpo, senza cambiare lo stato."""
        saved = self._pixel_size_dev
        self._prepare(pixel_size)
        result = (self.advance / self.dpr, self.line_height / self.dpr)
        self._prepare(saved)
        return result

    def use_natural_size(self, pixel_size: int, dpr: float = 1.0) -> None:
        """Cella = metriche del font: usata per screenshot canonici."""
        self.dpr = max(0.5, float(dpr))
        self._prepare(pixel_size)
        self.cell_w = self.advance / self.dpr
        self.cell_h = self.line_height / self.dpr

    def grid_size(self, cols: int, rows: int) -> tuple[float, float]:
        return self.cell_w * cols, self.cell_h * rows

    def size(self, buffer: CellBuffer) -> tuple[int, int]:
        return round(self.cell_w * buffer.width), round(self.cell_h * buffer.height)

    # -- risorse ---------------------------------------------------------
    def atlas(self, color: int, bold: bool = False) -> QImage:
        key = (resolve_color(color), bold)
        cached = self._atlases.get(key)
        if cached is not None:
            return cached
        image = QImage(self.advance * 256, self.line_height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setFont(self._bold_font if bold else self._font)
            painter.setPen(QColor(*self.palette[key[0]]))
            for byte, char in enumerate(_ATLAS_CHARS):
                if char == " " or is_geometric(char):
                    continue
                painter.drawText(QPointF(byte * self.advance, self.ascent), char)
        finally:
            painter.end()
        self._atlases[key] = image
        return image

    # -- disegno ---------------------------------------------------------
    def paint(self, painter: QPainter, buffer: CellBuffer, *,
              blink_on: bool = True, row_offset: int = 0, col_offset: int = 0) -> None:
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        dpr = self.dpr
        cell_w, cell_h = self.cell_w, self.cell_h
        advance, line = self.advance, self.line_height
        glyph_w = advance / dpr
        for row in range(buffer.height):
            top = (row + row_offset) * cell_h
            for col in range(buffer.width):
                cell = buffer.get(row, col)
                left = (col + col_offset) * cell_w
                bg = resolve_color(cell.bg)
                painter.fillRect(QRectF(left, top, cell_w, cell_h),
                                 QColor(*self.palette[bg]))
                if cell.ch == " " or (cell.blink and not blink_on):
                    continue
                fg = bright(cell.fg) if cell.bold else resolve_color(cell.fg)
                if is_geometric(cell.ch):
                    draw_geometric(painter, cell.ch, QRectF(left, top, cell_w, cell_h),
                                   QColor(*self.palette[fg]), dpr)
                    continue
                image = self.atlas(fg, cell.bold)
                x = round((left + (cell_w - glyph_w) / 2) * dpr)
                source = QRectF(to_byte(cell.ch) * advance, 0, advance, line)
                painter.drawImage(
                    QRectF(x / dpr, top, glyph_w, cell_h), image, source
                )
                if cell.underline:
                    thickness = max(1, line // 14)
                    underline_y = (self.ascent + max(1, thickness)) / dpr
                    painter.fillRect(
                        QRectF(x / dpr, top + underline_y, glyph_w, thickness / dpr),
                        QColor(*self.palette[fg]),
                    )

    def to_image(self, buffer: CellBuffer, *, blink_on: bool = True) -> QImage:
        width = round(self.cell_w * buffer.width * self.dpr)
        height = round(self.cell_h * buffer.height * self.dpr)
        image = QImage(max(1, width), max(1, height), QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.black)
        painter = QPainter(image)
        try:
            painter.scale(self.dpr, self.dpr)
            self.paint(painter, buffer, blink_on=blink_on)
        finally:
            painter.end()
        return image


def _atlas_chars() -> tuple[str, ...]:
    from ..cell.cp437 import CHARS

    return CHARS


_ATLAS_CHARS = _atlas_chars()


def best_pixel_size(width: float, height: float, cols: int, rows: int,
                    family: str | None = None) -> int:
    """Corpo massimo che fa entrare la griglia, senza costruire il renderer."""
    probe = CellRenderer(pixel_size=MIN_PIXEL_SIZE, family=family)
    probe.fit(width, height, cols, rows, dpr=1.0)
    return probe.pixel_size


__all__ = ["CellRenderer", "MAX_PIXEL_SIZE", "MIN_PIXEL_SIZE", "best_pixel_size"]
