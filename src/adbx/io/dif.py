"""File DIF (Data Interchange Format) di VisiCalc (O9).

Il DIF è un formato testuale a blocchi: `TABLE`, `VECTORS`, `TUPLES`, poi
righe `BOT`/`EOD`. I valori numerici sono scritti senza virgolette, i testi
fra virgolette con le virgolette interne raddoppiate.
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


class DifError(ValueError):
    pass


def read_dif(path: str | Path, options: ImportOptions) -> TableData:
    text = read_text(path, options.encoding)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    position = 0
    while position < len(lines) and lines[position].strip() != "TUPLES":
        position += 1
    if position >= len(lines):
        raise DifError("DIF: TUPLES section not found.")
    position += 1
    while position < len(lines) and not lines[position].strip():
        position += 1
    if position >= len(lines):
        raise DifError("DIF: missing tuple count.")
    try:
        count, width = (int(part.strip())
                        for part in lines[position].split(",")[:2])
    except ValueError as exc:
        raise DifError("DIF: invalid tuple count.") from exc
    position += 1
    rows: list[list[str]] = []
    while position < len(lines) and len(rows) < count:
        line = lines[position].strip()
        position += 1
        if not line:
            continue
        if line in ("EOD", "-1,0"):
            continue
        if line == "BOT":
            continue
        values: list[str] = [_parse_value(line)]
        for _index in range(width - 1):
            if position >= len(lines):
                break
            values.append(_parse_value(lines[position]))
            position += 1
        rows.append(values)
    columns = [[row[index] if index < len(row) else "" for row in rows]
               for index in range(width)]
    fields = infer_fields(columns,
                          [f"FIELD{index + 1}" for index in range(width)],
                          decimal_places=options.decimal_places)
    return TableData(fields, rows)


def _parse_value(line: str) -> str:
    text = line.strip()
    if text.startswith('"'):
        return text[1:-1].replace('""', '"') if text.endswith('"') else text[1:]
    if text in ("V", "NA", "ERROR"):
        return ""
    if text == "TRUE":
        return "T"
    if text == "FALSE":
        return "F"
    return text


def write_dif(path: str | Path, fields: Sequence[Field],
              records: Iterable[dict[str, str]],
              options: ExportOptions) -> None:
    rows = rows_for_export(fields, records, options)
    lines: list[str] = ["TABLE", "0,1"]
    for field in fields:
        lines.append(f'"{field.name}"')
    lines.append("VECTORS")
    for field in fields:
        lines.append(f"0,{max(1, field.length)}")
    lines.append('""')
    lines.append("TUPLES")
    lines.append(f"{len(rows)},{len(fields)}")
    for row in rows:
        lines.append("-1,0")
        lines.append("BOT")
        for index, value in enumerate(row):
            field = fields[index] if index < len(fields) else None
            if field is not None and field.type == "N" and value.strip():
                lines.append(value.strip())
            else:
                lines.append('"' + value.replace('"', '""') + '"')
    lines.append("-1,0")
    lines.append("EOD")
    write_text(path, "\r\n".join(lines) + "\r\n", options.encoding)
