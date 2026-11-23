"""O10 — motore di script: comandi, variabili e trigger."""


import pytest

from adbx.data.expressions import Context
from adbx.data.fields import Field
from adbx.screen.keys import Key
from adbx.script import (
    KIND_DIALOG,
    KIND_KEYSTROKE,
    DialogBox,
    DialogControl,
    Script,
    ScriptEngine,
    ScriptError,
    ScriptHost,
    ScriptStore,
    Variables,
    script_template,
)
from adbx.script.parser import split_args, tokenize
from adbx.script.variables import expression_literal


class FakeHost(ScriptHost):
    def __init__(self):
        self.keys = []
        self.writes = []
        self.tones = []
        self.beeps = 0
        self.pauses = 0
        self.waits = []
        self.screen_modes = []
        self.deferred = []
        self.mouse_events = []
        self.messages = []
        self.main_menus = 0
        self.tool_ends = 0
        self.ended_apps = 0
        self.external_calls = []
        self.prompt_values = []
        self.prompt_result = "answer"
        self.dialog_calls = []
        self.dialog_result = None
        self.lookup_result = None
        self.lookup_calls = []
        self.screen = ["Demo screen", "Second line"]
        self.context = Context(
            fields=(Field("NAME", "C", 10), Field("AMOUNT", "N", 8, 2)),
            values={"NAME": "Ada", "AMOUNT": "12.50"})

    def press(self, key):
        self.keys.append(key)

    def screen_lines(self):
        return self.screen

    def write(self, row, col, text):
        self.writes.append((row, col, text))

    def beep(self):
        self.beeps += 1

    def tone(self, frequency, duration):
        self.tones.append((frequency, duration))

    def pause(self):
        self.pauses += 1

    def wait_for(self, seconds):
        self.waits.append(("for", seconds))

    def wait_key(self, key):
        self.waits.append(("key", key))
        return key

    def wait_screen(self, row, col, text):
        self.waits.append(("screen", row, col, text))
        return True

    def wait_until(self, moment):
        self.waits.append(("until", moment))
        return True

    def screen_mode(self, mode):
        self.screen_modes.append(mode)

    def prompt(self, label, length, default="", secret=False):
        self.prompt_values.append((label, length))
        return self.prompt_result

    def show_dialog(self, name, *, modal=True):
        self.dialog_calls.append((name, modal))
        return self.dialog_result

    def field_context(self):
        return self.context

    def lookup(self, kind, database, index, key):
        self.lookup_calls.append((kind, database, index, key))
        return self.lookup_result

    def lookup_record(self, database, record):
        self.lookup_calls.append(("record", database, record))
        return self.lookup_result

    def external(self, program, parameter_database, minimum_memory, *, clear):
        self.external_calls.append((program, parameter_database,
                                    minimum_memory, clear))
        return 0

    def mouse(self, action, row=0, col=0):
        self.mouse_events.append((action, row, col))

    def main_menu(self):
        self.main_menus += 1

    def tool_end(self):
        self.tool_ends += 1

    def end_app(self):
        self.ended_apps += 1

    def defer_keys(self, keys):
        self.deferred.append(keys)

    def error(self, message):
        self.messages.append(message)


@pytest.fixture
def engine(tmp_path):
    store = ScriptStore(tmp_path / "scripts")
    host = FakeHost()
    return ScriptEngine(store, host), host, store


def run(engine, source, name="TEST"):
    script = Script(name, kind=KIND_KEYSTROKE, source=source)
    return engine.run(script)


def test_tokenizer_keystrokes_commands_and_comments():
    tokens = tokenize("AB{F10}{*comment*} {IF 1,{C} }")
    assert [token.value for token in tokens] == ["A", "B", "F10", " ",
                                                  "IF 1,{C} "]
    assert tokens[4].kind == "command"


def test_split_args_respects_blocks_and_quotes():
    assert split_args('A,"B,C",{D,E}') == ["A", '"B,C"', "{D,E}"]


def test_simple_keystrokes_are_fed_to_host(engine):
    engine, host, _store = engine
    assert run(engine, "AB{ENTER}{F10} x")
    assert host.keys == [Key("A", shift=True), Key("B", shift=True),
                         Key("ENTER"), Key("F10"), Key("SPACE"), Key("X")]


def test_set_and_expression_commands(engine):
    engine, host, _store = engine
    assert run(engine, '{SET %N,"5"}{SET %M,VAL(%N)+2}'
                     '{IF %M=7,{{WRITE 1,1,"ok"}}}')
    assert engine.variables.get("%M") == "7"
    assert host.writes == [(1, 1, "ok")]


def test_set_indirection(engine):
    engine, _host, _store = engine
    run(engine, '{SET %VARNAME,"%PRICE"}{SET@VARNAME,"20"}')
    assert engine.variables.get("%PRICE") == "20"


def test_variables_limits_indirection_and_persistence(tmp_path):
    variables = Variables()
    variables.set("A", "x" * 300)
    assert len(variables.get("A")) == 254
    variables.set("B", "%A")
    assert variables.get("@B") == variables.get("A")
    variables.set("QBE_ONE", "1")
    variables.set("QBE_TWO", "1")
    variables.set("OTHER", "1")
    assert variables.clear("%QBE_*") == 2
    variables.set("KEEP", "yes")
    path = tmp_path / "VARS.VAR"
    assert variables.save(path) == 4
    other = Variables()
    assert other.load(path) == 4
    assert other.get("KEEP") == "yes"


def test_expression_literal_quotes_text_and_numbers():
    assert expression_literal("12") == "12"
    assert expression_literal("T") == ".T."
    assert expression_literal("01/02/1990") == "{01/02/1990}"
    assert expression_literal("Ada") == '"Ada"'


def test_if_and_case(engine):
    engine, host, _store = engine
    source = ('{IF 1=2,{{WRITE 1,1,"no"}},{{WRITE 1,1,"yes"}}}'
              '{CASE 1=2,{{WRITE 2,1,"a"}}, 2=2,{{WRITE 2,1,"b"}}}')
    assert run(engine, source)
    assert host.writes == [(1, 1, "yes"), (2, 1, "b")]


def test_goto_and_loop(engine):
    engine, _host, _store = engine
    source = '{SET %N,"3"}:A{SET %C,VAL(%C)+1}{LOOP :A,%N}'
    assert run(engine, source)
    assert engine.variables.get("%C") == "3"
    assert engine.variables.get("%N") == "1"


def test_play_nested_script_and_cancel(engine):
    engine, host, store = engine
    store.save(Script("CHILD", source='{WRITE 1,1,"child"}'))
    assert run(engine, '{PLAY "CHILD"}{WRITE 2,1,"parent"}')
    assert host.writes == [(1, 1, "child"), (2, 1, "parent")]
    store.save(Script("STOP", source='{CANCEL}{WRITE 1,1,"never"}'))
    assert run(engine, '{PLAY "STOP"}{WRITE 3,1,"after"}')
    assert host.writes[-1] == (3, 1, "after")


def test_abort_cancel_and_endapp(engine):
    engine, host, _store = engine

    class StopHost(FakeHost):
        pass

    script = Script("X", source="{ABORT}")
    assert engine.run(script)
    assert host.main_menus == 1

    runner = ScriptEngine(ScriptStore(engine.store.directory), StopHost())
    assert runner.run(Script("Y", source="{ENDAPP}"))
    assert runner.host.ended_apps == 1


def test_abort_stops_parent(engine):
    engine, host, store = engine
    store.save(Script("STOPALL", source="{ABORT}"))
    assert run(engine, '{PLAY "STOPALL"}WRITE 1,1,"never"')
    assert host.main_menus == 1
    assert not host.writes


def test_screen_test_blocks_wrong_screen(engine):
    engine, host, _store = engine
    script = Script("T", source='{WRITE 1,1,"x"}')
    script.screen_test.lines = ["Missing text"]
    assert not engine.run(script)
    assert host.messages and "Screen test" in host.messages[0]
    assert not host.writes


def test_screen_test_matches_visible_text(engine):
    engine, host, _store = engine
    script = Script("T", source='{WRITE 1,1,"x"}')
    script.screen_test.lines = ["second   line"]
    assert engine.run(script)
    assert host.writes


def test_write_read_prompt_and_beep_tone(engine):
    engine, host, _store = engine
    host.screen = ["0123456789"]
    source = ('{WRITE 2,3,"hello"}{READ %R,1,2,4}'
              '{PROMPT "Name?",%NAME,10}{BEEP}{TONE 160,40}')
    assert run(engine, source)
    assert host.writes == [(2, 3, "hello")]
    assert engine.variables.get("%R") == "1234"
    assert engine.variables.get("%NAME") == "answer"
    assert host.beeps == 1 and host.tones == [(160, 40)]


def test_prompt_cancel_stops_script(engine):
    engine, host, _store = engine
    host.prompt_result = None
    assert run(engine, '{PROMPT "Name?",%NAME}')
    assert engine.variables.get("%NAME") == ""


def test_wait_commands(engine):
    engine, host, _store = engine
    source = ('{WAITFOR 2}{WAITKEY ENTER}{WAITSCRN 1,1,"Demo"}'
              '{WAITUNTIL 10:00}{PAUSE}')
    assert run(engine, source)
    assert host.waits == [("for", 2.0), ("key", Key("ENTER")),
                          ("screen", 1, 1, "Demo"), ("until", "10:00")]
    assert host.pauses == 1


def test_waitscrn_failure_uses_onerror(engine):
    engine, host, _store = engine

    class NoScreen(FakeHost):
        def wait_screen(self, row, col, text):
            return False

    engine.host = NoScreen()
    assert run(engine, '{ONERROR {{WRITE 1,1,"handled"}}}{WAITSCRN 1,1,"x"}')
    assert engine.host.writes == [(1, 1, "handled")]


def test_screen_modes_and_noclear(engine):
    engine, host, _store = engine
    assert run(engine, "{SCREENOFF}{SCREENFREEZE}{SCREENON}{NOCLEAR}")
    assert host.screen_modes == ["off", "freeze", "on", "noclear"]


def test_show_dialog_and_buttons(engine):
    engine, host, store = engine
    store.save(Script("BOX", kind=KIND_DIALOG, dialog=DialogBox(title="Hi")))
    assert run(engine, '{SHOW "BOX"}')
    assert host.dialog_calls == [("BOX", False)]


def test_onkey_and_allowkeys(engine):
    engine, host, _store = engine
    assert run(engine, '{ONKEY X,{{WRITE 1,1,"mapped"}}}X')
    assert host.writes == [(1, 1, "mapped")]
    assert run(engine, '{ALLOWKEYS "A",{{WRITE 2,1,"blocked"}}}AB')
    assert host.writes[-1] == (2, 1, "blocked")
    assert host.keys[-1] == Key("A", shift=True)


def test_onescape_and_onmain(engine):
    engine, host, _store = engine
    assert run(engine, '{ONESCAPE {{WRITE 1,1,"esc"}}}{MAINMENU}{ESC}')
    assert host.writes[0] == (1, 1, "esc")
    assert host.main_menus == 1
    assert run(engine, '{ONMAIN {{WRITE 2,1,"main"}}}{MAINMENU}')
    assert host.writes[-1] == (2, 1, "main")


def test_mouse_commands(engine):
    engine, host, _store = engine
    assert run(engine, "{MOUSEDCLICK 3,4}{MOUSEDOWN}{MOUSEMOVE 5,6}{MOUSEUP}")
    assert host.mouse_events == [("dclick", 3, 4), ("down", 0, 0),
                                 ("move", 5, 6), ("up", 0, 0)]


def test_exec_and_execlr(engine):
    engine, host, _store = engine
    assert run(engine, '{EXEC "TOOL.EXE","PARAM",640}{EXECCLR "X"}')
    assert host.external_calls == [("TOOL.EXE", "PARAM", 640, False),
                                   ("X", "", 0, True)]


def test_external_error_uses_onerror(engine):
    engine, _host, _store = engine

    class NoExec(FakeHost):
        def external(self, *args, **kwargs):
            raise ScriptError("no exec")

    engine.host = NoExec()
    assert run(engine, '{ONERROR {{WRITE 1,1,"handled"}}}{EXEC "X"}')
    assert engine.host.writes == [(1, 1, "handled")]


def test_rpl(engine):
    engine, host, _store = engine

    class RplHost(FakeHost):
        def rpl(self, code, parameter):
            return (f"{code}:{parameter}", "")

    engine.host = RplHost()
    assert run(engine, '{RPL 7,"P",%R,%E}')
    assert engine.variables.get("%R") == "7:P"
    assert engine.variables.get("%E") == ""


def test_xlookup_creates_variables(engine):
    engine, host, _store = engine
    host.lookup_result = {"NAME": "Ada", "AMOUNT": "1.00"}
    assert run(engine, '{XLOOKUP "DB","IDX","A1",%STATUS}')
    assert engine.variables.get("%DB_NAME") == "Ada"
    assert engine.variables.get("%STATUS") == "0"


def test_xlookup_missing_record_sets_218(engine):
    engine, host, _store = engine
    host.lookup_result = None
    assert run(engine, '{ONERROR {{WRITE 1,1,"missing"}}}'
                      '{XLOOKUP "DB","IDX","ZZ",%STATUS}')
    assert engine.variables.get("%STATUS") == "218"
    assert host.writes == [(1, 1, "missing")]


def test_debug_on_off_and_trace(engine):
    engine, host, _store = engine
    assert run(engine, "{DEBUGON}{WRITE 1,1,\"x\"}{DEBUGOFF}")
    assert not engine.debug_on
    assert engine.trace


def test_trigger_registry_and_fire(engine):
    engine, host, store = engine
    store.save(Script("ONSAVE", source='{WRITE 1,1,"saved"}'))
    engine.set_variable("%SYS_TRIG_REC_SAVE", "ONSAVE")
    assert engine.triggers.get("REC_SAVE") == "ONSAVE"
    assert engine.variables.get("%SYS_TRIG_REC_SAVE") == "ONSAVE"
    assert engine.fire("REC_SAVE")
    assert host.writes == [(1, 1, "saved")]
    engine.set_variable("%SYS_TRIG_REC_SAVE", "")
    assert not engine.fire("REC_SAVE")


def test_trigger_keystrokes_are_deferred(engine):
    engine, host, store = engine
    store.save(Script("TRIG", source='W{TRIGKEYS "Q"}E'))
    engine.set_variable("%SYS_TRIG_ZOOM", "TRIG")
    engine.fire("ZOOM")
    assert host.keys == []
    assert host.deferred == ["{SHIFT-W}", "Q", "{SHIFT-E}"]


def test_unknown_command_and_label(engine):
    engine, host, _store = engine
    assert run(engine, "{NOSUCHCOMMAND}")
    assert host.messages
    engine.host.messages.clear()
    assert run(engine, "{GOTO :Z}")
    assert engine.host.messages


def test_script_limits():
    with pytest.raises(ScriptError):
        Script("../BAD")
    with pytest.raises(ScriptError):
        Script("OK", source="x" * 3001)
    with pytest.raises(ScriptError):
        DialogBox(controls=[DialogControl(kind="Unknown")])


def test_store_roundtrip_rename_export_import(tmp_path):
    store = ScriptStore(tmp_path / "scripts")
    script = script_template("DEMO", KIND_KEYSTROKE)
    script.description = "demo"
    script.source = 'WRITE 1,1,"x"'
    store.save(script)
    assert store.names() == ["DEMO"]
    restored = store.get("DEMO")
    assert restored.source == script.source
    store.rename("DEMO", "DEMO2")
    assert store.names() == ["DEMO2"]
    scp = store.export_scp("DEMO2")
    assert scp.is_file()
    imported = store.import_scp(scp, "DEMO3")
    assert imported.source == script.source
    assert store.delete("DEMO2")
    assert not store.delete("MISSING")


def test_store_rejects_name_and_limit(tmp_path):
    store = ScriptStore(tmp_path / "scripts")
    with pytest.raises(ScriptError):
        store.save(Script("toolongname"))


def test_vsave_and_vrestore_roundtrip(engine, tmp_path):
    engine, _host, _store = engine
    assert run(engine, '{SET %KEEP,"yes"}{VSAVE "%KEEP","STATE"}')
    engine.variables.set("%KEEP", "changed")
    assert run(engine, '{VRESTORE "STATE"}')
    assert engine.variables.get("%KEEP") == "yes"


def test_vrestore_missing_uses_onerror(engine):
    engine, host, _store = engine
    assert run(engine, '{ONERROR {{WRITE 1,1,"missing"}}}{VRESTORE "NOPE"}')
    assert host.writes == [(1, 1, "missing")]


def test_toolend_and_trigger_variables(engine):
    engine, host, _store = engine
    assert run(engine, "{TOOLEND}")
    assert host.tool_ends == 1
    assert engine.variables.get("%SYS_TRIG_REC_SAVE") == ""


def test_xlookupc_and_xlookupr(engine):
    engine, host, _store = engine
    host.lookup_result = {"NAME": "Ada"}
    assert run(engine, '{XLOOKUPC "DB","IDX","A",%S1}'
                      '{XLOOKUPR "DB",2,%S2}')
    assert engine.variables.get("%S1") == "0"
    assert engine.variables.get("%S2") == "0"
    assert ("record", "DB", 2) in host.lookup_calls


def test_keys_from_source_roundtrip():
    from adbx.script.engine import keys_from_source

    keys = keys_from_source("AB{F10}{ALT-X} ")
    assert [key.name for key in keys] == ["A", "B", "F10", "X", "SPACE"]
    assert keys[1].shift and keys[3].alt


def test_mouse_and_screen_command_trace(engine):
    engine, host, _store = engine
    assert run(engine, '{SCREENOFF}{MOUSEMOVE 2,3}{SCREENON}')
    assert host.screen_modes == ["off", "on"]
    assert ("move", 2, 3) in host.mouse_events
