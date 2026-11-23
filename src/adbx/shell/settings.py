"""Schermate di configurazione: default, stampanti, colori, documentazione."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..app.store import ApplicationStore
from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW, Cell, CellBuffer
from ..config.colors import (
    COLOR_TOKENS,
    cycle_color,
    defaults_palette,
    load_colors,
    save_colors,
)
from ..config.defaults import PATTERNS, DefaultSettings
from ..config.display import clamp_zoom
from ..config.printers import (
    LETTERS,
    PAGE_ADVANCE,
    PRINTER_MODELS,
    PrinterConfig,
    PrinterDriver,
    PrinterError,
)
from ..data.workspace import Workspace
from ..docs.generator import (
    application_report,
    database_structure,
    field_rules_report,
    script_report,
    set_structure,
    write_document,
)
from ..screen.keys import Key, character
from ..script.store import ScriptStore
from ..shell.theme import Theme
from .theme import NEWPORT
from .widgets import (
    View,
    clip_text,
    draw_help_line,
    draw_menu_line,
    draw_status_line,
    title_bar,
)


@dataclass
class DefaultsSession:
    """Default settings del cap. 22."""

    defaults: DefaultSettings
    theme: Theme = NEWPORT
    selected: int = 0
    status: str = ""
    close: bool = False
    saved: bool = False
    edit_text: str = ""
    help_topic: str = "other"

    FIELDS = (
        ("Date separator", "date_separator", "text"),
        ("Date format", "date_format", "choice"),
        ("Auto flush", "auto_flush", "bool"),
        ("Pattern matching", "pattern", "choice"),
        ("Prevent change", "prevent_change", "bool"),
        ("Prevent enter", "prevent_enter", "bool"),
        ("Single step enters", "single_step_enters", "bool"),
        ("Utilities should lock", "utilities_lock", "bool"),
        ("dBASE IV compatibility", "dbase4", "bool"),
        ("Adjust for monochrome", "monochrome", "bool"),
        ("Script path", "script_path", "text"),
        ("Data path", "data_path", "text"),
        ("Last database", "last_database", "text"),
        ("Default printer", "printer_default", "text"),
        ("Screen zoom %", "screen_zoom", "int"),
    )

    def __post_init__(self) -> None:
        self._load()

    @property
    def title(self) -> str:
        return "Default Settings"

    def _load(self) -> None:
        name, _attr, kind = self.FIELDS[self.selected]
        value = getattr(self.defaults, _attr)
        if kind == "bool":
            self.edit_text = "Yes" if value else "No"
        else:
            self.edit_text = str(value)

    def handle(self, key: Key) -> None:
        self.status = ""
        if key.name == "F10":
            self._commit()
            self.saved = True
            self.close = True
            return
        if key.name == "ESC":
            self.close = True
            return
        if key.name == "UP":
            self._commit()
            self.selected = max(0, self.selected - 1)
            self._load()
            return
        if key.name == "DOWN":
            self._commit()
            self.selected = min(len(self.FIELDS) - 1, self.selected + 1)
            self._load()
            return
        name, _attr, kind = self.FIELDS[self.selected]
        if key.name == "ENTER":
            if kind == "bool":
                self.edit_text = "No" if self.edit_text == "Yes" else "Yes"
            elif kind == "choice" and name == "Date format":
                self.edit_text = ("European"
                                  if self.edit_text == "American"
                                  else "American")
            elif kind == "choice" and name == "Pattern matching":
                index = (PATTERNS.index(self.edit_text.lower())
                         if self.edit_text.lower() in PATTERNS else 0)
                self.edit_text = PATTERNS[(index + 1) % len(PATTERNS)]
            else:
                self._commit()
                self.selected = min(len(self.FIELDS) - 1, self.selected + 1)
                self._load()
            return
        if key.name == "BACKSPACE":
            self.edit_text = self.edit_text[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self.edit_text += text

    def _commit(self) -> None:
        _name, attr, kind = self.FIELDS[self.selected]
        value = self.edit_text
        if kind == "bool":
            setattr(self.defaults, attr, value.strip().upper().startswith("Y"))
        elif kind == "int":
            try:
                number = int(value.strip())
            except ValueError:
                self.status = "Screen zoom: a number from 50 to 200."
                return
            self.defaults.screen_zoom = clamp_zoom(number)
        elif attr == "pattern":
            lower = value.strip().lower()
            if lower in PATTERNS:
                self.defaults.pattern = lower
            else:
                self.status = "Pattern matching: Exact, Case or Case-insensitive."
        elif attr == "date_format":
            self.defaults.date_format = ("European"
                                         if value.lower().startswith("e")
                                         else "American")
        elif attr == "date_separator":
            self.defaults.date_separator = (value or "/")[:1]
        else:
            setattr(self.defaults, attr, value.strip())

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        for index, (label, _attr, _kind) in enumerate(self.FIELDS):
            row = 2 + index
            active = index == self.selected
            value = getattr(self.defaults, _attr)
            if _kind == "bool":
                text = "Yes" if value else "No"
            else:
                text = str(value)
            if active:
                text = self.edit_text
            buffer.write(row, 2, f"{label:<24}:",
                         fg=self.theme.accent if active else self.theme.label,
                         bg=self.theme.bg, bold=active)
            buffer.write(row, 28, clip_text(text, 40),
                         fg=self.theme.selected_fg if active else self.theme.text,
                         bg=self.theme.selected_bg if active else self.theme.bg)
        draw_status_line(buffer, self.theme, self.status or
                         "ENTER changes or advances; F10 saves")
        draw_help_line(buffer, self.theme,
                       "Defaults apply to dates, comparison, entry, locks and zoom.")
        regions = draw_menu_line(buffer, self.theme,
                                 [("F10", "Save"), ("ESC", "Cancel")])
        return View(buffer, regions)


@dataclass
class PrinterSession:
    """26 driver A–Z: elenco, scelta, modifica e cancellazione."""

    config: PrinterConfig
    theme: Theme = NEWPORT
    stage: str = "list"
    selected: int = 0
    driver: PrinterDriver | None = None
    field_index: int = 0
    edit_text: str = ""
    model_index: int = 0
    letter_text: str = ""
    status: str = ""
    close: bool = False
    saved: bool = False
    help_topic: str = "other"

    FIELDS = (
        ("Name", "name", "text"),
        ("Lines per page", "lines_per_page", "int"),
        ("Page advance", "page_advance", "choice"),
        ("Left margin", "margin_left", "int"),
        ("Right margin", "margin_right", "int"),
        ("Top margin", "margin_top", "int"),
        ("Bottom margin", "margin_bottom", "int"),
        ("Set-up codes", "setup", "codes"),
        ("Close-out codes", "close", "codes"),
        ("Normal codes", "normal", "codes"),
        ("Bold codes", "bold", "codes"),
        ("Italic codes", "italic", "codes"),
        ("Uline on codes", "underline_on", "codes"),
        ("Uline off codes", "underline_off", "codes"),
        ("Compressed on", "compressed_on", "codes"),
        ("Compressed off", "compressed_off", "codes"),
        ("Page 1 codes", "page1", "codes"),
        ("New page codes", "new_page", "codes"),
        ("Column offset", "column_offset", "int"),
        ("Port", "port", "text"),
        ("Description", "description", "text"),
    )

    @property
    def title(self) -> str:
        if self.stage == "list":
            return "Printer Configurations"
        if self.stage == "model":
            return "Supported Printers"
        if self.stage == "letter":
            return "Select a Printer Letter"
        return f"Printer Configuration {self.driver.letter if self.driver else ''}"

    def handle(self, key: Key) -> None:
        self.status = ""
        if self.stage == "list":
            self._handle_list(key)
        elif self.stage == "letter":
            self._handle_letter(key)
        elif self.stage == "model":
            self._handle_model(key)
        else:
            self._handle_edit(key)

    def _handle_list(self, key: Key) -> None:
        letters = sorted(self.config.drivers)
        if key.name == "UP" and letters:
            self.selected = max(0, self.selected - 1)
        elif key.name == "DOWN" and letters:
            self.selected = min(len(letters) - 1, self.selected + 1)
        elif key.name == "F2":
            self.stage = "letter"
            self.letter_text = ""
        elif key.name == "ENTER" and letters:
            self.driver = self.config.drivers[letters[self.selected]]
            self.stage = "edit"
            self.field_index = 0
            self._load()
        elif key.name == "F5" and letters:
            self.config.erase(letters[self.selected])
            self.selected = max(0, min(self.selected,
                                       max(0, len(self.config.drivers) - 1)))
        elif key.name == "F6" and letters:
            self.config.select(letters[self.selected])
            self.status = f"Default printer: {self.config.default}"
        elif key.name in ("F10", "ESC"):
            self.saved = True
            self.close = True

    def _handle_letter(self, key: Key) -> None:
        if key.name == "ENTER":
            letter = self.letter_text.strip().upper()[:1]
            if letter not in LETTERS:
                self.status = "Choose a letter A-Z."
                return
            self.driver = PrinterDriver(letter)
            self.stage = "model"
            self.model_index = 0
            return
        if key.name == "ESC":
            self.stage = "list"
            return
        if key.name == "BACKSPACE":
            self.letter_text = self.letter_text[:-1]
            return
        text = character(key)
        if text:
            self.letter_text += text.upper()

    def _handle_model(self, key: Key) -> None:
        if key.name == "UP":
            self.model_index = max(0, self.model_index - 1)
        elif key.name == "DOWN":
            self.model_index = min(len(PRINTER_MODELS) - 1,
                                   self.model_index + 1)
        elif key.name == "PGUP":
            self.model_index = max(0, self.model_index - 10)
        elif key.name == "PGDN":
            self.model_index = min(len(PRINTER_MODELS) - 1,
                                   self.model_index + 10)
        elif key.name == "ESC":
            self.stage = "letter"
        elif key.name == "ENTER" and self.driver is not None:
            model = PRINTER_MODELS[self.model_index]
            self.driver = PrinterDriver.from_model(self.driver.letter, model)
            self.config.install(self.driver)
            self.stage = "edit"
            self.field_index = 0
            self._load()

    def _handle_edit(self, key: Key) -> None:
        if key.name == "F10":
            self._commit()
            if self.driver is not None:
                self.config.install(self.driver)
            self.stage = "list"
            self.driver = None
            return
        if key.name == "ESC":
            self.stage = "list"
            self.driver = None
            return
        if key.name == "UP":
            self._commit()
            self.field_index = max(0, self.field_index - 1)
            self._load()
            return
        if key.name == "DOWN":
            self._commit()
            self.field_index = min(len(self.FIELDS) - 1,
                                   self.field_index + 1)
            self._load()
            return
        if key.name == "ENTER":
            _label, attr, kind = self.FIELDS[self.field_index]
            if kind == "choice":
                index = PAGE_ADVANCE.index(self.edit_text) \
                    if self.edit_text in PAGE_ADVANCE else 0
                self.edit_text = PAGE_ADVANCE[(index + 1) % len(PAGE_ADVANCE)]
            else:
                self._commit()
                self.field_index = min(len(self.FIELDS) - 1,
                                       self.field_index + 1)
                self._load()
            return
        if key.name == "BACKSPACE":
            self.edit_text = self.edit_text[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self.edit_text += text

    def _load(self) -> None:
        if self.driver is None:
            self.edit_text = ""
            return
        _label, attr, kind = self.FIELDS[self.field_index]
        value = getattr(self.driver, attr)
        if kind == "codes":
            self.edit_text = ",".join(str(code) for code in value)
        else:
            self.edit_text = str(value)

    def _commit(self) -> None:
        if self.driver is None:
            return
        _label, attr, kind = self.FIELDS[self.field_index]
        value = self.edit_text
        try:
            if kind == "int":
                setattr(self.driver, attr, int(value or "0"))
            elif kind == "codes":
                codes = []
                for part in value.replace(" ", "").split(","):
                    if part:
                        codes.append(int(part))
                setattr(self.driver, attr, codes)
            elif kind == "choice":
                if value in PAGE_ADVANCE:
                    self.driver.page_advance = value
                else:
                    self.status = "Page advance: Formfeed, Sheetfeeder or Linefeed."
            else:
                setattr(self.driver, attr, value)
            PrinterDriver.__post_init__(self.driver)
        except (ValueError, PrinterError) as exc:
            self.status = str(exc)

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        if self.stage == "list":
            letters = sorted(self.config.drivers)
            if not letters:
                buffer.write(2, 2, "No printer drivers installed.",
                             fg=self.theme.text, bg=self.theme.bg)
            for index, letter in enumerate(letters):
                driver = self.config.drivers[letter]
                active = index == self.selected
                marker = "\u25b8" if self.config.default == letter else " "
                text = f"{marker} {letter}  {driver.name:<30} " \
                       f"{driver.lines_per_page:>3} lines  {driver.page_advance}"
                if active:
                    buffer.fill_rect(2 + index, 1, 1, SCREEN_WIDTH - 2, " ",
                                     fg=self.theme.selected_fg,
                                     bg=self.theme.selected_bg)
                buffer.write(2 + index, 2, clip_text(text, SCREEN_WIDTH - 4),
                             fg=self.theme.selected_fg if active else self.theme.text,
                             bg=self.theme.selected_bg if active else self.theme.bg)
            draw_help_line(buffer, self.theme,
                           "F2 installs a driver, F5 erases, F6 selects default.")
            keys = [("F2", "Install"), ("F5", "Erase"), ("F6", "Default"),
                    ("F10", "Save")]
        elif self.stage == "letter":
            buffer.write(4, 2, "Install printer driver:",
                         fg=self.theme.label, bg=self.theme.bg)
            buffer.write(5, 2, self.letter_text or "_",
                         fg=self.theme.selected_fg, bg=self.theme.selected_bg)
            draw_help_line(buffer, self.theme,
                           "Choose an unused letter A-Z; ENTER continues.")
            keys = [("F10", "Continue"), ("ESC", "Cancel")]
        elif self.stage == "model":
            for index, model in enumerate(PRINTER_MODELS):
                row = 2 + index
                if row >= STATUS_ROW:
                    break
                active = index == self.model_index
                if active:
                    buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ",
                                     fg=self.theme.selected_fg,
                                     bg=self.theme.selected_bg)
                buffer.write(row, 2, clip_text(model.name, 40),
                             fg=self.theme.selected_fg if active else self.theme.text,
                             bg=self.theme.selected_bg if active else self.theme.bg)
            draw_help_line(buffer, self.theme,
                           "Select a supported printer; ENTER edits its codes.")
            keys = [("F10", "Continue"), ("ESC", "Cancel")]
        else:
            for index, (label, _attr, _kind) in enumerate(self.FIELDS):
                row = 2 + index
                active = index == self.field_index
                value = self.edit_text if active else (
                    ",".join(str(code) for code in getattr(self.driver, _attr))
                    if _kind == "codes" else str(getattr(self.driver, _attr)))
                buffer.write(row, 2, f"{label:<20}:",
                             fg=self.theme.accent if active else self.theme.label,
                             bg=self.theme.bg, bold=active)
                buffer.write(row, 24, clip_text(value, 60),
                             fg=self.theme.selected_fg if active else self.theme.text,
                             bg=self.theme.selected_bg if active else self.theme.bg)
            draw_help_line(buffer, self.theme,
                           "Codes are decimal, separated by commas.")
            keys = [("F10", "Save"), ("ESC", "Cancel")]
        draw_status_line(buffer, self.theme, self.status or
                         f"{len(self.config.drivers)} driver(s) installed")
        regions = draw_menu_line(buffer, self.theme, keys)
        return View(buffer, regions)


@dataclass
class ColorSession:
    """Colori del database o set corrente."""

    workspace: Workspace
    owner: str
    base_theme: Theme = NEWPORT
    theme: Theme = NEWPORT
    colors: dict[str, int] = field(default_factory=dict)
    selected: int = 0
    status: str = ""
    close: bool = False
    saved: bool = False
    help_topic: str = "other"

    def __post_init__(self) -> None:
        self.colors = defaults_palette()
        self.colors.update(load_colors(self.workspace, self.owner))

    @property
    def title(self) -> str:
        return f"Set Screen Colors - {self.owner}"

    def handle(self, key: Key) -> None:
        self.status = ""
        if key.name in ("UP",):
            self.selected = max(0, self.selected - 1)
        elif key.name == "DOWN":
            self.selected = min(len(COLOR_TOKENS) - 1, self.selected + 1)
        elif key.name in ("SPACE", "ENTER", "RIGHT"):
            name = COLOR_TOKENS[self.selected][0]
            self.colors[name] = cycle_color(self.colors.get(name, 7),
                                            1 if key.name != "LEFT" else -1)
        elif key.name == "LEFT":
            name = COLOR_TOKENS[self.selected][0]
            self.colors[name] = cycle_color(self.colors.get(name, 7), -1)
        elif key.name == "F4":
            self.colors = defaults_palette()
        elif key.name == "F10":
            save_colors(self.workspace, self.owner, self.colors)
            self.saved = True
            self.close = True
        elif key.name == "ESC":
            self.close = True

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        for index, (label, _field) in enumerate(COLOR_TOKENS):
            row = 2 + index
            active = index == self.selected
            value = self.colors.get(label, 7)
            text = f"{label:<24} {value:>2}"
            if active:
                buffer.fill_rect(row, 1, 1, 60, " ",
                                 fg=self.theme.selected_fg,
                                 bg=self.theme.selected_bg)
            buffer.write(row, 2, text,
                         fg=self.theme.selected_fg if active else self.theme.text,
                         bg=self.theme.selected_bg if active else self.theme.bg)
            buffer.put(row, 40, Cell(" ", fg=0, bg=value))
        draw_status_line(buffer, self.theme,
                         self.status or "SPACE/LEFT/RIGHT cycle colors")
        draw_help_line(buffer, self.theme,
                       "Colors are saved per database or set; F4 restores Newport.")
        regions = draw_menu_line(buffer, self.theme,
                                 [("SPACE", "Change"), ("F4", "Defaults"),
                                  ("F10", "Save"), ("ESC", "Cancel")])
        return View(buffer, regions)


@dataclass
class DocumentationSession:
    """Selezione e generazione dei report di documentazione."""

    workspace: Workspace
    script_store: ScriptStore
    application_store: ApplicationStore
    output_dir: Path
    theme: Theme = NEWPORT
    stage: str = "type"
    selected: int = 0
    type_index: int = 0
    target: str = ""
    width: int = 80
    graphics: bool = True
    output: object | None = None
    title: str = ""
    status: str = ""
    close: bool = False
    saved: bool = False
    pdf_path: Path | None = None
    help_topic: str = "other"

    TYPES = ("Database structure", "Set structure", "Field rules",
             "Application", "Script")

    @property
    def title_text(self) -> str:
        return "Documentation Program"

    def targets(self) -> list[str]:
        if self.type_index in (0, 2):
            return self.workspace.names()
        if self.type_index == 1:
            return self.workspace.set_names()
        if self.type_index == 3:
            return self.application_store.names()
        return self.script_store.names()

    def handle(self, key: Key) -> None:
        self.status = ""
        if key.name == "ESC":
            if self.stage == "type":
                self.close = True
            elif self.stage == "target":
                self.stage = "type"
            elif self.stage == "options":
                self.stage = "target"
            else:
                self.stage = "options"
            return
        if self.stage == "type":
            if key.name == "UP":
                self.selected = max(0, self.selected - 1)
            elif key.name == "DOWN":
                self.selected = min(len(self.TYPES) - 1, self.selected + 1)
            elif key.name == "ENTER":
                self.type_index = self.selected
                self.stage = "target"
                self.selected = 0
            return
        if self.stage == "target":
            targets = self.targets()
            if key.name == "UP" and targets:
                self.selected = max(0, self.selected - 1)
            elif key.name == "DOWN" and targets:
                self.selected = min(len(targets) - 1, self.selected + 1)
            elif key.name == "ENTER" and targets:
                self.target = targets[self.selected]
                self.stage = "options"
            return
        if self.stage == "options":
            if key.name == "UP":
                self.selected = max(0, self.selected - 1)
            elif key.name == "DOWN":
                self.selected = min(1, self.selected + 1)
            elif key.name == "ENTER":
                if self.selected == 0:
                    self.width = max(40, min(240, self.width + 10))
                else:
                    self.graphics = not self.graphics
            elif key.name == "F10":
                self._generate()
            return
        if self.stage == "preview":
            if key.name in ("F10", "ESC"):
                self.close = True
            elif key.name == "P":
                self._write_pdf()

    def _generate(self) -> None:
        try:
            if self.type_index == 0:
                database = self.workspace.get(self.target)
                if database is None:
                    raise ValueError(f"Database {self.target} not found.")
                self.output = database_structure(database, width=self.width)
                self.title = f"Structure of {self.target}"
            elif self.type_index == 1:
                definition = self.workspace.get_set(self.target)
                if definition is None:
                    raise ValueError(f"Set {self.target} not found.")
                self.output = set_structure(definition, width=self.width)
                self.title = f"Set structure {self.target}"
            elif self.type_index == 2:
                database = self.workspace.get(self.target)
                if database is None:
                    raise ValueError(f"Database {self.target} not found.")
                self.output = field_rules_report(database, width=self.width)
                self.title = f"Field rules {self.target}"
            elif self.type_index == 3:
                app = self.application_store.get(self.target)
                self.output = application_report(app, width=self.width)
                self.title = f"Application {self.target}"
            else:
                script = self.script_store.get(self.target)
                self.output = script_report(script, width=self.width)
                self.title = f"Script {self.target}"
        except Exception as exc:
            self.status = str(exc)
            return
        self.stage = "preview"
        self.status = "P writes the PDF; F10 closes."

    def _write_pdf(self) -> None:
        if self.output is None:
            return
        target = self.output_dir / f"DOC-{self.target}.PDF"
        try:
            self.pdf_path = write_document(self.output, target, self.title)
        except OSError as exc:
            self.status = f"Cannot write PDF: {exc}"
            return
        self.status = f"PDF written to {self.pdf_path}"

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title_text, self.theme)
        if self.stage == "type":
            for index, label in enumerate(self.TYPES):
                row = 2 + index
                active = index == self.selected
                if active:
                    buffer.fill_rect(row, 1, 1, 50, " ",
                                     fg=self.theme.selected_fg,
                                     bg=self.theme.selected_bg)
                buffer.write(row, 2, label,
                             fg=self.theme.selected_fg if active else self.theme.text,
                             bg=self.theme.selected_bg if active else self.theme.bg)
        elif self.stage == "target":
            targets = self.targets()
            if not targets:
                buffer.write(2, 2, "Nothing to document.",
                             fg=self.theme.text, bg=self.theme.bg)
            for index, name in enumerate(targets):
                row = 2 + index
                if row >= STATUS_ROW:
                    break
                active = index == self.selected
                if active:
                    buffer.fill_rect(row, 1, 1, 60, " ",
                                     fg=self.theme.selected_fg,
                                     bg=self.theme.selected_bg)
                buffer.write(row, 2, name,
                             fg=self.theme.selected_fg if active else self.theme.text,
                             bg=self.theme.selected_bg if active else self.theme.bg)
        elif self.stage == "options":
            buffer.write(2, 2, f"Target: {self.target}",
                         fg=self.theme.label, bg=self.theme.bg)
            values = (f"Page width: {self.width}",
                      f"Graphic characters: {'Yes' if self.graphics else 'No'}")
            for index, text in enumerate(values):
                row = 4 + index
                active = index == self.selected
                if active:
                    buffer.fill_rect(row, 1, 1, 60, " ",
                                     fg=self.theme.selected_fg,
                                     bg=self.theme.selected_bg)
                buffer.write(row, 2, text,
                             fg=self.theme.selected_fg if active else self.theme.text,
                             bg=self.theme.selected_bg if active else self.theme.bg)
        else:
            if self.output is not None and self.output.pages:
                for index, line in enumerate(self.output.pages[0].lines[:36]):
                    buffer.write(2 + index, 1, clip_text(line, 128),
                                 fg=self.theme.text, bg=self.theme.bg)
        draw_status_line(buffer, self.theme, self.status or
                         "ENTER selects; F10 generates or closes")
        draw_help_line(buffer, self.theme,
                       "Documentation reports use the active printer driver.")
        regions = draw_menu_line(buffer, self.theme,
                                 [("ENTER", "Select"), ("P", "PDF"),
                                  ("F10", "Continue"), ("ESC", "Back")])
        return View(buffer, regions)


__all__ = [
    "ColorSession", "DefaultsSession", "DocumentationSession",
    "PrinterSession",
]
