"""Table designer: creazione e riconfigurazione dei database.

La schermata è la stessa griglia dei record: un elenco di campi con nome,
tipo, lunghezza e decimali. Il salvataggio applica la tabella di conversione
del manuale: cambiare tipo non è una modifica cosmetica, è una migrazione.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW, Cell, CellBuffer
from ..data.fields import (
    FIELD_TYPES,
    FIXED_LENGTHS,
    Field,
    FieldError,
    make_field,
    validate_fields,
)
from ..data.workspace import Database, Workspace, WorkspaceError
from ..screen.keys import Key, character
from .theme import NEWPORT, Theme
from .widgets import (
    Region,
    View,
    clip_text,
    draw_help_line,
    draw_menu_line,
    draw_status_line,
    title_bar,
)

DESIGNER_KEYS = [("F1", "Help"), ("F5", "Delete field"), ("F6", "Insert field"),
                 ("F10", "Save"), ("ESC", "Cancel")]
ROW_TOP = 5
COLUMNS = (2, 12, 34, 44, 52)
COLUMN_NAMES = ("Number", "Field Name", "Type", "Length", "Decimal Place")
LAST_COLUMN = len(COLUMNS) - 1


@dataclass
class DesignerRow:
    original: str | None = None
    name: str = ""
    type: str = "C"
    length: str = "10"
    decimals: str = "0"

    @classmethod
    def blank(cls) -> "DesignerRow":
        return cls()

    @classmethod
    def from_field(cls, field: Field) -> "DesignerRow":
        return cls(field.name, field.name, field.type,
                   str(field.length), str(field.decimals))

    def text(self, column: int) -> str:
        self._apply_fixed()
        values = (self.name, self.type, self.length, self.decimals)
        data = column - 1
        return values[data] if 0 <= data < len(values) else ""

    def set_text(self, column: int, text: str) -> None:
        data = column - 1
        if data == 0:
            self.name = text.upper()
        elif data == 1:
            self.type = text.upper()[:1]
        elif data == 2:
            self.length = text
        elif data == 3:
            self.decimals = text
        self._apply_fixed()

    def editable(self, column: int) -> bool:
        data = column - 1
        if column == 0:
            return False
        if data in (0, 1):
            return True
        if data == 2:
            return self.type not in FIXED_LENGTHS
        if data == 3:
            return self.type == "N"
        return False

    def _apply_fixed(self) -> None:
        if self.type in FIXED_LENGTHS:
            self.length = str(FIXED_LENGTHS[self.type])
            self.decimals = "0"


@dataclass
class DesignerSession:
    workspace: Workspace
    name: str
    database: Database | None = None
    theme: Theme = NEWPORT
    rows: list[DesignerRow] = field(default_factory=list)
    row: int = 0
    column: int = 1
    top: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    replace_on_type: bool = False
    status: str = ""
    help_topic: str = "designer"
    close: bool = False
    dirty: bool = False
    saved_database: Database | None = None

    def __post_init__(self) -> None:
        if self.database is not None:
            self.rows = [DesignerRow.from_field(field) for field in self.database.fields]
            self.name = self.database.name
        if not self.rows:
            self.rows = [DesignerRow.blank()]
        self.row = 0
        self.column = 1 if self.rows[0].name else 0
        self._load_cell()

    @property
    def title(self) -> str:
        return ("Modify Database" if self.database is not None
                else "Create Database")

    @property
    def per_page(self) -> int:
        return max(1, STATUS_ROW - ROW_TOP)

    # -- cella attiva ----------------------------------------------------
    def _load_cell(self) -> None:
        self.row = max(0, min(self.row, len(self.rows) - 1))
        self.column = max(0, min(self.column, LAST_COLUMN))
        if not self.rows[self.row].editable(self.column):
            self._normalize_cursor(1)
        self.edit_text = self.rows[self.row].text(self.column)
        self.replace_on_type = self.column in (2, 3, 4)
        self.edit_cursor = 0 if self.replace_on_type else len(self.edit_text)
        self._fix_top()

    def _fix_top(self) -> None:
        if self.row < self.top:
            self.top = self.row
        elif self.row >= self.top + self.per_page:
            self.top = self.row - self.per_page + 1
        self.top = max(0, min(self.top, max(0, len(self.rows) - self.per_page)))

    def _commit_cell(self) -> bool:
        before = self.rows[self.row].text(self.column)
        self.rows[self.row].set_text(self.column, self.edit_text)
        after = self.rows[self.row].text(self.column)
        if after != before:
            self.dirty = True
        self.edit_text = after
        self.edit_cursor = min(self.edit_cursor, len(self.edit_text))
        return True

    def _normalize_cursor(self, direction: int) -> None:
        """Salta le celle non modificabili, cambiando riga quando serve."""
        for _ in range((LAST_COLUMN + 1) * max(1, len(self.rows))):
            if self.rows[self.row].editable(self.column):
                return
            self.column += direction
            if self.column > LAST_COLUMN:
                self.column = 0
                self.row += 1
            elif self.column < 0:
                self.column = LAST_COLUMN
                self.row -= 1
            if self.row >= len(self.rows):
                self.row = 0
            elif self.row < 0:
                self.row = len(self.rows) - 1

    def _move(self, delta_row: int = 0, delta_column: int = 0) -> None:
        self._commit_cell()
        if delta_row:
            self.row = max(0, min(len(self.rows) - 1, self.row + delta_row))
        if delta_column:
            self.column += delta_column
            if self.column > LAST_COLUMN:
                self.column = 0
                self.row = self.row + 1 if self.row + 1 < len(self.rows) else 0
            elif self.column < 0:
                self.column = LAST_COLUMN
                self.row = self.row - 1 if self.row > 0 else len(self.rows) - 1
        self._load_cell()

    # -- righe -----------------------------------------------------------
    def _insert_row(self) -> None:
        self._commit_cell()
        self.rows.insert(self.row + 1, DesignerRow.blank())
        self.row += 1
        self.column = 0
        self.dirty = True
        self._load_cell()
        self.status = "Field inserted."

    def _delete_row(self) -> None:
        self._commit_cell()
        if len(self.rows) == 1:
            self.rows[0] = DesignerRow.blank()
        else:
            del self.rows[self.row]
            self.row = min(self.row, len(self.rows) - 1)
        self.column = 0
        self.dirty = True
        self._load_cell()
        self.status = "Field deleted."

    # -- salvataggio -----------------------------------------------------
    def save(self) -> bool:
        self._commit_cell()
        fields: list[Field] = []
        mapping: list[tuple[str | None, Field]] = []
        for index, row in enumerate(self.rows, start=1):
            if not row.name.strip():
                if row.original is None and _is_blank(row):
                    continue
                self.status = f"Field {index}: enter a field name."
                return False
            try:
                field_definition = make_field(row.name, row.type, row.length,
                                              row.decimals)
            except FieldError as exc:
                self.status = f"Field {index}: {exc}"
                return False
            fields.append(field_definition)
            mapping.append((row.original, field_definition))
        try:
            validate_fields(fields)
        except FieldError as exc:
            self.status = str(exc)
            return False
        try:
            if self.database is None:
                saved = self.workspace.create_database(self.name, fields)
            else:
                saved = self.workspace.alter_database(self.name, mapping)
        except (WorkspaceError, OSError) as exc:
            self.status = str(exc)
            return False
        self.saved_database = saved
        self.database = saved
        self.rows = [DesignerRow.from_field(field) for field in saved.fields]
        for row in self.rows:
            row.original = row.name
        self.dirty = False
        self.status = "Database saved."
        self.close = True
        return True

    # -- tasti -----------------------------------------------------------
    def handle(self, key: Key) -> None:
        self.status = ""
        name = key.name
        if name == "F1":
            return
        if name == "F10":
            self.save()
            return
        if name == "ESC":
            self.close = True
            return
        if name == "F5":
            self._delete_row()
            return
        if name == "F6":
            self._insert_row()
            return
        if name == "UP":
            self._move(delta_row=-1)
            return
        if name == "DOWN":
            self._move(delta_row=1)
            return
        if name == "PGUP":
            self._move(delta_row=-self.per_page)
            return
        if name == "PGDN":
            self._move(delta_row=self.per_page)
            return
        if name == "TAB":
            self._move(delta_column=-1 if key.shift else 1)
            return
        if name == "ENTER":
            self._move(delta_column=1)
            return
        if name == "LEFT":
            self.edit_cursor = max(0, self.edit_cursor - 1)
            return
        if name == "RIGHT":
            self.edit_cursor = min(len(self.edit_text), self.edit_cursor + 1)
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
                self.dirty = True
            return
        if name == "DELETE":
            self.edit_text = (self.edit_text[:self.edit_cursor]
                              + self.edit_text[self.edit_cursor + 1:])
            self.dirty = True
            return
        text = character(key)
        if not text:
            return
        if self.column == 1 and text.isalpha() and not key.shift:
            text = text.upper()
        if self.column == 2:
            text = text.upper()
            if text not in FIELD_TYPES:
                self.status = "Field type is C, N, D, L or M."
                return
        if self.column in (3, 4) and not (text.isdigit() or text in "+-"):
            return
        if self.replace_on_type:
            self.edit_text = ""
            self.edit_cursor = 0
            self.replace_on_type = False
        if self.edit_cursor >= len(self.edit_text):
            self.edit_text += text
        else:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor + 1:])
        self.edit_cursor += len(text)
        self.dirty = True
        self.rows[self.row].set_text(self.column, self.edit_text)

    # -- mouse -----------------------------------------------------------
    def click_action(self, action: str) -> None:
        kind, _, value = action.partition(":")
        if kind != "cell":
            return
        parts = value.split(":")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            return
        self._commit_cell()
        self.row = max(0, min(len(self.rows) - 1, int(parts[0])))
        self.column = max(0, min(LAST_COLUMN, int(parts[1])))
        self._load_cell()

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT, Cell(fg=self.theme.text,
                                                             bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, f"{self.title} - {self.name}", self.theme)
        buffer.write(2, 2, "Database", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(2, 12, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(2, 14, self.name, fg=self.theme.text, bg=self.theme.bg,
                     bold=True)
        length = sum(_row_length(row) for row in self.rows)
        buffer.write(3, 2, "Fields", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(3, 12, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(3, 14, str(len(self.rows)), fg=self.theme.text,
                     bg=self.theme.bg)
        buffer.write(3, 19, "Record length", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(3, 34, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(3, 36, str(length), fg=self.theme.text, bg=self.theme.bg)

        for column, label in enumerate(COLUMN_NAMES):
            buffer.write(4, COLUMNS[column], label, fg=self.theme.text,
                         bg=self.theme.bg, bold=True)
        regions: list[Region] = []
        visible = self.rows[self.top:self.top + self.per_page]
        for offset, row in enumerate(visible):
            index = self.top + offset
            screen_row = ROW_TOP + offset
            if index == self.row:
                buffer.fill_rect(screen_row, 1, 1, 74, " ",
                                 fg=self.theme.selected_fg,
                                 bg=self.theme.selected_bg)
                fg, bg = self.theme.selected_fg, self.theme.selected_bg
            else:
                fg, bg = self.theme.text, self.theme.bg
            buffer.write(screen_row, COLUMNS[0], str(index + 1), fg=fg, bg=bg)
            for column in range(1, len(COLUMNS)):
                if index == self.row and column == self.column:
                    buffer.fill_rect(screen_row, COLUMNS[column], 1, 10, " ",
                                     fg=self.theme.selected_fg,
                                     bg=self.theme.selected_bg)
                    visible_text = self.edit_text
                    cursor = self.edit_cursor
                    if cursor >= 10:
                        visible_text = visible_text[cursor - 9:]
                        cursor = 9
                    buffer.write(screen_row, COLUMNS[column],
                                 clip_text(visible_text, 10),
                                 fg=self.theme.selected_fg,
                                 bg=self.theme.selected_bg, underline=True)
                    buffer.write(screen_row, COLUMNS[column] + cursor,
                                 visible_text[cursor] if cursor < len(visible_text) else " ",
                                 fg=self.theme.accent, bg=self.theme.selected_bg,
                                 blink=True, bold=True)
                else:
                    width = 20 if column == 1 else 9
                    buffer.write(screen_row, COLUMNS[column],
                                 clip_text(row.text(column), width), fg=fg, bg=bg)
                regions.append(Region(screen_row, COLUMNS[column], 1,
                                      10 if column else 8,
                                      f"dsn:cell:{index}:{column}"))
        pages = max(1, (len(self.rows) + self.per_page - 1) // self.per_page)
        if pages > 1:
            buffer.write(1, SCREEN_WIDTH - 20, f"Page {self.top // self.per_page + 1} of {pages}",
                         fg=self.theme.label, bg=self.theme.bg)

        draw_status_line(buffer, self.theme,
                         f"Field {self.row + 1} of {len(self.rows)}")
        draw_help_line(buffer, self.theme,
                       self.status or "TAB next column   F5 delete field   "
                       "F6 insert field   F10 save   ESC cancel")
        regions.extend(draw_menu_line(buffer, self.theme, DESIGNER_KEYS))
        return View(buffer, regions)


def _is_blank(row: DesignerRow) -> bool:
    return (not row.name and row.type == "C"
            and row.length in ("", "10") and row.decimals in ("", "0"))


def _row_length(row: DesignerRow) -> int:
    try:
        return int(row.length or 0)
    except ValueError:
        return 0


__all__ = ["COLUMNS", "DesignerRow", "DesignerSession"]
