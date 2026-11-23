"""Schermata dimostrativa della shell (provvisoria, fino a O1).

Serve a verificare il motore a celle: chrome a tre righe, menu a due colonne,
popup con ombra. In O1 diventera' il vero main menu.
"""

from __future__ import annotations

from ..cell.attrs import Color
from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, Cell, CellBuffer
from ..cell.cp437 import SHADE_DARK
from .scene import Scene, centered, popup

WHITE = int(Color.WHITE)
BLACK = int(Color.BLACK)
BLUE = int(Color.BLUE)
CYAN = int(Color.CYAN)
GRAY = int(Color.GRAY)
YELLOW = int(Color.YELLOW)
RED = int(Color.RED)

MENU = [
    "View/enter records",
    "Print",
    "Search/sort lists",
    "Indexes/ranges",
    "Global update/delete",
    "Choose database/set",
    "Database/set design",
    "Layouts",
    "Applications",
    "Utilities",
    "Other",
    "Quit",
]

HELP = {
    "View/enter records": "Display records from the current database or set",
    "Print": "Print reports, mail labels, forms, browse tables, and form letters",
    "Search/sort lists": "Search and/or sort the current database or set",
    "Indexes/ranges": "Create, select, and erase indexes and ranges",
    "Global update/delete": "Update a field, change case, delete records",
    "Choose database/set": "Open, close, or switch databases and sets",
    "Database/set design": "Create, modify, and erase databases and sets",
    "Layouts": "Create and edit forms, browse tables, reports, labels, letters",
    "Applications": "Run or edit custom menu applications",
    "Utilities": "Copy, append, pack, summarize, or cross-tabulate",
    "Other": "Information, configuration, and default settings",
    "Quit": "Leave adbx",
}


def _hot_key(label: str) -> int:
    """Indice della lettera maiuscola che funziona da scorciatoia."""
    for index, char in enumerate(label):
        if char.isupper():
            return index
    return 0


def _write_label(buffer: CellBuffer, row: int, col: int, label: str, *,
                 selected: bool = False) -> None:
    fg, bg = (BLACK, CYAN) if selected else (WHITE, BLUE)
    buffer.write(row, col, label, fg=fg, bg=bg)
    hot = _hot_key(label)
    buffer.write(row, col + hot, label[hot], fg=fg, bg=bg, bold=not selected)


def build_demo_scene(*, selected: int = 0, show_popup: bool = True) -> Scene:
    scene = Scene(SCREEN_WIDTH, SCREEN_HEIGHT, Cell(fg=WHITE, bg=BLUE))
    base = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT, Cell(fg=WHITE, bg=BLUE))
    base.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ", fg=WHITE, bg=BLUE)

    # Status box (righe 1-2)
    base.fill_rect(0, 0, 1, SCREEN_WIDTH, " ", fg=BLACK, bg=GRAY)
    base.write(0, 1, "Current database : C:\\ADBX\\DATA\\AVMOVIES", fg=BLACK, bg=GRAY)
    base.write(0, 50, "Records in database   44", fg=BLACK, bg=GRAY)
    base.fill_rect(1, 0, 1, SCREEN_WIDTH, " ", fg=BLACK, bg=GRAY)
    base.write(1, 1, "Primary index : by Record Number", fg=BLACK, bg=GRAY)
    base.write(1, 50, "Set : (none)", fg=BLACK, bg=GRAY)

    # Menu a due colonne
    columns = ((4, 4), (4, 36))
    for index, label in enumerate(MENU):
        row0, col0 = columns[index % 2]
        row = row0 + index // 2
        _write_label(base, row, col0, label, selected=index == selected)

    # Riga di stato (23), help (24), menu (25)
    base.fill_rect(22, 0, 1, SCREEN_WIDTH, " ", fg=BLACK, bg=CYAN)
    base.write(22, 1, "View", fg=BLACK, bg=CYAN)
    base.write(22, 20, "Record : 1/44", fg=BLACK, bg=CYAN)
    base.write(22, 60, "adbx 0.1.0", fg=BLACK, bg=CYAN)

    base.fill_rect(23, 0, 1, SCREEN_WIDTH, " ", fg=YELLOW, bg=BLACK)
    base.write(23, 1, HELP[MENU[selected]], fg=YELLOW, bg=BLACK)

    base.fill_rect(24, 0, 1, SCREEN_WIDTH, " ", fg=BLACK, bg=GRAY)
    base.write(24, 1, "F1 Help   F10 Continue   ALT-F10 MainMenu   ALT-F3 Scripts",
               fg=BLACK, bg=GRAY)

    scene.add("base", base)

    if show_popup:
        box = popup(38, 9, title="Open Databases", shadow=True)
        box.write(2, 2, "Name              Type   Modified", fg=GRAY, bg=BLUE)
        box.write(3, 2, "AVMOVIES          DBF    11/23/26", fg=WHITE, bg=BLUE)
        box.write(4, 2, "AVPATRON          DBF    11/23/26", fg=WHITE, bg=BLUE)
        box.write(5, 2, "AVSALES           DBF    11/23/26", fg=WHITE, bg=BLUE)
        box.write(6, 1, " " * 34, fg=BLACK, bg=CYAN)
        box.write(6, 2, "AVMOVIES", fg=BLACK, bg=CYAN)
        box.write(7, 1, "Enter name or select with arrows", fg=GRAY, bg=BLUE)
        row, col = centered(SCREEN_WIDTH, SCREEN_HEIGHT, 38, 9, top=6)
        scene.add("popup", box, row, col)

    return scene


def demo_buffer(*, selected: int = 0, show_popup: bool = True) -> CellBuffer:
    return build_demo_scene(selected=selected, show_popup=show_popup).composite()


__all__ = ["MENU", "build_demo_scene", "demo_buffer", "SHADE_DARK"]
