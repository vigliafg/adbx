"""Field rules: editor a due finestre e tabelle di supporto.

La schermata segue il capitolo 10 del manuale: in alto i campi, in basso le
regole del campo attivo su tre pagine. Le tabelle di lookup, il mapping, le
regole di post data e le cascate hanno un editor dedicato aperto con F7/F8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW, Cell, CellBuffer
from ..data.rules import (
    ADVANCED_OPTIONS,
    AUTO_POPUP_MODES,
    CASE_MODES,
    DEFAULT_MODES,
    DOUBLE_ENTRY_MODES,
    INCREMENT_MODES,
    LOOKUP_LOCATIONS,
    LOOKUP_SOURCES,
    LOOKUP_VALIDATIONS,
    MAX_LOOKUP_COLUMNS,
    POST_MODES,
    REQUIRED_MODES,
    VALUE_MODES,
    CascadingEntry,
    ConditionalDatabase,
    ConditionalGroup,
    FieldRule,
    LookupTable,
    MappingRow,
    PostingRule,
)
from ..data.workspace import Database
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

RULE_KEYS = [("F1", "Help"), ("F5", "Del rule"), ("F7", "Table/map"),
             ("F8", "Posting"), ("F9", "Switch"),
             ("F10", "Cont"), ("ESC", "Cancel")]
FIELD_KEYS = [("F1", "Help"), ("F5", "Delete rule"), ("F9", "Define rule"),
              ("F10", "Continue"), ("ESC", "Cancel")]
GRID_KEYS = [("F2", "Fields"), ("F5", "Delete row"), ("F6", "Insert row"),
             ("F10", "Continue"), ("ESC", "Cancel")]
RULE_TOP = 15
FIELD_TOP = 3


@dataclass(frozen=True)
class RuleRow:
    key: str
    label: str
    kind: str = "text"
    choices: tuple[str, ...] = ()


def _rows_page1(rule: FieldRule, field) -> list[RuleRow]:
    rows = [RuleRow("value", "Value", "cycle", VALUE_MODES)]
    if rule.value == "Calculated":
        rows.append(RuleRow("expression", "Expression"))
    if field.type == "C":
        rows.extend([RuleRow("case", "Case Convert", "cycle", CASE_MODES),
                     RuleRow("template", "Template"),
                     RuleRow("mask", "Mask")])
        if rule.mask:
            rows.append(RuleRow("allow_exceptions", "Allow exceptions",
                                "bool"))
    rows.append(RuleRow("default_mode", "Default Mode", "cycle",
                        DEFAULT_MODES))
    if rule.default_mode != "None":
        rows.append(RuleRow("default", "Default"))
    if field.type in ("C", "N", "D"):
        rows.append(RuleRow("increment", "Increment", "cycle",
                            INCREMENT_MODES))
    rows.append(RuleRow("auto_advance", "Auto-advance", "bool"))
    rows.append(RuleRow("prompt", "Prompt"))
    return rows


def _rows_page2(rule: FieldRule, field) -> list[RuleRow]:
    rows = [RuleRow("required", "Required", "cycle", REQUIRED_MODES)]
    if rule.required == "Expression":
        rows.append(RuleRow("required_expression", "Required Expn"))
    rows.append(RuleRow("validation", "Validation Expn"))
    if rule.validation:
        rows.append(RuleRow("validation_message", "Validation Msg"))
    rows.append(RuleRow("double_entry", "Double Entry", "cycle",
                        DOUBLE_ENTRY_MODES))
    if rule.double_entry == "Expression":
        rows.append(RuleRow("double_entry_expression", "Dbl Entry Expn"))
    rows.append(RuleRow("skip_expression", "Skip Expression"))
    rows.append(RuleRow("post_data", "Post data", "bool"))
    if rule.post_data:
        rows.append(RuleRow("postings", f"Posting rules ({len(rule.postings)})",
                            "hint"))
    return rows


def _rows_page3(rule: FieldRule, field) -> list[RuleRow]:
    rows = [RuleRow("lookup", "Lookup", "bool")]
    if not rule.lookup:
        return rows
    rows.append(RuleRow("lookup_validation", "Lookup Validation", "cycle",
                        LOOKUP_VALIDATIONS))
    if rule.lookup_validation in ("Exists", "Doesn't Exist"):
        rows.append(RuleRow("lookup_allow_exceptions", "Allow Exceptions",
                            "bool"))
    rows.extend([
        RuleRow("location", "Location", "cycle", LOOKUP_LOCATIONS),
        RuleRow("window_rows", "Rows in Window"),
        RuleRow("auto_popup", "Auto Pop-up", "cycle", AUTO_POPUP_MODES),
        RuleRow("lookup_source", "Lookup Source", "cycle", LOOKUP_SOURCES),
    ])
    if rule.auto_popup == "Expression":
        rows.extend([RuleRow("popup_entry", "Entry Expn"),
                     RuleRow("popup_exit", "Exit Expn")])
    if rule.lookup_source == "Database":
        rows.extend([
            RuleRow("lookup_database", "Lookup Database"),
            RuleRow("linking_index", "Linking Index"),
            RuleRow("display_index", "Display Index"),
        ])
    if rule.lookup_source == "Advanced":
        rows.append(RuleRow("advanced", "Advanced option", "cycle",
                            ADVANCED_OPTIONS))
        rows.append(RuleRow("lookup_database", "Lookup Database"))
        rows.append(RuleRow("linking_index", "Linking Index"))
        rows.append(RuleRow("display_index", "Display Index"))
    rows.append(RuleRow("editor", "F7 edit table/mapping", "hint"))
    return rows


def rule_rows(rule: FieldRule, field, page: int) -> list[RuleRow]:
    if field.is_memo:
        return [RuleRow("prompt", "Prompt")]
    if page == 1:
        return _rows_page1(rule, field)
    if page == 2:
        return _rows_page2(rule, field)
    return _rows_page3(rule, field)


@dataclass
class RulesSession:
    database: Database
    theme: Theme = NEWPORT
    rules: dict[str, FieldRule] = field(init=False, default_factory=dict)
    deleted: set[str] = field(init=False, default_factory=set)
    field_index: int = 0
    window: str = "fields"
    page: int = 1
    row: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    editing: bool = False
    picker: Picker | None = None
    picker_kind: str = ""
    editor: Any = None
    status: str = ""
    close: bool = False
    saved: bool = False
    help_topic: str = "field_rules"

    def __post_init__(self) -> None:
        self.rules = self.database.field_rules()
        self.field_index = 0
        self.window = "fields"
        self.page = 1
        self.row = 0

    # -- stato -----------------------------------------------------------
    @property
    def title(self) -> str:
        return f"Field Rules - {self.database.name}"

    @property
    def fields(self) -> tuple:
        return self.database.fields

    @property
    def current_field(self):
        if not self.fields:
            return None
        return self.fields[max(0, min(self.field_index, len(self.fields) - 1))]

    def current_rule(self, *, create: bool = True) -> FieldRule | None:
        field = self.current_field
        if field is None:
            return None
        rule = self.rules.get(field.name)
        if rule is None and create:
            rule = FieldRule(field.name)
            self.rules[field.name] = rule
        return rule or FieldRule(field.name)

    @property
    def page_count(self) -> int:
        field = self.current_field
        if field is None or field.is_memo:
            return 1
        return 3

    def rows(self) -> list[RuleRow]:
        field = self.current_field
        rule = self.current_rule(create=False)
        if field is None or rule is None:
            return []
        return rule_rows(rule, field, self.page)

    def _clamp_row(self) -> None:
        count = len(self.rows())
        self.row = max(0, min(self.row, max(0, count - 1)))

    def _value(self, key: str) -> str:
        rule = self.current_rule(create=False)
        if rule is None:
            return ""
        value = getattr(rule, key, "")
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if key == "postings":
            return f"{len(rule.postings)} rule(s)"
        return str(value)

    def _set_text(self, key: str, text: str) -> None:
        rule = self.current_rule()
        if rule is None:
            return
        if key == "window_rows":
            try:
                rule.window_rows = max(1, min(15, int(text or "10")))
            except ValueError:
                rule.window_rows = 10
            return
        if hasattr(rule, key):
            setattr(rule, key, text)

    # -- tasti -----------------------------------------------------------
    def handle(self, key: Key) -> None:
        self.status = ""
        if self.editor is not None:
            self.editor.handle(key)
            if self.editor.close:
                self._finish_editor()
            return
        if self.picker is not None:
            self._handle_picker(key)
            return
        if self.window == "fields":
            self._handle_fields(key)
        else:
            self._handle_rules(key)

    def _handle_fields(self, key: Key) -> None:
        name = key.name
        if name == "F1":
            return
        if name in ("UP", "DOWN"):
            self.field_index = max(0, min(len(self.fields) - 1,
                                          self.field_index
                                          + (-1 if name == "UP" else 1)))
            self.row = 0
            return
        if name in ("PGUP", "PGDN"):
            delta = -8 if name == "PGUP" else 8
            self.field_index = max(0, min(len(self.fields) - 1,
                                          self.field_index + delta))
            return
        if name in ("ENTER", "F9"):
            if self.current_field is not None:
                self.window = "rules"
                self.page = 1
                self.row = 0
                self.current_rule(create=True)
                self._clamp_row()
            return
        if name == "F5":
            field = self.current_field
            if field is not None:
                self.rules.pop(field.name, None)
                self.deleted.add(field.name)
                self.status = f"Rules for {field.name} deleted."
            return
        if name == "F7":
            self._open_lookup_editor()
            return
        if name == "F8":
            self._open_posting_editor()
            return
        if name == "F10":
            self.save()
            return
        if name == "ESC":
            self.close = True
            return

    def _handle_rules(self, key: Key) -> None:
        name = key.name
        if self.editing:
            if name == "ENTER":
                self._commit_edit()
                return
            if name == "ESC":
                self.editing = False
                self.edit_text = ""
                return
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
                return
            if name == "DELETE":
                self.edit_text = (self.edit_text[:self.edit_cursor]
                                  + self.edit_text[self.edit_cursor + 1:])
                return
            if name == "F2":
                self._open_field_picker()
                return
            text = character(key)
            if text:
                if text.isalpha() and not key.shift:
                    text = text.lower()
                if self.edit_cursor >= len(self.edit_text):
                    self.edit_text += text
                else:
                    self.edit_text = (self.edit_text[:self.edit_cursor]
                                      + text
                                      + self.edit_text[self.edit_cursor + 1:])
                self.edit_cursor += len(text)
            return
        if name == "F1":
            return
        if name == "F9":
            self._commit_edit()
            self.window = "fields"
            return
        if name == "F5":
            field = self.current_field
            if field is not None:
                self.rules.pop(field.name, None)
                self.deleted.add(field.name)
                self.row = 0
                self.status = f"Rules for {field.name} deleted."
            return
        if name == "F7":
            self._open_lookup_editor()
            return
        if name == "F8":
            self._open_posting_editor()
            return
        if name == "F10":
            self.save()
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("PGUP", "PGDN"):
            self._commit_edit()
            self.page = max(1, min(self.page_count,
                                   self.page + (-1 if name == "PGUP" else 1)))
            self.row = 0
            self._clamp_row()
            return
        if name in ("UP", "DOWN"):
            self._commit_edit()
            self.row = max(0, min(len(self.rows()) - 1,
                                  self.row + (-1 if name == "UP" else 1)))
            return
        if name == "TAB":
            self._commit_edit()
            if len(self.rows()):
                self.row = (self.row + (1 if not key.shift else -1)) \
                    % len(self.rows())
            return
        if name == "ENTER":
            row = self.rows()[self.row]
            if row.kind == "hint":
                if row.key == "editor":
                    self._open_lookup_editor()
                elif row.key == "postings":
                    self._open_posting_editor()
                return
            if row.kind in ("bool", "cycle"):
                self._cycle_row(row, -1 if key.shift else 1)
                return
            self.edit_text = self._value(row.key)
            self.edit_cursor = len(self.edit_text)
            self.editing = True
            return
        if name in ("LEFT", "RIGHT", "SPACE"):
            row = self.rows()[self.row]
            if row.kind in ("bool", "cycle"):
                self._cycle_row(row, -1 if name == "LEFT" else 1)

    def _cycle_row(self, row: RuleRow, delta: int) -> None:
        rule = self.current_rule()
        if rule is None:
            return
        if row.kind == "bool":
            setattr(rule, row.key, not getattr(rule, row.key))
        else:
            choices = list(row.choices)
            if not choices:
                return
            current = getattr(rule, row.key, choices[0])
            index = choices.index(current) if current in choices else 0
            setattr(rule, row.key, choices[(index + delta) % len(choices)])
        self._clamp_row()

    def _commit_edit(self) -> None:
        if not self.editing:
            return
        row = self.rows()[self.row]
        self._set_text(row.key, self.edit_text)
        self.editing = False
        self.edit_text = ""
        self._clamp_row()

    # -- picker dei campi ------------------------------------------------
    def _open_field_picker(self) -> None:
        names = [field.name for field in self.fields]
        self.picker = Picker("Fieldnames", names, purpose="field",
                             footer="ENTER insert   ESC cancel")
        self.picker_kind = "field"
        self.editor = None

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
            if value and self.editing:
                text = value
                if self.edit_cursor >= len(self.edit_text):
                    self.edit_text += text
                else:
                    self.edit_text = (self.edit_text[:self.edit_cursor]
                                      + text
                                      + self.edit_text[self.edit_cursor:])
                self.edit_cursor += len(text)
        elif key.name == "ESC":
            self.picker = None

    # -- editor collegati ------------------------------------------------
    def _open_lookup_editor(self) -> None:
        rule = self.current_rule()
        field = self.current_field
        if rule is None or field is None or field.is_memo:
            self.status = "Lookup rules are not available for this field."
            return
        if not rule.lookup:
            self.status = "Set Lookup to Yes first."
            return
        if rule.lookup_source == "Table":
            self.editor = LookupTableEditor(rule.table, self.theme,
                                            self.database, field.name)
        elif rule.lookup_source == "Database":
            self.editor = MappingEditor(rule.mapping, self.theme,
                                        self.database, rule.lookup_database)
        elif rule.advanced == "Cascading table":
            self.editor = CascadingEditor(rule.cascading, self.theme)
        elif rule.advanced == "Conditional table":
            self.editor = ConditionalTableEditor(rule.conditional_tables,
                                                 rule.table, self.theme,
                                                 self.database, field.name)
        elif rule.advanced == "Conditional database":
            self.editor = ConditionalDatabaseEditor(
                rule.conditional_databases, self.theme, self.database,
                rule.lookup_database)
        else:
            self.editor = MappingEditor(rule.mapping, self.theme,
                                        self.database, rule.lookup_database)

    def _open_posting_editor(self) -> None:
        rule = self.current_rule()
        field = self.current_field
        if rule is None or field is None or field.is_memo:
            self.status = "Post data is not available for this field."
            return
        if not rule.post_data:
            self.status = "Set Post data to Yes first."
            return
        self.editor = PostingEditor(rule.postings, self.theme, self.database)

    def _finish_editor(self) -> None:
        editor = self.editor
        self.editor = None
        rule = self.current_rule()
        if editor is None or rule is None or not editor.saved:
            return
        if isinstance(editor, LookupTableEditor):
            rule.table = editor.table
        elif isinstance(editor, MappingEditor):
            rule.mapping = editor.rows
        elif isinstance(editor, PostingEditor):
            rule.postings = editor.rows
        elif isinstance(editor, CascadingEditor):
            rule.cascading = editor.entries
        elif isinstance(editor, ConditionalTableEditor):
            rule.conditional_tables = editor.groups
            rule.table = editor.fallback
        elif isinstance(editor, ConditionalDatabaseEditor):
            rule.conditional_databases = editor.groups
        self.status = "Table saved."
        self._clamp_row()

    # -- salvataggio -----------------------------------------------------
    def save(self) -> bool:
        self._commit_edit()
        for name in self.deleted:
            self.database.delete_field_rule(name)
        for name, rule in list(self.rules.items()):
            field = next((item for item in self.fields if item.name == name),
                         None)
            if field is None:
                continue
            if rule.lookup and rule.lookup_source == "Database" \
                    and rule.lookup_database.strip():
                if self.database.workspace.get(rule.lookup_database) is None:
                    self.status = (f"Lookup database "
                                   f"{rule.lookup_database} not found.")
                    return False
            self.database.save_field_rule(rule)
        self.saved = True
        self.close = True
        self.status = "Field rules saved."
        return True

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        regions = self._view_fields(buffer)
        if self.window == "rules":
            regions.extend(self._view_rules(buffer))
        else:
            draw_status_line(buffer, self.theme,
                             self.status or "Select a field and press F9")
            draw_help_line(buffer, self.theme,
                           "ENTER/F9 define rule   F5 delete rule   "
                           "F10 continue   ESC cancel")
            regions.extend(draw_menu_line(buffer, self.theme, FIELD_KEYS))
        view = View(buffer, regions)
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        if self.editor is not None:
            return self.editor.view()
        return view

    def _view_fields(self, buffer: CellBuffer) -> list[Region]:
        field = self.current_field
        type_name = field.type_name if field is not None else ""
        buffer.write(1, 2, "Database", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(1, 12, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(1, 14, self.database.name, fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        buffer.write(1, 34, "Field", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(1, 46, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(1, 48, field.name if field is not None else "",
                     fg=self.theme.text, bg=self.theme.bg)
        buffer.write(1, 62, "Type", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(1, 66, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(1, 68, clip_text(type_name, SCREEN_WIDTH - 69),
                     fg=self.theme.text, bg=self.theme.bg)
        buffer.write(2, 2, "Fieldname", fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        buffer.write(2, 34, "Type", fg=self.theme.text, bg=self.theme.bg,
                     bold=True)
        buffer.write(2, 46, "Rules", fg=self.theme.text, bg=self.theme.bg,
                     bold=True)
        regions: list[Region] = []
        visible = 9
        top = max(0, min(self.field_index - visible + 1,
                         max(0, len(self.fields) - visible)))
        if self.field_index < top:
            top = self.field_index
        for offset in range(visible):
            index = top + offset
            if index >= len(self.fields):
                break
            item = self.fields[index]
            screen_row = FIELD_TOP + offset
            selected = index == self.field_index
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(screen_row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            buffer.write(screen_row, 2, clip_text(item.name, 24), fg=fg, bg=bg,
                         bold=selected)
            buffer.write(screen_row, 34, item.type_name, fg=fg, bg=bg)
            rule = self.rules.get(item.name)
            marker = "defined" if rule is not None and not rule.is_empty else ""
            buffer.write(screen_row, 46, marker, fg=fg, bg=bg)
            regions.append(Region(screen_row, 1, 1, SCREEN_WIDTH - 2,
                                  f"rules:field:{index}"))
        return regions

    def _view_rules(self, buffer: CellBuffer) -> list[Region]:
        rule = self.current_rule(create=False)
        if rule is None:
            return []
        page = self.page
        pages = self.page_count
        buffer.write(RULE_TOP - 2, 2, f"Page {page} of {pages}",
                     fg=self.theme.label, bg=self.theme.bg)
        buffer.write(RULE_TOP - 2, SCREEN_WIDTH - 18, "F9 switch window",
                     fg=self.theme.muted, bg=self.theme.bg)
        rows = self.rows()
        regions: list[Region] = []
        for offset, row in enumerate(rows):
            screen_row = RULE_TOP + offset
            if screen_row >= STATUS_ROW - 3:
                break
            selected = offset == self.row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(screen_row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            buffer.write(screen_row, 2, clip_text(row.label, 22), fg=fg, bg=bg,
                         bold=selected)
            buffer.write(screen_row, 25, ":", fg=fg, bg=bg)
            if row.kind == "hint":
                text = self._value(row.key)
            elif selected and self.editing:
                text = self.edit_text
            else:
                text = self._value(row.key)
            if selected and self.editing:
                width = SCREEN_WIDTH - 29
                visible = text[-width:] if len(text) > width else text
                buffer.write(screen_row, 27, clip_text(visible, width),
                             fg=fg, bg=bg, underline=True)
            else:
                buffer.write(screen_row, 27,
                             clip_text(text, SCREEN_WIDTH - 29), fg=fg, bg=bg,
                             bold=selected and row.kind in ("bool", "cycle"))
            regions.append(Region(screen_row, 2, 1, SCREEN_WIDTH - 4,
                                  f"rules:row:{offset}"))
        draw_status_line(buffer, self.theme,
                         self.status or "ENTER edit   PGUP/PGDN page   "
                                       "F10 continue")
        draw_help_line(buffer, self.theme,
                       "F2 fields   F7 lookup   F8 posting   F9 switch   "
                       "F10 continue")
        regions.extend(draw_menu_line(buffer, self.theme, RULE_KEYS))
        return regions


# -- editor a griglia -------------------------------------------------------


class GridEditor:
    """Base per tabelle e mapping: una riga per volta, testo o scelta."""

    title = ""
    columns: tuple[tuple[str, int], ...] = ()
    menu = GRID_KEYS
    footer = ""

    def __init__(self, theme: Theme = NEWPORT) -> None:
        self.theme = theme
        self.row = 0
        self.col = 0
        self.edit_text = ""
        self.edit_cursor = 0
        self.picker: Picker | None = None
        self.picker_col = 0
        self.status = ""
        self.close = False
        self.saved = False

    # -- dati ------------------------------------------------------------
    def row_count(self) -> int:
        raise NotImplementedError

    def cell(self, row: int, col: int) -> str:
        raise NotImplementedError

    def set_cell(self, row: int, col: int, text: str) -> None:
        raise NotImplementedError

    def add_row(self) -> None:
        raise NotImplementedError

    def delete_row(self, row: int) -> None:
        raise NotImplementedError

    def options(self, col: int) -> tuple[str, ...] | None:
        return None

    def picker_items(self, col: int) -> list[str] | None:
        return None

    def commit(self) -> None:
        self.set_cell(self.row, self.col, self.edit_text)

    def _load_cell(self) -> None:
        if self.row_count():
            self.row = max(0, min(self.row, self.row_count() - 1))
            self.col = max(0, min(self.col, len(self.columns) - 1))
            self.edit_text = self.cell(self.row, self.col)
        else:
            self.edit_text = ""
        self.edit_cursor = len(self.edit_text)

    # -- tasti -----------------------------------------------------------
    def handle(self, key: Key) -> None:
        self.status = ""
        if self.picker is not None:
            self._handle_picker(key)
            return
        name = key.name
        if name == "F1":
            return
        if name == "F2":
            items = self.picker_items(self.col)
            if items:
                self.picker = Picker("Fieldnames", items, purpose="field",
                                     footer="ENTER select   ESC cancel")
                self.picker_col = self.col
            return
        if name == "F5":
            self.commit()
            if self.row_count():
                self.delete_row(self.row)
                self.row = max(0, min(self.row, self.row_count() - 1))
                self._load_cell()
            return
        if name == "F6":
            self.commit()
            self.add_row()
            self.row = min(self.row + 1, self.row_count() - 1)
            self._load_cell()
            return
        if name == "F10":
            self.commit()
            if self.save_hook():
                self.saved = True
                self.close = True
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN"):
            self.commit()
            if self.row_count():
                self.row = max(0, min(self.row_count() - 1,
                                      self.row + (-1 if name == "UP" else 1)))
                self._load_cell()
            return
        if name in ("TAB", "ENTER"):
            self.commit()
            if name == "TAB":
                self.col = (self.col + (1 if not key.shift else -1)) \
                    % len(self.columns)
                self._load_cell()
            elif self.row_count():
                self.row = min(self.row + 1, self.row_count() - 1)
                self._load_cell()
            return
        if name in ("LEFT", "RIGHT") and not key.ctrl:
            self.commit()
            self.col = max(0, min(len(self.columns) - 1,
                                  self.col + (-1 if name == "LEFT" else 1)))
            self._load_cell()
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
                self.commit()
            return
        if name == "DELETE":
            self.edit_text = (self.edit_text[:self.edit_cursor]
                              + self.edit_text[self.edit_cursor + 1:])
            self.commit()
            return
        options = self.options(self.col)
        if options and name in ("SPACE",):
            current = self.edit_text
            index = options.index(current) if current in options else 0
            self.edit_text = options[(index + 1) % len(options)]
            self.commit()
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
        self.commit()

    def _handle_picker(self, key: Key) -> None:
        picker = self.picker
        assert picker is not None
        if key.name == "UP":
            picker.move(-1)
        elif key.name == "DOWN":
            picker.move(1)
        elif key.name == "ENTER":
            value = picker.value()
            self.picker = None
            if value and self.row_count():
                self.set_cell(self.row, self.picker_col, value)
                self._load_cell()
        elif key.name == "ESC":
            self.picker = None

    def save_hook(self) -> bool:
        return True

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        regions: list[Region] = []
        col = 2
        for index, (name, width) in enumerate(self.columns):
            buffer.write(2, col, clip_text(name, width - 1),
                         fg=self.theme.text, bg=self.theme.bg, bold=True)
            col += width
        visible = STATUS_ROW - 7
        top = max(0, min(self.row - visible + 1,
                         max(0, self.row_count() - visible)))
        for offset in range(visible):
            index = top + offset
            if index >= self.row_count():
                break
            screen_row = 3 + offset
            active_row = index == self.row
            fg = self.theme.selected_fg if active_row else self.theme.text
            bg = self.theme.selected_bg if active_row else self.theme.bg
            if active_row:
                buffer.fill_rect(screen_row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            col = 2
            for column, (name, width) in enumerate(self.columns):
                active = active_row and column == self.col
                text = self.cell(index, column)
                if active:
                    text = self.edit_text
                buffer.write(screen_row, col, clip_text(text, width - 1),
                             fg=fg, bg=bg, underline=active)
                regions.append(Region(screen_row, col, 1, width,
                                      f"grid:{index}:{column}"))
                col += width
        draw_status_line(buffer, self.theme,
                         self.status or self.footer
                         or "TAB next column   ENTER next row   F10 save")
        draw_help_line(buffer, self.theme,
                       "F2 fields   F5 delete row   F6 insert row   "
                       "F10 continue   ESC cancel")
        regions.extend(draw_menu_line(buffer, self.theme, self.menu))
        view = View(buffer, regions)
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        return view


class LookupTableEditor(GridEditor):
    table: LookupTable = field(default_factory=LookupTable)
    database: Database | None = None
    field_name: str = ""

    def __init__(self, table: LookupTable, theme: Theme = NEWPORT,
                 database: Database | None = None,
                 field_name: str = "") -> None:
        super().__init__(theme)
        self.table = LookupTable(list(table.columns),
                                 [list(row) for row in table.rows])
        self.database = database
        self.field_name = field_name
        if not self.table.rows:
            self.table.rows = [[""]]
        self.title = f"Lookup Table - {field_name}"
        self._load_cell()

    # Larghezza utile della tabella: dalla colonna 2 alla 77.
    TABLE_COLUMNS = SCREEN_WIDTH - 4

    @property
    def columns(self) -> tuple[tuple[str, int], ...]:
        titles = [self.field_name or "Choice"] + list(self.table.columns)
        if len(titles) == 1:
            return ((titles[0], self.TABLE_COLUMNS),)
        first = 24
        rest = min(14, max(8, (self.TABLE_COLUMNS - first) // (len(titles) - 1)))
        return tuple((name, first if index == 0 else rest)
                     for index, name in enumerate(titles))

    def row_count(self) -> int:
        return len(self.table.rows)

    def cell(self, row: int, col: int) -> str:
        if row >= len(self.table.rows):
            return ""
        values = self.table.rows[row]
        return values[col] if col < len(values) else ""

    def set_cell(self, row: int, col: int, text: str) -> None:
        if row >= len(self.table.rows):
            return
        values = self.table.rows[row]
        while len(values) <= col:
            values.append("")
        values[col] = text
        self.table.normalize()

    def add_row(self) -> None:
        if len(self.table.rows) >= 255:
            self.status = "A lookup table holds at most 255 rows."
            return
        self.table.rows.insert(self.row + 1,
                               ["" for _ in range(1 + len(self.table.columns))])

    def delete_row(self, row: int) -> None:
        if row < len(self.table.rows):
            del self.table.rows[row]
        if not self.table.rows:
            self.table.rows = [[""]]

    def picker_items(self, col: int) -> list[str] | None:
        if col != 0 or self.database is None:
            return None
        return [field.name for field in self.database.fields]

    def handle(self, key: Key) -> None:
        if key.name == "F2" and self.database is not None:
            # F2 aggiunge una colonna, non sceglie il campo della prima.
            names = [field.name for field in self.database.fields
                     if field.name not in self.table.columns]
            if len(self.table.columns) >= MAX_LOOKUP_COLUMNS - 1:
                self.status = "A lookup table holds at most six columns."
                return
            self.picker = Picker("Fieldnames", names, purpose="column",
                                 footer="ENTER add column   ESC cancel")
            self.picker_col = -1
            return
        super().handle(key)

    def _handle_picker(self, key: Key) -> None:
        picker = self.picker
        assert picker is not None
        if key.name == "UP":
            picker.move(-1)
        elif key.name == "DOWN":
            picker.move(1)
        elif key.name == "ENTER":
            value = picker.value()
            self.picker = None
            if value and self.picker_col == -1:
                self.table.columns.append(value)
                for row in self.table.rows:
                    row.append("")
        elif key.name == "ESC":
            self.picker = None

    def save_hook(self) -> bool:
        self.table.normalize()
        return True

    def view(self) -> View:
        return super().view()


class MappingEditor(GridEditor):
    rows: list[MappingRow] = field(default_factory=list)
    database: Database | None = None
    lookup_database: str = ""

    def __init__(self, rows: list[MappingRow], theme: Theme = NEWPORT,
                 database: Database | None = None,
                 lookup_database: str = "") -> None:
        super().__init__(theme)
        self.rows = [MappingRow(**row.__dict__) for row in rows] or \
            [MappingRow()]
        self.database = database
        self.lookup_database = lookup_database
        self.title = f"Lookup Mapping - {lookup_database or 'database'}"
        self.columns = (("Choice Field", 18), ("Filled Field", 18),
                        ("Condition", 16), ("Expression", 18),
                        ("Display", 8))
        self._load_cell()

    def row_count(self) -> int:
        return len(self.rows)

    def cell(self, row: int, col: int) -> str:
        item = self.rows[row]
        return (item.choice_field, item.filled_field, item.condition,
                item.expression, "Yes" if item.display else "No")[col]

    def set_cell(self, row: int, col: int, text: str) -> None:
        item = self.rows[row]
        if col == 0:
            item.choice_field = text.strip().upper()
        elif col == 1:
            item.filled_field = text.strip().upper()
        elif col == 2:
            item.condition = text.strip() or ".T."
        elif col == 3:
            item.expression = text
        else:
            item.display = text.strip().upper().startswith("Y")

    def add_row(self) -> None:
        self.rows.insert(self.row + 1, MappingRow())

    def delete_row(self, row: int) -> None:
        if row < len(self.rows):
            del self.rows[row]
        if not self.rows:
            self.rows = [MappingRow()]

    def options(self, col: int) -> tuple[str, ...] | None:
        return ("Yes", "No") if col == 4 else None

    def picker_items(self, col: int) -> list[str] | None:
        if self.database is None or col not in (0, 1):
            return None
        return [field.name for field in self.database.fields]

    def save_hook(self) -> bool:
        if not any(row.choice_field for row in self.rows):
            self.status = "Enter at least one choice field."
            return False
        return True


class PostingEditor(GridEditor):
    rows: list[PostingRule] = field(default_factory=list)
    database: Database | None = None

    def __init__(self, rows: list[PostingRule], theme: Theme = NEWPORT,
                 database: Database | None = None) -> None:
        super().__init__(theme)
        self.rows = [PostingRule(**row.__dict__) for row in rows] or \
            [PostingRule()]
        self.database = database
        self.title = "Posting Rules"
        self.columns = (("Database", 10), ("Field to post to", 14),
                        ("Mode", 8), ("Condition", 10), ("Expression", 14),
                        ("Link index", 10), ("Common", 10))
        self._load_cell()

    def row_count(self) -> int:
        return len(self.rows)

    def cell(self, row: int, col: int) -> str:
        item = self.rows[row]
        return (item.database, item.field, item.mode, item.condition,
                item.expression, item.linking_index, item.common)[col]

    def set_cell(self, row: int, col: int, text: str) -> None:
        item = self.rows[row]
        value = text.strip()
        if col == 0:
            item.database = value.upper()
        elif col == 1:
            item.field = value.upper()
        elif col == 2:
            item.mode = text if text in POST_MODES else "Add"
        elif col == 3:
            item.condition = text
        elif col == 4:
            item.expression = text
        elif col == 5:
            item.linking_index = value.upper()
        else:
            item.common = text

    def add_row(self) -> None:
        self.rows.insert(self.row + 1, PostingRule())

    def delete_row(self, row: int) -> None:
        if row < len(self.rows):
            del self.rows[row]
        if not self.rows:
            self.rows = [PostingRule()]

    def options(self, col: int) -> tuple[str, ...] | None:
        return POST_MODES if col == 2 else None

    def picker_items(self, col: int) -> list[str] | None:
        if self.database is None or col != 0:
            return None
        return self.database.workspace.names()

    def save_hook(self) -> bool:
        for row in self.rows:
            if not row.database or not row.field:
                self.status = "Every posting rule needs database and field."
                return False
        return True


class CascadingEditor:
    entries: list[CascadingEntry] = field(default_factory=list)
    theme: Theme = NEWPORT
    row: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    editing: bool = False
    status: str = ""
    close: bool = False
    saved: bool = False
    title: str = "Cascading Choice Table"

    def __init__(self, entries: list[CascadingEntry],
                 theme: Theme = NEWPORT) -> None:
        self.entries = [CascadingEntry(entry.depth, entry.text)
                        for entry in entries] or [CascadingEntry(0, "")]
        self.theme = theme
        self._load()

    def _load(self) -> None:
        self.row = max(0, min(self.row, len(self.entries) - 1))
        self.edit_text = self.entries[self.row].text
        self.edit_cursor = len(self.edit_text)

    def handle(self, key: Key) -> None:
        self.status = ""
        name = key.name
        if self.editing:
            if name == "ENTER":
                self._commit()
                self.editing = False
                return
            if name == "ESC":
                self.editing = False
                self._load()
                return
            if name == "TAB":
                self._commit()
                if key.shift:
                    self.entries[self.row].depth = max(
                        0, self.entries[self.row].depth - 1)
                else:
                    self.entries[self.row].depth += 1
                return
            if name == "BACKSPACE":
                if self.edit_cursor:
                    self.edit_text = (self.edit_text[:self.edit_cursor - 1]
                                      + self.edit_text[self.edit_cursor:])
                    self.edit_cursor -= 1
                    self._commit()
                return
            if name in ("LEFT", "RIGHT"):
                self.edit_cursor = max(0, min(
                    len(self.edit_text), self.edit_cursor
                    + (-1 if name == "LEFT" else 1)))
                return
            text = character(key)
            if text:
                if text.isalpha() and not key.shift:
                    text = text.lower()
                if self.edit_cursor >= len(self.edit_text):
                    self.edit_text += text
                else:
                    self.edit_text = (self.edit_text[:self.edit_cursor]
                                      + text
                                      + self.edit_text[self.edit_cursor + 1:])
                self.edit_cursor += len(text)
                self._commit()
            return
        if name == "F1":
            return
        if name == "F10":
            self.saved = True
            self.close = True
            return
        if name == "ESC":
            self.close = True
            return
        if name == "F5":
            del self.entries[self.row]
            if not self.entries:
                self.entries = [CascadingEntry(0, "")]
            self.row = min(self.row, len(self.entries) - 1)
            self._load()
            return
        if name == "F6" or name == "ENTER":
            depth = self.entries[self.row].depth
            self.entries.insert(self.row + 1, CascadingEntry(depth, ""))
            self.row += 1
            self._load()
            self.editing = True
            return
        if name == "TAB":
            if key.shift:
                self.entries[self.row].depth = max(
                    0, self.entries[self.row].depth - 1)
            else:
                self.entries[self.row].depth += 1
            return
        if name in ("UP", "DOWN"):
            self.row = max(0, min(len(self.entries) - 1,
                                  self.row + (-1 if name == "UP" else 1)))
            self._load()
            return
        if name == "F2":
            self.editing = True
            return

    def _commit(self) -> None:
        if 0 <= self.row < len(self.entries):
            self.entries[self.row].text = self.edit_text

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        buffer.write(2, 2, "Indent endpoints; use TAB / SHIFT-TAB to demote "
                           "or promote.", fg=self.theme.label,
                     bg=self.theme.bg)
        visible = STATUS_ROW - 8
        top = max(0, min(self.row - visible + 1,
                         max(0, len(self.entries) - visible)))
        regions: list[Region] = []
        for offset in range(visible):
            index = top + offset
            if index >= len(self.entries):
                break
            entry = self.entries[index]
            screen_row = 4 + offset
            selected = index == self.row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(screen_row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            endpoint = index + 1 >= len(self.entries) or \
                self.entries[index + 1].depth <= entry.depth
            text = " " * (entry.depth * 2) + entry.text
            if endpoint and entry.text:
                text += "   (endpoint)"
            if selected and self.editing:
                text = " " * (entry.depth * 2) + self.edit_text
            buffer.write(screen_row, 2, clip_text(text, SCREEN_WIDTH - 4),
                         fg=fg, bg=bg, bold=endpoint or selected,
                         underline=selected and self.editing)
            regions.append(Region(screen_row, 2, 1, SCREEN_WIDTH - 4,
                                  f"cascade:{index}"))
        draw_status_line(buffer, self.theme,
                         self.status or "TAB demote   SHIFT-TAB promote   "
                                       "ENTER edit/insert   F10 continue")
        draw_help_line(buffer, self.theme,
                       "ENTER/F2 edit   F5 delete row   F6 insert row   "
                       "F10 continue   ESC cancel")
        regions.extend(draw_menu_line(buffer, self.theme, GRID_KEYS))
        return View(buffer, regions)


class ConditionalTableEditor:
    groups: list[ConditionalGroup] = field(default_factory=list)
    fallback: LookupTable = field(default_factory=LookupTable)
    theme: Theme = NEWPORT
    database: Database | None = None
    field_name: str = ""
    row: int = 0
    col: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    editing: bool = False
    table_editor: LookupTableEditor | None = None
    table_target: int = -1
    status: str = ""
    close: bool = False
    saved: bool = False
    title: str = "Conditional Lookup Table"

    def __init__(self, groups: list[ConditionalGroup],
                 fallback: LookupTable, theme: Theme = NEWPORT,
                 database: Database | None = None,
                 field_name: str = "") -> None:
        self.groups = [ConditionalGroup(group.expression, group.filter,
                                        LookupTable(
                                            list(group.table.columns),
                                            [list(row) for row in group.table.rows]))
                       for group in groups] or [ConditionalGroup()]
        self.fallback = LookupTable(list(fallback.columns),
                                    [list(row) for row in fallback.rows])
        self.theme = theme
        self.database = database
        self.field_name = field_name
        self._load()

    def _load(self) -> None:
        self.row = max(0, min(self.row, len(self.groups) - 1))
        self.edit_text = self.groups[self.row].expression \
            if self.col == 0 else self.groups[self.row].filter
        self.edit_cursor = len(self.edit_text)

    def handle(self, key: Key) -> None:
        self.status = ""
        if self.table_editor is not None:
            self.table_editor.handle(key)
            if self.table_editor.close:
                editor = self.table_editor
                self.table_editor = None
                if editor.saved:
                    if self.table_target == -1:
                        self.fallback = editor.table
                    elif 0 <= self.table_target < len(self.groups):
                        self.groups[self.table_target].table = editor.table
                return
            return
        name = key.name
        if self.editing:
            if name == "ENTER":
                self.groups[self.row].expression = self.edit_text \
                    if self.col == 0 else self.groups[self.row].expression
                self.groups[self.row].filter = self.edit_text \
                    if self.col == 1 else self.groups[self.row].filter
                self.editing = False
                return
            if name == "ESC":
                self.editing = False
                self._load()
                return
            if name == "BACKSPACE":
                if self.edit_cursor:
                    self.edit_text = (self.edit_text[:self.edit_cursor - 1]
                                      + self.edit_text[self.edit_cursor:])
                    self.edit_cursor -= 1
                return
            if name in ("LEFT", "RIGHT"):
                self.edit_cursor = max(0, min(
                    len(self.edit_text), self.edit_cursor
                    + (-1 if name == "LEFT" else 1)))
                return
            text = character(key)
            if text:
                if text.isalpha() and not key.shift:
                    text = text.lower()
                self.edit_text += text
                self.edit_cursor += len(text)
            return
        if name == "F1":
            return
        if name == "F10":
            self.saved = True
            self.close = True
            return
        if name == "ESC":
            self.close = True
            return
        if name == "F5":
            del self.groups[self.row]
            if not self.groups:
                self.groups = [ConditionalGroup()]
            self.row = min(self.row, len(self.groups) - 1)
            self._load()
            return
        if name == "F6":
            self.groups.insert(self.row + 1, ConditionalGroup())
            self.row += 1
            self._load()
            return
        if name == "F7":
            self.table_target = self.row
            self.table_editor = LookupTableEditor(
                self.groups[self.row].table, self.theme, self.database,
                self.field_name)
            return
        if name == "F9":
            self.table_target = -1
            self.table_editor = LookupTableEditor(
                self.fallback, self.theme, self.database, self.field_name)
            return
        if name in ("UP", "DOWN"):
            self.row = max(0, min(len(self.groups) - 1,
                                  self.row + (-1 if name == "UP" else 1)))
            self._load()
            return
        if name == "TAB":
            self.col = 1 - self.col
            self._load()
            return
        if name == "ENTER":
            self.editing = True
            self.edit_text = self.groups[self.row].expression \
                if self.col == 0 else self.groups[self.row].filter
            self.edit_cursor = len(self.edit_text)

    def view(self) -> View:
        if self.table_editor is not None:
            return self.table_editor.view()
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        buffer.write(2, 2, "Expression", fg=self.theme.text, bg=self.theme.bg,
                     bold=True)
        buffer.write(2, 34, "Filter", fg=self.theme.text, bg=self.theme.bg,
                     bold=True)
        buffer.write(2, 52, "Choices", fg=self.theme.text, bg=self.theme.bg,
                     bold=True)
        regions: list[Region] = []
        for index, group in enumerate(self.groups[:visible_rows(3)]):
            screen_row = 3 + index
            selected = index == self.row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(screen_row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            expression = self.edit_text if selected and self.editing \
                and self.col == 0 else group.expression
            filter_text = self.edit_text if selected and self.editing \
                and self.col == 1 else group.filter
            buffer.write(screen_row, 2, clip_text(expression, 30), fg=fg,
                         bg=bg, underline=selected and self.editing)
            buffer.write(screen_row, 34, clip_text(filter_text, 16), fg=fg,
                         bg=bg, underline=selected and self.editing)
            buffer.write(screen_row, 52, str(len(group.table.rows)), fg=fg,
                         bg=bg)
            regions.append(Region(screen_row, 2, 1, SCREEN_WIDTH - 4,
                                  f"cond:{index}"))
        buffer.write(16, 2, f"Fall through table: {len(self.fallback.rows)} "
                            "row(s)   F9 edit", fg=self.theme.label,
                     bg=self.theme.bg)
        draw_status_line(buffer, self.theme,
                         self.status or "F6 add condition   F7 edit table   "
                                       "F10 continue")
        draw_help_line(buffer, self.theme,
                       "F5 delete   F6 add   F7 table   F9 fall through   "
                       "F10 continue")
        regions.extend(draw_menu_line(buffer, self.theme, GRID_KEYS))
        return View(buffer, regions)


class ConditionalDatabaseEditor:
    groups: list[ConditionalDatabase] = field(default_factory=list)
    theme: Theme = NEWPORT
    database: Database | None = None
    fallback_database: str = ""
    row: int = 0
    col: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    status: str = ""
    close: bool = False
    saved: bool = False
    title: str = "Conditional Lookup Databases"

    def __init__(self, groups: list[ConditionalDatabase],
                 theme: Theme = NEWPORT,
                 database: Database | None = None,
                 fallback_database: str = "") -> None:
        self.groups = [ConditionalDatabase(**group.__dict__)
                       for group in groups] or [ConditionalDatabase()]
        self.theme = theme
        self.database = database
        self.fallback_database = fallback_database
        self.columns = (("Expression", 20), ("Database", 14),
                        ("Link index", 13), ("Display index", 14),
                        ("Filter", 15))
        self._load()

    def _load(self) -> None:
        self.row = max(0, min(self.row, len(self.groups) - 1))
        self.col = max(0, min(self.col, len(self.columns) - 1))
        item = self.groups[self.row]
        self.edit_text = (item.expression, item.database, item.linking_index,
                          item.display_index, item.filter)[self.col]
        self.edit_cursor = len(self.edit_text)

    def handle(self, key: Key) -> None:
        self.status = ""
        name = key.name
        if name == "F1":
            return
        if name == "F10":
            self.saved = True
            self.close = True
            return
        if name == "ESC":
            self.close = True
            return
        if name == "F5":
            del self.groups[self.row]
            if not self.groups:
                self.groups = [ConditionalDatabase()]
            self.row = min(self.row, len(self.groups) - 1)
            self._load()
            return
        if name == "F6":
            self.groups.insert(self.row + 1, ConditionalDatabase())
            self.row += 1
            self._load()
            return
        if name in ("UP", "DOWN"):
            self._commit()
            self.row = max(0, min(len(self.groups) - 1,
                                  self.row + (-1 if name == "UP" else 1)))
            self._load()
            return
        if name == "TAB":
            self._commit()
            self.col = (self.col + (1 if not key.shift else -1)) \
                % len(self.columns)
            self._load()
            return
        if name in ("LEFT", "RIGHT") and not key.ctrl:
            self._commit()
            self.col = max(0, min(len(self.columns) - 1,
                                  self.col + (-1 if name == "LEFT" else 1)))
            self._load()
            return
        if name == "BACKSPACE":
            if self.edit_cursor:
                self.edit_text = (self.edit_text[:self.edit_cursor - 1]
                                  + self.edit_text[self.edit_cursor:])
                self.edit_cursor -= 1
                self._commit()
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
        self._commit()

    def _commit(self) -> None:
        item = self.groups[self.row]
        value = self.edit_text
        if self.col == 0:
            item.expression = value
        elif self.col == 1:
            item.database = value.strip().upper()
        elif self.col == 2:
            item.linking_index = value.strip().upper()
        elif self.col == 3:
            item.display_index = value.strip().upper()
        else:
            item.filter = value

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        buffer.write(2, 2, f"Fall through: {self.fallback_database or '(none)'}",
                     fg=self.theme.label, bg=self.theme.bg)
        col = 2
        for label, width in self.columns:
            buffer.write(3, col, clip_text(label, width - 1),
                         fg=self.theme.text, bg=self.theme.bg, bold=True)
            col += width
        regions: list[Region] = []
        for index, group in enumerate(self.groups[:visible_rows(4)]):
            screen_row = 4 + index
            selected = index == self.row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(screen_row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            values = (group.expression, group.database, group.linking_index,
                      group.display_index, group.filter)
            col = 2
            for column, (label, width) in enumerate(self.columns):
                text = self.edit_text if selected and column == self.col \
                    else values[column]
                buffer.write(screen_row, col, clip_text(text, width - 1),
                             fg=fg, bg=bg,
                             underline=selected and column == self.col)
                regions.append(Region(screen_row, col, 1, width,
                                      f"conddb:{index}:{column}"))
                col += width
        draw_status_line(buffer, self.theme,
                         self.status or "F6 add condition   F10 continue")
        draw_help_line(buffer, self.theme,
                       "F5 delete   F6 add   F10 continue   ESC cancel")
        regions.extend(draw_menu_line(buffer, self.theme, GRID_KEYS))
        return View(buffer, regions)


__all__ = [
    "CascadingEditor",
    "ConditionalDatabaseEditor",
    "ConditionalTableEditor",
    "LookupTableEditor",
    "MappingEditor",
    "PostingEditor",
    "RulesSession",
    "rule_rows",
]
