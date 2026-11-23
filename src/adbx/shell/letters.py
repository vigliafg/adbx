"""Form letter editor (O8)."""

from __future__ import annotations

from dataclasses import dataclass

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW, Cell, CellBuffer
from ..data.letters import LETTER_NAME_RE, LetterDefinition, LetterError
from ..data.workspace import Database, Workspace
from ..screen.keys import Key, character
from .dialogs import Picker, picker_view
from .theme import NEWPORT, Theme
from .widgets import (
    View,
    clip_text,
    draw_help_line,
    draw_menu_line,
    draw_status_line,
    title_bar,
)

LETTER_KEYS = [("F1", "Help"), ("F2", "Fields"), ("F3", "Commands"),
               ("F7", "Conditionals"), ("F10", "Save")]
CONTENT_TOP = 3
MAX_BODY = 10000


@dataclass
class LetterEditor:
    workspace: Workspace
    database: Database | None = None
    owner: str = ""
    letter: LetterDefinition | None = None
    theme: Theme = NEWPORT
    stage: str = "name"
    name_text: str = ""
    edit_existing: bool = False
    row: int = 0
    col: int = 0
    top: int = 0
    picker: Picker | None = None
    picker_kind: str = ""
    pending_database: str = ""
    pending_field: str = ""
    prompt_text: str = ""
    prompt_action: str = ""
    status: str = ""
    close: bool = False
    saved: bool = False
    saved_letter: LetterDefinition | None = None
    preview_request: bool = False
    help_topic: str = "letters"

    def __post_init__(self) -> None:
        if not self.owner:
            self.owner = self.database.name if self.database else ""
        if self.letter is not None:
            self.stage = "edit"
            self.edit_existing = True

    @property
    def owner_databases(self) -> dict[str, Database]:
        database = self.workspace.get(self.owner)
        if database is not None:
            return {database.name: database}
        definition = self.workspace.get_set(self.owner)
        if definition is None:
            return {}
        return {name: definition.database(name)
                for name in definition.database_names()}

    @property
    def title(self) -> str:
        if self.stage == "name":
            return "Create/Edit a Form Letter"
        if self.letter is None:
            return "Form Letter Layout"
        return f"Form Letter Layout - {self.letter.name}"

    def handle(self, key: Key) -> None:
        self.status = ""
        if self.picker is not None:
            self._handle_picker(key)
            return
        if self.stage == "name":
            self._handle_name(key)
        elif self.stage == "edit":
            self._handle_edit(key)
        elif self.stage == "prompt":
            self._handle_prompt(key)
        elif self.stage == "save":
            return
        elif self.stage == "borrow_name":
            self._handle_borrow_name(key)

    # -- nome ------------------------------------------------------------
    def _handle_name(self, key: Key) -> None:
        if key.name == "ENTER":
            name = self.name_text.strip().upper()
            if not LETTER_NAME_RE.match(name):
                self.status = "Letter names have 1-8 letters, digits or _."
                return
            existing = self.workspace.get_letter(self.owner, name)
            if existing is not None:
                self.letter = existing
                self.edit_existing = True
            else:
                self.letter = LetterDefinition(self.workspace, self.owner,
                                               name)
            self.stage = "edit"
            self.row = 0
            self.col = 0
            return
        if key.name == "ESC":
            self.close = True
            return
        text = character(key)
        if text and (text.isalnum() or text == "_"):
            self.name_text += text.upper()

    # -- editor ----------------------------------------------------------
    def _handle_edit(self, key: Key) -> None:
        letter = self.letter
        assert letter is not None
        name = key.name
        if name == "F2":
            self._open_field_picker()
            return
        if name == "F3":
            self.picker = Picker(
                "Commands",
                ["Line width", "Left margin", "Top margin", "Bottom margin",
                 "Page eject", "Include file", "Enable auto fill",
                 "Disable auto fill", "Control codes"],
                values=["width", "left", "top", "bottom", "eject", "include",
                        "fill+", "fill-", "codes"],
                footer="ENTER select   ESC cancel")
            self.picker_kind = "commands"
            return
        if name == "F7":
            self.picker = Picker(
                "Conditionals", ["IF", "ELSEIF", "ELSE", "ENDIF"],
                values=["if", "elseif", "else", "endif"],
                footer="ENTER select   ESC cancel")
            self.picker_kind = "conditional"
            return
        if name == "F10":
            self._open_save()
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN"):
            if name == "UP":
                self.row = max(0, self.row - 1)
            else:
                self.row = min(len(letter.body) - 1, self.row + 1)
            self.col = min(self.col, len(letter.body[self.row]))
            self._scroll()
            return
        if name in ("LEFT", "RIGHT"):
            if name == "LEFT":
                if self.col > 0:
                    self.col -= 1
                elif self.row > 0:
                    self.row -= 1
                    self.col = len(letter.body[self.row])
            else:
                if self.col < len(letter.body[self.row]):
                    self.col += 1
                elif self.row < len(letter.body) - 1:
                    self.row += 1
                    self.col = 0
            self._scroll()
            return
        if name == "HOME":
            self.col = 0
            return
        if name == "END":
            self.col = len(letter.body[self.row])
            return
        if name == "PGUP":
            self.row = max(0, self.row - 22)
            self._clamp_cursor()
            return
        if name == "PGDN":
            self.row = min(len(letter.body) - 1, self.row + 22)
            self._clamp_cursor()
            return
        if name == "ENTER":
            line = letter.body[self.row]
            letter.body[self.row] = line[:self.col]
            letter.body.insert(self.row + 1, line[self.col:])
            self.row += 1
            self.col = 0
            self._scroll()
            return
        if name == "BACKSPACE":
            line = letter.body[self.row]
            if self.col > 0:
                letter.body[self.row] = line[:self.col - 1] + line[self.col:]
                self.col -= 1
            elif self.row > 0:
                previous = letter.body[self.row - 1]
                letter.body[self.row - 1] = previous + line
                letter.body.pop(self.row)
                self.row -= 1
                self.col = len(previous)
            self._scroll()
            return
        if name == "DELETE":
            line = letter.body[self.row]
            if self.col < len(line):
                letter.body[self.row] = line[:self.col] + line[self.col + 1:]
            elif self.row < len(letter.body) - 1:
                letter.body[self.row] = line + letter.body[self.row + 1]
                letter.body.pop(self.row + 1)
            return
        if name == "SPACE":
            self._insert(" ")
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self._insert(text)

    def _insert(self, text: str) -> None:
        letter = self.letter
        assert letter is not None
        line = letter.body[self.row]
        letter.body[self.row] = line[:self.col] + text + line[self.col:]
        self.col += len(text)
        self._scroll()

    def _clamp_cursor(self) -> None:
        assert self.letter is not None
        self.row = max(0, min(self.row, len(self.letter.body) - 1))
        self.col = min(self.col, len(self.letter.body[self.row]))
        self._scroll()

    def _scroll(self) -> None:
        visible = STATUS_ROW - CONTENT_TOP - 2
        if self.row < self.top:
            self.top = self.row
        elif self.row >= self.top + visible:
            self.top = self.row - visible + 1

    # -- comandi ---------------------------------------------------------
    def _insert_line(self, text: str) -> None:
        letter = self.letter
        assert letter is not None
        letter.body.insert(self.row + 1, text)
        self.row += 1
        self.col = len(text)
        self._scroll()

    def _open_field_picker(self) -> None:
        items = list(self.owner_databases)
        values = list(self.owner_databases)
        items.append("SYSTEM")
        values.append("SYSTEM")
        self.picker = Picker("Database", items, values,
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "database"

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
            value = picker.value()
            kind = self.picker_kind
            self.picker = None
            if value:
                self._selected(kind, value)

    def _selected(self, kind: str, value: str) -> None:
        if kind == "database":
            self.pending_database = value
            self._open_fields(value)
        elif kind == "field":
            database, field = value.split(":", 1)
            self.pending_database = database
            self.pending_field = field
            self.picker = Picker(
                "Field format",
                ["Suppress", "Left", "Right", "Center",
                 "Suppress, delete line if empty"],
                values=["S", "L", "R", "C", "SD"],
                footer="ENTER select   ESC cancel")
            self.picker_kind = "format"
        elif kind == "format":
            self._insert_marker(value)
        elif kind == "commands":
            self._command(value)
        elif kind == "conditional":
            self._conditional(value)
        elif kind == "save":
            self._save_action(value)

    def _open_fields(self, database: str) -> None:
        items: list[str] = []
        values: list[str] = []
        if database == "SYSTEM":
            items = ["DATE", "REC_NUMBER"]
            values = ["SYSTEM:DATE", "SYSTEM:REC_NUMBER"]
        else:
            for definition in self.owner_databases[database].fields:
                items.append(definition.name)
                values.append(f"{database}:{definition.name}")
        self.picker = Picker("Fieldnames", items, values,
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "field"

    def _insert_marker(self, options: str) -> None:
        database = self.pending_database
        field = self.pending_field
        if database == "SYSTEM":
            marker = f"[SYSTEM->{field}"
        elif len(self.owner_databases) == 1:
            marker = f"[{field}"
        else:
            marker = f"[{database}->{field}"
        if options:
            marker += f".{options}"
        marker += "]"
        self._insert(marker)

    def _command(self, action: str) -> None:
        if action == "eject":
            self._insert_line("[.EJECT]")
            return
        if action in ("fill+", "fill-"):
            self._insert_line("[.FILL+]" if action == "fill+" else "[.FILL-]")
            return
        prompts = {"width": ("Line width", "[.WIDTH "),
                   "left": ("Left margin", "[.LEFT "),
                   "top": ("Top margin", "[.TOP "),
                   "bottom": ("Bottom margin", "[.BOTTOM "),
                   "include": ("Include file", "[.INCLUDE "),
                   "codes": ("Control codes", "[@")}
        prompt, prefix = prompts[action]
        self.prompt_action = action
        self.prompt_text = ""
        self._prompt_prefix = prefix
        self.stage = "prompt"
        self.status = prompt

    def _conditional(self, action: str) -> None:
        if action == "else":
            self._insert_line("[.ELSE]")
            return
        if action == "endif":
            self._insert_line("[.ENDIF]")
            return
        self.prompt_action = action
        self.prompt_text = ""
        self._prompt_prefix = ""
        self.stage = "prompt"
        self.status = "IF expression" if action == "if" else "ELSEIF expression"

    def _handle_prompt(self, key: Key) -> None:
        if key.name == "ENTER":
            text = self.prompt_text.strip()
            action = self.prompt_action
            if action in ("if", "elseif"):
                self._insert_line(f"[.{action.upper()} {text}]")
            elif action == "width":
                self._insert_line(f"[.WIDTH {text}]")
            elif action == "left":
                self._insert_line(f"[.LEFT {text}]")
            elif action == "top":
                self._insert_line(f"[.TOP {text}]")
            elif action == "bottom":
                self._insert_line(f"[.BOTTOM {text}]")
            elif action == "include":
                self._insert_line(f"[.INCLUDE {text}]")
            elif action == "codes":
                self._insert_line(f"[@{text}]")
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

    # -- salvataggio -----------------------------------------------------
    def _open_save(self) -> None:
        self.picker = Picker(
            "Save", ["Save", "Save and preview", "Save and continue editing",
                     "Save as a new name"],
            values=["save", "preview", "continue", "as"],
            footer="ENTER select   ESC cancel")
        self.picker_kind = "save"

    def _save_action(self, action: str) -> None:
        if action == "as":
            self.stage = "borrow_name"
            self.name_text = ""
            return
        if self.save():
            if action == "preview":
                self.preview_request = True
                self.close = True
            elif action == "continue":
                self.stage = "edit"
            else:
                self.close = True

    def _handle_borrow_name(self, key: Key) -> None:
        if key.name == "ENTER":
            name = self.name_text.strip().upper()
            if not LETTER_NAME_RE.match(name):
                self.status = "Letter names have 1-8 letters, digits or _."
                return
            if self.workspace.get_letter(self.owner, name) is not None:
                self.status = "That letter name is already used."
                return
            self.letter.name = name
            if self.save():
                self.close = True
            return
        if key.name == "ESC":
            self.close = True
            return
        text = character(key)
        if text and (text.isalnum() or text == "_"):
            self.name_text += text.upper()

    def save(self) -> bool:
        if self.letter is None:
            return False
        try:
            self.letter.save()
        except LetterError as exc:
            self.status = str(exc)
            return False
        self.saved = True
        self.saved_letter = self.letter
        self.status = f"Letter {self.letter.name} saved."
        return True

    def run(self):
        if self.letter is None:
            return None
        from ..data.letters import render_letters

        return render_letters(self.letter, self.workspace)

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        if self.stage in ("name", "borrow_name"):
            self._view_name(buffer)
        elif self.stage == "prompt":
            self._view_edit(buffer)
            self._view_prompt(buffer)
        else:
            self._view_edit(buffer)
        view = View(buffer, [])
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        return view

    def _view_name(self, buffer: CellBuffer) -> None:
        title_bar(buffer, "Create/Edit a Form Letter", self.theme)
        buffer.write(4, 2, "Letter name", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(4, 20, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.fill_rect(4, 22, 1, 12, " ", fg=self.theme.selected_fg,
                         bg=self.theme.selected_bg)
        buffer.write(4, 22, self.name_text or "_", fg=self.theme.selected_fg,
                     bg=self.theme.selected_bg, underline=True)
        draw_status_line(buffer, self.theme,
                         self.status or "Type a letter name and press ENTER")
        draw_help_line(buffer, self.theme, "ENTER accept   ESC cancel")

    def _view_edit(self, buffer: CellBuffer) -> None:
        letter = self.letter
        assert letter is not None
        title_bar(buffer, f"{self.title} - {len(letter.body)} lines", self.theme)
        visible = STATUS_ROW - CONTENT_TOP - 2
        for offset in range(visible):
            index = self.top + offset
            if index >= len(letter.body):
                break
            text = letter.body[index]
            selected = index == self.row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(CONTENT_TOP + offset, 0, 1,
                                 SCREEN_WIDTH, " ", fg=fg, bg=bg)
            buffer.write(CONTENT_TOP + offset, 1, clip_text(text,
                                                            SCREEN_WIDTH - 3),
                         fg=fg, bg=bg)
        cursor_row = CONTENT_TOP + self.row - self.top
        buffer.write(cursor_row, 1 + self.col, "_",
                     fg=self.theme.selected_fg, bg=self.theme.selected_bg,
                     blink=True)
        draw_status_line(buffer, self.theme,
                         self.status or f"Line {self.row + 1}  "
                                        f"Col {self.col + 1}")
        draw_help_line(buffer, self.theme,
                       "F2 fields   F3 commands   F7 conditionals   "
                       "F10 save   ESC cancel")
        draw_menu_line(buffer, self.theme, LETTER_KEYS)

    def _view_prompt(self, buffer: CellBuffer) -> None:
        row = STATUS_ROW - 5
        buffer.fill_rect(row, 10, 3, 70, " ", fg=self.theme.window_fg,
                         bg=self.theme.window_bg)
        buffer.write(row, 12, self.status, fg=self.theme.label,
                     bg=self.theme.window_bg, bold=True)
        buffer.write(row, 12, clip_text(self._prompt_prefix + self.prompt_text,
                                        66) if self._prompt_prefix
                     else clip_text(self.prompt_text, 66),
                     fg=self.theme.window_fg, bg=self.theme.window_bg,
                     underline=True)


__all__ = ["LetterEditor"]
