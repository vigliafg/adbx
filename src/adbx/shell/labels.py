"""Mail label designer (O8)."""

from __future__ import annotations

from dataclasses import dataclass

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, Cell, CellBuffer
from ..data.labels import (
    JUSTIFICATIONS,
    LABEL_LETTERS,
    PREDEFINED_LABELS,
    LabelCalc,
    LabelDefinition,
    LabelError,
    LabelField,
    LabelText,
)
from ..data.labels_engine import render_labels
from ..data.workspace import Database, Workspace
from ..screen.keys import Key, character
from .dialogs import Picker, picker_view
from .theme import NEWPORT, Theme
from .widgets import (
    View,
    clip_text,
    draw_help_line,
    draw_menu_line,
    draw_status_line,
    title_bar,
)

LABEL_KEYS = [("F1", "Help"), ("F2", "Fields"), ("F4", "Calc"),
              ("F5", "Del"), ("F7", "Params"), ("F9", "Line"),
              ("F10", "Save"), ("Alt-O", "Fmt")]
CONTENT_TOP = 4


@dataclass
class LabelDesigner:
    workspace: Workspace
    database: Database | None = None
    owner: str = ""
    label: LabelDefinition | None = None
    theme: Theme = NEWPORT
    stage: str = "letter"
    letter_text: str = ""
    edit_existing: bool = False
    param_row: int = 0
    edit_text: str = ""
    edit_key: str = ""
    editing: bool = False
    row: int = 1
    col: int = 1
    picker: Picker | None = None
    picker_kind: str = ""
    pending_database: str = ""
    format_row: int = 0
    format_col: int = 1
    calc_row: int = 0
    status: str = ""
    close: bool = False
    saved: bool = False
    saved_label: LabelDefinition | None = None
    preview_request: bool = False
    help_topic: str = "labels"

    def __post_init__(self) -> None:
        if not self.owner:
            self.owner = self.database.name if self.database else ""

    @property
    def owner_databases(self) -> dict[str, Database]:
        database = self.workspace.get(self.owner)
        if database is not None:
            return {database.name: database}
        definition = self.workspace.get_set(self.owner)
        if definition is None:
            return {}
        return {name: definition.database(name)
                for name in definition.database_names()}

    @property
    def title(self) -> str:
        if self.stage == "letter":
            return "Create/Edit a Mail Label"
        if self.label is None:
            return "Mail Label Layout"
        return f"Mail Label Layout - {self.label.letter} - {self.owner}"

    def handle(self, key: Key) -> None:
        self.status = ""
        if self.picker is not None:
            self._handle_picker(key)
            return
        if self.stage == "letter":
            self._handle_letter(key)
        elif self.stage == "params":
            self._handle_params(key)
        elif self.stage == "layout":
            self._handle_layout(key)
        elif self.stage == "formatting":
            self._handle_formatting(key)
        elif self.stage == "calc":
            self._handle_calc(key)
        elif self.stage == "calc_name":
            self._handle_calc_name(key)
        elif self.stage == "calc_expression":
            self._handle_calc_expression(key)
        elif self.stage == "borrow_letter":
            self._handle_borrow_letter(key)

    # -- creazione -------------------------------------------------------
    def _handle_letter(self, key: Key) -> None:
        if key.name == "ENTER":
            letter = self.letter_text.strip().upper()[:1] or "A"
            if letter not in LABEL_LETTERS:
                self.status = "Choose a label id A-Z."
                return
            existing = self.workspace.get_label(self.owner, letter)
            if existing is not None:
                self.label = existing
                self.edit_existing = True
                self.stage = "layout"
                self.row = 1
                self.col = 1
                self.status = "Editing an existing label."
            else:
                self.label = LabelDefinition(self.workspace, self.owner,
                                             letter)
                self.stage = "params"
                self.param_row = 0
            return
        if key.name == "ESC":
            self.close = True
            return
        text = character(key)
        if text and text.isalpha():
            self.letter_text = text.upper()

    def _parameter_rows(self) -> list[tuple[str, str, str, str]]:
        label = self.label
        assert label is not None
        return [
            ("description", "Label description", label.description, "text"),
            ("width", "Label width (columns)", str(label.width), "int"),
            ("height", "Label height (lines)", str(label.height), "int"),
            ("across", "Number of labels across", str(label.across), "int"),
            ("columns", "Columns between labels", str(label.columns_between),
             "int"),
            ("lines", "Lines between labels", str(label.lines_between), "int"),
            ("copies", "Number of copies of each label", label.copies, "text"),
            ("left", "Left margin", str(label.left_margin), "int"),
            ("continuous", "Print labels on continuous feed paper",
             _yes(label.continuous_feed), "bool"),
            ("rows", "How many rows of labels per page",
             str(label.rows_per_page), "int"),
            ("top", "Top margin", str(label.top_margin), "int"),
        ]

    def _handle_params(self, key: Key) -> None:
        rows = self._parameter_rows()
        name = key.name
        if self.editing:
            if name == "ENTER":
                self._commit_param()
                self.editing = False
                return
            if name == "ESC":
                self.editing = False
                return
            if name == "BACKSPACE":
                self.edit_text = self.edit_text[:-1]
                return
            text = character(key)
            if text:
                if text.isalpha() and not key.shift:
                    text = text.lower()
                self.edit_text += text
            return
        if name == "F4":
            self.picker = Picker(
                "Pre-defined sizes",
                [entry[0] for entry in PREDEFINED_LABELS],
                values=[str(index) for index in range(len(PREDEFINED_LABELS))],
                footer="ENTER select   ESC cancel")
            self.picker_kind = "predefined"
            return
        if name == "F10":
            self._commit_param()
            self.stage = "layout"
            self.row = 1
            self.col = 1
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN"):
            self._commit_param()
            self.param_row = max(0, min(len(rows) - 1,
                                        self.param_row
                                        + (-1 if name == "UP" else 1)))
            return
        if name == "ENTER":
            if rows[self.param_row][3] == "bool":
                self.label.continuous_feed = not self.label.continuous_feed
                return
            self.edit_text = rows[self.param_row][2]
            self.edit_key = rows[self.param_row][0]
            self.editing = True

    def _commit_param(self) -> None:
        label = self.label
        if label is None:
            return
        rows = self._parameter_rows()
        name = rows[self.param_row][0]
        if self.edit_key != name:
            return
        self.edit_key = ""
        value = self.edit_text.strip()
        if name == "description":
            label.description = value
        elif name == "copies":
            label.copies = value or "1"
        elif name in ("width", "height", "across", "columns", "lines",
                      "left", "rows", "top"):
            try:
                number = int(value)
            except ValueError:
                return
            attribute = {"width": "width", "height": "height",
                         "across": "across", "columns": "columns_between",
                         "lines": "lines_between", "left": "left_margin",
                         "rows": "rows_per_page", "top": "top_margin"}[name]
            setattr(label, attribute, number)
            label.__post_init__()

    # -- layout ----------------------------------------------------------
    def _handle_layout(self, key: Key) -> None:
        label = self.label
        assert label is not None
        name = key.name
        if name == "F2":
            self._open_field_picker()
            return
        if name == "F4":
            self.picker = Picker("Label field", ["Calculated field"],
                                 values=["calculated"],
                                 footer="ENTER select   ESC cancel")
            self.picker_kind = "synthetic"
            return
        if name == "F5":
            self._delete_at_cursor()
            return
        if name == "F7":
            self.stage = "params"
            self.param_row = 0
            return
        if name == "F9":
            self.picker = Picker(
                "Line", ["Left justify", "Center justify", "Right justify",
                         "Insert line", "Delete line", "Add line at end",
                         "Fill to end with -"],
                values=["left", "center", "right", "insert", "delete", "add",
                        "fill"],
                footer="ENTER select   ESC cancel")
            self.picker_kind = "line"
            return
        if name == "F10":
            self._open_save()
            return
        if key.alt and name == "O":
            self.stage = "formatting"
            self.format_row = self._field_index_at_cursor()
            self.format_col = 2
            return
        if name == "ESC":
            self.close = True
            return
        if name == "UP":
            self.row = max(1, self.row - 1)
            return
        if name == "DOWN":
            self.row = min(label.height, self.row + 1)
            return
        if name == "LEFT":
            self.col = max(1, self.col - 1)
            return
        if name == "RIGHT":
            self.col = min(label.width, self.col + 1)
            return
        if name == "HOME":
            self.col = 1
            return
        if name == "END":
            self.col = label.width
            return
        if name == "BACKSPACE":
            self._backspace()
            return
        if name == "DELETE":
            self._delete_char()
            return
        if name == "SPACE":
            self._type(" ")
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self._type(text)

    def _type(self, text: str) -> None:
        label = self.label
        assert label is not None
        item = self._text_at(self.row, self.col)
        if item is None:
            before = next((entry for entry in label.texts
                           if entry.row == self.row
                           and entry.col + len(entry.text) == self.col), None)
            if before is not None:
                before.text += text
            else:
                label.texts.append(LabelText(self.row, self.col, text))
        else:
            offset = self.col - item.col
            item.text = item.text[:offset] + text + item.text[offset + 1:]
        self.col = min(label.width, self.col + 1)

    def _text_at(self, row: int, col: int) -> LabelText | None:
        assert self.label is not None
        for item in self.label.texts:
            if item.row == row and item.col <= col < item.col + len(item.text):
                return item
        return None

    def _backspace(self) -> None:
        item = self._text_at(self.row, self.col - 1)
        assert self.label is not None
        if item is None:
            self.col = max(1, self.col - 1)
            return
        offset = self.col - 1 - item.col
        item.text = item.text[:offset] + item.text[offset + 1:]
        if not item.text:
            self.label.texts.remove(item)
        self.col = max(1, self.col - 1)

    def _delete_char(self) -> None:
        item = self._text_at(self.row, self.col)
        if item is None:
            return
        offset = self.col - item.col
        item.text = item.text[:offset] + item.text[offset + 1:]
        if not item.text:
            self.label.texts.remove(item)

    def _field_at(self, row: int, col: int) -> LabelField | None:
        assert self.label is not None
        for item in self.label.fields:
            if item.row == row and item.col <= col < item.col + max(
                    1, item.length):
                return item
        return None

    def _field_index_at_cursor(self) -> int:
        item = self._field_at(self.row, self.col)
        if item is None or self.label is None:
            return 0
        try:
            return self.label.fields.index(item)
        except ValueError:
            return 0

    def _delete_at_cursor(self) -> None:
        item = self._field_at(self.row, self.col)
        if item is not None:
            self.label.fields.remove(item)
            return
        text = self._text_at(self.row, self.col)
        if text is not None:
            self.label.texts.remove(text)

    # -- picker ----------------------------------------------------------
    def _open_field_picker(self) -> None:
        items = list(self.owner_databases) + ["SYSTEM"]
        values = list(self.owner_databases) + ["SYSTEM"]
        if self.label is not None and self.label.calcs:
            items.append("CALC")
            values.append("CALC")
        self.picker = Picker("Database", items, values,
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "database"

    def _handle_picker(self, key: Key) -> None:
        picker = self.picker
        assert picker is not None
        if key.name == "UP":
            picker.move(-1)
        elif key.name == "DOWN":
            picker.move(1)
        elif key.name == "PGUP":
            picker.move(-10)
        elif key.name == "PGDN":
            picker.move(10)
        elif key.name == "ESC":
            self.picker = None
        elif key.name == "ENTER":
            value = picker.value()
            kind = self.picker_kind
            self.picker = None
            if value:
                self._selected(kind, value)

    def _selected(self, kind: str, value: str) -> None:
        label = self.label
        assert label is not None
        if kind == "database":
            self.pending_database = value
            self._open_fields(value)
        elif kind == "field":
            database, field = value.split(":", 1)
            definition = (self.owner_databases[database].field(field)
                          if database not in ("SYSTEM", "CALC") else None)
            length = definition.length if definition else min(10, label.width)
            length = min(length, label.width - self.col + 1)
            if length <= 0:
                self.status = "No room for the field."
                return
            label.fields.append(LabelField(
                self.row, self.col, f"{database}.{field}", database, field,
                length, "Suppress"))
            self.col = min(label.width, self.col + length)
        elif kind == "synthetic":
            self.stage = "calc"
            self.status = "F2 adds a calculated field."
        elif kind == "line":
            self._line_action(value)
        elif kind == "predefined":
            entry = PREDEFINED_LABELS[int(value)]
            _title, width, height, across, columns, lines = entry
            label.width, label.height = width, height
            label.across, label.columns_between = across, columns
            label.lines_between = lines
            label.__post_init__()
            self.status = f"Size: {entry[0]}."
        elif kind == "save":
            self._save_action(value)
        elif kind == "calc_delete":
            label.calcs = [calc for calc in label.calcs if calc.name != value]

    def _open_fields(self, database_name: str) -> None:
        label = self.label
        assert label is not None
        items: list[str] = []
        values: list[str] = []
        if database_name == "SYSTEM":
            names = ("DATE", "TIME", "REC_NUMBER", "CNTR_GRAND", "DELETED",
                     "INDEX_NAME", "INDEX_DESC", "INDEX_EQN", "DB_NAME",
                     "DB_DESC", "SET_NAME", "SET_DESC")
            items = list(names)
            values = [f"SYSTEM:{name}" for name in names]
        elif database_name == "CALC":
            items = [calc.name for calc in label.calcs]
            values = [f"CALC:{calc.name}" for calc in label.calcs]
        else:
            for definition in self.owner_databases[database_name].fields:
                if definition.is_memo:
                    continue
                items.append(definition.name)
                values.append(f"{database_name}:{definition.name}")
        if not items:
            self.status = "No fields available."
            return
        self.picker = Picker("Fieldnames", items, values,
                             footer="ENTER place field   ESC cancel")
        self.picker_kind = "field"

    def _line_action(self, action: str) -> None:
        label = self.label
        assert label is not None
        if action == "add":
            label.height = min(20, label.height + 1)
            return
        if action == "insert":
            for item in label.fields:
                if item.row >= self.row:
                    item.row += 1
            for item in label.texts:
                if item.row >= self.row:
                    item.row += 1
            label.height = min(20, label.height + 1)
            return
        if action == "delete":
            label.fields = [item for item in label.fields
                            if item.row != self.row]
            label.texts = [item for item in label.texts
                           if item.row != self.row]
            for item in label.fields:
                if item.row > self.row:
                    item.row -= 1
            for item in label.texts:
                if item.row > self.row:
                    item.row -= 1
            label.height = max(1, label.height - 1)
            self.row = min(self.row, label.height)
            return
        if action == "fill":
            label.texts.append(LabelText(self.row, self.col,
                                         "-" * (label.width - self.col + 1)))
            return
        texts = [item for item in label.texts if item.row == self.row]
        if not texts:
            return
        start = min(item.col for item in texts)
        end = max(item.col + len(item.text) for item in texts)
        if action == "left":
            shift = 1 - start
        elif action == "center":
            shift = (label.width - (end - start)) // 2 + 1 - start
        else:
            shift = label.width - (end - start) + 1 - start
        for item in texts:
            item.col = max(1, item.col + shift)

    # -- calcolati -------------------------------------------------------
    def _handle_calc(self, key: Key) -> None:
        label = self.label
        assert label is not None
        if key.name == "F10":
            self.stage = "layout"
            return
        if key.name == "ESC":
            self.close = True
            return
        if key.name == "F2":
            self.edit_text = ""
            self.stage = "calc_name"
            return
        if key.name in ("UP", "DOWN") and label.calcs:
            self.calc_row = max(0, min(len(label.calcs) - 1,
                                       self.calc_row
                                       + (-1 if key.name == "UP" else 1)))
            return
        if key.name == "F5" and label.calcs:
            removed = label.calcs.pop(self.calc_row)
            label.fields = [item for item in label.fields
                            if item.source != f"CALC.{removed.name}"]
            self.calc_row = max(0, min(self.calc_row, len(label.calcs) - 1))

    def _handle_calc_name(self, key: Key) -> None:
        if key.name == "ENTER":
            name = self.edit_text.strip().upper()
            try:
                LabelCalc(name, "0")
            except LabelError as exc:
                self.status = str(exc)
                return
            self._pending_calc_name = name
            self.edit_text = ""
            self.stage = "calc_expression"
            return
        if key.name == "ESC":
            self.stage = "calc"
            return
        if key.name == "BACKSPACE":
            self.edit_text = self.edit_text[:-1]
            return
        text = character(key)
        if text and (text.isalnum() or text == "_"):
            self.edit_text += text.upper()

    def _handle_calc_expression(self, key: Key) -> None:
        label = self.label
        assert label is not None
        if key.name == "ENTER":
            try:
                calc = LabelCalc(getattr(self, "_pending_calc_name", "CALC1"),
                                 self.edit_text.strip())
            except LabelError as exc:
                self.status = str(exc)
                return
            label.calcs.append(calc)
            self.stage = "calc"
            self.status = f"Calculated field {calc.name} saved."
            return
        if key.name == "ESC":
            self.stage = "calc"
            return
        if key.name == "BACKSPACE":
            self.edit_text = self.edit_text[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self.edit_text += text

    # -- formatting ------------------------------------------------------
    def _handle_formatting(self, key: Key) -> None:
        label = self.label
        assert label is not None
        rows = label.fields
        name = key.name
        if name == "F10":
            self.stage = "layout"
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN") and rows:
            self.format_row = max(0, min(len(rows) - 1,
                                         self.format_row
                                         + (-1 if name == "UP" else 1)))
            return
        if name == "TAB":
            self.format_col = self.format_col % 7 + 1
            return
        if name in ("LEFT", "RIGHT"):
            self.format_col = max(1, min(7, self.format_col
                                         + (-1 if name == "LEFT" else 1)))
            return
        if not rows:
            return
        item = rows[self.format_row]
        if self.editing:
            if name == "ENTER":
                self._set_format(item, self.format_col, self.edit_text)
                self.editing = False
                return
            if name == "ESC":
                self.editing = False
                return
            if name == "BACKSPACE":
                self.edit_text = self.edit_text[:-1]
                return
            text = character(key)
            if text:
                self.edit_text += text
            return
        if name == "ENTER":
            self.edit_text = self._format_value(item, self.format_col)
            self.editing = True
            return
        if name == "SPACE":
            if self.format_col == 2:
                index = (JUSTIFICATIONS.index(item.justification)
                         if item.justification in JUSTIFICATIONS else 0)
                item.justification = JUSTIFICATIONS[
                    (index + 1) % len(JUSTIFICATIONS)]
            elif self.format_col == 6:
                item.delete_line_if_empty = not item.delete_line_if_empty

    def _format_value(self, item: LabelField, column: int) -> str:
        return {1: item.source, 2: item.justification, 3: str(item.length),
                4: item.format,
                5: "" if item.decimals is None else str(item.decimals),
                6: _yes(item.delete_line_if_empty), 7: item.source}.get(column, "")

    def _set_format(self, item: LabelField, column: int, value: str) -> None:
        if column == 2:
            if value.strip() in JUSTIFICATIONS:
                item.justification = value.strip()
        elif column == 3:
            try:
                item.length = max(1, min(self.label.width - item.col + 1,
                                         int(value)))
            except (ValueError, AttributeError):
                pass
        elif column == 4:
            item.format = value.strip()
        elif column == 5:
            try:
                item.decimals = max(0, min(14, int(value)))
            except ValueError:
                item.decimals = None
        elif column == 6:
            item.delete_line_if_empty = value.strip().upper().startswith("Y")

    # -- salvataggio -----------------------------------------------------
    def _open_save(self) -> None:
        self.picker = Picker(
            "Save", ["Save", "Save and preview", "Save and continue editing",
                     "Save as a new letter"],
            values=["save", "preview", "continue", "as"],
            footer="ENTER select   ESC cancel")
        self.picker_kind = "save"

    def _save_action(self, action: str) -> None:
        if action == "as":
            self.stage = "borrow_letter"
            self.letter_text = ""
            return
        if self.save():
            if action == "preview":
                self.preview_request = True
                self.close = True
            elif action == "continue":
                self.stage = "layout"
            else:
                self.close = True

    def _handle_borrow_letter(self, key: Key) -> None:
        if key.name == "ENTER":
            letter = self.letter_text.strip().upper()[:1]
            if letter not in LABEL_LETTERS:
                self.status = "Choose a label id A-Z."
                return
            if self.workspace.get_label(self.owner, letter) is not None:
                self.status = "That label id is already used."
                return
            self.label.letter = letter
            if self.save():
                self.close = True
            return
        if key.name == "ESC":
            self.close = True
            return
        text = character(key)
        if text and text.isalpha():
            self.letter_text = text.upper()

    def save(self) -> bool:
        if self.label is None:
            return False
        try:
            self.label.save()
        except LabelError as exc:
            self.status = str(exc)
            return False
        self.saved = True
        self.saved_label = self.label
        self.status = f"Label {self.label.letter} saved."
        return True

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        if self.stage in ("letter", "borrow_letter"):
            self._view_letter(buffer)
        elif self.stage == "params":
            self._view_params(buffer)
        elif self.stage == "formatting":
            self._view_formatting(buffer)
        elif self.stage in ("calc", "calc_name", "calc_expression"):
            self._view_calc(buffer)
        else:
            self._view_layout(buffer)
        view = View(buffer, [])
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        return view

    def _view_letter(self, buffer: CellBuffer) -> None:
        title_bar(buffer, "Create/Edit a Mail Label", self.theme)
        buffer.write(4, 2, "Label id (A-Z)", fg=self.theme.label,
                     bg=self.theme.bg)
        buffer.write(4, 20, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.fill_rect(4, 22, 1, 4, " ", fg=self.theme.selected_fg,
                         bg=self.theme.selected_bg)
        buffer.write(4, 22, self.letter_text or "_",
                     fg=self.theme.selected_fg, bg=self.theme.selected_bg,
                     underline=True)
        draw_status_line(buffer, self.theme,
                         self.status or "Type a label id and press ENTER")
        draw_help_line(buffer, self.theme, "ENTER accept   ESC cancel")

    def _view_params(self, buffer: CellBuffer) -> None:
        label = self.label
        assert label is not None
        title_bar(buffer, f"Label Parameters - {label.letter}", self.theme)
        for index, (_key, name, value, _kind) in enumerate(
                self._parameter_rows()):
            row = 3 + index
            selected = index == self.param_row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ", fg=fg, bg=bg)
            buffer.write(row, 2, clip_text(name, 50), fg=fg, bg=bg,
                         bold=selected)
            buffer.write(row, 54, ":", fg=fg, bg=bg)
            text = self.edit_text if selected and self.editing else value
            buffer.write(row, 56, clip_text(text, 30), fg=fg, bg=bg,
                         underline=selected and self.editing)
        draw_status_line(buffer, self.theme,
                         self.status or "F4 pre-defined sizes   F10 continue")
        draw_help_line(buffer, self.theme,
                       "ENTER edit/toggle   F4 sizes   F10 continue   ESC cancel")

    def _view_layout(self, buffer: CellBuffer) -> None:
        label = self.label
        assert label is not None
        title_bar(buffer, f"{self.title}   {label.width}x{label.height}",
                  self.theme)
        top = CONTENT_TOP
        buffer.box(top - 1, 0, label.height + 2, label.width + 2,
                   fg=self.theme.border, bg=self.theme.bg, double=True)
        for text in label.texts:
            buffer.write(top + text.row - 1, text.col,
                         clip_text(text.text, label.width - text.col + 1),
                         fg=self.theme.text, bg=self.theme.bg)
        for item in label.fields:
            width = max(1, item.length)
            placeholder = f"[{item.name or item.source}]"
            buffer.write(top + item.row - 1, item.col,
                         clip_text(placeholder, width), fg=self.theme.accent,
                         bg=self.theme.bg, underline=True)
        buffer.write(top + self.row - 1, self.col, "_",
                     fg=self.theme.selected_fg, bg=self.theme.selected_bg,
                     blink=True)
        draw_status_line(buffer, self.theme,
                         self.status or f"Row {self.row}  Col {self.col}  "
                                        f"{label.across} across")
        draw_help_line(buffer, self.theme,
                       "F2 fields   F4 calc   F5 delete   F7 params   "
                       "F9 line   F10 save   Alt-O format")
        draw_menu_line(buffer, self.theme, LABEL_KEYS)

    def _view_calc(self, buffer: CellBuffer) -> None:
        label = self.label
        assert label is not None
        title_bar(buffer, "Calculated Fields", self.theme)
        for index, calc in enumerate(label.calcs[:20]):
            row = 3 + index
            selected = index == self.calc_row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ", fg=fg, bg=bg)
            buffer.write(row, 3, calc.name, fg=fg, bg=bg, bold=selected)
            buffer.write(row, 15, clip_text(calc.expression, 90), fg=fg, bg=bg)
        if self.stage == "calc_name":
            buffer.write(3, 3, "Name:", fg=self.theme.label, bg=self.theme.bg)
            buffer.write(3, 11, self.edit_text, fg=self.theme.selected_fg,
                         bg=self.theme.selected_bg, underline=True)
        if self.stage == "calc_expression":
            buffer.write(3, 3, "Expression:", fg=self.theme.label,
                         bg=self.theme.bg)
            buffer.write(3, 17, clip_text(self.edit_text, 100),
                         fg=self.theme.selected_fg, bg=self.theme.selected_bg,
                         underline=True)
        draw_status_line(buffer, self.theme,
                         self.status or "F2 add   F5 delete   F10 continue")
        draw_help_line(buffer, self.theme,
                       "F2 add   F5 delete   F10 continue   ESC cancel")

    def _view_formatting(self, buffer: CellBuffer) -> None:
        label = self.label
        assert label is not None
        title_bar(buffer, "Formatting Options", self.theme)
        headers = ("Field", "Justification", "Len", "Fmt", "Dec", "DelLine")
        columns = (2, 26, 44, 50, 58, 64)
        for header, column in zip(headers, columns):
            buffer.write(2, column, header, fg=self.theme.text,
                         bg=self.theme.bg, bold=True)
        for index, item in enumerate(label.fields[:20]):
            row = 3 + index
            selected = index == self.format_row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ", fg=fg, bg=bg)
            values = (item.source, item.justification, str(item.length),
                      item.format,
                      "" if item.decimals is None else str(item.decimals),
                      _yes(item.delete_line_if_empty))
            for column, (value, x) in enumerate(zip(values, columns)):
                text = self.edit_text if selected and self.editing \
                    and column + 1 == self.format_col else value
                buffer.write(row, x, clip_text(text, 18), fg=fg, bg=bg,
                             underline=selected and self.editing
                             and column + 1 == self.format_col)
        draw_status_line(buffer, self.theme,
                         self.status or "SPACE changes justification/delete")
        draw_help_line(buffer, self.theme,
                       "UP/DOWN field   TAB column   ENTER edit   "
                       "F10 back")

    def run(self):
        if self.label is None:
            return None
        return render_labels(self.label, self.workspace)


def _yes(value: bool) -> str:
    return "Yes" if value else "No"


__all__ = ["LabelDesigner"]
