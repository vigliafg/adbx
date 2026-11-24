"""Indexes/ranges: finestre di creazione indice e di Range Settings."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW, Cell, CellBuffer
from ..data import indexing
from ..data.expressions import Context, ExprError, evaluate
from ..data.workspace import Database, WorkspaceError
from ..screen.keys import Key, character
from .dialogs import Picker, picker_view
from .theme import NEWPORT, Theme
from .widgets import (
    Region,
    View,
    clip_text,
    visible_rows,
    draw_help_line,
    draw_menu_line,
    draw_status_line,
    title_bar,
)

INDEX_KEYS = [("F1", "Help"), ("F2", "Fields"), ("F5", "Delete level"),
              ("F6", "Insert level"), ("F10", "Continue"), ("ESC", "Cancel")]
OPTIONS_KEYS = [("F1", "Help"), ("F10", "Save"), ("ESC", "Back")]
RANGE_KEYS = [("F1", "Help"), ("F2", "Index"), ("F3", "Key values"),
              ("F7", "Retrieve"), ("F10", "Continue"), ("Alt-E", "Exit")]

TABLE_TOP = 5
LEVEL_COL = 2
FIELD_COL = 12
DIRECTION_COL = 40
OPTIONS_TOP = 6
OPTION_LABEL_COL = 2
OPTION_VALUE_COL = 26


@dataclass
class IndexSession:
    database: Database
    name: str
    theme: Theme = NEWPORT
    mode: str = "table"
    existing: indexing.IndexDefinition | None = None
    stage: str = "table"
    levels: list[tuple[str, str]] = field(default_factory=list)
    expression: str = ""
    description: str = ""
    filter: str = ""
    allow: str = indexing.ALLOW_ALL
    case_sensitive: bool = False
    row: int = 0
    column: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    picker: Picker | None = None
    picker_kind: str = ""
    status: str = ""
    close: bool = False
    saved: indexing.IndexDefinition | None = None
    help_topic: str = "indexes"

    def __post_init__(self) -> None:
        self.name = self.name.upper()
        if self.existing is not None:
            definition = self.existing
            self.expression = definition.expression
            self.description = definition.description
            self.filter = definition.filter
            self.allow = definition.allow
            self.case_sensitive = definition.case_sensitive
            if definition.levels:
                self.levels = list(definition.levels)
                self.mode = "table"
                self.stage = "table"
            else:
                self.levels = []
                self.mode = "expression"
                self.stage = "expression"
        if not self.expression and not self.levels:
            self.levels = [("", "A")]
        if self.mode == "expression":
            self.stage = "expression"
        elif self.stage == "expression":
            self.stage = "expression"
        else:
            self.stage = "table"
        if self.stage == "table" and not self.levels:
            self.levels = [("", "A")]
        self._load_cell()

    # -- celle della tabella --------------------------------------------
    @property
    def title(self) -> str:
        return "Create an Index" if self.existing is None else "Index Options"

    def _load_cell(self) -> None:
        if self.levels:
            self.row = max(0, min(self.row, len(self.levels) - 1))
            self.column = max(0, min(self.column, 1))
            if self.column == 0:
                self.edit_text = self.levels[self.row][0]
            else:
                self.edit_text = self.levels[self.row][1]
        else:
            self.edit_text = ""
        self.edit_cursor = len(self.edit_text)

    def _commit_cell(self) -> None:
        if not self.levels:
            return
        name, direction = self.levels[self.row]
        if self.column == 0:
            name = self.edit_text.strip().upper()
        else:
            direction = self.edit_text.upper()[:1] or "A"
        self.levels[self.row] = (name, direction)
        if self.column == 0:
            self.edit_text = name
        else:
            self.edit_text = direction

    def _build_expression(self) -> str:
        return "+".join(name for name, _direction in self.levels if name)

    # -- transizioni -----------------------------------------------------
    def _to_options(self) -> None:
        self._commit_cell()
        if not any(name for name, _direction in self.levels):
            self.status = "Enter at least one field."
            return
        if not self.expression:
            self.expression = self._build_expression()
        self.stage = "options"
        self.row = 0
        self.column = 0
        self.edit_text = self.expression
        self.edit_cursor = len(self.edit_text)

    def _option_rows(self) -> list[str]:
        return ["Index expression", "Description", "Filter expression",
                "Allow", "Case sensitive"]

    def _option_text(self, row: int) -> str:
        return [self.expression, self.description, self.filter,
                {indexing.ALLOW_ALL: "All",
                 indexing.ALLOW_UNIQUE: "Unique",
                 indexing.ALLOW_EXCEPTIONS: "Unique with exceptions"}
                .get(self.allow, self.allow),
                "Yes" if self.case_sensitive else "No"][row]

    def _set_option_text(self, row: int, text: str) -> None:
        if row == 0:
            self.expression = text
        elif row == 1:
            self.description = text
        elif row == 2:
            self.filter = text

    def _load_option(self) -> None:
        self.row = max(0, min(self.row, 4))
        self.edit_text = self._option_text(self.row)
        self.edit_cursor = len(self.edit_text)

    def _cycle_option(self, delta: int = 1) -> None:
        if self.row == 3:
            modes = list(indexing.ALLOW_MODES)
            index = modes.index(self.allow) if self.allow in modes else 0
            self.allow = modes[(index + delta) % len(modes)]
        elif self.row == 4:
            self.case_sensitive = not self.case_sensitive
        self._load_option()

    def _validate(self) -> bool:
        expression = self.expression.strip()
        if not expression:
            self.status = "Enter an index expression."
            return False
        if self.filter.strip():
            try:
                evaluate(self.filter, self._sample_context())
            except ExprError as exc:
                self.status = f"Filter: {exc}"
                return False
        try:
            key = indexing.index_key(
                self.database,
                indexing.IndexDefinition(self.name, expression),
                self._sample_values())
        except indexing.IndexError_ as exc:
            self.status = str(exc)
            return False
        if len(key) > indexing.MAX_KEY_LENGTH:
            self.status = ("The index key is longer than "
                           f"{indexing.MAX_KEY_LENGTH} characters.")
            return False
        return True

    def _sample_values(self) -> dict[str, str]:
        first = self.database.sequences()
        return (self.database.read(first[0]) if first
                else {field.name: "" for field in self.database.fields})

    def _sample_context(self) -> Context:
        return Context(fields=self.database.fields, values=self._sample_values(),
                       pattern=self.database.workspace.pattern_mode)

    def save(self) -> bool:
        if not self._validate():
            return False
        definition = indexing.IndexDefinition(
            self.name, self.expression.strip(), self.description.strip(),
            self.filter.strip(), self.allow, self.case_sensitive, True,
            [(name, direction) for name, direction in self.levels if name])
        try:
            indexing.save_index(self.database, definition,
                                replace=self.existing is not None)
            self.database.set_primary_index(definition.name)
        except (indexing.IndexError_, WorkspaceError) as exc:
            self.status = str(exc)
            return False
        self.saved = definition
        self.status = (f"Index {definition.name} created: "
                       f"{self.database.count()} records indexed.")
        self.close = True
        return True

    # -- tasti -----------------------------------------------------------
    def handle(self, key: Key) -> None:
        self.status = ""
        if self.picker is not None:
            self._handle_picker(key)
            return
        if key.alt and key.name == "E":
            self.close = True
            return
        if key.name == "F1":
            return
        if self.stage == "table":
            self._handle_table(key)
        else:
            self._handle_options(key)

    def _handle_table(self, key: Key) -> None:
        name = key.name
        if name == "F2":
            self._open_field_picker()
            return
        if name == "F5":
            self._delete_row()
            return
        if name == "F6":
            self._insert_row()
            return
        if name == "F10":
            self._to_options()
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN"):
            self._commit_cell()
            self.row = max(0, min(len(self.levels) - 1,
                                  self.row + (-1 if name == "UP" else 1)))
            self._load_cell()
            return
        if name in ("TAB", "ENTER"):
            self._commit_cell()
            self.column = 0 if key.shift else (self.column + 1) % 2
            self._load_cell()
            return
        if name in ("LEFT", "RIGHT"):
            self.edit_cursor = max(0, min(len(self.edit_text),
                                          self.edit_cursor
                                          + (-1 if name == "LEFT" else 1)))
            return
        if name == "HOME":
            self.edit_cursor = 0
            return
        if name == "END":
            self.edit_cursor = len(self.edit_text)
            return
        if name == "BACKSPACE":
            if self.edit_cursor:
                self.edit_text = (self.edit_text[:self.edit_cursor - 1]
                                  + self.edit_text[self.edit_cursor:])
                self.edit_cursor -= 1
                self._commit_cell()
            return
        if name == "DELETE":
            self.edit_text = (self.edit_text[:self.edit_cursor]
                              + self.edit_text[self.edit_cursor + 1:])
            self._commit_cell()
            return
        if name == "SPACE" and self.column == 1:
            self._toggle_direction()
            return
        text = character(key)
        if not text:
            return
        if self.column == 1:
            text = text.upper()
            if text not in ("A", "D"):
                self.status = "Direction is A (ascending) or D (descending)."
                return
            self.edit_text = text
            self.edit_cursor = 1
            self._commit_cell()
            return
        if text.isalpha() and not key.shift:
            text = text.upper()
        if self.edit_cursor >= len(self.edit_text):
            self.edit_text += text
        else:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor + 1:])
        self.edit_cursor += len(text)
        self._commit_cell()

    def _toggle_direction(self) -> None:
        name, direction = self.levels[self.row]
        self.levels[self.row] = (name, "D" if direction == "A" else "A")
        self._load_cell()

    def _insert_row(self) -> None:
        self._commit_cell()
        self.levels.insert(self.row + 1, ("", "A"))
        self.row += 1
        self.column = 0
        self._load_cell()

    def _delete_row(self) -> None:
        self._commit_cell()
        if len(self.levels) == 1:
            self.levels = [("", "A")]
        else:
            del self.levels[self.row]
            self.row = min(self.row, len(self.levels) - 1)
        self.column = 0
        self._load_cell()

    def _handle_options(self, key: Key) -> None:
        name = key.name
        if name == "F10":
            self.save()
            return
        if name == "ESC":
            if self.mode == "table":
                self.stage = "table"
                self.row = 0
                self._load_cell()
            else:
                self.close = True
            return
        if name in ("UP", "DOWN"):
            self._save_option_text()
            delta = -1 if name == "UP" else 1
            self.row = max(0, min(4, self.row + delta))
            self._load_option()
            return
        if name in ("TAB", "ENTER"):
            if self.row in (3, 4):
                self._cycle_option(-1 if key.shift else 1)
                return
            self._save_option_text()
            self.row = (self.row + (-1 if key.shift else 1)) % 5
            self._load_option()
            return
        if self.row in (3, 4):
            if name in ("SPACE", "LEFT", "RIGHT"):
                self._cycle_option(-1 if name == "LEFT" else 1)
            return
        if name in ("LEFT", "RIGHT"):
            self.edit_cursor = max(0, min(len(self.edit_text),
                                          self.edit_cursor
                                          + (-1 if name == "LEFT" else 1)))
            return
        if name == "HOME":
            self.edit_cursor = 0
            return
        if name == "END":
            self.edit_cursor = len(self.edit_text)
            return
        if name == "BACKSPACE":
            if self.edit_cursor:
                self.edit_text = (self.edit_text[:self.edit_cursor - 1]
                                  + self.edit_text[self.edit_cursor:])
                self.edit_cursor -= 1
                self._save_option_text()
            return
        if name == "DELETE":
            self.edit_text = (self.edit_text[:self.edit_cursor]
                              + self.edit_text[self.edit_cursor + 1:])
            self._save_option_text()
            return
        text = character(key)
        if not text:
            return
        if text.isalpha() and not key.shift:
            text = text.lower()
        if self.edit_cursor >= len(self.edit_text):
            self.edit_text += text
        else:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor + 1:])
        self.edit_cursor += len(text)
        self._save_option_text()

    def _save_option_text(self) -> None:
        if self.row in (0, 1, 2):
            self._set_option_text(self.row, self.edit_text)

    # -- picker ----------------------------------------------------------
    def _open_field_picker(self) -> None:
        names = [field.name for field in self.database.fields]
        self.picker = Picker("Fieldnames", names, purpose="field",
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "field"
        self.picker.selected = next(
            (index for index, name in enumerate(names)
             if name == self.levels[self.row][0]), 0)

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
        elif key.name == "ENTER":
            value = picker.value()
            self.picker = None
            if not value:
                return
            if self.picker_kind == "field":
                self.levels[self.row] = (value.upper(),
                                         self.levels[self.row][1])
                self.column = 0
                self._load_cell()
        elif key.name == "ESC":
            self.picker = None

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, f"{self.title} - {self.name}", self.theme)
        regions: list[Region] = []
        if self.stage == "table":
            regions = self._view_table(buffer)
        else:
            regions = self._view_options(buffer)
        view = View(buffer, regions)
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        return view

    def _view_table(self, buffer: CellBuffer) -> list[Region]:
        buffer.write(2, 2, "Database", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(2, 12, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(2, 14, self.database.name, fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        buffer.write(3, 2, "Index", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(3, 12, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(3, 14, self.name, fg=self.theme.text, bg=self.theme.bg)
        buffer.write(4, LEVEL_COL, "Level", fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        buffer.write(4, FIELD_COL, "Field", fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        buffer.write(4, DIRECTION_COL, "Direction", fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        regions: list[Region] = []
        for offset, (name, direction) in enumerate(self.levels[:visible_rows(TABLE_TOP)]):
            row = TABLE_TOP + offset
            active = offset == self.row
            fg = self.theme.selected_fg if active else self.theme.text
            bg = self.theme.selected_bg if active else self.theme.bg
            if active:
                buffer.fill_rect(row, 1, 1, 66, " ", fg=fg, bg=bg)
            buffer.write(row, LEVEL_COL, str(offset + 1), fg=fg, bg=bg)
            field_text = name
            if active and self.column == 0:
                field_text = self.edit_text
            buffer.write(row, FIELD_COL, clip_text(field_text, 22), fg=fg, bg=bg,
                         underline=active and self.column == 0)
            direction_text = ("Ascending" if direction == "A" else "Descending")
            if active and self.column == 1:
                direction_text = ("Ascending" if self.edit_text.upper() == "A"
                                  else "Descending")
            buffer.write(row, DIRECTION_COL, direction_text, fg=fg, bg=bg,
                         underline=active and self.column == 1)
            regions.append(Region(row, LEVEL_COL, 1, 60, f"idx:cell:{offset}"))
        draw_status_line(buffer, self.theme,
                         self.status or f"Level {self.row + 1} of "
                                        f"{len(self.levels)}")
        draw_help_line(buffer, self.theme,
                       "F2 choose field   F5/F6 delete/insert level   "
                       "F10 continue   ESC cancel")
        regions.extend(draw_menu_line(buffer, self.theme, INDEX_KEYS))
        return regions

    def _view_options(self, buffer: CellBuffer) -> list[Region]:
        buffer.write(2, 2, "Database", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(2, 12, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(2, 14, self.database.name, fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        buffer.write(3, 2, "Index file", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(3, 12, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(3, 14, self.name, fg=self.theme.text, bg=self.theme.bg)
        regions: list[Region] = []
        for index, label in enumerate(self._option_rows()):
            row = OPTIONS_TOP + index
            active = index == self.row
            fg = self.theme.selected_fg if active else self.theme.text
            bg = self.theme.selected_bg if active else self.theme.bg
            if active:
                buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            buffer.write(row, OPTION_LABEL_COL, label, fg=fg, bg=bg)
            buffer.write(row, OPTION_VALUE_COL, ":", fg=fg, bg=bg)
            text = self.edit_text if active else self._option_text(index)
            if active and index in (0, 1, 2):
                text = self.edit_text
            width = SCREEN_WIDTH - OPTION_VALUE_COL - 4
            if active and index in (0, 1, 2):
                visible = text[-width:] if len(text) > width else text
                buffer.write(row, OPTION_VALUE_COL + 2,
                             clip_text(visible, width), fg=fg, bg=bg,
                             underline=True)
            else:
                buffer.write(row, OPTION_VALUE_COL + 2,
                             clip_text(text, width), fg=fg, bg=bg,
                             bold=active)
            regions.append(Region(row, OPTION_LABEL_COL, 1,
                                  SCREEN_WIDTH - 4, f"idx:option:{index}"))
        draw_status_line(buffer, self.theme,
                         self.status or "TAB next field   ENTER change option")
        draw_help_line(buffer, self.theme,
                       "F10 create index   ESC back")
        regions.extend(draw_menu_line(buffer, self.theme, OPTIONS_KEYS))
        return regions


RANGE_ROWS = ("Primary index", "Order", "Show", "First record", "Last record",
              "Unique keys", "Filter", "Filter status")


@dataclass
class RangeSession:
    database: Database
    theme: Theme = NEWPORT
    settings: indexing.RangeSettings = field(
        default_factory=indexing.RangeSettings)
    stage: str = "settings"
    row: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    picker: Picker | None = None
    picker_kind: str = ""
    save_choice: int = 0
    save_letter: str = "A"
    save_description: str = ""
    save_row: int = 0
    temporary: bool = False
    status: str = ""
    close: bool = False
    applied: bool = False
    help_topic: str = "ranges"

    def __post_init__(self) -> None:
        self.settings = self.settings.copy()
        self._load_row()

    # -- valori delle righe ---------------------------------------------
    def _row_text(self, row: int) -> str:
        settings = self.settings
        if row == 0:
            return self._primary_text()
        if row == 1:
            return ("Ascending" if settings.order == indexing.ORDER_ASCENDING
                    else "Descending")
        if row == 2:
            return {indexing.SHOW_ALL: "All",
                    indexing.SHOW_DELETED: "Deleted",
                    indexing.SHOW_NOT_DELETED: "Not deleted"
                    }.get(settings.show, settings.show)
        if row == 3:
            return settings.first_key or "<First>"
        if row == 4:
            return settings.last_key or "<Last>"
        if row == 5:
            return "Yes" if settings.unique_keys else "No"
        if row == 6:
            return settings.filter
        return "Active" if settings.filter_active else "Inactive"

    def _primary_text(self) -> str:
        primary = self.settings.primary
        if primary.startswith(indexing.SEARCH_PREFIX):
            search = indexing.get_search_list(
                self.database, self.settings.search_id)
            return f"Search/Sort: {search.label}" if search else "Search/Sort"
        if primary in (indexing.RECORD_NUMBER, indexing.SEARCH_LIST):
            return "Record Number"
        definition = indexing.find_index(self.database, primary)
        return definition.label if definition else primary

    def _load_row(self) -> None:
        self.row = max(0, min(self.row, len(RANGE_ROWS) - 1))
        if self.row in (3, 4, 6):
            self.edit_text = self._row_text(self.row)
            self.edit_cursor = len(self.edit_text)
        else:
            self.edit_text = ""
            self.edit_cursor = 0

    def _commit_row(self) -> None:
        if self.row in (3, 4):
            key = self.edit_text.strip()
            if key in ("<First>", "<Last>"):
                key = ""
            if self.row == 3:
                self.settings.first_key = key
            else:
                self.settings.last_key = key
        elif self.row == 6:
            self.settings.filter = self.edit_text

    def _cycle(self, delta: int) -> None:
        if self.row == 1:
            self.settings.order = (
                indexing.ORDER_DESCENDING
                if self.settings.order == indexing.ORDER_ASCENDING
                else indexing.ORDER_ASCENDING)
        elif self.row == 2:
            modes = list(indexing.SHOW_MODES)
            index = modes.index(self.settings.show)
            self.settings.show = modes[(index + delta) % len(modes)]
        elif self.row == 5:
            self.settings.unique_keys = not self.settings.unique_keys
        elif self.row == 7:
            self.settings.filter_active = not self.settings.filter_active
        self._load_row()

    # -- picker ----------------------------------------------------------
    def _open_primary_picker(self) -> None:
        items = ["Record Number"]
        values = [indexing.RECORD_NUMBER]
        markers = [""]
        for definition in indexing.indexes(self.database, attached=True):
            marker = "\u25b8 " if definition.name == self.settings.primary else ""
            markers.append(marker)
            items.append(definition.label)
            values.append(definition.name)
        history = indexing.search_history(self.database, limit=1)
        if history:
            search = history[0]
            stale = "\u2666 " if search.out_of_date(self.database) else ""
            markers.append(stale)
            items.append(f"Search/Sort: {search.label}")
            values.append(f"{indexing.SEARCH_PREFIX}{search.id}")
        self.picker = Picker("Primary index", items, values, purpose="primary",
                             markers=markers)
        self.picker_kind = "primary"

    def _open_key_picker(self) -> None:
        definition = None
        if self.settings.primary not in (indexing.RECORD_NUMBER,
                                         indexing.SEARCH_LIST) \
                and not self.settings.primary.startswith(indexing.SEARCH_PREFIX):
            definition = indexing.find_index(self.database, self.settings.primary)
        if definition is None:
            self.status = "Select an index before choosing key values."
            return
        values = [key.rstrip() for key in
                  indexing.key_values(self.database, definition)]
        values.insert(0, "<Last>")
        self.picker = Picker("Key Values", values, purpose="key",
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "key"

    def _open_retrieve_picker(self) -> None:
        items = ["Default Range"]
        values = ["DEFAULT"]
        for letter, description, _settings in indexing.saved_ranges(self.database):
            items.append(f"{letter} - {description or 'Range ' + letter}")
            values.append(letter)
        self.picker = Picker("Retrieve a Range", items, values,
                             purpose="retrieve",
                             footer="ENTER retrieve   ESC cancel")
        self.picker_kind = "retrieve"

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
        elif key.name == "ENTER":
            value = picker.value()
            kind = self.picker_kind
            self.picker = None
            if kind == "primary" and value:
                self.settings.primary = value
            elif kind == "key" and value:
                if self.row == 3:
                    self.settings.first_key = value
                elif self.row == 4:
                    self.settings.last_key = value
                else:
                    self.row = 3
                    self.settings.first_key = value
            elif kind == "retrieve":
                if value == "DEFAULT":
                    self.settings = indexing.default_range()
                else:
                    found = indexing.get_range(self.database, value)
                    if found is not None:
                        self.settings = found[1].copy()
                self.row = 0
                self.status = "Range retrieved."
            self._load_row()
        elif key.name == "ESC":
            self.picker = None

    # -- tasti -----------------------------------------------------------
    def handle(self, key: Key) -> None:
        self.status = ""
        if self.picker is not None:
            self._handle_picker(key)
            return
        if key.alt and key.name == "E":
            self._apply()
            return
        if key.name == "F1":
            return
        if self.stage == "savebox":
            self._handle_savebox(key)
            return
        if self.stage == "savefields":
            self._handle_savefields(key)
            return
        name = key.name
        if name == "F2":
            self._open_primary_picker()
            return
        if name == "F3":
            self._open_key_picker()
            return
        if name == "F7":
            self._open_retrieve_picker()
            return
        if name == "F10":
            self._commit_row()
            if self.temporary:
                self._apply(save=False)
            else:
                self.stage = "savebox"
                self.save_choice = 0
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN"):
            self._commit_row()
            self.row = max(0, min(len(RANGE_ROWS) - 1,
                                  self.row + (-1 if name == "UP" else 1)))
            self._load_row()
            return
        if name in ("TAB", "ENTER"):
            self._commit_row()
            if self.row in (1, 2, 5, 7):
                self._cycle(-1 if key.shift else 1)
                return
            if self.row == 0:
                self._open_primary_picker()
                return
            self.row = (self.row + (-1 if key.shift else 1)) % len(RANGE_ROWS)
            self._load_row()
            return
        if name in ("LEFT", "RIGHT", "SPACE") and self.row in (1, 2, 5, 7):
            self._cycle(-1 if name == "LEFT" else 1)
            return
        if self.row in (3, 4, 6):
            if name in ("LEFT", "RIGHT"):
                self.edit_cursor = max(0, min(
                    len(self.edit_text), self.edit_cursor
                    + (-1 if name == "LEFT" else 1)))
                return
            if name == "HOME":
                self.edit_cursor = 0
                return
            if name == "END":
                self.edit_cursor = len(self.edit_text)
                return
            if name == "BACKSPACE":
                if self.edit_cursor:
                    self.edit_text = (self.edit_text[:self.edit_cursor - 1]
                                      + self.edit_text[self.edit_cursor:])
                    self.edit_cursor -= 1
                    self._commit_row()
                return
            if name == "DELETE":
                self.edit_text = (self.edit_text[:self.edit_cursor]
                                  + self.edit_text[self.edit_cursor + 1:])
                self._commit_row()
                return
            text = character(key)
            if text:
                if text.isalpha() and not key.shift:
                    text = text.lower()
                if self.edit_cursor >= len(self.edit_text):
                    self.edit_text += text
                else:
                    self.edit_text = (self.edit_text[:self.edit_cursor] + text
                                      + self.edit_text[self.edit_cursor + 1:])
                self.edit_cursor += len(text)
                self._commit_row()

    def _apply(self, *, save: bool = False) -> None:
        if not self.temporary:
            self.database.save_current_range(self.settings)
        self.applied = True
        self.close = True
        self.status = "Range applied."

    def _handle_savebox(self, key: Key) -> None:
        if key.name in ("UP", "DOWN"):
            self.save_choice = 1 - self.save_choice
        elif key.name == "ENTER":
            if self.save_choice == 0:
                self.stage = "savefields"
                self.save_row = 0
            else:
                self._apply()
        elif key.name == "ESC":
            self.stage = "settings"

    def _handle_savefields(self, key: Key) -> None:
        if key.name == "F10":
            letter = self.save_letter.strip().upper()[:1]
            if not letter.isalpha():
                self.status = "Choose a range letter A-Z."
                return
            indexing.save_range(self.database, letter,
                                self.save_description.strip(), self.settings)
            self._apply()
            return
        if key.name in ("UP", "DOWN"):
            self.save_row = 1 - self.save_row
            return
        if key.name == "ESC":
            self.stage = "savebox"
            return
        if self.save_row == 0:
            text = character(key)
            if text and text.isalpha():
                self.save_letter = text.upper()
            elif key.name == "BACKSPACE":
                self.save_letter = ""
            return
        if key.name == "BACKSPACE":
            self.save_description = self.save_description[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self.save_description += text

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, f"Range Settings - {self.database.name}", self.theme)
        regions: list[Region] = []
        if self.stage in ("savebox", "savefields"):
            regions = self._view_settings(buffer)
            regions.extend(self._view_save(buffer))
        else:
            regions = self._view_settings(buffer)
        view = View(buffer, regions)
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        return view

    def _view_settings(self, buffer: CellBuffer) -> list[Region]:
        regions: list[Region] = []
        for index, label in enumerate(RANGE_ROWS):
            row = 4 + index
            active = index == self.row and self.stage == "settings"
            fg = self.theme.selected_fg if active else self.theme.text
            bg = self.theme.selected_bg if active else self.theme.bg
            if active:
                buffer.fill_rect(row, 1, 1, 72, " ", fg=fg, bg=bg)
            buffer.write(row, 3, label, fg=fg, bg=bg, bold=active)
            buffer.write(row, 22, ":", fg=fg, bg=bg)
            text = self.edit_text if active and index in (3, 4, 6) \
                else self._row_text(index)
            width = 52
            if active and index in (3, 4, 6):
                visible = text[-width:] if len(text) > width else text
                buffer.write(row, 24, clip_text(visible, width), fg=fg, bg=bg,
                             underline=True)
            else:
                buffer.write(row, 24, clip_text(text, width), fg=fg, bg=bg,
                             bold=active)
            regions.append(Region(row, 3, 1, 70, f"range:row:{index}"))
        draw_status_line(buffer, self.theme,
                         self.status or "UP/DOWN move   TAB change   F10 continue")
        draw_help_line(buffer, self.theme,
                       "F2 index   F3 key values   F7 retrieve   "
                       "F10 continue   Alt-E exit")
        regions.extend(draw_menu_line(buffer, self.theme, RANGE_KEYS))
        return regions

    def _view_save(self, buffer: CellBuffer) -> list[Region]:
        from .widgets import window
        if self.stage == "savebox":
            width, height = 34, 7
            panel = window(width, height, "Save", self.theme)
            for index, label in enumerate(("Save range", "Exit")):
                selected = index == self.save_choice
                fg = self.theme.selected_fg if selected else self.theme.window_fg
                bg = self.theme.selected_bg if selected else self.theme.window_bg
                if selected:
                    panel.fill_rect(2 + index, 1, 1, width - 2, " ", fg=fg, bg=bg)
                panel.write(2 + index, 2, label, fg=fg, bg=bg)
            row = max(1, (STATUS_ROW - height) // 2)
            col = max(1, (SCREEN_WIDTH - width) // 2)
            return [Region(row, col, height, width, "range:savebox")]
        width, height = 56, 8
        panel = window(width, height, "Save Range", self.theme)
        panel.write(2, 2, "Letter", fg=self.theme.label, bg=self.theme.window_bg)
        panel.write(2, 12, ":", fg=self.theme.label, bg=self.theme.window_bg)
        panel.write(2, 14, self.save_letter or "_", fg=self.theme.window_fg,
                    bg=self.theme.window_bg, underline=self.save_row == 0)
        panel.write(3, 2, "Description", fg=self.theme.label,
                    bg=self.theme.window_bg)
        panel.write(3, 12, ":", fg=self.theme.label, bg=self.theme.window_bg)
        panel.write(3, 14, clip_text(self.save_description, width - 18),
                    fg=self.theme.window_fg, bg=self.theme.window_bg,
                    underline=self.save_row == 1)
        panel.write(height - 2, 2, "F10 save   ESC back", fg=self.theme.muted,
                    bg=self.theme.window_bg)
        row = max(1, (STATUS_ROW - height) // 2)
        col = max(1, (SCREEN_WIDTH - width) // 2)
        return [Region(row, col, height, width, "range:savefields")]


__all__ = ["IndexSession", "RANGE_ROWS", "RangeSession"]
