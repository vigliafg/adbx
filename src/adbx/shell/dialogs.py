"""Dialoghi condivisi fra indici, range e search/sort: elenchi a comparsa."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..cell.buffer import SCREEN_WIDTH, STATUS_ROW
from . import screens
from .theme import NEWPORT, Theme
from .widgets import Region, View, clip_text, window


@dataclass
class Picker:
    """Elenco a comparsa con selezione e scopo."""

    title: str
    items: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    selected: int = 0
    purpose: str = ""
    footer: str = ""
    markers: list[str] = field(default_factory=list)
    width: int = 64

    def __post_init__(self) -> None:
        if not self.values:
            self.values = list(self.items)
        if not self.markers:
            self.markers = ["" for _ in self.items]

    def move(self, delta: int) -> None:
        if self.items:
            self.selected = max(0, min(len(self.items) - 1,
                                       self.selected + delta))

    def value(self) -> str:
        if 0 <= self.selected < len(self.values):
            return self.values[self.selected]
        return ""


def picker_view(base: View, picker: Picker,
                theme: Theme = NEWPORT) -> View:
    """Finestra centrale sopra la schermata base."""
    width = max(24, min(picker.width, SCREEN_WIDTH - 4))
    rows = max(1, len(picker.items))
    height = min(STATUS_ROW - 2, rows + 5)
    panel = window(width, height, picker.title, theme)
    visible = height - 4
    top = max(0, min(picker.selected - visible + 1,
                     max(0, len(picker.items) - visible)))
    regions: list[Region] = []
    row = max(1, (STATUS_ROW - height) // 2)
    col = max(1, (SCREEN_WIDTH - width) // 2)
    for offset in range(visible):
        index = top + offset
        if index >= len(picker.items):
            break
        screen_row = 2 + offset
        selected = index == picker.selected
        fg = theme.selected_fg if selected else theme.window_fg
        bg = theme.selected_bg if selected else theme.window_bg
        if selected:
            panel.fill_rect(screen_row, 1, 1, width - 2, " ", fg=fg, bg=bg)
        marker = picker.markers[index] if index < len(picker.markers) else ""
        text = f"{marker}{picker.items[index]}"
        panel.write(screen_row, 2, clip_text(text, width - 4), fg=fg, bg=bg)
        regions.append(Region(row + screen_row, col + 1, 1, width - 2,
                              f"pick:{index}"))
    footer = picker.footer or "UP/DOWN select   ENTER confirm   ESC cancel"
    panel.write(height - 2, 2, clip_text(footer, width - 4),
                fg=theme.muted, bg=theme.window_bg)
    return screens.overlay_view(base, panel, row, col, regions, theme)


def field_markers(selected: list[str], names: list[str],
                  marker: str = "\u25b8 ") -> list[str]:
    """Marcatori per la Field Selection del Locate."""
    chosen = {name.upper() for name in selected}
    return [marker if name.upper() in chosen else "  " for name in names]


__all__ = ["Picker", "field_markers", "picker_view"]
