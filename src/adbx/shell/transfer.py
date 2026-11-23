"""Import/export dei formati di scambio (O9)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..data import indexing
from ..data.fields import Field, FieldError
from ..data.workspace import Database, Workspace, WorkspaceError
from ..io import (
    FORMATS,
    ExportOptions,
    ImportOptions,
    TableData,
    export_from_database,
    read_table,
    with_extension,
)
from ..io.common import infer_fields
from ..io.formats import TransferResult
from ..screen.keys import Key
from .dialogs import Picker
from .theme import NEWPORT, Theme
from .utilities import FormRow, _FormSession, _range_text

TYPE_NAMES = (("Character", "C"), ("Numeric", "N"), ("Date", "D"),
              ("Logical", "L"), ("Memo", "M"))
CASE_DATE_FORMATS = ("MM/DD/YYYY", "MM/DD/YY", "YYYYMMDD")


@dataclass
class TransferSession(_FormSession):
    workspace: Workspace | None = None
    database: Database | None = None
    mode: str = "import"
    theme: Theme = NEWPORT
    stage: str = "file"
    row: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    status: str = ""
    close: bool = False
    picker: Picker | None = None
    picker_kind: str = ""
    format_key: str = ""
    path_text: str = ""
    target_name: str = ""
    description: str = ""
    overwrite: bool = False
    options: ImportOptions | ExportOptions | None = None
    table: TableData | None = None
    fields: list[Field] = field(default_factory=list)
    included: list[bool] = field(default_factory=list)
    chosen: list[str] = field(default_factory=list)
    balance: int = 0
    result: TransferResult | None = None
    request: str = ""
    settings: indexing.RangeSettings | None = None
    edit_field: int = 0

    def __post_init__(self) -> None:
        if self.database is not None and self.settings is None:
            self.settings = self.database.current_range.copy()
        self.options = (ImportOptions() if self.mode == "import"
                        else ExportOptions())
        self.open_format_picker()

    @property
    def title(self) -> str:
        return "Import Data" if self.mode == "import" else "Export Data"

    def open_format_picker(self) -> None:
        specs = [spec for spec in FORMATS
                 if (spec.importable if self.mode == "import"
                     else spec.exportable)]
        self.picker = Picker("Data Import" if self.mode == "import"
                             else "Data Export",
                             [spec.label for spec in specs],
                             values=[spec.key for spec in specs],
                             purpose="format", width=72)
        self.picker_kind = "format"

    # -- righe -----------------------------------------------------------
    def rows(self) -> list[FormRow]:
        if self.stage == "format":
            return []
        if self.stage == "file":
            return [FormRow("File name", self.path_text)]
        if self.stage == "options":
            return self._option_rows()
        if self.stage == "adjust":
            return self._adjust_rows()
        if self.stage == "adjust-edit":
            return self._adjust_edit_rows()
        if self.stage == "target":
            rows = [FormRow("Database name", self.target_name),
                    FormRow("Description", self.description)]
            if self._target_exists():
                rows.append(FormRow("Overwrite existing",
                                    "Yes" if self.overwrite else "No",
                                    "choice"))
            return rows
        if self.stage == "fields":
            return self._field_rows(self.database, self.chosen)
        return []

    def _option_rows(self) -> list[FormRow]:
        rows: list[FormRow] = []
        if self.mode == "import":
            rows.append(FormRow("File has fieldnames",
                                "Yes" if self.options.fieldnames else "No",
                                "choice"))
            rows.append(FormRow("Examine file for defaults",
                                "Yes" if self.options.examine else "No",
                                "choice"))
            rows.append(FormRow("Skip file header",
                                str(self.options.skip_header)))
            if self.format_key in ("delimited", "csv"):
                rows.append(FormRow("Field separator",
                                    self.options.separator))
                rows.append(FormRow("Quote character", self.options.quote))
            if self.format_key == "table":
                rows.append(FormRow("How many fields",
                                    str(self.options.field_count)))
                rows.append(FormRow("Field width", str(self.options.width)))
                rows.append(FormRow("Spacing", str(self.options.spacing)))
                rows.append(FormRow("File has returns/linefeeds",
                                    "Yes" if self.options.linefeeds else "No",
                                    "choice"))
                if not self.options.linefeeds:
                    rows.append(FormRow("Length of record",
                                        str(self.options.record_length)))
            rows.append(FormRow("Default decimal places",
                                str(self.options.decimal_places)))
            return rows
        rows.append(FormRow("Output fieldnames",
                            "Yes" if self.options.fieldnames else "No",
                            "choice"))
        if self.format_key in ("delimited", "csv"):
            rows.append(FormRow("Enclose character fields",
                                "Yes" if self.options.quote_character else "No",
                                "choice"))
            rows.append(FormRow("Field separator", self.options.separator))
            rows.append(FormRow("Quote character", self.options.quote))
            rows.append(FormRow("Suppress trailing separator",
                                "Yes" if not self.options.trailing_separator
                                else "No", "choice"))
        if self.format_key == "table":
            rows.append(FormRow("Field width", str(self.options.width)))
            rows.append(FormRow("Spacing", str(self.options.spacing)))
        if self.format_key == "lotus":
            rows.append(FormRow("Date format", self.options.date_format,
                                "choice"))
        rows.append(FormRow("Range", _range_text(self.settings, self.database)
                            if self.settings else "", "readonly"))
        return rows

    def _adjust_rows(self) -> list[FormRow]:
        rows = []
        for index, field_def in enumerate(self.fields):
            marker = "* " if index < len(self.included) and self.included[index] else "  "
            decimals = f".{field_def.decimals}" if field_def.type == "N" else ""
            rows.append(FormRow(field_def.name,
                                f"{marker}{field_def.type_name} "
                                f"{field_def.length}{decimals}", "choice",
                                action=str(index)))
        return rows

    def _adjust_edit_rows(self) -> list[FormRow]:
        field_def = self.fields[self.edit_field]
        return [
            FormRow("Field name", field_def.name),
            FormRow("Field type", field_def.type_name, "choice"),
            FormRow("Length", str(field_def.length)),
            FormRow("Decimal places", str(field_def.decimals)),
        ]

    def _field_rows(self, database: Database | None,
                    chosen: list[str]) -> list[FormRow]:
        rows = []
        if database is None:
            return rows
        selected = {name.upper() for name in chosen}
        for field_def in database.fields:
            marker = "* " if field_def.name in selected else "  "
            rows.append(FormRow(field_def.name,
                                marker + field_def.type_name, "choice",
                                action=field_def.name))
        return rows

    # -- editing ---------------------------------------------------------
    def set_text(self, index: int, text: str) -> None:
        if self.stage == "file":
            self.path_text = text
            return
        if self.stage == "options":
            self._set_option(index, text)
            return
        if self.stage == "adjust-edit":
            self._set_adjust(index, text)
            return
        if self.stage == "target":
            if index == 0:
                self.target_name = text.upper()
            elif index == 1:
                self.description = text

    def _option_names(self) -> list[str]:
        options = self.options
        if self.mode == "import":
            names = ["fieldnames", "examine", "skip_header"]
            if self.format_key in ("delimited", "csv"):
                names += ["separator", "quote"]
            if self.format_key == "table":
                names += ["field_count", "width", "spacing", "linefeeds"]
                if not options.linefeeds:
                    names += ["record_length"]
            names += ["decimal_places"]
            return names
        names = ["fieldnames"]
        if self.format_key in ("delimited", "csv"):
            names += ["quote_character", "separator", "quote",
                      "trailing_separator"]
        if self.format_key == "table":
            names += ["width", "spacing"]
        if self.format_key == "lotus":
            names += ["date_format"]
        return names

    def _set_option(self, index: int, text: str) -> None:
        options = self.options
        names = self._option_names()
        if index >= len(names):
            return
        name = names[index]
        if name in ("separator", "quote"):
            setattr(options, name, text[:1] or ("," if name == "separator"
                                                else '"'))
        elif name in ("skip_header", "field_count", "width", "spacing",
                      "record_length", "decimal_places"):
            try:
                setattr(options, name, max(0, int(text)))
            except ValueError:
                pass
        elif name == "date_format":
            options.date_format = text.upper()
        else:
            setattr(options, name, bool(text))

    def _set_adjust(self, index: int, text: str) -> None:
        field_def = self.fields[self.edit_field]
        try:
            if index == 0:
                self.fields[self.edit_field] = Field(
                    text.upper(), field_def.type, field_def.length,
                    field_def.decimals)
            elif index == 2:
                length = max(1, int(text))
                if field_def.type in ("D", "L", "M"):
                    length = field_def.length
                self.fields[self.edit_field] = Field(
                    field_def.name, field_def.type, length,
                    field_def.decimals)
            elif index == 3:
                decimals = max(0, int(text))
                if field_def.type == "N":
                    self.fields[self.edit_field] = Field(
                        field_def.name, field_def.type, field_def.length,
                        min(decimals, field_def.length - 1, 14))
        except (ValueError, FieldError):
            pass

    def cycle(self, index: int, delta: int) -> None:
        if self.stage == "options":
            self._cycle_option(index, delta)
            return
        if self.stage == "adjust":
            if index < len(self.included):
                self.included[index] = not self.included[index]
            return
        if self.stage == "adjust-edit" and index == 1:
            field_def = self.fields[self.edit_field]
            types = [code for _label, code in TYPE_NAMES]
            current = types.index(field_def.type) if field_def.type in types else 0
            type_code = types[(current + delta) % len(types)]
            from ..data.fields import FIXED_LENGTHS

            length = FIXED_LENGTHS.get(type_code, field_def.length)
            decimals = field_def.decimals if type_code == "N" else 0
            if type_code == "N":
                length = min(19, max(length, decimals + 1))
            try:
                self.fields[self.edit_field] = Field(
                    field_def.name, type_code, max(1, length), decimals)
            except FieldError as exc:
                self.status = str(exc)
            return
        if self.stage == "fields":
            database = self.database
            if database is None or index >= len(database.fields):
                return
            name = database.fields[index].name
            if name in self.chosen:
                self.chosen.remove(name)
            else:
                self.chosen.append(name)
            return
        if self.stage == "target" and self._target_exists() and index == 2:
            self.overwrite = not self.overwrite

    def _cycle_option(self, index: int, delta: int) -> None:
        options = self.options
        names = self._option_names()
        if index >= len(names):
            return
        name = names[index]
        if name in ("fieldnames", "examine", "quote_character"):
            setattr(options, name, not getattr(options, name))
        elif name == "linefeeds":
            options.linefeeds = not options.linefeeds
            self._load_row()
        elif name == "trailing_separator":
            options.trailing_separator = not options.trailing_separator
        elif name == "date_format":
            formats = list(CASE_DATE_FORMATS)
            current = formats.index(options.date_format) \
                if options.date_format in formats else 0
            options.date_format = formats[(current + delta) % len(formats)]

    # -- pickers ---------------------------------------------------------
    def accept_picker(self, value: str) -> None:
        if not value:
            self.close = True
            return
        if self.picker_kind == "format":
            self.format_key = value
            self.stage = "file"
            self.row = 0
            self._load_row()
            return

    def open_picker(self, index: int) -> None:
        return

    # -- percorsi e lettura ---------------------------------------------
    def _path(self, *, for_export: bool = False) -> Path:
        path = Path(self.path_text.strip())
        if not path.is_absolute():
            base = (self.workspace.directory if self.workspace is not None
                    else Path.cwd())
            path = base / path
        if for_export:
            return with_extension(path, self.format_key)
        if not path.suffix:
            candidate = with_extension(path, self.format_key)
            if candidate.exists():
                return candidate
        return path

    def _target_exists(self) -> bool:
        if self.workspace is None or not self.target_name:
            return False
        return self.workspace.get(self.target_name) is not None

    # -- transizioni -----------------------------------------------------
    def continue_stage(self) -> None:
        if self.stage == "file":
            if not self.path_text.strip():
                self.status = "Enter a file name."
                return
            if self.mode == "import":
                self._read_file()
            else:
                self._start_export_fields()
            return
        if self.stage == "options":
            if self.mode == "import":
                self._read_file()
            else:
                self._run_export()
            return
        if self.stage == "adjust":
            self.stage = "target"
            if not self.target_name:
                self.target_name = Path(self.path_text).stem.upper()[:8]
            self.row = 0
            self._load_row()
            return
        if self.stage == "adjust-edit":
            self.stage = "adjust"
            self.row = self.edit_field
            self._load_row()
            return
        if self.stage == "fields":
            if not self.chosen:
                self.status = "Select at least one field."
                return
            self.stage = "options"
            self.row = 0
            self._load_row()
            return
        if self.stage == "target":
            self._run_import()
            return

    def _read_file(self) -> None:
        path = self._path()
        if not path.exists():
            self.status = f"File not found: {path}"
            return
        try:
            table = read_table(path, self.format_key, self.options)
        except Exception as exc:
            self.status = str(exc)
            return
        if self.format_key in ("dbase3", "dbase2") and self.options.examine:
            # Il tipo dei DBF è già nel file: non si sovrascrive.
            pass
        elif not self.options.examine and table.rows:
            columns = [[row[index] if index < len(row) else ""
                        for row in table.rows[:1]]
                       for index in range(len(table.fields))]
            table.fields = infer_fields(
                columns, [field.name for field in table.fields],
                decimal_places=self.options.decimal_places)
        if not table.fields:
            self.status = "The file has no fields."
            return
        self.table = table
        self.fields = [Field(field.name, field.type, field.length,
                             field.decimals) for field in table.fields]
        self.included = [True] * len(self.fields)
        self.stage = "adjust"
        self.row = 0
        self.status = f"{len(table.rows)} record(s) read."
        self._load_row()

    def _start_export_fields(self) -> None:
        if self.database is None:
            self.status = "Open a database first."
            return
        self.chosen = [field.name for field in self.database.fields]
        self.stage = "fields"
        self.row = 0
        self._load_row()

    def _run_import(self) -> None:
        if self.workspace is None or self.table is None:
            self.close = True
            return
        if not self.target_name.strip():
            self.status = "Enter a database name."
            return
        selected = [field for index, field in enumerate(self.fields)
                    if index < len(self.included) and self.included[index]]
        if not selected:
            self.status = "Select at least one field."
            return
        if self._target_exists():
            if not self.overwrite:
                self.status = "Database exists; choose Overwrite."
                return
            self.workspace.drop_database(self.target_name)
        try:
            database = self.workspace.create_database(
                self.target_name, selected, description=self.description)
        except (WorkspaceError, FieldError) as exc:
            self.status = str(exc)
            return
        from ..io.common import import_text

        imported = 0
        for row in self.table.rows:
            record: dict[str, str] = {}
            for index, field_def in enumerate(self.fields):
                if index >= len(self.included) or not self.included[index]:
                    continue
                text = row[index] if index < len(row) else ""
                record[field_def.name] = import_text(field_def, text)
            database.append(record)
            imported += 1
        self.workspace.save_database(database)
        self.result = TransferResult(self._path(), imported, selected)
        self.status = f"Imported {imported} record(s) into {database.name}."
        self.close = True

    def _run_export(self) -> None:
        if self.database is None:
            self.status = "Open a database first."
            return
        selected = [field for field in self.database.fields
                    if field.name in self.chosen]
        if not selected:
            self.status = "Select at least one field."
            return
        try:
            self.result = export_from_database(
                self.database, self._path(for_export=True), self.format_key,
                selected, self.options, self.settings)
        except Exception as exc:
            self.status = str(exc)
            return
        self.status = (f"Exported {self.result.records} record(s) to "
                       f"{self.result.path.name}.")
        self.close = True

    def back_stage(self) -> None:
        if self.stage in ("file",):
            self.open_format_picker()
            self.stage = "format"
            return
        if self.stage == "options" and self.mode == "import":
            self.stage = "file"
            self.row = 0
            self._load_row()
            return
        if self.stage == "options" and self.mode == "export":
            self.stage = "fields"
            self.row = 0
            self._load_row()
            return
        if self.stage == "adjust":
            self.stage = "options"
            self.row = 0
            self._load_row()
            return
        if self.stage == "adjust-edit":
            self.stage = "adjust"
            self.row = self.edit_field
            self._load_row()
            return
        if self.stage == "fields":
            self.stage = "file"
            self.row = 0
            self._load_row()
            return
        if self.stage == "target":
            self.stage = "adjust"
            self.row = 0
            self._load_row()
            return
        self.close = True

    def handle(self, key: Key) -> None:
        if self.stage == "adjust" and key.name == "ENTER" and self.picker is None:
            rows = self.rows()
            if rows:
                self.edit_field = self.row
                self.stage = "adjust-edit"
                self.row = 0
                self._load_row()
            return
        if self.stage in ("fields",) and key.name == "ENTER" and self.picker is None:
            self.cycle(self.row, 1)
            return
        super().handle(key)

    def request_range(self) -> None:
        self.request = "range"

    def set_range(self, settings: indexing.RangeSettings) -> None:
        self.settings = settings
        self.request = ""
        self.row = 0
        self._load_row()

    def status_text(self) -> str:
        return {
            "file": "Enter the file name, with an optional path.",
            "options": "Enter the file settings.",
            "adjust": "ENTER edit field   SPACE include/exclude   F10 continue",
            "adjust-edit": "Change name, type, length and decimals.",
            "fields": "ENTER select/de-select fields.",
            "target": "Enter the new database name.",
        }.get(self.stage, "F10 continue")

    def help_text(self) -> str:
        if self.stage == "adjust":
            return "ENTER edit   SPACE include   F10 continue   ESC back"
        if self.mode == "export":
            return "F7 range   F10 export   ESC back"
        return "F10 continue   ESC back"


__all__ = ["TransferSession"]
