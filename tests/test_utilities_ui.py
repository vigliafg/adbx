"""O9 — schermate delle utility, import/export e global update."""

from pathlib import Path

from adbx.data import indexing
from adbx.data.fields import Field
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def type_text(target, text):
    for char in text:
        target.handle(Key("SPACE" if char == " " else char,
                          shift=char.isupper()))


def clear_text(target, length):
    for _step in range(length):
        target.handle(Key("BACKSPACE"))


def pick(session, value):
    for _step in range(40):
        if session.picker is None:
            return False
        if session.picker.value() == value:
            return True
        session.picker.move(1)
    return False


def make_sales(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVSALES", [
        Field("CUST_ID", "C", 4), Field("NAME", "C", 12),
        Field("AMT", "N", 7, 2), Field("INV", "C", 4),
    ])
    for row in (("1001", "Richardson", "3.24", "A001"),
                ("1001", "Richardson", "4.00", "A002"),
                ("1021", "Barber", "5.00", "A111")):
        database.append(dict(zip(
            [field.name for field in database.fields], row)))
    indexing.save_index(
        database, indexing.IndexDefinition("CUST", "CUST_ID"))
    other = workspace.create_database("EXT", [
        Field("CUST_ID", "C", 4), Field("NAME", "C", 12),
        Field("AMT", "N", 7, 2), Field("INV", "C", 4)])
    other.append({"CUST_ID": "1001", "NAME": "External", "AMT": "9.99",
                  "INV": "B001"})
    other.append({"CUST_ID": "9999", "NAME": "New", "AMT": "7.77",
                  "INV": "B002"})
    indexing.save_index(other, indexing.IndexDefinition("CUSTE", "CUST_ID"))
    workspace.save_database(other)
    database.set_primary_index("CUST")
    workspace.save_database(database)
    return workspace, database


def open_utility(controller, index):
    controller.handle(Key("U"))
    assert controller.overlay.target == "utilities"
    for _step in range(index):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))


def test_copy_summarize_and_crosstab_screens(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)

    open_utility(controller, 0)
    session = controller.utility_session
    assert session.stage == "fields"
    controller.handle(Key("F10"))
    assert session.stage == "options"
    type_text(session, "COPY1")
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert workspace.get("COPY1") is not None
    assert "Copy: 3 record(s)" in controller.overlay.text

    controller.handle(Key("ENTER"))
    open_utility(controller, 2)
    session = controller.utility_session
    assert session.stage == "fields"
    assert session.summary[2][1] == "Total"
    controller.handle(Key("F10"))
    type_text(session, "SUM1")
    controller.handle(Key("F10"))
    assert workspace.get("SUM1") is not None
    assert "Summarize: 2 record(s)" in controller.overlay.text

    controller.handle(Key("ENTER"))
    open_utility(controller, 5)
    session = controller.utility_session
    assert session.command == "crosstab"
    type_text(session, "XT1")
    controller.handle(Key("F10"))
    table = workspace.get("XT1")
    assert table is not None
    assert "RICHARDSON" in [field.name for field in table.fields]


def test_append_screen_and_mapping(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_utility(controller, 1)
    session = controller.utility_session
    assert pick(session, "EXT")
    controller.handle(Key("ENTER"))
    assert session.stage == "options"
    assert session.source_name == "EXT"
    controller.handle(Key("F10"))
    assert session.stage == "mapping"
    assert [mapping.target for mapping in session.mappings] == [
        "CUST_ID", "NAME", "AMT", "INV"]
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert database.count() == 5


def test_relational_join_screen(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    controller.handle(Key("U"))
    for _step in range(6):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.target == "relational"
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    session = controller.relational_session
    assert session.command == "join"
    assert pick(session, "EXT")
    controller.handle(Key("ENTER"))
    assert pick(session, "CUSTE")
    controller.handle(Key("ENTER"))
    assert session.stage == "common"
    assert session.index_name == "CUSTE"
    controller.handle(Key("F10"))
    assert session.stage == "primary-fields"
    controller.handle(Key("F10"))
    assert session.stage == "secondary-fields"
    controller.handle(Key("F10"))
    assert session.stage == "options"
    type_text(session, "JOIN1")
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    joined = workspace.get("JOIN1")
    assert joined is not None
    assert joined.count() == 3


def test_post_and_global_update_screens(tmp_path):
    workspace, database = make_sales(tmp_path)
    transaction = workspace.create_database("TRAN", [
        Field("CUST_ID", "C", 4), Field("AMT", "N", 7, 2),
        Field("POSTED", "L", 1)])
    transaction.append({"CUST_ID": "1001", "AMT": "1.00", "POSTED": "0"})
    workspace.save_database(transaction)
    controller = ShellController(tmp_path, open_path=database.source)
    controller.handle(Key("U"))
    for _step in range(6):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))  # Post database
    session = controller.relational_session
    assert session.command == "post"
    assert pick(session, "TRAN")
    controller.handle(Key("ENTER"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    type_text(session, "POSTED")
    controller.handle(Key("F10"))
    assert session.stage == "post-fields"
    assert any(included for _master, _source, _op, included
               in session.post_rows)
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert [row["POSTED"] for row in
            (transaction.read(seq) for seq in transaction.sequences())] == ["1"]

    controller.handle(Key("ENTER"))
    controller.handle(Key("G"))  # main menu -> Global
    assert controller.overlay.target == "global"
    controller.handle(Key("ENTER"))  # Update a field
    session = controller.global_session
    assert session.stage == "expressions"
    type_text(session, "AMT * 2")
    controller.handle(Key("F10"))
    assert session.stage == "confirm"
    controller.handle(Key("ENTER"))
    assert controller.base == "menu"


def test_global_case_and_delete_range(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    controller.handle(Key("G"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    session = controller.global_session
    assert session.command == "case"
    session.case_mode = "Upper case"
    controller.handle(Key("F10"))
    controller.handle(Key("ENTER"))
    assert [row["NAME"] for row in
            (database.read(seq) for seq in database.sequences())] == [
        "RICHARDSON", "RICHARDSON", "BARBER"]

    controller.handle(Key("ENTER"))
    controller.handle(Key("G"))
    for _step in range(2):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    session = controller.global_session
    assert session.command == "delete-range"
    controller.handle(Key("ENTER"))
    assert database.count() == 0
    assert database.count(include_deleted=True) == 3


def test_zap_database_confirmation(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_utility(controller, 4)
    assert controller.overlay.kind == "confirm"
    controller.handle(Key("ENTER"))
    assert database.count(include_deleted=True) == 0
    assert "Zapped AVSALES" in controller.overlay.text


def test_import_and_export_screens(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    source = Path(tmp_path) / "in.CSV"
    source.write_text("CUST_ID,AMT\n2000,1.50\n", encoding="ascii")

    # Import data (ottava voce).
    open_utility(controller, 7)
    session = controller.transfer_session
    assert session.mode == "import"
    assert pick(session, "csv")
    controller.handle(Key("ENTER"))
    type_text(session, "in.CSV")
    controller.handle(Key("F10"))
    assert session.stage == "adjust"
    controller.handle(Key("F10"))
    assert session.stage == "target"
    clear_text(session, len(session.target_name))
    type_text(session, "IMPORTED")
    controller.handle(Key("F10"))
    imported = workspace.get("IMPORTED")
    assert imported is not None
    assert imported.read(1)["CUST_ID"] == "2000"

    controller.handle(Key("ENTER"))
    open_utility(controller, 8)
    session = controller.transfer_session
    assert session.mode == "export"
    assert pick(session, "csv")
    controller.handle(Key("ENTER"))
    type_text(session, "out")
    controller.handle(Key("F10"))
    assert session.stage == "fields"
    controller.handle(Key("F10"))
    assert session.stage == "options"
    controller.handle(Key("F10"))
    target = Path(tmp_path) / "out.CSV"
    assert target.exists()
    assert "CUST_ID" in target.read_text()
