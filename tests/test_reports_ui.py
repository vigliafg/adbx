"""O7 — report designer, anteprima, PDF e menu Print."""

from adbx.data.fields import Field
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def type_text(target, text):
    for char in text:
        target.handle(Key("SPACE" if char == " " else char,
                          shift=char.isupper()))


def make_sales(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVSALES", [
        Field("CUST_ID", "C", 6), Field("LASTNAME", "C", 15),
        Field("INV_NUMBER", "C", 4), Field("INVTOTAL", "N", 8, 2),
    ])
    for row in (("1001", "Richardson", "A001", "3.24"),
                ("1001", "Richardson", "A002", "4.00"),
                ("1021", "Barber", "A111", "5.00")):
        database.append(dict(zip([field.name for field in database.fields],
                                 row)))
    return workspace, database


def open_reports(controller):
    controller.handle(Key("L"))
    assert controller.overlay.target == "layouts"
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.target == "reports"


def create_custom(controller, letter="A"):
    open_reports(controller)
    controller.handle(Key("ENTER"))
    session = controller.report_designer
    type_text(session, letter)
    session.handle(Key("ENTER"))
    session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    assert session.stage == "params1"
    return session


def choose_picker(controller, value):
    session = controller.report_designer
    for _step in range(80):
        picker = session.picker
        assert picker is not None
        if picker.value() == value:
            controller.handle(Key("ENTER"))
            return True
        controller.handle(Key("DOWN"))
    return False


def place_field(controller, database, field, display="Value"):
    controller.handle(Key("F2"))
    assert choose_picker(controller, database)
    assert choose_picker(controller, f"{database}:{field}")
    assert choose_picker(controller, display)


def test_custom_report_params_grouping_and_layout(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    session = create_custom(controller, "C")

    session.handle(Key("ENTER"))
    type_text(session, "Alpha Video Invoice Report 2")
    session.handle(Key("ENTER"))
    session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    session.handle(Key("BACKSPACE"))
    session.handle(Key("BACKSPACE"))
    type_text(session, "120")
    session.handle(Key("ENTER"))
    session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    session.handle(Key("BACKSPACE"))
    type_text(session, "1")
    session.handle(Key("ENTER"))
    assert session.report.width == 120
    assert session.report.group_count == 1

    session.handle(Key("F10"))
    assert session.param_page == 2
    session.handle(Key("F10"))
    assert session.stage == "grouping"
    session.handle(Key("F2"))
    assert choose_picker(controller, "AVSALES.CUST_ID")
    assert session.report.groups[0].break_field == "AVSALES.CUST_ID"

    # Bandiere del gruppo.
    session.handle(Key("TAB"))
    session.handle(Key("ENTER"))
    assert session.report.groups[0].reprint_titles
    session.handle(Key("TAB"))
    session.handle(Key("F10"))
    assert session.stage == "layout"
    assert session.section in session.report.sections

    session.section = "detail"
    session.row = 1
    session.col = 1
    place_field(controller, "AVSALES", "CUST_ID", "Unique")
    session.col = 10
    place_field(controller, "AVSALES", "INVTOTAL", "Value")
    assert session.report.fields[-1].source == "AVSALES.INVTOTAL"
    assert session.report.fields[0].data == "Unique"

    controller.handle(Key("F10"))
    controller.handle(Key("ENTER"))  # Save
    assert controller.base == "menu"
    saved = workspace.get_report("AVSALES", "C")
    assert saved is not None
    assert saved.description == "Alpha Video Invoice Report 2"
    assert saved.group_count == 1
    assert saved.groups[0].break_field == "AVSALES.CUST_ID"


def test_quick_report_save_preview_and_pdf(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_reports(controller)
    controller.handle(Key("ENTER"))
    session = controller.report_designer
    type_text(session, "A")
    session.handle(Key("ENTER"))
    session.handle(Key("ENTER"))  # Quick setup
    assert session.stage == "layout"
    text = "\n".join(controller.view().buffer.to_lines())
    assert "Quick Report" in text.replace(" ", "") or any(
        "Quick Report" in item.text for item in session.report.texts)
    controller.handle(Key("F10"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Save and preview
    assert controller.base == "reportpreview"
    preview = controller.report_preview
    assert preview.output.pages
    assert "Richardson" in preview.output.text
    preview.handle(Key("PGDN"))
    preview.handle(Key("DOWN"))
    preview.handle(Key("RIGHT"))
    preview.handle(Key("HOME"))
    preview.handle(Key("F10"))
    assert preview.pdf_path is not None and preview.pdf_path.exists()
    preview.handle(Key("ESC"))
    controller.handle(Key("ESC"))
    assert controller.base == "menu"


def test_print_menu_chooses_report(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_reports(controller)
    controller.handle(Key("ENTER"))
    session = controller.report_designer
    type_text(session, "A")
    session.handle(Key("ENTER"))
    session.handle(Key("ENTER"))
    controller.handle(Key("F10"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))  # chiude il messaggio
    controller.handle(Key("P"))
    assert controller.overlay.target == "print"
    controller.handle(Key("ENTER"))
    assert controller.overlay.action == "print-report"
    controller.handle(Key("ENTER"))
    assert controller.base == "reportpreview"
    assert "A - Quick report" in controller.report_preview.title
    controller.handle(Key("ESC"))


def test_borrow_and_erase_report(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_reports(controller)
    controller.handle(Key("ENTER"))
    session = controller.report_designer
    type_text(session, "A")
    session.handle(Key("ENTER"))
    session.handle(Key("ENTER"))
    controller.handle(Key("F10"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))

    open_reports(controller)
    controller.handle(Key("DOWN"))  # Borrow
    controller.handle(Key("ENTER"))
    assert controller.overlay.action == "borrow-report"
    controller.handle(Key("ENTER"))
    assert controller.report_designer.stage == "borrow_letter"
    type_text(controller, "B")
    controller.handle(Key("ENTER"))
    assert controller.base == "menu"
    assert workspace.get_report("AVSALES", "B") is not None
    controller.handle(Key("ENTER"))  # chiude il messaggio

    open_reports(controller)
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))  # Erase
    controller.handle(Key("ENTER"))
    assert controller.overlay.action == "erase-report"
    while controller.overlay.items[controller.overlay.selected][1] != "B":
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "confirm"
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))
    assert workspace.get_report("AVSALES", "B") is None


def test_calculated_and_summary_fields_from_designer(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    session = create_custom(controller, "D")
    session.handle(Key("F10"))
    session.handle(Key("F10"))
    assert session.stage == "layout"
    session.section = "detail"
    session.row = 1
    session.col = 30

    session.handle(Key("F4"))
    assert session.picker_kind == "synthetic"
    controller.handle(Key("ENTER"))  # calculated
    assert session.stage == "calc"
    session.handle(Key("F2"))
    assert session.stage == "calc_name"
    type_text(session, "DOUBLE")
    session.handle(Key("ENTER"))
    type_text(session, "INVTOTAL * 2")
    session.handle(Key("ENTER"))
    assert session.report.calcs[0].name == "DOUBLE"
    session.handle(Key("F10"))
    assert session.stage == "layout"

    session.row = 1
    session.col = 45
    place_field(controller, "CALC", "DOUBLE", "Value")
    assert session.report.fields[-1].source == "CALC.DOUBLE"

    session.handle(Key("F4"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # summary
    assert session.picker_kind == "summary_field"
    assert choose_picker(controller, "AVSALES.INVTOTAL")
    assert choose_picker(controller, "Total")
    assert choose_picker(controller, "Grand")
    assert choose_picker(controller, "None")
    assert choose_picker(controller, "Pre-processed")
    assert session.report.summaries
    assert session.report.fields[-1].source.startswith("SUMMARY.")

    session.section = "detail"
    session.row = 1
    session.col = 1
    session.handle(Key("F9"))
    assert session.picker_kind == "line"
    controller.handle(Key("ENTER"))  # left justify
    session.handle(Key("F3"))
    assert session.picker_kind == "sections_menu"
    controller.handle(Key("ENTER"))  # insert
    assert session.picker_kind == "sections_add"
    assert choose_picker(controller, "report_header")
    assert "report_header" in session.report.sections
    session.handle(Key("F3"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # delete
    assert choose_picker(controller, "titles")
    assert "titles" not in session.report.sections


def test_formatting_options_from_designer(tmp_path):
    workspace, database = make_sales(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    session = create_custom(controller, "E")
    session.handle(Key("F10"))
    session.handle(Key("F10"))
    session.section = "detail"
    session.row = 1
    session.col = 1
    place_field(controller, "AVSALES", "LASTNAME", "Value")
    assert session.report.fields
    session.handle(Key("Alt-O") if False else Key("O", alt=True))
    assert session.stage == "formatting"
    session.format_row = 0
    session.format_col = 4
    session.handle(Key("ENTER"))
    session.edit_text = "8"
    session.handle(Key("ENTER"))
    session.format_col = 3
    session.handle(Key("SPACE"))
    session.format_col = 5
    session.handle(Key("SPACE"))
    session.handle(Key("F10"))
    assert session.stage == "layout"
    item = session.report.fields[0]
    assert item.length == 8
    assert item.data == "Unique"
    assert item.justification in ("R", "C", "N", "L")
