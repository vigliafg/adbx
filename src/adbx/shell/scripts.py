"""Schermate degli script: editor, dialog designer, menu bar e debugger.

L'editor lavora su una lista di righe, come il letter editor: il cursore è
una cella della griglia e ogni carattere è una cella. Il dialog designer e il
menu bar designer usano la stessa griglia con celle modificabili, secondo
l'invariante dei designer di `PLAN.md` §3.8.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW, Cell, CellBuffer
from ..screen.keys import Key, character
from ..script.engine import ScriptRunner
from ..script.model import (
    CONTROL_BUTTON,
    CONTROL_DISPLAY,
    CONTROL_PROMPT,
    DialogBox,
    DialogControl,
    MenuBarScript,
    MenuItem,
    ScreenTest,
    Script,
)
from ..script.store import ScriptStore
from .dialogs import Picker, picker_view
from .theme import NEWPORT, Theme
from .widgets import (
    View,
    blit,
    clip_text,
    draw_help_line,
    draw_menu_line,
    draw_status_line,
    title_bar,
    window,
)

CONTENT_TOP = 5
EDITOR_KEYS = [("F1", "Help"), ("F2", "Cmds"), ("F3", "Learn"),
               ("F4", "Append"), ("F5", "Screen test"), ("F6", "Mark area"),
               ("F10", "Save")]
DESIGN_KEYS = [("F1", "Help"), ("F2", "Prompt"), ("F3", "Button"),
               ("F4", "Display"), ("F5", "Delete"), ("F10", "Save")]
MENU_KEYS = [("F1", "Help"), ("F2", "Add item"), ("F5", "Delete"),
             ("F10", "Save")]

COMMANDS = [
    ("ABORT", "{ABORT}"), ("ALLOWKEYS", '{ALLOWKEYS "",{}}'),
    ("BEEP", "{BEEP}"), ("CANCEL", "{CANCEL}"),
    ("CASE", "{CASE ,{}}"), ("CLEAR", '{CLEAR "%*"}'),
    ("DEBUGOFF", "{DEBUGOFF}"), ("DEBUGON", "{DEBUGON}"),
    ("ENDAPP", "{ENDAPP}"), ("EXEC", '{EXEC ""}'),
    ("EXECCLR", '{EXECCLR ""}'), ("GOTO", "{GOTO :A}"),
    ("IF", "{IF ,{},{}}"), ("LOOP", "{LOOP :A,%N}"),
    ("MAINMENU", "{MAINMENU}"), ("MOUSEDCLICK", "{MOUSEDCLICK 1,1}"),
    ("MOUSEDOWN", "{MOUSEDOWN}"), ("MOUSEMOVE", "{MOUSEMOVE 1,1}"),
    ("MOUSEUP", "{MOUSEUP}"), ("NOCLEAR", "{NOCLEAR}"),
    ("ONERROR", "{ONERROR {}}"), ("ONESCAPE", "{ONESCAPE {}}"),
    ("ONKEY", '{ONKEY "",{}}'), ("ONMAIN", "{ONMAIN {}}"),
    ("PAUSE", "{PAUSE}"), ("PLAY", '{PLAY ""}'),
    ("PROMPT", '{PROMPT "",%VAR,20}'), ("READ", "{READ %VAR,1,1,10}"),
    ("RPL", "{RPL 1,\"\",%R,%E}"), ("SCREENFREEZE", "{SCREENFREEZE}"),
    ("SCREENOFF", "{SCREENOFF}"), ("SCREENON", "{SCREENON}"),
    ("SET", '{SET %VAR,""}'), ("SHOW", '{SHOW ""}'),
    ("TONE", "{TONE 160,40}"), ("TOOLEND", "{TOOLEND}"),
    ("TRIGKEYS", '{TRIGKEYS ""}'), ("VRESTORE", '{VRESTORE ""}'),
    ("VSAVE", '{VSAVE "%*",""}'), ("WAITFOR", "{WAITFOR 1}"),
    ("WAITKEY", "{WAITKEY}"), ("WAITSCRN", '{WAITSCRN 1,1,""}'),
    ("WAITUNTIL", "{WAITUNTIL 10:00}"), ("WRITE", '{WRITE 1,1,""}'),
    ("XLOOKUP", '{XLOOKUP "","","",%STATUS}'),
    ("XLOOKUPC", '{XLOOKUPC "","","",%STATUS}'),
    ("XLOOKUPR", '{XLOOKUPR "",1,%STATUS}'),
]


@dataclass
class ScriptEditor:
    """Editor della sequenza di tasti e comandi."""

    store: ScriptStore
    script: Script
    theme: Theme = NEWPORT
    lines: list[str] = field(default_factory=list)
    row: int = 0
    col: int = 0
    top: int = 0
    status: str = ""
    close: bool = False
    saved: bool = False
    learn_request: bool = False
    append_request: bool = False
    picker: Picker | None = None
    picker_kind: str = ""
    stage: str = "edit"
    prompt_text: str = ""
    capture_lines: list[str] = field(default_factory=list)
    help_topic: str = "scripts"

    def __post_init__(self) -> None:
        self.lines = self.script.source.split("\n") or [""]
        if len(self.lines) == 1 and not self.lines[0]:
            self.lines = [""]

    @property
    def title(self) -> str:
        return f"Script Editor - {self.script.name}"

    @property
    def source(self) -> str:
        return "\n".join(self.lines)

    # -- input -----------------------------------------------------------
    def handle(self, key: Key) -> None:
        self.status = ""
        if self.picker is not None:
            self._handle_picker(key)
            return
        if self.stage == "screen-test":
            self._handle_screen_test(key)
            return
        if self.stage == "description":
            self._handle_description(key)
            return
        name = key.name
        if name == "F1":
            return
        if name == "F2":
            self.picker = Picker(
                "Script Commands", [label for label, _template in COMMANDS],
                [template for _label, template in COMMANDS],
                footer="ENTER select   ESC cancel")
            self.picker_kind = "commands"
            return
        if name == "F3":
            self.learn_request = True
            return
        if name == "F4":
            self.append_request = True
            return
        if name == "F5":
            self.stage = "screen-test"
            self.prompt_text = " | ".join(self.script.screen_test.lines)
            return
        if name == "F6":
            self._mark_area()
            return
        if name == "F7":
            self.stage = "description"
            self.prompt_text = self.script.description
            return
        if name == "F8":
            self.status = "Detail is always on: one cell per character."
            return
        if name == "F10":
            self._save()
            return
        if name == "ESC":
            self.close = True
            return
        if name == "UP":
            self._move_row(-1)
            return
        if name == "DOWN":
            self._move_row(1)
            return
        if name == "LEFT":
            if self.col:
                self.col -= 1
            elif self.row:
                self.row -= 1
                self.col = len(self.lines[self.row])
            self._scroll()
            return
        if name == "RIGHT":
            if self.col < len(self.lines[self.row]):
                self.col += 1
            elif self.row + 1 < len(self.lines):
                self.row += 1
                self.col = 0
            self._scroll()
            return
        if name == "HOME":
            self.col = 0
            return
        if name == "END":
            self.col = len(self.lines[self.row])
            return
        if name == "PGUP":
            self._move_row(-22)
            return
        if name == "PGDN":
            self._move_row(22)
            return
        if name == "ENTER":
            line = self.lines[self.row]
            self.lines[self.row] = line[:self.col]
            self.lines.insert(self.row + 1, line[self.col:])
            self.row += 1
            self.col = 0
            self._scroll()
            return
        if name == "BACKSPACE":
            line = self.lines[self.row]
            if self.col:
                self.lines[self.row] = line[:self.col - 1] + line[self.col:]
                self.col -= 1
            elif self.row:
                previous = self.lines[self.row - 1]
                self.lines[self.row - 1] = previous + line
                self.lines.pop(self.row)
                self.row -= 1
                self.col = len(previous)
            self._scroll()
            return
        if name == "DELETE":
            line = self.lines[self.row]
            if self.col < len(line):
                self.lines[self.row] = line[:self.col] + line[self.col + 1:]
            elif self.row + 1 < len(self.lines):
                self.lines[self.row] = line + self.lines[self.row + 1]
                self.lines.pop(self.row + 1)
            return
        if name == "TAB":
            self._insert("\t")
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self._insert(text)

    def _insert(self, text: str) -> None:
        line = self.lines[self.row]
        self.lines[self.row] = line[:self.col] + text + line[self.col:]
        self.col += len(text)
        self._scroll()

    def _move_row(self, delta: int) -> None:
        self.row = max(0, min(self.row + delta, len(self.lines) - 1))
        self.col = min(self.col, len(self.lines[self.row]))
        self._scroll()

    def _scroll(self) -> None:
        visible = STATUS_ROW - CONTENT_TOP - 1
        if self.row < self.top:
            self.top = self.row
        elif self.row >= self.top + visible:
            self.top = self.row - visible + 1

    # -- comandi ---------------------------------------------------------
    def _handle_picker(self, key: Key) -> None:
        picker = self.picker
        assert picker is not None
        if key.name == "UP":
            picker.move(-1)
        elif key.name == "DOWN":
            picker.move(1)
        elif key.name == "PGUP":
            picker.move(-10)
        elif key.name == "PGDN":
            picker.move(10)
        elif key.name == "ESC":
            self.picker = None
        elif key.name == "ENTER":
            template = picker.value()
            self.picker = None
            if template:
                self._insert_block(template)

    def _insert_block(self, text: str) -> None:
        self._insert(text)

    def _handle_screen_test(self, key: Key) -> None:
        if key.name == "ENTER":
            text = self.prompt_text
            lines = [line.strip() for line in text.replace("|", "\n").split("\n")]
            self.script.screen_test = ScreenTest(
                lines=[line for line in lines if line])
            self.stage = "edit"
            self.status = ("Screen test set." if self.script.screen_test.enabled
                           else "Screen test disabled.")
            return
        if key.name == "ESC":
            self.stage = "edit"
            return
        if key.name == "BACKSPACE":
            self.prompt_text = self.prompt_text[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self.prompt_text += text

    def _handle_description(self, key: Key) -> None:
        if key.name == "ENTER":
            self.script.description = self.prompt_text[:80]
            self.stage = "edit"
            return
        if key.name == "ESC":
            self.stage = "edit"
            return
        if key.name == "BACKSPACE":
            self.prompt_text = self.prompt_text[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self.prompt_text += text

    def _mark_area(self) -> None:
        if self.capture_lines:
            lines = [line.rstrip() for line in self.capture_lines if line.strip()]
            self.script.screen_test = ScreenTest(lines=lines)
            self.status = f"Screen area marked: {len(lines)} line(s)."
        else:
            self.status = "No screen to mark."

    def _save(self) -> bool:
        try:
            self.script.source = self.source
            self.store.save(self.script)
        except Exception as exc:  # ScriptError, OSError
            self.status = str(exc)
            return False
        self.saved = True
        self.status = f"Script {self.script.name} saved."
        return True

    # -- disegno ---------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        buffer.write(1, 1, f"Description: {self.script.description}",
                     fg=self.theme.label, bg=self.theme.bg)
        test = ("Yes" if self.script.has_screen_test else "No")
        buffer.write(2, 1, f"Screen test: {test}",
                     fg=self.theme.label, bg=self.theme.bg)
        buffer.write(3, 1, "Keys/Commands:", fg=self.theme.accent,
                     bg=self.theme.bg, bold=True)
        visible = STATUS_ROW - CONTENT_TOP - 1
        for offset in range(visible):
            index = self.top + offset
            if index >= len(self.lines):
                break
            row = CONTENT_TOP + offset
            number = f"{index + 1:>3}"
            buffer.write(row, 0, number, fg=self.theme.label, bg=self.theme.bg)
            text = self.lines[index].replace("\\t", "\t")
            buffer.write(row, 4, clip_text(text, SCREEN_WIDTH - 6),
                         fg=self.theme.text, bg=self.theme.bg)
        if self.stage == "edit":
            row = CONTENT_TOP + self.row - self.top
            if 0 <= row < STATUS_ROW:
                col = min(4 + self.col, SCREEN_WIDTH - 1)
                cell = buffer.get(row, col)
                buffer.put(row, col, Cell(cell.ch, fg=cell.bg, bg=cell.fg))
        elif self.stage in ("screen-test", "description"):
            label = ("Screen test (separate lines with |):"
                     if self.stage == "screen-test" else "Description:")
            buffer.write(STATUS_ROW - 2, 1, label, fg=self.theme.accent,
                         bg=self.theme.bg, bold=True)
            buffer.write(STATUS_ROW - 1, 1, clip_text(self.prompt_text,
                                                      SCREEN_WIDTH - 2),
                         fg=self.theme.submenu_fg, bg=self.theme.selected_bg)
        draw_status_line(buffer, self.theme,
                         self.status or f"Line {self.row + 1}, Col {self.col + 1}")
        draw_help_line(buffer, self.theme,
                       "Keys are typed literally; commands use curly braces.")
        regions = draw_menu_line(buffer, self.theme, EDITOR_KEYS)
        if self.picker is not None:
            panel = picker_view(self.picker, self.theme)
            row = max(1, (SCREEN_HEIGHT - panel.height) // 2 - 2)
            col = max(1, (SCREEN_WIDTH - panel.width) // 2)
            blit(buffer, panel, row, col)
        return View(buffer, regions)


# Debugger: sorgente a sinistra, variabili a destra (griglia 80 colonne).
SOURCE_WIDTH = 48
SOURCE_COLUMNS = 50          # colonna della separatrice verticale
VARIABLES_COL = 53


@dataclass
class DialogDesigner:
    """Designer a celle di un dialog box."""

    store: ScriptStore
    script: Script
    theme: Theme = NEWPORT
    dialog: DialogBox = field(default_factory=DialogBox)
    focus: str = "settings"
    setting: int = 0
    control: int = 0
    column: int = 1
    edit_text: str = ""
    edit_cursor: int = 0
    status: str = ""
    close: bool = False
    saved: bool = False
    help_topic: str = "scripts"

    def __post_init__(self) -> None:
        if self.script.dialog is None:
            self.script.dialog = DialogBox(title=self.script.name)
        self.dialog = self.script.dialog
        self._load()

    @property
    def title(self) -> str:
        return f"Dialog Box Designer - {self.script.name}"

    SETTINGS = ("Title", "Row", "Col", "Height", "Width", "Foreground",
                "Background", "Shadow", "No clear")

    def values(self) -> tuple:
        return (self.dialog.title, self.dialog.row, self.dialog.col,
                self.dialog.height, self.dialog.width,
                self.dialog.foreground, self.dialog.background,
                "Yes" if self.dialog.shadow else "No",
                "Yes" if self.dialog.no_clear else "No")

    def _load(self) -> None:
        self.setting = max(0, min(self.setting, len(self.SETTINGS) - 1))
        self.control = max(0, min(self.control,
                                  max(0, len(self.dialog.controls) - 1)))
        if self.focus == "settings":
            self.edit_text = str(self.values()[self.setting])
        else:
            self.edit_text = self.control_text(self.control, self.column)
            self.edit_cursor = len(self.edit_text)

    def control_text(self, index: int, column: int) -> str:
        if not (0 <= index < len(self.dialog.controls)):
            return ""
        control = self.dialog.controls[index]
        values = (control.kind, control.row, control.col, control.width,
                  control.variable or control.label, control.action)
        return str(values[column]) if 0 <= column < len(values) else ""

    def handle(self, key: Key) -> None:
        self.status = ""
        name = key.name
        if name == "F1":
            return
        if name == "F2":
            self._add(CONTROL_PROMPT)
            return
        if name == "F3":
            self._add(CONTROL_BUTTON)
            return
        if name == "F4":
            self._add(CONTROL_DISPLAY)
            return
        if name == "F5":
            self.dialog.remove(self.control)
            self.control = max(0, min(self.control,
                                      len(self.dialog.controls) - 1))
            self._load()
            return
        if name == "F10":
            self._save()
            return
        if name == "ESC":
            self.close = True
            return
        if name == "TAB":
            self.focus = "controls" if self.focus == "settings" else "settings"
            self._load()
            return
        if name == "UP":
            if self.focus == "settings":
                self.setting = max(0, self.setting - 1)
            else:
                self.control = max(0, self.control - 1)
            self._load()
            return
        if name == "DOWN":
            if self.focus == "settings":
                self.setting = min(len(self.SETTINGS) - 1, self.setting + 1)
            else:
                self.control = min(max(0, len(self.dialog.controls) - 1),
                                   self.control + 1)
            self._load()
            return
        if name == "LEFT":
            if self.focus == "controls":
                self.column = max(0, self.column - 1)
                self._load()
            return
        if name == "RIGHT":
            if self.focus == "controls":
                self.column = min(5, self.column + 1)
                self._load()
            return
        if name == "ENTER":
            self._commit()
            return
        if name == "BACKSPACE":
            self.edit_text = self.edit_text[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self.edit_text += text

    def _commit(self) -> None:
        value = self.edit_text
        if self.focus == "settings":
            try:
                self._apply_setting(self.setting, value)
            except ValueError:
                self.status = "Enter a valid value."
                return
        else:
            control = self.dialog.controls[self.control]
            if self.column == 0:
                upper = value.strip().title()
                if upper not in (CONTROL_PROMPT, CONTROL_BUTTON,
                                 CONTROL_DISPLAY):
                    self.status = "Control type: Prompt, Button or Display."
                    return
                control.kind = upper
            elif self.column in (1, 2, 3):
                try:
                    number = int(value or "1")
                except ValueError:
                    self.status = "Enter a number."
                    return
                if self.column == 1:
                    control.row = number
                elif self.column == 2:
                    control.col = number
                else:
                    control.width = number
            elif self.column == 4:
                if control.kind == CONTROL_DISPLAY:
                    control.variable = value
                elif control.kind == CONTROL_BUTTON:
                    control.label = value
                else:
                    control.variable = value
            else:
                control.action = value
            self.dialog._fit(control)
        self._load()

    def _apply_setting(self, index: int, value: str) -> None:
        dialog = self.dialog
        if index == 0:
            dialog.title = value[:70]
        elif index == 1:
            dialog.row = int(value)
        elif index == 2:
            dialog.col = int(value)
        elif index == 3:
            dialog.height = int(value)
        elif index == 4:
            dialog.width = int(value)
        elif index == 5:
            dialog.foreground = int(value)
        elif index == 6:
            dialog.background = int(value)
        elif index == 7:
            dialog.shadow = _yes(value)
        elif index == 8:
            dialog.no_clear = _yes(value)
        DialogBox.__post_init__(dialog)

    def _add(self, kind: str) -> None:
        control = DialogControl(kind=kind, row=min(3, self.dialog.height - 2),
                                col=2, width=min(20, self.dialog.width - 4))
        if kind == CONTROL_PROMPT:
            control.label = "Prompt:"
            control.variable = "%VALUE"
        elif kind == CONTROL_BUTTON:
            control.label = "OK"
            control.action = "{ENTER}"
        else:
            control.variable = "%VALUE"
        try:
            self.dialog.add(control)
        except Exception as exc:
            self.status = str(exc)
            return
        self.focus = "controls"
        self.control = len(self.dialog.controls) - 1
        self.column = 4 if kind != CONTROL_BUTTON else 4
        self._load()

    def _save(self) -> bool:
        self.script.dialog = self.dialog
        try:
            self.store.save(self.script)
        except Exception as exc:
            self.status = str(exc)
            return False
        self.saved = True
        self.status = f"Dialog box {self.script.name} saved."
        return True

    CONTROL_COLUMNS = ((1, 8), (10, 3), (14, 3), (18, 5), (24, 27), (52, 26))

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        for index, label in enumerate(self.SETTINGS):
            row = 1 + index
            active = self.focus == "settings" and index == self.setting
            buffer.write(row, 1, f"{label:<12}:", fg=self.theme.accent
                         if active else self.theme.label, bg=self.theme.bg,
                         bold=active)
            text = str(self.values()[index])
            if active and self.edit_text != text:
                text = self.edit_text
            buffer.write(row, 15, clip_text(text, 12),
                         fg=self.theme.selected_fg if active else self.theme.text,
                         bg=self.theme.selected_bg if active else self.theme.bg)
        buffer.write(11, 1, "Controls", fg=self.theme.accent, bg=self.theme.bg,
                     bold=True)
        headers = ("Type", "Row", "Col", "Width", "Variable/Label", "Action")
        for (x, width), header in zip(self.CONTROL_COLUMNS, headers):
            buffer.write(12, x, clip_text(header, width),
                         fg=self.theme.label, bg=self.theme.bg)
        for index, control in enumerate(self.dialog.controls):
            row = 13 + index
            if row >= 21:
                break
            active = self.focus == "controls" and index == self.control
            values = (control.kind, control.row, control.col, control.width,
                      control.variable or control.label, control.action)
            for col, ((x, width), text) in enumerate(
                    zip(self.CONTROL_COLUMNS, values)):
                if active and col == self.column:
                    if self.edit_text != str(text):
                        text = self.edit_text
                    fg, bg = self.theme.selected_fg, self.theme.selected_bg
                else:
                    fg, bg = self.theme.text, self.theme.bg
                buffer.write(row, x, clip_text(str(text), width), fg=fg, bg=bg)
        preview = window(max(12, min(self.dialog.width, 48)),
                         max(4, min(self.dialog.height, 10)),
                         self.dialog.title or self.script.name, self.theme)
        for control in self.dialog.controls:
            row = min(control.row, preview.height - 2)
            col = min(control.col, preview.width - 2)
            text = (control.label if control.kind == CONTROL_BUTTON
                    else control.variable or control.label)
            if control.kind == CONTROL_PROMPT:
                text = f"{control.label} {text}"
            preview.write(row, col, clip_text(text, control.width),
                          fg=self.theme.window_fg, bg=self.theme.window_bg)
        blit(buffer, preview, 1, 30)
        draw_status_line(buffer, self.theme, self.status or
                         "TAB switch pane   ENTER edit   F2/F3/F4 add")
        draw_help_line(buffer, self.theme,
                       "A dialog box can hold Prompts, Buttons and Displays.")
        regions = draw_menu_line(buffer, self.theme, DESIGN_KEYS)
        return View(buffer, regions)


@dataclass
class MenuBarDesigner:
    """Editor delle voci di un menu bar personalizzato."""

    store: ScriptStore
    script: Script
    theme: Theme = NEWPORT
    menu: MenuBarScript = field(default_factory=MenuBarScript)
    row: int = 0
    column: int = 0
    edit_text: str = ""
    status: str = ""
    close: bool = False
    saved: bool = False
    help_topic: str = "scripts"

    def __post_init__(self) -> None:
        if self.script.menu is None:
            self.script.menu = MenuBarScript()
        self.menu = self.script.menu
        self._load()

    @property
    def title(self) -> str:
        return f"Menu Bar Designer - {self.script.name}"

    COLUMNS = ("Key", "Label", "Action")

    def _load(self) -> None:
        if self.menu.items:
            self.row = max(0, min(self.row, len(self.menu.items) - 1))
            values = (self.menu.items[self.row].key,
                      self.menu.items[self.row].label,
                      self.menu.items[self.row].action)
            self.edit_text = values[self.column]
        else:
            self.row = 0
            self.edit_text = ""

    def handle(self, key: Key) -> None:
        self.status = ""
        name = key.name
        if name == "F1":
            return
        if name == "F2":
            self.menu.add(MenuItem(f"F{len(self.menu.items) + 1}",
                                   "New choice", "{ENTER}"))
            self.row = len(self.menu.items) - 1
            self.column = 1
            self._load()
            return
        if name == "F5":
            if self.menu.items:
                self.menu.items.pop(self.row)
            self._load()
            return
        if name == "F10":
            self._save()
            return
        if name == "ESC":
            self.close = True
            return
        if name == "UP":
            self.row = max(0, self.row - 1)
            self._load()
            return
        if name == "DOWN":
            self.row = min(max(0, len(self.menu.items) - 1), self.row + 1)
            self._load()
            return
        if name == "LEFT":
            self.column = max(0, self.column - 1)
            self._load()
            return
        if name == "RIGHT":
            self.column = min(2, self.column + 1)
            self._load()
            return
        if name == "ENTER":
            self._commit()
            return
        if name == "BACKSPACE":
            self.edit_text = self.edit_text[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self.edit_text += text

    def _commit(self) -> None:
        if not self.menu.items:
            return
        item = self.menu.items[self.row]
        if self.column == 0:
            item.key = (self.edit_text.strip().upper() or item.key)[:12]
        elif self.column == 1:
            item.label = self.edit_text[:40] or item.label
        else:
            item.action = self.edit_text
        self._load()

    def _save(self) -> bool:
        self.script.menu = self.menu
        try:
            self.store.save(self.script)
        except Exception as exc:
            self.status = str(exc)
            return False
        self.saved = True
        self.status = f"Menu bar {self.script.name} saved."
        return True

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        for col, header in enumerate(self.COLUMNS):
            buffer.write(1, 2 + col * 20, header, fg=self.theme.accent,
                         bg=self.theme.bg, bold=True)
        for index, item in enumerate(self.menu.items):
            row = 2 + index
            if row >= 20:
                break
            values = (item.key, item.label, item.action)
            for col, text in enumerate(values):
                active = index == self.row and col == self.column
                if active and self.edit_text != text:
                    text = self.edit_text
                buffer.write(row, 2 + col * 20, clip_text(text, 19),
                             fg=self.theme.selected_fg if active else self.theme.text,
                             bg=self.theme.selected_bg if active else self.theme.bg)
        buffer.write(23, 2, "Preview:", fg=self.theme.accent, bg=self.theme.bg,
                     bold=True)
        col = 2
        for item in self.menu.items:
            buffer.write(24, col, item.key, fg=self.theme.accent,
                         bg=self.theme.menu_bg, bold=True)
            col += len(item.key)
            buffer.write(24, col, item.label, fg=self.theme.menu_fg,
                         bg=self.theme.menu_bg)
            col += len(item.label) + 3
        draw_status_line(buffer, self.theme, self.status or
                         "F2 add   F5 delete   ENTER edit")
        draw_help_line(buffer, self.theme,
                       "A menu bar script is assigned to a form or browse table.")
        regions = draw_menu_line(buffer, self.theme, MENU_KEYS)
        return View(buffer, regions)


@dataclass
class ScriptDebugSession:
    """Debugger: F10 esegue un token, F5 fino alla fine, F3 variabili."""

    engine: object
    script: Script
    theme: Theme = NEWPORT
    runner: ScriptRunner | None = None
    status: str = ""
    close: bool = False
    done: bool = False
    help_topic: str = "scripts"

    def __post_init__(self) -> None:
        self.runner = ScriptRunner(self.engine, self.script.source,
                                   name=self.script.name)

    @property
    def title(self) -> str:
        return f"Debug Script - {self.script.name}"

    def handle(self, key: Key) -> None:
        self.status = ""
        if key.name == "ESC":
            self.close = True
            return
        if key.name == "F5":
            self._run_all()
            return
        if key.name in ("F10", "ENTER"):
            self._step()
            return
        if key.name == "F3":
            self.status = f"{len(self.engine.variables)} variable(s)."
            return
        if key.name == "F4":
            self.engine.debug_on = not self.engine.debug_on
            self.status = ("Debugger on." if self.engine.debug_on
                           else "Debugger off.")
            return

    def _step(self) -> None:
        if self.runner is None or self.done:
            self.done = True
            self.status = "Script finished."
            return
        try:
            self.done = self.runner.step()
        except Exception as exc:
            self.status = str(exc)
            self.done = True
            return
        if self.done:
            self.status = "Script finished."
        else:
            self.status = f"Step {self.runner.pc} of {len(self.runner.tokens)}."

    def _run_all(self) -> None:
        if self.runner is None:
            self.done = True
            return
        try:
            self.runner.run()
        except Exception as exc:
            self.status = str(exc)
        self.done = True
        self.status = "Script finished."

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        lines = self.script.source.split("\n") or [""]
        current = 0
        if self.runner is not None and self.runner.pc < len(self.runner.tokens):
            position = self.runner.tokens[self.runner.pc].position
            current = self.script.source[:position].count("\n")
        for offset, line in enumerate(lines[:STATUS_ROW - 2]):
            row = 2 + offset
            active = offset == current
            buffer.write(row, 1, clip_text(line, SOURCE_WIDTH),
                         fg=self.theme.selected_fg if active else self.theme.text,
                         bg=self.theme.selected_bg if active else self.theme.bg,
                         bold=active)
        variables = [f"%{name[1:]}={value}" for name, value in
                     self.engine.variables.items()[:8]]
        buffer.vline(1, SOURCE_COLUMNS + 1, STATUS_ROW - 1,
                     fg=self.theme.border, bg=self.theme.bg)
        buffer.write(2, VARIABLES_COL, "Variables", fg=self.theme.accent,
                     bg=self.theme.bg, bold=True)
        for index, text in enumerate(variables):
            buffer.write(3 + index, VARIABLES_COL,
                         clip_text(text, SCREEN_WIDTH - VARIABLES_COL - 1),
                         fg=self.theme.text, bg=self.theme.bg)
        draw_status_line(buffer, self.theme,
                         self.status or "F10 step   F5 run   F4 debug   ESC")
        draw_help_line(buffer, self.theme,
                       "The highlighted line is the next command to execute.")
        regions = draw_menu_line(buffer, self.theme,
                                 [("F3", "Variables"), ("F4", "Debug"),
                                  ("F5", "Run"), ("F10", "Step"),
                                  ("ESC", "Close")])
        return View(buffer, regions)


def _yes(text: str) -> bool:
    return text.strip().upper().startswith("Y")


@dataclass
class DialogRuntime:
    """Esecuzione interattiva di un dialog box sul guscio."""

    script: Script
    theme: Theme = NEWPORT
    values: dict[str, str] = field(default_factory=dict)
    focus: int = 0
    status: str = ""
    close: bool = False
    action_request: str = ""
    help_topic: str = "scripts"

    def __post_init__(self) -> None:
        dialog = self.script.dialog or DialogBox()
        for control in dialog.controls:
            if control.variable and control.variable not in self.values:
                self.values[control.variable] = control.default

    @property
    def dialog(self) -> DialogBox:
        return self.script.dialog or DialogBox()

    def handle(self, key: Key) -> None:
        self.status = ""
        controls = self.dialog.controls
        if key.name == "ESC":
            self.close = True
            return
        if key.name in ("TAB", "DOWN"):
            self._move(1)
            return
        if key.name == "UP":
            self._move(-1)
            return
        if key.name == "F10":
            self._activate()
            return
        if not controls:
            return
        control = controls[self.focus]
        if control.kind == CONTROL_BUTTON:
            if key.name == "ENTER":
                self._activate()
            return
        if key.name == "ENTER":
            self._move(1)
            return
        if key.name == "HOME":
            return
        if key.name == "BACKSPACE":
            value = self.values.get(control.variable, "")
            self.values[control.variable] = value[:-1]
            return
        text = character(key)
        if text:
            value = self.values.get(control.variable, "")
            if len(value) >= control.length:
                return
            self.values[control.variable] = value + text

    def _move(self, delta: int) -> None:
        if self.dialog.controls:
            self.focus = (self.focus + delta) % len(self.dialog.controls)

    def _activate(self) -> None:
        controls = self.dialog.controls
        if not controls:
            self.close = True
            return
        control = controls[self.focus]
        if control.kind == CONTROL_BUTTON:
            if control.label:
                self.status = control.label
            self.action_request = control.action
        else:
            self._move(1)

    def view(self) -> View:
        box = self.dialog
        buffer = ScreenBuffer().buffer
        title_bar(buffer, f"Dialog - {self.script.name}", self.theme)
        panel = window(box.width, box.height, box.title or self.script.name,
                       self.theme)
        for index, control in enumerate(box.controls):
            row = min(control.row, panel.height - 2)
            col = min(control.col, panel.width - 2)
            active = index == self.focus
            if control.kind == CONTROL_PROMPT:
                label = control.label or (control.variable or "Value")
                panel.write(row, col - 1,
                            clip_text(f"{label}", max(1, control.width)),
                            fg=self.theme.window_fg, bg=self.theme.window_bg)
                value = self.values.get(control.variable, "")
                if active:
                    panel.write(row + 1, col, clip_text(value + " " * control.length,
                                                       control.length),
                                fg=self.theme.selected_fg,
                                bg=self.theme.selected_bg)
                else:
                    panel.write(row + 1, col, clip_text(value, control.length),
                                fg=self.theme.window_fg,
                                bg=self.theme.window_bg)
            elif control.kind == CONTROL_BUTTON:
                label = f" {control.label or 'OK'} "
                panel.write(row, col, clip_text(label, control.width),
                            fg=self.theme.selected_fg if active else self.theme.title_fg,
                            bg=self.theme.selected_bg if active else self.theme.title_bg)
            else:
                value = self.values.get(control.variable, "")
                panel.write(row, col, clip_text(value, control.width),
                            fg=self.theme.window_fg, bg=self.theme.window_bg)
        blit(buffer, panel, box.row, box.col)
        draw_status_line(buffer, self.theme,
                         self.status or "TAB move   ENTER select   ESC close")
        draw_help_line(buffer, self.theme,
                       "Dialog box controls feed script variables.")
        regions = draw_menu_line(buffer, self.theme,
                                 [("TAB", "Next"), ("F10", "Select"),
                                  ("ESC", "Close")])
        return View(buffer, regions)


class ScreenBuffer:
    """Piccolo aiuto per costruire un buffer 132×43."""

    def __init__(self, theme: Theme = NEWPORT) -> None:
        self.buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                                 Cell(fg=theme.text, bg=theme.bg))
        self.buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                              fg=theme.text, bg=theme.bg)


__all__ = [
    "COMMANDS", "CONTENT_TOP", "DESIGN_KEYS", "DialogDesigner", "DialogRuntime",
    "EDITOR_KEYS", "MENU_KEYS", "MenuBarDesigner", "ScreenBuffer",
    "ScriptDebugSession", "ScriptEditor",
]
