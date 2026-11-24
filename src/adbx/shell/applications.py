"""Schermate delle applicazioni: editor, runtime, banner e protezioni.

L'editor mostra l'outline dei menu e i parametri della voce corrente; il
runtime mostra il menu dell'applicazione al posto del main menu. Banner
painter e schermata di protezione completano i comandi del capitolo 17.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..app.model import (
    ACTIONS,
    ALLOW_ESCAPE,
    COLUMNS,
    FLOWS,
    SPACINGS,
    AppItem,
    Application,
    AppMenu,
    BannerScreen,
    hot_letter,
    outline,
    password_hash,
)
from ..app.protection import PROTECTION_TYPES, protected_types, toggle_protection
from ..app.runtime import ApplicationRuntime
from ..app.store import ApplicationStore
from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW, Cell, CellBuffer
from ..screen.keys import Key, character
from .theme import NEWPORT, Theme
from .widgets import (
    View,
    clip_text,
    draw_help_line,
    draw_menu_line,
    draw_status_line,
    title_bar,
)

EDITOR_KEYS = [("F1", "Help"), ("F2", "Items"), ("F4", "Macro"),
               ("F6", "Banner"), ("F8", "Simulate"), ("F9", "Window"),
               ("F10", "Continue")]
PARAM_KEYS = [("F1", "Help"), ("F6", "Banner"), ("F10", "Continue")]
OUTLINE_TOP = 2
OUTLINE_ROWS = 10  # righe 2..11 con la griglia 80x25
DETAIL_TOP = 13
BANNER_KEYS = [("F1", "Help"), ("F3", "Foreground"), ("F4", "Background"),
               ("F10", "Save"), ("ESC", "Cancel")]


def _yes(text: str) -> bool:
    return text.strip().upper().startswith("Y")


@dataclass
class ApplicationEditor:
    store: ApplicationStore
    app: Application
    theme: Theme = NEWPORT
    stage: str = "parameters"
    parameter: int = 0
    edit_text: str = ""
    rows: list = field(default_factory=list)
    row: int = 0
    top: int = 0
    focus: str = "outline"
    detail: int = 0
    status: str = ""
    close: bool = False
    saved: bool = False
    banner_request: bool = False
    simulate_request: bool = False
    learn_request: bool = False
    macro_request: bool = False
    dirty: bool = False
    help_topic: str = "applications"

    def __post_init__(self) -> None:
        self.rows = outline(self.app)
        self._load_parameter()
        self._load_detail()

    @property
    def title(self) -> str:
        if self.stage == "parameters":
            return f"Application Parameters - {self.app.name}"
        return f"Application Editor - {self.app.name}"

    def handle(self, key: Key) -> None:
        if self.stage == "parameters":
            self._handle_parameters(key)
        else:
            self._handle_outline(key)

    # -- parametri -------------------------------------------------------
    PARAMS = ("Description", "Startup database/set", "Startup macro",
              "Script path", "Application banner", "Allow escape",
              "Escape password")

    def parameter_values(self) -> tuple:
        return (self.app.description, self.app.startup, self.app.startup_macro,
                self.app.script_path,
                "Yes" if self.app.banner_enabled else "No",
                self.app.allow_escape,
                "******" if self.app.escape_password_hash else "")

    def _load_parameter(self) -> None:
        self.parameter = max(0, min(self.parameter, len(self.PARAMS) - 1))
        self.edit_text = str(self.parameter_values()[self.parameter])

    def _commit_parameter(self) -> None:
        index = self.parameter
        value = self.edit_text
        if index == 0:
            self.app.description = value[:60]
        elif index == 1:
            self.app.startup = value.strip()
        elif index == 2:
            self.app.startup_macro = value[:3000]
        elif index == 3:
            self.app.script_path = value.strip()
        elif index == 4:
            self.app.banner_enabled = _yes(value)
        elif index == 5:
            upper = value.strip().title()
            if upper in ALLOW_ESCAPE:
                self.app.allow_escape = upper
            else:
                self.status = "Allow escape: Yes, No or Password."
        elif index == 6:
            if value != "******":
                self.app.escape_password_hash = password_hash(value)
        self.dirty = True
        self._load_parameter()

    def _handle_parameters(self, key: Key) -> None:
        if key.name == "F1":
            return
        if key.name == "F6":
            self.banner_request = True
            return
        if key.name == "F10":
            self._commit_parameter()
            if self.app.startup_macro and len(self.app.startup_macro) > 3000:
                self.status = "Startup macro limited to 3,000 characters."
                return
            self.stage = "outline"
            return
        if key.name == "ESC":
            self.close = True
            return
        if key.name == "UP":
            self._commit_parameter()
            self.parameter = max(0, self.parameter - 1)
            self._load_parameter()
            return
        if key.name == "DOWN":
            self._commit_parameter()
            self.parameter = min(len(self.PARAMS) - 1, self.parameter + 1)
            self._load_parameter()
            return
        if key.name == "ENTER":
            if self.parameter in (4,):
                self.edit_text = "No" if _yes(self.edit_text) else "Yes"
            elif self.parameter == 5:
                options = list(ALLOW_ESCAPE)
                current = self.edit_text.title()
                self.edit_text = options[
                    (options.index(current) + 1) % len(options)
                    if current in options else 0]
            else:
                self._commit_parameter()
                self.parameter = min(len(self.PARAMS) - 1, self.parameter + 1)
                self._load_parameter()
            return
        if key.name == "BACKSPACE":
            self.edit_text = self.edit_text[:-1]
            return
        text = character(key)
        if text:
            if key.name != "SPACE" and text.isalpha() and not key.shift:
                text = text.lower()
            self.edit_text += text

    # -- outline ---------------------------------------------------------
    def _load_detail(self) -> None:
        row = self.current_row
        if row is None:
            self.detail = 0
            self.edit_text = ""
            return
        fields = self.detail_fields(row)
        self.detail = max(0, min(self.detail, len(fields) - 1))
        self.edit_text = str(fields[self.detail][1])

    @property
    def current_row(self):
        if 0 <= self.row < len(self.rows):
            return self.rows[self.row]
        return None

    def detail_fields(self, row) -> list[tuple[str, object]]:
        if row.kind == "menu":
            return [("Menu title", row.menu.title),
                    ("Menu flow", row.menu.flow),
                    ("Columns", row.menu.columns),
                    ("Spacing", row.menu.spacing)]
        item = row.item
        assert item is not None
        return [("Menu text", item.text), ("Help line", item.help_line),
                ("Menu action", item.action), ("Target", item.target),
                ("Macro keys", item.macro),
                ("Password", "******" if item.password_hash else ""),
                ("Help file", item.help_file)]

    def _commit_detail(self) -> None:
        row = self.current_row
        if row is None:
            return
        value = self.edit_text
        if row.kind == "menu":
            if self.detail == 0:
                row.menu.title = (value or "MAIN MENU")[:40]
            elif self.detail == 1:
                upper = value.strip().title()
                if upper in FLOWS:
                    row.menu.flow = upper
                else:
                    self.status = "Menu flow: Return, Stay or Advance."
            elif self.detail == 2:
                upper = value.strip().title()
                if upper in COLUMNS:
                    row.menu.columns = upper
                else:
                    self.status = "Columns: Single or Double."
            else:
                upper = value.strip().title()
                if upper in SPACINGS:
                    row.menu.spacing = upper
                else:
                    self.status = "Spacing: Single, Double, Triple or Quadruple."
        else:
            item = row.item
            assert item is not None
            if self.detail == 0:
                item.text = (value or "Undefined menu choice")[:60]
            elif self.detail == 1:
                item.help_line = value[:79]
            elif self.detail == 2:
                upper = value.strip().title().replace("Goto", "GotO")
                if upper in ACTIONS:
                    item.action = upper
                    if upper == "Sub-Menu" and item.submenu is None:
                        item.submenu = AppMenu(title=item.text)
                else:
                    self.status = "Action: Sub-Menu, Macro, Call-App, GotO-App."
            elif self.detail == 3:
                item.target = value.strip()
            elif self.detail == 4:
                if len(value) <= 3000:
                    item.macro = value
                else:
                    self.status = "Macro limited to 3,000 characters."
            elif self.detail == 5:
                if value != "******":
                    item.password_hash = password_hash(value)
            else:
                item.help_file = value.strip()
        self.dirty = True
        self.rows = outline(self.app)
        self._load_detail()

    def _handle_outline(self, key: Key) -> None:
        if key.name == "F1":
            return
        if key.name == "F2":
            self._add_item()
            return
        if key.name == "F5":
            self._delete_item()
            return
        if key.name == "F4":
            if self.focus == "detail" and self.current_row.kind == "item" \
                    and self.current_row.item.action == "Macro":
                self._commit_detail()
                self.macro_request = True
            return
        if key.name == "F3":
            self.learn_request = True
            return
        if key.name == "F6":
            self._commit_detail()
            self.banner_request = True
            return
        if key.name == "F8":
            self._commit_detail()
            self.simulate_request = True
            return
        if key.name == "F9":
            self._commit_detail() if self.focus == "detail" else None
            self.focus = "detail" if self.focus == "outline" else "outline"
            if self.focus == "detail":
                self._load_detail()
            return
        if key.name == "F10":
            self._commit_detail() if self.focus == "detail" else None
            self._save()
            return
        if key.name == "ESC":
            self.close = True
            return
        if key.name == "TAB":
            self.focus = "detail" if self.focus == "outline" else "outline"
            if self.focus == "detail":
                self._load_detail()
            return
        if key.name == "UP":
            if self.focus == "outline":
                self.row = max(0, self.row - 1)
                self._scroll()
                self._load_detail()
            else:
                if self.detail > 0:
                    self._commit_detail()
                    self.detail -= 1
                    self._load_detail()
            return
        if key.name == "DOWN":
            if self.focus == "outline":
                self.row = min(len(self.rows) - 1, self.row + 1)
                self._scroll()
                self._load_detail()
            else:
                self._commit_detail()
                self.detail = min(len(self.detail_fields(self.current_row)) - 1,
                                  self.detail + 1)
                self._load_detail()
            return
        if key.name == "PGUP":
            self.row = max(0, self.row - OUTLINE_ROWS)
            self._scroll()
            self._load_detail()
            return
        if key.name == "PGDN":
            self.row = min(len(self.rows) - 1, self.row + OUTLINE_ROWS)
            self._scroll()
            self._load_detail()
            return
        if self.focus == "detail":
            if key.name == "ENTER":
                self._commit_detail()
                self.detail = min(len(self.detail_fields(self.current_row)) - 1,
                                  self.detail + 1)
                self._load_detail()
                return
            if key.name == "BACKSPACE":
                self.edit_text = self.edit_text[:-1]
                return
            text = character(key)
            if text:
                if text.isalpha() and not key.shift:
                    text = text.lower()
                self.edit_text += text

    def _scroll(self) -> None:
        if self.row < self.top:
            self.top = self.row
        elif self.row >= self.top + OUTLINE_ROWS:
            self.top = self.row - OUTLINE_ROWS + 1

    def _add_item(self) -> None:
        row = self.current_row
        if row is None:
            return
        target_menu = row.menu
        item = AppItem("Undefined menu choice", action="Macro")
        if row.kind == "item":
            index = target_menu.items.index(row.item)
            target_menu.items.insert(index + 1, item)
        else:
            target_menu.items.append(item)
        self.rows = outline(self.app)
        self.row = next((index for index, candidate in enumerate(self.rows)
                         if candidate.item is item), self.row)
        self._scroll()
        self.focus = "detail"
        self.detail = 0
        self._load_detail()
        self.dirty = True

    def _delete_item(self) -> None:
        row = self.current_row
        if row is None or row.kind != "item":
            self.status = "Select a menu item to delete."
            return
        try:
            row.menu.items.remove(row.item)
        except ValueError:
            return
        self.rows = outline(self.app)
        self.row = min(self.row, len(self.rows) - 1)
        self._scroll()
        self._load_detail()
        self.dirty = True

    def _save(self) -> bool:
        try:
            self.store.save(self.app)
        except Exception as exc:
            self.status = str(exc)
            return False
        self.saved = True
        self.status = f"Application {self.app.name} saved."
        return True

    # -- disegno ---------------------------------------------------------
    def view(self) -> View:
        if self.stage == "parameters":
            return self._parameters_view()
        return self._outline_view()

    def _parameters_view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        buffer.write(2, 2, self.app.name, fg=self.theme.accent,
                     bg=self.theme.bg, bold=True)
        for index, label in enumerate(self.PARAMS):
            row = 4 + index
            active = index == self.parameter
            buffer.write(row, 2, f"{label:<22}:",
                         fg=self.theme.accent if active else self.theme.label,
                         bg=self.theme.bg, bold=active)
            value = str(self.parameter_values()[index])
            if active:
                value = self.edit_text
            buffer.write(row, 27, clip_text(value, 60),
                         fg=self.theme.selected_fg if active else self.theme.text,
                         bg=self.theme.selected_bg if active else self.theme.bg)
        buffer.write(12, 2, "Enter description for this application",
                     fg=self.theme.label, bg=self.theme.bg)
        draw_status_line(buffer, self.theme,
                         self.status or f"Application {self.app.name}")
        draw_help_line(buffer, self.theme,
                       "F10 continues to the Application Editor.")
        regions = draw_menu_line(buffer, self.theme, PARAM_KEYS)
        return View(buffer, regions)

    def _outline_view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        for offset in range(OUTLINE_ROWS):
            index = self.top + offset
            if index >= len(self.rows):
                break
            row = self.rows[index]
            text = "  " * row.depth + row.text
            line = OUTLINE_TOP + offset
            active = index == self.row and self.focus == "outline"
            if active:
                buffer.fill_rect(line, 0, 1, SCREEN_WIDTH, " ",
                                 fg=self.theme.selected_fg,
                                 bg=self.theme.selected_bg)
            buffer.write(line, 1, clip_text(text, SCREEN_WIDTH - 2),
                         fg=self.theme.selected_fg if active else self.theme.text,
                         bg=self.theme.selected_bg if active else self.theme.bg,
                         bold=active)
        buffer.fill_rect(DETAIL_TOP - 1, 0, 1, SCREEN_WIDTH, "-",
                         fg=self.theme.border, bg=self.theme.bg)
        current = self.current_row
        if current is not None:
            fields = self.detail_fields(current)
            buffer.write(DETAIL_TOP, 1, "MENU HEADING" if current.kind == "menu"
                         else "MENU ITEM", fg=self.theme.accent,
                         bg=self.theme.bg, bold=True)
            for index, (label, value) in enumerate(fields):
                row = DETAIL_TOP + 1 + index
                active = self.focus == "detail" and index == self.detail
                text = str(value)
                if active:
                    text = self.edit_text
                buffer.write(row, 1, f"{label:<14}:",
                             fg=self.theme.accent if active else self.theme.label,
                             bg=self.theme.bg, bold=active)
                buffer.write(row, 17, clip_text(text, SCREEN_WIDTH - 18),
                             fg=self.theme.selected_fg if active else self.theme.text,
                             bg=self.theme.selected_bg if active else self.theme.bg)
        draw_status_line(buffer, self.theme, self.status or
                         f"{len(self.rows)} outline lines")
        draw_help_line(buffer, self.theme,
                       "F2 adds a choice, F5 deletes, F9 switches window.")
        regions = draw_menu_line(buffer, self.theme, EDITOR_KEYS)
        return View(buffer, regions)


@dataclass
class MacroEditor:
    """Editor multilinea per le macro di una voce di menu."""

    text: str
    theme: Theme = NEWPORT
    lines: list[str] = field(default_factory=list)
    row: int = 0
    col: int = 0
    top: int = 0
    status: str = ""
    close: bool = False
    saved: bool = False
    help_topic: str = "applications"

    def __post_init__(self) -> None:
        self.lines = self.text.split("\n") or [""]

    @property
    def title(self) -> str:
        return "Macro Editor"

    @property
    def body(self) -> str:
        return "\n".join(self.lines)[:3000]

    def handle(self, key: Key) -> None:
        self.status = ""
        if key.name == "F10":
            self.saved = True
            self.close = True
            return
        if key.name == "ESC":
            self.close = True
            return
        if key.name == "UP":
            self.row = max(0, self.row - 1)
            self.col = min(self.col, len(self.lines[self.row]))
            self._scroll()
            return
        if key.name == "DOWN":
            self.row = min(len(self.lines) - 1, self.row + 1)
            self.col = min(self.col, len(self.lines[self.row]))
            self._scroll()
            return
        if key.name == "LEFT":
            self.col = max(0, self.col - 1)
            return
        if key.name == "RIGHT":
            self.col = min(len(self.lines[self.row]), self.col + 1)
            return
        if key.name == "HOME":
            self.col = 0
            return
        if key.name == "END":
            self.col = len(self.lines[self.row])
            return
        if key.name == "ENTER":
            line = self.lines[self.row]
            self.lines[self.row] = line[:self.col]
            self.lines.insert(self.row + 1, line[self.col:])
            self.row += 1
            self.col = 0
            self._scroll()
            return
        if key.name == "BACKSPACE":
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
        if key.name == "DELETE":
            line = self.lines[self.row]
            if self.col < len(line):
                self.lines[self.row] = line[:self.col] + line[self.col + 1:]
            elif self.row + 1 < len(self.lines):
                self.lines[self.row] = line + self.lines[self.row + 1]
                self.lines.pop(self.row + 1)
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            line = self.lines[self.row]
            self.lines[self.row] = line[:self.col] + text + line[self.col:]
            self.col += len(text)
            self._scroll()

    def _scroll(self) -> None:
        visible = STATUS_ROW - 3
        if self.row < self.top:
            self.top = self.row
        elif self.row >= self.top + visible:
            self.top = self.row - visible + 1

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        for offset in range(STATUS_ROW - 3):
            index = self.top + offset
            if index >= len(self.lines):
                break
            row = 2 + offset
            buffer.write(row, 1, clip_text(self.lines[index], 128),
                         fg=self.theme.text, bg=self.theme.bg)
        draw_status_line(buffer, self.theme,
                         self.status or f"{len(self.body)}/3000 characters")
        draw_help_line(buffer, self.theme,
                       "Macros accept keys and script commands.")
        regions = draw_menu_line(buffer, self.theme,
                                 [("F10", "Save"), ("ESC", "Cancel")])
        return View(buffer, regions)


@dataclass
class BannerPainter:
    """Painter a celle del banner di apertura."""

    app: Application
    theme: Theme = NEWPORT
    row: int = 0
    col: int = 0
    foreground: int = 15
    background: int = 1
    status: str = ""
    close: bool = False
    saved: bool = False
    help_topic: str = "applications"

    def __post_init__(self) -> None:
        self.foreground = self.app.banner.foreground
        self.background = self.app.banner.background

    @property
    def banner(self) -> BannerScreen:
        return self.app.banner

    def handle(self, key: Key) -> None:
        self.status = ""
        name = key.name
        if name == "F10":
            self.app.banner.foreground = self.foreground
            self.app.banner.background = self.background
            self.saved = True
            self.close = True
            return
        if name == "ESC":
            self.close = True
            return
        if name == "F3":
            self.foreground = (self.foreground + 1) % 16
            self.status = f"Foreground {self.foreground}"
            return
        if name == "F4":
            self.background = (self.background + 1) % 16
            self.status = f"Background {self.background}"
            return
        if name == "UP":
            self.row = max(0, self.row - 1)
            return
        if name == "DOWN":
            self.row = min(SCREEN_HEIGHT - 2, self.row + 1)
            return
        if name == "LEFT":
            self.col = max(0, self.col - 1)
            return
        if name == "RIGHT":
            self.col = min(SCREEN_WIDTH - 1, self.col + 1)
            return
        if name == "HOME":
            self.col = 0
            return
        if name == "END":
            self.col = SCREEN_WIDTH - 1
            return
        if name == "BACKSPACE":
            if self.col:
                self.col -= 1
                self.banner.put(self.row, self.col, " ", self.foreground,
                                self.background)
            return
        if name == "DELETE":
            self.banner.put(self.row, self.col, " ", self.foreground,
                            self.background)
            return
        text = character(key)
        if text:
            self.banner.put(self.row, self.col, text, self.foreground,
                            self.background)
            self.col = min(SCREEN_WIDTH - 1, self.col + 1)

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        for row in range(SCREEN_HEIGHT):
            for col in range(SCREEN_WIDTH):
                fg, bg = self.banner.cell_colors(row, col)
                buffer.put(row, col, Cell(self.banner.text(row, col),
                                          fg=fg, bg=bg))
        draw_status_line(buffer, self.theme,
                         self.status or
                         f"Row {self.row + 1}, Col {self.col + 1}   "
                         f"Fg {self.foreground}  Bg {self.background}")
        draw_help_line(buffer, self.theme,
                       "Type the banner text; F3/F4 change colors.")
        regions = draw_menu_line(buffer, self.theme, BANNER_KEYS)
        return View(buffer, regions)


@dataclass
class ApplicationSession:
    """Menu di un'applicazione in esecuzione o in simulazione."""

    runtime: ApplicationRuntime
    theme: Theme = NEWPORT
    status: str = ""
    close: bool = False
    banner_pending: bool = False
    help_request: str = ""
    help_topic: str = "applications"

    def __post_init__(self) -> None:
        self.banner_pending = (self.runtime.app.banner_enabled
                               and self.runtime.app.banner.enabled
                               and not self.runtime.banner_done)

    @property
    def app(self) -> Application:
        return self.runtime.app

    def start(self) -> None:
        self.banner_pending = False
        self.runtime.banner_done = True

    def handle(self, key: Key) -> None:
        self.status = ""
        name = key.name
        if self.banner_pending:
            self.start()
            return
        if name == "F1":
            item = self.runtime.item
            if item is not None and item.help_file:
                self.help_request = item.help_file
            return
        if name == "UP":
            self.runtime.move(-1)
            return
        if name == "DOWN":
            self.runtime.move(1)
            return
        if name == "PGUP":
            self.runtime.move(-10)
            return
        if name == "PGDN":
            self.runtime.move(10)
            return
        if name == "ENTER":
            self.runtime.activate()
            return
        if name == "ESC":
            self.runtime.back()
            return
        text = character(key)
        if text and self.runtime.select(text):
            return

    def view(self) -> View:
        if self.banner_pending:
            return self.banner_view()
        return menu_view(self.runtime, self.theme, self.status)

    def banner_view(self) -> View:
        return banner_view(self.runtime.app, self.theme)


def banner_view(app: Application, theme: Theme = NEWPORT) -> View:
    buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                        Cell(fg=app.banner.foreground,
                             bg=app.banner.background))
    for row in range(SCREEN_HEIGHT):
        for col in range(SCREEN_WIDTH):
            fg, bg = app.banner.cell_colors(row, col)
            buffer.put(row, col, Cell(app.banner.text(row, col), fg=fg, bg=bg))
    draw_status_line(buffer, theme, "Press any key to continue")
    draw_help_line(buffer, theme, "Application banner")
    return View(buffer)


def menu_view(runtime: ApplicationRuntime, theme: Theme = NEWPORT,
              status: str = "") -> View:
    buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                        Cell(fg=theme.text, bg=theme.bg))
    buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                     fg=theme.text, bg=theme.bg)
    title = runtime.menu.title
    buffer.fill_rect(2, 0, 1, SCREEN_WIDTH, " ",
                     fg=theme.selected_fg, bg=theme.selected_bg)
    buffer.write(2, max(1, (SCREEN_WIDTH - len(title)) // 2), title,
                 fg=theme.selected_fg, bg=theme.selected_bg, bold=True)
    items = runtime.menu.items
    spacing = {"Single": 1, "Double": 2, "Triple": 3, "Quadruple": 4}[
        runtime.menu.spacing]
    columns = 2 if runtime.menu.columns == "Double" else 1
    per_column = max(1, (STATUS_ROW - 5) // spacing)
    column_width = SCREEN_WIDTH // columns
    for index, item in enumerate(items):
        group = index // per_column
        offset = index % per_column
        row = 4 + offset * spacing
        col = 2 + group * column_width
        active = index == runtime.index
        text = item.text
        if active:
            buffer.fill_rect(row, col - 1, 1, column_width - 2, " ",
                             fg=theme.selected_fg, bg=theme.selected_bg)
        fg = theme.selected_fg if active else theme.text
        bg = theme.selected_bg if active else theme.bg
        hot = hot_letter(text)
        position = text.find(hot) if hot else 0
        buffer.write(row, col, clip_text(text, column_width - 4), fg=fg, bg=bg)
        if hot and position >= 0:
            buffer.put(row, col + position,
                       Cell(hot, fg=fg if active else theme.accent, bg=bg,
                            bold=True))
    draw_status_line(buffer, theme,
                     f"{runtime.app.name}"
                     + ("   SIMULATION" if runtime.simulate else "")
                     + (f"   {status or runtime.status}" if status or
                        runtime.status else ""))
    draw_help_line(buffer, theme, runtime.help_line or
                   "Choose a menu item; ESC backs up one level.")
    regions = draw_menu_line(buffer, theme,
                             [("F1", "Help"), ("ENTER", "Select"),
                              ("ESC", "Back")])
    return View(buffer, regions)


@dataclass
class ProtectionSession:
    """Prevent/allow file alterations per un database o set."""

    workspace: object
    owner: str
    theme: Theme = NEWPORT
    items: list[tuple[str, bool]] = field(default_factory=list)
    selected: int = 0
    status: str = ""
    close: bool = False
    help_topic: str = "applications"

    def __post_init__(self) -> None:
        self.reload()

    @property
    def title(self) -> str:
        return f"Prevent/allow file alterations - {self.owner}"

    def reload(self) -> None:
        current = protected_types(self.workspace, self.owner)
        self.items = [(name, name in current) for name in PROTECTION_TYPES]

    def handle(self, key: Key) -> None:
        self.status = ""
        if key.name == "UP":
            self.selected = max(0, self.selected - 1)
        elif key.name == "DOWN":
            self.selected = min(len(self.items) - 1, self.selected + 1)
        elif key.name in ("SPACE", "ENTER"):
            name, _value = self.items[self.selected]
            toggle_protection(self.workspace, self.owner, name)
            self.reload()
        elif key.name == "F10":
            self.close = True
        elif key.name == "ESC":
            self.close = True

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        buffer.write(2, 2, "Protect these supporting files:",
                     fg=self.theme.accent, bg=self.theme.bg, bold=True)
        for index, (name, prevented) in enumerate(self.items):
            row = 4 + index
            active = index == self.selected
            marker = "[X]" if prevented else "[ ]"
            text = f"{marker} {name}"
            if active:
                buffer.fill_rect(row, 1, 1, 50, " ",
                                 fg=self.theme.selected_fg,
                                 bg=self.theme.selected_bg)
            buffer.write(row, 2, text,
                         fg=self.theme.selected_fg if active else self.theme.text,
                         bg=self.theme.selected_bg if active else self.theme.bg)
        draw_status_line(buffer, self.theme, self.status or
                         "SPACE toggles   F10 saves")
        draw_help_line(buffer, self.theme,
                       "Protected files cannot be edited until allowed again.")
        regions = draw_menu_line(buffer, self.theme,
                                 [("SPACE", "Toggle"), ("F10", "Save"),
                                  ("ESC", "Cancel")])
        return View(buffer, regions)


__all__ = [
    "ApplicationEditor", "ApplicationSession", "BANNER_KEYS", "BannerPainter",
    "DETAIL_TOP", "EDITOR_KEYS", "MacroEditor", "OUTLINE_TOP",
    "PARAM_KEYS", "ProtectionSession", "banner_view", "menu_view",
]
