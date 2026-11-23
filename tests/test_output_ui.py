"""O8 — designer etichette, editor lettere, anteprima e menu Print."""

from adbx.data.fields import Field
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def type_text(target, text):
    for char in text:
        target.handle(Key("SPACE" if char == " " else char,
                          shift=char.isupper()))


def make_patrons(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVPATRON", [
        Field("SALUTATION", "C", 4), Field("FIRSTNAME", "C", 10),
        Field("LASTNAME", "C", 12), Field("ADDRESS1", "C", 20),
        Field("ADDRESS2", "C", 20), Field("CITY", "C", 15),
        Field("STATE", "C", 2), Field("ZIP", "C", 5),
    ])
    database.append({
        "SALUTATION": "Ms.", "FIRSTNAME": "Grace", "LASTNAME": "Jones",
        "ADDRESS1": "11 Willow Street", "ADDRESS2": "",
        "CITY": "Rushton", "STATE": "NY", "ZIP": "11211",
    })
    return workspace, database


def choose_picker(controller, session, value):
    for _step in range(60):
        picker = session.picker
        assert picker is not None
        if picker.value() == value:
            controller.handle(Key("ENTER"))
            return True
        controller.handle(Key("DOWN"))
    return False


def open_labels(controller):
    controller.handle(Key("L"))
    assert controller.overlay.target == "layouts"
    for _ in range(3):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.target == "labels"


def open_letters(controller):
    controller.handle(Key("L"))
    assert controller.overlay.target == "layouts"
    for _ in range(4):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.target == "letters"


def test_create_label_from_menu_and_preview(tmp_path):
    workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_labels(controller)
    controller.handle(Key("ENTER"))
    session = controller.label_designer
    session.handle(Key("A"))
    session.handle(Key("ENTER"))
    assert session.stage == "params"
    # description
    session.handle(Key("ENTER"))
    type_text(controller, "Mail Labels with Message Line")
    session.handle(Key("ENTER"))
    # width 40
    session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    session.edit_text = "40"
    session.handle(Key("ENTER"))
    # height 8
    session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    session.edit_text = "8"
    session.handle(Key("ENTER"))
    # two across
    session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    session.edit_text = "2"
    session.handle(Key("ENTER"))
    session.handle(Key("F10"))
    assert session.stage == "layout"
    assert session.label.width == 40 and session.label.height == 8
    assert session.label.across == 2

    session.row = 2
    session.col = 1
    controller.handle(Key("F2"))
    assert choose_picker(controller, session, "AVPATRON")
    assert choose_picker(controller, session, "AVPATRON:SALUTATION")
    session.col = 6
    controller.handle(Key("F2"))
    assert choose_picker(controller, session, "AVPATRON")
    assert choose_picker(controller, session, "AVPATRON:FIRSTNAME")
    session.row = 2
    session.col = 17
    controller.handle(Key("F2"))
    assert choose_picker(controller, session, "AVPATRON")
    assert choose_picker(controller, session, "AVPATRON:LASTNAME")
    assert len(session.label.fields) == 3

    # formatting: la giustificazione predefinita e' Suppress
    controller.handle(Key("O", alt=True))
    assert session.stage == "formatting"
    session.format_row = 0
    session.format_col = 2
    session.handle(Key("SPACE"))
    assert session.label.fields[0].justification == "Left"
    session.handle(Key("SPACE"))
    assert session.label.fields[0].justification == "Right"
    session.handle(Key("F10"))
    assert session.stage == "layout"

    controller.handle(Key("F10"))
    assert session.picker is not None
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Save and preview
    assert controller.base == "reportpreview"
    assert "Ms. Grace Jones" in controller.report_preview.output.text
    controller.handle(Key("F10"))
    assert controller.report_preview.pdf_path.exists()
    controller.handle(Key("ESC"))
    assert controller.base == "menu"


def test_label_borrow_erase_and_print_menu(tmp_path):
    workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_labels(controller)
    controller.handle(Key("ENTER"))
    session = controller.label_designer
    session.handle(Key("A"))
    session.handle(Key("ENTER"))
    session.handle(Key("F10"))
    controller.handle(Key("F10"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))
    assert workspace.get_label("AVPATRON", "A") is not None

    open_labels(controller)
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.action == "borrow-label"
    controller.handle(Key("ENTER"))
    assert controller.label_designer.stage == "borrow_letter"
    type_text(controller, "B")
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))
    assert workspace.get_label("AVPATRON", "B") is not None

    controller.handle(Key("P"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.action == "print-label"
    controller.handle(Key("ENTER"))
    assert controller.base == "reportpreview"
    controller.handle(Key("ESC"))

    open_labels(controller)
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    while controller.overlay.items[controller.overlay.selected][1] != "B":
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))
    assert workspace.get_label("AVPATRON", "B") is None


def test_create_letter_from_menu_and_preview(tmp_path):
    workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_letters(controller)
    controller.handle(Key("ENTER"))
    editor = controller.letter_editor
    type_text(controller, "POPORNOT")
    controller.handle(Key("ENTER"))
    assert editor.stage == "edit"

    type_text(controller, "Dear ")
    controller.handle(Key("F2"))
    assert choose_picker(controller, editor, "AVPATRON")
    assert choose_picker(controller, editor, "AVPATRON:FIRSTNAME")
    assert choose_picker(controller, editor, "S")
    assert "[FIRSTNAME.S]" in editor.letter.body[0]

    controller.handle(Key("ENTER"))
    type_text(controller, "Welcome to Alpha Video.")
    controller.handle(Key("F3"))
    assert editor.picker_kind == "commands"
    controller.handle(Key("ENTER"))  # line width
    type_text(controller, "30")
    controller.handle(Key("ENTER"))
    assert "[.WIDTH 30]" in editor.letter.body

    controller.handle(Key("F7"))
    assert editor.picker_kind == "conditional"
    controller.handle(Key("ENTER"))  # IF
    type_text(controller, "ACTIVE = .T.")
    controller.handle(Key("ENTER"))
    assert any(line.startswith("[.IF") for line in editor.letter.body)
    controller.handle(Key("F7"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # ELSE
    controller.handle(Key("F7"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # ENDIF
    assert "[.ELSE]" in editor.letter.body
    assert "[.ENDIF]" in editor.letter.body

    controller.handle(Key("F10"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Save and preview
    assert controller.base == "reportpreview"
    assert "Dear Grace" in controller.report_preview.output.text
    controller.handle(Key("P"))
    assert controller.report_preview.pdf_path.exists()
    controller.handle(Key("ESC"))
    assert controller.base == "menu"
    assert workspace.get_letter("AVPATRON", "POPORNOT") is not None


def test_letter_print_menu_and_erase(tmp_path):
    workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_letters(controller)
    controller.handle(Key("ENTER"))
    type_text(controller, "TEST")
    controller.handle(Key("ENTER"))
    type_text(controller, "Hello")
    controller.handle(Key("F10"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))
    assert workspace.get_letter("AVPATRON", "TEST") is not None

    controller.handle(Key("P"))
    for _ in range(4):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.action == "print-letter"
    controller.handle(Key("ENTER"))
    assert controller.base == "reportpreview"
    assert "Hello" in controller.report_preview.output.text
    controller.handle(Key("ESC"))

    open_letters(controller)
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.action == "erase-letter"
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "confirm"
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))
    assert workspace.get_letter("AVPATRON", "TEST") is None
