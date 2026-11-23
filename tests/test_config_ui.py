"""O12 — schermate di configurazione, stampa e documentazione."""

from adbx.config.defaults import ConfigStore
from adbx.config.printers import driver_from_catalog
from adbx.data.fields import Field, format_value
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def type_text(target, text):
    for char in text:
        target.handle(Key("SPACE" if char == " " else char,
                          shift=char.isupper()))


def make_db(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVMOVIES", [
        Field("TITLE", "C", 20), Field("DATE", "D", 8),
        Field("PRICE", "N", 6, 2)])
    database.append({"TITLE": "Dumbo", "DATE": "19900131", "PRICE": "3.50"})
    workspace.save_database(database)
    return workspace, database


def open_other(controller, index):
    controller.handle(Key("O"))
    assert controller.overlay.target == "other"
    for _step in range(index):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))


def test_other_menu_lists_configuration(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    controller.handle(Key("O"))
    text = "\n".join(controller.view().buffer.to_lines())
    assert "Default settings" in text
    assert "Printer configuration" in text
    assert "Set screen colors" in text
    assert "Documentation" in text


def test_defaults_session_toggle_and_persist(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_other(controller, 1)
    assert controller.base == "defaults"
    session = controller.defaults_session
    controller.handle(Key("DOWN"))  # Date format
    controller.handle(Key("ENTER"))
    assert session.edit_text == "European"
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    config = ConfigStore(tmp_path)
    assert config.defaults.date_format == "European"
    assert format_value(database.field("DATE"), "19900131") == "31/01/1990"
    # ripristina il default per gli altri test
    config.defaults.date_format = "American"
    config.save()
    from adbx.data import fields
    fields.configure_dates("/", False)


def test_defaults_prevent_enter(tmp_path):
    _workspace, database = make_db(tmp_path)
    config = ConfigStore(tmp_path)
    config.defaults.prevent_enter = True
    config.save()
    controller = ShellController(tmp_path, open_path=database.source)
    controller.handle(Key("V"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.base == "menu"
    assert "prevented" in controller.overlay.text


def test_printer_install_select_save(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_other(controller, 2)
    assert controller.base == "printers"
    session = controller.printer_session
    controller.handle(Key("F2"))
    assert session.stage == "letter"
    type_text(controller, "A")
    controller.handle(Key("ENTER"))
    assert session.stage == "model"
    controller.handle(Key("ENTER"))
    assert session.stage == "edit"
    assert session.driver.letter == "A"
    controller.handle(Key("F10"))
    assert session.stage == "list"
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    config = ConfigStore(tmp_path)
    assert config.printers.default == "A"
    assert config.printers.active is not None
    assert config.printers.active.name == "Generic parallel printer"


def test_printer_edit_codes_and_page_advance(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    config = ConfigStore(tmp_path)
    config.printers.install(driver_from_catalog("A", 1))
    config.save()
    controller = ShellController(tmp_path, open_path=database.source)
    open_other(controller, 2)
    session = controller.printer_session
    controller.handle(Key("ENTER"))
    assert session.stage == "edit"
    session.field_index = 2
    session._load()
    assert session.edit_text == "Formfeed"
    controller.handle(Key("ENTER"))
    assert session.edit_text == "Sheetfeeder"
    session.field_index = 17
    session._load()
    session.edit_text = "12,10"
    controller.handle(Key("ENTER"))
    assert session.driver.new_page == [12, 10]


def test_color_session_persists_and_applies(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_other(controller, 3)
    assert controller.base == "colors"
    controller.handle(Key("SPACE"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("SPACE"))
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert controller.theme.bg != 1 or controller.theme.text != 15
    reopened = ShellController(tmp_path, open_path=database.source)
    assert reopened.theme.bg == controller.theme.bg
    assert reopened.theme.text == controller.theme.text


def test_documentation_generate_preview_and_pdf(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_other(controller, 4)
    assert controller.base == "documentation"
    session = controller.documentation_session
    controller.handle(Key("ENTER"))  # Database structure
    assert session.stage == "target"
    controller.handle(Key("ENTER"))
    assert session.stage == "options"
    controller.handle(Key("F10"))
    assert session.stage == "preview"
    assert "AVMOVIES" in "\n".join(controller.view().buffer.to_lines())
    controller.handle(Key("P"))
    pdf = session.pdf_path
    assert pdf is not None and pdf.is_file()
    assert pdf.read_bytes().startswith(b"%PDF")
    controller.handle(Key("F10"))
    assert controller.base == "menu"


def test_pattern_matching_saved_in_config(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_other(controller, 0)
    assert controller.workspace.pattern_mode == "case"
    config = ConfigStore(tmp_path)
    assert config.defaults.pattern == "case"


def test_defaults_screen_zoom_edits_and_persists(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    open_other(controller, 1)
    session = controller.defaults_session
    session.selected = len(session.FIELDS) - 1
    session._load()
    assert session.edit_text == "100"
    for _step in range(3):
        controller.handle(Key("BACKSPACE"))
    type_text(controller, "130")
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert controller.screen_zoom == 130
    assert ConfigStore(tmp_path).defaults.screen_zoom == 130

    reopened = ShellController(tmp_path, open_path=database.source)
    assert reopened.screen_zoom == 130
    reopened.set_screen_zoom(999)
    assert reopened.screen_zoom == 200
    assert ConfigStore(tmp_path).defaults.screen_zoom == 200
