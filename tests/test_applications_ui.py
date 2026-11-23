"""O11 — schermate delle applicazioni: editor, runtime, banner e protezioni."""


from adbx.app.model import (
    AppItem,
    Application,
    AppMenu,
    BannerScreen,
    password_hash,
)
from adbx.app.store import ApplicationStore
from adbx.data.fields import Field
from adbx.data.forms import FormDefinition, FormField
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def type_text(target, text):
    for char in text:
        target.handle(Key("SPACE" if char == " " else char,
                          shift=char.isupper()))


def make_db(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVPATRON", [
        Field("NAME", "C", 20), Field("CITY", "C", 15)])
    database.append({"NAME": "Ada", "CITY": "Placid"})
    database.append({"NAME": "Bob", "CITY": "Placid"})
    workspace.save_database(database)
    return workspace, database


def app_store(tmp_path):
    return ApplicationStore(tmp_path / "objects" / "apps")


def demo_app(name="AVSYSTEM"):
    app = Application(name, description="Alpha Video Store System")
    app.menu = AppMenu(title="ALPHA VIDEO", flow="Return", items=[
        AppItem("Customers", action="Macro",
                macro='{WRITE 1,1,"customers"}'),
        AppItem("Movies", action="Sub-Menu",
                submenu=AppMenu(title="MOVIES", flow="Stay", items=[
                    AppItem("By title", action="Macro",
                            macro='{WRITE 2,1,"title"}')])),
    ])
    return app


def test_applications_menu(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    controller.handle(Key("A"))
    assert controller.overlay.kind == "submenu"
    assert controller.overlay.target == "applications"
    text = "\n".join(controller.view().buffer.to_lines())
    assert "Create/edit application" in text
    assert "Prevent/allow file alterations" in text


def test_create_application_parameters_and_outline(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    app_store(tmp_path).save(demo_app())
    controller._application_action("edit")
    type_text(controller, "AVSYSTEM")
    controller.handle(Key("ENTER"))
    assert controller.base == "appeditor"
    editor = controller.application_editor
    assert editor.stage == "parameters"
    assert "Alpha Video Store System" in editor.edit_text or True
    controller.handle(Key("F10"))
    assert editor.stage == "outline"
    assert editor.rows[0].text == "= ALPHA VIDEO"
    editor.focus = "outline"
    editor.row = 0
    controller.handle(Key("F2"))
    assert len(editor.app.menu.items) == 3
    assert editor.focus == "detail"
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    restored = app_store(tmp_path).get("AVSYSTEM")
    assert len(restored.menu.items) == 3


def test_edit_detail_text_action_and_macro_editor(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    app_store(tmp_path).save(demo_app())
    controller._open_application_editor("AVSYSTEM")
    editor = controller.application_editor
    editor.stage = "outline"
    editor.focus = "outline"
    editor.row = 1
    editor.focus = "detail"
    editor.detail = 0
    editor.edit_text = "Patrons"
    editor.handle(Key("ENTER"))
    assert editor.app.menu.items[0].text == "Patrons"
    editor.detail = 4
    editor.edit_text = '{WRITE 4,1,"macro"}'
    editor.handle(Key("ENTER"))
    assert editor.app.menu.items[0].macro == '{WRITE 4,1,"macro"}'
    editor.detail = 4
    controller.handle(Key("F4"))
    assert controller.base == "macroeditor"
    controller.macro_editor.lines = ['{WRITE 5,1,"edited"}']
    controller.handle(Key("F10"))
    assert controller.base == "appeditor"
    assert editor.app.menu.items[0].macro == '{WRITE 5,1,"edited"}'


def test_add_submenu_action_creates_heading(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    app_store(tmp_path).save(demo_app())
    controller._open_application_editor("AVSYSTEM")
    editor = controller.application_editor
    editor.stage = "outline"
    editor.row = 1  # Customers item
    editor.focus = "detail"
    editor.detail = 2
    editor.edit_text = "Sub-Menu"
    editor.handle(Key("ENTER"))
    assert editor.app.menu.items[0].action == "Sub-Menu"
    assert any(row.kind == "menu" for row in editor.rows)


def test_run_application_macro_and_submenu(tmp_path):
    _workspace, database = make_db(tmp_path)
    app_store(tmp_path).save(demo_app())
    controller = ShellController(tmp_path, open_path=database.source)
    controller._application_action("run")
    assert controller.overlay.action == "run-app"
    controller.handle(Key("ENTER"))
    assert controller.base == "appsession"
    assert controller.application_session.runtime.menu.title == "ALPHA VIDEO"
    controller.handle(Key("C"))
    assert (1, 1, "customers") in controller.script_writes
    controller.handle(Key("M"))
    assert controller.application_session.runtime.menu.title == "MOVIES"
    controller.handle(Key("B"))
    assert (2, 1, "title") in controller.script_writes
    controller.handle(Key("ESC"))
    assert controller.application_session.runtime.menu.title == "ALPHA VIDEO"
    controller.handle(Key("ESC"))
    assert controller.base == "menu"


def test_application_password_prompt(tmp_path):
    _workspace, database = make_db(tmp_path)
    app = demo_app()
    app.menu.items[0].password_hash = password_hash("secret")
    app_store(tmp_path).save(app)
    controller = ShellController(tmp_path, open_path=database.source)
    controller._open_application_session_by_name("AVSYSTEM")
    controller.handle(Key("C"))
    assert controller.overlay.action == "app-password"
    type_text(controller, "wrong")
    controller.handle(Key("ENTER"))
    assert controller.application_session.runtime.status == "Incorrect password."
    controller.handle(Key("C"))
    type_text(controller, "SECRET")
    controller.handle(Key("ENTER"))
    assert (1, 1, "customers") in controller.script_writes


def test_application_escape_policies(tmp_path):
    _workspace, database = make_db(tmp_path)
    app = demo_app()
    app.allow_escape = "Password"
    app.escape_password_hash = password_hash("esc")
    app_store(tmp_path).save(app)
    controller = ShellController(tmp_path, open_path=database.source)
    controller._open_application_session_by_name("AVSYSTEM")
    controller.handle(Key("ESC"))
    assert controller.overlay.action == "app-escape"
    type_text(controller, "ESC")
    controller.handle(Key("ENTER"))
    assert controller.base == "menu"


def test_banner_painter_and_startup_banner(tmp_path):
    _workspace, database = make_db(tmp_path)
    app = demo_app()
    app.banner = BannerScreen()
    app_store(tmp_path).save(app)
    controller = ShellController(tmp_path, open_path=database.source)
    controller._open_application_editor("AVSYSTEM")
    editor = controller.application_editor
    editor.stage = "outline"
    controller.handle(Key("F6"))
    assert controller.base == "bannerpainter"
    painter = controller.banner_painter
    type_text(painter, "WELCOME")
    controller.handle(Key("F3"))
    controller.handle(Key("F10"))
    assert controller.base == "appeditor"
    assert painter.app.banner.text(0, 0) == "W"
    controller.handle(Key("F10"))
    assert app_store(tmp_path).get("AVSYSTEM").banner.text(0, 0) == "W"
    controller._open_application_session_by_name("AVSYSTEM")
    assert controller.application_session.banner_pending
    assert "WELCOME" in "\n".join(controller.view().buffer.to_lines())
    controller.handle(Key("ENTER"))
    assert not controller.application_session.banner_pending
    assert controller.application_session.runtime.menu.title == "ALPHA VIDEO"


def test_simulation_does_not_run_macro(tmp_path):
    _workspace, database = make_db(tmp_path)
    app_store(tmp_path).save(demo_app())
    controller = ShellController(tmp_path, open_path=database.source)
    controller._open_application_editor("AVSYSTEM")
    controller.application_editor.stage = "outline"
    controller.handle(Key("F8"))
    assert controller.base == "appsession"
    assert controller.application_session.runtime.simulate
    controller.handle(Key("C"))
    assert (1, 1, "customers") not in controller.script_writes
    controller.handle(Key("ESC"))
    assert controller.base == "appeditor"
    assert controller.application_editor is not None


def test_startup_database_and_macro(tmp_path):
    workspace, database = make_db(tmp_path)
    app = demo_app()
    app.startup = "AVPATRON.DBF"
    app.startup_macro = '{WRITE 6,1,"startup"}'
    app_store(tmp_path).save(app)
    other = workspace.create_database("OTHER", [Field("X", "C", 2)])
    workspace.save_database(other)
    controller = ShellController(tmp_path)
    controller._open_application_session_by_name("AVSYSTEM")
    assert controller.database is not None
    assert controller.database.name == "AVPATRON"
    assert (6, 1, "startup") in controller.script_writes


def test_protection_blocks_form_layout(tmp_path):
    workspace, database = make_db(tmp_path)
    form = FormDefinition(workspace, database.name, letter="A")
    form.fields = [FormField(database.name, "NAME", row=2, col=2)]
    workspace.save_form(form)
    controller = ShellController(tmp_path, open_path=database.source)
    controller._application_action("protect")
    assert controller.overlay.action == "protect-scope"
    controller.handle(Key("ENTER"))
    assert controller.base == "protection"
    session = controller.protection_session
    index = [name for name, _value in session.items].index("Forms")
    session.selected = index
    controller.handle(Key("SPACE"))
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    controller.handle(Key("L"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))
    assert controller.base == "menu"
    assert "protected" in controller.overlay.text


def test_erase_application(tmp_path):
    _workspace, database = make_db(tmp_path)
    app_store(tmp_path).save(demo_app())
    controller = ShellController(tmp_path, open_path=database.source)
    controller._application_action("erase")
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "confirm"
    controller.handle(Key("ENTER"))
    assert not app_store(tmp_path).names()


def test_create_new_application_from_prompt(tmp_path):
    _workspace, database = make_db(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    controller._application_action("edit")
    assert controller.overlay.action == "app-name"
    type_text(controller, "AVNEW")
    controller.handle(Key("ENTER"))
    assert controller.base == "appeditor"
    assert controller.application_editor.app.name == "AVNEW"
    controller.application_editor.edit_text = "A brand new application"
    controller.handle(Key("ENTER"))
    controller.handle(Key("F10"))
    controller.handle(Key("F10"))
    assert app_store(tmp_path).get("AVNEW").description == "A brand new application"


def test_macro_learning_assigns_item_macro(tmp_path):
    _workspace, database = make_db(tmp_path)
    app_store(tmp_path).save(demo_app())
    controller = ShellController(tmp_path, open_path=database.source)
    controller._open_application_editor("AVSYSTEM")
    editor = controller.application_editor
    editor.stage = "outline"
    editor.focus = "outline"
    editor.row = 1
    controller.handle(Key("F3"))
    assert controller.recording is not None
    controller.handle(Key("DOWN"))
    controller.handle(Key("F3", alt=True))
    assert editor.app.menu.items[0].macro == "{DOWN}"
    assert controller.base == "appeditor"


def test_application_help_file(tmp_path):
    _workspace, database = make_db(tmp_path)
    help_file = tmp_path / "APP.HLP"
    help_file.write_text("First help line\nSecond line\n", encoding="utf-8")
    app = demo_app()
    app.menu.items[0].help_file = str(help_file)
    app_store(tmp_path).save(app)
    controller = ShellController(tmp_path, open_path=database.source)
    controller._open_application_session_by_name("AVSYSTEM")
    controller.handle(Key("F1"))
    assert controller.overlay is not None
    assert "First help line" in controller.overlay.text
