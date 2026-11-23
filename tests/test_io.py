"""O9 — import/export: ogni formato ha una prova di andata e ritorno."""

from pathlib import Path

import pytest

from adbx.data.fields import Field
from adbx.data.workspace import Workspace
from adbx.io import (
    ExportOptions,
    ImportOptions,
    export_from_database,
    formats,
    import_into_workspace,
    read_table,
    write_table,
)

FIELDS = [Field("FIRSTNAME", "C", 12), Field("AMOUNT", "N", 7, 2),
          Field("WHEN", "D", 8), Field("ACTIVE", "L", 1)]
ROWS = [
    {"FIRSTNAME": "Ann", "AMOUNT": "3.24", "WHEN": "20240102",
     "ACTIVE": "1"},
    {"FIRSTNAME": "Bob", "AMOUNT": "4.00", "WHEN": "20240103",
     "ACTIVE": "0"},
]


def make_database(tmp_path, name="EXPORT"):
    workspace = Workspace(tmp_path)
    database = workspace.create_database(name, FIELDS)
    for row in ROWS:
        database.append(row)
    workspace.save_database(database)
    return workspace, database


FORMAT_KEYS = ["dbase3", "dbase2", "delimited", "csv", "table", "dif",
               "sylk", "lotus", "wordperfect", "multimate"]


@pytest.mark.parametrize("key", FORMAT_KEYS)
def test_every_format_round_trip(tmp_path, key):
    workspace, database = make_database(tmp_path)
    path = tmp_path / f"out-{key}{formats.default_extension(key)}"
    export_options = ExportOptions(fieldnames=True, width=12, spacing=1)
    if key == "lotus":
        export_options = ExportOptions(fieldnames=True, width=12,
                                       spacing=1, date_format="YYYYMMDD")
    write_table(path, key, FIELDS,
                [database.read(seq) for seq in database.sequences()],
                export_options)
    import_options = ImportOptions(fieldnames=True, width=12, spacing=1,
                                   field_count=4)
    table = read_table(path, key, import_options)
    assert len(table.rows) == 2
    records = formats.coerce_table(table, FIELDS)
    assert records == ROWS, key


def test_infer_fields_types():
    from adbx.io.common import infer_fields

    fields = infer_fields([
        ["Ann", "Bob"], ["3.24", "4"], ["20240102", "20240103"],
        ["T", "F"]], ["NAME", "AMOUNT", "WHEN", "ACTIVE"])
    assert [field.type for field in fields] == ["C", "N", "D", "L"]
    assert fields[1].decimals == 2
    assert [field.name for field in fields] == [
        "NAME", "AMOUNT", "WHEN", "ACTIVE"]


def test_csv_import_and_export_from_database(tmp_path):
    workspace, database = make_database(tmp_path)
    target = export_from_database(database, tmp_path / "sales", "csv")
    assert target.path.suffix == ".CSV"
    assert "FIRSTNAME" in target.path.read_text()
    new_directory = tmp_path / "import"
    new_directory.mkdir()
    other = Workspace(new_directory)
    result = import_into_workspace(other, "IMPORTED", target.path, "csv",
                                   ImportOptions(fieldnames=True),
                                   fields=FIELDS)
    assert result.records == 2
    imported = other.get("IMPORTED")
    assert [imported.read(seq) for seq in imported.sequences()] == ROWS


def test_delimited_options_quote_separator_and_header(tmp_path):
    path = tmp_path / "pipes.ASC"
    write_table(path, "delimited", FIELDS, ROWS, ExportOptions(
        fieldnames=True, separator="|", quote_character=True,
        record_separator="\r\n", trailing_separator=False))
    text = path.read_bytes().decode("cp437")
    assert text.startswith("FIRSTNAME|AMOUNT|WHEN|ACTIVE\r\n")
    assert '"Ann"|3.24|01/02/2024|T' in text
    table = read_table(path, "delimited", ImportOptions(
        fieldnames=True, separator="|"))
    assert table.rows[0][0] == "Ann"


def test_table_ascii_manual_widths(tmp_path):
    path = tmp_path / "fixed.TXT"
    write_table(path, "table", FIELDS, ROWS, ExportOptions(
        fieldnames=True, width=10, spacing=2))
    text = path.read_text()
    assert text.splitlines()[0].startswith("FIRSTNAME")
    table = read_table(path, "table", ImportOptions(
        fieldnames=True, width=10, spacing=2, field_count=4))
    assert table.rows[0][0] == "Ann"
    records = formats.coerce_table(table, FIELDS)
    assert records == ROWS


def test_db2_field_limit(tmp_path):
    fields = [Field(f"F{index:02d}", "C", 2) for index in range(1, 34)]
    with pytest.raises(Exception):
        write_table(tmp_path / "too.DBF", "dbase2", fields, [])


def test_dif_and_sylk_text_headers(tmp_path):
    dif_path = tmp_path / "data.DIF"
    write_table(dif_path, "dif", FIELDS, ROWS, ExportOptions(fieldnames=True))
    assert dif_path.read_text().startswith("TABLE")
    sylk_path = tmp_path / "data.SLK"
    write_table(sylk_path, "sylk", FIELDS, ROWS, ExportOptions(fieldnames=True))
    assert "C;Y1;X1;K\"FIRSTNAME\"" in sylk_path.read_text()


def test_lotus_export_is_wk1(tmp_path):
    path = tmp_path / "data.WK1"
    write_table(path, "lotus", FIELDS, ROWS,
                ExportOptions(fieldnames=True, date_format="YYYYMMDD"))
    data = path.read_bytes()
    assert data[:4] == b"\x00\x00\x02\x00"
    assert b"\x06\x04" in data[:6]
    table = read_table(path, "lotus", ImportOptions(fieldnames=True))
    assert table.rows[1][1] == "4.00"


def test_wordperfect_names_section(tmp_path):
    path = tmp_path / "merge.MRG"
    write_table(path, "wordperfect", FIELDS, ROWS, ExportOptions(
        fieldnames=True))
    text = path.read_text()
    assert text.startswith("{FIELD NAMES}")
    assert "{END FIELD}" in text and "{END RECORD}" in text
    table = read_table(path, "wordperfect", ImportOptions(fieldnames=True))
    assert [field.name for field in table.fields] == [
        "FIRSTNAME", "AMOUNT", "WHEN", "ACTIVE"]


def test_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        read_table(Path(tmp_path) / "x.xyz", "unknown")
