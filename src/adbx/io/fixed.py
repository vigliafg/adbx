"""ASCII tabellare a colonne fisse (O9)."""

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


def read_table(path: str | Path, options: ImportOptions) -> TableData:
    text = read_text(path, options.encoding)
    raw = text.replace("\r\n", "\n").replace("\r", "\n")
    if options.linefeeds:
        lines = raw.split("\n")
    else:
        width = max(1, options.record_length)
        lines = [raw[index:index + width]
                 for index in range(0, len(raw), width)]
    if options.skip_header:
        lines = lines[options.skip_header:]
    lines = [line for line in lines if line != ""]
    if not lines:
        return TableData([], [], ["File is empty."])
    count = max(1, options.field_count)
    width = max(1, options.width)
    spacing = max(0, options.spacing)
    starts = [index * (width + spacing) for index in range(count)]
    rows: list[list[str]] = []
    for line in lines:
        rows.append([
            line[start:start + width].rstrip() if start < len(line) else ""
            for start in starts
        ])
    names: list[str] = []
    if options.fieldnames:
        names = rows.pop(0)
    columns = [[row[index] for row in rows] for index in range(count)]
    fields = infer_fields(columns, names,
                          decimal_places=options.decimal_places)
    return TableData(fields, rows)


def write_table(path: str | Path, fields: Sequence[Field],
                records: Iterable[dict[str, str]],
                options: ExportOptions) -> None:
    width = max(1, options.width)
    spacing = max(0, options.spacing)
    rows = rows_for_export(fields, records, options)
    lines: list[str] = []
    if options.fieldnames:
        lines.append(_format_row([field.name for field in fields], fields,
                                 width, spacing))
    for row in rows:
        lines.append(_format_row(row, fields, width, spacing))
    terminator = options.record_separator or "\r\n"
    text = terminator.join(lines)
    if lines:
        text += terminator
    write_text(path, text, options.encoding)


def _format_row(values: Sequence[str], fields: Sequence[Field],
                width: int, spacing: int) -> str:
    parts: list[str] = []
    for index, value in enumerate(values):
        field = fields[index] if index < len(fields) else None
        text = (value or "")[:width]
        if field is not None and field.type in ("N", "D", "L"):
            text = text.rjust(width)
        else:
            text = text.ljust(width)
        parts.append(text)
    return (" " * spacing).join(parts)
