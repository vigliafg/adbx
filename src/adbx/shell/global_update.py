"""Global update/delete (O9): aggiornamenti, maiuscole, delete range."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..data import indexing, utilities
from ..data.workspace import Database, WorkspaceError
from ..screen.keys import Key
from .dialogs import Picker
from .theme import NEWPORT, Theme
from .utilities import FormRow, _FormSession, _range_text


@dataclass
class GlobalSession(_FormSession):
    database: Database | None = None
    command: str = "update-field"
    theme: Theme = NEWPORT
    stage: str = "expressions"
    row: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    status: str = ""
    close: bool = False
    picker: Picker | None = None
    picker_kind: str = ""
    settings: indexing.RangeSettings | None = None
    expressions: list[tuple[str, str]] = field(default_factory=list)
    case_mode: str = "Upper case"
    chosen: list[str] = field(default_factory=list)
    result: utilities.UtilityResult | None = None
    request: str = ""

    def __post_init__(self) -> None:
        if self.database is not None and self.settings is None:
            self.settings = self.database.current_range.copy()
        fields = list(self.database.fields) if self.database else []
        if self.command == "update-field":
            self.stage = "expressions"
            if fields:
                self.expressions = [(fields[0].name, "")]
        elif self.command == "case":
            self.stage = "case"
            self.chosen = [field.name for field in fields
                           if field.type == "C"]
        else:
            self.stage = "confirm"
        self._load_row()

    @property
    def title(self) -> str:
        return {"update-field": "Update a Field",
                "case": "Change Case",
                "delete-range": "Delete Range of Records",
                "undelete-range": "Undelete Range of Records"}.get(
            self.command, "Global Update/Delete")

    def rows(self) -> list[FormRow]:
        if self.stage == "expressions":
            return [FormRow(field_name, expression, "text",
                            action=field_name)
                    for field_name, expression in self.expressions]
        if self.stage == "case":
            rows = [FormRow("Conversion", self.case_mode, "choice")]
            selected = {name.upper() for name in self.chosen}
            if self.database is not None:
                for field_def in self.database.fields:
                    if field_def.type != "C":
                        continue
                    marker = "* " if field_def.name in selected else "  "
                    rows.append(FormRow(field_def.name, marker + "Character",
                                        "choice", action=field_def.name))
            return rows
        return [
            FormRow("Database", self.database.name if self.database else "",
                    "readonly"),
            FormRow("Range", _range_text(self.settings, self.database)
                    if self.settings and self.database else "", "readonly"),
            FormRow("Records", str(self._count()), "readonly"),
            FormRow("Continue", "Yes" if self.stage == "confirm" else "",
                    "readonly"),
        ]

    def _count(self) -> int:
        if self.database is None or self.settings is None:
            return 0
        try:
            return len(indexing.ordered_sequences(self.database, self.settings))
        except indexing.IndexError_:
            return 0

    def set_text(self, index: int, text: str) -> None:
        if self.stage != "expressions" or index >= len(self.expressions):
            return
        field_name, _expression = self.expressions[index]
        if self.row_field_mode(index) == "field":
            self.expressions[index] = (text.upper(), _expression)
        else:
            self.expressions[index] = (field_name, text)

    def row_field_mode(self, index: int) -> str:
        return "expression"

    def cycle(self, index: int, delta: int) -> None:
        if self.stage == "case":
            if index == 0:
                modes = list(utilities.CASE_MODES)
                current = modes.index(self.case_mode) \
                    if self.case_mode in modes else 0
                self.case_mode = modes[(current + delta) % len(modes)]
                return
            if self.database is None:
                return
            character_fields = [field for field in self.database.fields
                                if field.type == "C"]
            if index - 1 >= len(character_fields):
                return
            name = character_fields[index - 1].name
            if name in self.chosen:
                self.chosen.remove(name)
            else:
                self.chosen.append(name)

    def open_picker(self, index: int) -> None:
        if self.stage == "expressions" and self.database is not None:
            names = [field.name for field in self.database.fields]
            current = (self.expressions[index][0]
                       if index < len(self.expressions) else "")
            selected = names.index(current) if current in names else 0
            self.picker = Picker("Fieldnames", names, purpose="update-field",
                                 selected=selected)
            self.picker_kind = f"field:{index}"

    def accept_picker(self, value: str) -> None:
        if self.picker_kind.startswith("field:") and value:
            index = int(self.picker_kind.split(":", 1)[1])
            if index < len(self.expressions):
                self.expressions[index] = (value, self.expressions[index][1])

    def handle(self, key: Key) -> None:
        if self.stage == "expressions" and self.picker is None:
            if key.name == "F5":
                if len(self.expressions) > 1:
                    del self.expressions[self.row]
                    self.row = min(self.row, len(self.expressions) - 1)
                    self._load_row()
                return
            if key.name == "F6" and self.database is not None:
                field_name = self.database.fields[
                    min(self.row + 1, len(self.database.fields) - 1)].name
                self.expressions.append((field_name, ""))
                self.row = len(self.expressions) - 1
                self._load_row()
                return
        if self.stage == "confirm" and key.name == "ENTER":
            self._run()
            return
        super().handle(key)

    def continue_stage(self) -> None:
        if self.stage in ("expressions", "case"):
            self.stage = "confirm"
            self.row = 0
            self._load_row()
            return
        self._run()

    def _run(self) -> None:
        if self.database is None:
            self.close = True
            return
        try:
            if self.command == "update-field":
                updates = [utilities.UpdateExpression(field_name, expression)
                           for field_name, expression in self.expressions
                           if expression.strip()]
                if not updates:
                    self.status = "Enter at least one expression."
                    self.stage = "expressions"
                    self._load_row()
                    return
                self.result = utilities.update_fields(
                    self.database, updates, self.settings)
            elif self.command == "case":
                self.result = utilities.change_case(
                    self.database, self.chosen, self.case_mode, self.settings)
            elif self.command == "delete-range":
                self.result = utilities.mark_range(
                    self.database, True, self.settings)
            else:
                self.result = utilities.mark_range(
                    self.database, False, self.settings)
        except (utilities.UtilityError, WorkspaceError) as exc:
            self.status = str(exc)
            self.stage = "confirm" if self.stage == "confirm" else self.stage
            return
        self.close = True

    def back_stage(self) -> None:
        if self.stage == "confirm" and self.command in ("update-field", "case"):
            self.stage = "expressions" if self.command == "update-field" else "case"
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
        if self.stage == "expressions":
            return "F2 fieldname   F5 delete   F6 insert   F10 continue"
        if self.stage == "case":
            return "SPACE change conversion   ENTER select fields   F10 continue"
        labels = {"update-field": "ENTER update",
                  "case": "ENTER change case",
                  "delete-range": "ENTER delete",
                  "undelete-range": "ENTER undelete"}
        return labels.get(self.command, "ENTER execute") + "   ESC cancel"

    def help_text(self) -> str:
        if self.stage == "confirm":
            return "ENTER execute   ESC back"
        return "F7 range   F10 continue   ESC cancel"


__all__ = ["GlobalSession"]
