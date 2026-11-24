"""Search/sort lists: criteri in Table/Expression mode, sort e history."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW, Cell, CellBuffer
from ..data import indexing
from ..data.expressions import SearchRow, search_rows_expression
from ..data.workspace import Database, WorkspaceError
from ..screen.keys import Key, character
from . import screens
from .dialogs import Picker, picker_view
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

# Compatte per stare in 80 colonne.
SEARCH_KEYS = [("F1", "Help"), ("F2", "Fields"), ("F3", "Ops"),
               ("F4", "Sort"), ("F5", "Del"), ("F6", "Ins"),
               ("F8", "Desc"), ("F9", "Expr"), ("F10", "Go")]
SORT_KEYS = [("F1", "Help"), ("F2", "Fields"), ("F4", "Search"),
             ("F5", "Delete row"), ("F6", "Insert row"), ("F10", "Continue")]
EXPRESSION_KEYS = [("F1", "Help"), ("F9", "Table mode"),
                   ("F10", "Continue")]

SEARCH_TOP = 5
COL_FIELD = 2
COL_OPERATOR = 24
COL_VALUE = 30
COL_CONNECTOR = 58
OPERATORS = ["=", ">", "<", ">=", "<=", "<>", "?", "*A", "*F", "*L", "*W"]
SORT_TOP = 5
SORT_FIELD_COL = 12
SORT_DIRECTION_COL = 40


@dataclass
class SearchSession:
    database: Database
    theme: Theme = NEWPORT
    letter: str | None = None
    existing: indexing.SavedSearch | None = None
    mode: str = "table"
    stage: str = "search"
    rows: list[SearchRow] = field(default_factory=list)
    row: int = 0
    column: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    sort_rows: list[tuple[str, str]] = field(default_factory=list)
    sort_row: int = 0
    sort_column: int = 0
    expression: str = ""
    sort_expression: str = ""
    description: str = ""
    show: str = indexing.SHOW_NOT_DELETED
    case_sensitive: bool = False
    range_settings: indexing.RangeSettings | None = None
    range_ready: bool = False
    request_range: bool = False
    picker: Picker | None = None
    picker_kind: str = ""
    description_text: str = ""
    run_choice: int = 0
    status: str = ""
    close: bool = False
    result: indexing.SearchList | None = None
    help_topic: str = "search"

    def __post_init__(self) -> None:
        if self.range_settings is None:
            self.range_settings = self.database.current_range.copy()
        if self.existing is not None:
            saved = self.existing
            self.letter = saved.letter
            self.mode = saved.mode
            self.rows = [row for row in saved.search_rows] or [SearchRow()]
            self.expression = saved.search_expression
            self.sort_rows = list(saved.sort_rows)
            self.sort_expression = saved.sort_expression
            self.description = saved.description
            self.show = saved.show
            self.case_sensitive = saved.case_sensitive
            self.stage = "expression" if saved.mode == "expression" else "search"
        if not self.rows:
            self.rows = [SearchRow()]
        self._load_cell()

    # -- celle -----------------------------------------------------------
    @property
    def title(self) -> str:
        kind = "Search" if self.stage in ("search", "expression") else "Sort"
        return f"{kind} {'Table' if self.mode == 'table' else 'Expression'}"

    def _load_cell(self) -> None:
        if self.stage in ("search",) and self.mode == "table":
            if self.rows:
                self.row = max(0, min(self.row, len(self.rows) - 1))
                self.column = max(0, min(self.column, 3))
                self.edit_text = self._cell_text(self.rows[self.row], self.column)
            else:
                self.edit_text = ""
        elif self.stage == "sort":
            self.edit_text = self._sort_text()
        elif self.stage == "expression":
            self.edit_text = ""
        self.edit_cursor = len(self.edit_text)

    def _cell_text(self, row: SearchRow, column: int) -> str:
        return (row.field, row.operator, row.value, row.connector)[column]

    def _sort_text(self) -> str:
        if 0 <= self.sort_row < len(self.sort_rows):
            name, direction = self.sort_rows[self.sort_row]
            return name if self.sort_column == 0 else direction
        return ""

    def _commit_cell(self) -> None:
        if self.stage == "search" and self.mode == "table" and self.rows:
            row = self.rows[self.row]
            text = self.edit_text
            if self.column == 0:
                row.field = text.strip().upper()
            elif self.column == 1:
                row.operator = text.strip() or "="
            elif self.column == 2:
                row.value = text
            else:
                connector = text.strip().upper()
                row.connector = "OR" if connector.startswith("O") else "AND"
        elif self.stage == "sort" and 0 <= self.sort_row < len(self.sort_rows):
            name, direction = self.sort_rows[self.sort_row]
            if self.sort_column == 0:
                name = self.edit_text.strip().upper()
            else:
                direction = "D" if self.edit_text.upper().startswith("D") else "A"
            self.sort_rows[self.sort_row] = (name, direction)

    # -- criteri ---------------------------------------------------------
    def _effective_search_expression(self) -> str:
        if self.mode == "expression":
            return self.expression.strip()
        return search_rows_expression(self.rows)

    def _effective_sort_expression(self) -> str:
        if self.sort_expression.strip():
            return self.sort_expression.strip()
        return "+".join(name for name, _direction in self.sort_rows if name)

    def _use_last(self) -> None:
        history = indexing.search_history(self.database, limit=1)
        if not history:
            self.status = "There is no previous search/sort."
            return
        last = history[0]
        saved = (indexing.saved_search(self.database, last.letter)
                 if last.letter else None)
        self.rows = ([row for row in saved.search_rows] if saved else
                     [SearchRow()])
        if saved is None and last.search_expression:
            self.mode = "expression"
            self.expression = last.search_expression
            self.stage = "expression"
        self.sort_rows = list(last.sort_rows)
        self.sort_expression = last.sort_expression
        self.show = last.show
        self.case_sensitive = last.case_sensitive
        self.status = "Criteria from the last search/sort."

    def _to_expression(self) -> None:
        self._commit_cell()
        if not self.expression:
            self.expression = search_rows_expression(self.rows)
        self.mode = "expression"
        self.stage = "expression"
        self.row = 0
        self._load_cell()

    def _to_table(self) -> None:
        if not self.rows:
            self.rows = [SearchRow()]
        self.mode = "table"
        self.stage = "search"
        self.column = 0
        self._load_cell()

    def _continue(self) -> None:
        self._commit_cell()
        if not self.range_ready and not self._has_sort():
            self.request_range = True
            return
        self.stage = "runbox"
        self.run_choice = 0

    def _has_sort(self) -> bool:
        return bool(self.sort_expression.strip()
                    or any(name for name, _direction in self.sort_rows))

    def set_range(self, settings: indexing.RangeSettings) -> None:
        self.range_settings = settings.copy()
        self.range_ready = True
        self.request_range = False
        self._continue()

    def _run(self) -> bool:
        search_rows = [] if self.mode == "expression" else [
            row for row in self.rows if row.field.strip()]
        expression = (self.expression.strip()
                      if self.mode == "expression" else "")
        saved = None
        if self.letter:
            saved = indexing.SavedSearch(
                self.letter, self.description.strip(), self.mode,
                search_rows, expression, self.sort_rows,
                self.sort_expression.strip(), self.show, self.case_sensitive)
            indexing.save_saved_search(self.database, saved)
        try:
            self.result = indexing.run_search(
                self.database, search_rows=search_rows,
                search_expression=expression, sort_rows=self.sort_rows,
                sort_expression=self.sort_expression.strip(),
                show=self.show, case_sensitive=self.case_sensitive,
                range_settings=self.range_settings,
                letter=saved.letter if saved else None,
                def_version=saved.version if saved else 0,
                description=self.description.strip())
        except (indexing.IndexError_, WorkspaceError) as exc:
            self.status = str(exc)
            self.stage = "search" if self.mode == "table" else "expression"
            return False
        self.range_ready = False
        self.status = (f"{len(self.result.seqs)} record(s) in the "
                       "Search/Sort List.")
        self.close = True
        return True

    # -- picker ----------------------------------------------------------
    def _open_field_picker(self) -> None:
        names = [field.name for field in self.database.fields]
        if self.stage == "sort" and not self.sort_rows:
            self.sort_rows = [("", "A")]
            self.sort_row = 0
            self.sort_column = 0
        if self.stage == "search":
            names += ["*CHAR", "*NUM", "*DATE", "*LOGIC", "*MEMO"]
            current = self.rows[self.row].field if self.rows else ""
        else:
            current = (self.sort_rows[self.sort_row][0]
                       if 0 <= self.sort_row < len(self.sort_rows) else "")
        self.picker = Picker("Fieldnames", names, purpose="field",
                             footer="ENTER select   ESC cancel",
                             selected=names.index(current) if current in names else 0)
        self.picker_kind = "field"

    def _open_operator_picker(self) -> None:
        current = self.rows[self.row].operator if self.rows else "="
        self.picker = Picker("Operators", OPERATORS,
                             selected=(OPERATORS.index(current)
                                       if current in OPERATORS else 0),
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "operator"

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
            if not value:
                return
            if kind == "field":
                if self.stage == "search" and self.rows:
                    self.rows[self.row].field = value.upper()
                elif 0 <= self.sort_row < len(self.sort_rows):
                    self.sort_rows[self.sort_row] = (
                        value.upper(), self.sort_rows[self.sort_row][1])
                self._load_cell()
            elif kind == "operator" and self.rows:
                self.rows[self.row].operator = value
                self._load_cell()
        elif key.name == "ESC":
            self.picker = None

    # -- tasti -----------------------------------------------------------
    def handle(self, key: Key) -> None:
        self.status = ""
        self.request_range = False
        if self.picker is not None:
            self._handle_picker(key)
            return
        if key.name == "F1":
            return
        if self.stage == "runbox":
            self._handle_runbox(key)
            return
        if self.stage == "description":
            self._handle_description(key)
            return
        if self.stage == "expression":
            self._handle_expression(key)
            return
        if self.stage == "sort":
            self._handle_sort(key)
            return
        self._handle_search(key)

    def _handle_search(self, key: Key) -> None:
        name = key.name
        if name == "F2":
            self._open_field_picker()
            return
        if name == "F3":
            self._open_operator_picker()
            return
        if name == "F4":
            self._commit_cell()
            self.stage = "sort"
            self.sort_row = 0
            self.sort_column = 0
            self._load_cell()
            return
        if name == "F5":
            self._delete_row()
            return
        if name == "F6":
            self._insert_row()
            return
        if name == "F7":
            self._use_last()
            return
        if name == "F8":
            self.description_text = self.description
            self.stage = "description"
            return
        if name == "F9":
            self._to_expression()
            return
        if name == "F10":
            self._continue()
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN"):
            self._commit_cell()
            self.row = max(0, min(len(self.rows) - 1,
                                  self.row + (-1 if name == "UP" else 1)))
            self._load_cell()
            return
        if name in ("TAB", "ENTER"):
            self._commit_cell()
            self.column = (self.column + (-1 if key.shift else 1)) % 4
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
        text = character(key)
        if not text:
            return
        if text.isalpha() and not key.shift and self.column == 2:
            text = text.lower()
        if self.column in (0, 3):
            text = text.upper()
        if self.column == 3 and text not in ("A", "O"):
            return
        if self.edit_cursor >= len(self.edit_text):
            self.edit_text += text
        else:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor + 1:])
        self.edit_cursor += len(text)
        self._commit_cell()

    def _delete_row(self) -> None:
        self._commit_cell()
        if len(self.rows) == 1:
            self.rows = [SearchRow()]
        else:
            del self.rows[self.row]
            self.row = min(self.row, len(self.rows) - 1)
        self.column = 0
        self._load_cell()

    def _insert_row(self) -> None:
        self._commit_cell()
        self.rows.insert(self.row + 1, SearchRow())
        self.row += 1
        self.column = 0
        self._load_cell()

    def _handle_sort(self, key: Key) -> None:
        name = key.name
        if name == "F2":
            self._open_field_picker()
            return
        if name == "F4":
            self._commit_cell()
            self.stage = "search"
            self.column = 0
            self._load_cell()
            return
        if name == "F5":
            self._commit_cell()
            if self.sort_row < len(self.sort_rows):
                if len(self.sort_rows) == 1:
                    self.sort_rows = []
                else:
                    del self.sort_rows[self.sort_row]
                    self.sort_row = min(self.sort_row, len(self.sort_rows) - 1)
            self._load_cell()
            return
        if name == "F6":
            self._commit_cell()
            self.sort_rows.insert(self.sort_row + 1, ("", "A"))
            self.sort_row += 1
            self.sort_column = 0
            self._load_cell()
            return
        if name == "F10":
            self._continue()
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN"):
            self._commit_cell()
            self.sort_row = max(0, min(len(self.sort_rows) + 1,
                                       self.sort_row + (-1 if name == "UP" else 1)))
            self._load_cell()
            return
        if name == "TAB":
            self._commit_cell()
            if self.sort_row < len(self.sort_rows):
                self.sort_column = 1 - self.sort_column
            else:
                self.sort_row = min(len(self.sort_rows) + 1,
                                    self.sort_row + 1)
            self._load_cell()
            return
        if name == "ENTER":
            self._commit_cell()
            if self.sort_row < len(self.sort_rows):
                if self.sort_column == 1:
                    name_, direction = self.sort_rows[self.sort_row]
                    self.sort_rows[self.sort_row] = (
                        name_, "D" if direction == "A" else "A")
                    self._load_cell()
                else:
                    self.sort_column = 1
                    self._load_cell()
            elif self.sort_row == len(self.sort_rows):
                self.case_sensitive = not self.case_sensitive
            else:
                modes = list(indexing.SHOW_MODES)
                self.show = modes[(modes.index(self.show) + 1) % len(modes)]
            return
        if self.sort_row >= len(self.sort_rows):
            if name in ("LEFT", "RIGHT", "SPACE"):
                if self.sort_row == len(self.sort_rows):
                    self.case_sensitive = not self.case_sensitive
                else:
                    modes = list(indexing.SHOW_MODES)
                    self.show = modes[(modes.index(self.show) + 1) % len(modes)]
            return
        if name in ("LEFT", "RIGHT"):
            self.edit_cursor = max(0, min(len(self.edit_text),
                                          self.edit_cursor
                                          + (-1 if name == "LEFT" else 1)))
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
        text = character(key)
        if not text:
            return
        text = text.upper()
        if self.edit_cursor >= len(self.edit_text):
            self.edit_text += text
        else:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor + 1:])
        self.edit_cursor += len(text)
        self._commit_cell()

    def _handle_expression(self, key: Key) -> None:
        name = key.name
        if name == "F9":
            self._to_table()
            return
        if name == "F10":
            self._continue()
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN"):
            self.row = max(0, min(3, self.row + (-1 if name == "UP" else 1)))
            return
        if name == "ENTER":
            if self.row == 2:
                modes = list(indexing.SHOW_MODES)
                self.show = modes[(modes.index(self.show) + 1) % len(modes)]
            elif self.row == 3:
                self.case_sensitive = not self.case_sensitive
            return
        text = character(key)
        if text and text.isalpha() and not key.shift:
            text = text.lower()
        if self.row == 0:
            self.expression += text
        elif self.row == 1:
            self.sort_expression += text
        elif self.row == 2 and text.upper() in ("A", "D", "N"):
            modes = list(indexing.SHOW_MODES)
            self.show = modes[(modes.index(self.show) + 1) % len(modes)]
        elif self.row == 3 and text.upper() in ("Y", "N", "T", "F"):
            self.case_sensitive = text.upper() in ("Y", "T")
        if name == "BACKSPACE":
            if self.row == 0:
                self.expression = self.expression[:-1]
            elif self.row == 1:
                self.sort_expression = self.sort_expression[:-1]

    def _handle_description(self, key: Key) -> None:
        if key.name in ("ENTER", "F10"):
            self.description = self.description_text
            self.stage = "search" if self.mode == "table" else "expression"
            return
        if key.name == "ESC":
            self.stage = "search" if self.mode == "table" else "expression"
            return
        if key.name == "BACKSPACE":
            self.description_text = self.description_text[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self.description_text += text

    def _handle_runbox(self, key: Key) -> None:
        if key.name in ("UP", "DOWN"):
            self.run_choice = 1 - self.run_choice
        elif key.name == "ENTER":
            if self.run_choice == 0:
                self._run()
            else:
                self.close = True
        elif key.name == "ESC":
            self.stage = "search" if self.mode == "table" else "expression"

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        heading = {"search": "Search Table", "sort": "Sort Table",
                   "expression": "Search Expression",
                   "description": "Search/Sort Description",
                   "runbox": "Search/Sort Options"}[self.stage]
        title = heading
        if self.letter:
            title += f" - {self.letter}"
        title_bar(buffer, f"{title} - {self.database.name}", self.theme)
        regions: list[Region] = []
        if self.stage == "search" and self.mode == "table":
            regions = self._view_search(buffer)
        elif self.stage == "sort":
            regions = self._view_sort(buffer)
        elif self.stage == "description":
            regions = self._view_description(buffer)
        elif self.stage == "runbox":
            base = View(buffer, self._view_search(buffer)
                        if self.mode == "table" else self._view_expression(buffer))
            return self._runbox_view(base)
        else:
            regions = self._view_expression(buffer)
        view = View(buffer, regions)
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        return view

    def _view_search(self, buffer: CellBuffer) -> list[Region]:
        buffer.write(2, 2, "Search", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(2, 10, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(2, 12, self.description or "(no description)",
                     fg=self.theme.text, bg=self.theme.bg)
        buffer.write(4, COL_FIELD, "Field", fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        buffer.write(4, COL_OPERATOR, "Op.", fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        buffer.write(4, COL_VALUE, "Search for What?", fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        buffer.write(4, COL_CONNECTOR, "And/Or",
                     fg=self.theme.text, bg=self.theme.bg, bold=True)
        regions: list[Region] = []
        for offset, row in enumerate(self.rows[:16]):
            screen_row = SEARCH_TOP + offset
            active = offset == self.row
            fg = self.theme.selected_fg if active else self.theme.text
            bg = self.theme.selected_bg if active else self.theme.bg
            if active:
                buffer.fill_rect(screen_row, 1, 1, 70, " ", fg=fg, bg=bg)
            for column, col in enumerate((COL_FIELD, COL_OPERATOR,
                                          COL_VALUE, COL_CONNECTOR)):
                text = self._cell_text(row, column)
                if active and column == self.column:
                    text = self.edit_text
                width = (20 if column == 0 else 5 if column == 1
                         else 26 if column == 2 else 6)
                buffer.write(screen_row, col, clip_text(text, width),
                             fg=fg, bg=bg,
                             underline=active and column == self.column)
            regions.append(Region(screen_row, COL_FIELD, 1, 64,
                                  f"search:cell:{offset}"))
        draw_status_line(buffer, self.theme,
                         self.status or "TAB next column   F4 sort order   "
                                        "F10 continue")
        draw_help_line(buffer, self.theme,
                       "F2 fields   F3 operators   F7 last   F8 desc   "
                       "F9 expression   F10 continue")
        regions.extend(draw_menu_line(buffer, self.theme, SEARCH_KEYS))
        return regions

    def _view_sort(self, buffer: CellBuffer) -> list[Region]:
        buffer.write(2, 2, "Sort", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(2, 10, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(2, 12, self.description or "(no description)",
                     fg=self.theme.text, bg=self.theme.bg)
        buffer.write(4, 2, "Level", fg=self.theme.text, bg=self.theme.bg,
                     bold=True)
        buffer.write(4, SORT_FIELD_COL, "Field", fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        buffer.write(4, SORT_DIRECTION_COL, "Direction", fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        regions: list[Region] = []
        for offset, (name, direction) in enumerate(self.sort_rows[:12]):
            screen_row = SORT_TOP + offset
            active = offset == self.sort_row
            fg = self.theme.selected_fg if active else self.theme.text
            bg = self.theme.selected_bg if active else self.theme.bg
            if active:
                buffer.fill_rect(screen_row, 1, 1, 66, " ", fg=fg, bg=bg)
            field_text = name
            if active and self.sort_column == 0:
                field_text = self.edit_text
            buffer.write(screen_row, 2, str(offset + 1), fg=fg, bg=bg)
            buffer.write(screen_row, SORT_FIELD_COL,
                         clip_text(field_text, 22), fg=fg, bg=bg,
                         underline=active and self.sort_column == 0)
            buffer.write(screen_row, SORT_DIRECTION_COL,
                         "Ascending" if direction == "A" else "Descending",
                         fg=fg, bg=bg, underline=active and self.sort_column == 1)
            regions.append(Region(screen_row, 2, 1, 60, f"search:sort:{offset}"))
        options_row = SORT_TOP + len(self.sort_rows)
        for offset, label, text in (
                (0, "Case sensitive", "Yes" if self.case_sensitive else "No"),
                (1, "Show", {indexing.SHOW_ALL: "All",
                             indexing.SHOW_DELETED: "Deleted",
                             indexing.SHOW_NOT_DELETED: "Not deleted"
                             }.get(self.show, self.show))):
            screen_row = options_row + 1 + offset
            active = self.sort_row == len(self.sort_rows) + offset
            fg = self.theme.selected_fg if active else self.theme.text
            bg = self.theme.selected_bg if active else self.theme.bg
            if active:
                buffer.fill_rect(screen_row, 1, 1, 66, " ", fg=fg, bg=bg)
            buffer.write(screen_row, 2, label, fg=fg, bg=bg, bold=active)
            buffer.write(screen_row, 22, ":", fg=fg, bg=bg)
            buffer.write(screen_row, 24, text, fg=fg, bg=bg)
            regions.append(Region(screen_row, 2, 1, 40,
                                  f"search:sortoption:{offset}"))
        draw_status_line(buffer, self.theme,
                         self.status or "Field determines the sort order")
        draw_help_line(buffer, self.theme,
                       "F2 fields   F4 search criteria   F10 continue")
        regions.extend(draw_menu_line(buffer, self.theme, SORT_KEYS))
        return regions

    def _view_expression(self, buffer: CellBuffer) -> list[Region]:
        rows = (
            ("Search expression", self.expression),
            ("Sort expression", self.sort_expression),
            ("Show", {indexing.SHOW_ALL: "All",
                      indexing.SHOW_DELETED: "Deleted",
                      indexing.SHOW_NOT_DELETED: "Not deleted"
                      }.get(self.show, self.show)),
            ("Case sensitive", "Yes" if self.case_sensitive else "No"),
            ("Description", self.description),
        )
        regions: list[Region] = []
        for index, (label, value) in enumerate(rows):
            screen_row = 4 + index * 2
            active = index == self.row
            fg = self.theme.selected_fg if active else self.theme.text
            bg = self.theme.selected_bg if active else self.theme.bg
            if active:
                buffer.fill_rect(screen_row, 1, 1, 90, " ", fg=fg, bg=bg)
            buffer.write(screen_row, 2, label, fg=fg, bg=bg, bold=active)
            buffer.write(screen_row, 20, ":", fg=fg, bg=bg)
            buffer.write(screen_row, 22, clip_text(value, 100), fg=fg, bg=bg,
                         underline=active and index in (0, 1))
            regions.append(Region(screen_row, 2, 1, 100,
                                  f"search:expression:{index}"))
        draw_status_line(buffer, self.theme,
                         self.status or "Type the expressions; F10 continue")
        draw_help_line(buffer, self.theme,
                       "F4 sort order   F9 table mode   F10 continue")
        regions.extend(draw_menu_line(buffer, self.theme, EXPRESSION_KEYS))
        return regions

    def _view_description(self, buffer: CellBuffer) -> list[Region]:
        buffer.write(4, 2, "Description", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(4, 16, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.fill_rect(4, 18, 1, 90, " ", fg=self.theme.selected_fg,
                         bg=self.theme.selected_bg)
        buffer.write(4, 18, clip_text(self.description_text, 90),
                     fg=self.theme.selected_fg, bg=self.theme.selected_bg,
                     underline=True)
        draw_status_line(buffer, self.theme,
                         "Enter a description for the Search/Sort List")
        draw_help_line(buffer, self.theme, "ENTER accept   ESC cancel")
        return [Region(4, 18, 1, 90, "search:description")]

    def _runbox_view(self, base: View) -> View:
        width, height = 52, 8
        panel = window(width, height, "Search/Sort", self.theme)
        labels = (["Save and run search/sort", "Exit"] if self.letter
                  else ["Run one-time search/sort", "Exit"])
        for index, label in enumerate(labels):
            selected = index == self.run_choice
            fg = self.theme.selected_fg if selected else self.theme.window_fg
            bg = self.theme.selected_bg if selected else self.theme.window_bg
            if selected:
                panel.fill_rect(2 + index, 1, 1, width - 2, " ", fg=fg, bg=bg)
            panel.write(2 + index, 2, label, fg=fg, bg=bg)
        panel.write(height - 2, 2, "ENTER run   ESC back", fg=self.theme.muted,
                    bg=self.theme.window_bg)
        row = max(1, (STATUS_ROW - height) // 2)
        col = max(1, (SCREEN_WIDTH - width) // 2)
        regions = [Region(row + 2 + index, col + 1, 1, width - 2,
                          f"search:run:{index}")
                   for index in range(len(labels))]
        regions.append(Region(row, col, height, width, "search:runbox"))
        return screens.overlay_view(base, panel, row, col, regions, self.theme)


__all__ = ["OPERATORS", "SearchSession"]
