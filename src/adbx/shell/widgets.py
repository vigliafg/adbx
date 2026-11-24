"""Elementi comuni del guscio: finestre, ombre, righe di chrome, prompt."""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field

from ..cell.buffer import HELP_ROW, MENU_ROW, STATUS_ROW, Cell, CellBuffer
from ..cell.cp437 import SHADE_LIGHT
from .theme import Theme


@dataclass(frozen=True)
class Region:
    """Zona cliccabile, in coordinate schermo."""

    row: int
    col: int
    height: int
    width: int
    action: str

    def contains(self, row: int, col: int) -> bool:
        return (self.row <= row < self.row + self.height
                and self.col <= col < self.col + self.width)


@dataclass
class View:
    buffer: CellBuffer
    regions: list[Region] = field(default_factory=list)

    def region_at(self, row: int, col: int) -> Region | None:
        for region in reversed(self.regions):
            if region.contains(row, col):
                return region
        return None


def blit(destination: CellBuffer, source: CellBuffer, row: int, col: int) -> None:
    for r in range(source.height):
        target_row = row + r
        if not 0 <= target_row < destination.height:
            continue
        for c in range(source.width):
            target_col = col + c
            if not 0 <= target_col < destination.width:
                continue
            destination.put(target_row, target_col, source.get(r, c))


def shadow(destination: CellBuffer, row: int, col: int, height: int, width: int) -> None:
    """Scurisce le celle a destra e sotto la finestra, senza coprirle."""
    for c in range(col + 1, col + width + 1):
        cell = destination.get(row + height, c)
        destination.put(row + height, c,
                        Cell(SHADE_LIGHT, fg=0, bg=cell.bg))
    for r in range(row + 1, row + height + 1):
        cell = destination.get(r, col + width)
        destination.put(r, col + width, Cell(SHADE_LIGHT, fg=0, bg=cell.bg))


def window(width: int, height: int, title: str, theme: Theme) -> CellBuffer:
    """Finestra con barra del titolo scura e corpo chiaro bordato."""
    width = max(8, width)
    height = max(3, height)
    buffer = CellBuffer(width, height,
                        Cell(fg=theme.window_fg, bg=theme.window_bg))
    buffer.fill_rect(0, 0, height, width, " ",
                     fg=theme.window_fg, bg=theme.window_bg)
    buffer.fill_rect(0, 0, 1, width, " ", fg=theme.title_fg, bg=theme.title_bg)
    text = f" {title} "
    buffer.write(0, max(1, (width - len(text)) // 2), text,
                 fg=theme.title_fg, bg=theme.title_bg, bold=True)
    buffer.box(1, 0, height - 1, width, fg=theme.border, bg=theme.window_bg)
    return buffer


def title_bar(buffer: CellBuffer, title: str, theme: Theme, *, spaced: bool = True) -> None:
    """Barra del titolo a tutta larghezza, come nel Database Directory."""
    buffer.fill_rect(0, 0, 1, buffer.width, " ",
                     fg=theme.title_fg, bg=theme.title_bg)
    text = " ".join(title.upper()) if spaced else title
    if len(text) > buffer.width - 2:
        text = title
    buffer.write(0, max(1, (buffer.width - len(text)) // 2), text,
                 fg=theme.title_fg, bg=theme.title_bg, bold=True)


def text_lines(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width) or [""]


def draw_menu_line(buffer: CellBuffer, theme: Theme, items: list[tuple[str, str]],
                   *, row: int = MENU_ROW) -> list[Region]:
    """Disegna `F1 Help  F2 ...` e ritorna le zone cliccabili."""
    buffer.fill_rect(row, 0, 1, buffer.width, " ", fg=theme.menu_fg, bg=theme.menu_bg)
    col = 1
    regions: list[Region] = []
    for key, label in items:
        start = col
        col = buffer.write(row, col, key, fg=theme.accent, bg=theme.menu_bg, bold=True)
        col = buffer.write(row, col, label, fg=theme.menu_fg, bg=theme.menu_bg)
        regions.append(Region(row, start, 1, col - start, f"key:{key}"))
        col += 3
    return regions


def draw_help_line(buffer: CellBuffer, theme: Theme, text: str) -> None:
    buffer.fill_rect(HELP_ROW, 0, 1, buffer.width, " ",
                     fg=theme.help_fg, bg=theme.help_bg)
    if text:
        buffer.write(HELP_ROW, 1, text, fg=theme.help_fg, bg=theme.help_bg)


def draw_status_line(buffer: CellBuffer, theme: Theme, text: str = "") -> None:
    buffer.fill_rect(STATUS_ROW, 0, 1, buffer.width, " ",
                     fg=theme.status_fg, bg=theme.status_bg)
    if text:
        buffer.write(STATUS_ROW, 1, text, fg=theme.status_fg, bg=theme.status_bg, bold=True)


def prompt_line(buffer: CellBuffer, theme: Theme, label: str, text: str,
                cursor: int, *, row: int = HELP_ROW, col: int = 1) -> tuple[Region, int]:
    """Riga di immissione con cursore: ritorna la zona cliccabile e la colonna."""
    text_col = col + len(label) + 3
    available = max(8, buffer.width - text_col - 2)
    cursor = max(0, min(cursor, len(text)))
    start = 0
    if cursor >= available:
        start = cursor - available + 1
    visible = text[start:start + available]
    local_cursor = cursor - start

    buffer.fill_rect(row, 0, 1, buffer.width, " ", fg=theme.help_fg, bg=theme.help_bg)
    end = buffer.write(row, col, label, fg=theme.label, bg=theme.help_bg, bold=True)
    buffer.write(row, end, " :", fg=theme.label, bg=theme.help_bg)
    buffer.write(row, text_col, visible, fg=theme.text, bg=theme.help_bg, underline=True)
    cursor_col = text_col + local_cursor
    buffer.write(row, cursor_col, "_", fg=theme.accent, bg=theme.help_bg,
                 blink=True, bold=True, underline=False)
    region = Region(row, text_col, 1, available, "input")
    return region, cursor_col


def clip_text(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(0, width)]


def visible_rows(top: int) -> int:
    """Righe di contenuto disponibili da `top` fino alla status line."""
    return max(0, STATUS_ROW - top)


def elide_left(text: str, width: int) -> str:
    """Taglia l'inizio di un testo lungo, conservando la coda (nomi file)."""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return "…" + text[-(width - 1):]


__all__ = [
    "Region",
    "View",
    "blit",
    "clip_text",
    "draw_help_line",
    "draw_menu_line",
    "draw_status_line",
    "elide_left",
    "visible_rows",
    "prompt_line",
    "shadow",
    "text_lines",
    "title_bar",
    "window",
]
