"""Accettazione O2: lezioni 2, 4, 5 e 6 (dati e immissione)."""

from pathlib import Path

from support import open_directory

from adbx.data.fields import Field
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def _type(controller, text: str) -> None:
    for char in text:
        controller.handle(Key("SPACE" if char == " " else char,
                             shift=char.isupper()))


def _create_database(path: Path, fields: list[Field]) -> Path:
    workspace = Workspace(path)
    database = workspace.create_database("DEMO", fields)
    return database.source


def _open(path: Path) -> ShellController:
    return ShellController(path.parent, open_path=path)


def _mode(controller: ShellController, down: int) -> None:
    controller.handle(Key("V"))
    for _ in range(down):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))


def test_lesson_2_create_database_from_directory(tmp_path):
    controller = open_directory(ShellController(tmp_path))

    controller.handle(Key("F5"))
    assert controller.overlay is not None and controller.overlay.kind == "prompt"
    _type(controller, "DEMO")
    controller.handle(Key("ENTER"))
    assert controller.base == "designer"
    assert controller.designer.name == "DEMO"

    _type(controller, "NAME")
    controller.handle(Key("TAB"))
    controller.handle(Key("C"))
    controller.handle(Key("TAB"))
    _type(controller, "20")

    controller.handle(Key("F6"))
    _type(controller, "QTY")
    controller.handle(Key("TAB"))
    controller.handle(Key("N"))
    controller.handle(Key("TAB"))
    _type(controller, "5")

    controller.handle(Key("F6"))
    _type(controller, "NOTES")
    controller.handle(Key("TAB"))
    controller.handle(Key("M"))

    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert controller.database is not None
    assert [field.name for field in controller.database.fields] == [
        "NAME", "QTY", "NOTES"]
    assert (tmp_path / "DEMO.DBF").exists()
    assert controller.database.name == "DEMO"


def test_lesson_4_enter_and_view_records(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20),
                                      Field("QTY", "N", 5, 0)])
    controller = _open(path)

    _mode(controller, 1)  # Enter records
    assert controller.base == "records"
    assert controller.records.mode == "enter"
    _type(controller, "Ada")
    controller.handle(Key("TAB"))
    _type(controller, "3")
    controller.handle(Key("F10"))

    assert controller.base == "menu"
    assert controller.database.count() == 1
    assert controller.database.read(1) == {"NAME": "Ada", "QTY": "3"}

    _mode(controller, 0)  # View records
    text = "\n".join(controller.view().buffer.to_lines())
    assert "View Records" in text.replace("  ", " ") or "V I E W" in text
    assert "Ada" in text
    assert "Record 1 of 1" in text


def test_lesson_4_enter_mode_keeps_accepting_records(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20)])
    controller = _open(path)
    _mode(controller, 1)
    for name in ("Ada", "Bob"):
        _type(controller, name)
        controller.handle(Key("ENTER"))
    assert controller.database.count() == 2
    assert controller.records.mode == "enter"
    assert controller.records.seq is None
    controller.handle(Key("ESC"))
    assert controller.base == "menu"


def test_ctrl_enter_saves_and_opens_next_record(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20),
                                      Field("CITY", "C", 20)])
    controller = _open(path)
    _mode(controller, 1)  # Enter records
    _type(controller, "Ada")
    controller.handle(Key("ENTER", ctrl=True))

    assert controller.records.mode == "enter"
    assert controller.records.seq is None
    assert controller.records.field_index == 0
    assert controller.database.count() == 1
    assert controller.database.read(1)["NAME"] == "Ada"

    _type(controller, "Bob")
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert controller.database.count() == 2


def test_enter_key_is_advertised_on_the_last_field(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20),
                                      Field("CITY", "C", 20)])
    controller = _open(path)
    _mode(controller, 1)  # Enter records
    assert ("ENTER", "Next record") not in controller.records.menu_entries
    controller.handle(Key("TAB"))
    assert ("ENTER", "Next record") in controller.records.menu_entries


def test_view_enter_returns_to_view_and_browses_records(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20)])
    controller = _open(path)
    _mode(controller, 1)  # Enter records
    for name in ("Ada", "Bob"):
        _type(controller, name)
        controller.handle(Key("ENTER"))
    controller.handle(Key("ESC"))
    assert controller.base == "menu"
    assert controller.database.count() == 2

    _mode(controller, 0)  # View records
    assert controller.records.mode == "view"
    assert controller.records.current_seq == 1

    # E da View: si entra in Enter; F10 salva e torna a View sul record nuovo.
    controller.handle(Key("E"))
    assert controller.records.mode == "enter"
    _type(controller, "Cara")
    controller.handle(Key("F10"))
    assert controller.base == "records"
    assert controller.records.mode == "view"
    assert controller.records.current_seq == 3
    assert "Cara" in "\n".join(controller.view().buffer.to_lines())

    # Le frecce scorrono i record già inseriti.
    controller.handle(Key("UP"))
    assert controller.records.current_seq == 2
    controller.handle(Key("UP"))
    assert controller.records.current_seq == 1


def test_escape_in_enter_returns_to_view_without_saving(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20)])
    controller = _open(path)
    _mode(controller, 1)
    _type(controller, "Ada")
    controller.handle(Key("ENTER"))
    controller.handle(Key("ESC"))
    _mode(controller, 0)

    controller.handle(Key("E"))
    _type(controller, "Bob")
    controller.handle(Key("ESC"))
    assert controller.base == "records"
    assert controller.records.mode == "view"
    assert controller.database.count() == 1


def test_f10_on_blank_enter_record_returns_to_view(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20)])
    controller = _open(path)
    _mode(controller, 1)
    _type(controller, "Ada")
    controller.handle(Key("ENTER"))
    controller.handle(Key("ESC"))
    _mode(controller, 0)

    controller.handle(Key("E"))
    controller.handle(Key("F10"))
    assert controller.base == "records"
    assert controller.records.mode == "view"
    assert controller.database.count() == 1


def test_lesson_5_change_record(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20),
                                      Field("CITY", "C", 20)])
    controller = _open(path)
    _mode(controller, 1)
    _type(controller, "Ada")
    controller.handle(Key("TAB"))
    _type(controller, "Torino")
    controller.handle(Key("F10"))

    _mode(controller, 2)  # Change records
    assert controller.records.mode == "change"
    controller.handle(Key("BACKSPACE", ctrl=True))
    _type(controller, "Ada Lovelace")
    controller.handle(Key("F10"))
    assert controller.database.read(1)["NAME"] == "Ada Lovelace"


def test_lesson_6_delete_recall_and_pack(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20)])
    controller = _open(path)
    _mode(controller, 1)
    for name in ("one", "two", "three"):
        _type(controller, name)
        controller.handle(Key("ENTER"))
    controller.handle(Key("ESC"))

    _mode(controller, 0)  # View
    controller.handle(Key("D", alt=True))
    assert controller.database.count() == 2
    assert controller.database.count(include_deleted=True) == 3

    controller.handle(Key("F7"))
    controller.handle(Key("HOME"))
    assert controller.database.is_deleted(controller.records.current_seq)
    controller.handle(Key("U", alt=True))
    assert controller.database.count() == 3
    controller.handle(Key("F10"))

    _mode(controller, 0)  # View again
    controller.handle(Key("D", alt=True))  # delete again
    controller.handle(Key("F10"))
    controller.handle(Key("U"))  # Utilities
    for _step in range(3):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Pack database
    assert controller.overlay is not None
    assert "Packed 1 deleted record" in controller.overlay.text
    assert controller.database.count(include_deleted=True) == 2
    assert controller.database.sequences() == [1, 2]


def test_memo_editor_and_dbf_roundtrip(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20),
                                      Field("NOTES", "M", 10)])
    controller = _open(path)
    _mode(controller, 1)
    _type(controller, "Ada")
    controller.handle(Key("TAB"))
    controller.handle(Key("M", alt=True))
    assert controller.records.memo is not None
    _type(controller, "hello memo")
    controller.handle(Key("F10"))
    assert controller.records.memo is None
    controller.handle(Key("F10"))
    assert controller.database.read(1)["NOTES"] == "hello memo"

    reopened = _open(path)
    assert reopened.database.read(1)["NOTES"] == "hello memo"


def test_clipboard_copy_and_paste(tmp_path):
    path = _create_database(tmp_path, [Field("A", "C", 20), Field("B", "C", 20)])
    controller = _open(path)
    _mode(controller, 1)
    _type(controller, "value")
    controller.handle(Key("F5", alt=True))
    controller.handle(Key("TAB"))
    controller.handle(Key("F6", alt=True))
    controller.handle(Key("F10"))
    assert controller.database.read(1) == {"A": "value", "B": "value"}


def test_browse_table(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20),
                                      Field("QTY", "N", 5, 0)])
    controller = _open(path)
    _mode(controller, 1)
    _type(controller, "Ada")
    controller.handle(Key("TAB"))
    _type(controller, "3")
    controller.handle(Key("ENTER"))
    _type(controller, "Bob")
    controller.handle(Key("TAB"))
    _type(controller, "4")
    controller.handle(Key("F10"))

    _mode(controller, 3)  # Browse records
    assert controller.records.mode == "browse"
    controller.handle(Key("DOWN"))
    text = "\n".join(controller.view().buffer.to_lines())
    assert "Browse Records" in text.replace("  ", " ") or "B R O W S E" in text
    assert "Ada" in text and "Bob" in text
    assert controller.records.current_seq == 2


def test_open_imports_legacy_dbf_records(tmp_path):
    from support import write_dbf

    path = write_dbf(
        tmp_path / "LEGACY.DBF",
        rows=[("1006", "Dumbo", "Y"), ("1007", "Alien", "N")],
        fields=(("TAPE_ID", "C", 4, 0), ("TITLE", "C", 20, 0),
                ("AVAILABLE", "L", 1, 0)))
    controller = _open(path)
    assert controller.database.count() == 2
    assert controller.database.read(2) == {
        "TAPE_ID": "1007", "TITLE": "Alien", "AVAILABLE": "0"}
    _mode(controller, 0)
    assert "Dumbo" in "\n".join(controller.view().buffer.to_lines())


def test_password_prompt_preserves_case(tmp_path):
    path = _create_database(tmp_path, [Field("NAME", "C", 20)])
    controller = _open(path)
    controller.handle(Key("D"))
    for _ in range(5):  # Password
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "prompt"
    _type(controller, "Secret")
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "message"

    reopened = _open(path)
    assert reopened.database.locked
    assert reopened.overlay.kind == "prompt"
    _type(reopened, "secret")
    reopened.handle(Key("ENTER"))
    assert reopened.database.locked
    assert reopened.overlay.kind == "message"

    again = _open(path)
    _type(again, "Secret")
    again.handle(Key("ENTER"))
    assert not again.database.locked
    assert again.base == "menu"


def test_designer_converts_type_and_renames(tmp_path):
    path = _create_database(tmp_path, [Field("A", "C", 10)])
    controller = _open(path)
    _mode(controller, 1)
    _type(controller, "12")
    controller.handle(Key("F10"))

    controller.handle(Key("D"))
    controller.handle(Key("DOWN"))  # Modify database
    controller.handle(Key("ENTER"))
    assert controller.base == "designer"
    controller.handle(Key("TAB"))  # Type column
    controller.handle(Key("N"))
    controller.handle(Key("TAB"))  # Length
    _type(controller, "5")
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert controller.database.fields == (Field("A", "N", 5, 0),)
    assert controller.database.read(1)["A"] == "12"
