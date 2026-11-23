"""Host del motore di script per il guscio Qt/headless.

Il playback dei tasti passa da `ShellController.handle`: è lo stesso percorso
dell'input reale, come richiesto dal piano. Le altre primitive usano il
workspace per XLOOKUP, l'eventuale applicazione Qt per i prompt e il
controller per schermo, menu e trigger differiti.
"""

from __future__ import annotations

from ..data.expressions import Context
from ..data.indexing import find_index, index_key
from ..screen.keys import Key
from ..script.engine import ScriptError, ScriptHost


class ShellScriptHost(ScriptHost):
    def __init__(self, controller) -> None:
        self.controller = controller

    # -- schermo e tastiera ---------------------------------------------
    def press(self, key: Key) -> None:
        self.controller.handle(key)

    def cursor(self) -> tuple[int, int]:
        return self.controller.script_cursor

    def screen_lines(self) -> list[str]:
        return self.controller.view().buffer.to_lines()

    def write(self, row: int, col: int, text: str) -> None:
        self.controller.script_writes.append((row, col, text))

    def beep(self) -> None:
        self.controller.script_beeps += 1

    def tone(self, frequency: int, duration: int) -> None:
        self.controller.script_tones.append((frequency, duration))

    def pause(self) -> None:
        self.controller.script_pauses += 1

    def wait_for(self, seconds: float) -> None:
        self.controller.script_waits.append(("for", seconds))

    def wait_key(self, key: Key | None) -> Key | None:
        self.controller.script_waits.append(("key", key))
        return key

    def wait_screen(self, row: int, col: int, text: str) -> bool:
        lines = self.screen_lines()
        if 1 <= row <= len(lines):
            return text.upper() in lines[row - 1][max(0, col - 1):].upper()
        return False

    def wait_until(self, moment: str) -> bool:
        self.controller.script_waits.append(("until", moment))
        return True

    def screen_mode(self, mode: str) -> None:
        self.controller.script_set_screen_mode(mode)

    def prompt(self, label: str, length: int, default: str = "",
               secret: bool = False) -> str | None:
        return self.controller.script_prompt(label, length, default,
                                             secret=secret)

    def show_dialog(self, name: str, *, modal: bool = True) -> dict[str, str] | None:
        return self.controller.script_show_dialog(name, modal=modal)

    def field_context(self) -> Context | None:
        return self.controller.script_context()

    # -- database --------------------------------------------------------
    def _database(self, name: str):
        workspace = self.controller.workspace
        if workspace is None and self.controller.database is not None:
            workspace = self.controller.database.workspace
        if workspace is None:
            return None
        return workspace.get(name.upper())

    def lookup(self, kind: str, database: str, index: str,
               key: str) -> dict[str, str] | None:
        db = self._database(database)
        if db is None:
            raise ScriptError(f"XLOOKUP: database {database} not found.")
        definition = find_index(db, index.upper())
        if definition is None:
            raise ScriptError(f"XLOOKUP: index {index} not found.")
        needle = key if definition.case_sensitive else key.upper()
        best = None
        for seq in db.sequences():
            values = db.read(seq)
            candidate = index_key(db, definition, values, seq=seq)
            marker = candidate if definition.case_sensitive else candidate.upper()
            if kind == "closest":
                if marker >= needle:
                    best = values
                    break
            elif marker == needle:
                return values
            elif marker < needle:
                best = values
        return best

    def lookup_record(self, database: str, record: int) -> dict[str, str] | None:
        db = self._database(database)
        if db is None:
            raise ScriptError(f"XLOOKUP: database {database} not found.")
        seqs = db.sequences(include_deleted=True)
        if not 1 <= record <= len(seqs):
            return None
        return db.read(seqs[record - 1])

    # -- sistema ---------------------------------------------------------
    def external(self, program: str, parameter_database: str,
                 minimum_memory: int, *, clear: bool) -> int:
        raise ScriptError(
            "EXEC/EXECCLR non sono disponibili: adbx non esegue programmi "
            "DOS esterni.")

    def mouse(self, action: str, row: int = 0, col: int = 0) -> None:
        self.controller.script_mouse.append((action, row, col))
        if action == "dclick" and row and col:
            self.controller.click(row - 1, col - 1, double=True)

    def main_menu(self) -> None:
        self.controller.script_main_menu()

    def tool_end(self) -> None:
        self.controller.script_tool_end()

    def end_app(self) -> None:
        self.controller.script_end_app()

    def defer_keys(self, keys: str) -> None:
        self.controller.script_deferred.append(keys)

    def debug_pause(self, runner, token) -> None:
        self.controller.script_debug_pause(runner, token)

    def error(self, message: str) -> None:
        self.controller.script_error(message)

    def rpl(self, code: int, parameter: str) -> tuple[str, str]:
        raise ScriptError("RPL routines are not available in adbx.")


__all__ = ["ShellScriptHost"]
