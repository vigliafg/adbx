"""Rendering delle modalità record: form, browse table e memo editor."""

from __future__ import annotations

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW, Cell, CellBuffer
from ..data.fields import format_value
from . import screens
from .records import MODE_KEYS, RecordSession
from .theme import NEWPORT, Theme
from .widgets import (
    Region,
    View,
    clip_text,
    draw_help_line,
    draw_menu_line,
    draw_status_line,
    title_bar,
    window,
)

FORM_TOP = 3
BROWSE_HEADER_ROW = 2
BROWSE_TOP = 3
NUMBER_WIDTH = 6


def form_screen(session: RecordSession, theme: Theme = NEWPORT) -> View:
    buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT, Cell(fg=theme.text, bg=theme.bg))
    buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                     fg=theme.text, bg=theme.bg)
    title_bar(buffer, f"{session.title} - {session.database.name}", theme)
    regions: list[Region] = []
    fields = session.database.fields
    values = session._values()
    rows = STATUS_ROW - FORM_TOP
    columns = max(1, min(4, (len(fields) + rows - 1) // rows)) if fields else 1
    if len(fields) > 18:
        columns = max(2, columns)
    per_column = max(1, (len(fields) + columns - 1) // columns)
    column_width = SCREEN_WIDTH // columns
    label_width = min(13, max(8, column_width // 3))
    value_width = max(4, column_width - label_width - 3)

    draw_status_line(buffer, theme, _position_text(session))
    if not fields:
        buffer.write(FORM_TOP + 1, 2, "This database has no fields.",
                     fg=theme.text, bg=theme.bg)

    for index, field in enumerate(fields):
        group = index // per_column
        row = FORM_TOP + index % per_column
        col = 1 + group * column_width
        active = index == session.field_index
        label_fg = theme.accent if active else theme.label
        buffer.write(row, col, clip_text(field.name, label_width),
                     fg=label_fg, bg=theme.bg, bold=active)
        buffer.write(row, col + label_width, ":", fg=theme.label, bg=theme.bg)
        value_col = col + label_width + 2
        text = _display(session, field, values)
        if session.mode in ("enter", "change") and active:
            buffer.fill_rect(row, value_col, 1, value_width, " ",
                             fg=theme.selected_fg, bg=theme.selected_bg)
            _write_cursor_field(buffer, row, value_col, value_width, session,
                                theme)
        else:
            fg = theme.accent if active and session.mode == "view" else theme.text
            buffer.write(row, value_col, clip_text(text, value_width),
                         fg=fg, bg=theme.bg, bold=active)
        regions.append(Region(row, col, 1, value_col + value_width - col,
                              f"rec:field:{index}"))

    hint = _form_hint(session)
    draw_help_line(buffer, theme, session.status or hint)
    regions.extend(draw_menu_line(buffer, theme, MODE_KEYS[session.mode]))
    return View(buffer, regions)


def _display(session: RecordSession, field, values: dict[str, str]) -> str:
    if field.is_memo:
        return "<Memo>" if values.get(field.name) else ""
    return format_value(field, values.get(field.name, ""))


def _write_cursor_field(buffer: CellBuffer, row: int, col: int, width: int,
                        session: RecordSession, theme: Theme) -> None:
    """Scrive il valore attivo con cursore, facendo scorrere il testo lungo."""
    text = session.edit_text
    cursor = max(0, min(session.edit_cursor, len(text)))
    start = 0
    if cursor >= width:
        start = cursor - width + 1
    visible = text[start:start + width]
    buffer.write(row, col, visible, fg=theme.selected_fg, bg=theme.selected_bg,
                 underline=True)
    cursor_col = col + cursor - start
    char = text[cursor] if cursor < len(text) else " "
    buffer.write(row, cursor_col, char, fg=theme.accent, bg=theme.selected_bg,
                 blink=True, bold=True)
    if session.insert_mode:
        buffer.write(row, col + width - 1, "I", fg=theme.accent,
                     bg=theme.selected_bg, bold=True)


def _position_text(session: RecordSession) -> str:
    if session.mode == "enter" and session.seq is None:
        if session.record_count:
            return f"New record   ({session.record_count} existing)"
        return "New record"
    if session.record_count == 0:
        return "No records"
    text = f"Record {session.index + 1} of {session.record_count}"
    seq = session.current_seq
    if seq is not None and session.database.is_deleted(seq):
        text += "   DELETED"
    return text


def _form_hint(session: RecordSession) -> str:
    if session.mode == "view":
        return "UP/DOWN records   LEFT/RIGHT field   F7 show deleted   ALT-M memo   ALT-D delete"
    if session.mode == "browse":
        return "UP/DOWN records   LEFT/RIGHT columns   F7 show deleted   F10 continue"
    return "TAB next field   F10 save   ESC cancel   ALT-M memo   ALT-F5 copy   ALT-F6 paste"


def browse_screen(session: RecordSession, theme: Theme = NEWPORT) -> View:
    buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT, Cell(fg=theme.text, bg=theme.bg))
    buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                     fg=theme.text, bg=theme.bg)
    title_bar(buffer, f"{session.title} - {session.database.name}", theme)
    draw_status_line(buffer, theme, _position_text(session))
    fields = session.database.fields
    rows = session.database.browse(include_deleted=session.show_deleted)
    visible = STATUS_ROW - BROWSE_TOP
    regions: list[Region] = []

    buffer.write(BROWSE_HEADER_ROW, 0, "#", fg=theme.text, bg=theme.bg, bold=True)
    columns = _columns(session)
    for field, width, col in columns:
        buffer.write(BROWSE_HEADER_ROW, col, clip_text(field.name, width - 1),
                     fg=theme.text, bg=theme.bg, bold=True)
        regions.append(Region(BROWSE_HEADER_ROW, col, 1, width,
                              f"rec:col:{fields.index(field)}"))

    start = min(session.top, max(0, len(rows) - visible))
    for offset in range(visible):
        position = start + offset
        if position >= len(rows):
            break
        seq, deleted, values = rows[position]
        row = BROWSE_TOP + offset
        selected = position == session.index
        fg, bg = ((theme.selected_fg, theme.selected_bg) if selected
                  else (theme.text, theme.bg))
        if selected:
            buffer.fill_rect(row, 0, 1, SCREEN_WIDTH, " ", fg=fg, bg=bg)
        buffer.write(row, 0, f"{'*' if deleted else ' '}{seq:4d} ", fg=fg, bg=bg,
                     bold=deleted)
        for field, width, col in columns:
            text = _browse_value(field, values.get(field.name, ""))
            if field.type == "N":
                text = text.rjust(width - 1)
            buffer.write(row, col, clip_text(text, width - 1), fg=fg, bg=bg)
        regions.append(Region(row, 0, 1, SCREEN_WIDTH, f"rec:row:{position}"))

    if session.browse_field:
        buffer.write(BROWSE_HEADER_ROW, SCREEN_WIDTH - 1, "<",
                     fg=theme.accent, bg=theme.bg, bold=True)
    if columns and columns[-1][2] + columns[-1][1] < SCREEN_WIDTH:
        buffer.write(BROWSE_HEADER_ROW, SCREEN_WIDTH - 1, ">",
                     fg=theme.accent, bg=theme.bg, bold=True)
    draw_help_line(buffer, theme, session.status or _form_hint(session))
    regions.extend(draw_menu_line(buffer, theme, MODE_KEYS[session.mode]))
    return View(buffer, regions)


def _columns(session: RecordSession) -> list[tuple[object, int, int]]:
    columns: list[tuple[object, int, int]] = []
    col = NUMBER_WIDTH + 1
    for field in session.database.fields[session.browse_field:]:
        desired = max(field.length, len(field.name))
        if field.is_memo:
            width = max(7, len(field.name) + 1)
        else:
            width = max(4, min(desired, 18)) + 1
        if col + width > SCREEN_WIDTH:
            break
        columns.append((field, width, col))
        col += width
    return columns


def _browse_value(field, value: str) -> str:
    if field.is_memo:
        return "<Memo>" if value else ""
    return format_value(field, value)


def memo_overlay(session: RecordSession, theme: Theme = NEWPORT) -> View:
    base = (browse_screen(session, theme)
            if session.mode == "browse" else form_screen(session, theme))
    editor = session.memo
    assert editor is not None
    title = f"Memo - {session.database.name}.{editor.field_name}"
    if editor.readonly:
        title += " (read only)"
    width, height = 104, 27
    panel = window(width, height, title, theme)
    body_height = height - 5
    for offset in range(body_height):
        index = editor.top + offset
        if index >= len(editor.lines):
            break
        line = editor.lines[index]
        text = line[editor.left:editor.left + width - 4]
        panel.write(2 + offset, 2, text,
                    fg=theme.window_fg, bg=theme.window_bg,
                    underline=index == editor.row and not editor.readonly)
        if index == editor.row and not editor.readonly:
            cursor = editor.col - editor.left
            if 0 <= cursor < width - 4:
                char = line[editor.col] if editor.col < len(line) else " "
                panel.write(2 + offset, 2 + cursor, char, fg=1,
                            bg=theme.window_bg, blink=True, bold=True)
    position = f"{editor.row + 1},{editor.col + 1}   {len(editor.body)} characters"
    footer = ("ESC Close" if editor.readonly
              else "F10 Save   ESC Cancel   PgUp/PgDn Scroll")
    panel.write(height - 2, 2, footer, fg=theme.muted, bg=theme.window_bg)
    panel.write(height - 2, width - len(position) - 3, position,
                fg=theme.muted, bg=theme.window_bg)
    row = max(1, (STATUS_ROW - height) // 2)
    col = max(1, (SCREEN_WIDTH - width) // 2)
    region = Region(row, col, height, width, "rec:memo")
    return screens.overlay_view(base, panel, row, col, [region], theme)


__all__ = ["BROWSE_HEADER_ROW", "BROWSE_TOP", "browse_screen", "form_screen",
           "memo_overlay"]
