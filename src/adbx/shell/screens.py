"""Schermate del guscio: main menu, directory, struttura, stato, overlay."""

from __future__ import annotations

from pathlib import Path

from ..cell.buffer import (
    HELP_ROW,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    STATUS_ROW,
    Cell,
    CellBuffer,
)
from .help import LinkSpan, link_spans, topic, wrap_topic
from .state import ShellState
from .theme import NEWPORT, Theme
from .widgets import (
    Region,
    View,
    blit,
    clip_text,
    draw_help_line,
    draw_menu_line,
    draw_status_line,
    prompt_line,
    shadow,
    text_lines,
    title_bar,
    window,
)

# Comandi del main menu, nell'ordine in cui li percorrono le frecce.
COMMANDS: tuple[tuple[str, str], ...] = (
    ("View/enter records", "view"),
    ("Print", "print"),
    ("Search/sort lists", "search"),
    ("Indexes/ranges", "indexes"),
    ("Global update/delete", "global"),
    ("Choose database/set", "choose"),
    ("Database/set design", "design"),
    ("Layouts", "layouts"),
    ("Applications", "applications"),
    ("Utilities", "utilities"),
    ("Other", "other"),
    ("Quit", "quit"),
)

COMMAND_HELP: dict[str, str] = {
    "view": "View, change, enter or delete records",
    "print": "Print reports, labels, forms and letters",
    "search": "Search and/or sort the current database or set",
    "indexes": "Create, select, and erase indexes and ranges",
    "global": "Update a field, change case, delete records",
    "choose": "Open, close, or switch databases and sets",
    "design": "Create, modify, and erase databases and sets",
    "layouts": "Create and edit forms, browse tables, reports, labels, letters",
    "applications": "Run or edit custom menu applications",
    "utilities": "Copy, append, pack, summarize, or cross-tabulate",
    "other": "Information, configuration, and default settings",
    "quit": "Leave Alpha Four and return to DOS",
}

MAIN_MENU_HELP = "Select a command with the arrow keys or its hot key"
MAIN_MENU_KEYS = [
    ("F1", "Help"),
    ("Alt-F1", "Quick record"),
    ("Alt-F2", "Quick play"),
    ("Alt-F3", "Script menu"),
    ("Alt-F9", "DOS access"),
]

DIRECTORY_TITLE = "Database Directory"
DIRECTORY_KEYS = [("F3", "Import"), ("F4", "History on"), ("F6", "Refresh"),
                  ("F5", "Create Db"), ("F8", "Detail on"), ("F9", "DOS")]

LIST_TOP = 6
LIST_LEFT = 2
NAME_WIDTH = 21
TYPE_COL = 25
DATE_COL = 32
DETAIL_RECORDS_COL = 44
DETAIL_FIELDS_COL = 58


def hot_index(label: str) -> int:
    for index, char in enumerate(label):
        if char.isupper():
            return index
    return 0


def _write_hot(buffer: CellBuffer, row: int, col: int, label: str, *,
               fg: int, bg: int) -> None:
    hot = hot_index(label)
    buffer.write(row, col, label, fg=fg, bg=bg)
    buffer.write(row, col + hot, label[hot], fg=fg, bg=bg, bold=True)


def _status_box(buffer: CellBuffer, state: ShellState, theme: Theme) -> None:
    buffer.fill_rect(0, 0, 2, SCREEN_WIDTH, " ", fg=theme.text, bg=theme.bg)
    buffer.write(0, 1, "Current database", fg=theme.label, bg=theme.bg)
    buffer.write(0, 18, ":", fg=theme.label, bg=theme.bg)
    buffer.write(0, 20, clip_text(state.current_path_text, 60),
                 fg=theme.text, bg=theme.bg, bold=True)
    buffer.write(1, 1, "Primary index", fg=theme.label, bg=theme.bg)
    buffer.write(1, 18, ":", fg=theme.label, bg=theme.bg)
    buffer.write(1, 20, state.current.index_label if state.current else "",
                 fg=theme.text, bg=theme.bg)

    records = state.records_text
    if records:
        label, value = "Records in database", f" : {records}"
        start = SCREEN_WIDTH - len(label) - len(value) - 1
        buffer.write(0, start, label, fg=theme.label, bg=theme.bg)
        buffer.write(0, start + len(label), value, fg=theme.text, bg=theme.bg)


def main_menu(state: ShellState, selected: int = 0,
              theme: Theme = NEWPORT) -> View:
    """Main menu a 12 comandi, con status box e riga di aiuto."""
    buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT, Cell(fg=theme.text, bg=theme.bg))
    buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                     fg=theme.text, bg=theme.bg)
    _status_box(buffer, state, theme)

    width, height = 72, 9
    top = 4
    left = (SCREEN_WIDTH - width) // 2
    win = window(width, height, "Alpha Four Main Menu", theme)
    regions: list[Region] = []
    for index, (label, _topic) in enumerate(COMMANDS):
        row = 2 + index % 6
        col = 3 if index < 6 else 38
        if index == selected:
            win.fill_rect(row, col - 1, 1, len(label) + 2, " ",
                          fg=theme.selected_fg, bg=theme.selected_bg)
            _write_hot(win, row, col, label, fg=theme.selected_fg, bg=theme.selected_bg)
        else:
            _write_hot(win, row, col, label, fg=theme.window_fg, bg=theme.window_bg)
        regions.append(Region(top + row, left + col - 1, 1, 27, f"menu:{index}"))

    shadow(buffer, top, left, height, width)
    blit(buffer, win, top, left)

    draw_status_line(buffer, theme)
    topic_id = COMMANDS[selected][1]
    draw_help_line(buffer, theme, COMMAND_HELP.get(topic_id, MAIN_MENU_HELP))
    regions.extend(draw_menu_line(buffer, theme, MAIN_MENU_KEYS))
    return View(buffer, regions)


def directory(state: ShellState, cursor: int, input_text: str, input_cursor: int,
              first: int = 0, theme: Theme = NEWPORT) -> View:
    """Database Directory: path, filtro, elenco, prompt e function keys."""
    buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT, Cell(fg=theme.text, bg=theme.bg))
    buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                     fg=theme.text, bg=theme.bg)
    title_bar(buffer, DIRECTORY_TITLE, theme)

    buffer.write(2, 1, "Drive/Path", fg=theme.label, bg=theme.bg)
    buffer.write(2, 13, ":", fg=theme.label, bg=theme.bg)
    buffer.write(2, 15, clip_text(state.path_text(), SCREEN_WIDTH - 20),
                 fg=theme.text, bg=theme.bg, bold=True)
    buffer.write(3, 1, "Default", fg=theme.label, bg=theme.bg)
    buffer.write(3, 13, ":", fg=theme.label, bg=theme.bg)
    buffer.write(3, 15, state.default_types_text, fg=theme.text, bg=theme.bg)

    header_row = LIST_TOP - 1
    buffer.write(header_row, LIST_LEFT, "Name", fg=theme.text, bg=theme.bg, bold=True)
    buffer.write(header_row, TYPE_COL, "Type", fg=theme.text, bg=theme.bg, bold=True)
    buffer.write(header_row, DATE_COL, "Date", fg=theme.text, bg=theme.bg, bold=True)
    if state.detail:
        buffer.write(header_row, DETAIL_RECORDS_COL, "Records",
                     fg=theme.text, bg=theme.bg, bold=True)
        buffer.write(header_row, DETAIL_FIELDS_COL, "Fields",
                     fg=theme.text, bg=theme.bg, bold=True)

    entries = state.listing.entries if state.listing else []
    visible = STATUS_ROW - LIST_TOP
    first = max(0, min(first, max(0, len(entries) - visible)))
    regions: list[Region] = []
    for offset, entry in enumerate(entries[first:first + visible]):
        row = LIST_TOP + offset
        index = first + offset
        selected = index == cursor
        fg, bg = (theme.selected_fg, theme.selected_bg) if selected else (theme.text, theme.bg)
        if selected:
            buffer.fill_rect(row, 0, 1, 78, " ", fg=fg, bg=bg)
        name = entry.name if entry.kind != "file" else entry.name
        buffer.write(row, LIST_LEFT, clip_text(name, NAME_WIDTH), fg=fg, bg=bg)
        if entry.kind == "file":
            buffer.write(row, TYPE_COL, entry.ext, fg=fg, bg=bg)
        elif entry.kind == "dir":
            buffer.write(row, TYPE_COL, "<DIR>", fg=fg, bg=bg)
        buffer.write(row, DATE_COL, entry.date, fg=fg, bg=bg)
        if state.detail and entry.kind == "file":
            if entry.records is not None:
                text = str(entry.records)
                buffer.write(row, DETAIL_RECORDS_COL + 7 - len(text), text, fg=fg, bg=bg)
            if entry.fields is not None:
                text = str(entry.fields)
                buffer.write(row, DETAIL_FIELDS_COL + 6 - len(text), text, fg=fg, bg=bg)
        regions.append(Region(row, 0, 1, SCREEN_WIDTH, f"dir:{index}"))

    if first > 0:
        buffer.write(LIST_TOP, 0, "↑", fg=theme.accent, bg=theme.bg, bold=True)
    if first + visible < len(entries):
        buffer.write(LIST_TOP + visible - 1, 0, "↓", fg=theme.accent, bg=theme.bg, bold=True)
    if state.listing and state.listing.error:
        buffer.write(LIST_TOP, LIST_LEFT, clip_text(state.listing.error, 100),
                     fg=theme.accent, bg=theme.bg)

    prompt_region, _cursor_col = prompt_line(
        buffer, theme, "Enter name of the database/set", input_text, input_cursor)
    regions.append(prompt_region)
    draw_status_line(buffer, theme)
    regions.extend(draw_menu_line(buffer, theme, _directory_keys(state)))
    return View(buffer, regions)


def _directory_keys(state: ShellState) -> list[tuple[str, str]]:
    items = list(DIRECTORY_KEYS)
    label = "Detail off" if state.detail else "Detail on"
    items[4] = ("F8", label)
    return items


def structure(state: ShellState, page: int = 0, theme: Theme = NEWPORT) -> View:
    """Struttura del database: 15 campi per pagina."""
    buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT, Cell(fg=theme.text, bg=theme.bg))
    buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                     fg=theme.text, bg=theme.bg)
    title_bar(buffer, "Database Structure", theme)
    current = state.current
    regions: list[Region] = []
    if current is None or current.header is None:
        buffer.write(3, 2, "No database structure available.",
                     fg=theme.text, bg=theme.bg)
    else:
        header = current.header
        buffer.write(2, 2, "Database", fg=theme.label, bg=theme.bg)
        buffer.write(2, 12, ":", fg=theme.label, bg=theme.bg)
        buffer.write(2, 14, current.name, fg=theme.text, bg=theme.bg, bold=True)
        buffer.write(3, 2, "Length", fg=theme.label, bg=theme.bg)
        buffer.write(3, 12, ":", fg=theme.label, bg=theme.bg)
        buffer.write(3, 14, str(header.record_length), fg=theme.text, bg=theme.bg)
        buffer.write(5, 2, "Number", fg=theme.text, bg=theme.bg, bold=True)
        buffer.write(5, 12, "Name", fg=theme.text, bg=theme.bg, bold=True)
        buffer.write(5, 32, "Type", fg=theme.text, bg=theme.bg, bold=True)
        buffer.write(5, 40, "Width", fg=theme.text, bg=theme.bg, bold=True)
        buffer.write(5, 50, "Decimal Place", fg=theme.text, bg=theme.bg, bold=True)
        per_page = 15
        start = page * per_page
        for offset, field in enumerate(header.fields[start:start + per_page]):
            row = 6 + offset
            buffer.write(row, 3, str(start + offset + 1), fg=theme.text, bg=theme.bg)
            buffer.write(row, 12, field.name[:18], fg=theme.text, bg=theme.bg)
            buffer.write(row, 32, field.type, fg=theme.text, bg=theme.bg)
            buffer.write(row, 41, str(field.length), fg=theme.text, bg=theme.bg)
            buffer.write(row, 50, str(field.decimals), fg=theme.text, bg=theme.bg)
        pages = max(1, (len(header.fields) + per_page - 1) // per_page)
        if pages > 1:
            buffer.write(HELP_ROW, 1, f"Page {page + 1} of {pages}",
                         fg=theme.label, bg=theme.bg)

    draw_status_line(buffer, theme)
    keys = [("F10", "Continue")]
    if current is not None and current.header is not None:
        keys.insert(0, ("PgDn", "Next Page"))
        keys.insert(0, ("PgUp", "Previous Page"))
    regions.extend(draw_menu_line(buffer, theme, keys))
    return View(buffer, regions)


def status_screen(state: ShellState, theme: Theme = NEWPORT) -> View:
    buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT, Cell(fg=theme.text, bg=theme.bg))
    buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                     fg=theme.text, bg=theme.bg)
    title_bar(buffer, "Status", theme)
    current = state.current
    rows = [
        ("Database", current.name if current else "(none)"),
        ("File", str(current.path) if current else "(none)"),
        ("Records", state.records_text or "(unknown)"),
        ("Fields", str(current.fields) if current and current.fields else "(unknown)"),
        ("Primary index", current.index_label if current else "(none)"),
        ("Set", state.current.ext if current and current.ext == "SET" else "(none)"),
        ("Form", "(none)"),
        ("Browse table", "(none)"),
        ("Range", "(none)"),
        ("Printer", "(none)"),
        ("Program", "adbx 0.1 (Alpha Four 3.0 compatible)"),
    ]
    for offset, (label, value) in enumerate(rows):
        row = 2 + offset
        buffer.write(row, 2, label, fg=theme.label, bg=theme.bg)
        buffer.write(row, 16, ":", fg=theme.label, bg=theme.bg)
        buffer.write(row, 18, clip_text(value, 100), fg=theme.text, bg=theme.bg)
    draw_status_line(buffer, theme)
    regions = draw_menu_line(buffer, theme, [("F10", "Continue")])
    return View(buffer, regions)


# -- overlay -------------------------------------------------------------


def overlay_view(base: View, panel: CellBuffer, row: int, col: int,
                 regions: list[Region], theme: Theme = NEWPORT) -> View:
    """Sovrappone una finestra alla vista di base, con ombra."""
    shadow(base.buffer, row, col, panel.height, panel.width)
    blit(base.buffer, panel, row, col)
    shifted = [Region(region.row + row, region.col + col,
                      region.height, region.width, region.action)
               for region in regions]
    return View(base.buffer, base.regions + shifted)


def message_overlay(base: View, text: str, theme: Theme = NEWPORT) -> View:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        lines.extend(text_lines(paragraph, 54))
    height = len(lines) + 5
    width = 62
    panel = window(width, height, "Notice", theme)
    for offset, line in enumerate(lines):
        panel.write(2 + offset, 2, line, fg=theme.window_fg, bg=theme.window_bg)
    panel.write(height - 2, 2, "Press ENTER or ESC", fg=theme.muted, bg=theme.window_bg)
    row = max(2, (STATUS_ROW - height) // 2)
    col = (SCREEN_WIDTH - width) // 2
    return overlay_view(base, panel, row, col,
                        [Region(row, col, height, width, "close")], theme)


def prompt_overlay(base: View, title: str, label: str, text: str, cursor: int, *,
                   secret: bool = False, theme: Theme = NEWPORT) -> View:
    """Finestra di immissione a una riga: nome database, password, conferme."""
    width = 66
    height = 7
    panel = window(width, height, title, theme)
    panel.write(2, 2, label, fg=theme.label, bg=theme.window_bg, bold=True)
    shown = "*" * len(text) if secret else text
    cursor = max(0, min(cursor, len(shown)))
    visible = shown[max(0, cursor - 50):max(0, cursor - 50) + 54]
    panel.write(3, 3, visible, fg=theme.window_fg, bg=theme.window_bg,
                underline=True)
    local = cursor - max(0, cursor - 50)
    char = shown[cursor] if cursor < len(shown) else " "
    panel.write(3, 3 + local, char, fg=1, bg=theme.window_bg, blink=True, bold=True)
    panel.write(height - 2, 3, "ENTER Confirm   ESC Cancel",
                fg=theme.muted, bg=theme.window_bg)
    row = max(2, (STATUS_ROW - height) // 2)
    col = (SCREEN_WIDTH - width) // 2
    region = Region(row + 3, col + 3, 1, 54, "prompt")
    return overlay_view(base, panel, row, col, [region], theme)


def confirm_overlay(base: View, text: str, theme: Theme = NEWPORT) -> View:
    """Conferma di un'operazione distruttiva: ENTER esegue, ESC annulla."""
    lines = text_lines(text, 54)
    height = len(lines) + 5
    width = 62
    panel = window(width, height, "Confirm", theme)
    for offset, line in enumerate(lines):
        panel.write(2 + offset, 2, line, fg=theme.window_fg, bg=theme.window_bg)
    panel.write(height - 2, 2, "ENTER Confirm   ESC Cancel",
                fg=theme.muted, bg=theme.window_bg)
    row = max(2, (STATUS_ROW - height) // 2)
    col = (SCREEN_WIDTH - width) // 2
    return overlay_view(base, panel, row, col,
                        [Region(row, col, height, width, "confirm")], theme)


def help_overlay(base: View, topic_id: str, *, scroll: int = 0, link_index: int = 0,
                 theme: Theme = NEWPORT) -> tuple[View, list[LinkSpan], list[tuple[int, int]]]:
    """Finestra di aiuto con link; ritorna vista, span e posizioni schermo."""
    current = topic(topic_id)
    lines = wrap_topic(current, 72)
    max_body = 30
    scroll = max(0, min(scroll, max(0, len(lines) - max_body)))
    visible = lines[scroll:scroll + max_body]
    height = max(8, len(visible) + 6)
    width = 76
    panel = window(width, height, current.title, theme)

    spans = link_spans(visible)
    link_positions: list[tuple[int, int]] = []
    for row, runs in enumerate(visible):
        column = 0
        for run in runs:
            fg = theme.window_fg
            bg = theme.window_bg
            bold = False
            if run.target:
                span_index = next(
                    (index for index, span in enumerate(spans)
                     if span.line == row
                     and span.column <= column < span.column + span.length),
                    None,
                )
                fg = 1  # blu su finestra chiara
                bold = True
                link_positions.append((2 + row, 2 + column))
                if span_index == link_index:
                    fg, bg = theme.selected_fg, theme.selected_bg
            panel.write(2 + row, 2 + column, run.text, fg=fg, bg=bg, bold=bold)
            column += len(run.text)

    footer = "ENTER Follow   BACKSPACE Back   ESC Close   PgUp/PgDn Scroll"
    panel.write(height - 2, 2, footer, fg=theme.muted, bg=theme.window_bg)

    row = max(1, (STATUS_ROW - height) // 2)
    col = (SCREEN_WIDTH - width) // 2
    regions = [
        Region(row + 2 + span.line, col + 2 + span.column, 1, span.length,
               f"help:{span.target}")
        for span in spans
    ]
    return overlay_view(base, panel, row, col, regions, theme), spans, link_positions


def submenu_overlay(base: View, items: list[tuple[str, str | None]], selected: int,
                    theme: Theme = NEWPORT, title: str = "Desktop Options") -> View:
    width = 46
    height = len(items) + 5
    panel = window(width, height, title, theme)
    regions: list[Region] = []
    for index, (label, _action) in enumerate(items):
        row = 2 + index
        if index == selected:
            panel.fill_rect(row, 1, 1, width - 2, " ",
                            fg=theme.selected_fg, bg=theme.selected_bg)
            panel.write(row, 3, label, fg=theme.selected_fg, bg=theme.selected_bg)
        else:
            panel.write(row, 3, label, fg=theme.window_fg, bg=theme.window_bg)
        regions.append(Region(row, 1, 1, width - 2, f"submenu:{index}"))
    panel.write(height - 2, 3, "ENTER Select   ESC Cancel",
                fg=theme.muted, bg=theme.window_bg)
    row = max(2, (STATUS_ROW - height) // 2)
    col = (SCREEN_WIDTH - width) // 2
    return overlay_view(base, panel, row, col, regions, theme)


def history_overlay(base: View, paths: list[Path], selected: int,
                    theme: Theme = NEWPORT) -> View:
    width = 78
    height = max(8, min(len(paths), 10) + 5)
    panel = window(width, height, "Selection History", theme)
    regions: list[Region] = []
    for index, path in enumerate(paths[:10]):
        row = 2 + index
        text = clip_text(str(path), width - 6)
        if index == selected:
            panel.fill_rect(row, 1, 1, width - 2, " ",
                            fg=theme.selected_fg, bg=theme.selected_bg)
            panel.write(row, 3, text, fg=theme.selected_fg, bg=theme.selected_bg)
        else:
            panel.write(row, 3, text, fg=theme.window_fg, bg=theme.window_bg)
        regions.append(Region(row, 1, 1, width - 2, f"history:{index}"))
    panel.write(height - 2, 3, "ENTER Open   ESC Cancel",
                fg=theme.muted, bg=theme.window_bg)
    row = max(2, (STATUS_ROW - height) // 2)
    col = (SCREEN_WIDTH - width) // 2
    return overlay_view(base, panel, row, col, regions, theme)


__all__ = [
    "COMMANDS",
    "COMMAND_HELP",
    "DIRECTORY_TITLE",
    "hot_index",
    "directory",
    "help_overlay",
    "history_overlay",
    "main_menu",
    "message_overlay",
    "status_screen",
    "structure",
    "submenu_overlay",
]
