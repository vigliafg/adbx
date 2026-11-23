"""File SYLK (Symbolic Link) per Multiplan (O9).

Le celle sono record `C;Y<riga>;X<colonna>;K<valore>`; `K` introduce un
numero oppure una stringa fra virgolette. Il file termina con `E`.
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


class SylkError(ValueError):
    pass


def read_sylk(path: str | Path, options: ImportOptions) -> TableData:
    text = read_text(path, options.encoding)
    cells: dict[tuple[int, int], str] = {}
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line.startswith("C;"):
            continue
        row = column = None
        value = ""
        for part in _split_fields(line):
            if part.startswith("Y") and part[1:].isdigit():
                row = int(part[1:]) - 1
            elif part.startswith("X") and part[1:].isdigit():
                column = int(part[1:]) - 1
            elif part.startswith("K"):
                value = _parse_value(part[1:])
            elif part == "E":
                value = ""
        if row is None or column is None:
            continue
        cells[(row, column)] = value
    if not cells:
        return TableData([], [], ["SYLK: no cell records."])
    max_row = max(row for row, _column in cells)
    max_column = max(column for _row, column in cells)
    rows = [[cells.get((row, column), "")
             for column in range(max_column + 1)]
            for row in range(max_row + 1)]
    names: list[str] = []
    if options.fieldnames:
        names = rows.pop(0)
    columns = [[row[index] if index < len(row) else "" for row in rows]
               for index in range(max_column + 1)]
    fields = infer_fields(columns, names,
                          decimal_places=options.decimal_places)
    return TableData(fields, rows)


def _split_fields(line: str) -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    quoted = False
    index = 0
    while index < len(line):
        char = line[index]
        if char == '"':
            if quoted and index + 1 < len(line) and line[index + 1] == '"':
                current.extend(['"', '"'])
                index += 2
                continue
            quoted = not quoted
            current.append(char)
            index += 1
            continue
        if char == ";" and not quoted:
            fields.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    fields.append("".join(current))
    return fields


def _parse_value(text: str) -> str:
    text = text.strip()
    if text.startswith('"'):
        return text[1:-1].replace('""', '"') if text.endswith('"') else text[1:]
    return text


def write_sylk(path: str | Path, fields: Sequence[Field],
               records: Iterable[dict[str, str]],
               options: ExportOptions) -> None:
    rows = rows_for_export(fields, records, options)
    lines: list[str] = ["ID;P"]
    row_number = 1
    if options.fieldnames:
        for column, field in enumerate(fields, start=1):
            lines.append(f'C;Y{row_number};X{column};K"{field.name}"')
        row_number += 1
    for row in rows:
        for column, value in enumerate(row, start=1):
            field = fields[column - 1] if column - 1 < len(fields) else None
            if field is not None and field.type == "N" and value.strip():
                cell = value.strip()
            else:
                cell = '"' + value.replace('"', '""') + '"'
            lines.append(f"C;Y{row_number};X{column};K{cell}")
        row_number += 1
    lines.append("E")
    write_text(path, "\r\n".join(lines) + "\r\n", options.encoding)
