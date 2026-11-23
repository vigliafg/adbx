"""Lettura dell'intestazione dei file dBASE (.DBF).

Serve al guscio per mostrare nome, data e numero di record senza aprire il
database: lo strato dati vero arriverà con O2. Il reader è volutamente minimo
(intestazione + elenco campi) e tollerante: un file rovinato non deve far
fallire il browser di directory.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import date
from pathlib import Path


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


__all__ = ["DbfError", "DbfField", "DbfHeader", "read_header", "record_count"]
