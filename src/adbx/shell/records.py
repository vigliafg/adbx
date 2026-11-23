"""Modalità record: View, Enter, Change, Browse, memo e clipboard.

Il session object è l'unico proprietario dello stato di una visita ai dati.
Il controller gli passa i tasti; lui produce una `View` tramite
`record_screens`. Nessun widget, nessuna copia del database in RAM.

Le regole di tastiera seguono l'inventario del manuale: TAB sposta di dieci
record, CTRL-HOME/END vanno al primo/ultimo, ALT-D/ALT-U cancellano e
richiamano, ALT-M apre il memo, ALT-F5/ALT-F6 copiano e incollano.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..cell.buffer import STATUS_ROW
from ..data.fields import Field, FieldError, format_value, parse_value
from ..data.workspace import Database, WorkspaceError
from ..screen.keys import Key, character
from .theme import NEWPORT, Theme
from .widgets import View

MODE_TITLES = {
    "view": "View Records",
    "enter": "Enter Records",
    "change": "Change Records",
    "browse": "Browse Records",
}

MODE_KEYS = {
    "view": [("F1", "Help"), ("F10", "Continue"), ("F7", "Show deleted"),
             ("Alt-M", "Memo"), ("Alt-D", "Delete"), ("Alt-U", "Undelete"),
             ("Alt-F5", "Copy")],
    "browse": [("F1", "Help"), ("F10", "Continue"), ("F7", "Show deleted"),
               ("Alt-M", "Memo"), ("Alt-D", "Delete"), ("Alt-U", "Undelete"),
               ("Alt-F5", "Copy")],
    "enter": [("F1", "Help"), ("F10", "Save"), ("ESC", "Cancel"),
              ("Alt-M", "Memo"), ("Alt-F5", "Copy"), ("Alt-F6", "Paste")],
    "change": [("F1", "Help"), ("F10", "Save"), ("ESC", "Cancel"),
               ("Alt-M", "Memo"), ("Alt-F5", "Copy"), ("Alt-F6", "Paste")],
}

FORM_WORK_TOP = 3


@dataclass
class MemoEditor:
    field_name: str
    text: str = ""
    readonly: bool = False
    row: int = 0
    col: int = 0
    top: int = 0
    left: int = 0
    width: int = 92
    height: int = 21

    def __post_init__(self) -> None:
        self.lines = self.text.split("\n") if self.text else [""]

    lines: list[str] = field(init=False, default_factory=list)

    @property
    def body(self) -> str:
        return "\n".join(self.lines)

    def set_text(self, text: str) -> None:
        self.text = text
        self.lines = text.split("\n") if text else [""]
        self.row = min(self.row, len(self.lines) - 1)
        self.col = min(self.col, len(self.lines[self.row]))

    def handle(self, key: Key) -> str:
        """Gestisce un tasto; ritorna "save", "cancel" o ""."""
        name = key.name
        if name in ("F10", "ESC"):
            return "cancel" if name == "ESC" else "save"
        if self.readonly:
            if name == "UP":
                self.row = max(0, self.row - 1)
                self.col = min(self.col, len(self.lines[self.row]))
            elif name == "DOWN":
                self.row = min(len(self.lines) - 1, self.row + 1)
                self.col = min(self.col, len(self.lines[self.row]))
            elif name == "LEFT":
                self.col = max(0, self.col - 1)
            elif name == "RIGHT":
                self.col = min(len(self.lines[self.row]), self.col + 1)
            elif name == "PGUP":
                self.row = max(0, self.row - self.height)
                self.col = min(self.col, len(self.lines[self.row]))
            elif name == "PGDN":
                self.row = min(len(self.lines) - 1, self.row + self.height)
                self.col = min(self.col, len(self.lines[self.row]))
            self._scroll()
            return ""
        if name == "UP":
            self.row = max(0, self.row - 1)
            self.col = min(self.col, len(self.lines[self.row]))
        elif name == "DOWN":
            self.row = min(len(self.lines) - 1, self.row + 1)
            self.col = min(self.col, len(self.lines[self.row]))
        elif name == "LEFT":
            self.col = max(0, self.col - 1)
        elif name == "RIGHT":
            self.col = min(len(self.lines[self.row]), self.col + 1)
        elif name == "HOME":
            self.col = 0
        elif name == "END":
            self.col = len(self.lines[self.row])
        elif name == "PGUP":
            self.row = max(0, self.row - self.height)
            self.col = min(self.col, len(self.lines[self.row]))
        elif name == "PGDN":
            self.row = min(len(self.lines) - 1, self.row + self.height)
            self.col = min(self.col, len(self.lines[self.row]))
        elif name == "ENTER":
            line = self.lines[self.row]
            self.lines[self.row:self.row + 1] = [line[:self.col], line[self.col:]]
            self.row += 1
            self.col = 0
        elif name == "BACKSPACE":
            if self.col:
                line = self.lines[self.row]
                self.lines[self.row] = line[:self.col - 1] + line[self.col:]
                self.col -= 1
            elif self.row:
                previous = self.lines[self.row - 1]
                self.col = len(previous)
                self.lines[self.row - 1:self.row + 1] = [previous + self.lines[self.row]]
                self.row -= 1
        elif name == "DELETE":
            line = self.lines[self.row]
            if self.col < len(line):
                self.lines[self.row] = line[:self.col] + line[self.col + 1:]
            elif self.row + 1 < len(self.lines):
                self.lines[self.row:self.row + 2] = [line + self.lines[self.row + 1]]
        elif name == "TAB":
            self._insert("    ")
        else:
            text = _typed_char(key)
            if text:
                self._insert(text)
        self._scroll()
        return ""

    def _insert(self, text: str) -> None:
        line = self.lines[self.row]
        self.lines[self.row] = line[:self.col] + text + line[self.col:]
        self.col += len(text)

    def _scroll(self) -> None:
        if self.row < self.top:
            self.top = self.row
        elif self.row >= self.top + self.height:
            self.top = self.row - self.height + 1
        if self.col < self.left:
            self.left = self.col
        elif self.col >= self.left + self.width:
            self.left = self.col - self.width + 1


@dataclass
class RecordSession:
    database: Database
    mode: str
    theme: Theme = NEWPORT
    clipboard: list[str] = field(default_factory=lambda: [""])
    show_deleted: bool = False
    status: str = ""
    help_topic: str = "records"
    close: bool = False
    index: int = 0
    top: int = 0
    field_index: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    insert_mode: bool = False
    draft: dict[str, str] = field(default_factory=dict)
    seq: int | None = None
    dirty: bool = False
    memo: MemoEditor | None = None
    browse_field: int = 0
    _seqs: list[int] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if self.mode not in MODE_TITLES:
            raise ValueError(f"Unknown record mode: {self.mode}")
        self._reload()
        if self.mode == "enter":
            self._start_new()
        elif self._seqs:
            self.index = min(self.index, len(self._seqs) - 1)
            if self.mode == "change":
                self._load_record()
        else:
            self.status = "This database has no records."

    # -- stato -----------------------------------------------------------
    @property
    def title(self) -> str:
        return MODE_TITLES[self.mode]

    @property
    def current_seq(self) -> int | None:
        if 0 <= self.index < len(self._seqs):
            return self._seqs[self.index]
        return None

    @property
    def record_count(self) -> int:
        return len(self._seqs)

    @property
    def page_rows(self) -> int:
        return max(1, STATUS_ROW - (FORM_WORK_TOP + 1))

    def _reload(self, keep: int | None = None) -> None:
        self._seqs = self.database.sequences(include_deleted=self.show_deleted)
        if keep is not None and keep in self._seqs:
            self.index = self._seqs.index(keep)
        self.index = max(0, min(self.index, max(0, len(self._seqs) - 1)))
        self._fix_top()

    def _fix_top(self) -> None:
        visible = self.page_rows
        if self.index < self.top:
            self.top = self.index
        elif self.index >= self.top + visible:
            self.top = self.index - visible + 1
        self.top = max(0, min(self.top, max(0, len(self._seqs) - visible)))

    def _load_record(self) -> None:
        seq = self.current_seq
        if seq is None:
            self.draft = {}
            self.seq = None
            return
        self.seq = seq
        self.draft = self.database.read(seq)
        self.dirty = False
        self._load_field()

    def _start_new(self) -> None:
        self.seq = None
        self.draft = {field.name: "" for field in self.database.fields}
        self.field_index = 0
        self.dirty = False
        self._load_field()

    def _values(self) -> dict[str, str]:
        if self.mode in ("enter", "change"):
            return self.draft
        seq = self.current_seq
        return self.database.read(seq) if seq is not None else {}

    # -- campi -----------------------------------------------------------
    def _field(self) -> Field | None:
        if 0 <= self.field_index < len(self.database.fields):
            return self.database.fields[self.field_index]
        return None

    def _load_field(self) -> None:
        field = self._field()
        if field is None:
            self.edit_text = ""
            self.edit_cursor = 0
            return
        self.edit_text = format_value(field, self.draft.get(field.name, ""))
        self.edit_cursor = len(self.edit_text)

    def _commit_field(self) -> bool:
        field = self._field()
        if field is None or field.is_memo:
            return True
        try:
            value = parse_value(field, self.edit_text)
        except FieldError as exc:
            self.status = str(exc)
            return False
        if value != self.draft.get(field.name, ""):
            self.dirty = True
        self.draft[field.name] = value
        self.edit_text = format_value(field, value)
        self.edit_cursor = min(self.edit_cursor, len(self.edit_text))
        return True

    def _move_field(self, delta: int, *, wrap: bool = False) -> None:
        if not self._commit_field():
            return
        count = len(self.database.fields)
        if count == 0:
            return
        target = self.field_index + delta
        if wrap:
            target %= count
        else:
            target = max(0, min(count - 1, target))
        if target != self.field_index:
            self.field_index = target
            self._load_field()

    def _typed(self, key: Key) -> None:
        if self.mode not in ("enter", "change"):
            return
        field = self._field()
        if field is None or field.is_memo:
            return
        text = _typed_char(key)
        if not text:
            return
        if self.insert_mode:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor:])
        else:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor + 1:])
        self.edit_cursor += len(text)
        self.dirty = True

    # -- salvataggio -----------------------------------------------------
    def save(self) -> bool:
        if self.mode not in ("enter", "change"):
            return True
        if not self._commit_field():
            return False
        if not any((self.draft.get(field.name) or "").strip()
                   for field in self.database.fields):
            self.status = "Enter at least one value before saving."
            return False
        try:
            if self.seq is None:
                self.seq = self.database.append(self.draft)
                self.status = f"Record {self.seq} added."
            else:
                self.database.update(self.seq, self.draft)
                self.status = f"Record {self.seq} saved."
        except WorkspaceError as exc:
            self.status = str(exc)
            return False
        self._persist()
        self.dirty = False
        self._reload(keep=self.seq)
        return True

    def _persist(self) -> None:
        try:
            self.database.workspace.save_database(self.database)
        except (OSError, WorkspaceError) as exc:
            self.status += f" (.DBF not updated: {exc})"

    def _discard(self) -> None:
        self.dirty = False
        self.memo = None
        if self.mode == "change":
            self._load_record()
        elif self.mode == "enter":
            self._start_new()
        self.status = "Changes discarded."

    # -- navigazione -----------------------------------------------------
    def _move_record(self, delta: int) -> None:
        if self.mode in ("enter", "change") and self.dirty:
            self.status = "Save the record with F10 or cancel with ESC before moving."
            return
        if not self._seqs:
            return
        self.index = max(0, min(len(self._seqs) - 1, self.index + delta))
        self._fix_top()
        if self.mode == "change":
            self._load_record()

    def _goto_record(self, index: int) -> None:
        if self.mode in ("enter", "change") and self.dirty:
            self.status = "Save the record with F10 or cancel with ESC before moving."
            return
        if not self._seqs:
            return
        self.index = max(0, min(len(self._seqs) - 1, index))
        self._fix_top()
        if self.mode == "change":
            self._load_record()

    def _toggle_deleted(self) -> None:
        if self.mode in ("enter", "change") and self.dirty:
            self.status = "Save or cancel the record first."
            return
        keep = self.current_seq
        self.show_deleted = not self.show_deleted
        self._reload(keep=keep)
        self.status = ("Deleted records are shown."
                       if self.show_deleted else "Deleted records are hidden.")
        if self.mode == "change":
            self._load_record()

    def _delete_current(self) -> None:
        if self.mode not in ("view", "browse"):
            self.status = "Delete records from View or Browse mode."
            return
        seq = self.current_seq
        if seq is None:
            self.status = "No record selected."
            return
        self.database.delete(seq)
        self._persist()
        self.status = "Record marked for deletion. Use Show deleted and Alt-U to recall it."
        if not self.show_deleted:
            self._reload()
            if self.mode == "change":
                self._load_record()

    def _undelete_current(self) -> None:
        if self.mode not in ("view", "browse"):
            self.status = "Undelete records from View or Browse mode."
            return
        seq = self.current_seq
        if seq is None:
            self.status = "No record selected."
            return
        if not self.show_deleted:
            self.status = "Turn on Show deleted (F7) to recall a deleted record."
            return
        self.database.undelete(seq)
        self._persist()
        self.status = "Record recalled."
        self._reload(keep=seq)

    # -- memo ------------------------------------------------------------
    def _memo_field(self) -> Field | None:
        if self.mode in ("enter", "change"):
            field = self._field()
            if field is not None and field.is_memo:
                return field
            if field is not None and self.field_index < len(self.database.fields):
                pass
        if 0 <= self.field_index < len(self.database.fields):
            candidate = self.database.fields[self.field_index]
            if candidate.is_memo:
                return candidate
        return next(iter(self.database.memo_fields), None)

    def _open_memo(self) -> None:
        field = self._memo_field()
        if field is None:
            self.status = "This database has no memo fields."
            return
        values = self._values()
        self.memo = MemoEditor(
            field.name, values.get(field.name, ""),
            readonly=self.mode in ("view", "browse"))
        self.status = f"Memo: {field.name}"

    def _close_memo(self, action: str) -> None:
        editor = self.memo
        if editor is None:
            return
        self.memo = None
        if action == "cancel":
            self.status = "Memo unchanged."
            return
        if editor.readonly:
            return
        if len(editor.body) > 5000:
            self.status = "A memo is at most 5000 characters."
            return
        self.draft[editor.field_name] = editor.body
        self.dirty = True
        self._load_field()
        self.status = "Memo updated; save the record with F10."

    # -- clipboard -------------------------------------------------------
    def _clipboard_value(self) -> str:
        if self.mode == "browse":
            seq = self.current_seq
            if seq is None:
                return ""
            values = self.database.read(seq)
            field = self.database.fields[min(self.browse_field, len(self.database.fields) - 1)]
            return format_value(field, values.get(field.name, ""))
        if self.mode in ("enter", "change"):
            return self.edit_text
        values = self._values()
        if not self.database.fields:
            return ""
        field = self.database.fields[min(self.field_index, len(self.database.fields) - 1)]
        if field.is_memo:
            return values.get(field.name, "")
        return format_value(field, values.get(field.name, ""))

    def _copy(self) -> None:
        self.clipboard[0] = self._clipboard_value()
        self.status = "Field copied."

    def _paste(self) -> None:
        if self.mode not in ("enter", "change"):
            self.status = "Paste is available while entering or changing a record."
            return
        field = self._field()
        if field is None or field.is_memo:
            self.status = "Select a field to paste into."
            return
        self.edit_text = self.clipboard[0]
        self.edit_cursor = len(self.edit_text)
        self.dirty = True
        self.status = "Field pasted."

    # -- tasti -----------------------------------------------------------
    def handle(self, key: Key) -> None:
        self.status = ""
        self.help_topic = "browse" if self.mode == "browse" else "records"
        if self.memo is not None:
            action = self.memo.handle(key)
            if action:
                self._close_memo(action)
            return
        name = key.name
        if name == "F1":
            if key.alt:
                return
            return
        if key.alt:
            if name == "M":
                self._open_memo()
            elif name == "D":
                self._delete_current()
            elif name == "U":
                self._undelete_current()
            elif name == "F5":
                self._copy()
            elif name == "F6":
                self._paste()
            return
        if name == "F10":
            if self.mode == "view" or self.mode == "browse":
                self.close = True
            elif self.save():
                self.close = True
            return
        if name == "ESC":
            if self.mode in ("enter", "change") and self.dirty:
                self._discard()
            self.close = True
            return
        if name == "F7":
            self._toggle_deleted()
            return
        if self.mode == "browse":
            self._handle_browse(key)
        elif self.mode == "view":
            self._handle_view(key)
        else:
            self._handle_form(key)

    def _handle_view(self, key: Key) -> None:
        name = key.name
        if name == "UP":
            self._move_record(-1)
        elif name == "DOWN":
            self._move_record(1)
        elif name == "PGUP":
            self._move_record(-10)
        elif name == "PGDN":
            self._move_record(10)
        elif name == "TAB":
            self._move_record(10 if not key.shift else -10)
        elif name == "HOME":
            self._goto_record(0)
        elif name == "END":
            self._goto_record(len(self._seqs) - 1)
        elif name == "LEFT":
            if self.database.fields:
                self.field_index = (self.field_index - 1) % len(self.database.fields)
        elif name == "RIGHT":
            if self.database.fields:
                self.field_index = (self.field_index + 1) % len(self.database.fields)

    def _handle_browse(self, key: Key) -> None:
        name = key.name
        if name == "UP":
            self._move_record(-1)
        elif name == "DOWN":
            self._move_record(1)
        elif name == "PGUP":
            self._move_record(-self.page_rows)
        elif name == "PGDN":
            self._move_record(self.page_rows)
        elif name == "TAB":
            self._move_record(10 if not key.shift else -10)
        elif name == "HOME":
            self._goto_record(0)
        elif name == "END":
            self._goto_record(len(self._seqs) - 1)
        elif name == "LEFT":
            self.browse_field = max(0, self.browse_field - 1)
        elif name == "RIGHT":
            self.browse_field = min(max(0, len(self.database.fields) - 1),
                                    self.browse_field + 1)

    def _handle_form(self, key: Key) -> None:
        name = key.name
        if name in ("TAB", "SHIFT-TAB"):
            self._move_field(-1 if key.shift else 1, wrap=True)
        elif name == "UP":
            self._move_field(-1)
        elif name == "DOWN":
            self._move_field(1)
        elif name in ("LEFT", "RIGHT", "HOME", "END"):
            if self.edit_text and name == "LEFT":
                self.edit_cursor = max(0, self.edit_cursor - 1)
            elif name == "RIGHT":
                self.edit_cursor = min(len(self.edit_text), self.edit_cursor + 1)
            elif name == "HOME":
                self.edit_cursor = 0
            elif name == "END":
                self.edit_cursor = len(self.edit_text)
        elif name == "BACKSPACE" and key.ctrl:
            self.edit_text = ""
            self.edit_cursor = 0
            self.dirty = True
        elif name == "BACKSPACE":
            if self.edit_cursor:
                self.edit_text = (self.edit_text[:self.edit_cursor - 1]
                                  + self.edit_text[self.edit_cursor:])
                self.edit_cursor -= 1
                self.dirty = True
        elif name == "DELETE":
            self.edit_text = (self.edit_text[:self.edit_cursor]
                              + self.edit_text[self.edit_cursor + 1:])
            self.dirty = True
        elif name == "INSERT":
            self.insert_mode = not self.insert_mode
            self.status = "Insert on." if self.insert_mode else "Overwrite on."
        elif name == "ENTER":
            field = self._field()
            if (self.mode == "enter" and field is not None
                    and self.field_index == len(self.database.fields) - 1):
                if self.save():
                    self._start_new()
            else:
                self._move_field(1, wrap=True)
        elif name == "PGUP":
            self._move_record(-1)
        elif name == "PGDN":
            self._move_record(1)
        elif name == "SPACE" or len(name) == 1 or character(key):
            if name in ("SPACE",) or character(key):
                self._typed(key)

    # -- mouse -----------------------------------------------------------
    def click_action(self, action: str, *, double: bool = False) -> None:
        kind, _, value = action.partition(":")
        if kind == "row" and value.isdigit():
            self._goto_record(int(value))
        elif kind == "field" and value.isdigit():
            if self.mode in ("enter", "change"):
                self._commit_field()
            self.field_index = max(0, min(len(self.database.fields) - 1, int(value)))
            self._load_field()
        elif kind == "col" and value.isdigit():
            self.browse_field = int(value)

    def view(self) -> View:
        from . import record_screens

        if self.memo is not None:
            return record_screens.memo_overlay(self, self.theme)
        if self.mode == "browse":
            return record_screens.browse_screen(self, self.theme)
        return record_screens.form_screen(self, self.theme)


def _typed_char(key: Key) -> str:
    text = character(key)
    if not text:
        return ""
    if len(text) == 1 and text.isalpha():
        return text if key.shift else text.lower()
    return text


__all__ = ["MODE_KEYS", "MODE_TITLES", "MemoEditor", "RecordSession"]
