"""Motore di esecuzione degli script.

Il motore è deliberatamente sincrono e indipendente dalla UI: un `ScriptHost`
fornisce le primitive (premere un tasto, scrivere sullo schermo, chiedere un
valore, mostrare un dialog box). Il guscio Qt implementa lo stesso host, così
il playback passa dall'unico gestore di tastiera.

Sono implementati tutti i comandi del Reference Manual, capitolo 18, e i
ventidue eventi di trigger. Lo stato di esecuzione è riutilizzabile: un
`ScriptRunner` esegue un token per volta, il che permette al debugger di
fermarsi e avanzare con F10.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ..data.expressions import (
    Context,
    ExprError,
    evaluate,
    evaluate_boolean,
    value_to_text,
)
from ..screen.keys import Key, is_special
from ..screen.keys import parse as parse_key
from .model import (
    MAX_SCRIPT_CHARS,
    ScreenTest,
    Script,
    ScriptError,
)
from .parser import (
    block_body,
    command_body,
    command_name,
    is_block,
    split_args,
    tokenize,
    unquote,
)
from .store import ScriptStore
from .triggers import BY_CODE, TriggerRegistry
from .variables import Variables

MAX_NESTING = 10
_KEY_CHARS = {
    "-": "MINUS", "=": "EQUAL", "+": "PLUS", ",": "COMMA", ".": "PERIOD",
    ";": "SEMICOLON", ":": "COLON", "/": "SLASH", "\\": "BACKSLASH",
    "[": "LBRACKET", "]": "RBRACKET", "'": "QUOTE", '"': "DQUOTE",
    "`": "BACKTICK", "~": "TILDE", "!": "BANG", "?": "QUESTION",
    "*": "STAR", "&": "AMPERSAND", "^": "CARET", "%": "PERCENT",
    "$": "DOLLAR", "#": "HASH", "@": "AT", "<": "LT", ">": "GT",
    "(": "LPAREN", ")": "RPAREN", "_": "UNDERSCORE", "|": "PIPE",
}


class ScriptHalt(Exception):
    """Controllo di flusso: lo script si ferma."""


class ScriptCancel(ScriptHalt):
    """`{CANCEL}`: ferma lo script corrente e torna al chiamante."""


class ScriptAbort(ScriptHalt):
    """`{ABORT}`: ferma tutti gli script e torna al main menu."""


class ScriptEndApp(ScriptHalt):
    """`{ENDAPP}`: termina lo script e l'applicazione corrente."""


class ScriptHost:
    """Primitive offerte dal guscio al motore; i test possono sovrascriverle."""

    def press(self, key: Key) -> None:
        pass

    def cursor(self) -> tuple[int, int]:
        return (1, 1)

    def screen_lines(self) -> list[str]:
        return []

    def write(self, row: int, col: int, text: str) -> None:
        pass

    def beep(self) -> None:
        pass

    def tone(self, frequency: int, duration: int) -> None:
        pass

    def pause(self) -> None:
        pass

    def wait_for(self, seconds: float) -> None:
        pass

    def wait_key(self, key: Key | None) -> Key | None:
        return None

    def wait_screen(self, row: int, col: int, text: str) -> bool:
        return True

    def wait_until(self, moment: str) -> bool:
        return True

    def screen_mode(self, mode: str) -> None:
        pass

    def prompt(self, label: str, length: int, default: str = "",
               secret: bool = False) -> str | None:
        return None

    def read_screen(self, row: int, col: int, length: int) -> str:
        lines = self.screen_lines()
        if not (1 <= row <= len(lines)):
            return ""
        return lines[row - 1][max(0, col - 1):max(0, col - 1) + length]

    def show_dialog(self, name: str, *, modal: bool = True) -> dict[str, str] | None:
        return None

    def field_context(self) -> Context | None:
        return None

    def lookup(self, kind: str, database: str, index: str,
               key: str) -> dict[str, str] | None:
        return None

    def lookup_record(self, database: str, record: int) -> dict[str, str] | None:
        return None

    def external(self, program: str, parameter_database: str,
                 minimum_memory: int, *, clear: bool) -> int:
        raise ScriptError("External programs are not available in adbx.")

    def mouse(self, action: str, row: int = 0, col: int = 0) -> None:
        pass

    def main_menu(self) -> None:
        pass

    def tool_end(self) -> None:
        pass

    def end_app(self) -> None:
        pass

    def defer_keys(self, keys: str) -> None:
        pass

    def debug_pause(self, runner: "ScriptRunner", token: Any) -> None:
        pass

    def error(self, message: str) -> None:
        pass

    def rpl(self, code: int, parameter: str) -> tuple[str, str]:
        raise ScriptError(f"RPL routine {code} is not available.")


@dataclass
class ScriptEngine:
    """Ambiente condiviso da tutti gli script di una sessione."""

    store: ScriptStore
    host: ScriptHost
    variables: Variables = field(default_factory=Variables)
    triggers: TriggerRegistry = field(default_factory=TriggerRegistry)
    debug_on: bool = False
    nesting: int = 0
    allowed_keys: set[str] | None = None
    allow_else: str = ""
    on_error: str = ""
    on_escape: str = ""
    on_main: str = ""
    on_keys: dict[str, str] = field(default_factory=dict)
    last_error: str = ""
    trace: list[str] = field(default_factory=list)
    completed: bool = False

    def __post_init__(self) -> None:
        for event in BY_CODE.values():
            self.variables.set(event.variable, "")
        for event, script in self.triggers.scripts.items():
            self.variables.set(BY_CODE[event].variable, script)
        self.variables.set("%SYS_SCRIPT_PATH", str(self.store.directory))
        self.variables.set("%SYS_LAST_KEY", "")
        self.variables.set("%SYS_LAST_BUTTON", "")
        self.variables.set("%SYS_SAVE_MODE", "")
        self.variables.set("%SYS_VIEW_MODE", "V")
        self.variables.set("%SYS_TOOLS", "")
        self.variables.set("%SYS_SEARCH_COUNT", "0")
        self.variables.set("%SYS_SEARCH_OLD", "N")

    # -- valutazione -----------------------------------------------------
    def context(self) -> Context:
        return self.host.field_context() or Context(fields=(), values={})

    def evaluate(self, expression: str, *, strict: bool = False) -> Any:
        text = self.variables.expand_expression(expression).strip()
        if not text:
            return ""
        try:
            return evaluate(text, self.context())
        except ExprError:
            literal = unquote(expression)
            if literal != expression.strip() or not strict:
                return literal
            raise

    def condition(self, expression: str) -> bool:
        text = self.variables.expand_expression(expression).strip()
        if not text:
            return False
        return evaluate_boolean(text, self.context())

    def value_text(self, expression: str) -> str:
        value = self.evaluate(expression)
        if isinstance(value, bool):
            return "T" if value else "F"
        if isinstance(value, date):
            return value.strftime("%m/%d/%Y")
        if isinstance(value, Decimal):
            return value_to_text(value)
        return str(value) if value is not None else ""

    def text(self, argument: str) -> str:
        """Argomento character: toglie le virgolette e espande `%var`. """
        value = self.variables.expand(argument.strip())
        return unquote(value)

    # -- trigger ---------------------------------------------------------
    def set_variable(self, name: str, value: str) -> None:
        target = self.variables.resolve_target(name)
        self.variables.set(target, value)
        if target.startswith("%SYS_TRIG_"):
            if self.triggers.set_from_variable(target, value):
                for event, script in self.triggers.scripts.items():
                    self.variables.set(BY_CODE[event].variable, script)
                if not value.strip():
                    self.variables.set(target, "")

    def fire(self, event: str, *, trigger_host: bool = True) -> bool:
        """Esegue lo script associato all'evento, se attivo."""
        name = self.triggers.get(event)
        if not name:
            return False
        script = self.store.get(name, missing_ok=True)
        if script is None:
            self.host.error(f"Trigger script {name} not found.")
            return False
        runner = ScriptRunner(self, script.source, name=script.name,
                              trigger_mode=trigger_host)
        try:
            runner.run()
        except ScriptCancel:
            return True
        except (ScriptAbort, ScriptEndApp):
            raise
        except ScriptError as exc:
            self.last_error = str(exc)
            self.host.error(str(exc))
        return True

    def run(self, script: Script | str) -> bool:
        source = script.source if isinstance(script, Script) else script
        name = script.name if isinstance(script, Script) else "<inline>"
        test = script.screen_test if isinstance(script, Script) else ScreenTest()
        if not test.matches(self.host.screen_lines()):
            self.host.error("Screen test failed: the current screen is not "
                            "the one expected by the script.")
            return False
        runner = ScriptRunner(self, source, name=name)
        try:
            runner.run()
        except ScriptCancel:
            return True
        except ScriptAbort:
            self.host.main_menu()
            return True
        except ScriptEndApp:
            self.host.end_app()
            return True
        self.completed = runner.completed
        return runner.completed

    def play(self, name: str) -> bool:
        script = self.store.get(name, missing_ok=True)
        if script is None or not script.playable:
            self.host.error(f"Script {name} not found or not playable.")
            return False
        if self.nesting >= MAX_NESTING:
            self.host.error("Script nesting is limited to 10 levels.")
            return False
        self.nesting += 1
        try:
            return self.run(script)
        finally:
            self.nesting -= 1


@dataclass
class ScriptRunner:
    """Esecuzione di un singolo script, un token per volta."""

    engine: ScriptEngine
    source: str
    name: str = "<inline>"
    trigger_mode: bool = False
    tokens: list = field(init=False, default_factory=list)
    labels: dict[str, int] = field(init=False, default_factory=dict)
    pc: int = 0
    depth: int = 0
    completed: bool = False
    deferred: bool = False

    def __post_init__(self) -> None:
        if len(self.source) > MAX_SCRIPT_CHARS:
            raise ScriptError(
                f"Scripts are limited to {MAX_SCRIPT_CHARS} characters.")
        self.tokens = tokenize(self.source)
        self.labels = _labels(self.tokens)

    # -- ciclo -----------------------------------------------------------
    def run(self) -> None:
        while not self.completed:
            self.step()

    def step(self) -> bool:
        if self.completed:
            return True
        while self.pc < len(self.tokens):
            token = self.tokens[self.pc]
            self.pc += 1
            if token.kind == "key" and token.value == ":":
                if self.pc < len(self.tokens):
                    following = self.tokens[self.pc]
                    if following.kind == "key" and following.value.isalpha():
                        self.pc += 1
                        continue
            if self.engine.debug_on:
                self.engine.host.debug_pause(self, token)
            try:
                self._execute(token)
            except ScriptError as exc:
                self.engine.last_error = str(exc)
                if self.engine.on_error:
                    self._block(self.engine.on_error)
                    continue
                self.engine.host.error(str(exc))
                self.completed = True
                return True
            return False
        self.completed = True
        return True

    def _execute(self, token) -> None:
        if token.kind == "key":
            self._press_char(token.value)
            return
        raw = token.value
        name = command_name(raw)
        if not name:
            return
        if name.startswith("%"):
            self._play_variable(name)
            return
        body = command_body(raw)
        args = split_args(body) if body.strip() else []
        self.engine.trace.append(f"{name} {body}".strip())
        handler = getattr(self, f"_cmd_{name.lower()}", None)
        if handler is None and name.startswith("SET@"):
            handler = self._cmd_set
        if handler is not None:
            handler(args, raw)
            return
        self._command_key(name)

    # -- tasti -----------------------------------------------------------
    def _press_char(self, char: str) -> None:
        key = _char_key(char)
        self._press(key)

    def _press(self, key: Key) -> None:
        engine = self.engine
        engine.variables.set("%SYS_LAST_KEY", key.name)
        if engine.allowed_keys is not None:
            label = _key_label(key)
            if label not in engine.allowed_keys and key.name not in engine.allowed_keys:
                if engine.allow_else:
                    self._block(engine.allow_else)
                return
        mapping = engine.on_keys.get(_key_label(key)) or engine.on_keys.get(key.name)
        if mapping:
            self._block(mapping)
            return
        if key.name == "ESC" and engine.on_escape:
            self._block(engine.on_escape)
            return
        if self.trigger_mode:
            engine.host.defer_keys(_key_source(key))
            return
        engine.host.press(key)

    def _command_key(self, name: str) -> None:
        if len(name) > 1 and not is_special(name):
            raise ScriptError(f"Unknown script command: {{{name}}}")
        try:
            self._press(parse_key(name))
        except ValueError as exc:
            raise ScriptError(f"Unknown script command: {{{name}}}") from exc

    def _play_variable(self, name: str) -> None:
        variable = name
        if "@" not in variable:
            variable = "%" + variable.lstrip("%")
        content = self.engine.variables.get(variable)
        if not content:
            return
        if self.depth >= MAX_NESTING:
            raise ScriptError("Script nesting is limited to 10 levels.")
        self._block(content)

    def _block(self, source: str) -> None:
        if self.depth >= MAX_NESTING:
            raise ScriptError("Script nesting is limited to 10 levels.")
        runner = ScriptRunner(self.engine, source,
                              name=self.name, trigger_mode=self.trigger_mode,
                              depth=self.depth + 1)
        runner.deferred = self.deferred
        runner.run()

    # -- comandi ---------------------------------------------------------
    def _cmd_abort(self, args: list[str], raw: str) -> None:
        raise ScriptAbort()

    def _cmd_cancel(self, args: list[str], raw: str) -> None:
        raise ScriptCancel()

    def _cmd_endapp(self, args: list[str], raw: str) -> None:
        raise ScriptEndApp()

    def _cmd_mainmenu(self, args: list[str], raw: str) -> None:
        self.engine.host.main_menu()
        if self.engine.on_main:
            self._block(self.engine.on_main)

    def _cmd_toolend(self, args: list[str], raw: str) -> None:
        self.engine.host.tool_end()

    def _cmd_beep(self, args: list[str], raw: str) -> None:
        self.engine.host.beep()

    def _cmd_tone(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        if len(parts) < 2:
            raise ScriptError("TONE needs frequency and duration.")
        frequency = _int(parts[0], "TONE frequency")
        duration = _int(parts[1], "TONE duration")
        if not 100 <= frequency <= 300:
            raise ScriptError("TONE frequency must be between 100 and 300.")
        self.engine.host.tone(frequency, max(1, duration))

    def _cmd_set(self, args: list[str], raw: str) -> None:
        head = command_name(raw)
        if head.startswith("SET@"):
            target = head[3:]
            if len(args) < 1:
                raise ScriptError("SET needs a value.")
            parts = [f"@{target}"] + args
        else:
            parts = split_args(body_of(raw))
        if len(parts) < 2:
            raise ScriptError("SET needs a variable and a value.")
        target = parts[0].strip()
        if target.startswith("@"):
            indirect = self.engine.variables.raw(target[1:])
            if not indirect:
                raise ScriptError(f"Variable {target} is empty.")
            target = indirect
        value = self.engine.value_text(",".join(parts[1:]))
        self.engine.set_variable(target, value)

    def _cmd_clear(self, args: list[str], raw: str) -> None:
        pattern = unquote(body_of(raw).strip()) or "%*"
        self.engine.variables.clear(pattern)

    def _cmd_vsave(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        if len(parts) < 2:
            raise ScriptError("VSAVE needs a variable pattern and a file.")
        pattern = unquote(parts[0]) or "%*"
        filename = self.engine.text(parts[1])
        self.engine.variables.save(self._var_path(filename), pattern)

    def _cmd_vrestore(self, args: list[str], raw: str) -> None:
        filename = self.engine.text(body_of(raw))
        if not filename:
            raise ScriptError("VRESTORE needs a file name.")
        path = self._var_path(filename)
        if not path.is_file():
            raise ScriptError(f"Variable file not found: {path.name}")
        self.engine.variables.load(path)

    def _var_path(self, filename: str) -> Path:
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix(".VAR")
        if not path.is_absolute():
            path = self.engine.store.directory / path
        return path

    def _cmd_goto(self, args: list[str], raw: str) -> None:
        label = self._label(body_of(raw))
        self.pc = self.labels[label]

    def _cmd_loop(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        if len(parts) < 2:
            raise ScriptError("LOOP needs a label and a counter variable.")
        label = self._label(parts[0])
        counter = parts[1].strip()
        try:
            value = int(Decimal(self.engine.variables.get(counter) or "0"))
        except (InvalidOperation, ValueError):
            value = 0
        if value <= 1:
            return
        self.engine.variables.set(counter, str(value - 1))
        self.pc = self.labels[label]

    def _label(self, text: str) -> str:
        value = text.strip().lstrip(":").upper()
        if not value or value not in self.labels:
            raise ScriptError(f"Unknown script label: {text.strip()}")
        return value

    def _cmd_if(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        if len(parts) < 2:
            raise ScriptError("IF needs an expression and a block.")
        selected = block_body(parts[1])
        if not self.engine.condition(parts[0]):
            selected = block_body(parts[2]) if len(parts) > 2 else ""
        if selected:
            self._block(selected)

    def _cmd_case(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        index = 0
        while index + 1 < len(parts):
            if is_block(parts[index]) and index + 1 >= len(parts):
                if not parts[index]:
                    break
                self._block(block_body(parts[index]))
                return
            expression = parts[index]
            block = block_body(parts[index + 1])
            if self.engine.condition(expression):
                self._block(block)
                return
            index += 2
        if index < len(parts) and is_block(parts[index]):
            self._block(block_body(parts[index]))

    def _cmd_allowkeys(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        if not parts:
            self.engine.allowed_keys = None
            self.engine.allow_else = ""
            return
        keys = self.engine.text(parts[0])
        if not keys:
            self.engine.allowed_keys = None
            self.engine.allow_else = ""
            return
        allowed: set[str] = set()
        for item in re.split(r"[\s,]+", keys):
            if not item:
                continue
            allowed.add(item.upper())
            try:
                allowed.add(parse_key(item).name)
            except ValueError:
                pass
        self.engine.allowed_keys = allowed
        self.engine.allow_else = block_body(parts[1]) if len(parts) > 1 else ""

    def _cmd_onkey(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        if len(parts) < 2:
            raise ScriptError("ONKEY needs a key and a block.")
        key_text = unquote(self.engine.variables.expand(parts[0].strip()))
        label = key_text.upper()
        try:
            label = _key_label(parse_key(key_text))
        except ValueError:
            pass
        if len(self.engine.on_keys) >= 64 and label not in self.engine.on_keys:
            raise ScriptError("ONKEY holds at most 64 mappings.")
        self.engine.on_keys[label] = block_body(parts[1])

    def _cmd_onescape(self, args: list[str], raw: str) -> None:
        self.engine.on_escape = block_body(body_of(raw))

    def _cmd_onerror(self, args: list[str], raw: str) -> None:
        self.engine.on_error = block_body(body_of(raw))

    def _cmd_onmain(self, args: list[str], raw: str) -> None:
        self.engine.on_main = block_body(body_of(raw))

    def _cmd_pause(self, args: list[str], raw: str) -> None:
        self.engine.host.pause()

    def _cmd_waitfor(self, args: list[str], raw: str) -> None:
        try:
            seconds = float(Decimal(self.engine.text(body_of(raw)) or "0"))
        except (InvalidOperation, ValueError) as exc:
            raise ScriptError("WAITFOR needs a number of seconds.") from exc
        self.engine.host.wait_for(max(0.0, seconds))

    def _cmd_waitkey(self, args: list[str], raw: str) -> None:
        text = body_of(raw).strip()
        key: Key | None = None
        if text:
            if is_block(text):
                text = block_body(text)
            key = parse_key(text.strip("{}"))
        self.engine.host.wait_key(key)

    def _cmd_waitscrn(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        if len(parts) < 3:
            raise ScriptError("WAITSCRN needs row, column and text.")
        row = _int(parts[0], "WAITSCRN row")
        col = _int(parts[1], "WAITSCRN column")
        if not self.engine.host.wait_screen(row, col, self.engine.text(parts[2])):
            raise ScriptError("WAITSCRN: the expected text did not appear.")

    def _cmd_waituntil(self, args: list[str], raw: str) -> None:
        moment = self.engine.text(body_of(raw))
        if not self.engine.host.wait_until(moment):
            raise ScriptError(f"WAITUNTIL: time {moment} not reached.")

    def _cmd_write(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        if len(parts) < 3:
            raise ScriptError("WRITE needs row, column and text.")
        self.engine.host.write(_int(parts[0], "WRITE row"),
                               _int(parts[1], "WRITE column"),
                               self.engine.text(",".join(parts[2:])))

    def _cmd_read(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        if len(parts) < 4:
            raise ScriptError("READ needs variable, row, column and length.")
        value = self.engine.host.read_screen(
            _int(parts[1], "READ row"), _int(parts[2], "READ column"),
            _int(parts[3], "READ length"))
        self.engine.set_variable(parts[0], value)

    def _cmd_prompt(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        if len(parts) < 2:
            raise ScriptError("PROMPT needs a label and a variable.")
        length = _int(parts[2], "PROMPT length") if len(parts) > 2 else 20
        label = self.engine.text(parts[0])
        value = self.engine.host.prompt(label, length)
        if value is None:
            raise ScriptCancel()
        self.engine.set_variable(parts[1].strip(), value)

    def _cmd_show(self, args: list[str], raw: str) -> None:
        name = self.engine.text(body_of(raw))
        if not name:
            raise ScriptError("SHOW needs a dialog box name.")
        self.engine.host.show_dialog(name, modal=False)

    def _cmd_screenfreeze(self, args: list[str], raw: str) -> None:
        self.engine.host.screen_mode("freeze")

    def _cmd_screenoff(self, args: list[str], raw: str) -> None:
        self.engine.host.screen_mode("off")

    def _cmd_screenon(self, args: list[str], raw: str) -> None:
        self.engine.host.screen_mode("on")

    def _cmd_noclear(self, args: list[str], raw: str) -> None:
        self.engine.host.screen_mode("noclear")

    def _cmd_debugon(self, args: list[str], raw: str) -> None:
        self.engine.debug_on = True

    def _cmd_debugoff(self, args: list[str], raw: str) -> None:
        self.engine.debug_on = False

    def _cmd_play(self, args: list[str], raw: str) -> None:
        text = body_of(raw).strip()
        name = self.engine.variables.expand(text)
        if is_block(name):
            name = block_body(name)
        name = unquote(name).strip()
        if not name:
            raise ScriptError("PLAY needs a script name.")
        if not self.engine.play(name):
            raise ScriptCancel()

    def _cmd_trigkeys(self, args: list[str], raw: str) -> None:
        self.deferred = True
        keys = self.engine.variables.expand(body_of(raw))
        self.engine.host.defer_keys(unquote(keys))

    def _cmd_mousedclick(self, args: list[str], raw: str) -> None:
        self._mouse("dclick", args)

    def _cmd_mousedown(self, args: list[str], raw: str) -> None:
        self._mouse("down", args)

    def _cmd_mousemove(self, args: list[str], raw: str) -> None:
        self._mouse("move", args)

    def _cmd_mouseup(self, args: list[str], raw: str) -> None:
        self._mouse("up", args)

    def _mouse(self, action: str, args: list[str]) -> None:
        parts = split_args(",".join(args))
        row = _int(parts[0], "mouse row") if parts and parts[0] else 0
        col = _int(parts[1], "mouse column") if len(parts) > 1 and parts[1] else 0
        self.engine.host.mouse(action, row, col)

    def _cmd_exec(self, args: list[str], raw: str) -> None:
        self._exec(args, clear=False)

    def _cmd_execclr(self, args: list[str], raw: str) -> None:
        self._exec(args, clear=True)

    def _exec(self, args: list[str], *, clear: bool) -> None:
        parts = split_args(",".join(args))
        if not parts:
            raise ScriptError("EXEC needs a program name.")
        program = self.engine.text(parts[0])
        parameter = self.engine.text(parts[1]) if len(parts) > 1 else ""
        memory = _int(parts[2], "EXEC memory") if len(parts) > 2 else 0
        self.engine.host.external(program, parameter, memory, clear=clear)

    def _cmd_rpl(self, args: list[str], raw: str) -> None:
        parts = split_args(body_of(raw))
        if len(parts) < 4:
            raise ScriptError("RPL needs code, parameter, result and error.")
        code = _int(parts[0], "RPL code")
        result, error = self.engine.host.rpl(code, self.engine.text(parts[1]))
        self.engine.set_variable(parts[2], result)
        self.engine.set_variable(parts[3], error)

    def _cmd_xlookup(self, args: list[str], raw: str) -> None:
        self._lookup("exact", body_of(raw))

    def _cmd_xlookupc(self, args: list[str], raw: str) -> None:
        self._lookup("closest", body_of(raw))

    def _cmd_xlookupr(self, args: list[str], raw: str) -> None:
        self._lookup("record", body_of(raw))

    def _lookup(self, mode: str, body: str) -> None:
        parts = split_args(body)
        minimum = 3 if mode == "record" else 4
        if len(parts) < minimum:
            raise ScriptError("XLOOKUP needs database, index, key and variable.")
        database = self.engine.text(parts[0])
        if mode == "record":
            index = ""
            key = self.engine.variables.expand(unquote(parts[1]))
            status_var = parts[2].strip()
        else:
            index = self.engine.text(parts[1])
            key = self.engine.variables.expand(unquote(parts[2]))
            status_var = parts[3].strip()
        if mode == "record":
            try:
                record = int(Decimal(key or "0"))
            except (InvalidOperation, ValueError):
                record = 0
            result = self.engine.host.lookup_record(database, record)
        else:
            result = self.engine.host.lookup(mode, database, index, key)
        if not result:
            self.engine.set_variable(status_var, "218")
            raise ScriptError("XLOOKUP: no record found.")
        for field_name, value in result.items():
            self.engine.variables.set(f"%{database.upper()}_{field_name.upper()}",
                                      value)
        self.engine.set_variable(status_var, "0")


def body_of(raw: str) -> str:
    name = command_name(raw)
    return raw.strip()[len(name):].lstrip(" ,")


def _labels(tokens) -> dict[str, int]:
    labels: dict[str, int] = {}
    index = 0
    while index + 1 < len(tokens):
        token = tokens[index]
        if token.kind == "key" and token.value == ":":
            following = tokens[index + 1]
            if following.kind == "key" and following.value.isalpha():
                labels[following.value.upper()] = index + 2
                index += 2
                continue
        index += 1
    return labels


def char_key(char: str) -> Key:
    if char == " ":
        return Key("SPACE")
    if char.isalpha():
        return Key(char.upper(), shift=char.isupper())
    if char.isdigit():
        return Key(char)
    name = _KEY_CHARS.get(char)
    if name is None:
        return Key(char)
    return Key(name)


def keys_from_source(text: str) -> list[Key]:
    """Converte una sequenza registrata (`AB{F10}`) in tasti."""
    keys: list[Key] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "{":
            end = text.find("}", index + 1)
            if end < 0:
                break
            try:
                keys.append(parse_key(text[index + 1:end]))
            except ValueError:
                pass
            index = end + 1
            continue
        if char in "\r\n\t":
            index += 1
            continue
        keys.append(char_key(char))
        index += 1
    return keys


def _char_key(char: str) -> Key:
    return char_key(char)


def _key_label(key: Key) -> str:
    parts = []
    if key.ctrl:
        parts.append("CTRL")
    if key.alt:
        parts.append("ALT")
    if key.shift:
        parts.append("SHIFT")
    parts.append(key.name)
    return "-".join(parts)


def _key_source(key: Key) -> str:
    label = _key_label(key)
    if label == "SPACE":
        return " "
    if len(key.name) == 1 and not (key.ctrl or key.alt or key.shift):
        return key.name
    return "{" + label + "}"


def _int(text: str, label: str) -> int:
    try:
        return int(Decimal(unquote(text.strip()) or "0"))
    except (InvalidOperation, ValueError) as exc:
        raise ScriptError(f"{label} must be a number.") from exc


__all__ = [
    "MAX_NESTING", "ScriptAbort", "ScriptCancel", "ScriptEndApp",
    "ScriptEngine", "ScriptError", "ScriptHalt", "ScriptHost", "ScriptRunner",
    "body_of", "char_key", "keys_from_source",
]
