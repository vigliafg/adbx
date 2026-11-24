"""O12 — configurazione, driver di stampa, colori e documentazione."""

from pathlib import Path

from adbx.app.model import AppItem, Application, AppMenu
from adbx.app.store import ApplicationStore
from adbx.config.colors import defaults_palette, load_colors, save_colors, theme_for
from adbx.config.defaults import ConfigStore, DefaultSettings
from adbx.config.printers import (
    LETTERS,
    PRINTER_MODELS,
    PrinterConfig,
    PrinterDriver,
    configure_printer,
    driver_from_catalog,
)
from adbx.data import fields
from adbx.data.fields import Field, format_value, parse_value
from adbx.data.report_engine import ReportOutput, ReportPage
from adbx.data.workspace import Workspace
from adbx.docs.generator import (
    application_report,
    database_structure,
    field_rules_report,
    script_report,
    set_structure,
    write_document,
)
from adbx.render.report_pdf import write_report_pdf
from adbx.script.model import Script
from adbx.script.store import ScriptStore
from adbx.shell.theme import NEWPORT


def test_defaults_roundtrip_and_dates():
    defaults = DefaultSettings(date_separator="-", date_format="European",
                              pattern="insensitive", prevent_enter=True)
    restored = DefaultSettings.from_dict(defaults.to_dict())
    assert restored.date_separator == "-"
    assert restored.european_dates
    assert restored.prevent_enter
    fields.configure_dates("-", True)
    try:
        value = parse_value(Field("D", "D", 8), "31-12-1999")
        assert value == "19991231"
        assert format_value(Field("D", "D", 8), value) == "31-12-1999"
    finally:
        fields.configure_dates("/", False)
    assert format_value(Field("D", "D", 8), "19991231") == "12/31/1999"


def test_config_store(tmp_path):
    store = ConfigStore(tmp_path)
    store.defaults.single_step_enters = True
    store.defaults.date_separator = "."
    store.printers.install(driver_from_catalog("A", 1))
    store.save()
    again = ConfigStore(tmp_path)
    assert again.defaults.single_step_enters
    assert again.defaults.date_separator == "."
    assert again.printers.default == "A"
    assert again.printers.active.name == "Epson FX-850"


def test_screen_zoom_is_clamped_and_persisted(tmp_path):
    from adbx.config.display import ZOOM_DEFAULT, ZOOM_MAX, ZOOM_MIN

    assert DefaultSettings().screen_zoom == ZOOM_DEFAULT
    assert DefaultSettings(screen_zoom=130).screen_zoom == 130
    assert DefaultSettings(screen_zoom=10).screen_zoom == ZOOM_MIN
    assert DefaultSettings(screen_zoom=999).screen_zoom == ZOOM_MAX
    assert DefaultSettings.from_dict({"screen_zoom": "140"}).screen_zoom == 140

    store = ConfigStore(tmp_path)
    store.defaults.screen_zoom = 130
    store.save()
    assert ConfigStore(tmp_path).defaults.screen_zoom == 130


def test_zoom_base_uses_max_fit_and_zoom_scales_it():
    from adbx.config.display import base_pixel_size, zoom_pixel_size

    # Il 100% è il massimo che entra (o il tetto).
    assert base_pixel_size(18, 24) == 18
    assert base_pixel_size(40, 72) == 40
    assert base_pixel_size(43, 24) == 24
    # Lo zoom è un fattore su quel corpo.
    assert zoom_pixel_size(40, 110) == 44
    assert zoom_pixel_size(24, 150) == 36


def test_printer_catalog_has_26_models_and_letters():
    assert len(PRINTER_MODELS) == 26
    assert len(LETTERS) == 26
    config = PrinterConfig()
    for index, letter in enumerate(LETTERS):
        config.install(driver_from_catalog(letter, index))
    assert len(config.drivers) == 26
    assert config.default == "A"
    assert config.select("Z")
    assert config.default == "Z"
    assert config.erase("Z")
    assert config.default == "A"


def test_printer_driver_codes_and_page_advance():
    driver = PrinterDriver("A", page_advance="Formfeed",
                           setup=[27, 64], close=[27, 69])
    assert driver.advance_bytes() == b"\x0c"
    driver.page_advance = "Linefeed"
    assert driver.advance_bytes() == b"\n" * 66
    config = PrinterConfig(drivers={"A": driver}, default="A")
    stream = config.render_text(["one", "two"])
    assert stream.startswith(b"\x1b@")
    assert b"one\ntwo" in stream
    assert stream.endswith(b"\x1bE")


def test_pdf_uses_driver_margins(tmp_path):
    output = ReportOutput([ReportPage(1, ["Report line"])], width=80)
    plain = tmp_path / "plain.pdf"
    write_report_pdf(output, plain, "Plain")
    driver = PrinterDriver("A", margin_left=10, margin_top=5)
    configured = tmp_path / "margins.pdf"
    write_report_pdf(output, configured, "Margins", driver=driver)
    assert plain.is_file() and configured.is_file()
    assert plain.read_bytes() != configured.read_bytes()


def test_documentation_database_and_rules(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("DEMO", [
        Field("NAME", "C", 10), Field("AMOUNT", "N", 8, 2)])
    database.append({"NAME": "Ada", "AMOUNT": "12.00"})
    structure = database_structure(database)
    text = structure.to_text()
    assert "DEMO" in text and "NAME" in text and "AMOUNT" in text
    rules = field_rules_report(database)
    assert "Field rules" in rules.to_text()


def test_documentation_sets_scripts_and_apps(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create_database("DEMO", [Field("NAME", "C", 10)])
    from adbx.data.sets import SetDefinition

    definition = SetDefinition(workspace, "DEMOSET", primary="DEMO")
    workspace.save_set(definition)
    set_text = set_structure(definition).to_text()
    assert "DEMOSET" in set_text and "DEMO" in set_text

    store = ScriptStore(tmp_path / "scripts")
    script = store.save(Script("MAIN", source='{PLAY "CHILD"}'))
    store.save(Script("CHILD", source="{BEEP}"))
    script_text = script_report(script).to_text()
    assert "MAIN" in script_text and "CHILD" in script_text

    app_store = ApplicationStore(tmp_path / "apps")
    app = Application("DEMOAPP", menu=AppMenu(items=[
        AppItem("Run", action="Macro", macro="X")]))
    app_store.save(app)
    app_text = application_report(app).to_text()
    assert "DEMOAPP" in app_text and "Run" in app_text


def test_documentation_pdf(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("DEMO", [Field("NAME", "C", 10)])
    output = database_structure(database)
    pdf = write_document(output, tmp_path / "DOC.PDF", "Structure")
    assert pdf.is_file()
    assert pdf.read_bytes().startswith(b"%PDF")


def test_colors_roundtrip(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create_database("DEMO", [Field("NAME", "C", 5)])
    assert load_colors(workspace, "DEMO") == {}
    colors = defaults_palette()
    colors["Background"] = 4
    colors["Text"] = 15
    save_colors(workspace, "DEMO", colors)
    assert load_colors(workspace, "DEMO")["Background"] == 4
    theme = theme_for(workspace, "DEMO", NEWPORT)
    assert theme.bg == 4 and theme.text == 15


def test_printer_pdf_current_driver_global(tmp_path):
    configure_printer(PrinterDriver("A", margin_left=8))
    try:
        output = ReportOutput([ReportPage(1, ["x"])], width=80)
        path = write_report_pdf(output, tmp_path / "x.pdf", "X")
        assert path.is_file()
    finally:
        configure_printer(None)


def test_config_file_path(tmp_path):
    store = ConfigStore(tmp_path)
    store.save()
    assert (tmp_path / "config.json").is_file()
    assert Path(tmp_path / "config.json").read_text().startswith("{")
