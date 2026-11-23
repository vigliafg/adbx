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
              rows: list[tuple[str, ...]] | None = None,
              updated: tuple[int, int, int] = (1993, 6, 1)) -> Path:
    year, month, day = updated
    if rows is not None:
        records = len(rows)
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
    if rows is None:
        data += b"\x00" * (records * record_length)
    else:
        for row in rows:
            data += b" "
            for (name, ftype, length, decimals), value in zip(fields, row):
                text = str(value)
                if ftype == "N":
                    text = text.rjust(length)
                else:
                    text = text.ljust(length)
                data += text.encode("cp437", "replace")[:length]
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


def make_movies(tmp_path):
    """Database AVMOVIES ridotto, con titoli, soggetti, rating e memo."""
    from adbx.data.fields import Field
    from adbx.data.workspace import Workspace

    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVMOVIES", [
        Field("TAPE_ID", "C", 4), Field("TAPE_TITLE", "C", 30),
        Field("TAPE_DESC", "M", 10), Field("SUBJECT", "C", 20),
        Field("RATING", "C", 5),
    ])
    rows = [
        ("1006", "Dumbo", "A Disney cartoon favorite.", "Children", "NR"),
        ("1007", "For Your Eyes Only", "James Bond - 007.",
         "Action/Adventure", "PG"),
        ("1001", "Big Easy, The", "A suspense set in New Orleans.",
         "Action/Adventure", "R"),
        ("1013", "Gone With The Wind", "A civil war epic.", "Drama", "G"),
        ("1015", "Benji", "A dog saves the day.", "Children", "G"),
        ("1021", "Bugs Bunny's Wacky Adventures",
         "Bone-chilling fun with Bugs.", "Children", "G"),
        ("1022", "Moonstruck", "A romantic comedy.", "Comedy", "PG"),
    ]
    for tape_id, title, description, subject, rating in rows:
        database.append({"TAPE_ID": tape_id, "TAPE_TITLE": title,
                         "TAPE_DESC": description, "SUBJECT": subject,
                         "RATING": rating})
    return tmp_path / "AVMOVIES.DBF", database


def make_patrons(tmp_path):
    """Database AVPATRON ridotto per search/sort e range."""
    from adbx.data.fields import Field
    from adbx.data.workspace import Workspace

    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVPATRON", [
        Field("NAME", "C", 20), Field("CITY", "C", 15),
        Field("STATE", "C", 2), Field("ACTIVE", "L", 1),
    ])
    rows = [
        ("Ada", "Placid", "NY", "1"),
        ("Bob", "Placid", "CA", "0"),
        ("Cara", "Snowville", "NY", "1"),
        ("Dan", "Placid", "NY", "1"),
        ("Eve", "Lake Placid", "NY", "1"),
    ]
    for name, city, state, active in rows:
        database.append({"NAME": name, "CITY": city, "STATE": state,
                         "ACTIVE": active})
    return tmp_path / "AVPATRON.DBF", database
