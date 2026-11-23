"""Strato dati SQLite + specchio DBF (O2)."""

import pytest
from support import write_dbf

from adbx.data.dbf import read_header, read_rows, write_rows
from adbx.data.fields import Field
from adbx.data.workspace import Workspace, WorkspaceError


def test_create_append_update_mirror(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("DEMO", [
        Field("NAME", "C", 20), Field("QTY", "N", 5, 0), Field("NOTES", "M", 10),
    ])
    assert (tmp_path / "DEMO.DBF").exists()
    assert database.count() == 0

    seq = database.append({"NAME": "Ada", "QTY": "3", "NOTES": "first"})
    assert seq == 1
    assert database.read(seq) == {"NAME": "Ada", "QTY": "3", "NOTES": "first"}
    assert database.count() == 1

    database.update(seq, {"NAME": "Ada Lovelace", "QTY": "4", "NOTES": "second"})
    assert database.read(seq)["NAME"] == "Ada Lovelace"
    workspace.save_database(database)

    header = read_header(tmp_path / "DEMO.DBF")
    assert header.records == 1
    assert header.fields[0].name == "NAME"
    assert header.fields[2].type == "M"
    rows = read_rows(tmp_path / "DEMO.DBF", header)
    assert rows[0].values["NAME"] == "Ada Lovelace"
    assert rows[0].values["NOTES"] == "second"


def test_logical_delete_pack_and_renumber(tmp_path):
    database = Workspace(tmp_path).create_database(
        "DEMO", [Field("NAME", "C", 10)])
    for name in ("one", "two", "three"):
        database.append({"NAME": name})
    database.delete(2)
    assert database.count() == 2
    assert database.count(include_deleted=True) == 3
    assert database.sequences() == [1, 3]

    assert database.pack() == 2
    assert database.sequences() == [1, 2]
    assert database.read(2)["NAME"] == "three"
    assert database.count(include_deleted=True) == 2


def test_import_dbf_rows_and_memos(tmp_path):
    path = write_dbf(
        tmp_path / "LEGACY.DBF", rows=[("1006", "Dumbo", "64", "Y"),
                                       ("1007", "Alien", "117", "N")],
        fields=(("TAPE_ID", "C", 4, 0), ("TITLE", "C", 20, 0),
                ("RUNTIME", "N", 3, 0), ("AVAILABLE", "L", 1, 0)))
    database = Workspace(tmp_path).open_database(path)
    assert database.name == "LEGACY"
    assert database.count() == 2
    assert database.read(1) == {"TAPE_ID": "1006", "TITLE": "Dumbo",
                                "RUNTIME": "64", "AVAILABLE": "1"}
    assert database.read(2)["AVAILABLE"] == "0"

    memo_path = tmp_path / "MEMO.DBF"
    fields = [Field("TITLE", "C", 20), Field("BODY", "M", 10)]
    write_rows(memo_path, fields, [(False, {"TITLE": "One", "BODY": "hello memo"})])
    memo = Workspace(tmp_path).open_database(memo_path)
    assert memo.read(1)["BODY"] == "hello memo"


def test_alter_renames_drops_adds_and_converts(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database(
        "DEMO", [Field("A", "C", 10), Field("B", "C", 10)])
    database.append({"A": "12ABC", "B": "T"})
    database.append({"A": "99", "B": "F"})

    updated = workspace.alter_database("DEMO", [
        ("A", Field("AMOUNT", "N", 5, 0)),
        ("B", Field("ACTIVE", "L", 1)),
        (None, Field("NOTE", "C", 5)),
    ])
    assert [field.name for field in updated.fields] == ["AMOUNT", "ACTIVE", "NOTE"]
    assert updated.read(1) == {"AMOUNT": "12", "ACTIVE": "1", "NOTE": ""}
    assert updated.read(2) == {"AMOUNT": "99", "ACTIVE": "0", "NOTE": ""}
    assert read_header(tmp_path / "DEMO.DBF").fields[0].name == "AMOUNT"


def test_duplicate_names_and_missing_files(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create_database("DEMO", [Field("A", "C", 10)])
    with pytest.raises(WorkspaceError):
        workspace.create_database("DEMO", [Field("B", "C", 10)])
    with pytest.raises(WorkspaceError):
        workspace.open_database(tmp_path / "MISSING.DBF")


def test_password_roundtrip(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create_database("DEMO", [Field("A", "C", 10)])
    workspace.set_password("DEMO", "segreta")
    locked = workspace.get("DEMO")
    assert locked.locked
    assert not workspace.check_password(locked, "sbagliata")
    assert workspace.check_password(locked, "segreta")
    assert not locked.locked
    workspace.set_password("DEMO", None)
    assert not workspace.get("DEMO").locked


def test_drop_created_database_removes_files(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create_database("DEMO", [Field("A", "C", 10)])
    assert workspace.drop_database("DEMO")
    assert not (tmp_path / "DEMO.DBF").exists()
    assert workspace.get("DEMO") is None
