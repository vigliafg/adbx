"""Schermate delle utility sui dati (O9).

Le utility condividono una forma a righe: etichetta, valore, tipo. I campi
di testo si digitano, le scelte si cambiano con ENTER/SPACE, i campi si
scelgono da un elenco a comparsa. `F10` prosegue, `ESC` torna indietro.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, Cell, CellBuffer
from ..data import indexing, utilities
from ..data.fields import Field
from ..data.workspace import Database, Workspace, WorkspaceError
from ..screen.keys import Key, character
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
)

UTILITY_KEYS = [("F1", "Help"), ("F2", "Fields"), ("F5", "Delete"),
                ("F6", "Insert"), ("F7", "Range"), ("F10", "Continue"),
                ("ESC", "Back")]
OPTIONS_KEYS = [("F1", "Help"), ("F7", "Range"), ("F10", "Continue"),
                ("ESC", "Cancel")]
FIELD_KEYS = [("F1", "Help"), ("ENTER", "Select"), ("SPACE", "Change"),
              ("F10", "Continue"), ("ESC", "Cancel")]


@dataclass
class FormRow:
    label: str
    value: str
    kind: str = "text"  # text, choice, readonly, picker
    action: str = ""
    enabled: bool = True


def _range_text(settings: indexing.RangeSettings, database: Database) -> str:
    primary = settings.primary
    if primary in (indexing.RECORD_NUMBER, indexing.SEARCH_LIST) \
            or primary.startswith(indexing.SEARCH_PREFIX):
        label = "Record Number"
    else:
        definition = indexing.find_index(database, primary)
        label = definition.label if definition else primary
    show = {indexing.SHOW_ALL: "All", indexing.SHOW_DELETED: "Deleted",
            indexing.SHOW_NOT_DELETED: "Not deleted"}.get(
        settings.show, settings.show)
    return f"{label}; {show}; {'descending' if settings.order == indexing.ORDER_DESCENDING else 'ascending'}"


class _FormSession:
    """Base per le schermate a righe."""

    theme: Theme = NEWPORT
    title: str = "Utilities"
    row: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    status: str = ""
    close: bool = False
    picker: Picker | None = None
    picker_kind: str = ""
    regions: list[Region] = field(default_factory=list)

    def rows(self) -> list[FormRow]:
        return []

    def set_text(self, index: int, text: str) -> None:
        return

    def cycle(self, index: int, delta: int) -> None:
        return

    def pick(self, index: int) -> None:
        self.open_picker(index)

    def open_picker(self, index: int) -> None:
        return

    def continue_stage(self) -> None:
        return

    def back_stage(self) -> None:
        self.close = True

    def help_topic(self) -> str:
        return "utilities"

    def _load_row(self) -> None:
        rows = self.rows()
        if not rows:
            self.row = 0
            self.edit_text = ""
            self.edit_cursor = 0
            return
        self.row = max(0, min(self.row, len(rows) - 1))
        row = rows[self.row]
        if row.kind == "text":
            self.edit_text = row.value
            self.edit_cursor = len(self.edit_text)
        else:
            self.edit_text = ""
            self.edit_cursor = 0

    def _commit(self) -> None:
        rows = self.rows()
        if 0 <= self.row < len(rows) and rows[self.row].kind == "text":
            self.set_text(self.row, self.edit_text)

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
            self.picker = None
            self.accept_picker(picker.value())
        elif key.name == "ESC":
            self.picker = None

    def accept_picker(self, value: str) -> None:
        return

    def handle(self, key: Key) -> None:
        self.status = ""
        if self.picker is not None:
            self._handle_picker(key)
            return
        if key.name == "F1" and not key.alt:
            self.status = self.help_topic()
            return
        name = key.name
        rows = self.rows()
        if name == "F10":
            self._commit()
            self.continue_stage()
            return
        if name == "ESC":
            self._commit()
            self.back_stage()
            return
        if name == "F2":
            self._commit()
            if rows:
                self.open_picker(self.row)
            return
        if name == "F7" and hasattr(self, "request_range"):
            self._commit()
            self.request_range()
            return
        if name in ("UP", "DOWN"):
            self._commit()
            if rows:
                self.row = max(0, min(len(rows) - 1,
                                      self.row + (-1 if name == "UP" else 1)))
            self._load_row()
            return
        if not rows:
            return
        row = rows[self.row]
        if name in ("TAB", "ENTER"):
            self._commit()
            if row.kind == "choice":
                self.cycle(self.row, -1 if key.shift else 1)
                return
            if row.kind == "picker":
                self.open_picker(self.row)
                return
            if name == "TAB":
                self.row = (self.row + (-1 if key.shift else 1)) % len(rows)
                self._load_row()
            return
        if row.kind == "choice":
            if name in ("SPACE", "LEFT", "RIGHT"):
                self.cycle(self.row, -1 if name in ("SPACE", "LEFT") else 1)
            return
        if row.kind != "text":
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
                self.set_text(self.row, self.edit_text)
            return
        if name == "DELETE":
            self.edit_text = (self.edit_text[:self.edit_cursor]
                              + self.edit_text[self.edit_cursor + 1:])
            self.set_text(self.row, self.edit_text)
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
        self.set_text(self.row, self.edit_text)

    # -- disegno ---------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        regions: list[Region] = []
        rows = self.rows()
        top = 3
        for index, row in enumerate(rows):
            line = top + index
            if line >= SCREEN_HEIGHT - 3:
                break
            active = index == self.row
            fg = self.theme.selected_fg if active else self.theme.text
            bg = self.theme.selected_bg if active else self.theme.bg
            if active:
                buffer.fill_rect(line, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            buffer.write(line, 2, row.label, fg=fg, bg=bg)
            value = row.value
            if active and row.kind == "text":
                value = self.edit_text
            buffer.write(line, 30, ":", fg=fg, bg=bg)
            width = SCREEN_WIDTH - 34
            buffer.write(line, 32, clip_text(value, width), fg=fg, bg=bg,
                         underline=active and row.kind == "text",
                         bold=active and row.kind == "readonly")
            regions.append(Region(line, 1, 1, SCREEN_WIDTH - 2,
                                  f"util:row:{index}"))
        draw_status_line(buffer, self.theme,
                         self.status or self.status_text())
        draw_help_line(buffer, self.theme, self.help_text())
        regions.extend(draw_menu_line(buffer, self.theme,
                                      FIELD_KEYS if self.is_field_stage()
                                      else UTILITY_KEYS))
        view = View(buffer, regions)
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        return view

    def status_text(self) -> str:
        return "ENTER change   TAB next   F10 continue   ESC back"

    def help_text(self) -> str:
        return "F1 help   F2 choose   F10 continue   ESC back"

    def is_field_stage(self) -> bool:
        return False


# -- copy, append, summarize, crosstab -------------------------------------


@dataclass
class UtilitySession(_FormSession):
    workspace: Workspace | None = None
    database: Database | None = None
    active_set: object | None = None
    command: str = "copy"
    theme: Theme = NEWPORT
    stage: str = "options"
    row: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    status: str = ""
    close: bool = False
    picker: Picker | None = None
    picker_kind: str = ""
    name: str = ""
    description: str = ""
    inherit: bool = False
    all_fields: bool = True
    chosen: list[tuple[str, str]] = field(default_factory=list)
    settings: indexing.RangeSettings | None = None
    result: utilities.UtilityResult | None = None
    request: str = ""
    # append
    source_name: str = ""
    source: Database | None = None
    append_mode: str = "All"
    append_filter: str = ""
    mappings: list[utilities.AppendMapping] = field(default_factory=list)
    # summarize
    summary: list[tuple[str, str, bool]] = field(default_factory=list)
    # crosstab
    row_field: str = ""
    column_field: str = ""
    tab_field: str = ""
    operation: str = "Count"
    create_names: bool = False
    names_name: str = ""
    see_results: bool = False
    columns: list[utilities.CrosstabColumn] = field(default_factory=list)
    explicit_columns: bool = False

    def __post_init__(self) -> None:
        if self.database is not None and self.settings is None:
            self.settings = self.database.current_range.copy()
        self._prepare()

    # -- preparazione ----------------------------------------------------
    def _sources(self) -> list[tuple[str, Field]]:
        if self.database is None:
            return []
        if self.active_set is not None:
            try:
                return [(name, definition) for name, definition, _label
                        in self.active_set.flat_fields()]
            except Exception:
                pass
        return [(self.database.name, field) for field in self.database.fields]

    def _primary_fields(self) -> list[Field]:
        return list(self.database.fields) if self.database is not None else []

    def _prepare(self) -> None:
        sources = self._sources()
        if self.command == "copy":
            self.stage = "fields"
            self.chosen = [(name, field.name) for name, field in sources]
        elif self.command == "append":
            self.stage = "source"
            self.open_source_picker()
        elif self.command == "summarize":
            self.stage = "fields"
            primary = self.database.name if self.database is not None else ""
            self.summary = []
            for name, field in sources:
                if name != primary:
                    continue
                operation = "Total" if field.type == "N" else "Group"
                self.summary.append((field.name, operation, True))
            if not any(item[2] for item in self.summary) and sources:
                self.summary = [(sources[0][1].name, "Group", True)]
        elif self.command == "crosstab":
            self.stage = "options"
            fields = self._primary_fields()
            if fields:
                self.row_field = fields[0].name
                self.column_field = fields[min(1, len(fields) - 1)].name
                self.tab_field = fields[min(2, len(fields) - 1)].name
                if self.tab_field:
                    field = self.database.field(self.tab_field)
                    self.operation = "Total" if field.type == "N" else "Count"
                self.names_name = (self.name or "XTAB") + "N"
        self._load_row()

    @property
    def title(self) -> str:
        labels = {"copy": "Copy Database", "append": "Append Database",
                  "summarize": "Summarize Database",
                  "crosstab": "Cross Tabulation"}
        return labels.get(self.command, "Utilities")

    def is_field_stage(self) -> bool:
        return self.stage in ("fields",)

    def help_topic(self) -> str:
        return "utilities"

    # -- righe -----------------------------------------------------------
    def rows(self) -> list[FormRow]:
        if self.command == "copy":
            return self._copy_rows()
        if self.command == "append":
            return self._append_rows()
        if self.command == "summarize":
            return self._summary_rows()
        return self._crosstab_rows()

    def _copy_rows(self) -> list[FormRow]:
        if self.stage == "fields":
            rows = [FormRow("Fields", "All fields" if self.all_fields
                            else "Selected fields", "choice")]
            if not self.all_fields:
                chosen = {item[1].upper() for item in self.chosen}
                for name, field in self._sources():
                    marker = "* " if field.name in chosen else "  "
                    rows.append(FormRow(f"{name}.{field.name}",
                                        marker + field.type_name, "choice"))
            return rows
        return [
            FormRow("Database name", self.name),
            FormRow("Description", self.description),
            FormRow("Inherit support files", "Yes" if self.inherit else "No",
                    "choice"),
            FormRow("Range", _range_text(self.settings, self.database)
                    if self.settings else "", "readonly"),
        ]

    def _append_rows(self) -> list[FormRow]:
        if self.stage == "options":
            return [
                FormRow("External database", self.source_name, "readonly"),
                FormRow("Append option", self.append_mode, "choice"),
                FormRow("Filter expression", self.append_filter),
            ]
        if self.stage == "mapping":
            rows: list[FormRow] = []
            for index, mapping in enumerate(self.mappings):
                rows.append(FormRow(mapping.target,
                                    mapping.source or "<None>", "picker",
                                    action=str(index)))
            return rows
        return []

    def _summary_rows(self) -> list[FormRow]:
        if self.stage == "fields":
            rows: list[FormRow] = []
            for field_name, operation, included in self.summary:
                marker = "* " if included else "  "
                rows.append(FormRow(field_name, f"{marker}{operation}", "choice",
                                    action=field_name))
            return rows
        return [
            FormRow("Database name", self.name),
            FormRow("Description", self.description),
            FormRow("Range", _range_text(self.settings, self.database)
                    if self.settings else "", "readonly"),
        ]

    def _crosstab_rows(self) -> list[FormRow]:
        if self.stage == "columns":
            rows: list[FormRow] = []
            for index, column in enumerate(self.columns):
                text = f"{column.name} | {column.expression}"
                rows.append(FormRow(f"Column {index + 1}", text, "text",
                                    action=f"name:{index}"))
            return rows
        return [
            FormRow("Database name", self.name),
            FormRow("Row field", self.row_field, "picker"),
            FormRow("Column field", self.column_field, "picker"),
            FormRow("Tabulation field", self.tab_field, "picker"),
            FormRow("Tabulation operation", self.operation, "choice"),
            FormRow("Use expressions for columns",
                    "Yes" if self.explicit_columns else "No", "choice"),
            FormRow("Create names database",
                    "Yes" if self.create_names else "No", "choice"),
            FormRow("Names database", self.names_name),
            FormRow("See results immediately",
                    "Yes" if self.see_results else "No", "choice"),
            FormRow("Range", _range_text(self.settings, self.database)
                    if self.settings else "", "readonly"),
        ]

    # -- editing ---------------------------------------------------------
    def set_text(self, index: int, text: str) -> None:
        if self.command == "copy":
            if index == 0:
                self.name = text.upper()
            elif index == 1:
                self.description = text
        elif self.command == "append":
            if self.stage == "options" and index == 2:
                self.append_filter = text
        elif self.command == "summarize":
            if index == 0:
                self.name = text.upper()
            elif index == 1:
                self.description = text
        elif self.command == "crosstab":
            if self.stage == "columns":
                if 0 <= index < len(self.columns):
                    name, _separator, expression = text.partition("|")
                    self.columns[index] = utilities.CrosstabColumn(
                        name.strip().upper()[:10], expression.strip())
                return
            if index == 0:
                self.name = text.upper()
            elif index == 7:
                self.names_name = text.upper()

    def cycle(self, index: int, delta: int) -> None:
        if self.command == "copy":
            if self.stage == "fields" and index == 0:
                self.all_fields = not self.all_fields
                self.row = 0
                self._load_row()
                return
            if self.stage == "fields":
                name, field = self._sources()[index - 1]
                item = (name, field.name)
                if item in self.chosen:
                    self.chosen.remove(item)
                else:
                    self.chosen.append(item)
                self.all_fields = False
                return
            if index == 2:
                self.inherit = not self.inherit
                return
        elif self.command == "append":
            if self.stage == "options" and index == 1:
                modes = list(utilities.APPEND_MODES)
                current = modes.index(self.append_mode) \
                    if self.append_mode in modes else 0
                self.append_mode = modes[(current + delta) % len(modes)]
                return
        elif self.command == "summarize":
            if self.stage == "fields":
                field_name, operation, included = self.summary[index]
                operations = list(utilities.SUMMARY_OPERATIONS)
                current = operations.index(operation) if operation in operations else 0
                self.summary[index] = (field_name,
                                       operations[(current + delta) % len(operations)],
                                       included)
                return
        elif self.command == "crosstab":
            if self.stage == "options":
                if index == 4:
                    operations = list(utilities.CROSSTAB_OPERATIONS)
                    current = operations.index(self.operation) \
                        if self.operation in operations else 0
                    self.operation = operations[(current + delta) % len(operations)]
                elif index == 5:
                    self.explicit_columns = not self.explicit_columns
                elif index == 6:
                    self.create_names = not self.create_names
                elif index == 8:
                    self.see_results = not self.see_results

    def handle(self, key: Key) -> None:
        if self.command == "summarize" and self.stage == "fields" \
                and key.name == "ENTER" and self.picker is None:
            rows = self.rows()
            if rows and 0 <= self.row < len(self.summary):
                field_name, operation, included = self.summary[self.row]
                self.summary[self.row] = (field_name, operation, not included)
            return
        if self.command == "crosstab" and self.picker is None:
            if self.stage == "options" and key.name == "F3":
                self.stage = "columns"
                if not self.columns:
                    self.columns = [utilities.CrosstabColumn("COL1", "")]
                self.explicit_columns = True
                self.row = 0
                self._load_row()
                return
            if self.stage == "columns":
                if key.name == "F5" and self.columns:
                    del self.columns[self.row]
                    self.row = min(self.row, max(0, len(self.columns) - 1))
                    self._load_row()
                    return
                if key.name == "F6":
                    self.columns.append(
                        utilities.CrosstabColumn(f"COL{len(self.columns) + 1}",
                                                  ""))
                    self.row = len(self.columns) - 1
                    self._load_row()
                    return
        super().handle(key)

    def open_picker(self, index: int) -> None:
        if self.command == "append":
            if self.stage == "mapping" and self.mappings:
                mapping = self.mappings[index]
                names = [field.name for field in self.source.fields] \
                    if self.source is not None else []
                items = ["<None>"] + names
                selected = 0
                if mapping.source in names:
                    selected = names.index(mapping.source) + 1
                self.picker = Picker("Fieldnames", items, purpose="mapping",
                                     selected=selected)
                self.picker_kind = f"mapping:{index}"
            return
        if self.command == "crosstab" and self.stage == "options":
            fields = self._primary_fields()
            if index in (1, 2, 3):
                names = [field.name for field in fields]
                current = [self.row_field, self.column_field,
                           self.tab_field][index - 1]
                selected = names.index(current) if current in names else 0
                self.picker = Picker("Fieldnames", names,
                                     purpose=["row", "column", "tab"][index - 1],
                                     selected=selected)
                self.picker_kind = ["row", "column", "tab"][index - 1]

    def accept_picker(self, value: str) -> None:
        if not value:
            return
        if self.picker_kind.startswith("mapping:"):
            index = int(self.picker_kind.split(":", 1)[1])
            mapping = self.mappings[index]
            self.mappings[index] = utilities.AppendMapping(
                mapping.target, "" if value == "<None>" else value)
            return
        if self.picker_kind == "source":
            self.source = self.workspace.get(value) if self.workspace else None
            if self.source is None:
                self.status = "Database not found."
                return
            self.source_name = value
            self.mappings = utilities.default_mappings(self.database,
                                                       self.source)
            self.stage = "options"
            self.row = 0
            self._load_row()
            return
        if self.picker_kind in ("row", "column", "tab"):
            if self.picker_kind == "row":
                self.row_field = value
            elif self.picker_kind == "column":
                self.column_field = value
            else:
                self.tab_field = value
                field = self.database.field(value)
                if field.type == "N" and self.operation == "Count":
                    self.operation = "Total"
            self._load_row()

    # -- transizioni -----------------------------------------------------
    def continue_stage(self) -> None:
        if self.command == "copy":
            self._copy_continue()
        elif self.command == "append":
            self._append_continue()
        elif self.command == "summarize":
            self._summary_continue()
        else:
            self._crosstab_continue()

    def _copy_continue(self) -> None:
        if self.stage == "fields":
            if not self.all_fields and not self.chosen:
                self.status = "Select at least one field."
                return
            self.stage = "options"
            self.row = 0
            self._load_row()
            return
        if not self.name.strip():
            self.status = "Enter a database name."
            return
        fields = None if self.all_fields else [
            utilities.CopyField(name, field) for name, field in self.chosen]
        try:
            self.result = utilities.copy_database(self.database,
                                                  utilities.CopyOptions(
                                                      self.name, self.description,
                                                      self.inherit, fields,
                                                      self.settings,
                                                      self.active_set))
        except (utilities.UtilityError, WorkspaceError) as exc:
            self.status = str(exc)
            return
        self.close = True

    def _append_continue(self) -> None:
        if self.stage == "options":
            self.stage = "mapping"
            self.row = 0
            self._load_row()
            return
        if self.stage == "mapping":
            try:
                self.result = utilities.append_database(
                    self.database, self.source,
                    utilities.AppendOptions(self.append_mode,
                                            self.append_filter,
                                            list(self.mappings)))
            except (utilities.UtilityError, WorkspaceError) as exc:
                self.status = str(exc)
                return
            self.close = True

    def _summary_continue(self) -> None:
        if self.stage == "fields":
            selected = [utilities.SummaryField(name, operation)
                        for name, operation, included in self.summary
                        if included]
            if not selected:
                self.status = "Select at least one field."
                return
            self.stage = "options"
            self.row = 0
            self._load_row()
            return
        if not self.name.strip():
            self.status = "Enter a database name."
            return
        selected = [utilities.SummaryField(name, operation)
                    for name, operation, included in self.summary if included]
        try:
            self.result = utilities.summarize(
                self.database,
                utilities.SummarizeOptions(self.name, selected,
                                           self.description, self.settings,
                                           self.active_set))
        except (utilities.UtilityError, WorkspaceError) as exc:
            self.status = str(exc)
            return
        self.close = True

    def _crosstab_continue(self) -> None:
        if self.stage == "columns":
            self.stage = "options"
            self.row = 0
            self._load_row()
            return
        if not self.name.strip():
            self.status = "Enter a database name."
            return
        columns = self.columns if self.explicit_columns else None
        if columns is not None and not columns:
            self.status = "Define at least one column with F6."
            return
        try:
            self.result = utilities.crosstab(
                self.database, utilities.CrosstabOptions(
                    self.name, self.row_field, self.column_field,
                    self.tab_field, self.operation, columns,
                    self.create_names, self.names_name,
                    self.see_results, self.settings))
        except (utilities.UtilityError, WorkspaceError) as exc:
            self.status = str(exc)
            return
        self.close = True

    def back_stage(self) -> None:
        if self.command == "copy" and self.stage == "options":
            self.stage = "fields"
            self.row = 0
            self._load_row()
            return
        if self.command == "append" and self.stage == "mapping":
            self.stage = "options"
            self.row = 0
            self._load_row()
            return
        if self.command == "summarize" and self.stage == "options":
            self.stage = "fields"
            self.row = 0
            self._load_row()
            return
        if self.command == "crosstab" and self.stage == "columns":
            self.stage = "options"
            self.row = 0
            self._load_row()
            return
        self.close = True

    def request_range(self) -> None:
        self.request = "range"

    def open_source_picker(self) -> None:
        if self.workspace is None:
            self.close = True
            return
        names = [name for name in self.workspace.names()
                 if self.database is None or name != self.database.name]
        if not names:
            self.status = "There are no other databases."
            self.stage = "source"
            return
        self.picker = Picker("Database Directory", names, purpose="source",
                             width=72)
        self.picker_kind = "source"

    def set_range(self, settings: indexing.RangeSettings) -> None:
        self.settings = settings
        self.request = ""
        self.row = 0
        self._load_row()

    def status_text(self) -> str:
        if self.command == "append" and self.stage == "source":
            return "Select the external database."
        if self.command == "copy" and self.stage == "fields":
            return "ENTER select/de-select   F10 continue"
        if self.command == "summarize" and self.stage == "fields":
            return "ENTER include/exclude   SPACE change operation   F10 continue"
        if self.command == "crosstab" and self.stage == "columns":
            return "Type 'name | expression'; F5/F6 delete/insert column"
        return f"{self.command.title()}: fill in the options."

    def help_text(self) -> str:
        if self.command == "crosstab" and self.stage == "options":
            return "F3 columns   F7 range   F10 continue   ESC cancel"
        if self.command in ("copy", "summarize"):
            return "F7 range settings   F10 continue   ESC cancel"
        return "F10 continue   ESC cancel"


__all__ = ["FormRow", "UtilitySession", "UTILITY_KEYS", "OPTIONS_KEYS"]
