"""Relational commands (O9): post, join, intersect e subtract."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..data import indexing, utilities
from ..data.workspace import Database, Workspace, WorkspaceError
from ..screen.keys import Key
from .dialogs import Picker
from .theme import NEWPORT, Theme
from .utilities import FormRow, _FormSession, _range_text


@dataclass
class RelationalSession(_FormSession):
    workspace: Workspace | None = None
    database: Database | None = None
    command: str = "join"
    theme: Theme = NEWPORT
    stage: str = "secondary"
    row: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    status: str = ""
    close: bool = False
    picker: Picker | None = None
    picker_kind: str = ""
    secondary_name: str = ""
    secondary: Database | None = None
    index_name: str = ""
    common_expression: str = ""
    primary_chosen: list[str] = field(default_factory=list)
    secondary_chosen: list[str] = field(default_factory=list)
    name: str = ""
    description: str = ""
    settings: indexing.RangeSettings | None = None
    result: utilities.UtilityResult | None = None
    request: str = ""
    # post
    post_filter: str = ""
    status_field: str = ""
    mark_unmatched: bool = False
    post_rows: list[tuple[str, str, str, bool]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.database is not None and self.settings is None:
            self.settings = self.database.current_range.copy()
        if self.command == "post":
            self._prepare_post()
            self.open_secondary_picker()
        else:
            self.open_secondary_picker()

    @property
    def title(self) -> str:
        labels = {"post": "Post Database", "join": "Join Databases",
                  "intersect": "Intersect Databases",
                  "subtract": "Subtract Databases"}
        return labels.get(self.command, "Relational Commands")

    # -- preparazione ----------------------------------------------------
    def _prepare_post(self) -> None:
        primary = self.database.primary_index
        self.common_expression = ""
        if primary not in (indexing.RECORD_NUMBER, indexing.SEARCH_LIST) \
                and not primary.startswith(indexing.SEARCH_PREFIX):
            definition = indexing.find_index(self.database, primary)
            if definition is not None:
                self.common_expression = definition.expression
        self.post_rows = []
        self.primary_chosen = []
        for definition in self.database.fields:
            self.post_rows.append((definition.name, definition.name,
                                   "Replace", False))

    def _prepare_index_fields(self) -> None:
        self.primary_chosen = [field.name for field in self.database.fields]
        self.secondary_chosen = ([field.name for field in self.secondary.fields]
                                 if self.secondary is not None else [])

    # -- righe -----------------------------------------------------------
    def rows(self) -> list[FormRow]:
        if self.stage == "common":
            if self.command == "post":
                return [
                    FormRow("Transaction database", self.secondary_name,
                            "readonly"),
                    FormRow("Common expression", self.common_expression),
                    FormRow("Transaction filter", self.post_filter),
                    FormRow("Transaction status field", self.status_field),
                    FormRow("Mark unmatched deleted",
                            "Yes" if self.mark_unmatched else "No", "choice"),
                ]
            return [
                FormRow("Secondary database", self.secondary_name,
                        "readonly"),
                FormRow("Secondary index", self.index_name, "readonly"),
                FormRow("Common expression", self.common_expression),
                FormRow("Range", _range_text(self.settings, self.database)
                        if self.settings else "", "readonly"),
            ]
        if self.stage == "post-fields":
            rows: list[FormRow] = []
            for index, (master, source, operation, included) in enumerate(
                    self.post_rows):
                marker = "* " if included else "  "
                rows.append(FormRow(master, f"{marker}{source} : {operation}",
                                    "choice", action=str(index)))
            return rows
        if self.stage == "primary-fields":
            return self._field_rows(self.database, self.primary_chosen)
        if self.stage == "secondary-fields":
            return self._field_rows(self.secondary, self.secondary_chosen)
        if self.stage == "options":
            return [
                FormRow("Result database", self.name),
                FormRow("Description", self.description),
                FormRow("Range", _range_text(self.settings, self.database)
                        if self.settings else "", "readonly"),
            ]
        return []

    def _field_rows(self, database: Database | None,
                    chosen: list[str]) -> list[FormRow]:
        rows: list[FormRow] = []
        if database is None:
            return rows
        selected = {name.upper() for name in chosen}
        for definition in database.fields:
            marker = "* " if definition.name in selected else "  "
            rows.append(FormRow(definition.name, marker + definition.type_name,
                                "choice", action=definition.name))
        return rows

    # -- editing ---------------------------------------------------------
    def set_text(self, index: int, text: str) -> None:
        if self.stage == "common":
            if self.command == "post":
                if index == 1:
                    self.common_expression = text
                elif index == 2:
                    self.post_filter = text
                elif index == 3:
                    self.status_field = text.upper()
            elif index == 2:
                self.common_expression = text
        elif self.stage == "options":
            if index == 0:
                self.name = text.upper()
            elif index == 1:
                self.description = text

    def cycle(self, index: int, delta: int) -> None:
        if self.stage == "common" and self.command == "post" and index == 4:
            self.mark_unmatched = not self.mark_unmatched
            return
        if self.stage in ("primary-fields", "secondary-fields"):
            database = (self.database if self.stage == "primary-fields"
                        else self.secondary)
            chosen = (self.primary_chosen if self.stage == "primary-fields"
                      else self.secondary_chosen)
            if database is None or index >= len(database.fields):
                return
            name = database.fields[index].name
            if name in chosen:
                chosen.remove(name)
            else:
                chosen.append(name)
            return
        if self.stage == "post-fields":
            master, source, operation, included = self.post_rows[index]
            operations = list(utilities.POST_OPERATIONS)
            current = operations.index(operation) if operation in operations else 0
            self.post_rows[index] = (master, source,
                                     operations[(current + delta) % len(operations)],
                                     included)

    def enter_row(self, index: int) -> None:
        if self.stage in ("primary-fields", "secondary-fields"):
            self.cycle(index, 1)
            return
        if self.stage == "post-fields":
            master, source, operation, included = self.post_rows[index]
            self.post_rows[index] = (master, source, operation, not included)
            return
        self.open_picker(index)

    def handle(self, key: Key) -> None:
        if (self.stage in ("primary-fields", "secondary-fields",
                           "post-fields") and key.name == "ENTER"
                and self.picker is None):
            self.status = ""
            rows = self.rows()
            if rows:
                self.enter_row(self.row)
            return
        super().handle(key)

    def open_picker(self, index: int) -> None:
        if self.stage == "post-fields":
            if self.secondary is None or not self.post_rows:
                return
            names = [field.name for field in self.secondary.fields]
            current = self.post_rows[index][1]
            selected = names.index(current) if current in names else 0
            self.picker = Picker("Transaction fieldnames", names,
                                 purpose="post-field", selected=selected)
            self.picker_kind = f"post:{index}"
            return
        if self.stage == "common" and self.command != "post":
            return

    def accept_picker(self, value: str) -> None:
        if not value:
            return
        if self.picker_kind == "secondary":
            self.secondary = self.workspace.get(value) if self.workspace else None
            if self.secondary is None:
                self.status = "Database not found."
                return
            self.secondary_name = value
            if self.command == "post":
                names = {field.name for field in self.secondary.fields}
                self.post_rows = [
                    (master, source, operation, source in names)
                    for master, source, operation, _included in self.post_rows
                ]
                self.stage = "common"
                self.row = 0
                self._load_row()
            else:
                self.open_index_picker()
            return
        if self.picker_kind == "index":
            self.index_name = value
            definition = indexing.find_index(self.secondary, value)
            if definition is not None and not self.common_expression:
                self.common_expression = definition.expression
            self._prepare_index_fields()
            self.stage = "common"
            self.row = 0
            self._load_row()
            return
        if self.picker_kind.startswith("post:"):
            index = int(self.picker_kind.split(":", 1)[1])
            master, _source, operation, included = self.post_rows[index]
            self.post_rows[index] = (master, value, operation, included)

    def open_secondary_picker(self) -> None:
        if self.workspace is None:
            self.close = True
            return
        names = [name for name in self.workspace.names()
                 if self.database is None or name != self.database.name]
        if not names:
            self.status = "There are no other databases."
            return
        self.picker = Picker("Database Directory", names,
                             purpose="secondary", width=72)
        self.picker_kind = "secondary"

    def open_index_picker(self) -> None:
        if self.secondary is None:
            return
        definitions = indexing.indexes(self.secondary)
        if not definitions:
            self.status = (f"{self.secondary.name} has no indexes; "
                           "create one before the relational command.")
            return
        names = [definition.name for definition in definitions]
        labels = [definition.label for definition in definitions]
        self.picker = Picker("Index Files", labels, values=names,
                             purpose="index", width=72)
        self.picker_kind = "index"

    # -- transizioni -----------------------------------------------------
    def continue_stage(self) -> None:
        if self.command == "post":
            self._continue_post()
            return
        if self.stage == "common":
            if not self.common_expression.strip():
                self.status = "Enter the common expression."
                return
            self.stage = "primary-fields"
            self.row = 0
            self._load_row()
            return
        if self.stage == "primary-fields":
            if not self.primary_chosen:
                self.status = "Select at least one field from the primary."
                return
            self.stage = "secondary-fields"
            self.row = 0
            self._load_row()
            return
        if self.stage == "secondary-fields":
            if not self.primary_chosen and not self.secondary_chosen:
                self.status = "Select at least one field for the result."
                return
            self.stage = "options"
            self.row = 0
            self._load_row()
            return
        if self.stage == "options":
            if not self.name.strip():
                self.status = "Enter a name for the result database."
                return
            primary_fields = [utilities.JoinField(self.database.name, name)
                              for name in self.primary_chosen]
            secondary_fields = [utilities.JoinField(self.secondary.name, name)
                                for name in self.secondary_chosen]
            try:
                self.result = utilities.relational(
                    self.database, self.secondary,
                    utilities.RelationalOptions(
                        self.command.title(), self.name, self.index_name,
                        self.common_expression, primary_fields,
                        secondary_fields, self.settings, self.description))
            except (utilities.UtilityError, WorkspaceError) as exc:
                self.status = str(exc)
                return
            self.close = True

    def _continue_post(self) -> None:
        if self.stage == "common":
            if not self.common_expression.strip():
                self.status = "Enter the common expression."
                return
            self.stage = "post-fields"
            self.row = 0
            self._load_row()
            return
        if self.stage == "post-fields":
            selected = [utilities.PostField(master, source, operation)
                        for master, source, operation, included
                        in self.post_rows if included and source]
            if not selected:
                self.status = "Select at least one field to post."
                return
            try:
                self.result = utilities.post(
                    self.database, self.secondary,
                    utilities.PostOptions(self.common_expression,
                                          self.post_filter,
                                          self.status_field,
                                          self.mark_unmatched, selected))
            except (utilities.UtilityError, WorkspaceError) as exc:
                self.status = str(exc)
                return
            self.close = True

    def back_stage(self) -> None:
        if self.command == "post":
            if self.stage == "post-fields":
                self.stage = "common"
                self.row = 0
                self._load_row()
                return
            if self.stage == "common":
                self.close = True
                return
        if self.stage == "common":
            self.stage = "secondary"
            self.open_secondary_picker()
            return
        if self.stage == "primary-fields":
            self.stage = "common"
            self.row = 0
            self._load_row()
            return
        if self.stage == "secondary-fields":
            self.stage = "primary-fields"
            self.row = 0
            self._load_row()
            return
        if self.stage == "options":
            self.stage = "secondary-fields"
            self.row = 0
            self._load_row()
            return
        self.close = True

    def request_range(self) -> None:
        self.request = "range"

    def set_range(self, settings: indexing.RangeSettings) -> None:
        self.settings = settings
        self.request = ""
        self.row = 0
        self._load_row()

    def status_text(self) -> str:
        return {"secondary": "Select the secondary database.",
                "common": "Fill in the common fields.",
                "post-fields": "ENTER include   SPACE operation   F2 source",
                "primary-fields": "ENTER select/de-select primary fields.",
                "secondary-fields": "ENTER select/de-select secondary fields.",
                "options": "Enter the result database name."}.get(
            self.stage, "F10 continue")

    def help_text(self) -> str:
        if self.stage in ("primary-fields", "secondary-fields",
                          "post-fields"):
            return "ENTER select   F10 continue   ESC back"
        if self.command != "post":
            return "F7 range   F10 continue   ESC cancel"
        return "F10 continue   ESC cancel"


__all__ = ["RelationalSession"]
