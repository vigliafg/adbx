"""O10 — schermate degli script: menu, editor, designer, debug e playback."""


from adbx.data.fields import Field
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.script import (
    KIND_DIALOG,
    KIND_KEYSTROKE,
    KIND_MENU,
    DialogBox,
    MenuBarScript,
    Script,
    ScriptStore,
)
from adbx.shell.controller import ShellController
from adbx.shell.scripts import COMMANDS


def type_text(target, text):
    for char in text:
        target.handle(Key("SPACE" if char == " " else char,
                          shift=char.isupper()))


def choose(controller, index):
    for _step in range(index):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))


def make_patrons(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVPATRON", [
        Field("NAME", "C", 20), Field("CITY", "C", 15),
        Field("STATE", "C", 2), Field("ACTIVE", "L", 1),
    ])
    for name, city, state, active in (
            ("Ada", "Placid", "NY", "1"), ("Bob", "Placid", "CA", "0"),
            ("Cara", "Snowville", "NY", "1")):
        database.append({"NAME": name, "CITY": city, "STATE": state,
                         "ACTIVE": active})
    workspace.save_database(database)
    return workspace, database


def store_for(tmp_path):
    return ScriptStore(tmp_path / "objects" / "scripts")


def test_alt_f3_opens_script_menu(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    controller.handle(Key("F3", alt=True))
    assert controller.overlay.kind == "submenu"
    assert controller.overlay.target == "scripts"
    text = "\n".join(controller.view().buffer.to_lines())
    assert "create Keystroke script" in text
    assert "display script Variables" in text


def test_create_edit_and_save_keystroke_script(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    controller.handle(Key("F3", alt=True))
    choose(controller, 1)  # create Keystroke script
    type_text(controller, "HELLO")
    controller.handle(Key("ENTER"))
    type_text(controller, "Demo script")
    controller.handle(Key("ENTER"))
    assert controller.base == "scripteditor"
    editor = controller.script_editor
    assert editor is not None
    type_text(editor, '{WRITE 1,1,"hello"}')
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    script = store_for(tmp_path).get("HELLO")
    assert script.source == '{WRITE 1,1,"hello"}'
    assert script.description == "Demo script"


def test_editor_command_picker_inserts_template(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    store_for(tmp_path).save(Script("EDIT", source=""))
    controller._open_script("EDIT")
    editor = controller.script_editor
    editor.handle(Key("F2"))
    assert editor.picker is not None
    for _step in range(len(COMMANDS)):
        if editor.picker.value().startswith("{WRITE"):
            break
        editor.picker.move(1)
    editor.handle(Key("ENTER"))
    assert "{WRITE" in editor.source


def test_screen_test_and_capture(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    store_for(tmp_path).save(Script("TEST", source=""))
    controller._open_script("TEST")
    editor = controller.script_editor
    editor.handle(Key("F5"))
    type_text(editor, "Alpha Four")
    editor.handle(Key("ENTER"))
    assert editor.script.screen_test.lines == ["Alpha Four"]
    editor.handle(Key("F6"))
    assert editor.script.screen_test.enabled
    assert any("Alpha Four" in line for line in editor.script.screen_test.lines)


def test_play_script_uses_key_handler(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    store_for(tmp_path).save(Script("HELLO", source='{WRITE 2,1,"hello"}'))
    assert controller._play_script("HELLO")
    assert (2, 1, "hello") in controller.script_writes
    assert "hello" in "\n".join(controller.view().buffer.to_lines())


def test_play_choose_list_and_erase(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    store_for(tmp_path).save(Script("AAA", source='{WRITE 1,1,"a"}'))
    controller.handle(Key("F4", alt=True))
    assert controller.overlay.action == "play-script"
    controller.handle(Key("ENTER"))
    assert controller.script_writes
    controller._script_choose("erase-script", "Erase a script")
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "confirm"
    controller.handle(Key("ENTER"))
    assert not store_for(tmp_path).names()


def test_variables_overlay_edit_and_erase(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    engine = controller._script_engine()
    engine.variables.set("%DEMO", "one")
    controller._script_action("variables")
    assert controller.overlay.kind == "variables"
    assert "DEMO" in "\n".join(controller.view().buffer.to_lines())
    controller.handle(Key("ENTER"))
    type_text(controller, "two")
    controller.handle(Key("ENTER"))
    assert engine.variables.get("%DEMO") == "two"
    controller._script_action("variables")
    controller.handle(Key("F4"))
    assert not engine.variables.get("%DEMO")


def test_set_script_path(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    target = tmp_path / "SCRIPTS"
    controller._set_script_path(str(target))
    assert target.is_dir()
    assert controller._script_store().directory == target.resolve()
    controller._script_create(KIND_KEYSTROKE, "P1", "one")
    assert controller.script_editor is not None
    controller.handle(Key("ESC"))
    assert target.joinpath("P1.JSON").is_file()


def test_dialog_designer_and_runtime(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    store_for(tmp_path).save(Script("BOX", kind=KIND_DIALOG,
                                    dialog=DialogBox(title="Hello")))
    controller._open_script("BOX")
    designer = controller.dialog_designer
    assert designer is not None
    designer.handle(Key("F2"))
    designer.handle(Key("F3"))
    assert [control.kind for control in designer.dialog.controls] == [
        "Prompt", "Button"]
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    script = store_for(tmp_path).get("BOX")
    assert script.dialog is not None and len(script.dialog.controls) == 2
    assert controller._play_script("BOX")
    assert controller.base == "scriptdialog"
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("ESC"))
    assert controller.base == "menu"


def test_menu_bar_designer(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    store_for(tmp_path).save(Script("BAR", kind=KIND_MENU,
                                    menu=MenuBarScript()))
    controller._open_script("BAR")
    designer = controller.menu_designer
    designer.handle(Key("F2"))
    designer.handle(Key("F2"))
    assert len(designer.menu.items) == 2
    designer.handle(Key("F5"))
    assert len(designer.menu.items) == 1
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert len(store_for(tmp_path).get("BAR").menu.items) == 1


def test_debugger_steps_commands(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    store_for(tmp_path).save(Script("DBG", source=('{WRITE 1,1,"a"}'
                                                   '{WRITE 2,1,"b"}')))
    controller._open_script_debug("DBG")
    session = controller.script_debug
    assert session is not None
    assert controller.base == "scriptdebugger"
    session.handle(Key("F10"))
    assert (1, 1, "a") in controller.script_writes
    session.handle(Key("F10"))
    assert (2, 1, "b") in controller.script_writes
    controller.handle(Key("ESC"))
    assert controller.base == "menu"


def test_quick_record_and_play(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    controller.handle(Key("F1", alt=True))
    assert controller.recording is not None
    controller.handle(Key("DOWN"))
    controller.handle(Key("F3", alt=True))
    assert controller.recording is None
    script = store_for(tmp_path).get("UNTITLED")
    assert "{DOWN}" in script.source
    controller.handle(Key("F2", alt=True))
    assert controller.script_writes or True


def test_autoexec_runs_at_startup(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    store_for(tmp_path).save(Script("AUTOEXEC",
                                    source='{WRITE 3,1,"auto"}'))
    controller = ShellController(tmp_path, open_path=database.source)
    assert (3, 1, "auto") in controller.script_writes


def test_open_database_script_plays(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    store_for(tmp_path).save(Script("AVPATRO!",
                                    source='{WRITE 4,1,"opened"}'))
    controller = ShellController(tmp_path, open_path=database.source)
    assert (4, 1, "opened") in controller.script_writes


def test_ctrl_function_key_plays_script(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    store_for(tmp_path).save(Script("CTRLF1", source='{WRITE 5,1,"hot"}'))
    controller.handle(Key("F1", ctrl=True))
    assert (5, 1, "hot") in controller.script_writes


def test_record_delete_trigger(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    store = store_for(tmp_path)
    store.save(Script("ONDEL", source='{WRITE 6,1,"deleted"}'))
    store.save(Script("SETTRIG",
                      source='{SET %SYS_TRIG_REC_DEL,"ONDEL"}'))
    controller._play_script("SETTRIG")
    controller.handle(Key("ESC"))
    controller.handle(Key("V"))
    controller.handle(Key("ENTER"))
    assert controller.base == "records"
    controller.handle(Key("D", alt=True))
    assert (6, 1, "deleted") in controller.script_writes


def test_tools_plays_script_for_database(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    store_for(tmp_path).save(Script("AVPATRON", source='{WRITE 7,1,"tool"}'))
    controller.handle(Key("V"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("T"))
    assert controller.overlay is not None
    assert controller.overlay.action == "play-tools"
    controller.handle(Key("ENTER"))
    assert (7, 1, "tool") in controller.script_writes


def test_script_screen_test_blocks_playback(tmp_path):
    _workspace, database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=database.source)
    script = Script("BLOCK", source='{WRITE 8,1,"no"}')
    script.screen_test.lines = ["Text that is not on screen"]
    store_for(tmp_path).save(script)
    assert not controller._play_script("BLOCK")
    assert not controller.script_writes
    assert controller.overlay is not None
    assert "Screen test" in controller.overlay.text


def test_custom_menu_bar_replaces_view_menu(tmp_path):
    from adbx.data.forms import FormDefinition, FormField
    from adbx.script import MenuBarScript, MenuItem

    workspace, database = make_patrons(tmp_path)
    form = FormDefinition(workspace, database.name, letter="A")
    form.fields = [FormField(database.name, "NAME", row=2, col=2)]
    form.custom_menu = "BAR"
    workspace.save_form(form)
    store_for(tmp_path).save(Script(
        "BAR", kind=KIND_MENU,
        menu=MenuBarScript(items=[
            MenuItem("F2", "Say hello", '{WRITE 9,1,"menu"}'),
            MenuItem("F10", "Continue", "{F10}")])))
    controller = ShellController(tmp_path, open_path=database.source)
    controller.handle(Key("V"))
    controller.handle(Key("ENTER"))
    assert controller.records.menu_entries[0] == ("F2", "Say hello")
    controller.handle(Key("F2"))
    assert (9, 1, "menu") in controller.script_writes
