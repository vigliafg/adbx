"""O5 — set editor e consultazione dei set dall'interfaccia."""

from adbx.data import indexing
from adbx.data.fields import Field
from adbx.data.sets import Link, SetDefinition
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def type_text(target, text):
    for char in text:
        target.handle(Key("SPACE" if char == " " else char,
                          shift=char.isupper()))


def make_set(tmp_path):
    workspace = Workspace(tmp_path)
    header = workspace.create_database("AVHEADER", [
        Field("INV_NO", "C", 6), Field("CUST_ID", "C", 6),
        Field("INV_DATE", "D", 8)])
    patrons = workspace.create_database("AVPATRON", [
        Field("CUST_ID", "C", 6), Field("NAME", "C", 20),
        Field("CITY", "C", 15)])
    items = workspace.create_database("AVITEMS", [
        Field("INV_NO", "C", 6), Field("TAPE_ID", "C", 6),
        Field("QUANTITY", "N", 3, 0)])
    movies = workspace.create_database("AVMOVIES", [
        Field("TAPE_ID", "C", 6), Field("TITLE", "C", 30)])
    indexing.save_index(patrons, indexing.IndexDefinition(
        "AVPATID", "CUST_ID"))
    indexing.save_index(items, indexing.IndexDefinition(
        "AVINVNO", "INV_NO"))
    indexing.save_index(movies, indexing.IndexDefinition(
        "AVMOVID", "TAPE_ID"))
    patrons.append({"CUST_ID": "1001", "NAME": "Ada", "CITY": "Rome"})
    header.append({"INV_NO": "A015", "CUST_ID": "1001",
                   "INV_DATE": "19930505"})
    items.append({"INV_NO": "A015", "TAPE_ID": "1018", "QUANTITY": "1"})
    items.append({"INV_NO": "A015", "TAPE_ID": "1025", "QUANTITY": "2"})
    movies.append({"TAPE_ID": "1018", "TITLE": "Dumbo"})
    definition = SetDefinition(workspace, "AVIDEO", "Alpha Video", "AVHEADER")
    definition.links = [
        Link("AVHEADER", "AVPATRON", "AVPATID", "CUST_ID", "First"),
        Link("AVHEADER", "AVITEMS", "AVINVNO", "INV_NO", "All",
             referential=True, cascading_updates=True,
             cascading_deletes=True),
        Link("AVITEMS", "AVMOVIES", "AVMOVID", "TAPE_ID", "First",
             edit_child="No", add_child="No"),
    ]
    definition.save()
    return workspace, definition, header, patrons, items, movies


def open_set(controller, name="AVIDEO"):
    controller.handle(Key("C"))
    assert controller.overlay.kind == "submenu"
    controller.handle(Key("DOWN"))  # Open a set
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "choose"
    controller.handle(Key("ENTER"))
    assert controller.active_set is not None
    assert controller.active_set.name == name


def test_create_set_design_from_menu(tmp_path):
    workspace = Workspace(tmp_path)
    header = workspace.create_database("AVHEADER", [
        Field("INV_NO", "C", 6), Field("CUST_ID", "C", 6)])
    patrons = workspace.create_database("AVPATRON", [
        Field("CUST_ID", "C", 6), Field("NAME", "C", 20)])
    indexing.save_index(patrons, indexing.IndexDefinition(
        "AVPATID", "CUST_ID"))
    controller = ShellController(tmp_path, open_path=header.source)

    controller.handle(Key("D"))
    for _ in range(3):  # Set commands
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.target == "sets"
    controller.handle(Key("ENTER"))  # Create a set design
    assert controller.base == "setdesigner"
    session = controller.set_designer
    assert session.stage == "name"

    type_text(session, "AVIDEO")
    session.handle(Key("ENTER"))
    type_text(session, "Alpha Video")
    session.handle(Key("ENTER"))
    assert session.picker is not None
    session.handle(Key("ENTER"))  # AVHEADER
    assert session.stage == "settings"
    assert session.primary == "AVHEADER"

    session.handle(Key("F6"))
    session.handle(Key("ENTER"))
    session.handle(Key("F2"))
    while session.picker.value() != "AVPATRON":
        session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    session.handle(Key("F2"))
    session.handle(Key("ENTER"))
    session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    type_text(session, "CUST_ID")
    session.handle(Key("ENTER"))
    assert session._current_link().common == "CUST_ID"
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    saved = workspace.get_set("AVIDEO")
    assert saved is not None
    assert saved.description == "Alpha Video"
    assert [(link.parent, link.child) for link in saved.links] == [
        ("AVHEADER", "AVPATRON")]
    assert controller.active_set is not None
    assert controller.state.set_name == "AVIDEO"
    assert "Current set" in "\n".join(controller.view().buffer.to_lines())


def test_set_view_child_region_and_zoom(tmp_path):
    workspace, _definition, header, _patrons, _items, _movies = \
        make_set(tmp_path)
    controller = ShellController(tmp_path, open_path=header.source)
    open_set(controller)

    controller.handle(Key("V"))
    controller.handle(Key("ENTER"))  # View records
    assert controller.base == "setrecords"
    session = controller.set_records
    assert session.mode == "view"
    text = "\n".join(controller.view().buffer.to_lines())
    assert "Ada" in text
    assert "AVITEMS" in text
    assert "1018" in text

    controller.handle(Key("F6"))
    assert session.focus == "child"
    controller.handle(Key("DOWN"))
    assert session.child_index == 1
    controller.handle(Key("Z", alt=True))
    assert session.zoom is not None
    assert session.zoom.database.name == "AVITEMS"
    controller.handle(Key("ESC"))
    assert session.zoom is None
    controller.handle(Key("F10"))
    assert controller.base == "menu"


def test_set_enter_change_and_cascade(tmp_path):
    workspace, _definition, header, _patrons, items, _movies = \
        make_set(tmp_path)
    controller = ShellController(tmp_path, open_path=header.source)
    open_set(controller)
    controller.handle(Key("V"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Enter records
    session = controller.set_records
    assert session.mode == "enter"
    session.draft[("AVHEADER", "INV_NO")] = "A016"
    session.draft[("AVHEADER", "CUST_ID")] = "1001"
    session.draft[("AVPATRON", "CUST_ID")] = "1001"
    session.draft[("AVPATRON", "NAME")] = "Ada"
    session.field_index = 0
    session.edit_text = "A016"
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert header.count() == 2
    assert header.read(2)["INV_NO"] == "A016"

    # Change del genitore: il nuovo INV_NO arriva ai figli A015.
    controller.handle(Key("V"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Change records
    session = controller.set_records
    assert session.mode == "change"
    session.draft[("AVHEADER", "INV_NO")] = "A020"
    session.field_index = 0
    session.edit_text = "A020"
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert {items.read(seq)["INV_NO"] for seq in items.sequences()} == {
        "A020"}

    # Delete del genitore: cascata sui figli.
    controller.handle(Key("V"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("D", alt=True))
    assert header.is_deleted(1)
    assert all(items.is_deleted(seq) for seq in items.sequences())


def test_modify_and_erase_set(tmp_path):
    workspace, _definition, header, _patrons, _items, _movies = \
        make_set(tmp_path)
    controller = ShellController(tmp_path, open_path=header.source)
    controller.handle(Key("D"))
    for _ in range(3):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("DOWN"))  # Modify a set design
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "choose"
    controller.handle(Key("ENTER"))
    assert controller.base == "setdesigner"
    assert controller.set_designer.definition.name == "AVIDEO"
    controller.handle(Key("ESC"))
    assert controller.base == "menu"

    controller.handle(Key("D"))
    for _ in range(3):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))  # Erase a set design
    controller.handle(Key("ENTER"))  # apre la scelta del set
    controller.handle(Key("ENTER"))  # sceglie AVIDEO
    assert controller.overlay.kind == "confirm"
    controller.handle(Key("ENTER"))
    assert workspace.get_set("AVIDEO") is None


def test_switch_and_close_set(tmp_path):
    workspace, _definition, header, _patrons, _items, _movies = \
        make_set(tmp_path)
    controller = ShellController(tmp_path, open_path=header.source)
    open_set(controller)
    assert controller.state.set_name == "AVIDEO"

    controller.handle(Key("C"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))  # Switch databases
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "choose"
    labels = [label for label, _value in controller.overlay.items]
    assert "AVIDEO (set)" in labels
    controller.handle(Key("ESC"))

    controller.handle(Key("C"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))  # Close
    controller.handle(Key("ENTER"))
    assert controller.active_set is None
    assert controller.state.set_name == ""
    assert controller.database is None
