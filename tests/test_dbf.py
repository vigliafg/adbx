from datetime import date

import pytest
from support import write_dbf

from adbx.data.dbf import DbfError, read_header, record_count


def test_header_roundtrip(tmp_path):
    path = write_dbf(tmp_path / "TEST.DBF", records=7,
                     fields=(("NAME", "C", 10, 0), ("AMOUNT", "N", 8, 2)),
                     updated=(1993, 6, 1))
    header = read_header(path)
    assert header.records == 7
    assert header.updated == date(1993, 6, 1)
    assert header.field_count == 2
    assert [field.name for field in header.fields] == ["NAME", "AMOUNT"]
    assert header.fields[1].type == "N"
    assert header.fields[1].length == 8
    assert header.fields[1].decimals == 2
    assert header.record_length == 1 + 10 + 8


def test_record_count_helper(tmp_path):
    path = write_dbf(tmp_path / "TEST.DBF", records=44)
    assert record_count(path) == 44


def test_invalid_file_raises(tmp_path):
    path = tmp_path / "BAD.DBF"
    path.write_bytes(b"not a database")
    with pytest.raises(DbfError):
        read_header(path)


def test_missing_file_raises(tmp_path):
    with pytest.raises(DbfError):
        read_header(tmp_path / "MISSING.DBF")
