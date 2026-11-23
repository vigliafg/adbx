"""Fogli Lotus 1-2-3 WKS/WK1 (O9).

Il file è una sequenza di record `(tipo uint16, lunghezza uint16, corpo)`.
Si leggono celle LABEL, NUMBER, INTEGER e FORMULA (usando il risultato già
calcolato). L'esportazione produce un WK1 con una riga di intestazione
facoltativa e le date come numeri seriali con formato data.
"""

from __future__ import annotations

import struct
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Sequence

from ..data.fields import Field
from .common import (
    ExportOptions,
    ImportOptions,
    TableData,
    infer_fields,
    rows_for_export,
)

BOF = 0x0000
EOF = 0x0001
INTEGER = 0x000D
NUMBER = 0x000E
LABEL = 0x000F
FORMULA = 0x0010

FORMAT_TEXT = 0xF5
FORMAT_DATE = 0xF2
SERIAL_EPOCH = date(1899, 12, 31)
DATE_SPECIALS = {2, 3, 4, 7, 8, 9, 10}


class LotusError(ValueError):
    pass


def read_lotus(path: str | Path, options: ImportOptions) -> TableData:
    data = Path(path).read_bytes()
    if len(data) < 6:
        raise LotusError("Lotus: file too short.")
    position = 0
    cells: dict[tuple[int, int], str] = {}
    version = None
    while position + 4 <= len(data):
        opcode, length = struct.unpack_from("<HH", data, position)
        position += 4
        body = data[position:position + length]
        position += length
        if opcode == BOF:
            if len(body) >= 2:
                version = struct.unpack_from("<H", body, 0)[0]
            continue
        if opcode == EOF:
            break
        if opcode == LABEL and len(body) >= 5:
            fmt, column, row = struct.unpack_from("<BHH", body, 0)
            text = body[5:].split(b"\x00", 1)[0].decode("cp437", "replace")
            cells[(row, column)] = text
        elif opcode == NUMBER and len(body) >= 13:
            fmt, column, row, number = struct.unpack_from("<BHHd", body, 0)
            cells[(row, column)] = _number_cell(fmt, number)
        elif opcode == INTEGER and len(body) >= 7:
            fmt, column, row, number = struct.unpack_from("<BHHh", body, 0)
            cells[(row, column)] = _number_cell(fmt, float(number))
        elif opcode == FORMULA and len(body) >= 13:
            fmt, column, row, number = struct.unpack_from("<BHHd", body, 0)
            cells[(row, column)] = _number_cell(fmt, number)
    if version not in (0x0404, 0x0406) and not cells:
        raise LotusError("Lotus: not a WKS/WK1 worksheet.")
    if not cells:
        return TableData([], [], ["Lotus: no cells."])
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


def _number_cell(fmt: int, number: float) -> str:
    if _is_date_format(fmt):
        try:
            value = SERIAL_EPOCH + timedelta(days=int(round(number)))
            return value.strftime("%Y%m%d")
        except (OverflowError, ValueError):
            return ""
    kind = (fmt >> 4) & 0x07
    if kind <= 6:
        decimals = fmt & 0x0F
        return f"{number:.{decimals}f}"
    text = f"{number:.14f}".rstrip("0").rstrip(".")
    return text or "0"


def _is_date_format(fmt: int) -> bool:
    return ((fmt >> 4) & 0x07) == 0x07 and (fmt & 0x0F) in DATE_SPECIALS


def write_lotus(path: str | Path, fields: Sequence[Field],
                records: Iterable[dict[str, str]],
                options: ExportOptions) -> None:
    rows = rows_for_export(fields, records, options)
    body = bytearray()
    body += struct.pack("<HHH", BOF, 2, 0x0406)
    row_number = 0
    if options.fieldnames:
        for column, field in enumerate(fields):
            body += _label(column, row_number, field.name)
        row_number = 1
    for row in rows:
        for column, value in enumerate(row):
            field = fields[column] if column < len(fields) else None
            if field is None:
                continue
            if field.type == "N" and value.strip():
                try:
                    number = float(value)
                except ValueError:
                    number = 0.0
                body += _number(NUMBER, min(15, field.decimals), column,
                                row_number, number)
            elif field.type == "D" and len(value) == 8 and value.isdigit():
                moment = date(int(value[:4]), int(value[4:6]), int(value[6:]))
                serial = float((moment - SERIAL_EPOCH).days)
                body += _number(NUMBER, FORMAT_DATE, column, row_number, serial)
            else:
                body += _label(column, row_number, value)
        row_number += 1
    body += struct.pack("<HH", EOF, 0)
    Path(path).write_bytes(bytes(body))


def _label(column: int, row: int, text: str) -> bytes:
    raw = text.encode("cp437", "replace")[:240] + b"\x00"
    payload = struct.pack("<BHH", FORMAT_TEXT, column, row) + raw
    return struct.pack("<HH", LABEL, len(payload)) + payload


def _number(opcode: int, fmt: int, column: int, row: int,
            number: float) -> bytes:
    payload = struct.pack("<BHHd", fmt, column, row, number)
    return struct.pack("<HH", opcode, len(payload)) + payload
