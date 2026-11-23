"""Controllore del guscio: stato, schermate, tastiera e mouse.

È il punto in cui gli eventi diventano comandi. Lo stesso `handle(Key)` sarà
usato dal motore di script (O10) per digitare sequenze: qui non esiste altra
strada di input.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW
from ..data import indexing
from ..data import rules as field_rules
from ..data.indexing import RECORD_NUMBER, SEARCH_PREFIX
from ..data.workspace import Database, Workspace, WorkspaceError
from ..screen.keys import Key, character
from ..screen.keys import parse as parse_key
from . import screens
from .designer import DesignerSession
from .files import strip_wildcard
from .help import link_spans, topic, wrap_topic
from .indexes import IndexSession, RangeSession
from .records import RecordSession
from .rules import RulesSession
from .searching import SearchSession
from .sets import SetDesigner, SetSession
from .state import ShellState, default_root, demo_state
from .theme import NEWPORT, Theme
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
    "applications": "O10",
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

RULES_ITEMS: tuple[tuple[str, str], ...] = (
    ("Create/edit field rules", "edit"),
    ("Re-evaluate field rules", "reevaluate"),
    ("Erase field rules", "erase"),
)

UTILITY_ITEMS: tuple[tuple[str, str], ...] = (
    ("Pack database", "pack"),
    ("Copy database", "copy"),
    ("Append to database", "append"),
    ("Summarize database", "summarize"),
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
        return self._with_overlay(base)

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
                "indexes": "Indexes/Ranges",
                "search": "Search/Sort Lists",
                "global": "Global Update/Delete",
                "index-mode": "Create an Index",
                "other": "Other",
                "field-rules": "Field Rules",
                "sets": "Set Commands",
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
        if overlay.kind == "help":
            view, _spans, _positions = screens.help_overlay(
                base, overlay.topic_id, scroll=overlay.scroll,
                link_index=overlay.link, theme=self.theme)
            return view
        return base

    # -- input -----------------------------------------------------------
    def handle(self, key: Key) -> None:
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
        if self.active_set is not None:
            self.set_records = SetSession(self.active_set, mode, self.theme)
            self.base = "setrecords"
            self.overlay = None
            return
        self.records = RecordSession(self.database, mode, self.theme,
                                     clipboard=self.clipboard,
                                     show_deleted=show_deleted)
        self.base = "records"
        self.overlay = None

    def _handle_records(self, key: Key) -> None:
        session = self.records
        assert session is not None
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

    # -- set -------------------------------------------------------------
    def _set_action(self, action: str) -> None:
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
        self._notice(f"Utilities → {action} is not available yet (wave O9).")

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
        if session.status:
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
        self._notice(f"Global update → {action} is not available yet "
                     "(wave O9).")

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
    controller.clipboard = [""]
    controller.pending_path = None
    controller.base = "menu"
    return controller


__all__ = ["COMMAND_WAVES", "DESKTOP_ITEMS", "INPUT_COL", "Overlay",
           "ShellController", "demo_controller"]
