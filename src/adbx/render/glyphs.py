"""Caratteri grafici disegnati geometricamente nella cella.

I font monospaziati non garantiscono che le linee di cornice tocchino i bordi
della cella: DejaVu Sans Mono, per esempio, lascia un pixel di vuoto e le
verticali risultano tratteggiate. Questi simboli vengono quindi disegnati con
rettangoli, alla risoluzione del dispositivo, e restano continui a qualunque
corpo del font.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter

# (su, giu, sinistra, destra): 0 assente, 1 singola, 2 doppia
ARMS: dict[str, tuple[int, int, int, int]] = {
    "─": (0, 0, 1, 1),
    "│": (1, 1, 0, 0),
    "┌": (0, 1, 0, 1),
    "┐": (0, 1, 1, 0),
    "└": (1, 0, 0, 1),
    "┘": (1, 0, 1, 0),
    "├": (1, 1, 0, 1),
    "┤": (1, 1, 1, 0),
    "┬": (0, 1, 1, 1),
    "┴": (1, 0, 1, 1),
    "┼": (1, 1, 1, 1),
    "═": (0, 0, 2, 2),
    "║": (2, 2, 0, 0),
    "╔": (0, 2, 0, 2),
    "╗": (0, 2, 2, 0),
    "╚": (2, 0, 0, 2),
    "╝": (2, 0, 2, 0),
    "╠": (2, 2, 0, 2),
    "╣": (2, 2, 2, 0),
    "╦": (0, 2, 2, 2),
    "╩": (2, 0, 2, 2),
    "╬": (2, 2, 2, 2),
}

SHADES: dict[str, int] = {"░": 0, "▒": 1, "▓": 2}
SHADE_ALPHA = (64, 128, 192)
BLOCKS: dict[str, str] = {"█": "full", "▄": "bottom", "▀": "top", "▌": "left", "▐": "right"}


def is_geometric(char: str) -> bool:
    return char in ARMS or char in SHADES or char in BLOCKS


@dataclass(frozen=True)
class _Geometry:
    x0: int
    y0: int
    x1: int
    y1: int
    thin: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0


def _geometry(rect: QRectF, dpr: float) -> _Geometry:
    x0 = round(rect.x() * dpr)
    y0 = round(rect.y() * dpr)
    x1 = round((rect.x() + rect.width()) * dpr)
    y1 = round((rect.y() + rect.height()) * dpr)
    thin = max(1, (y1 - y0) // 16)
    return _Geometry(x0, y0, x1, y1, thin)


def _offsets(kind: int, thin: int) -> tuple[int, ...]:
    if kind == 2:
        gap = max(1, thin)
        return (-(thin + gap), thin + gap)
    return (0,)


def _draw_arms(painter: QPainter, arms: tuple[int, int, int, int], g: _Geometry, dpr: float) -> None:
    up, down, left, right = arms
    cx = g.x0 + g.width // 2
    cy = g.y0 + g.height // 2
    v_offsets = _offsets(max(up, down), g.thin)
    h_offsets = _offsets(max(left, right), g.thin)
    # Le linee si sovrappongono al centro, così gli angoli restano chiusi.
    reach_v = max((abs(offset) for offset in v_offsets), default=0) + g.thin
    reach_h = max((abs(offset) for offset in h_offsets), default=0) + g.thin

    if up:
        for offset in v_offsets:
            x = cx + offset - g.thin // 2
            _fill(painter, dpr, x, g.y0, g.thin, cy - g.y0 + reach_v)
    if down:
        for offset in v_offsets:
            x = cx + offset - g.thin // 2
            _fill(painter, dpr, x, cy - reach_v, g.thin, g.y1 - (cy - reach_v))
    if left:
        for offset in h_offsets:
            y = cy + offset - g.thin // 2
            _fill(painter, dpr, g.x0, y, cx - g.x0 + reach_h, g.thin)
    if right:
        for offset in h_offsets:
            y = cy + offset - g.thin // 2
            _fill(painter, dpr, cx - reach_h, y, g.x1 - (cx - reach_h), g.thin)


def _fill(painter: QPainter, dpr: float, x: float, y: float, w: float, h: float) -> None:
    if w <= 0 or h <= 0:
        return
    painter.fillRect(QRectF(x / dpr, y / dpr, w / dpr, h / dpr), painter.brush())


def _draw_shade(painter: QPainter, level: int, g: _Geometry, color: QColor, dpr: float) -> None:
    """Retinatura resa come velo traslucido: resta nitida a ogni corpo."""
    tint = QColor(color)
    tint.setAlpha(SHADE_ALPHA[level])
    rect = QRectF(g.x0 / dpr, g.y0 / dpr, g.width / dpr, g.height / dpr)
    painter.fillRect(rect, tint)


def _draw_block(painter: QPainter, kind: str, g: _Geometry, dpr: float) -> None:
    w, h = g.width, g.height
    if kind == "full":
        _fill(painter, dpr, g.x0, g.y0, w, h)
        return
    half_h, half_w = h // 2, w // 2
    if kind == "top":
        _fill(painter, dpr, g.x0, g.y0, w, half_h)
    elif kind == "bottom":
        _fill(painter, dpr, g.x0, g.y0 + half_h, w, h - half_h)
    elif kind == "left":
        _fill(painter, dpr, g.x0, g.y0, half_w, h)
    elif kind == "right":
        _fill(painter, dpr, g.x0 + half_w, g.y0, w - half_w, h)


def draw_geometric(painter: QPainter, char: str, rect: QRectF, color: QColor, dpr: float) -> None:
    """Disegna `char` nella cella `rect` (coordinate logiche)."""
    g = _geometry(rect, dpr)
    if g.width <= 0 or g.height <= 0:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    if char in ARMS:
        _draw_arms(painter, ARMS[char], g, dpr)
    elif char in BLOCKS:
        _draw_block(painter, BLOCKS[char], g, dpr)
    elif char in SHADES:
        _draw_shade(painter, SHADES[char], g, color, dpr)
    painter.restore()


__all__ = ["ARMS", "BLOCKS", "SHADES", "draw_geometric", "is_geometric"]
