"""Registro dei formati di import/export (O9)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from ..data import indexing
from ..data.fields import Field, FieldError, parse_value
from ..data.workspace import Database, WorkspaceError
from .common import (
    ExportOptions,
    ImportOptions,
    TableData,
    import_text,
)
from .dbf2 import read_dbf2, write_dbf2
from .delimited import read_delimited, write_delimited
from .dif import read_dif, write_dif
from .fixed import read_table as read_fixed
from .fixed import write_table as write_fixed
from .lotus import read_lotus, write_lotus
from .sylk import read_sylk, write_sylk
from .wordperfect import (
    read_multimate,
    read_wordperfect,
    write_multimate,
    write_wordperfect,
)


@dataclass(frozen=True)
class FormatSpec:
    key: str
    label: str
    extension: str
    importable: bool = True
    exportable: bool = True


FORMATS: tuple[FormatSpec, ...] = (
    FormatSpec("dbase2", "dBASE II DBF file", "DBF"),
    FormatSpec("dbase3", "dBASE III/IV DBF file", "DBF"),
    FormatSpec("delimited", "Character separated ASCII file", "ASC"),
    FormatSpec("csv", "CSV (comma separated)", "CSV"),
    FormatSpec("table", "Table ASCII file", "TXT"),
    FormatSpec("dif", "VisiCalc / DIF file", "DIF"),
    FormatSpec("sylk", "SYLK / Multiplan file", "SLK"),
    FormatSpec("lotus", "Lotus 1-2-3 / Symphony worksheet", "WK1"),
    FormatSpec("wordperfect", "WordPerfect merge document", "MRG"),
    FormatSpec("multimate", "MultiMate secondary document", "DOC"),
)
BY_KEY = {spec.key: spec for spec in FORMATS}


@dataclass
class TransferResult:
    path: Path
    records: int
    fields: list[Field]
    skipped: int = 0
    notes: list[str] = None

    def __post_init__(self) -> None:
        if self.notes is None:
            self.notes = []


def spec_for(key: str) -> FormatSpec:
    try:
        return BY_KEY[key]
    except KeyError as exc:
        raise ValueError(f"Unknown file format: {key}") from exc


def default_extension(key: str) -> str:
    return "." + spec_for(key).extension


def with_extension(path: str | Path, key: str) -> Path:
    target = Path(path)
    if not target.suffix:
        target = target.with_suffix(default_extension(key))
    return target


def read_table(path: str | Path, key: str,
               options: ImportOptions | None = None) -> TableData:
    spec = spec_for(key)
    if not spec.importable:
        raise ValueError(f"{spec.label} is export only.")
    options = options or ImportOptions()
    if key == "dbase2":
        return read_dbf2(path, options)
    if key == "dbase3":
        return _read_dbase3(path, options)
    if key in ("delimited", "csv"):
        if key == "csv":
            options = _clone(options, separator=",", quote='"')
        return read_delimited(path, options)
    if key == "table":
        return read_fixed(path, options)
    if key == "dif":
        return read_dif(path, options)
    if key == "sylk":
        return read_sylk(path, options)
    if key == "lotus":
        return read_lotus(path, options)
    if key == "wordperfect":
        return read_wordperfect(path, options)
    if key == "multimate":
        return read_multimate(path, options)
    raise ValueError(f"Unknown file format: {key}")


def write_table(path: str | Path, key: str, fields: Sequence[Field],
                records: Iterable[dict[str, str]],
                options: ExportOptions | None = None) -> None:
    spec = spec_for(key)
    if not spec.exportable:
        raise ValueError(f"{spec.label} is import only.")
    options = options or ExportOptions()
    if key == "dbase2":
        write_dbf2(path, fields, records, options)
        return
    if key == "dbase3":
        _write_dbase3(path, fields, records)
        return
    if key in ("delimited", "csv"):
        if key == "csv":
            options = _clone_export(options, separator=",", quote='"')
        write_delimited(path, fields, records, options)
        return
    if key == "table":
        write_fixed(path, fields, records, options)
        return
    if key == "dif":
        write_dif(path, fields, records, options)
        return
    if key == "sylk":
        write_sylk(path, fields, records, options)
        return
    if key == "lotus":
        write_lotus(path, fields, records, options)
        return
    if key == "wordperfect":
        write_wordperfect(path, fields, records, options)
        return
    if key == "multimate":
        write_multimate(path, fields, records, options)
        return
    raise ValueError(f"Unknown file format: {key}")


def _read_dbase3(path: str | Path, options: ImportOptions) -> TableData:
    from ..data.dbf import canonical_row, read_header, read_rows

    header = read_header(path)
    fields = [Field(field.name, field.type, field.length, field.decimals)
              for field in header.fields]
    rows: list[list[str]] = []
    for row in read_rows(path, header):
        if row.deleted:
            continue
        values = canonical_row(path, row, fields)
        rows.append([values.get(field.name, "") for field in fields])
    return TableData(fields, rows)


def _write_dbase3(path: str | Path, fields: Sequence[Field],
                  records: Iterable[dict[str, str]]) -> None:
    from ..data.dbf import write_rows

    write_rows(path, fields, [(False, record) for record in records])


def _clone(options: ImportOptions, **changes) -> ImportOptions:
    data = dict(options.__dict__)
    data.update(changes)
    return ImportOptions(**data)


def _clone_export(options: ExportOptions, **changes) -> ExportOptions:
    data = dict(options.__dict__)
    data.update(changes)
    return ExportOptions(**data)


def import_into_workspace(workspace, name: str, path: str | Path, key: str,
                          options: ImportOptions | None = None,
                          fields: Sequence[Field] | None = None,
                          description: str = "") -> TransferResult:
    """Legge un file e crea un database nel workspace."""
    table = read_table(path, key, options)
    selected = list(fields) if fields is not None else list(table.fields)
    if not selected:
        raise ValueError("The file has no fields.")
    try:
        database = workspace.create_database(name, selected,
                                             description=description)
    except (WorkspaceError, FieldError) as exc:
        raise ValueError(str(exc)) from exc
    skipped = 0
    imported = 0
    for row in table.rows:
        record: dict[str, str] = {}
        for index, field in enumerate(selected):
            text = row[index] if index < len(row) else ""
            record[field.name] = import_text(field, text)
        database.append(record)
        imported += 1
    workspace.save_database(database)
    return TransferResult(Path(path), imported, selected, skipped,
                          list(table.notes))


def export_from_database(database: Database, path: str | Path, key: str,
                         fields: Sequence[Field] | None = None,
                         options: ExportOptions | None = None,
                         settings: indexing.RangeSettings | None = None) -> TransferResult:
    """Scrive i record del range corrente nel formato scelto."""
    selected = list(fields) if fields is not None else list(database.fields)
    seqs = indexing.ordered_sequences(database, settings)
    records = [database.read(seq) for seq in seqs]
    target = with_extension(path, key)
    if target.exists():
        target.unlink()
    write_table(target, key, selected, records, options)
    return TransferResult(target, len(records), selected, 0, [])


def coerce_table(table: TableData, fields: Sequence[Field]) -> list[dict[str, str]]:
    """Converte le righe grezze nei valori canonici dei campi scelti."""
    result: list[dict[str, str]] = []
    for row in table.rows:
        record: dict[str, str] = {}
        for index, field in enumerate(fields):
            text = row[index] if index < len(row) else ""
            try:
                record[field.name] = import_text(field, text)
            except FieldError:
                record[field.name] = ""
        result.append(record)
    return result


def parse_field_value(field: Field, text: str) -> str:
    try:
        return parse_value(field, text)
    except FieldError:
        return ""
