"""O6 — form designer e form personalizzati in View/Enter/Change."""

from adbx.data import indexing
from adbx.data.fields import Field
from adbx.data.forms import FormDefinition, FormField, FormRegion
from adbx.data.sets import Link, SetDefinition
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def type_text(target, text):
    for char in text:
        target.handle(Key("SPACE" if char == " " else char,
                          shift=char.isupper()))


def make_movies(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVMOVIES", [
        Field("TAPE_ID", "C", 4), Field("TAPE_TITLE", "C", 30),
        Field("TAPE_DESC", "M", 10), Field("RUNTIME", "N", 3, 0),
    ])
    database.append({"TAPE_ID": "1006", "TAPE_TITLE": "Dumbo",
                     "TAPE_DESC": "A Disney cartoon favorite.",
                     "RUNTIME": "64"})
    return workspace, database


def open_layouts_forms(controller):
    controller.handle(Key("L"))
    assert controller.overlay.target == "layouts"
    controller.handle(Key("ENTER"))
    assert controller.overlay.target == "forms"


def create_form_with_title(controller, letter="A", description="Movie form"):
    open_layouts_forms(controller)
    controller.handle(Key("ENTER"))  # Create/edit
    session = controller.form_designer
    type_text(session, letter)
    session.handle(Key("ENTER"))
    type_text(session, description)
    session.handle(Key("ENTER"))
    session.handle(Key("F10"))  # parameters -> layout
    session.handle(Key("F2"))
    picker = session.picker
    while picker.value() != "AVMOVIES:TAPE_TITLE":
        session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    return session


def test_create_form_from_menu_and_view_it(tmp_path):
    workspace, database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    create_form_with_title(controller)
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    form = workspace.get_form("AVMOVIES", "A")
    assert form is not None
    assert form.description == "Movie form"
    assert workspace.active_form("AVMOVIES").letter == "A"

    controller.handle(Key("ENTER"))
    controller.handle(Key("V"))
    controller.handle(Key("ENTER"))  # View records
    assert controller.records.form is not None
    assert controller.records.form.letter == "A"
    text = "\n".join(controller.view().buffer.to_lines())
    assert "Dumbo" in text

    # Il custom form contiene solo TAPE_TITLE: il cursore si muove su quello.
    controller.handle(Key("F10"))
    controller.handle(Key("V"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Enter records
    type_text(controller, "Roxanne")
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert controller.database.read(2)["TAPE_TITLE"] == "Roxanne"
    assert controller.database.read(2)["TAPE_ID"] == ""


def test_form_designer_labels_boxes_and_parameters(tmp_path):
    workspace, database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    session = create_form_with_title(controller)
    session.handle(Key("UP"))
    session.handle(Key("HOME"))
    type_text(session, "Movie: ")
    session.row = 6
    session.col = 2
    session.handle(Key("F8"))
    session.handle(Key("F7"))
    # Description, custom menu, restrict, printable, print width, margins.
    session.param_row = 1
    session.handle(Key("ENTER"))
    type_text(session, " &Print &Quit")
    session.handle(Key("ENTER"))
    session.param_row = 3
    session.handle(Key("ENTER"))  # Printable No
    session.handle(Key("F10"))
    controller.handle(Key("F10"))
    form = workspace.get_form("AVMOVIES", "A")
    assert not form.printable
    assert form.custom_menu == " &Print &Quit"
    assert any(label.text.startswith("Movie:") for label in form.labels)
    assert form.boxes


def test_formatting_options_length_and_window(tmp_path):
    workspace, database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    session = create_form_with_title(controller)
    session.handle(Key("F9"))
    assert session.stage == "formatting"
    session.format_row = 0
    session.format_col = 2
    session.handle(Key("ENTER"))
    session.edit_text = "10"
    session.handle(Key("ENTER"))
    session.format_col = 3
    session.handle(Key("ENTER"))
    session.edit_text = "5"
    session.handle(Key("ENTER"))
    session.handle(Key("F10"))
    controller.handle(Key("F10"))
    form = workspace.get_form("AVMOVIES", "A")
    assert form.fields[0].length == 10
    assert form.fields[0].window == 5


def make_set_form(tmp_path):
    workspace = Workspace(tmp_path)
    header = workspace.create_database("AVHEADER", [
        Field("INV_NO", "C", 6), Field("CUST_ID", "C", 6)])
    items = workspace.create_database("AVITEMS", [
        Field("INV_NO", "C", 6), Field("QTY", "N", 4, 0)])
    indexing.save_index(items, indexing.IndexDefinition("AVINVNO", "INV_NO"))
    header.append({"INV_NO": "A015", "CUST_ID": "1001"})
    items.append({"INV_NO": "A015", "QTY": "2"})
    items.append({"INV_NO": "A015", "QTY": "3"})
    definition = SetDefinition(workspace, "AVIDEO", "", "AVHEADER")
    definition.links = [Link("AVHEADER", "AVITEMS", "AVINVNO", "INV_NO",
                             "All")]
    definition.save()
    form = FormDefinition(workspace, "AVIDEO", "A", "Invoice form")
    form.fields = [
        FormField("AVHEADER", "INV_NO", 0, 1, 1, 6, 6, "Invoice", True),
        FormField("CALC", "TOTAL", 0, 1, 20, 10, 10, "Items total", True,
                  kind="summary", summary="Total", summary_field="QTY",
                  summary_database="AVITEMS"),
    ]
    form.regions = [FormRegion("AVITEMS", 0, 5, 1, 8, 50, "Line items")]
    form.printable = False
    form.save()
    return workspace, definition, header, items


def test_set_form_region_and_summary(tmp_path):
    workspace, definition, header, _items = make_set_form(tmp_path)
    controller = ShellController(tmp_path, open_path=header.source)
    controller._activate_set("AVIDEO")
    controller.handle(Key("V"))
    controller.handle(Key("ENTER"))
    session = controller.set_records
    assert session.form is not None
    text = "\n".join(controller.view().buffer.to_lines())
    assert "Invoice" in text
    assert "Line items" in text
    assert "5" in text
    assert "A015" in text
    controller.handle(Key("F6"))
    assert session.focus == "child"
    controller.handle(Key("DOWN"))
    controller.handle(Key("Z", alt=True))
    assert session.zoom is not None
    controller.handle(Key("ESC"))
    controller.handle(Key("F10"))
    assert controller.base == "menu"


def test_select_and_erase_form_from_menu(tmp_path):
    workspace, database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    create_form_with_title(controller)
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    controller.handle(Key("ENTER"))

    open_layouts_forms(controller)
    controller.handle(Key("DOWN"))  # Select active form
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "choose"
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "message"
    assert "active" in controller.overlay.text
    controller.handle(Key("ENTER"))

    open_layouts_forms(controller)
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))  # Erase a form
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))  # choose A
    assert controller.overlay.kind == "confirm"
    controller.handle(Key("ENTER"))
    assert workspace.get_form("AVMOVIES", "A") is None
