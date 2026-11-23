"""Helper per costruire file DBF sintetici nei test."""

from __future__ import annotations

import os
import struct
from datetime import datetime
from pathlib import Path

DEFAULT_FIELDS = tuple(
    (f"FIELD{index}", "C", 10, 0) for index in range(1, 5)
)


def write_dbf(path: Path, *, records: int = 0, fields=DEFAULT_FIELDS,
              updated: tuple[int, int, int] = (1993, 6, 1)) -> Path:
    year, month, day = updated
    header_length = 32 + 32 * len(fields) + 1
    record_length = 1 + sum(field[2] for field in fields)

    data = bytearray()
    data += bytes([0x03, year - 1900, month, day])
    data += struct.pack("<IHH", records, header_length, record_length)
    data += b"\x00" * 20
    for name, ftype, length, decimals in fields:
        block = bytearray(32)
        raw = name.upper().encode("ascii")[:11]
        block[:len(raw)] = raw
        block[11] = ord(ftype)
        block[16] = length
        block[17] = decimals
        data += block
    data += b"\x0d"
    data += b"\x00" * (records * record_length)
    path.write_bytes(bytes(data))
    stamp = datetime(year, month, day, 12, 0).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def make_tutorial_set(directory: Path) -> Path:
    """Dataset con i nomi del Tutorial, valori ridotti ma coerenti."""
    directory.mkdir(parents=True, exist_ok=True)
    set_file = directory / "ALPHAVID.SET"
    set_file.write_text("", encoding="ascii")
    stamp = datetime(1993, 6, 1, 12, 0).timestamp()
    os.utime(set_file, (stamp, stamp))
    write_dbf(directory / "AVMOVIES.DBF", records=50,
              fields=(("TAPE_ID", "C", 4, 0), ("TAPE_TITLE", "C", 40, 0),
                      ("TAPE_DESC", "M", 10, 0), ("SUBJECT", "C", 20, 0),
                      ("RUNTIME", "N", 3, 0), ("RATING", "C", 5, 0),
                      ("TAPETYPE", "C", 5, 0), ("AVAILABLE", "L", 1, 0),
                      ("PRICE", "N", 6, 2), ("QUANTITY", "N", 3, 0),
                      ("NOTES", "C", 20, 0)))
    write_dbf(directory / "AVPATRON.DBF", records=28,
              fields=(("CUST_ID", "C", 4, 0), ("LASTNAME", "C", 15, 0)))
    write_dbf(directory / "AVSALES.DBF", records=109,
              fields=tuple((f"F{index}", "C", 8, 0) for index in range(1, 25)))
    write_dbf(directory / "AVSALES2.DBF", records=16,
              fields=(("INV_NO", "C", 4, 0), ("QUANTITY", "N", 3, 0)))
    return directory
