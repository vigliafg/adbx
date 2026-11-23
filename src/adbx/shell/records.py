"""Modalità record: View, Enter, Change, Browse, memo e clipboard.

Il session object è l'unico proprietario dello stato di una visita ai dati.
Il controller gli passa i tasti; lui produce una `View` tramite
`record_screens`. Nessun widget, nessuna copia del database in RAM.

Le regole di tastiera seguono l'inventario del manuale: TAB sposta di dieci
record, CTRL-HOME/END vanno al primo/ultimo, ALT-D/ALT-U cancellano e
richiamano, ALT-M apre il memo, ALT-F5/ALT-F6 copiano e incollano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..cell.buffer import STATUS_ROW
from ..data import indexing
from ..data import rules as field_rules
from ..data.fields import Field, FieldError, format_value, parse_value
from ..data.indexing import (
    RECORD_NUMBER,
    SHOW_ALL,
    SHOW_NOT_DELETED,
    RangeSettings,
)
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
    "view": [("F1", "Help"), ("F", "Find"), ("L", "Locate"), ("I", "Index"),
             ("R", "Range"), ("S", "Replace"), ("F10", "Continue"),
             ("F7", "Show deleted"), ("Alt-M", "Memo"), ("Alt-D", "Delete"),
             ("Alt-U", "Undelete")],
    "browse": [("F1", "Help"), ("F", "Find"), ("L", "Locate"), ("I", "Index"),
               ("R", "Range"), ("F10", "Continue"), ("F7", "Show deleted"),
               ("Alt-M", "Memo"), ("Alt-D", "Delete"), ("Alt-U", "Undelete")],
    "enter": [("F1", "Help"), ("F3", "Choices"), ("F10", "Save"),
              ("ESC", "Cancel"), ("Alt-M", "Memo"), ("Alt-F5", "Copy"),
              ("Alt-F6", "Paste")],
    "change": [("F1", "Help"), ("F3", "Choices"), ("F10", "Save"),
               ("ESC", "Cancel"), ("Alt-M", "Memo"), ("Alt-F5", "Copy"),
               ("Alt-F6", "Paste")],
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
class LookupState:
    """Finestra di lookup aperta sul campo corrente."""

    field_name: str
    choices: field_rules.LookupChoices
    selected: int = 0
    path: tuple[str, ...] = ()
    search: str = ""
    auto: bool = False

    def move(self, delta: int) -> None:
        if self.choices.values:
            self.selected = max(0, min(len(self.choices.values) - 1,
                                       self.selected + delta))

    @property
    def choice(self) -> str:
        if 0 <= self.selected < len(self.choices.values):
            return self.choices.values[self.selected]
        return ""


@dataclass
class LocateState:
    """Ricerca di un testo in un insieme di campi (Locate a record)."""

    text: str
    fields: list[str] = field(default_factory=list)
    start: int = 0
    found: int | None = None
    memo_hit: bool = False


@dataclass
class RecordSession:
    database: Database
    mode: str
    theme: Theme = NEWPORT
    clipboard: list[str] = field(default_factory=lambda: [""])
    show_deleted: bool = False
    status: str = ""
    request: str = ""
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
    range_settings: RangeSettings | None = None
    find_history: list[str] = field(default_factory=list)
    locate: LocateState | None = None
    lookup: LookupState | None = None
    double: tuple[str, str] | None = None
    rule_map: dict[str, field_rules.FieldRule] = field(
        init=False, default_factory=dict)
    _seqs: list[int] = field(init=False, default_factory=list)
    _browse_rows: list[tuple[int, bool, dict[str, str]]] | None = field(
        init=False, default=None)
    _value_cache: dict[int, dict[str, str]] | None = field(
        init=False, default=None)

    def __post_init__(self) -> None:
        if self.mode not in MODE_TITLES:
            raise ValueError(f"Unknown record mode: {self.mode}")
        self.rule_map = self.database.field_rules()
        if self.range_settings is None:
            self.range_settings = self.database.current_range.copy()
        elif isinstance(self.range_settings, RangeSettings):
            self.range_settings = self.range_settings.copy()
        if self.show_deleted:
            self.range_settings.show = SHOW_ALL
        self.show_deleted = self.range_settings.show != SHOW_NOT_DELETED
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

    @property
    def is_search_list(self) -> bool:
        return self.database.primary_index.startswith(indexing.SEARCH_PREFIX)

    @property
    def search_out_of_date(self) -> bool:
        if not self.is_search_list:
            return False
        search = indexing.get_search_list(
            self.database, self.range_settings.search_id)
        return search is not None and search.out_of_date(self.database)

    @property
    def order_indicator(self) -> str:
        return "D" if self.range_settings.order == indexing.ORDER_DESCENDING else "A"

    def apply_range(self, settings: RangeSettings | None = None) -> None:
        keep = self.current_seq
        self.range_settings = ((settings or self.database.current_range).copy()
                               if settings is not None
                               else self.database.current_range.copy())
        self.show_deleted = self.range_settings.show != SHOW_NOT_DELETED
        self._reload(keep=keep)
        if self.mode == "change":
            self._load_record()
        self.status = "Range applied."

    # -- regole di campo -------------------------------------------------
    def _rule(self, field: Field | None) -> field_rules.FieldRule | None:
        if field is None:
            return None
        return self.rule_map.get(field.name)

    def field_prompt(self) -> str:
        field = self._field()
        rule = self._rule(field)
        return rule.prompt if rule and rule.prompt else ""

    def _is_calculated(self, field: Field) -> bool:
        rule = self._rule(field)
        return bool(rule and rule.value in ("Calculated", "Summary"))

    def _recalculate(self) -> None:
        if self.mode in ("enter", "change"):
            field_rules.recalculate(self.rule_map, self.database, self.draft)

    def _apply_new_record_rules(self) -> None:
        for definition in self.database.fields:
            rule = self._rule(definition)
            if rule is None or definition.is_memo \
                    or self._is_calculated(definition):
                continue
            if rule.default_mode != "None":
                value = field_rules.default_value(rule, self.database,
                                                  self.draft)
                if value:
                    self.draft[definition.name] = value
            if rule.increment == "Records":
                self.draft[definition.name] = field_rules.next_increment(
                    rule, self.database, definition)
        self._recalculate()

    def _open_lookup(self, *, auto: bool = False) -> None:
        field = self._field()
        rule = self._rule(field)
        if field is None or rule is None or not rule.lookup:
            return
        choices = field_rules.lookup_choices(rule, self.database, self.draft)
        if choices.empty:
            self.status = "There are no lookup values."
            return
        self.lookup = LookupState(field.name, choices, auto=auto)
        self.status = ""

    def _maybe_open_lookup(self) -> None:
        if self.lookup is not None or self.mode not in ("enter", "change"):
            return
        field = self._field()
        rule = self._rule(field)
        if rule is None or not rule.lookup:
            return
        if field_rules.auto_popup(rule, self.database, self.draft,
                                  mode=self.mode):
            self._open_lookup(auto=True)

    def _handle_lookup(self, key: Key) -> None:
        state = self.lookup
        assert state is not None
        rule = self._rule(self._field())
        name = key.name
        if name == "ESC":
            self.lookup = None
            self.status = "Lookup cancelled."
            return
        if name == "UP":
            state.move(-1)
        elif name == "DOWN":
            state.move(1)
        elif name == "PGUP":
            state.move(-10)
        elif name == "PGDN":
            state.move(10)
        elif name in ("LEFT", "BACKSPACE") and state.path:
            state.path = state.path[:-1]
            state.selected = 0
            state.search = ""
            state.choices = field_rules.lookup_choices(
                rule, self.database, self.draft, state.path)
        elif name == "ENTER":
            choice = state.choice
            if not choice:
                return
            if rule is not None and rule.lookup_source == "Advanced" \
                    and rule.advanced == "Cascading table":
                _value, endpoint = field_rules.cascading_value(
                    rule, state.path, choice)
                if not endpoint:
                    state.path = state.path + (choice,)
                    state.selected = 0
                    state.search = ""
                    state.choices = field_rules.lookup_choices(
                        rule, self.database, self.draft, state.path)
                    return
            filled = field_rules.lookup_fill(
                rule, self.database, self.draft, choice, state.path)
            self.draft.update(filled)
            self.lookup = None
            self.dirty = True
            self._recalculate()
            self._load_field()
            self.status = "Lookup value entered."
            self._maybe_auto_advance()
        else:
            text = character(key)
            if text:
                if len(text) == 1 and text.isalpha() and not key.shift:
                    text = text.lower()
                state.search += text
                needle = state.search.upper()
                for index, value in enumerate(state.choices.values):
                    if value.upper().startswith(needle):
                        state.selected = index
                        break

    def _reload(self, keep: int | None = None) -> None:
        try:
            self._seqs = indexing.ordered_sequences(
                self.database, self.range_settings)
        except indexing.IndexError_ as exc:
            self.status = str(exc)
            self._seqs = []
        if keep is not None and keep in self._seqs:
            self.index = self._seqs.index(keep)
        self.index = max(0, min(self.index, max(0, len(self._seqs) - 1)))
        self._browse_rows = None
        self._value_cache = None
        self._fix_top()

    def values_for(self, seq: int) -> dict[str, str]:
        """Valori di un record, con una cache per la sessione."""
        if self._value_cache is None:
            self._value_cache = {
                item_seq: values
                for item_seq, _deleted, values in self.database.iter_values(
                    include_deleted=True)
            }
        return self._value_cache.get(seq, self.database.read(seq))

    def _fix_top(self) -> None:
        visible = self.page_rows
        if self.index < self.top:
            self.top = self.index
        elif self.index >= self.top + visible:
            self.top = self.index - visible + 1
        self.top = max(0, min(self.top, max(0, len(self._seqs) - visible)))

    def _load_record(self) -> None:
        self.lookup = None
        self.double = None
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
        self.double = None
        self.lookup = None
        self._apply_new_record_rules()
        self.field_index = self._first_usable(0, 1)
        self._load_field()
        self._maybe_open_lookup()

    def _first_usable(self, start: int, direction: int) -> int:
        count = len(self.database.fields)
        if not count:
            return 0
        index = start
        for _step in range(count):
            field = self.database.fields[index]
            rule = self._rule(field)
            if not self._is_calculated(field) and not (
                    rule is not None
                    and field_rules.should_skip(rule, self.database,
                                                self.draft)):
                return index
            index = (index + direction) % count
        return start

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
        value = self.draft.get(field.name, "")
        rule = self._rule(field)
        if field.is_memo:
            self.edit_text = ""
        elif rule is not None and rule.template:
            self.edit_text = field_rules.template_display(rule.template, value)
        else:
            self.edit_text = format_value(field, value)
        self.edit_cursor = len(self.edit_text)
        if rule is not None and rule.template:
            positions = field_rules.editable_positions(rule.template)
            empty = next((position for position in positions
                          if position >= len(self.edit_text)
                          or not self.edit_text[position].strip()), None)
            self.edit_cursor = empty if empty is not None else len(self.edit_text)

    def _commit_field(self) -> bool:
        field = self._field()
        if field is None or field.is_memo:
            return True
        if self.mode not in ("enter", "change") or self._is_calculated(field):
            return True
        rule = self._rule(field)
        text = self.edit_text
        if rule is not None and rule.template and \
                field_rules.template_is_blank(rule.template, text):
            text = ""
        if rule is not None and rule.mask:
            error = field_rules.mask_error(rule.template, rule.mask, text)
            if error:
                if not rule.allow_exceptions:
                    self.status = error
                    return False
                self.status = error + " Allowed as an exception."
        try:
            value = parse_value(field, text)
        except FieldError as exc:
            self.status = str(exc)
            return False
        if rule is not None and rule.case != "None":
            value = field_rules.apply_case(value, rule.case)
        if rule is not None and field_rules.double_entry_required(
                rule, self.database, self.draft):
            if self.double is None or self.double[0] != field.name:
                self.double = (field.name, value)
                self.draft[field.name] = value
                self.edit_text = ""
                self.edit_cursor = 0
                self.status = f"Enter {field.name} again to confirm."
                return False
            first = self.double[1]
            self.double = None
            if value.strip() != first.strip():
                self.draft[field.name] = ""
                self.edit_text = ""
                self.edit_cursor = 0
                self.status = ("The two entries do not match. "
                               "Enter the value again.")
                return False
        previous = self.draft.get(field.name, "")
        self.draft[field.name] = value
        if value != previous:
            self.dirty = True
        if rule is not None and rule.template:
            self.edit_text = field_rules.template_display(rule.template, value)
        else:
            self.edit_text = format_value(field, value)
        self.edit_cursor = min(self.edit_cursor, len(self.edit_text))
        if rule is not None:
            error = field_rules.validation_error(rule, self.database,
                                                 self.draft)
            if error:
                self.status = error
                return False
            error = field_rules.lookup_validation_error(rule, self.database,
                                                        self.draft)
            if error:
                if rule.lookup_allow_exceptions:
                    self.status = error + " Allowed as an exception."
                else:
                    self.status = error
                    return False
        self._recalculate()
        return True

    def _move_field(self, delta: int, *, wrap: bool = False) -> None:
        if not self._commit_field():
            return
        field = self._field()
        rule = self._rule(field)
        if field is not None and delta > 0 and rule is not None and \
                field_rules.missing_required(rule, self.database, self.draft):
            self.status = f"{field.name} is required."
            return
        count = len(self.database.fields)
        if count == 0:
            return
        target = self.field_index + delta
        if wrap:
            target %= count
        else:
            target = max(0, min(count - 1, target))
        direction = 1 if delta > 0 else -1
        for _step in range(count):
            candidate = self.database.fields[target]
            candidate_rule = self._rule(candidate)
            calculated = self._is_calculated(candidate)
            skipped = (candidate_rule is not None and
                       field_rules.should_skip(candidate_rule, self.database,
                                               self.draft))
            if not calculated and not skipped:
                break
            next_target = target + direction
            if wrap:
                next_target %= count
            elif next_target < 0 or next_target >= count:
                return
            target = next_target
        else:
            return
        if target != self.field_index:
            self.field_index = target
            self.lookup = None
            self._load_field()
            self._maybe_open_lookup()

    def _maybe_auto_advance(self) -> None:
        field = self._field()
        rule = self._rule(field)
        if field is None or rule is None or not rule.auto_advance:
            return
        if rule.template:
            positions = field_rules.editable_positions(rule.template)
            if positions and all(
                    position < len(self.edit_text)
                    and self.edit_text[position].strip()
                    for position in positions):
                self._move_field(1, wrap=True)
            return
        if len(self.edit_text) >= field.length:
            self._move_field(1, wrap=True)

    def _typed(self, key: Key) -> None:
        if self.mode not in ("enter", "change"):
            return
        field = self._field()
        if field is None or field.is_memo or self._is_calculated(field):
            return
        text = _typed_char(key)
        if not text:
            return
        rule = self._rule(field)
        if rule is not None and rule.template:
            self._typed_template(field, rule, text)
            return
        if rule is not None and rule.mask and self.edit_cursor < len(rule.mask):
            mask_char = rule.mask[self.edit_cursor]
            if not _mask_accepts(mask_char, text):
                if not rule.allow_exceptions:
                    self.status = _mask_message(mask_char)
                    return
                self.status = _mask_message(mask_char) + " Allowed as an exception."
        if self.insert_mode:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor:])
        else:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor + 1:])
        self.edit_cursor += len(text)
        self.dirty = True
        self._maybe_auto_advance()

    def _backspace_template(self, rule: field_rules.FieldRule) -> None:
        positions = field_rules.editable_positions(rule.template)
        candidates = [position for position in positions
                      if position < self.edit_cursor
                      and position < len(self.edit_text)
                      and self.edit_text[position].strip()]
        if not candidates:
            return
        target = candidates[-1]
        chars = list(self.edit_text)
        chars[target] = " "
        self.edit_text = "".join(chars)
        self.edit_cursor = target
        self.dirty = True

    def _delete_template(self, rule: field_rules.FieldRule) -> None:
        positions = field_rules.editable_positions(rule.template)
        target = next((position for position in positions
                       if position >= self.edit_cursor
                       and position < len(self.edit_text)
                       and self.edit_text[position].strip()), None)
        if target is None:
            return
        chars = list(self.edit_text)
        chars[target] = " "
        self.edit_text = "".join(chars)
        self.dirty = True

    def _typed_template(self, field: Field, rule: field_rules.FieldRule,
                        text: str) -> None:
        template = rule.template
        positions = field_rules.editable_positions(template)
        if not positions:
            return
        current = self.edit_text
        if len(current) != len(template):
            current = field_rules.template_display(template, current)
        target = next((position for position in positions
                       if position >= self.edit_cursor), None)
        if target is None:
            target = next((position for position in positions
                           if not current[position].strip()), None)
        if target is None:
            return
        mask_char = field_rules.mask_slots(template, rule.mask).get(target, "")
        if mask_char and not _mask_accepts(mask_char, text):
            if not rule.allow_exceptions:
                self.status = _mask_message(mask_char)
                return
            self.status = _mask_message(mask_char) + " Allowed as an exception."
        chars = list(current)
        chars[target] = text
        self.edit_text = "".join(chars)
        self.edit_cursor = target + 1
        self.dirty = True
        self._maybe_auto_advance()

    # -- salvataggio -----------------------------------------------------
    def _duplicate_indexes(self, values: dict[str, str]
                           ) -> list[tuple[indexing.IndexDefinition, bool]]:
        """Indici attached il cui key value è già usato da un altro record."""
        duplicates: list[tuple[indexing.IndexDefinition, bool]] = []
        for definition in indexing.indexes(self.database, attached=True):
            if definition.allow == indexing.ALLOW_ALL:
                continue
            try:
                key = indexing.index_key(self.database, definition, values)
            except indexing.IndexError_:
                continue
            marker = key if definition.case_sensitive else key.upper()
            for seq, deleted, other in self.database.iter_values(
                    include_deleted=False):
                if seq == self.seq:
                    continue
                if not indexing.index_filter_passes(
                        self.database, definition, other, seq=seq,
                        deleted=deleted):
                    continue
                try:
                    other_key = indexing.index_key(
                        self.database, definition, other, seq=seq,
                        deleted=deleted)
                except indexing.IndexError_:
                    continue
                other_marker = (other_key if definition.case_sensitive
                                else other_key.upper())
                if other_marker == marker:
                    duplicates.append(
                        (definition,
                         definition.allow == indexing.ALLOW_EXCEPTIONS))
                    break
        return duplicates

    def save(self) -> bool:
        if self.mode not in ("enter", "change"):
            return True
        if self.double is not None:
            self.status = (f"Enter {self.double[0]} again to confirm, "
                           "then save.")
            return False
        if not self._commit_field():
            return False
        self._recalculate()
        for definition in self.database.fields:
            rule = self._rule(definition)
            if rule is None or definition.is_memo:
                continue
            if field_rules.missing_required(rule, self.database, self.draft):
                self.status = f"{definition.name} is required."
                return False
            error = field_rules.validation_error(rule, self.database,
                                                 self.draft)
            if error:
                self.status = f"{definition.name}: {error}"
                return False
            if rule.mask and not rule.allow_exceptions:
                error = field_rules.mask_error(
                    rule.template, rule.mask,
                    self.draft.get(definition.name, ""))
                if error:
                    self.status = f"{definition.name}: {error}"
                    return False
            error = field_rules.lookup_validation_error(rule, self.database,
                                                        self.draft)
            if error and not rule.lookup_allow_exceptions:
                self.status = f"{definition.name}: {error}"
                return False
        if not any((self.draft.get(field.name) or "").strip()
                   for field in self.database.fields):
            self.status = "Enter at least one value before saving."
            return False
        # Increment = Updates: +1 a ogni salvataggio.
        for definition in self.database.fields:
            rule = self._rule(definition)
            if rule is not None and rule.increment == "Updates" \
                    and not definition.is_memo:
                self.draft[definition.name] = field_rules.increment_value(
                    definition, self.draft.get(definition.name, ""),
                    rule.template)
        duplicates = self._duplicate_indexes(self.draft)
        blocked = [definition.name for definition, exception in duplicates
                   if not exception]
        if blocked:
            self.status = ("Duplicate key value for index "
                           + ", ".join(blocked) + ".")
            return False
        warning = (""
                   if not duplicates else
                   " Duplicate key allowed for index "
                   + ", ".join(definition.name
                               for definition, _exception in duplicates)
                   + ".")
        old_values = (self.database.read(self.seq)
                      if self.seq is not None else {})
        try:
            if self.seq is None:
                self.seq = self.database.append(self.draft)
                self.status = f"Record {self.seq} added." + warning
            else:
                self.database.update(self.seq, self.draft)
                self.status = f"Record {self.seq} saved." + warning
        except WorkspaceError as exc:
            self.status = str(exc)
            return False
        warnings: list[str] = []
        for definition in self.database.fields:
            rule = self._rule(definition)
            if rule is not None and rule.post_data:
                warnings.extend(field_rules.post_values(
                    rule, self.database, old_values, self.draft, rule))
        if warnings:
            self.status += " " + " ".join(warnings)
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
        if self.show_deleted:
            self.range_settings.show = SHOW_NOT_DELETED
        else:
            self.range_settings.show = SHOW_ALL
        self.show_deleted = self.range_settings.show != SHOW_NOT_DELETED
        self.database.save_current_range(self.range_settings)
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

    # -- find, locate, sostituzione, duplicati ---------------------------
    def browse_rows(self) -> list[tuple[int, bool, dict[str, str]]]:
        if self._browse_rows is None:
            wanted = set(self._seqs)
            order = {seq: position for position, seq in enumerate(self._seqs)}
            rows = [item for item in self.database.browse(include_deleted=True)
                    if item[0] in wanted]
            rows.sort(key=lambda item: order.get(item[0], len(order)))
            self._browse_rows = rows
        return self._browse_rows

    def find_label(self) -> str:
        primary = self.database.primary_index
        if primary.startswith(indexing.SEARCH_PREFIX):
            search = indexing.get_search_list(
                self.database, self._search_id(primary))
            if search is not None and (search.sort_expression or search.sort_rows):
                if search.sort_expression:
                    return search.sort_expression
                return "+".join(name for name, _direction in search.sort_rows)
            return "RECORD NUMBER"
        if primary in (RECORD_NUMBER, indexing.SEARCH_LIST):
            return "RECORD NUMBER"
        definition = indexing.find_index(self.database, primary)
        return definition.label if definition is not None else primary

    def _search_id(self, primary: str) -> int | None:
        try:
            return int(primary[len(indexing.SEARCH_PREFIX):])
        except ValueError:
            return None

    def _find_key(self, seq: int) -> str:
        """Chiave del record secondo l'indice primario, per Find."""
        primary = self.database.primary_index
        values = self.values_for(seq)
        if primary.startswith(indexing.SEARCH_PREFIX):
            search = indexing.get_search_list(
                self.database, self._search_id(primary))
            if search is not None and search.sort_expression:
                from ..data.expressions import Context, evaluate, key_text
                context = Context(
                    fields=self.database.fields, values=values,
                    pattern=self.database.workspace.pattern_mode, padded=True,
                    seq=seq, count=self.database.count(include_deleted=True))
                return key_text(evaluate(search.sort_expression, context))
            if search is not None and search.sort_rows:
                field = self.database.field(search.sort_rows[0][0])
                from ..data.expressions import Context, field_value, value_to_text
                context = Context(
                    fields=self.database.fields, values=values,
                    pattern=self.database.workspace.pattern_mode, seq=seq,
                    count=self.database.count(include_deleted=True))
                return value_to_text(field_value(context, field.name))
            return str(seq)
        if primary in (RECORD_NUMBER, indexing.SEARCH_LIST):
            return str(seq)
        definition = indexing.find_index(self.database, primary)
        if definition is None:
            return str(seq)
        return indexing.index_key(self.database, definition, values, seq=seq)

    def find(self, text: str) -> bool:
        """Find: primo record la cui chiave è uguale o successiva al testo."""
        if self.mode not in ("view", "browse", "change"):
            self.status = "Find is available in View, Browse and Change."
            return False
        needle = (text or "").strip()
        if not needle:
            return False
        if needle not in self.find_history:
            self.find_history.insert(0, needle)
            del self.find_history[20:]
        if self.database.primary_index in (RECORD_NUMBER, indexing.SEARCH_LIST) \
                or self.find_label() == "RECORD NUMBER":
            try:
                target = int(needle)
            except ValueError:
                self.status = "Enter a record number to find."
                return False
            for position, seq in enumerate(self._seqs):
                if seq >= target:
                    self._set_position(position)
                    self.status = f"Record {seq}."
                    return True
            if self._seqs:
                self._set_position(len(self._seqs) - 1)
            self.status = "No record at or after that number."
            return False
        needle_key = needle.upper()
        closest = 0
        for position, seq in enumerate(self._seqs):
            key = self._find_key(seq)
            if key.upper() >= needle_key:
                self._set_position(position)
                self.status = f"Find: {key.rstrip() or needle}"
                return True
            closest = position
        if self._seqs:
            self._set_position(closest)
        self.status = "No exact match; showing the closest record."
        return False

    def _set_position(self, position: int) -> None:
        self.index = max(0, min(len(self._seqs) - 1, position))
        self._fix_top()
        if self.mode == "change":
            self._load_record()

    def start_locate(self, text: str, fields: list[str]) -> bool:
        needle = (text or "").strip()
        if not needle:
            self.status = "Enter a string to locate."
            return False
        if not fields:
            self.status = "Select at least one field."
            return False
        self.locate = LocateState(needle, fields, start=0)
        return self.next_locate()

    def next_locate(self) -> bool:
        state = self.locate
        if state is None:
            return False
        needle = state.text.upper()
        for position in range(state.start, len(self._seqs)):
            seq = self._seqs[position]
            values = self.values_for(seq)
            for name in state.fields:
                field = self.database.fields[
                    [item.name for item in self.database.fields].index(name)]
                value = values.get(name, "")
                if needle in value.upper():
                    state.start = position + 1
                    state.found = position
                    state.memo_hit = field.is_memo
                    self._set_position(position)
                    self.status = (f"Locate: {name}"
                                   + (" (Memo)" if field.is_memo else "")
                                   + " - F3 next, ESC exit")
                    return True
        state.start = len(self._seqs)
        self.status = "No more records match the locate string."
        return False

    def cancel_locate(self) -> None:
        self.locate = None
        self.status = "Locate ended."

    def replace_all(self, find: str, replacement: str,
                    fields: list[str]) -> int:
        """Sostituisce ogni occorrenza nei campi scelti (memo esclusi)."""
        if self.mode != "view":
            self.status = "Search and replace is available in View mode."
            return 0
        if not find:
            self.status = "Enter a string to replace."
            return 0
        total = 0
        for seq in list(self._seqs):
            values = self.database.read(seq)
            changed = False
            for name in fields:
                field = self.database.field(name)
                if field.is_memo or not values.get(name):
                    continue
                new_value, count = re.subn(
                    re.escape(find), replacement, values[name], flags=re.IGNORECASE)
                if not count:
                    continue
                values[name] = new_value[:field.length]
                total += count
                changed = True
            if changed:
                self.database.update(seq, values)
        if total:
            self._persist()
            self._reload()
        self.status = f"Replaced {total} occurrence(s)."
        return total

    def delete_duplicates(self) -> int:
        """Marca cancellati i duplicati della chiave dell'indice primario."""
        primary = self.database.primary_index
        definition = None
        if primary.startswith(indexing.SEARCH_PREFIX):
            self.status = "Select an index before deleting duplicates."
            return 0
        if primary in (RECORD_NUMBER, indexing.SEARCH_LIST):
            self.status = "Select an index before deleting duplicates."
            return 0
        definition = indexing.find_index(self.database, primary)
        if definition is None:
            self.status = f"Index {primary} not found."
            return 0
        seen: set[str] = set()
        removed = 0
        for seq in list(self._seqs):
            values = self.values_for(seq)
            key = indexing.index_key(self.database, definition, values, seq=seq)
            marker = key if definition.case_sensitive else key.upper()
            if marker in seen:
                self.database.delete(seq)
                removed += 1
            else:
                seen.add(marker)
        if removed:
            self._persist()
            self._reload()
        self.status = f"{removed} duplicate record(s) marked deleted."
        return removed

    # -- tasti -----------------------------------------------------------
    def handle(self, key: Key) -> None:
        self.status = ""
        self.help_topic = "browse" if self.mode == "browse" else "records"
        if self.lookup is not None:
            self._handle_lookup(key)
            return
        if self.memo is not None:
            action = self.memo.handle(key)
            if action:
                self._close_memo(action)
            return
        name = key.name
        if self.locate is not None:
            if name == "F3":
                self.next_locate()
                return
            if name == "ESC":
                self.cancel_locate()
                return
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
        if self.mode in ("view", "browse") and not key.ctrl:
            if name == "F":
                self.request = "find"
                return
            if name == "L":
                self.request = "locate"
                return
            if name == "I":
                self.request = "index"
                return
            if name == "R":
                self.request = "range"
                return
            if name == "S" and self.mode == "view":
                self.request = "replace"
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
            field = self._field()
            rule = self._rule(field)
            if rule is not None and rule.template:
                self._backspace_template(rule)
            elif self.edit_cursor:
                self.edit_text = (self.edit_text[:self.edit_cursor - 1]
                                  + self.edit_text[self.edit_cursor:])
                self.edit_cursor -= 1
                self.dirty = True
        elif name == "DELETE":
            field = self._field()
            rule = self._rule(field)
            if rule is not None and rule.template:
                self._delete_template(rule)
            else:
                self.edit_text = (self.edit_text[:self.edit_cursor]
                                  + self.edit_text[self.edit_cursor + 1:])
                self.dirty = True
        elif name == "INSERT":
            self.insert_mode = not self.insert_mode
            self.status = "Insert on." if self.insert_mode else "Overwrite on."
        elif name == "F3":
            self._open_lookup()
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
        if kind == "lookup" and value.isdigit() and self.lookup is not None:
            self.lookup.selected = max(0, min(len(self.lookup.choices.values) - 1,
                                              int(value)))
            if double:
                self._handle_lookup(Key("ENTER"))
            return
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

        if self.lookup is not None:
            return record_screens.lookup_overlay(self, self.theme)
        if self.memo is not None:
            return record_screens.memo_overlay(self, self.theme)
        if self.mode == "browse":
            return record_screens.browse_screen(self, self.theme)
        return record_screens.form_screen(self, self.theme)


def _mask_accepts(mask_char: str, text: str) -> bool:
    if mask_char == "9":
        return text.isdigit()
    if mask_char == "A":
        return text.isalpha() and text.isupper()
    if mask_char == "a":
        return text.isalpha()
    return True


def _mask_message(mask_char: str) -> str:
    if mask_char == "9":
        return "This position accepts digits only."
    if mask_char == "A":
        return "This position accepts uppercase letters only."
    if mask_char == "a":
        return "This position accepts letters only."
    return ""


def _typed_char(key: Key) -> str:
    text = character(key)
    if not text:
        return ""
    if len(text) == 1 and text.isalpha():
        return text if key.shift else text.lower()
    return text


__all__ = ["LocateState", "MODE_KEYS", "MODE_TITLES", "MemoEditor",
           "RecordSession"]
