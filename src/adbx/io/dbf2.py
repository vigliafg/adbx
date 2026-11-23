"""File dBASE II (.DBF) per il capitolo 20.

dBASE II usa un'intestazione di 8 byte e descrittori di campo di 16 byte,
senza tipo Data e con al massimo 32 campi. In esportazione le date diventano
carattere (come da manuale); in importazione si conserva il tipo letto.
"""

from __future__ import annotations

import struct
from datetime import date
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

MAX_FIELDS = 32


class Dbf2Error(ValueError):
    pass


def read_dbf2(path: str | Path, options: ImportOptions) -> TableData:
    data = Path(path).read_bytes()
    if len(data) < 10:
        raise Dbf2Error("dBASE II: header too short.")
    version, year, month, day, records, header_length, record_length = \
        struct.unpack_from("<BBBBHHH", data, 0)
    if version != 0x02:
        raise Dbf2Error("dBASE II: invalid version byte.")
    if header_length < 10 + 16 or record_length < 1:
        raise Dbf2Error("dBASE II: invalid header lengths.")
    descriptors = data[10:header_length]
    fields: list[Field] = []
    offset = 0
    while offset + 16 <= len(descriptors) and descriptors[offset] != 0x0D:
        block = descriptors[offset:offset + 16]
        name = block[:11].split(b"\x00", 1)[0].decode("cp437", "replace").strip()
        ftype = chr(block[11]).upper()
        length = block[12]
        decimals = block[13]
        offset += 16
        if not name:
            continue
        if ftype not in ("C", "N", "L"):
            ftype = "C"
        try:
            fields.append(Field(name, ftype, max(1, length),
                                decimals if ftype == "N" else 0))
        except Exception:
            fields.append(Field(name[:10], "C", max(1, length), 0))
    if not fields:
        raise Dbf2Error("dBASE II: no fields.")
    rows: list[list[str]] = []
    position = header_length
    for _index in range(records):
        if position + record_length > len(data):
            break
        chunk = data[position:position + record_length]
        position += record_length
        cursor = 1
        row: list[str] = []
        for field in fields:
            raw = chunk[cursor:cursor + field.length]
            cursor += field.length
            text = raw.decode("cp437", "replace")
            row.append(text.strip() if field.type in ("N", "L") else text.rstrip())
        rows.append(row)
    columns = [[row[index] if index < len(row) else "" for row in rows]
               for index in range(len(fields))]
    if options.examine:
        names = [field.name for field in fields]
        fields = infer_fields(columns, names,
                              decimal_places=options.decimal_places)
    return TableData(fields, rows)


def write_dbf2(path: str | Path, fields: Sequence[Field],
               records: Iterable[dict[str, str]],
               options: ExportOptions) -> None:
    if len(fields) > MAX_FIELDS:
        raise Dbf2Error("dBASE II holds at most 32 fields.")
    out_fields: list[Field] = []
    for field in fields:
        if field.type == "D":
            out_fields.append(Field(field.name, "C", 8, 0))
        elif field.type == "M":
            out_fields.append(Field(field.name, "C", 254, 0))
        elif field.type == "L":
            out_fields.append(field)
        else:
            out_fields.append(field)
    rows = rows_for_export(out_fields, records, options)
    header_length = 10 + 16 * len(out_fields) + 1
    record_length = 1 + sum(field.length for field in out_fields)
    today = date.today()
    header = bytearray([0x02, today.year - 1900, today.month, today.day])
    header += struct.pack("<HHH", len(rows), header_length, record_length)
    for field in out_fields:
        block = bytearray(16)
        raw = field.name.encode("ascii", "replace")[:11]
        block[:len(raw)] = raw
        block[11] = ord(field.type)
        block[12] = field.length
        block[13] = field.decimals
        header += block
    header += b"\x0d"
    body = bytearray()
    for row in rows:
        body += b" "
        for field, value in zip(out_fields, row):
            if field.type == "C":
                text = value[:field.length].ljust(field.length)
            elif field.type == "N":
                text = value.strip().rjust(field.length)[-field.length:]
            else:
                marker = value.strip().upper()
                text = ("T" if marker in ("1", "T", "Y", "TRUE") else
                        "F" if marker in ("0", "F", "N", "FALSE") else " "
                        ).ljust(1)
            body += text.encode("cp437", "replace")
    Path(path).write_bytes(bytes(header) + bytes(body) + b"\x1a")
