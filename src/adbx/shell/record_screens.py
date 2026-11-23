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
    if session.form is not None:
        return custom_form_screen(session, theme)
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
    draw_help_line(buffer, theme,
                   session.status or _form_field_hint(session) or hint)
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
    text += f"   [{session.order_indicator}]"
    if session.is_search_list:
        text += " Search/Sort"
        if session.search_out_of_date:
            text += " \u2666"
    return text


def _form_field_hint(session: RecordSession) -> str:
    prompt = session.field_prompt()
    if prompt:
        return prompt
    return ""


def _form_hint(session: RecordSession) -> str:
    if session.locate is not None:
        return "F3 next locate   ESC exit locate   ALT-M memo   ALT-D delete"
    if session.mode == "view":
        return ("F Find   L Locate   I Index   R Range   F7 show deleted   "
                "ALT-M memo   ALT-D delete")
    if session.mode == "browse":
        return ("F Find   L Locate   I Index   R Range   F7 show deleted   "
                "F10 continue")
    return "TAB next field   F10 save   ESC cancel   ALT-M memo   ALT-F5 copy   ALT-F6 paste"


def browse_screen(session: RecordSession, theme: Theme = NEWPORT) -> View:
    buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT, Cell(fg=theme.text, bg=theme.bg))
    buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                     fg=theme.text, bg=theme.bg)
    title_bar(buffer, f"{session.title} - {session.database.name}", theme)
    draw_status_line(buffer, theme, _position_text(session))
    fields = session.database.fields
    rows = session.browse_rows()
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


def lookup_overlay(session: RecordSession, theme: Theme = NEWPORT) -> View:
    """Finestra di scelta sopra il form; gestisce tabelle e cascate."""
    state = session.lookup
    assert state is not None
    base = form_screen(session, theme)
    choices = state.choices
    columns = list(choices.headers) or ["Choice"]
    def _width(column: int, maximum: int) -> int:
        longest = len(columns[column])
        for row in choices.rows[:50]:
            if column < len(row):
                longest = max(longest, len(row[column]))
        return min(maximum, max(8, longest + 2))

    widths = [_width(0, 30)]
    widths += [_width(index, 18) for index in range(1, len(columns))]
    total = sum(widths) + 2
    width = min(SCREEN_WIDTH - 4, max(34, total))
    height = min(STATUS_ROW - 2, max(6, min(len(choices.values), 15) + 6))
    title = session.lookup.field_name.title() + " Choices"
    if state.path:
        title += " - " + " > ".join(state.path)
    panel = window(width, height, title, theme)
    header = ""
    for name, column_width in zip(columns, widths):
        header += clip_text(name, column_width).ljust(column_width)
    panel.write(2, 1, clip_text(header, width - 2), fg=theme.label,
                bg=theme.window_bg, bold=True)
    visible = height - 5
    top = max(0, min(state.selected - visible + 1,
                     max(0, len(choices.values) - visible)))
    regions: list[Region] = []
    for offset in range(visible):
        index = top + offset
        if index >= len(choices.values):
            break
        row = 3 + offset
        selected = index == state.selected
        fg = theme.selected_fg if selected else theme.window_fg
        bg = theme.selected_bg if selected else theme.window_bg
        if selected:
            panel.fill_rect(row, 1, 1, width - 2, " ", fg=fg, bg=bg)
        cells = choices.rows[index] if index < len(choices.rows) else []
        text = ""
        for column_index, column_width in enumerate(widths):
            cell = cells[column_index] if column_index < len(cells) else ""
            text += clip_text(cell, column_width).ljust(column_width)
        panel.write(row, 1, clip_text(text, width - 2), fg=fg, bg=bg)
        regions.append(Region(row, 1, 1, width - 2, f"lookup:{index}"))
    footer = ("ENTER choose   LEFT up a level   ESC cancel"
              if state.path or choices.source == "Cascading"
              else "ENTER choose   ESC cancel   type to find")
    panel.write(height - 2, 1, clip_text(footer, width - 2), fg=theme.muted,
                bg=theme.window_bg)
    location = "3"
    rule = session._rule(session._field())
    if rule is not None:
        location = rule.location
    if location == "Hidden":
        row = max(2, (STATUS_ROW - height) // 2)
        col = (SCREEN_WIDTH - width) // 2
    else:
        number = int(location) if location.isdigit() else 5
        column = (number - 1) % 3
        line = (number - 1) // 3
        col = [2, (SCREEN_WIDTH - width) // 2,
               SCREEN_WIDTH - width - 2][column]
        row = [2, (STATUS_ROW - height) // 2,
               STATUS_ROW - height - 1][line]
    return screens.overlay_view(base, panel, max(1, row), max(1, col),
                                regions, theme)


def custom_form_screen(session: RecordSession,
                       theme: Theme = NEWPORT) -> View:
    """Form definito dall'utente: campi, testi, riquadri e pagine."""
    form = session.form
    buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                        Cell(fg=theme.text, bg=theme.bg))
    buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                     fg=theme.text, bg=theme.bg)
    title_bar(buffer, f"{session.title} - {session.database.name}", theme)
    values = session._values()
    page = max(0, min(session.form_page, form.pages - 1))
    for box in form.page_boxes(page):
        buffer.box(box.row, box.col, box.height, box.width,
                   fg=theme.border, bg=theme.bg, double=box.double)
    for label in form.page_labels(page):
        buffer.write(label.row, label.col, clip_text(
            label.text, max(0, SCREEN_WIDTH - label.col)), fg=theme.text,
            bg=theme.bg)
    navigation = session._navigation_fields()
    active_name = ""
    if 0 <= session.field_index < len(navigation):
        active_name = navigation[session.field_index].name
    for item in form.page_fields(page):
        if item.kind == "summary":
            text = ""
        elif item.kind == "calculated":
            text = form.value_for(item, values, session.database)
        else:
            text = values.get(item.field, "")
        width = max(1, item.window or item.length or 1)
        if item.show_title and item.title:
            buffer.write(item.row - 1, item.col,
                         clip_text(item.title, max(20, width)),
                         fg=theme.label, bg=theme.bg)
        if item.format.startswith("!") and item.kind == "field":
            body = text[: item.length or len(text)]
            lines = [body[index:index + width]
                     for index in range(0, len(body), width)] or [""]
            for offset, line in enumerate(lines):
                buffer.write(item.row + offset, item.col,
                             clip_text(line, width), fg=theme.text,
                             bg=theme.bg)
            continue
        active = (session.mode in ("enter", "change")
                  and item.kind == "field" and item.field == active_name)
        if active:
            buffer.fill_rect(item.row, item.col, 1, width, " ",
                             fg=theme.selected_fg, bg=theme.selected_bg)
            text = session.edit_text
            buffer.write(item.row, item.col, clip_text(text, width),
                         fg=theme.selected_fg, bg=theme.selected_bg,
                         underline=True)
        else:
            if item.justification == "R":
                text = text.rjust(width)
            elif item.justification == "C":
                text = text.center(width)
            buffer.write(item.row, item.col, clip_text(text, width),
                         fg=theme.text, bg=theme.bg,
                         bold=item.kind in ("calculated", "summary"))
        if item.kind == "field":
            index = next((position for position, field in enumerate(navigation)
                          if field.name == item.field), -1)
            if index >= 0:
                buffer_region = Region(item.row, item.col, 1, width,
                                       f"rec:field:{index}")
                # regioni raccolte sotto
                session._form_regions = getattr(session, "_form_regions", [])
                session._form_regions.append(buffer_region)
    draw_status_line(buffer, theme, _position_text(session))
    hint = _form_hint(session)
    draw_help_line(buffer, theme,
                   session.status or _form_field_hint(session) or hint)
    regions = list(getattr(session, "_form_regions", []))
    session._form_regions = []
    regions.extend(draw_menu_line(buffer, theme, MODE_KEYS[session.mode]))
    return View(buffer, regions)
