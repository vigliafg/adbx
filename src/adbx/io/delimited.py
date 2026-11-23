"""ASCII carattere-separato e CSV (O9).

Il formato è quello del capitolo 20: separatore configurabile, campi
carattere fra virgolette, nomi di campo nella prima riga, soppressione degli
spazi finali e del separatore finale, record terminati da CR/LF.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from ..data.fields import Field
from .common import (
    ExportOptions,
    ImportOptions,
    TableData,
    default_columns,
    infer_fields,
    read_text,
    rows_for_export,
    write_text,
)


def read_delimited(path: str | Path, options: ImportOptions) -> TableData:
    text = read_text(path, options.encoding)
    separator = _char(options.separator, ",")
    quote = _char(options.quote, '"')
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if options.skip_header:
        lines = lines[options.skip_header:]
    lines = [line for line in lines if line != "" or not options.linefeeds]
    rows = [_parse_line(line, separator, quote) for line in lines]
    if not rows:
        return TableData([], [], ["File is empty."])
    names: list[str] = []
    if options.fieldnames:
        names = rows.pop(0)
    columns = default_columns(rows)
    if not columns:
        return TableData([], [], ["File has no data rows."])
    fields = infer_fields(columns, names,
                          decimal_places=options.decimal_places)
    return TableData(fields, [list(row) for row in rows])


def _parse_line(line: str, separator: str, quote: str) -> list[str]:
    if not separator:
        return [line]
    values: list[str] = []
    current: list[str] = []
    quoted = False
    index = 0
    while index < len(line):
        char = line[index]
        if quoted:
            if char == quote:
                if index + 1 < len(line) and line[index + 1] == quote:
                    current.append(quote)
                    index += 2
                    continue
                quoted = False
                index += 1
                continue
            current.append(char)
            index += 1
            continue
        if char == quote and not current:
            quoted = True
            index += 1
            continue
        if char == separator:
            values.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    values.append("".join(current))
    return values


def write_delimited(path: str | Path, fields: Sequence[Field],
                    records: Iterable[dict[str, str]],
                    options: ExportOptions) -> None:
    separator = _char(options.separator, ",")
    quote = _char(options.quote, '"')
    rows = rows_for_export(fields, records, options)
    lines: list[str] = []
    if options.fieldnames:
        lines.append(separator.join(field.name for field in fields))
    for row in rows:
        lines.append(_join(row, fields, separator, quote, options))
    terminator = options.record_separator or "\r\n"
    text = terminator.join(lines)
    if lines:
        text += terminator
    write_text(path, text, options.encoding)


def _join(values: Sequence[str], fields: Sequence[Field], separator: str,
          quote: str, options: ExportOptions) -> str:
    parts: list[str] = []
    for index, value in enumerate(values):
        field = fields[index] if index < len(fields) else None
        text = value if value is not None else ""
        if field is not None and field.type in ("C", "M") \
                and options.quote_character:
            escaped = text.replace(quote, quote + quote)
            text = quote + escaped + quote
        elif field is not None and field.type == "D" \
                and options.quote_character and separator in text:
            text = quote + text + quote
        parts.append(text)
    if options.trailing_separator:
        return separator.join(parts) + separator
    return separator.join(parts)


def _char(value: str, default: str) -> str:
    if not value:
        return default
    if value.startswith("^") and len(value) >= 2:
        return chr(ord(value[1].upper()) - 64)
    return value[:1]
