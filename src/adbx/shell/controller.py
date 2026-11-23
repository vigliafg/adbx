"""Controllore del guscio: stato, schermate, tastiera e mouse.

È il punto in cui gli eventi diventano comandi. Lo stesso `handle(Key)` sarà
usato dal motore di script (O10) per digitare sequenze: qui non esiste altra
strada di input.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..app.model import AppError, AppItem, Application, outline
from ..app.protection import is_protected
from ..app.runtime import ApplicationRuntime
from ..app.store import ApplicationStore
from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW
from ..data import indexing
from ..data import rules as field_rules
from ..data.expressions import Context
from ..data.indexing import RECORD_NUMBER, SEARCH_PREFIX
from ..data.labels_engine import render_labels
from ..data.letters import render_letters
from ..data.report_engine import render_report
from ..data.workspace import Database, Workspace, WorkspaceError
from ..screen.keys import Key, character
from ..screen.keys import parse as parse_key
from ..script.engine import (
    ScriptEngine,
    ScriptError,
    ScriptRunner,
    keys_from_source,
)
from ..script.model import (
    KIND_DIALOG,
    KIND_KEYSTROKE,
    KIND_MENU,
    Script,
)
from ..script.store import ScriptStore, script_template
from ..script.variables import clean_name
from . import screens
from .applications import (
    ApplicationEditor,
    ApplicationSession,
    BannerPainter,
    MacroEditor,
    ProtectionSession,
)
from .designer import DesignerSession
from .files import strip_wildcard
from .forms import FormDesigner
from .global_update import GlobalSession
from .help import link_spans, topic, wrap_topic
from .indexes import IndexSession, RangeSession
from .labels import LabelDesigner
from .letters import LetterEditor
from .records import RecordSession
from .relational import RelationalSession
from .reports import ReportDesigner, ReportPreview
from .rules import RulesSession
from .script_host import ShellScriptHost
from .scripts import (
    DialogDesigner,
    DialogRuntime,
    MenuBarDesigner,
    ScriptDebugSession,
    ScriptEditor,
)
from .searching import SearchSession
from .sets import SetDesigner, SetSession
from .state import ShellState, default_root, demo_state
from .theme import NEWPORT, Theme
from .transfer import TransferSession
from .utilities import UtilitySession
from .widgets import View

INPUT_LABEL = "Enter name of the database/set"
INPUT_COL = 1 + len(INPUT_LABEL) + 3
LIST_TOP = screens.LIST_TOP
LIST_VISIBLE = STATUS_ROW - LIST_TOP

DESKTOP_ITEMS: tuple[tuple[str, str | None], ...] = (
    ("Open a database", "open"),
    ("Open a set", "open-set"),
    ("Switch databases", "switch"),
    ("Close a database", "close"),
    ("Save current desktop", "save"),
    ("Retrieve a desktop", "retrieve"),
    ("Erase a desktop", "erase"),
)

COMMAND_WAVES = {
    "print": "O7",
    "search": "O3",
    "indexes": "O3",
    "global": "O9",
    "layouts": "O6",
    "applications": "O11",
    "other": "O12",
}

RECORD_ITEMS: tuple[tuple[str, str], ...] = (
    ("View records", "view"),
    ("Enter records", "enter"),
    ("Change records", "change"),
    ("Browse records", "browse"),
    ("Delete/recall records", "recall"),
)

DESIGN_ITEMS: tuple[tuple[str, str], ...] = (
    ("Create database", "create"),
    ("Modify database", "modify"),
    ("Field rules", "field-rules"),
    ("Set commands", "sets"),
    ("Erase database", "erase"),
    ("Password", "password"),
)

SET_ITEMS: tuple[tuple[str, str], ...] = (
    ("Create a set design", "create"),
    ("Modify a set design", "modify"),
    ("Erase a set design", "erase"),
)

LAYOUT_ITEMS: tuple[tuple[str, str], ...] = (
    ("Forms", "forms"),
    ("Browse tables", "browse-tables"),
    ("Reports", "reports"),
    ("Mail labels", "labels"),
    ("Letters", "letters"),
)

LABEL_ITEMS: tuple[tuple[str, str], ...] = (
    ("Create/edit a mail label", "create"),
    ("Borrow a mail label", "borrow"),
    ("Erase a mail label", "erase"),
)

LETTER_ITEMS: tuple[tuple[str, str], ...] = (
    ("Create/edit a form letter", "create"),
    ("Erase a form letter", "erase"),
)

REPORT_ITEMS: tuple[tuple[str, str], ...] = (
    ("Create/edit a report", "create"),
    ("Borrow a report", "borrow"),
    ("Erase a report", "erase"),
)

PRINT_ITEMS: tuple[tuple[str, str], ...] = (
    ("Report", "report"),
    ("Form", "form"),
    ("Browse table", "browse"),
    ("Mail labels", "labels"),
    ("Letters", "letters"),
)

FORM_ITEMS: tuple[tuple[str, str], ...] = (
    ("Create/edit a form", "create"),
    ("Select active form", "select"),
    ("Erase a form", "erase"),
)

RULES_ITEMS: tuple[tuple[str, str], ...] = (
    ("Create/edit field rules", "edit"),
    ("Re-evaluate field rules", "reevaluate"),
    ("Erase field rules", "erase"),
)

UTILITY_ITEMS: tuple[tuple[str, str], ...] = (
    ("Copy database", "copy"),
    ("Append to database", "append"),
    ("Summarize database", "summarize"),
    ("Pack database", "pack"),
    ("Zap database", "zap"),
    ("Cross Tabulation", "crosstab"),
    ("Relational commands", "relational"),
    ("Import data", "import"),
    ("Export data", "export"),
)

RELATIONAL_ITEMS: tuple[tuple[str, str], ...] = (
    ("Post database", "post"),
    ("Join database", "join"),
    ("Intersect database", "intersect"),
    ("Subtract database", "subtract"),
)

INDEX_ITEMS: tuple[tuple[str, str], ...] = (
    ("Primary index selection", "primary"),
    ("Create an index", "create"),
    ("Update indexes", "update"),
    ("Attach/detach an index", "attach"),
    ("Erase an index", "erase"),
    ("Create/edit a range", "range"),
    ("Retrieve a range", "retrieve-range"),
)

SEARCH_ITEMS: tuple[tuple[str, str], ...] = (
    ("Create/edit a saved search/sort", "create"),
    ("Run a saved search/sort", "run"),
    ("One-time search/sort", "one-time"),
    ("Erase a saved search/sort", "erase"),
    ("Search/Sort list history", "history"),
)

OTHER_ITEMS: tuple[tuple[str, str], ...] = (
    ("Pattern matching", "pattern"),
)

GLOBAL_ITEMS: tuple[tuple[str, str], ...] = (
    ("Update a field", "update-field"),
    ("Change case", "case"),
    ("Delete range of records", "delete-range"),
    ("Undelete range of records", "undelete-range"),
    ("Delete duplicate records", "duplicates"),
)

SCRIPTS_ITEMS: tuple[tuple[str, str], ...] = (
    ("Modify a script", "modify"),
    ("create Keystroke script", "create-keystroke"),
    ("create Dialog script", "create-dialog"),
    ("create menu baR script", "create-menu"),
    ("Erase a script", "erase"),
    ("Play a script", "play"),
    ("Set script path", "path"),
    ("display script Variables", "variables"),
    ("deBug a script", "debug"),
)


APPLICATION_ITEMS: tuple[tuple[str, str], ...] = (
    ("Run an application", "run"),
    ("Create/edit application", "edit"),
    ("Erase an application", "erase"),
    ("Prevent/allow file alterations", "protect"),
)


def _key_source(key: Key) -> str:
    """Rappresentazione di un tasto nel testo di uno script registrato."""
    char = character(key)
    if char and not key.ctrl and not key.alt:
        return char
    parts = []
    if key.ctrl:
        parts.append("CTRL")
    if key.alt:
        parts.append("ALT")
    if key.shift:
        parts.append("SHIFT")
    parts.append(key.name)
    return "{" + "-".join(parts) + "}"


def _keys_from_source(text: str):
    return keys_from_source(text)


@dataclass
class Overlay:
    kind: str
    text: str = ""
    topic_id: str = "main_menu"
    scroll: int = 0
    link: int = 0
    selected: int = 0
    stack: list[str] = field(default_factory=list)
    items: list[tuple[str, str]] = field(default_factory=list)
    target: str = "desktop"
    input_text: str = ""
    input_cursor: int = 0
    action: str = ""
    action_title: str = "Prompt"
    secret: bool = False
    markers: list[str] = field(default_factory=list)
    chosen: list[str] = field(default_factory=list)


class ShellController:
    """Macchina a stati del guscio, indipendente da Qt."""

    def __init__(self, root: str | Path | None = None, *,
                 open_path: str | Path | None = None,
                 application: str | None = None,
                 theme: Theme = NEWPORT) -> None:
        self.state = ShellState(Path(root).expanduser() if root else default_root())
        self.theme = theme
        self.menu_index = 0
        self.cursor = 0
        self.first = 0
        self.input_text = ""
        self.input_cursor = 0
        self.structure_page = 0
        self.overlay: Overlay | None = None
        self.quit = False
        self.workspace: Workspace | None = None
        self.database: Database | None = None
        self.records: RecordSession | None = None
        self.designer: DesignerSession | None = None
        self.clipboard: list[str] = [""]
        self.pending_path: Path | None = None
        self.index_session: IndexSession | None = None
        self.range_session: RangeSession | None = None
        self.search_session: SearchSession | None = None
        self.rules_session: RulesSession | None = None
        self.active_set = None
        self.set_records: SetSession | None = None
        self.set_designer: SetDesigner | None = None
        self.form_designer: FormDesigner | None = None
        self.report_designer: ReportDesigner | None = None
        self.report_preview: ReportPreview | None = None
        self.label_designer: LabelDesigner | None = None
        self.letter_editor: LetterEditor | None = None
        self.utility_session: UtilitySession | None = None
        self.relational_session: RelationalSession | None = None
        self.transfer_session: TransferSession | None = None
        self.global_session: GlobalSession | None = None
        self.script_editor: ScriptEditor | None = None
        self.dialog_designer: DialogDesigner | None = None
        self.menu_designer: MenuBarDesigner | None = None
        self.script_debug: ScriptDebugSession | None = None
        self.dialog_runtime: DialogRuntime | None = None
        self.script_directory: Path | None = None
        self.script_engine: ScriptEngine | None = None
        self.application_store_directory: Path | None = None
        self.application_editor: ApplicationEditor | None = None
        self.application_session: ApplicationSession | None = None
        self.application_runtime: ApplicationRuntime | None = None
        self.banner_painter: BannerPainter | None = None
        self.macro_editor: MacroEditor | None = None
        self.protection_session: ProtectionSession | None = None
        self.application_return_base = "menu"
        self.editing_application_macro: AppItem | None = None
        self.pending_app_password = False
        self.pending_app_escape = False
        self._app_script_directory: Path | None = None
        self.pending_script_kind = ""
        self.pending_script_name = ""
        self.pending_script_description = ""
        self.recording: list[str] | None = None
        self.recording_name = ""
        self.recording_source = ""
        self.script_return_base = "menu"
        self.script_writes: list[tuple[int, int, str]] = []
        self.script_beeps = 0
        self.script_tones: list[tuple[int, int]] = []
        self.script_pauses = 0
        self.script_waits: list[tuple] = []
        self.script_screen_mode = ""
        self.script_deferred: list[str] = []
        self.script_mouse: list[tuple] = []
        self.script_cursor = (1, 1)
        self.script_display_dialog: Script | None = None
        self._flushing = False
        self._opening_script = False
        self._in_script = False
        self.pending_index_name = ""
        self.pending_locate_text = ""
        self.pending_replace: list[str] = []
        self.pending_saved_search = ""
        self.overlay_chosen: list[str] = []
        self.return_base = "menu"

        if open_path is not None:
            self._open_entry(Path(open_path))
        else:
            self.state.refresh()
        self.base = "menu" if self.state.current else "directory"
        self.cursor = self.first = self._first_file_index()
        self._sync_input()
        self._autostart()
        if application:
            self._open_application_session_by_name(application)

    # -- accesso alle schermate -----------------------------------------
    def view(self) -> View:
        if self.base == "records" and self.records is not None:
            base = self.records.view()
        elif self.base == "designer" and self.designer is not None:
            base = self.designer.view()
        elif self.base == "index" and self.index_session is not None:
            base = self.index_session.view()
        elif self.base == "range" and self.range_session is not None:
            base = self.range_session.view()
        elif self.base == "search" and self.search_session is not None:
            base = self.search_session.view()
        elif self.base == "rules" and self.rules_session is not None:
            base = self.rules_session.view()
        elif self.base == "setrecords" and self.set_records is not None:
            base = self.set_records.view()
        elif self.base == "setdesigner" and self.set_designer is not None:
            base = self.set_designer.view()
        elif self.base == "formdesigner" and self.form_designer is not None:
            base = self.form_designer.view()
        elif self.base == "reportdesigner" and self.report_designer is not None:
            base = self.report_designer.view()
        elif self.base == "reportpreview" and self.report_preview is not None:
            base = self.report_preview.view()
        elif self.base == "labeldesigner" and self.label_designer is not None:
            base = self.label_designer.view()
        elif self.base == "lettereditor" and self.letter_editor is not None:
            base = self.letter_editor.view()
        elif self.base == "utility" and self.utility_session is not None:
            base = self.utility_session.view()
        elif self.base == "relational" and self.relational_session is not None:
            base = self.relational_session.view()
        elif self.base == "transfer" and self.transfer_session is not None:
            base = self.transfer_session.view()
        elif self.base == "global" and self.global_session is not None:
            base = self.global_session.view()
        elif self.base == "scripteditor" and self.script_editor is not None:
            base = self.script_editor.view()
        elif self.base == "dialogdesigner" and self.dialog_designer is not None:
            base = self.dialog_designer.view()
        elif self.base == "menubardesigner" and self.menu_designer is not None:
            base = self.menu_designer.view()
        elif self.base == "scriptdebugger" and self.script_debug is not None:
            base = self.script_debug.view()
        elif self.base == "scriptdialog" and self.dialog_runtime is not None:
            base = self.dialog_runtime.view()
        elif self.base == "appeditor" and self.application_editor is not None:
            base = self.application_editor.view()
        elif self.base == "appsession" and self.application_session is not None:
            base = self.application_session.view()
        elif self.base == "bannerpainter" and self.banner_painter is not None:
            base = self.banner_painter.view()
        elif self.base == "macroeditor" and self.macro_editor is not None:
            base = self.macro_editor.view()
        elif self.base == "protection" and self.protection_session is not None:
            base = self.protection_session.view()
        elif self.base == "directory":
            base = screens.directory(
                self.state, self.cursor, self.input_text, self.input_cursor,
                self.first, self.theme)
        elif self.base == "structure":
            base = screens.structure(self.state, self.structure_page, self.theme)
        elif self.base == "status":
            base = screens.status_screen(self.state, self.theme)
        else:
            base = screens.main_menu(self.state, self.menu_index, self.theme)
        base = self._script_layer(base)
        return self._with_overlay(base)

    def _script_layer(self, view: View) -> View:
        """Disegna gli effetti dei comandi di script sullo schermo."""
        mode = getattr(self, "script_screen_mode", "")
        writes = list(getattr(self, "script_writes", []))
        if mode == "off":
            view.buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                                  fg=self.theme.text, bg=self.theme.bg)
        for row, col, text in writes:
            if 1 <= row <= SCREEN_HEIGHT and 1 <= col <= SCREEN_WIDTH:
                view.buffer.write(row - 1, col - 1, text[:SCREEN_WIDTH - col + 1],
                                  fg=self.theme.text, bg=self.theme.bg)
        return view

    def dump(self) -> str:
        return self.view().buffer.dump()

    def _with_overlay(self, base: View) -> View:
        overlay = self.overlay
        if overlay is None:
            return base
        if overlay.kind == "message":
            return screens.message_overlay(base, overlay.text, self.theme)
        if overlay.kind == "confirm":
            return screens.confirm_overlay(base, overlay.text, self.theme)
        if overlay.kind == "prompt":
            return screens.prompt_overlay(
                base, overlay.action_title, overlay.text, overlay.input_text,
                overlay.input_cursor, secret=overlay.secret, theme=self.theme)
        if overlay.kind == "submenu":
            title = {
                "records": "View/Enter Records",
                "design": "Database/set Design",
                "utilities": "Utilities",
                "relational": "Relational Commands",
                "indexes": "Indexes/Ranges",
                "search": "Search/Sort Lists",
                "global": "Global Update/Delete",
                "index-mode": "Create an Index",
                "other": "Other",
                "field-rules": "Field Rules",
                "sets": "Set Commands",
                "layouts": "Layouts",
                "forms": "Forms",
                "reports": "Reports",
                "labels": "Mail Labels",
                "letters": "Form Letters",
                "print": "Print",
                "scripts": "Scripts",
                "applications": "Applications",
            }.get(overlay.target, "Desktop Options")
            items = overlay.items or list(DESKTOP_ITEMS)
            return screens.submenu_overlay(base, items, overlay.selected,
                                           self.theme, title=title)
        if overlay.kind == "choose":
            return screens.choose_overlay(
                base, overlay.text, list(overlay.items), overlay.selected,
                self.theme, markers=overlay.markers)
        if overlay.kind == "fields":
            return screens.fields_overlay(
                base, [label for label, _value in overlay.items],
                overlay.chosen, overlay.selected, overlay.text, self.theme)
        if overlay.kind == "search-history":
            history = indexing.search_history(self._active_database(), limit=10)
            return screens.search_history_overlay(
                base, history, overlay.selected, self.theme,
                database=self._active_database())
        if overlay.kind == "history":
            return screens.history_overlay(base, self.state.history,
                                           overlay.selected, self.theme)
        if overlay.kind == "variables":
            return screens.variables_overlay(base, overlay.items,
                                             overlay.selected, self.theme)
        if overlay.kind == "help":
            view, _spans, _positions = screens.help_overlay(
                base, overlay.topic_id, scroll=overlay.scroll,
                link_index=overlay.link, theme=self.theme)
            return view
        return base

    # -- input -----------------------------------------------------------
    def handle(self, key: Key) -> None:
        if self.recording is not None:
            if key.alt and key.name == "F3":
                self._stop_recording()
                return
            self.recording.append(_key_source(key))
        if key.ctrl and key.name.startswith("F"):
            try:
                number = int(key.name[1:])
            except ValueError:
                number = 0
            if 1 <= number <= 10 and self._play_hot_key(number):
                return
        if key.alt and key.name == "F1":
            self._quick_record()
            return
        if key.alt and key.name == "F2":
            self._play_script("UNTITLED")
            return
        if key.alt and key.name == "F3":
            self._open_scripts_menu()
            return
        if key.alt and key.name == "F4":
            self._script_choose("play-script", "Play a script")
            return
        if key.alt and key.name == "F10":
            self._to_main_menu()
            return
        if self.overlay is not None:
            self._handle_overlay(key)
            return
        if self.base == "records":
            self._handle_records(key)
        elif self.base == "designer":
            self._handle_designer(key)
        elif self.base == "index":
            self._handle_index_session(key)
        elif self.base == "range":
            self._handle_range_session(key)
        elif self.base == "search":
            self._handle_search_session(key)
        elif self.base == "rules":
            self._handle_rules_session(key)
        elif self.base == "setrecords":
            self._handle_set_records(key)
        elif self.base == "setdesigner":
            self._handle_set_designer(key)
        elif self.base == "formdesigner":
            self._handle_form_designer(key)
        elif self.base == "reportdesigner":
            self._handle_report_designer(key)
        elif self.base == "reportpreview":
            self._handle_report_preview(key)
        elif self.base == "labeldesigner":
            self._handle_label_designer(key)
        elif self.base == "lettereditor":
            self._handle_letter_editor(key)
        elif self.base == "utility":
            self._handle_utility_session(key)
        elif self.base == "relational":
            self._handle_relational_session(key)
        elif self.base == "transfer":
            self._handle_transfer_session(key)
        elif self.base == "global":
            self._handle_global_session(key)
        elif self.base == "scripteditor":
            self._handle_script_editor(key)
        elif self.base == "dialogdesigner":
            self._handle_dialog_designer(key)
        elif self.base == "menubardesigner":
            self._handle_menu_designer(key)
        elif self.base == "scriptdebugger":
            self._handle_script_debug(key)
        elif self.base == "scriptdialog":
            self._handle_dialog_runtime(key)
        elif self.base == "appeditor":
            self._handle_app_editor(key)
        elif self.base == "appsession":
            self._handle_app_session(key)
        elif self.base == "bannerpainter":
            self._handle_banner_painter(key)
        elif self.base == "macroeditor":
            self._handle_macro_editor(key)
        elif self.base == "protection":
            self._handle_protection(key)
        elif self.base == "directory":
            self._handle_directory(key)
        elif self.base == "structure":
            self._handle_structure(key)
        elif self.base == "status":
            self._handle_status(key)
        else:
            self._handle_menu(key)

    def click(self, row: int, col: int, *, button: str = "left",
              double: bool = False) -> None:
        if button == "right":
            self.handle(Key("ESC"))
            return
        if not (0 <= row < SCREEN_HEIGHT and 0 <= col < SCREEN_WIDTH):
            return
        region = self.view().region_at(row, col)
        if region is None:
            return
        kind, _, value = region.action.partition(":")
        if kind == "key":
            self.handle(parse_key(value))
        elif kind == "menu":
            self.menu_index = int(value)
            if double:
                self._execute_menu()
        elif kind == "dir":
            self._move_to(int(value))
            if double:
                entry = self._selected()
                if entry is not None:
                    self._activate(entry)
        elif kind == "input":
            self.input_cursor = max(0, min(col - INPUT_COL, len(self.input_text)))
        elif kind == "submenu" and self.overlay is not None:
            self.overlay.selected = int(value)
            if double:
                self._activate_overlay_item()
        elif kind == "choose" and self.overlay is not None:
            self.overlay.selected = int(value)
            if double:
                self._activate_choose()
        elif kind == "fields" and self.overlay is not None:
            self.overlay.selected = int(value)
            if double:
                self._toggle_field_choice()
        elif kind == "searchhistory" and self.overlay is not None:
            self.overlay.selected = int(value)
            if double:
                self._activate_search_history()
        elif kind == "history" and self.overlay is not None:
            self.overlay.selected = int(value)
            if double:
                self._activate_history()
        elif kind == "prompt" and self.overlay is not None:
            self.overlay.input_cursor = max(
                0, min(col - (SCREEN_WIDTH - 66) // 2 - 3,
                        len(self.overlay.input_text)))
        elif kind == "confirm" and self.overlay is not None:
            self._confirm_action()
        elif kind == "rec" and self.records is not None:
            self.records.click_action(value, double=double)
        elif kind == "dsn" and self.designer is not None:
            self.designer.click_action(value)
        elif kind == "help":
            self._open_help(value, push=True)
        elif kind == "close":
            self.overlay = None

    # -- directory -------------------------------------------------------
    def _entries(self):
        return self.state.listing.entries if self.state.listing else []

    def _first_file_index(self) -> int:
        for index, entry in enumerate(self._entries()):
            if entry.kind == "file":
                return index
        return 0

    def _selected(self):
        entries = self._entries()
        if 0 <= self.cursor < len(entries):
            return entries[self.cursor]
        return None

    def _selected_text(self) -> str:
        entry = self._selected()
        return entry.selectable_text if entry else ""

    def _sync_input(self) -> None:
        text = self._selected_text() or self.state.path_text()
        self.input_text = text
        self.input_cursor = len(text)

    def _move_to(self, index: int) -> None:
        entries = self._entries()
        if not entries:
            self.cursor = self.first = 0
            return
        self.cursor = max(0, min(index, len(entries) - 1))
        self.first = max(0, min(self.first, max(0, len(entries) - LIST_VISIBLE)))
        if self.cursor < self.first:
            self.first = self.cursor
        elif self.cursor >= self.first + LIST_VISIBLE:
            self.first = self.cursor - LIST_VISIBLE + 1
        self._sync_input()

    def _handle_directory(self, key: Key) -> None:
        name = key.name
        entries = self._entries()
        if name == "UP":
            self._move_to(self.cursor - 1)
        elif name == "DOWN":
            self._move_to(self.cursor + 1)
        elif name == "PGUP":
            self._move_to(self.cursor - LIST_VISIBLE)
        elif name == "PGDN":
            self._move_to(self.cursor + LIST_VISIBLE)
        elif name == "HOME":
            self._move_to(0)
        elif name == "END":
            self._move_to(len(entries) - 1)
        elif name == "LEFT":
            self.input_cursor = max(0, self.input_cursor - 1)
        elif name == "RIGHT":
            self.input_cursor = min(len(self.input_text), self.input_cursor + 1)
        elif name == "BACKSPACE":
            if self.input_cursor > 0:
                self.input_text = (self.input_text[:self.input_cursor - 1]
                                   + self.input_text[self.input_cursor:])
                self.input_cursor -= 1
        elif name == "DELETE":
            self.input_text = (self.input_text[:self.input_cursor]
                               + self.input_text[self.input_cursor + 1:])
        elif name in ("ENTER", "F10"):
            self._enter_directory()
        elif name == "ESC":
            self._leave_directory()
        elif name == "F1":
            self._open_help("directory")
        elif name == "F3":
            self._notice("Import is not available yet (wave O9).")
        elif name == "F4":
            self._open_history()
        elif name == "F5":
            self._prompt_create()
        elif name == "F6":
            self._refresh()
        elif name == "F8":
            self.state.detail = not self.state.detail
        elif name == "F9":
            self._notice("DOS access is not available: adbx runs in a window.")
        else:
            char = character(key)
            if char:
                self.input_text = (self.input_text[:self.input_cursor] + char
                                   + self.input_text[self.input_cursor:])
                self.input_cursor += 1

    def _refresh(self) -> None:
        selected = self._selected()
        self.state.refresh()
        if selected is not None:
            index = self.state.listing.index_of(selected.path) if self.state.listing else -1
            if index >= 0:
                self.cursor = index
        self._move_to(self.cursor)

    def _enter_directory(self) -> None:
        text = self.input_text.strip()
        if not text:
            entry = self._selected()
            if entry is not None:
                self._activate(entry)
            return
        self._resolve(text)

    def _activate(self, entry) -> None:
        if entry.kind in ("parent", "dir", "drive"):
            try:
                self.state.change_directory(entry.path)
            except OSError as exc:
                self._notice(f"Cannot open {entry.path}: {exc}")
                return
            self.cursor = self.first = self._first_file_index()
            self._sync_input()
        elif entry.kind == "file":
            self._open_entry(entry.path)

    def _resolve(self, text: str) -> None:
        expanded = os.path.expanduser(text)
        if expanded in (".", ".."):
            target = self.state.root / expanded
            try:
                self.state.change_directory(target)
            except OSError as exc:
                self._notice(str(exc))
            else:
                self.cursor = self.first = 0
                self._sync_input()
            return
        if "*" in expanded or "?" in expanded:
            directory, pattern = strip_wildcard(expanded)
            target = Path(directory).expanduser() if directory else self.state.root
            if not target.is_absolute():
                target = self.state.root / target
            try:
                self.state.change_directory(target, pattern or "*")
            except OSError as exc:
                self._notice(f"Cannot open {target}: {exc}")
            else:
                self.cursor = self.first = 0
                self._sync_input()
            return
        path = Path(expanded)
        if not path.is_absolute():
            path = self.state.root / path
        if path.is_dir():
            try:
                self.state.change_directory(path)
            except OSError as exc:
                self._notice(str(exc))
            else:
                self.cursor = self.first = 0
                self._sync_input()
            return
        if not path.exists() and not path.suffix:
            path = path.with_suffix(".DBF")
        if path.exists():
            self._open_entry(path)
        else:
            self._notice(f"File not found: {path}")

    def _open_entry(self, path: Path) -> None:
        ext = path.suffix.lstrip(".").upper()
        if ext == "SET":
            workspace = Workspace(path.parent)
            self.workspace = workspace
            if self._activate_set(path.stem.upper()):
                self.state.change_directory(path.parent)
                self.base = "menu"
                self.menu_index = 0
                self.overlay = None
                self._sync_input()
            return
        try:
            current = self.state.open(path)
        except (OSError, ValueError) as exc:
            self._notice(f"Cannot open {path.name}: {exc}")
            return
        database = self._open_database(path)
        if database is None:
            return
        self.state.change_directory(path.parent)
        self.base = "menu"
        self.menu_index = 0
        self.overlay = None
        self._sync_input()
        if database.locked:
            self.pending_path = path
            self._prompt_unlock(database)
        elif current.records is None:
            self._notice(f"Opened {current.name} (record count unavailable).")
        if not database.locked:
            self._play_open_script(database.name)

    def _open_database(self, path: Path) -> Database | None:
        self.active_set = None
        self.state.set_name = ""
        try:
            workspace = Workspace(path.parent)
            database = workspace.open_database(path)
        except (WorkspaceError, OSError) as exc:
            self._notice(f"Cannot open {path.name}: {exc}")
            return None
        self.workspace = workspace
        self.database = database
        self.state.database = database
        return database

    def _leave_directory(self) -> None:
        if self.input_text != self._selected_text():
            self._sync_input()
            return
        if self.state.current is not None:
            self.base = "menu"
        else:
            self._notice("Select a database or set first.")

    # -- menu ------------------------------------------------------------
    def _handle_menu(self, key: Key) -> None:
        name = key.name
        if key.alt:
            if name == "F1":
                self._notice("Quick record is not available yet (wave O2).")
            elif name == "F2":
                self._notice("Quick play is not available yet (wave O2).")
            elif name == "F3":
                self._notice("Script menu is not available yet (wave O10).")
            elif name == "F9":
                self._notice("DOS access is not available: adbx runs in a window.")
            return
        count = len(screens.COMMANDS)
        if name == "UP":
            self.menu_index = (self.menu_index - 1) % count
        elif name == "DOWN":
            self.menu_index = (self.menu_index + 1) % count
        elif name == "LEFT":
            self.menu_index = (self.menu_index - 6) % count
        elif name == "RIGHT":
            self.menu_index = (self.menu_index + 6) % count
        elif name in ("ENTER", "F10"):
            self._execute_menu()
        elif name == "F1":
            self._open_help(screens.COMMANDS[self.menu_index][1])
        elif name == "F2":
            self._open_info("structure")
        elif name == "F3":
            self._open_info("status")
        elif name == "ESC":
            return
        elif name == "F4":
            self._notice("History is a directory command (F4).")
        elif name == "F9":
            self._notice("DOS access is not available: adbx runs in a window.")
        else:
            char = character(key)
            if char:
                for index, (label, _topic) in enumerate(screens.COMMANDS):
                    if label[screens.hot_index(label)] == char:
                        self.menu_index = index
                        self._execute_menu()
                        return

    def _execute_menu(self) -> None:
        label, topic_id = screens.COMMANDS[self.menu_index]
        if topic_id == "quit":
            self.quit = True
            return
        if topic_id == "choose":
            self.overlay = Overlay("submenu", items=list(DESKTOP_ITEMS),
                                   target="desktop")
            return
        if topic_id == "view":
            if self.database is None:
                self._notice("Select a database or set first.")
                return
            if self.database.locked:
                self._prompt_unlock(self.database)
                return
            self.overlay = Overlay("submenu", items=list(RECORD_ITEMS),
                                   target="records")
            return
        if topic_id == "design":
            self.overlay = Overlay("submenu", items=list(DESIGN_ITEMS),
                                   target="design")
            return
        if topic_id == "layouts":
            if self.database is None:
                self._notice("Select a database or set first.")
                return
            self.overlay = Overlay("submenu", items=list(LAYOUT_ITEMS),
                                   target="layouts")
            return
        if topic_id == "print":
            if self.database is None and self.active_set is None:
                self._notice("Select a database or set first.")
                return
            self.overlay = Overlay("submenu", items=list(PRINT_ITEMS),
                                   target="print")
            return
        if topic_id == "utilities":
            self.overlay = Overlay("submenu", items=list(UTILITY_ITEMS),
                                   target="utilities")
            return
        if topic_id == "indexes":
            if self.database is None:
                self._notice("Select a database or set first.")
                return
            if self.database.locked:
                self._prompt_unlock(self.database)
                return
            self.overlay = Overlay("submenu", items=list(INDEX_ITEMS),
                                   target="indexes")
            return
        if topic_id == "search":
            if self.database is None:
                self._notice("Select a database or set first.")
                return
            if self.database.locked:
                self._prompt_unlock(self.database)
                return
            self.overlay = Overlay("submenu", items=list(SEARCH_ITEMS),
                                   target="search")
            return
        if topic_id == "global":
            if self.database is None:
                self._notice("Select a database or set first.")
                return
            self.overlay = Overlay("submenu", items=list(GLOBAL_ITEMS),
                                   target="global")
            return
        if topic_id == "other":
            self.overlay = Overlay("submenu", items=list(OTHER_ITEMS),
                                   target="other")
            return
        if topic_id == "applications":
            self.application_return_base = self.base
            self.overlay = Overlay("submenu",
                                   items=list(APPLICATION_ITEMS),
                                   target="applications")
            return
        wave = COMMAND_WAVES.get(topic_id, "a later wave")
        self._notice(f"{label} is not available yet (wave {wave}).")

    # -- records e designer ---------------------------------------------
    def _start_records(self, mode: str) -> None:
        if self.database is None:
            self._notice("Select a database or set first.")
            return
        if self.database.locked:
            self._prompt_unlock(self.database)
            return
        if mode == "recall":
            mode = "view"
            show_deleted = True
        else:
            show_deleted = False
        owner = self._form_owner()
        form = (self.workspace.active_form(owner)
                if self.workspace is not None and owner else None)
        if self.active_set is not None:
            self.set_records = SetSession(self.active_set, mode, self.theme,
                                          form=form)
            self.base = "setrecords"
            self.overlay = None
            return
        self.records = RecordSession(self.database, mode, self.theme,
                                     clipboard=self.clipboard,
                                     show_deleted=show_deleted, form=form,
                                     event_hook=self._record_event)
        self._apply_custom_menu(self.records)
        self.base = "records"
        self.overlay = None

    def _handle_records(self, key: Key) -> None:
        session = self.records
        assert session is not None
        if self._custom_menu_action(key):
            return
        if key.name == "F1" and not key.alt:
            self._open_help(session.help_topic)
            return
        session.request = ""
        session.handle(key)
        if session.request:
            self._record_request(session.request)
            return
        if session.close:
            self._finish_records()

    def _finish_records(self) -> None:
        self.records = None
        self.base = "menu"
        if self.database is not None:
            self.state.database = self.database
        self.state.set_name = (self.active_set.name
                               if self.active_set is not None else "")

    def _open_designer(self, database: Database | None,
                       name: str | None = None) -> None:
        directory = (database.source.parent if database is not None
                     else (self.workspace.directory if self.workspace is not None
                           else self.state.root))
        if database is None:
            try:
                workspace = Workspace(directory)
            except (WorkspaceError, OSError) as exc:
                self._notice(str(exc))
                return
            self.workspace = workspace
            chosen = (name or "").strip().upper()
            if chosen.endswith(".DBF"):
                chosen = chosen[:-4]
            if not chosen:
                self._notice("Enter a database name.")
                return
        else:
            workspace = database.workspace
            chosen = database.name
            self.workspace = workspace
        self.designer = DesignerSession(workspace, chosen, database, self.theme)
        self.base = "designer"
        self.overlay = None

    def _handle_designer(self, key: Key) -> None:
        session = self.designer
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help("designer")
            return
        session.handle(key)
        if session.close:
            self._finish_designer()

    def _finish_designer(self) -> None:
        session = self.designer
        self.designer = None
        if session is not None and session.saved_database is not None:
            self._adopt_database(session.saved_database)
        else:
            self.base = "menu" if self.state.current is not None else "directory"

    def _adopt_database(self, database: Database, *, path: Path | None = None) -> None:
        self.workspace = database.workspace
        self.database = database
        self.state.database = database
        target = path or database.source
        try:
            self.state.open(target)
            self.state.change_directory(database.source.parent)
        except (OSError, ValueError):
            self.state.refresh()
        self.base = "menu"
        self.menu_index = 0
        self.overlay = None
        self._sync_input()
        self._play_open_script(database.name)

    # -- prompt e conferme ----------------------------------------------
    def _prompt_create(self) -> None:
        self.overlay = Overlay(
            "prompt", text="Enter name of new database",
            action="create", action_title="Create Database")

    def _prompt_unlock(self, database: Database) -> None:
        self.overlay = Overlay(
            "prompt", text=f"Enter password for {database.name}",
            action=f"unlock:{database.name}", action_title="Password",
            secret=True)

    def _prompt_password(self) -> None:
        if self.database is None:
            self._notice("Select a database first.")
            return
        self.overlay = Overlay(
            "prompt", text="Enter new password (blank removes it)",
            action=f"password:{self.database.name}", action_title="Set Password",
            secret=True)

    def _submit_prompt(self) -> None:
        overlay = self.overlay
        assert overlay is not None
        text = overlay.input_text.strip()
        action = overlay.action
        if action.startswith("script-name:"):
            kind = action.split(":", 1)[1]
            self._script_name_entered(kind, text)
            return
        if action.startswith("script-desc:"):
            _prefix, kind, name = action.split(":", 2)
            self._script_create(kind, name, text)
            return
        if action == "script-path":
            self._set_script_path(text)
            return
        if action == "app-name":
            self._open_application_editor(text)
            return
        if action == "app-password":
            self.overlay = None
            session = self.application_session
            if session is not None:
                request = session.runtime.provide_password(text)
                if request:
                    self._handle_application_request(session)
            self.pending_app_password = False
            return
        if action == "app-escape":
            self.overlay = None
            session = self.application_session
            if session is not None and session.runtime.escape_password(text):
                self._exit_application()
            elif session is not None:
                self._notice(session.runtime.status)
            self.pending_app_escape = False
            return
        if action.startswith("variable-edit:"):
            variable = action.split(":", 1)[1]
            self._script_engine().set_variable(variable, text)
            self.overlay = None
            self._notice(f"{variable} set.")
            return
        if action == "create":
            self._open_designer(None, text)
            return
        if action == "index-name":
            self.pending_index_name = text.upper() or "INDEX"
            self.overlay = Overlay(
                "submenu", items=[("Table mode", "table"),
                                  ("Expression mode", "expression")],
                target="index-mode")
            return
        if action == "search-letter":
            letter = (text.strip().upper() or "A")[:1]
            if not letter.isalpha():
                self.overlay = None
                self._notice("Search/sort ids are letters A-Z.")
                return
            existing = (indexing.saved_search(self.database, letter)
                        if self.database is not None else None)
            if existing is not None:
                self._start_search_session(existing=existing)
            else:
                self._start_search_session(letter=letter)
            return
        if action == "find":
            self.overlay = None
            if self.records is not None:
                self.records.find(text)
            return
        if action == "locate":
            self.overlay = None
            self.pending_locate_text = text
            chosen = [field.name for field in self.database.fields
                      if not field.is_memo] if self.database else []
            self._open_fields("Field Selection", chosen, "locate-fields")
            return
        if action == "replace-find":
            self.overlay = None
            self.pending_replace = [text]
            self.overlay = Overlay(
                "prompt", text="Replace with", action="replace-with",
                action_title="Search and Replace")
            return
        if action == "replace-with":
            self.overlay = None
            self.pending_replace.append(text)
            chosen = [field.name for field in self.database.fields
                      if field.type == "C"] if self.database else []
            self._open_fields("Fields to Search and Replace", chosen,
                              "replace-fields")
            return
        if action.startswith("unlock:"):
            name = action.split(":", 1)[1]
            database = (self.workspace.get(name) if self.workspace is not None
                        else None)
            if database is None:
                self.overlay = None
                self._notice(f"Database {name} is no longer available.")
                return
            if not database.workspace.check_password(database, text):
                self.overlay = None
                self._notice("Incorrect password.")
                return
            self.database = database
            self.state.database = database
            self.overlay = None
            self.base = "menu"
            return
        if action.startswith("password:"):
            name = action.split(":", 1)[1]
            database = self.database
            if database is None or database.workspace.get(name) is None:
                self.overlay = None
                self._notice("Database is no longer available.")
                return
            database.workspace.set_password(name, text or None)
            refreshed = database.workspace.get(name)
            if refreshed is not None:
                refreshed.unlocked = True
                self.database = refreshed
                self.state.database = refreshed
            self.overlay = None
            self._notice("Password removed." if not text else "Password set.")
            return
        self.overlay = None

    def _confirm_action(self) -> None:
        overlay = self.overlay
        assert overlay is not None
        action = overlay.action
        self.overlay = None
        if action.startswith("delete-app:"):
            name = action.split(":", 1)[1]
            try:
                self._application_store().delete(name)
            except AppError as exc:
                self._notice(str(exc))
                return
            self._notice(f"Application {name} erased.")
            return
        if action.startswith("delete-script:"):
            name = action.split(":", 1)[1]
            try:
                self._script_store().delete(name)
            except ScriptError as exc:
                self._notice(str(exc))
                return
            self._notice(f"Script {name} erased.")
            return
        if action.startswith("script-overwrite:"):
            _prefix, kind, name = action.split(":", 2)
            self.pending_script_kind = kind
            self.pending_script_name = name
            self.overlay = Overlay(
                "prompt", text="Description",
                action=f"script-desc:{kind}:{name}",
                action_title="Script Description")
            return
        if action.startswith("delete-index:"):
            name = action.split(":", 1)[1]
            if self.database is not None:
                indexing.delete_index(self.database, name)
                if self.records is not None:
                    self.records.apply_range()
                self._notice(f"Index {name} erased.")
            return
        if action.startswith("erase-search:"):
            letter = action.split(":", 1)[1]
            if self.database is not None:
                indexing.delete_saved_search(self.database, letter)
                self._notice(f"Search/sort {letter} erased.")
            return
        if action.startswith("delete-search-list:"):
            search_id = int(action.split(":", 1)[1])
            if self.database is not None:
                indexing.delete_search_list(self.database, search_id)
                if self.records is not None:
                    self.records.apply_range()
                self._notice("Search/Sort List deleted.")
            return
        if action.startswith("delete-label:"):
            letter = action.split(":", 1)[1]
            if self._workspace() is not None:
                self._workspace().delete_label(self._form_owner(), letter)
                self._notice(f"Label {letter} erased.")
            return
        if action.startswith("delete-letter:"):
            name = action.split(":", 1)[1]
            if self._workspace() is not None:
                self._workspace().delete_letter(self._form_owner(), name)
                self._notice(f"Letter {name} erased.")
            return
        if action.startswith("delete-report:"):
            letter = action.split(":", 1)[1]
            if self._workspace() is not None:
                self._workspace().delete_report(self._form_owner(), letter)
                self._notice(f"Report {letter} erased.")
            return
        if action.startswith("delete-form:"):
            letter = action.split(":", 1)[1]
            if self._workspace() is not None:
                self._workspace().delete_form(self._form_owner(), letter)
                self._notice(f"Form {letter} erased.")
            return
        if action.startswith("delete-set:"):
            name = action.split(":", 1)[1]
            if self._workspace() is not None:
                self._workspace().delete_set(name)
                if self.active_set is not None and self.active_set.name == name:
                    self.active_set = None
                    self.state.set_name = ""
                self._notice(f"Set {name} erased.")
            return
        if action == "erase-field-rules":
            if self.database is not None:
                self.database.clear_field_rules()
                self._notice("Field rules erased.")
            return
        if action == "zap-database":
            if self.database is not None:
                name = self.database.name
                try:
                    self.database.zap()
                    self.database.workspace.save_database(self.database)
                except (WorkspaceError, OSError) as exc:
                    self._notice(f"Cannot zap: {exc}")
                    return
                self._notice(f"Zapped {name}; the structure is unchanged.")
            return
        if action == "replace-all":
            find = self.pending_replace[0] if self.pending_replace else ""
            replacement = (self.pending_replace[1]
                           if len(self.pending_replace) > 1 else "")
            chosen = list(self.overlay_chosen)
            if self.records is not None:
                self.records.replace_all(find, replacement, chosen)
                self._notice(self.records.status)
            return
        if action.startswith("erase:"):
            name = action.split(":", 1)[1]
            workspace = (self.database.workspace if self.database is not None
                         else self.workspace)
            if workspace is None:
                return
            workspace.drop_database(name)
            if self.database is not None and self.database.name == name:
                self.database = None
                self.state.database = None
                self.state.current = None
                try:
                    self.state.refresh()
                except OSError:
                    pass
                self.base = "directory"
                self.cursor = self.first = self._first_file_index()
                self._sync_input()
            self._notice(f"Database {name} erased.")

    # -- script ----------------------------------------------------------
    def _script_store(self) -> ScriptStore:
        if self.script_directory is None:
            root = (self.workspace.directory if self.workspace is not None
                    else self.state.root)
            configured = ""
            if self.workspace is not None:
                configured = self.workspace.setting("script_path", "")
            self.script_directory = (Path(configured).expanduser()
                                     if configured else
                                     Path(root) / "objects" / "scripts")
        return ScriptStore(self.script_directory)

    def _script_engine(self) -> ScriptEngine:
        if self.script_engine is None:
            self.script_engine = ScriptEngine(self._script_store(),
                                              ShellScriptHost(self))
            engine = self.script_engine
            engine.variables.set("%SYS_SCRIPT_PATH",
                                 str(self._script_store().directory))
            engine.variables.set("%SYS_VIEW_MODE",
                                 "B" if self.records is not None
                                 and self.records.mode == "browse" else "V")
            engine.variables.set("%SYS_TOOLS", "")
        return self.script_engine

    def _script_variables(self):
        return self._script_engine().variables

    def _open_scripts_menu(self) -> None:
        if self.base not in ("scripteditor", "dialogdesigner",
                             "menubardesigner", "scriptdebugger",
                             "scriptdialog"):
            self.script_return_base = self.base
        self.overlay = Overlay("submenu", items=list(SCRIPTS_ITEMS),
                               target="scripts")

    def _script_action(self, action: str) -> None:
        if action == "modify":
            self._script_choose("modify-script", "Modify a script")
            return
        if action.startswith("create-"):
            kind = {"create-keystroke": KIND_KEYSTROKE,
                    "create-dialog": KIND_DIALOG,
                    "create-menu": KIND_MENU}.get(action, KIND_KEYSTROKE)
            title = {"keystroke": "Keystroke",
                     "dialog": "Dialog Box",
                     "menu": "Menu Bar"}[kind]
            self.overlay = Overlay(
                "prompt", text=f"Enter a name for the {title} script",
                action=f"script-name:{kind}", action_title="New Script")
            return
        if action == "erase":
            self._script_choose("erase-script", "Erase a script")
            return
        if action == "play":
            self._script_choose("play-script", "Play a script")
            return
        if action == "path":
            self.overlay = Overlay(
                "prompt", text="Script path",
                action="script-path", action_title="Set Script Path",
                input_text=str(self._script_store().directory),
                input_cursor=len(str(self._script_store().directory)))
            return
        if action == "variables":
            self.overlay = Overlay(
                "variables", items=self._script_variables().items(),
                selected=0)
            return
        if action == "debug":
            self._script_choose("debug-script", "Debug a script")
            return

    def _script_choose(self, action: str, title: str,
                       *, playable_only: bool | None = None) -> None:
        store = self._script_store()
        names = store.names()
        if playable_only:
            names = [name for name in names
                     if (script := store.get(name, missing_ok=True))
                     and script.playable]
        if not names:
            self._notice("There are no scripts in the script path.")
            return
        items = []
        for name in names:
            script = store.get(name, missing_ok=True)
            if script is None:
                continue
            items.append((f"{name:<8} {script.kind_label:<10} "
                          f"{script.description}", name))
        self.overlay = Overlay("choose", text=title, items=items,
                               action=action)

    def _script_name_entered(self, kind: str, text: str) -> None:
        try:
            name = clean_name(text)
        except ScriptError:
            self.overlay = None
            self._notice("Script names have 1-8 letters, digits or _.")
            return
        store = self._script_store()
        if store.exists_name(name):
            self.overlay = Overlay(
                "confirm", text=f"Overwrite existing script {name}?",
                action=f"script-overwrite:{kind}:{name}")
            return
        self.pending_script_kind = kind
        self.pending_script_name = name
        self.overlay = Overlay(
            "prompt", text="Description",
            action=f"script-desc:{kind}:{name}",
            action_title="Script Description")

    def _script_create(self, kind: str, name: str, description: str) -> None:
        self.overlay = None
        try:
            script = script_template(name, kind)
            script.description = description[:80]
            self._script_store().save(script)
        except ScriptError as exc:
            self._notice(str(exc))
            return
        self._open_script(script.name)

    def _open_script(self, name: str) -> None:
        try:
            script = self._script_store().get(name)
        except ScriptError as exc:
            self._notice(str(exc))
            return
        assert script is not None
        self.overlay = None
        self.script_return_base = (self.base if self.base not in
                                   ("scripteditor", "dialogdesigner",
                                    "menubardesigner", "scriptdebugger")
                                   else self.script_return_base)
        if script.kind == KIND_DIALOG:
            self.dialog_designer = DialogDesigner(self._script_store(),
                                                  script, self.theme)
            self.base = "dialogdesigner"
        elif script.kind == KIND_MENU:
            self.menu_designer = MenuBarDesigner(self._script_store(),
                                                 script, self.theme)
            self.base = "menubardesigner"
        else:
            screen_lines = self.view().buffer.to_lines()
            self.script_editor = ScriptEditor(self._script_store(), script,
                                              self.theme,
                                              capture_lines=screen_lines)
            self.base = "scripteditor"

    def _handle_script_editor(self, key: Key) -> None:
        session = self.script_editor
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help(session.help_topic)
            return
        session.handle(key)
        if session.learn_request or session.append_request:
            append = session.append_request
            script = session.script
            script.source = session.source
            self._begin_learning(script, append=append)
            return
        if session.saved or session.close:
            self._finish_script_session()
            if session.status:
                self._notice(session.status)

    def _handle_dialog_designer(self, key: Key) -> None:
        session = self.dialog_designer
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help(session.help_topic)
            return
        session.handle(key)
        if session.saved or session.close:
            self._finish_script_session()
            if session.status:
                self._notice(session.status)

    def _handle_menu_designer(self, key: Key) -> None:
        session = self.menu_designer
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help(session.help_topic)
            return
        session.handle(key)
        if session.saved or session.close:
            self._finish_script_session()
            if session.status:
                self._notice(session.status)

    def _open_script_debug(self, name: str) -> None:
        try:
            script = self._script_store().get(name)
        except ScriptError as exc:
            self._notice(str(exc))
            return
        if script is None:
            self._notice(f"Script {name} not found.")
            return
        self.overlay = None
        engine = self._script_engine()
        engine.debug_on = False
        self.script_return_base = (self.base if self.base in
                                   ("menu", "records") else "menu")
        self.script_debug = ScriptDebugSession(engine, script, self.theme)
        self.base = "scriptdebugger"

    def _handle_script_debug(self, key: Key) -> None:
        session = self.script_debug
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help(session.help_topic)
            return
        session.handle(key)
        if session.close:
            self.script_debug = None
            self.script_engine.debug_on = False
            self.base = (self.script_return_base
                         if self.script_return_base in
                         ("menu", "records") else "menu")
            if session.status:
                self._notice(session.status)

    def _handle_dialog_runtime(self, key: Key) -> None:
        session = self.dialog_runtime
        assert session is not None
        if key.name == "F1":
            self._open_help(session.help_topic)
            return
        session.handle(key)
        if session.action_request or session.close:
            action = session.action_request
            self.dialog_runtime = None
            engine = self._script_engine()
            for variable, value in session.values.items():
                engine.variables.set(variable, value)
            self.base = (self.script_return_base
                         if self.script_return_base in
                         ("menu", "records") else "menu")
            if action:
                self._play_inline(action)

    def _finish_script_session(self) -> None:
        self.script_editor = None
        self.dialog_designer = None
        self.menu_designer = None
        self.base = (self.script_return_base
                     if self.script_return_base in ("menu", "records")
                     else "menu")

    def _set_script_path(self, text: str) -> None:
        path = Path(text).expanduser()
        if not path.is_absolute():
            path = self.state.root / path
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.overlay = None
            self._notice(f"Cannot use script path: {exc}")
            return
        self.script_directory = path
        if self.workspace is not None:
            self.workspace.set_setting("script_path", str(path))
        if self.script_engine is not None:
            self.script_engine.store = ScriptStore(path)
            self.script_engine.variables.set("%SYS_SCRIPT_PATH", str(path))
        self.overlay = None
        self._notice(f"Script path set to {path}.")

    def _play_script(self, name: str) -> bool:
        try:
            script = self._script_store().get(name, missing_ok=True)
        except ScriptError as exc:
            self._notice(str(exc))
            return False
        if script is None:
            self._notice(f"Script {name} not found.")
            return False
        if not script.playable:
            self._notice("Menu bar scripts are assigned to layouts, "
                         "not played directly.")
            return False
        self.overlay = None
        if script.kind == KIND_DIALOG:
            self.dialog_runtime = DialogRuntime(script, self.theme)
            self.script_return_base = (self.base if self.base in
                                       ("menu", "records") else "menu")
            self.base = "scriptdialog"
            return True
        engine = self._script_engine()
        engine.variables.set("%SYS_VIEW_MODE",
                             "B" if self.records is not None
                             and self.records.mode == "browse" else "V")
        self._in_script = True
        try:
            ok = engine.run(script)
        except (ScriptError, OSError) as exc:
            self._in_script = False
            self._notice(f"Script: {exc}")
            return False
        finally:
            self._in_script = False
        self._flush_deferred()
        if ok:
            self._notice(f"Script {script.name} finished.")
        return ok

    def _play_inline(self, source: str) -> bool:
        engine = self._script_engine()
        self._in_script = True
        try:
            runner = ScriptRunner(engine, source, name="<inline>")
            runner.run()
        except ScriptError as exc:
            self._notice(f"Script: {exc}")
            return False
        finally:
            self._in_script = False
        self._flush_deferred()
        return True

    def _play_hot_key(self, number: int) -> bool:
        engine = self._script_engine()
        variable = f"%SYS_CTRLF{number}"
        name = engine.variables.get(variable) or f"CTRLF{number}"
        if not self._script_store().exists_name(name):
            return False
        return self._play_script(name)

    def _quick_record(self) -> None:
        if self.recording is not None:
            return
        script = script_template("UNTITLED", KIND_KEYSTROKE)
        self._begin_learning(script, append=False)
        self._notice("Recording UNTITLED. Press ALT-F3 to stop.")

    def _begin_learning(self, script: Script, *, append: bool) -> None:
        self.recording_name = script.name
        self.recording_source = script.source if append else ""
        self.recording = []
        self._recording_script = script
        self.script_editor = None
        self.dialog_designer = None
        self.menu_designer = None
        self.base = (self.script_return_base
                     if self.script_return_base in ("menu", "records")
                     else "menu")
        self.overlay = None

    def _stop_recording(self) -> None:
        if self.recording is None:
            return
        source = self.recording_source + "".join(self.recording)
        macro_editor = getattr(self, "_recording_macro", None)
        macro_item = getattr(self, "_recording_macro_item", None)
        if macro_editor is not None and macro_item is not None:
            macro_item.macro = source[:3000]
            macro_editor.dirty = True
            macro_editor.rows = outline(macro_editor.app)
            self.recording = None
            self._recording_macro = None
            self._recording_macro_item = None
            self.base = "appeditor"
            self._notice(f"Macro recorded ({len(source)} characters).")
            return
        script = getattr(self, "_recording_script", None)
        self.recording = None
        self._recording_script = None
        if script is None:
            return
        script.source = source[:3000]
        try:
            self._script_store().save(script)
        except ScriptError as exc:
            self._notice(str(exc))
            return
        self._notice(f"Script {script.name} recorded "
                     f"({len(script.source)} characters).")

    def _autostart(self) -> None:
        try:
            script = self._script_store().get("AUTOEXEC", missing_ok=True)
        except (ScriptError, OSError):
            return
        if script is not None and script.kind == KIND_KEYSTROKE:
            if self.base in ("menu", "directory"):
                self._play_script("AUTOEXEC")

    def _play_open_script(self, name: str) -> None:
        if getattr(self, "_opening_script", False):
            return
        script_name = name.strip().upper()[:7] + "!"
        try:
            if not self._script_store().exists_name(script_name):
                return
        except ScriptError:
            return
        self._opening_script = True
        try:
            self._play_script(script_name)
        finally:
            self._opening_script = False

    # -- trigger ---------------------------------------------------------
    def _record_event(self, event: str, **context) -> None:
        if getattr(self, "_firing_trigger", False):
            return
        engine = self.script_engine
        if engine is None:
            return
        if context.get("field"):
            engine.variables.set("%SYS_FIELD_NAME", context["field"])
        if context.get("region"):
            engine.variables.set("%SYS_REGION_NAME", context["region"])
        if context.get("save_mode"):
            engine.variables.set("%SYS_SAVE_MODE", context["save_mode"])
        if context.get("count") is not None:
            engine.variables.set("%SYS_SEARCH_COUNT", str(context["count"]))
        self._fire_script_trigger(event)

    def _fire_script_trigger(self, event: str) -> bool:
        engine = self.script_engine
        if engine is None or not engine.triggers.get(event):
            return False
        self._firing_trigger = True
        try:
            fired = engine.fire(event)
        finally:
            self._firing_trigger = False
        self._flush_deferred()
        return fired

    def _flush_deferred(self) -> None:
        deferred = list(getattr(self, "script_deferred", []))
        if not deferred or getattr(self, "_flushing", False):
            return
        self.script_deferred.clear()
        self._flushing = True
        try:
            for chunk in deferred:
                for key in _keys_from_source(chunk):
                    self.handle(key)
        finally:
            self._flushing = False

    # -- primitive dell'host --------------------------------------------
    def script_prompt(self, label: str, length: int, default: str = "",
                      *, secret: bool = False) -> str | None:
        try:
            from PyQt6.QtWidgets import QApplication, QInputDialog
        except ImportError:
            return default
        if QApplication.instance() is None:
            return default
        value, accepted = QInputDialog.getText(
            None, "adbx", label,
            QInputDialog.EchoMode.Password if secret
            else QInputDialog.EchoMode.Normal, default)
        return value[:length] if accepted else None

    def script_show_dialog(self, name: str, *,
                           modal: bool = True) -> dict[str, str] | None:
        try:
            script = self._script_store().get(name, missing_ok=True)
        except ScriptError:
            return None
        if script is None or script.kind != KIND_DIALOG:
            self._notice(f"Dialog box {name} not found.")
            return None
        self.script_display_dialog = script
        values = {}
        dialog = script.dialog
        if dialog is not None:
            for control in dialog.controls:
                if control.variable:
                    values[control.variable] = control.default
        return values

    def script_context(self) -> Context | None:
        database = self.database
        if self.set_records is not None:
            primary = self.set_records.primary
            values: dict[str, str] = {}
            for (name, field), value in self.set_records.draft.items():
                if name == primary.name:
                    values[field] = value
            if not values and self.set_records.current_seq is not None:
                values = primary.read(self.set_records.current_seq)
            return Context(fields=primary.fields, values=values,
                           pattern=primary.workspace.pattern_mode,
                           seq=self.set_records.current_seq or 0,
                           count=primary.count())
        if database is None:
            return None
        values = {}
        seq = 0
        if self.records is not None:
            values = self.records._values()
            seq = self.records.current_seq or 0
        return Context(fields=database.fields, values=values,
                       pattern=database.workspace.pattern_mode,
                       seq=seq, count=database.count())

    def script_prompt_value(self, variable: str) -> str:
        return self._script_variables().get(variable)

    def script_main_menu(self) -> None:
        self.script_screen_mode = "on"
        self.script_writes.clear()
        self._to_main_menu()

    def script_tool_end(self) -> None:
        if self.records is not None:
            self.base = "records"
        else:
            self.base = "menu"

    def script_end_app(self) -> None:
        if self.application_session is not None:
            self._exit_application()
            return
        self.base = "menu"
        self._notice("Application ended.")

    def script_debug_pause(self, runner, token) -> None:
        row, col = self.script_cursor
        self.script_cursor = (row, col)

    def script_error(self, message: str) -> None:
        if not getattr(self, "_in_script", False):
            self._notice(f"Script: {message}")
        else:
            self._notice(f"Script: {message}")

    def script_set_screen_mode(self, mode: str) -> None:
        self.script_screen_mode = mode
        if mode == "on":
            self.script_writes.clear()

    def _open_tools(self) -> None:
        engine = self._script_engine()
        preferred = engine.variables.get("%SYS_TOOLS")
        if preferred:
            self._play_script(preferred)
            return
        store = self._script_store()
        names = [name for name in store.names()
                 if (script := store.get(name, missing_ok=True))
                 and script.playable]
        if not names:
            self._notice("There are no Tools scripts in the script path.")
            return
        items = [(name, name) for name in names]
        self.overlay = Overlay("choose", text="Tools",
                               items=items, action="play-tools")

    def _apply_custom_menu(self, session: RecordSession) -> None:
        form = getattr(session, "form", None)
        name = getattr(form, "custom_menu", "") if form is not None else ""
        if not name:
            session.menu_items = None
            return
        try:
            script = self._script_store().get(name, missing_ok=True)
        except ScriptError:
            script = None
        if script is None or script.kind != KIND_MENU or script.menu is None:
            session.menu_items = None
            return
        session.menu_items = list(script.menu.items)

    def _custom_menu_action(self, key: Key) -> bool:
        session = self.records
        if session is None or not getattr(session, "menu_items", None):
            return False
        for item in session.menu_items:
            try:
                mapped = parse_key(item.key)
            except ValueError:
                continue
            if mapped == key:
                if item.action:
                    self._play_inline(item.action)
                return True
        return False



    def _files_protected(self, kind: str) -> bool:
        workspace = self._workspace()
        if workspace is None:
            return False
        owner = self._form_owner()
        if not owner:
            owner = (self.active_set.name if self.active_set is not None
                     else (self.database.name if self.database is not None
                           else ""))
        if owner and is_protected(workspace, owner, kind):
            self._notice(f"{kind} for {owner} are protected. "
                         "Use Applications, Prevent/allow file alterations.")
            return True
        return False

    # -- applicazioni ----------------------------------------------------
    def _application_store(self) -> ApplicationStore:
        if self.application_store_directory is None:
            root = (self.workspace.directory if self.workspace is not None
                    else self.state.root)
            configured = ""
            if self.workspace is not None:
                configured = self.workspace.setting("application_path", "")
            self.application_store_directory = (
                Path(configured).expanduser() if configured else
                Path(root) / "objects" / "apps")
        return ApplicationStore(self.application_store_directory)

    def _application_action(self, action: str) -> None:
        if action == "run":
            self._choose_application("run-app", "Run an application")
            return
        if action == "edit":
            self.overlay = Overlay(
                "prompt", text="Application name",
                action="app-name", action_title="Create/edit Application")
            return
        if action == "erase":
            self._choose_application("erase-app", "Erase an application")
            return
        if action == "protect":
            self._choose_protection_scope()
            return

    def _choose_application(self, action: str, title: str) -> None:
        store = self._application_store()
        names = store.names()
        if not names:
            self._notice("There are no applications in this directory.")
            return
        items = []
        for name in names:
            app = store.get(name, missing_ok=True)
            if app is not None:
                items.append((app.label, name))
        self.overlay = Overlay("choose", text=title, items=items,
                               action=action)

    def _choose_protection_scope(self) -> None:
        workspace = self._workspace()
        if workspace is None:
            self._notice("Open a database or set first.")
            return
        items = [(name, f"DB:{name}") for name in workspace.names()]
        items += [(f"{name} (set)", f"SET:{name}")
                  for name in workspace.set_names()]
        if not items:
            self._notice("There are no databases or sets in this directory.")
            return
        self.overlay = Overlay("choose", text="Protect files for",
                               items=items, action="protect-scope")

    def _open_application_editor(self, name: str) -> None:
        store = self._application_store()
        try:
            app = store.get(name, missing_ok=True)
        except AppError as exc:
            self._notice(str(exc))
            return
        if app is None:
            try:
                app = Application(name)
            except ValueError as exc:
                self._notice(str(exc))
                return
        self.overlay = None
        self.application_return_base = (self.base if self.base in
                                        ("menu", "records") else "menu")
        self.application_editor = ApplicationEditor(store, app, self.theme)
        self.base = "appeditor"

    def _handle_app_editor(self, key: Key) -> None:
        session = self.application_editor
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help(session.help_topic)
            return
        session.handle(key)
        if session.banner_request:
            session.banner_request = False
            if not session.app.banner_enabled:
                self._notice("Enable the application banner first.")
            else:
                self.banner_painter = BannerPainter(session.app, self.theme)
                self.base = "bannerpainter"
            return
        if session.macro_request:
            session.macro_request = False
            row = session.current_row
            if row is not None and row.kind == "item":
                self.editing_application_macro = row.item
                self.macro_editor = MacroEditor(row.item.macro, self.theme)
                self.base = "macroeditor"
            return
        if session.learn_request:
            session.learn_request = False
            self._begin_macro_learning(session)
            return
        if session.simulate_request:
            session.simulate_request = False
            self._open_application_session(session.app, simulate=True)
            return
        if session.saved or session.close:
            self.application_editor = None
            self.base = (self.application_return_base
                         if self.application_return_base in
                         ("menu", "records") else "menu")
            if session.status:
                self._notice(session.status)

    def _handle_banner_painter(self, key: Key) -> None:
        session = self.banner_painter
        assert session is not None
        if key.name == "F1":
            self._open_help(session.help_topic)
            return
        session.handle(key)
        if session.saved or session.close:
            self.banner_painter = None
            self.base = "appeditor"
            if session.status:
                self._notice(session.status)

    def _handle_macro_editor(self, key: Key) -> None:
        session = self.macro_editor
        assert session is not None
        if key.name == "F1":
            self._open_help(session.help_topic)
            return
        session.handle(key)
        if session.close:
            if session.saved and self.editing_application_macro is not None:
                self.editing_application_macro.macro = session.body
                if self.application_editor is not None:
                    self.application_editor.dirty = True
                    self.application_editor.rows = outline(
                        self.application_editor.app)
            self.macro_editor = None
            self.editing_application_macro = None
            self.base = "appeditor"

    def _handle_protection(self, key: Key) -> None:
        session = self.protection_session
        assert session is not None
        if key.name == "F1":
            self._open_help(session.help_topic)
            return
        session.handle(key)
        if session.close:
            self.protection_session = None
            self.base = "menu"

    def _open_application_session_by_name(self, name: str) -> bool:
        try:
            app = self._application_store().get(name, missing_ok=True)
        except AppError as exc:
            self._notice(str(exc))
            return False
        if app is None:
            self._notice(f"Application {name} not found.")
            return False
        self._open_application_session(app)
        return True

    def _open_application_session(self, app: Application, *,
                                  simulate: bool = False) -> None:
        self._apply_application_startup(app)
        store = self._application_store()
        runtime = ApplicationRuntime(app, store, simulate=simulate)
        session = ApplicationSession(runtime, self.theme)
        self.application_runtime = runtime
        self.application_session = session
        if not simulate:
            self.application_return_base = (self.base if self.base in
                                            ("menu", "records") else "menu")
        self.base = "appsession"
        self.overlay = None
        if not session.banner_pending and app.startup_macro:
            self._play_inline(app.startup_macro)

    def _handle_app_session(self, key: Key) -> None:
        session = self.application_session
        assert session is not None
        runtime = session.runtime
        if key.name == "F1" and not key.alt:
            session.handle(key)
            if session.help_request:
                path = session.help_request
                session.help_request = ""
                self._show_application_help(path)
            else:
                self._open_help(session.help_topic)
            return
        before_banner = session.banner_pending
        session.handle(key)
        if before_banner and not session.banner_pending:
            if runtime.app.startup_macro:
                self._play_inline(runtime.app.startup_macro)
            return
        if session.help_request:
            path = session.help_request
            session.help_request = ""
            self._show_application_help(path)
            return
        if runtime.request:
            self._handle_application_request(session)
            return
        if session.status:
            self._notice(session.status)
        runtime.status = ""

    def _handle_application_request(self, session: ApplicationSession) -> None:
        runtime = session.runtime
        request = runtime.request
        runtime.request = ""
        item = runtime.requested_item
        if request == "password":
            self.pending_app_password = True
            self.overlay = Overlay(
                "prompt", text=f"Password for {item.text if item else 'choice'}",
                action="app-password", action_title="Application Password",
                secret=True)
            return
        if request == "escape-password":
            self.pending_app_escape = True
            self.overlay = Overlay(
                "prompt", text="Escape password",
                action="app-escape", action_title="Application Password",
                secret=True)
            return
        if request == "macro" and item is not None:
            self._play_inline(item.macro)
            runtime.after_action()
            return
        if request == "call" and item is not None:
            if runtime.call(item.target):
                self._apply_application_startup(runtime.app)
                runtime.after_action()
            elif runtime.status:
                self._notice(runtime.status)
            return
        if request == "goto" and item is not None:
            if runtime.go_to(item.target):
                self._apply_application_startup(runtime.app)
            elif runtime.status:
                self._notice(runtime.status)
            return
        if request == "exit":
            self._exit_application()

    def _exit_application(self) -> None:
        runtime = self.application_runtime
        session = self.application_session
        if runtime is not None and runtime.call_stack:
            runtime.return_from_call()
            self._apply_application_startup(runtime.app)
            return
        if session is not None and session.runtime.simulate:
            self.application_session = None
            self.application_runtime = None
            self.base = "appeditor"
            return
        self.application_session = None
        self.application_runtime = None
        if self._app_script_directory is not None:
            self.script_directory = self._app_script_directory
            if self.script_engine is not None:
                self.script_engine.store = ScriptStore(self.script_directory)
            self._app_script_directory = None
        self.base = (self.application_return_base
                     if self.application_return_base in ("menu", "records")
                     else "menu")

    def _apply_application_startup(self, app: Application) -> None:
        data_path = (self.workspace.directory if self.workspace is not None
                     else self.state.root)
        if app.script_path:
            value = app.script_path.replace("<DATAPATH>", str(data_path))
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = data_path / path
            if self._app_script_directory is None:
                self._app_script_directory = self.script_directory
            self.script_directory = path
            if self.script_engine is not None:
                self.script_engine.store = ScriptStore(path)
        engine = self._script_engine() if app.startup_macro else self.script_engine
        if engine is not None:
            engine.variables.set("%SYS_APP_PATH",
                                 str(self._application_store().directory))
            engine.variables.set("%SYS_APP_DESKTOP", str(data_path))
        if app.startup:
            self._open_application_startup(app.startup, data_path)

    def _open_application_startup(self, startup: str, data_path: Path) -> None:
        text = startup.strip()
        path = Path(text).expanduser()
        if not path.is_absolute():
            path = data_path / path
        if not path.suffix:
            for suffix in (".SET", ".DBF"):
                candidate = path.with_suffix(suffix)
                if candidate.is_file():
                    path = candidate
                    break
        if not path.is_file():
            database = (self._workspace().get(path.stem.upper())
                        if self._workspace() is not None else None)
            if database is not None and path.suffix.upper() != ".SET":
                self._adopt_database(database)
                return
        if path.suffix.upper() == ".SET" and path.is_file():
            self._open_entry(path)
            self.base = "appsession"
            return
        if path.is_file():
            self._open_entry(path)
            self.base = "appsession"

    def _show_application_help(self, path: str) -> None:
        try:
            text = Path(path).expanduser().read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            self._notice(f"Help file {path} not found.")
            return
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        self._notice(" | ".join(lines[:3]) or "The help file is empty.")

    def _begin_macro_learning(self, editor: ApplicationEditor) -> None:
        row = editor.current_row
        if row is None or row.kind != "item":
            self._notice("Select a menu item first.")
            return
        self.recording_name = "MACRO"
        self.recording_source = ""
        self.recording = []
        self._recording_macro = editor
        self._recording_macro_item = row.item
        self.overlay = None
        self.base = "appeditor"
        self._notice("Recording macro. Press ALT-F3 to stop.")

    # -- dispatch dei sottomenu -----------------------------------------
    def _activate_overlay_item(self) -> None:
        overlay = self.overlay
        assert overlay is not None
        if not overlay.items:
            return
        action = overlay.items[overlay.selected][1]
        if overlay.target == "desktop":
            self._desktop_action(action)
        elif overlay.target == "records":
            self._start_records(action)
        elif overlay.target == "design":
            self._design_action(action)
        elif overlay.target == "utilities":
            self._utility_action(action)
        elif overlay.target == "relational":
            self._relational_action(action)
        elif overlay.target == "indexes":
            self._index_action(action)
        elif overlay.target == "search":
            self._search_action(action)
        elif overlay.target == "global":
            self._global_action(action)
        elif overlay.target == "other":
            self._other_action(action)
        elif overlay.target == "index-mode":
            self._start_index_session(action)
        elif overlay.target == "field-rules":
            self._field_rules_action(action)
        elif overlay.target == "sets":
            self._set_action(action)
        elif overlay.target == "layouts":
            self._layout_action(action)
        elif overlay.target == "forms":
            self._forms_action(action)
        elif overlay.target == "reports":
            self._reports_action(action)
        elif overlay.target == "labels":
            self._labels_action(action)
        elif overlay.target == "letters":
            self._letters_action(action)
        elif overlay.target == "print":
            self._print_action(action)
        elif overlay.target == "scripts":
            self._script_action(action)
        elif overlay.target == "applications":
            self._application_action(action)

    def _design_action(self, action: str) -> None:
        if action == "create":
            self._prompt_create()
            return
        if action == "sets":
            if self.database is None:
                self.overlay = None
                self._notice("Select a database first.")
                return
            self.overlay = Overlay("submenu", items=list(SET_ITEMS),
                                   target="sets")
            return
        if action == "field-rules":
            if self.database is None:
                self.overlay = None
                self._notice("Select a database first.")
                return
            if self.database.locked:
                self._prompt_unlock(self.database)
                return
            self.overlay = Overlay("submenu", items=list(RULES_ITEMS),
                                   target="field-rules")
            return
        if self.database is None:
            self.overlay = None
            self._notice("Select a database first.")
            return
        if action == "modify":
            self._open_designer(self.database)
        elif action == "erase":
            self.overlay = Overlay(
                "confirm", text=f"Erase database {self.database.name} and its data?",
                action=f"erase:{self.database.name}")
        elif action == "password":
            self._prompt_password()

    # -- layout/forms ----------------------------------------------------
    def _form_owner(self) -> str:
        return (self.active_set.name if self.active_set is not None
                else (self.database.name if self.database is not None else ""))

    def _layout_action(self, action: str) -> None:
        if action == "forms":
            self.overlay = Overlay("submenu", items=list(FORM_ITEMS),
                                   target="forms")
            return
        if action == "reports":
            self.overlay = Overlay("submenu", items=list(REPORT_ITEMS),
                                   target="reports")
            return
        if action == "labels":
            self.overlay = Overlay("submenu", items=list(LABEL_ITEMS),
                                   target="labels")
            return
        if action == "letters":
            self.overlay = Overlay("submenu", items=list(LETTER_ITEMS),
                                   target="letters")
            return
        self.overlay = None
        self._notice(f"Layouts → {action} is not available yet (later wave).")

    def _forms_action(self, action: str) -> None:
        if action in ("create", "modify", "select", "erase") \
                and self._files_protected("Forms"):
            return
        workspace = self._workspace()
        owner = self._form_owner()
        if workspace is None or not owner:
            self._notice("Select a database or set first.")
            return
        if action == "create":
            self.form_designer = FormDesigner(
                workspace, self.database, owner=owner, theme=self.theme)
            self.overlay = None
            self.base = "formdesigner"
            return
        forms = workspace.forms(owner)
        if action in ("select", "erase"):
            if not forms:
                self._notice("There are no forms for this database or set.")
                return
            items = [(form.label, form.letter) for form in forms]
            self.overlay = Overlay(
                "choose", text="Forms", items=items,
                action="select-form" if action == "select" else "erase-form")
            return

    def _handle_form_designer(self, key: Key) -> None:
        session = self.form_designer
        assert session is not None
        if key.name == "F1" and not key.alt and session.picker is None:
            self._open_help("forms")
            return
        session.handle(key)
        if session.close:
            self._finish_form_designer()

    def _finish_form_designer(self) -> None:
        session = self.form_designer
        self.form_designer = None
        self.base = "menu"
        if session is None:
            return
        if session.saved and session.saved_form is not None:
            self._notice(f"Form {session.saved_form.letter} saved and active.")
        elif session.status:
            self._notice(session.status)

    # -- label -----------------------------------------------------------
    def _labels_action(self, action: str) -> None:
        if action in ("create", "borrow", "erase") \
                and self._files_protected("Mail labels"):
            return
        workspace = self._workspace()
        owner = self._form_owner()
        if workspace is None or not owner:
            self._notice("Select a database or set first.")
            return
        if action == "create":
            self.label_designer = LabelDesigner(
                workspace, self.database, owner=owner, theme=self.theme)
            self.overlay = None
            self.base = "labeldesigner"
            return
        labels = workspace.labels(owner)
        if action in ("borrow", "erase"):
            if not labels:
                self._notice("There are no labels for this database or set.")
                return
            items = [(label.label, label.letter) for label in labels]
            self.overlay = Overlay(
                "choose", text="Mail labels", items=items,
                action="borrow-label" if action == "borrow" else
                "erase-label")

    def _handle_label_designer(self, key: Key) -> None:
        session = self.label_designer
        assert session is not None
        if key.name == "F1" and not key.alt and session.picker is None:
            self._open_help("labels")
            return
        session.handle(key)
        if session.close:
            self._finish_label_designer()

    def _finish_label_designer(self) -> None:
        session = self.label_designer
        self.label_designer = None
        self.base = "menu"
        if session is None:
            return
        if session.preview_request and session.saved_label is not None:
            self._open_label_preview(session.saved_label)
            return
        if session.saved and session.saved_label is not None:
            self._notice(f"Label {session.saved_label.letter} saved.")
        elif session.status:
            self._notice(session.status)

    def _open_label_preview(self, label) -> None:
        workspace = self._workspace()
        if workspace is None:
            return
        try:
            output = render_labels(label, workspace)
        except ValueError as exc:
            self._notice(f"Label not printable: {exc}")
            return
        target = workspace.directory / f"{label.owner}-{label.letter}.pdf"
        self.report_preview = ReportPreview(
            output, label.label, theme=self.theme, pdf_path=target)
        self.base = "reportpreview"
        self.overlay = None

    # -- letter ----------------------------------------------------------
    def _letters_action(self, action: str) -> None:
        if action in ("create", "erase") and self._files_protected("Letters"):
            return
        workspace = self._workspace()
        owner = self._form_owner()
        if workspace is None or not owner:
            self._notice("Select a database or set first.")
            return
        if action == "create":
            self.letter_editor = LetterEditor(
                workspace, self.database, owner=owner, theme=self.theme)
            self.overlay = None
            self.base = "lettereditor"
            return
        letters = workspace.letters(owner)
        if action == "erase":
            if not letters:
                self._notice("There are no letters for this database or set.")
                return
            items = [(letter.label, letter.name) for letter in letters]
            self.overlay = Overlay("choose", text="Form letters", items=items,
                                   action="erase-letter")

    def _handle_letter_editor(self, key: Key) -> None:
        session = self.letter_editor
        assert session is not None
        if key.name == "F1" and not key.alt and session.picker is None:
            self._open_help("letters")
            return
        session.handle(key)
        if session.close:
            self._finish_letter_editor()

    def _finish_letter_editor(self) -> None:
        session = self.letter_editor
        self.letter_editor = None
        self.base = "menu"
        if session is None:
            return
        if session.preview_request and session.saved_letter is not None:
            self._open_letter_preview(session.saved_letter)
            return
        if session.saved and session.saved_letter is not None:
            self._notice(f"Letter {session.saved_letter.name} saved.")
        elif session.status:
            self._notice(session.status)

    def _open_letter_preview(self, letter) -> None:
        workspace = self._workspace()
        if workspace is None:
            return
        try:
            output = render_letters(letter, workspace)
        except ValueError as exc:
            self._notice(f"Letter not printable: {exc}")
            return
        target = workspace.directory / f"{letter.owner}-{letter.name}.pdf"
        self.report_preview = ReportPreview(
            output, letter.label, theme=self.theme, pdf_path=target)
        self.base = "reportpreview"
        self.overlay = None

    # -- report ----------------------------------------------------------
    def _reports_action(self, action: str) -> None:
        if action in ("create", "borrow", "erase") \
                and self._files_protected("Reports"):
            return
        workspace = self._workspace()
        owner = self._form_owner()
        if workspace is None or not owner:
            self._notice("Select a database or set first.")
            return
        if action == "create":
            self.report_designer = ReportDesigner(
                workspace, self.database, owner=owner, theme=self.theme)
            self.overlay = None
            self.base = "reportdesigner"
            return
        reports = workspace.reports(owner)
        if action in ("borrow", "erase"):
            if not reports:
                self._notice("There are no reports for this database or set.")
                return
            items = [(report.label, report.letter) for report in reports]
            self.overlay = Overlay(
                "choose", text="Reports", items=items,
                action="borrow-report" if action == "borrow" else
                "erase-report")
            return

    def _print_action(self, action: str) -> None:
        self.overlay = None
        workspace = self._workspace()
        owner = self._form_owner()
        if workspace is None or not owner:
            self._notice("Select a database or set first.")
            return
        if action == "report":
            reports = workspace.reports(owner)
            if not reports:
                self._notice("There are no reports for this database or set.")
                return
            items = [(report.label, report.letter) for report in reports]
            self.overlay = Overlay("choose", text="Print report", items=items,
                                   action="print-report")
            return
        if action == "labels":
            labels = workspace.labels(owner)
            if not labels:
                self._notice("There are no labels for this database or set.")
                return
            items = [(label.label, label.letter) for label in labels]
            self.overlay = Overlay("choose", text="Print mail labels",
                                   items=items, action="print-label")
            return
        if action == "letters":
            letters = workspace.letters(owner)
            if not letters:
                self._notice("There are no letters for this database or set.")
                return
            items = [(letter.label, letter.name) for letter in letters]
            self.overlay = Overlay("choose", text="Print form letter",
                                   items=items, action="print-letter")
            return
        self._notice("Printing forms and browse tables arrives with O12.")

    def _open_report_preview(self, report) -> None:
        workspace = self._workspace()
        if workspace is None:
            return
        try:
            output = render_report(report, workspace)
        except (ValueError, KeyError) as exc:
            self._notice(f"Report not printable: {exc}")
            return
        target = workspace.directory / f"{report.owner}-{report.letter}.pdf"
        self.report_preview = ReportPreview(
            output, report.label, theme=self.theme, pdf_path=target)
        self.base = "reportpreview"
        self.overlay = None

    def _handle_report_designer(self, key: Key) -> None:
        session = self.report_designer
        assert session is not None
        if key.name == "F1" and not key.alt and session.picker is None:
            self._open_help("reports")
            return
        session.handle(key)
        if session.close:
            self._finish_report_designer()

    def _finish_report_designer(self) -> None:
        session = self.report_designer
        self.report_designer = None
        self.base = "menu"
        if session is None:
            return
        if session.preview_request and session.saved_report is not None:
            self._open_report_preview(session.saved_report)
            return
        if session.saved and session.saved_report is not None:
            self._notice(f"Report {session.saved_report.letter} saved.")
        elif session.status:
            self._notice(session.status)

    def _handle_report_preview(self, key: Key) -> None:
        session = self.report_preview
        assert session is not None
        if key.name == "F1":
            return
        session.handle(key)
        if session.close:
            self.report_preview = None
            self.base = "menu"

    # -- set -------------------------------------------------------------
    def _set_action(self, action: str) -> None:
        if self._files_protected("Sets"):
            return
        workspace = self._workspace()
        if workspace is None:
            self._notice("Open a database first.")
            return
        if action == "create":
            self.set_designer = SetDesigner(workspace, self.database,
                                            theme=self.theme)
            self.overlay = None
            self.base = "setdesigner"
            return
        if action == "modify":
            items = [(name, name) for name in workspace.set_names()]
            if not items:
                self._notice("There are no sets in this directory.")
                return
            self.overlay = Overlay("choose", text="Sets", items=items,
                                   action="modify-set")
            return
        if action == "erase":
            items = [(name, name) for name in workspace.set_names()]
            if not items:
                self._notice("There are no sets in this directory.")
                return
            self.overlay = Overlay("choose", text="Erase a set", items=items,
                                   action="erase-set")

    def _workspace(self):
        if self.workspace is None and self.database is not None:
            self.workspace = self.database.workspace
        return self.workspace

    def _activate_set(self, name: str) -> bool:
        workspace = self._workspace()
        if workspace is None:
            return False
        definition = workspace.get_set(name)
        if definition is None:
            self._notice(f"Set {name} not found.")
            return False
        try:
            primary = definition.primary_database
        except Exception as exc:
            self._notice(str(exc))
            return False
        self.active_set = definition
        self.database = primary
        self.state.database = primary
        self.state.set_name = definition.name
        self.state.current = None
        self.state.database = primary
        self.base = "menu"
        self.overlay = None
        self._sync_input()
        self._play_open_script(definition.name)
        return True

    def _choose_desktop(self, action: str) -> None:
        workspace = self._workspace()
        if workspace is None:
            self._notice("Open a database first.")
            return
        items = [(name, name) for name in workspace.names()]
        if action == "open-set":
            items = [(name, name) for name in workspace.set_names()]
            if not items:
                self._notice("There are no sets in this directory.")
                return
            self.overlay = Overlay("choose", text="Open a set", items=items,
                                   action="open-set")
            return
        if action == "switch":
            items += [(f"{name} (set)", f"SET:{name}")
                      for name in workspace.set_names()]
            self.overlay = Overlay("choose", text="Open Databases/Sets",
                                   items=items, action="switch")

    def _handle_set_designer(self, key: Key) -> None:
        session = self.set_designer
        assert session is not None
        if key.name == "F1" and not key.alt \
                and session.integrity_editor is None:
            self._open_help("sets")
            return
        session.handle(key)
        if session.close:
            self._finish_set_designer()

    def _finish_set_designer(self) -> None:
        session = self.set_designer
        self.set_designer = None
        self.base = "menu"
        if session is None:
            return
        if session.saved and session.saved_definition is not None:
            self.active_set = session.saved_definition
            self.database = session.saved_definition.primary_database
            self.state.database = self.database
            self.state.set_name = session.saved_definition.name
            self._notice("Set saved.")
        elif session.status:
            self._notice(session.status)

    def _handle_set_records(self, key: Key) -> None:
        session = self.set_records
        assert session is not None
        if key.name == "F1" and not key.alt and session.zoom is None:
            self._open_help("sets")
            return
        session.handle(key)
        if session.close:
            self.set_records = None
            self.base = "menu"

    # -- field rules -----------------------------------------------------
    def _field_rules_action(self, action: str) -> None:
        if self._files_protected("Field rules"):
            return
        database = self.database
        if database is None:
            self._notice("Select a database first.")
            return
        if action == "edit":
            self.rules_session = RulesSession(database, self.theme)
            self.overlay = None
            self.base = "rules"
            return
        if action == "reevaluate":
            changed, problems = field_rules.re_evaluate(
                database, database.field_rules())
            message = f"Field rules applied to {changed} record(s)."
            if problems:
                message += " " + problems[0]
                if len(problems) > 1:
                    message += f" (+{len(problems) - 1} more)"
            self._notice(message)
            return
        if action == "erase":
            self.overlay = Overlay(
                "confirm", text="Erase all field rules for this database?",
                action="erase-field-rules")
            return

    def _handle_rules_session(self, key: Key) -> None:
        session = self.rules_session
        assert session is not None
        if key.name == "F1" and not key.alt and session.editor is None:
            self._open_help("field_rules")
            return
        session.handle(key)
        if session.close:
            self._finish_rules_session()

    def _finish_rules_session(self) -> None:
        session = self.rules_session
        self.rules_session = None
        self.base = "menu"
        if session is None:
            return
        if session.saved:
            self._notice("Field rules saved.")
            if self.records is not None:
                self.records.rule_map = self.database.field_rules()

    def _utility_action(self, action: str) -> None:
        self.overlay = None
        if action == "pack":
            if self.database is None:
                self._notice("Select a database first.")
                return
            removed = self.database.count(include_deleted=True) - self.database.count()
            try:
                remaining = self.database.pack()
                self.database.workspace.save_database(self.database)
            except (WorkspaceError, OSError) as exc:
                self._notice(f"Cannot pack: {exc}")
                return
            self._notice(f"Packed {removed} deleted record(s); "
                         f"{remaining} remain.")
            return
        if action == "zap":
            if self.database is None:
                self._notice("Select a database first.")
                return
            self.overlay = Overlay(
                "confirm",
                text=f"Zap {self.database.name}? All records are removed.",
                action="zap-database")
            return
        if action == "relational":
            if self.database is None:
                self._notice("Select a database first.")
                return
            self.overlay = Overlay("submenu", items=list(RELATIONAL_ITEMS),
                                   target="relational")
            return
        workspace = self._workspace()
        if workspace is None:
            self._notice("Open a database first.")
            return
        if action in ("import", "export"):
            self.transfer_session = TransferSession(
                workspace, self.database,
                "import" if action == "import" else "export", self.theme)
            self.base = "transfer"
            return
        if action in ("copy", "append", "summarize", "crosstab"):
            if self.database is None:
                self._notice("Select a database first.")
                return
            self.utility_session = UtilitySession(
                workspace, self.database, self.active_set, action, self.theme)
            self.base = "utility"
            return

    def _relational_action(self, action: str) -> None:
        self.overlay = None
        if self.database is None:
            self._notice("Select a database first.")
            return
        if self.active_set is not None:
            self._notice("Relational commands work on a single database.")
            return
        self.relational_session = RelationalSession(
            self._workspace(), self.database, action, self.theme)
        self.base = "relational"

    def _handle_utility_session(self, key: Key) -> None:
        session = self.utility_session
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help(session.help_topic())
            return
        session.request = ""
        session.handle(key)
        if session.request == "range":
            self._start_range_session(return_base="utility",
                                      settings=session.settings,
                                      temporary=True)
            return
        if session.close:
            self._finish_utility_session()

    def _finish_utility_session(self) -> None:
        session = self.utility_session
        self.utility_session = None
        self.base = "menu"
        if session is None:
            return
        if session.result is not None:
            self._notice(session.result.message())
            if session.command == "crosstab" and session.see_results \
                    and session.result.output is not None:
                database = self._open_database(session.result.output.source)
                if database is not None:
                    try:
                        self.state.open(database.source)
                    except OSError:
                        pass
        elif session.status:
            self._notice(session.status)

    def _handle_relational_session(self, key: Key) -> None:
        session = self.relational_session
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help("utilities")
            return
        session.request = ""
        session.handle(key)
        if session.request == "range":
            self._start_range_session(return_base="relational",
                                      settings=session.settings,
                                      temporary=True)
            return
        if session.close:
            self._finish_relational_session()

    def _finish_relational_session(self) -> None:
        session = self.relational_session
        self.relational_session = None
        self.base = "menu"
        if session is None:
            return
        if session.result is not None:
            self._notice(session.result.message())
        elif session.status:
            self._notice(session.status)

    def _handle_transfer_session(self, key: Key) -> None:
        session = self.transfer_session
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help("utilities")
            return
        session.request = ""
        session.handle(key)
        if session.request == "range":
            self._start_range_session(return_base="transfer",
                                      settings=session.settings,
                                      temporary=True)
            return
        if session.close:
            self._finish_transfer_session()

    def _finish_transfer_session(self) -> None:
        session = self.transfer_session
        self.transfer_session = None
        self.base = "menu"
        if session is None:
            return
        if session.result is not None:
            self._notice(session.status or "Transfer complete.")
            if session.mode == "import" and session.target_name:
                database = (session.workspace.get(session.target_name)
                            if session.workspace is not None else None)
                if database is not None:
                    self.database = database
                    self.state.database = database
                    self.state.set_name = ""
                    try:
                        self.state.open(database.source)
                    except OSError:
                        self.state.current = None
        elif session.status:
            self._notice(session.status)

    def _handle_global_session(self, key: Key) -> None:
        session = self.global_session
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help("utilities")
            return
        session.request = ""
        session.handle(key)
        if session.request == "range":
            self._start_range_session(return_base="global",
                                      settings=session.settings,
                                      temporary=True)
            return
        if session.close:
            self._finish_global_session()

    def _finish_global_session(self) -> None:
        session = self.global_session
        self.global_session = None
        self.base = "menu"
        if session is None:
            return
        if session.result is not None:
            self._notice(session.result.message())
            if self.records is not None:
                self.records.apply_range()
        elif session.status:
            self._notice(session.status)

    # -- indici, range e search/sort ------------------------------------
    def _active_database(self) -> Database | None:
        return self.database

    def _choose_primary(self) -> None:
        database = self.database
        if database is None:
            self._notice("Select a database first.")
            return
        items: list[tuple[str, str]] = [("Record Number", RECORD_NUMBER)]
        markers = ["\u25b8 " if database.primary_index == RECORD_NUMBER else ""]
        for definition in indexing.indexes(database, attached=True):
            markers.append(
                "\u25b8 " if database.primary_index == definition.name else "")
            items.append((definition.label, definition.name))
        history = indexing.search_history(database, limit=1)
        if history:
            search = history[0]
            stale = "\u2666 " if search.out_of_date(database) else ""
            markers.append(
                "\u25b8 " if database.primary_index ==
                f"{SEARCH_PREFIX}{search.id}" else stale)
            items.append((f"Search/Sort: {search.label}",
                          f"{SEARCH_PREFIX}{search.id}"))
        self.overlay = Overlay("choose", text="Indexes", items=items,
                               markers=markers, action="set-primary")

    def _index_action(self, action: str) -> None:
        database = self.database
        if database is None:
            self._notice("Select a database first.")
            return
        if action == "primary":
            self._choose_primary()
        elif action == "create":
            self.overlay = Overlay(
                "prompt", text="Enter index filename",
                action="index-name", action_title="Create an Index")
        elif action == "update":
            self._choose_index(action="update-index", attached_only=True)
        elif action == "attach":
            self._choose_index(action="toggle-attach", attached_only=False)
        elif action == "erase":
            self._choose_index(action="erase-index", attached_only=False)
        elif action == "range":
            self._start_range_session(return_base="menu")
        elif action == "retrieve-range":
            self._choose_saved_range()

    def _choose_index(self, *, action: str, attached_only: bool) -> None:
        database = self.database
        assert database is not None
        definitions = indexing.indexes(database, attached=attached_only or None)
        if not definitions:
            self._notice("There are no indexes for this database.")
            return
        items = []
        markers = []
        for definition in definitions:
            items.append((definition.label, definition.name))
            markers.append("\u25b8 " if definition.attached else "  ")
        self.overlay = Overlay("choose", text="Index Files", items=items,
                               markers=markers, action=action)

    def _start_index_session(self, mode: str) -> None:
        database = self.database
        if database is None:
            return
        name = self.pending_index_name.strip().upper()
        if not name:
            self.overlay = None
            self._notice("Enter an index filename.")
            return
        if len(name) > 8:
            self.overlay = None
            self._notice("Index names use at most 8 characters.")
            return
        existing = indexing.find_index(database, name)
        self.index_session = IndexSession(
            database, name, self.theme, mode=mode, existing=existing)
        self.overlay = None
        self.base = "index"

    def _handle_index_session(self, key: Key) -> None:
        session = self.index_session
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help("indexes")
            return
        session.handle(key)
        if session.close:
            self._finish_index_session()

    def _finish_index_session(self) -> None:
        session = self.index_session
        self.index_session = None
        self.base = "menu"
        if session is None:
            return
        if session.saved is not None:
            self._notice(session.status)
            if self.records is not None:
                self.records.apply_range()
        elif session.status:
            self._notice(session.status)

    def _start_range_session(self, *, return_base: str,
                             temporary: bool = False,
                             settings=None) -> None:
        if not temporary and self._files_protected("Ranges"):
            return
        database = self.database
        if database is None:
            self._notice("Select a database first.")
            return
        self.return_base = return_base
        self.range_session = RangeSession(
            database, self.theme,
            settings=settings or database.current_range,
            temporary=temporary)
        self.base = "range"

    def _handle_range_session(self, key: Key) -> None:
        session = self.range_session
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help("ranges")
            return
        session.handle(key)
        if session.close:
            self._finish_range_session()

    def _finish_range_session(self) -> None:
        session = self.range_session
        self.range_session = None
        if session is None:
            return
        if session.applied and self.records is not None \
                and self.return_base == "records":
            self.records.apply_range()
        if session.applied and self.search_session is not None \
                and self.return_base == "search":
            self.search_session.set_range(session.settings)
            self.base = "search"
            return
        if session.applied and self.pending_saved_search:
            letter = self.pending_saved_search
            self.pending_saved_search = ""
            self.base = "menu"
            self._run_saved_search(letter, session.settings)
            return
        if session.applied and self.return_base == "menu" \
                and self.records is not None:
            self.records.apply_range()
        if session.applied and self.return_base in (
                "utility", "relational", "transfer", "global"):
            target = {
                "utility": self.utility_session,
                "relational": self.relational_session,
                "transfer": self.transfer_session,
                "global": self.global_session,
            }[self.return_base]
            if target is not None:
                target.set_range(session.settings)
        if session.status and not session.applied:
            self._notice(session.status)
        self.base = self.return_base
        if self.pending_saved_search:
            self.pending_saved_search = ""

    def _choose_saved_range(self) -> None:
        database = self.database
        assert database is not None
        ranges = indexing.saved_ranges(database)
        if not ranges:
            self._notice("There are no saved ranges.")
            return
        items = [("Default Range", "DEFAULT")]
        for letter, description, _settings in ranges:
            items.append((f"{letter} - {description or 'Range ' + letter}",
                          letter))
        self.overlay = Overlay("choose", text="Retrieve a Range",
                               items=items, action="apply-range")

    def _start_search_session(self, *, letter: str | None = None,
                              existing=None) -> None:
        if self._files_protected("Search/Sort lists"):
            return
        database = self.database
        if database is None:
            self._notice("Select a database first.")
            return
        self.search_session = SearchSession(
            database, self.theme, letter=letter, existing=existing)
        self.base = "search"
        self.overlay = None

    def _handle_search_session(self, key: Key) -> None:
        session = self.search_session
        assert session is not None
        if key.name == "F1" and not key.alt:
            self._open_help("search")
            return
        session.handle(key)
        if session.request_range:
            session.request_range = False
            self._start_range_session(return_base="search", temporary=True,
                                      settings=session.range_settings)
            return
        if session.close:
            self._finish_search_session()

    def _finish_search_session(self) -> None:
        session = self.search_session
        self.search_session = None
        self.base = "menu"
        if session is None:
            return
        if session.result is not None:
            self._notice(f"{len(session.result.seqs)} record(s) in the "
                         "Search/Sort List.")
            if self.records is not None:
                self.records.apply_range()

    def _search_action(self, action: str) -> None:
        database = self.database
        if database is None:
            self._notice("Select a database first.")
            return
        if action == "create":
            self.overlay = Overlay(
                "prompt", text="Enter search/sort letter A-Z (blank for A)",
                action="search-letter", action_title="Saved Search/Sort")
        elif action == "run":
            searches = indexing.saved_searches(database)
            if not searches:
                self._notice("There are no saved search/sort definitions.")
                return
            items = [(f"{search.letter} - {search.description or search.letter}",
                      search.letter) for search in searches]
            self.overlay = Overlay("choose", text="Saved Search/Sort",
                                   items=items, action="run-saved")
        elif action == "one-time":
            self._start_search_session()
        elif action == "erase":
            searches = indexing.saved_searches(database)
            if not searches:
                self._notice("There are no saved search/sort definitions.")
                return
            items = [(f"{search.letter} - {search.description or search.letter}",
                      search.letter) for search in searches]
            self.overlay = Overlay("choose", text="Erase Search/Sort",
                                   items=items, action="erase-saved")
        elif action == "history":
            if not indexing.search_history(database):
                self._notice("The Search/Sort history is empty.")
                return
            self.overlay = Overlay("search-history")

    def _run_saved_search(self, letter: str,
                          settings=None) -> None:
        database = self.database
        if database is None:
            return
        try:
            result = indexing.run_saved_search(
                database, letter,
                range_settings=settings or database.current_range)
        except (indexing.IndexError_, WorkspaceError) as exc:
            self._notice(f"Cannot run search {letter}: {exc}")
            return
        self._notice(f"{len(result.seqs)} record(s) in the "
                     "Search/Sort List.")
        if self.records is not None:
            self.records.apply_range()

    def _other_action(self, action: str) -> None:
        self.overlay = None
        if action == "pattern":
            workspace = (self.database.workspace if self.database is not None
                         else self.workspace)
            if workspace is None:
                self._notice("Open a database first.")
                return
            modes = ["exact", "case", "insensitive"]
            current = workspace.pattern_mode
            value = modes[(modes.index(current) + 1) % len(modes)]
            workspace.pattern_mode = value
            label = {"exact": "Exact", "case": "Case",
                     "insensitive": "Case-insensitive"}[value]
            self._notice(f"Pattern matching: {label}.")
            return
        self._notice(f"Other → {action} is not available yet (wave O12).")

    def _global_action(self, action: str) -> None:
        self.overlay = None
        if action == "duplicates":
            self._delete_duplicates()
            return
        if self.database is None:
            self._notice("Select a database first.")
            return
        self.global_session = GlobalSession(self.database, action, self.theme)
        self.base = "global"

    def _delete_duplicates(self) -> None:
        database = self.database
        if database is None:
            self._notice("Select a database first.")
            return
        if database.primary_index in (RECORD_NUMBER, indexing.SEARCH_LIST) \
                or database.primary_index.startswith(SEARCH_PREFIX):
            self._notice("Select an index before deleting duplicates.")
            return
        session = RecordSession(database, "view", self.theme)
        removed = session.delete_duplicates()
        self._notice(session.status)
        if removed and self.records is not None:
            self.records.apply_range()

    # -- richieste delle modalità record --------------------------------
    def _record_request(self, request: str) -> None:
        session = self.records
        if session is None:
            return
        if request == "find":
            self.overlay = Overlay(
                "prompt", text=f"Which '{session.find_label()}'",
                action="find", action_title="Find")
        elif request == "locate":
            self.overlay = Overlay(
                "prompt", text="Locate", action="locate",
                action_title="Locate a Record")
        elif request == "index":
            self._choose_primary()
        elif request == "range":
            self._start_range_session(return_base="records",
                                      settings=session.range_settings)
        elif request == "replace":
            self.overlay = Overlay(
                "prompt", text="Search for", action="replace-find",
                action_title="Search and Replace")
        elif request == "tools":
            self._open_tools()

    def _open_fields(self, title: str, chosen: list[str],
                     action: str) -> None:
        database = self.database
        if database is None:
            return
        items = [(field.name, field.name) for field in database.fields]
        self.overlay = Overlay("fields", text=title, items=items,
                               chosen=chosen, action=action)

    def _toggle_field_choice(self) -> None:
        overlay = self.overlay
        assert overlay is not None
        if not overlay.items:
            return
        name = overlay.items[overlay.selected][1]
        upper = name.upper()
        if upper in {item.upper() for item in overlay.chosen}:
            overlay.chosen = [item for item in overlay.chosen
                              if item.upper() != upper]
        else:
            overlay.chosen.append(name)

    # -- dispatcher degli elenchi ---------------------------------------
    def _activate_choose(self) -> None:
        overlay = self.overlay
        assert overlay is not None
        if not overlay.items:
            return
        label, value = overlay.items[overlay.selected]
        action = overlay.action
        self.overlay = None
        database = self.database
        if action == "run-app":
            self._open_application_session_by_name(value)
            return
        if action == "erase-app":
            self.overlay = Overlay("confirm",
                                   text=f"Erase application {value}?",
                                   action=f"delete-app:{value}")
            return
        if action == "protect-scope":
            scope, _, owner = value.partition(":")
            workspace = self._workspace()
            if workspace is None:
                return
            self.protection_session = ProtectionSession(
                workspace, owner, self.theme)
            self.application_return_base = self.base
            self.base = "protection"
            return
        if action == "modify-script":
            self._open_script(value)
            return
        if action in ("play-script", "play-tools"):
            self._play_script(value)
            return
        if action == "erase-script":
            self.overlay = Overlay("confirm", text=f"Erase script {value}?",
                                   action=f"delete-script:{value}")
            return
        if action == "debug-script":
            self._open_script_debug(value)
            return
        if action in ("open-set", "modify-set", "switch"):
            name = value
            if value.startswith("SET:"):
                self._activate_set(value.split(":", 1)[1])
                return
            if action == "open-set":
                self._activate_set(name)
                return
            definition = self._workspace().get_set(name) if self._workspace() else None
            if definition is None:
                return
            self.set_designer = SetDesigner(
                definition.workspace, self.database, definition=definition,
                theme=self.theme)
            self.base = "setdesigner"
            return
        if action in ("borrow-label", "erase-label", "print-label"):
            workspace = self._workspace()
            if workspace is None:
                return
            label = workspace.get_label(self._form_owner(), value)
            if label is None:
                return
            if action == "print-label":
                self._open_label_preview(label)
            elif action == "erase-label":
                self.overlay = Overlay(
                    "confirm", text=f"Erase label {value}?",
                    action=f"delete-label:{value}")
            else:
                self.label_designer = LabelDesigner(
                    workspace, self.database, owner=self._form_owner(),
                    label=label, theme=self.theme, stage="borrow_letter",
                    letter_text="", edit_existing=False)
                self.base = "labeldesigner"
            return
        if action in ("print-letter", "erase-letter"):
            workspace = self._workspace()
            if workspace is None:
                return
            letter = workspace.get_letter(self._form_owner(), value)
            if letter is None:
                return
            if action == "print-letter":
                self._open_letter_preview(letter)
            else:
                self.overlay = Overlay(
                    "confirm", text=f"Erase letter {value}?",
                    action=f"delete-letter:{value}")
            return
        if action in ("borrow-report", "erase-report", "print-report"):
            workspace = self._workspace()
            if workspace is None:
                return
            report = workspace.get_report(self._form_owner(), value)
            if report is None:
                return
            if action == "print-report":
                self._open_report_preview(report)
            elif action == "erase-report":
                self.overlay = Overlay(
                    "confirm", text=f"Erase report {value}?",
                    action=f"delete-report:{value}")
            else:
                self.report_designer = ReportDesigner(
                    workspace, self.database, owner=self._form_owner(),
                    report=report, theme=self.theme, stage="borrow_letter",
                    letter_text="", edit_existing=False)
                self.base = "reportdesigner"
            return
        if action in ("select-form", "erase-form"):
            if action == "select-form":
                self._workspace().set_active_form(self._form_owner(), value)
                self._notice(f"Form {value} is now active.")
            else:
                self.overlay = Overlay(
                    "confirm", text=f"Erase form {value}?",
                    action=f"delete-form:{value}")
            return
        if action == "erase-set":
            self.overlay = Overlay(
                "confirm", text=f"Erase set {value}?",
                action=f"delete-set:{value}")
            return
        if database is None:
            return
        if action == "set-primary":
            database.set_primary_index(value)
            if self.records is not None:
                self.records.apply_range()
            self._notice(f"Primary index: {indexing.primary_label(database)}.")
        elif action == "update-index":
            definition = indexing.find_index(database, value)
            if definition is not None:
                self.index_session = IndexSession(
                    database, definition.name, self.theme,
                    existing=definition)
                self.base = "index"
        elif action == "toggle-attach":
            definition = indexing.find_index(database, value)
            if definition is None:
                return
            try:
                indexing.set_index_attached(
                    database, value, not definition.attached)
            except indexing.IndexError_ as exc:
                self._notice(str(exc))
                return
            self._notice(
                f"Index {value} "
                + ("attached." if not definition.attached else "detached."))
        elif action == "erase-index":
            self.overlay = Overlay(
                "confirm", text=f"Erase index {value}?",
                action=f"delete-index:{value}")
        elif action == "apply-range":
            if value == "DEFAULT":
                settings = indexing.default_range()
            else:
                found = indexing.get_range(database, value)
                if found is None:
                    return
                settings = found[1]
            database.save_current_range(settings)
            if self.records is not None:
                self.records.apply_range(settings)
            self._notice("Range retrieved.")
        elif action == "run-saved":
            saved = indexing.saved_search(database, value)
            if saved is None:
                return
            if saved.sort_rows or saved.sort_expression.strip():
                self._run_saved_search(value)
            else:
                self.pending_saved_search = value
                self._start_range_session(return_base="menu",
                                          temporary=True)
        elif action == "erase-saved":
            self.overlay = Overlay(
                "confirm", text=f"Erase search/sort {value}?",
                action=f"erase-search:{value}")

    def _refresh_selected_history(self) -> None:
        overlay = self.overlay
        database = self.database
        if overlay is None or database is None:
            return
        history = indexing.search_history(database, limit=10)
        if not history:
            self.overlay = None
            return
        search = history[min(overlay.selected, len(history) - 1)]
        try:
            rebuilt = indexing.refresh_search_list(database, search.id)
        except (indexing.IndexError_, WorkspaceError) as exc:
            self._notice(f"Cannot refresh: {exc}")
            return
        overlay.selected = 0
        if self.records is not None:
            self.records.apply_range()
        self._notice(f"Search/Sort refreshed: {len(rebuilt.seqs)} record(s).")

    def _delete_selected_history(self) -> None:
        overlay = self.overlay
        database = self.database
        if overlay is None or database is None:
            return
        history = indexing.search_history(database, limit=10)
        if not history:
            self.overlay = None
            return
        search = history[min(overlay.selected, len(history) - 1)]
        self.overlay = Overlay(
            "confirm", text=f"Delete Search/Sort List '{search.label}'?",
            action=f"delete-search-list:{search.id}")

    def _activate_search_history(self) -> None:
        overlay = self.overlay
        assert overlay is not None
        database = self.database
        if database is None:
            self.overlay = None
            return
        history = indexing.search_history(database, limit=10)
        if not history:
            self.overlay = None
            return
        selected = min(overlay.selected, len(history) - 1)
        search = history[selected]
        database.set_primary_index(f"{SEARCH_PREFIX}{search.id}")
        self.overlay = None
        if self.records is not None:
            self.records.apply_range()
            self.base = "records"
        else:
            self.base = "menu"
        self._notice(f"Search/Sort: {search.label}.")

    def _open_info(self, screen: str) -> None:
        if self.state.current is None:
            self._notice("Select a database first.")
            return
        self.base = screen
        self.structure_page = 0

    # -- struttura e stato ----------------------------------------------
    def _handle_structure(self, key: Key) -> None:
        header = self.state.current.header if self.state.current else None
        pages = 1
        if header is not None and header.fields:
            pages = (len(header.fields) + 14) // 15
        if key.name == "PGDN":
            self.structure_page = min(pages - 1, self.structure_page + 1)
        elif key.name == "PGUP":
            self.structure_page = max(0, self.structure_page - 1)
        elif key.name in ("F10", "ESC"):
            self.base = "menu"
        elif key.name == "F1":
            self._open_help("structure")

    def _handle_status(self, key: Key) -> None:
        if key.name in ("F10", "ESC"):
            self.base = "menu"
        elif key.name == "F1":
            self._open_help("status")

    # -- overlay ---------------------------------------------------------
    def _notice(self, text: str) -> None:
        self.overlay = Overlay("message", text=text)

    def _open_help(self, topic_id: str, *, push: bool = False) -> None:
        stack: list[str] = []
        if push and self.overlay is not None and self.overlay.kind == "help":
            stack = self.overlay.stack + [self.overlay.topic_id]
        self.overlay = Overlay("help", topic_id=topic_id, stack=stack)

    def _help_link_count(self) -> int:
        assert self.overlay is not None
        lines = wrap_topic(topic(self.overlay.topic_id))
        return len(link_spans(lines))

    def _open_history(self) -> None:
        if not self.state.history:
            self._notice("The selection history is empty.")
            return
        self.overlay = Overlay("history")

    def _handle_overlay(self, key: Key) -> None:
        overlay = self.overlay
        assert overlay is not None
        name = key.name
        if overlay.kind == "message":
            if name in ("ENTER", "ESC", "F10"):
                self.overlay = None
            return
        if overlay.kind == "submenu":
            count = len(overlay.items) or len(DESKTOP_ITEMS)
            if name == "UP":
                overlay.selected = (overlay.selected - 1) % count
            elif name == "DOWN":
                overlay.selected = (overlay.selected + 1) % count
            elif name == "ENTER":
                self._activate_overlay_item()
            elif name == "ESC":
                self.overlay = None
            return
        if overlay.kind == "confirm":
            if name == "ENTER":
                self._confirm_action()
            elif name == "ESC":
                self.overlay = None
            return
        if overlay.kind == "choose":
            if name == "UP":
                overlay.selected = max(0, overlay.selected - 1)
            elif name == "DOWN":
                overlay.selected = min(len(overlay.items) - 1,
                                       overlay.selected + 1)
            elif name == "PGUP":
                overlay.selected = max(0, overlay.selected - 10)
            elif name == "PGDN":
                overlay.selected = min(len(overlay.items) - 1,
                                       overlay.selected + 10)
            elif name == "ENTER":
                self._activate_choose()
            elif name == "ESC":
                self.overlay = None
            return
        if overlay.kind == "fields":
            if name == "UP":
                overlay.selected = max(0, overlay.selected - 1)
            elif name == "DOWN":
                overlay.selected = min(len(overlay.items) - 1,
                                       overlay.selected + 1)
            elif name == "PGUP":
                overlay.selected = max(0, overlay.selected - 10)
            elif name == "PGDN":
                overlay.selected = min(len(overlay.items) - 1,
                                       overlay.selected + 10)
            elif name in ("ENTER", "SPACE"):
                self._toggle_field_choice()
            elif name == "F3":
                overlay.chosen = [label for label, _value in overlay.items
                                  if not (self.database is not None
                                          and self.database.field(label).is_memo)]
            elif name == "F4":
                overlay.chosen = [label for label, _value in overlay.items]
            elif name == "F10":
                chosen = list(overlay.chosen)
                action = overlay.action
                self.overlay = None
                if action == "locate-fields" and self.records is not None:
                    self.records.start_locate(self.pending_locate_text, chosen)
                elif action == "replace-fields":
                    self.overlay_chosen = chosen
                    self.overlay = Overlay(
                        "confirm",
                        text=f"Replace all occurrences in "
                             f"{len(chosen)} field(s)?",
                        action="replace-all")
            elif name == "ESC":
                self.overlay = None
            return
        if overlay.kind == "search-history":
            if name == "UP":
                overlay.selected = max(0, overlay.selected - 1)
            elif name == "DOWN":
                history = (indexing.search_history(self._active_database())
                           if self._active_database() else [])
                overlay.selected = min(max(0, len(history) - 1),
                                       overlay.selected + 1)
            elif name == "ENTER":
                self._activate_search_history()
            elif name == "F5":
                self._refresh_selected_history()
            elif name == "F4":
                self._delete_selected_history()
            elif name == "ESC":
                self.overlay = None
            return
        if overlay.kind == "prompt":
            if name == "ENTER":
                self._submit_prompt()
            elif name == "ESC":
                self.overlay = None
            elif name == "LEFT":
                overlay.input_cursor = max(0, overlay.input_cursor - 1)
            elif name == "RIGHT":
                overlay.input_cursor = min(len(overlay.input_text),
                                           overlay.input_cursor + 1)
            elif name == "HOME":
                overlay.input_cursor = 0
            elif name == "END":
                overlay.input_cursor = len(overlay.input_text)
            elif name == "BACKSPACE":
                if overlay.input_cursor:
                    overlay.input_text = (
                        overlay.input_text[:overlay.input_cursor - 1]
                        + overlay.input_text[overlay.input_cursor:])
                    overlay.input_cursor -= 1
            elif name == "DELETE":
                overlay.input_text = (
                    overlay.input_text[:overlay.input_cursor]
                    + overlay.input_text[overlay.input_cursor + 1:])
            else:
                char = character(key)
                if char:
                    if len(char) == 1 and char.isalpha() and not key.shift:
                        char = char.lower()
                    overlay.input_text = (
                        overlay.input_text[:overlay.input_cursor] + char
                        + overlay.input_text[overlay.input_cursor:])
                    overlay.input_cursor += 1
            return
        if overlay.kind == "history":
            history = self.state.history
            if name == "UP":
                overlay.selected = max(0, overlay.selected - 1)
            elif name == "DOWN":
                overlay.selected = min(len(history) - 1, overlay.selected + 1)
            elif name == "ENTER":
                self._activate_history()
            elif name == "ESC":
                self.overlay = None
            return
        if overlay.kind == "variables":
            if name == "UP":
                overlay.selected = max(0, overlay.selected - 1)
            elif name == "DOWN":
                overlay.selected = min(max(0, len(overlay.items) - 1),
                                       overlay.selected + 1)
            elif name == "ENTER" and overlay.items:
                variable = overlay.items[overlay.selected][0]
                value = overlay.items[overlay.selected][1]
                self.overlay = Overlay(
                    "prompt", text=f"{variable} = {value}",
                    action=f"variable-edit:{variable}",
                    action_title="Script Variable")
            elif name == "F4" and overlay.items:
                variable = overlay.items[overlay.selected][0]
                self._script_engine().variables.delete(variable)
                overlay.items = self._script_engine().variables.items()
                overlay.selected = min(overlay.selected,
                                       max(0, len(overlay.items) - 1))
            elif name in ("F10", "ESC"):
                self.overlay = None
            return
        if overlay.kind == "help":
            if name == "ESC":
                self.overlay = None
            elif name in ("BACKSPACE", "LEFT"):
                if overlay.stack:
                    previous = overlay.stack.pop()
                    overlay.topic_id = previous
                    overlay.scroll = 0
                    overlay.link = 0
                else:
                    self.overlay = None
            elif name == "UP":
                if self._help_link_count():
                    overlay.link = max(0, overlay.link - 1)
                else:
                    overlay.scroll = max(0, overlay.scroll - 1)
            elif name == "DOWN":
                if self._help_link_count():
                    overlay.link = min(self._help_link_count() - 1, overlay.link + 1)
                else:
                    overlay.scroll += 1
            elif name == "PGUP":
                overlay.scroll = max(0, overlay.scroll - 6)
            elif name == "PGDN":
                overlay.scroll += 6
            elif name == "ENTER":
                spans = link_spans(wrap_topic(topic(overlay.topic_id)))
                if spans and overlay.link < len(spans):
                    self._open_help(spans[overlay.link].target, push=True)

    def _desktop_action(self, action: str) -> None:
        if action in ("open-set", "switch"):
            self._choose_desktop(action)
            return
        if action == "close":
            self.active_set = None
            self.database = None
            self.state.database = None
            self.state.set_name = ""
            self.state.current = None
            self.base = "directory"
            self.overlay = None
            self._notice("Database closed.")
            return
        if action == "open":
            self.overlay = None
            if self.state.current is not None:
                try:
                    self.state.change_directory(self.state.current.path.parent)
                except OSError:
                    self.state.refresh()
            else:
                self.state.refresh()
            self.base = "directory"
            self.cursor = self.first = 0
            if self.state.current is not None and self.state.listing is not None:
                index = self.state.listing.index_of(self.state.current.path)
                if index >= 0:
                    self.cursor = index
            if self.cursor == 0:
                self.cursor = self._first_file_index()
            self._sync_input()
        else:
            self._notice("Desktop management is not available yet (wave O5).")

    def _activate_history(self) -> None:
        overlay = self.overlay
        assert overlay is not None
        path = self.state.history[overlay.selected]
        self.overlay = None
        self._open_entry(path)

    def _to_main_menu(self) -> None:
        if self.base in ("scripteditor", "dialogdesigner", "menubardesigner",
                         "scriptdebugger", "scriptdialog") and self.overlay is None:
            self.script_editor = None
            self.dialog_designer = None
            self.menu_designer = None
            self.script_debug = None
            self.dialog_runtime = None
            self.script_display_dialog = None
            self.base = "menu"
            return
        if self.base == "formdesigner" and self.overlay is None:
            self.form_designer = None
            self.base = "menu"
            return
        if self.base == "reportdesigner" and self.overlay is None:
            self.report_designer = None
            self.base = "menu"
            return
        if self.base == "reportpreview" and self.overlay is None:
            self.report_preview = None
            self.base = "menu"
            return
        if self.base == "labeldesigner" and self.overlay is None:
            self.label_designer = None
            self.base = "menu"
            return
        if self.base == "lettereditor" and self.overlay is None:
            self.letter_editor = None
            self.base = "menu"
            return
        if self.base in ("setrecords", "setdesigner") and self.overlay is None:
            if self.base == "setrecords":
                self.set_records = None
            else:
                self.set_designer = None
            self.base = "menu"
            return
        if self.base == "rules" and self.overlay is None:
            if self.rules_session is not None:
                self.rules_session.close = True
                self._finish_rules_session()
            return
        if self.base in ("index", "range", "search") and self.overlay is None:
            if self.base == "index" and self.index_session is not None:
                self.index_session.close = True
                self._finish_index_session()
            elif self.base == "range" and self.range_session is not None:
                self.range_session.close = True
                self._finish_range_session()
            elif self.base == "search" and self.search_session is not None:
                self.search_session.close = True
                self._finish_search_session()
            return
        if self.base == "records" and self.records is not None:
            if self.records.memo is not None:
                self._notice("Save or cancel the memo first.")
                return
            if self.records.dirty:
                self._notice("Save the record with F10 or cancel with ESC first.")
                return
            self._finish_records()
            return
        if self.base == "designer" and self.designer is not None:
            if self.designer.dirty:
                self._notice("Save the database with F10 or cancel with ESC first.")
                return
            self._finish_designer()
            return
        if self.overlay is not None:
            self.overlay = None
            if self.base != "menu" and self.state.current is not None:
                self.base = "menu"
            return
        if self.state.current is not None:
            self.base = "menu"
            self.overlay = None
        else:
            self._notice("No database selected.")


def demo_controller() -> ShellController:
    """Controllore deterministico per smoke test e screenshot."""
    controller = ShellController.__new__(ShellController)
    controller.state = demo_state()
    controller.theme = NEWPORT
    controller.menu_index = 0
    controller.cursor = 0
    controller.first = 0
    controller.input_text = controller.state.listing.entries[0].selectable_text
    controller.input_cursor = len(controller.input_text)
    controller.structure_page = 0
    controller.overlay = None
    controller.quit = False
    controller.workspace = None
    controller.database = None
    controller.records = None
    controller.designer = None
    controller.form_designer = None
    controller.report_designer = None
    controller.report_preview = None
    controller.label_designer = None
    controller.letter_editor = None
    controller.set_designer = None
    controller.set_records = None
    controller.active_set = None
    controller.clipboard = [""]
    controller.pending_path = None
    controller.base = "menu"
    controller.script_editor = None
    controller.dialog_designer = None
    controller.menu_designer = None
    controller.script_debug = None
    controller.dialog_runtime = None
    controller.script_directory = None
    controller.script_engine = None
    controller.script_return_base = "menu"
    controller.recording = None
    controller.recording_name = ""
    controller.recording_source = ""
    controller.script_writes = []
    controller.script_beeps = 0
    controller.script_tones = []
    controller.script_pauses = 0
    controller.script_waits = []
    controller.script_screen_mode = ""
    controller.script_deferred = []
    controller.script_mouse = []
    controller.script_cursor = (1, 1)
    controller.script_display_dialog = None
    controller._flushing = False
    controller._opening_script = False
    controller._in_script = False
    controller._firing_trigger = False
    return controller


__all__ = ["COMMAND_WAVES", "DESKTOP_ITEMS", "INPUT_COL", "Overlay",
           "ShellController", "demo_controller"]
