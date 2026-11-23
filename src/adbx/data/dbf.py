"""Lettura e scrittura dei file dBASE (.DBF) e dei memo (.DBT).

Il browser di directory usa solo l'intestazione. Lo strato dati importa i
record veri e, quando un database viene salvato, riscrive il .DBF: il file
resta il formato di scambio con il mondo dBASE, mentre SQLite è il motore di
lavoro (PLAN §3.3).

Il reader è tollerante: un file rovinato non deve far fallire il browser e
un record troncato termina l'importazione invece di propagare l'errore.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from .fields import MAX_MEMO, Field


class DbfError(ValueError):
    """Il file non è un DBF leggibile."""


@dataclass(frozen=True)
class DbfField:
    name: str
    type: str
    length: int
    decimals: int


@dataclass(frozen=True)
class DbfHeader:
    version: int
    updated: date | None
    records: int
    header_length: int
    record_length: int
    fields: tuple[DbfField, ...]

    @property
    def field_count(self) -> int:
        return len(self.fields)


# Tipi campo accettati da dBASE III/Alpha Four per un database "normale".
_KNOWN_TYPES = set("CDNLM")


def read_header(path: str | Path) -> DbfHeader:
    """Legge l'intestazione di un DBF; solleva `DbfError` se non valida."""
    path = Path(path)
    try:
        with path.open("rb") as handle:
            head = handle.read(32)
            if len(head) < 32:
                raise DbfError("intestazione troncata")
            version = head[0]
            year, month, day = head[1], head[2], head[3]
            records, header_length, record_length = struct.unpack_from("<IHH", head, 4)
            if header_length < 33 or record_length < 1:
                raise DbfError("lunghezze non valide")
            if header_length > 32 + 32 * 255:
                raise DbfError("intestazione troppo grande")
            raw_fields = handle.read(header_length - 32)
    except OSError as exc:
        raise DbfError(str(exc)) from exc

    fields: list[DbfField] = []
    offset = 0
    while offset + 32 <= len(raw_fields):
        block = raw_fields[offset:offset + 32]
        if block[0] == 0x0D:
            break
        name = block[:11].split(b"\x00", 1)[0].decode("cp437", "replace").strip()
        ftype = chr(block[11]).upper()
        length = block[16]
        decimals = block[17]
        if name and ftype in _KNOWN_TYPES:
            fields.append(DbfField(name, ftype, length, decimals))
        offset += 32

    updated: date | None = None
    if year and 1 <= month <= 12 and 1 <= day <= 31:
        try:
            updated = date(1900 + year, month, day)
        except ValueError:
            updated = None

    return DbfHeader(
        version=version,
        updated=updated,
        records=max(0, records),
        header_length=header_length,
        record_length=record_length,
        fields=tuple(fields),
    )


def record_count(path: str | Path) -> int | None:
    try:
        return read_header(path).records
    except DbfError:
        return None


@dataclass(frozen=True)
class DbfRow:
    """Un record importato: valori canonici, memo già risolti."""

    deleted: bool
    values: dict[str, str]


def memo_path(path: str | Path) -> Path:
    path = Path(path)
    for suffix in (".DBT", ".dbt", ".Dbt"):
        candidate = path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return path.with_suffix(".DBT")


def read_memo(path: str | Path, pointer: str, *, block_size: int = 512) -> str:
    """Legge il testo di un memo dato il puntatore a 10 caratteri."""
    pointer = (pointer or "").strip()
    if not pointer.isdigit() or int(pointer) <= 0:
        return ""
    block = int(pointer)
    memo = memo_path(path)
    try:
        with memo.open("rb") as handle:
            handle.seek(block * block_size)
            chunks: list[bytes] = []
            while True:
                chunk = handle.read(block_size)
                if not chunk:
                    break
                stop = chunk.find(b"\x1a")
                if stop >= 0:
                    chunks.append(chunk[:stop])
                    break
                chunks.append(chunk)
                if len(chunks) > (MAX_MEMO // block_size) + 2:
                    break
    except OSError:
        return ""
    raw = b"".join(chunks)
    return raw.split(b"\x1a", 1)[0].decode("cp437", "replace")


def read_rows(path: str | Path, header: DbfHeader | None = None,
              *, with_memos: bool = True) -> list[DbfRow]:
    """Legge tutti i record di un DBF, nell'ordine fisico del file."""
    path = Path(path)
    header = header or read_header(path)
    rows: list[DbfRow] = []
    needed = header.header_length + header.records * header.record_length
    try:
        with path.open("rb") as handle:
            handle.seek(header.header_length)
            raw = handle.read(max(0, needed - header.header_length))
    except OSError as exc:
        raise DbfError(str(exc)) from exc

    for index in range(header.records):
        start = index * header.record_length
        record = raw[start:start + header.record_length]
        if len(record) < header.record_length:
            break
        deleted = record[:1] == b"*"
        values: dict[str, str] = {}
        offset = 1
        for field in header.fields:
            chunk = record[offset:offset + field.length]
            offset += field.length
            values[field.name] = _decode_field(path, field, chunk, with_memos)
        rows.append(DbfRow(deleted=deleted, values=values))
    return rows


def _decode_field(path: Path, field: DbfField, chunk: bytes, with_memos: bool) -> str:
    raw = chunk.decode("cp437", "replace")
    if field.type == "C":
        return raw.rstrip(" \x00")
    if field.type == "N":
        return raw.strip()
    if field.type == "D":
        text = raw.strip()
        return text if len(text) == 8 and text.isdigit() else ""
    if field.type == "L":
        first = raw.strip()[:1].upper()
        if first in ("T", "Y"):
            return "1"
        if first in ("F", "N"):
            return "0"
        return ""
    if field.type == "M":
        if not with_memos:
            return raw.strip()
        return read_memo(path, raw)
    return raw.rstrip()


def write_rows(path: str | Path, fields: Sequence[Field],
               rows: Sequence[tuple[bool, dict[str, str]]]) -> None:
    """Riscrive un DBF (e il .DBT) in modo atomico.

    `rows` contiene `(deleted, values)` con i valori canonici dello strato
    dati. I memo sono accodati al .DBT e nel DBF resta il puntatore.
    """
    path = Path(path)
    memo_fields = [field for field in fields if field.is_memo]
    memo_blocks: dict[tuple[int, str], int] = {}
    memo_data = bytearray(b"\x00" * 512)
    next_block = 1
    if memo_fields:
        for index, (_deleted, values) in enumerate(rows):
            for field in memo_fields:
                body = values.get(field.name, "")
                if not body:
                    continue
                encoded = body.encode("cp437", "replace")
                block = bytearray(encoded[:MAX_MEMO])
                block += b"\x1a"
                padding = (-len(block)) % 512
                block += b"\x00" * padding
                memo_data += block
                memo_blocks[(index, field.name)] = next_block
                next_block += len(block) // 512
        struct.pack_into("<I", memo_data, 0, next_block)

    header_length = 32 + 32 * len(fields) + 1
    record_length = 1 + sum(field.length for field in fields)
    today = date.today()
    header = bytearray()
    header += bytes([0x83 if memo_fields else 0x03, today.year - 1900,
                     today.month, today.day])
    header += struct.pack("<IHH", len(rows), header_length, record_length)
    header += b"\x00" * 20
    for field in fields:
        block = bytearray(32)
        name = field.name.encode("ascii", "replace")[:11]
        block[:len(name)] = name
        block[11] = ord(field.type)
        block[16] = field.length & 0xFF
        block[17] = field.decimals & 0xFF
        header += block
    header += b"\x0d"

    body = bytearray()
    for index, (deleted, values) in enumerate(rows):
        body += b"*" if deleted else b" "
        for field in fields:
            body += _encode_field(field, values.get(field.name, ""),
                                  memo_blocks.get((index, field.name)))

    _atomic_write(path, bytes(header) + bytes(body) + b"\x1a")
    if memo_fields:
        _atomic_write(memo_path(path), bytes(memo_data))


def _encode_field(field: Field, value: str, memo_block: int | None) -> bytes:
    if field.type == "C":
        text = (value or "")[: field.length].ljust(field.length)
    elif field.type == "N":
        text = (value or "").strip().rjust(field.length)
    elif field.type == "D":
        text = (value or "").strip()[:8].ljust(8)
    elif field.type == "L":
        text = ("T" if value == "1" else "F" if value == "0" else " ").ljust(1)
    elif field.type == "M":
        text = ("" if memo_block is None else str(memo_block)).rjust(10)
    else:
        text = (value or "")[: field.length].ljust(field.length)
    return text.encode("cp437", "replace")


def _atomic_write(path: Path, data: bytes) -> None:
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
    os.replace(temporary, path)


def canonical_row(path: str | Path, row: DbfRow,
                  fields: Sequence[Field]) -> dict[str, str]:
    """Normalizza i valori grezzi di un DBF per lo strato dati."""
    values: dict[str, str] = {}
    for field in fields:
        value = row.values.get(field.name, "")
        if field.type == "D":
            values[field.name] = value if len(value) == 8 and value.isdigit() else ""
        elif field.type == "L":
            values[field.name] = value if value in ("1", "0") else ""
        elif field.type == "N":
            values[field.name] = value.strip()
        else:
            values[field.name] = value
    return values


__all__ = [
    "DbfError",
    "DbfField",
    "DbfHeader",
    "DbfRow",
    "canonical_row",
    "memo_path",
    "read_header",
    "read_memo",
    "read_rows",
    "record_count",
    "write_rows",
]
