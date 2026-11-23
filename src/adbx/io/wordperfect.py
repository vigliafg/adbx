"""Documenti secondari WordPerfect 5.1 e MultiMate (O9).

WordPerfect: i campi sono separati da `{END FIELD}` seguito da un ritorno a
capo, i record da `{END RECORD}` seguito da un'interruzione di pagina. La
sezione facoltativa `{FIELD NAMES}` elenca i nomi separati da `~`.

MultiMate: il manuale descrive un documento secondario con una pagina per
record e i codici di merge inseriti automaticamente. Qui si usa il simbolo
di merge `»` come separatore di campo e una pagina per record; le codifiche
binarie MultiMate non sono replicate (deviazione dichiarata).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from ..data.fields import Field
from .common import (
    ExportOptions,
    ImportOptions,
    TableData,
    infer_fields,
    read_text,
    rows_for_export,
    write_text,
)

END_FIELD = "{END FIELD}"
END_RECORD = "{END RECORD}"
FIELD_NAMES = "{FIELD NAMES}"
MULTIMATE_FIELD = "\u00bb"


def read_wordperfect(path: str | Path, options: ImportOptions) -> TableData:
    text = read_text(path, options.encoding)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    names: list[str] = []
    marker = text.find(FIELD_NAMES)
    if marker == 0:
        end = text.find(END_RECORD)
        if end >= 0:
            header = text[len(FIELD_NAMES):end]
            names = [part.strip() for part in header.split("~") if part.strip()]
            text = text[end + len(END_RECORD):]
    text = text.replace("\f", "\n")
    chunks = text.split(END_RECORD)
    rows: list[list[str]] = []
    width = 0
    for chunk in chunks:
        chunk = chunk.strip("\n")
        if not chunk.strip():
            continue
        values = chunk.split(END_FIELD)
        if values and not values[-1].strip():
            values.pop()
        cleaned = [value.strip("\n").strip() for value in values]
        if not any(cleaned):
            continue
        width = max(width, len(cleaned))
        rows.append(cleaned)
    if not rows:
        return TableData([], [], ["WordPerfect: no records."])
    columns = [[row[index] if index < len(row) else "" for row in rows]
               for index in range(width)]
    fields = infer_fields(columns, names,
                          decimal_places=options.decimal_places)
    return TableData(fields, rows)


def write_wordperfect(path: str | Path, fields: Sequence[Field],
                      records: Iterable[dict[str, str]],
                      options: ExportOptions) -> None:
    rows = rows_for_export(fields, records, options)
    parts: list[str] = []
    if options.fieldnames:
        names = "~".join(field.name for field in fields) + "~~"
        parts.append(f"{FIELD_NAMES}{names}{END_RECORD}\f\n")
    for row in rows:
        body = "".join(f"{value}{END_FIELD}\n" for value in row)
        parts.append(f"{body}{END_RECORD}\f\n")
    write_text(path, "".join(parts), options.encoding)


def read_multimate(path: str | Path, options: ImportOptions) -> TableData:
    text = read_text(path, options.encoding)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    names: list[str] = []
    pages = text.split("\f")
    if options.fieldnames and pages:
        header = pages.pop(0)
        names = [part.strip() for part in header.split(MULTIMATE_FIELD)
                 if part.strip()]
    rows: list[list[str]] = []
    width = 0
    for page in pages:
        page = page.strip("\n")
        if not page.strip():
            continue
        values = [part.strip("\n").strip() for part in page.split(MULTIMATE_FIELD)]
        if values and not values[-1]:
            values.pop()
        if not any(values):
            continue
        width = max(width, len(values))
        rows.append(values)
    if not rows:
        return TableData([], [], ["MultiMate: no records."])
    columns = [[row[index] if index < len(row) else "" for row in rows]
               for index in range(width)]
    fields = infer_fields(columns, names,
                          decimal_places=options.decimal_places)
    return TableData(fields, rows)


def write_multimate(path: str | Path, fields: Sequence[Field],
                    records: Iterable[dict[str, str]],
                    options: ExportOptions) -> None:
    rows = rows_for_export(fields, records, options)
    parts: list[str] = []
    if options.fieldnames:
        parts.append(MULTIMATE_FIELD.join(field.name for field in fields) + "\f\n")
    for row in rows:
        parts.append(MULTIMATE_FIELD.join(row) + "\f\n")
    write_text(path, "".join(parts), options.encoding)
