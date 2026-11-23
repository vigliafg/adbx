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
from ..screen.keys import Key, character
from ..screen.keys import parse as parse_key
from . import screens
from .files import strip_wildcard
from .help import link_spans, topic, wrap_topic
from .state import ShellState, default_root, demo_state
from .theme import NEWPORT, Theme
from .widgets import View

INPUT_LABEL = "Enter name of the database/set"
INPUT_COL = 1 + len(INPUT_LABEL) + 3
LIST_TOP = screens.LIST_TOP
LIST_VISIBLE = STATUS_ROW - LIST_TOP

DESKTOP_ITEMS: tuple[tuple[str, str | None], ...] = (
    ("Open a database", "open"),
    ("Switch databases", "switch"),
    ("Close a database", "close"),
    ("Save current desktop", "save"),
    ("Retrieve a desktop", "retrieve"),
    ("Erase a desktop", "erase"),
)

COMMAND_WAVES = {
    "view": "O2",
    "print": "O7",
    "search": "O3",
    "indexes": "O3",
    "global": "O9",
    "design": "O2",
    "layouts": "O6",
    "applications": "O10",
    "utilities": "O9",
    "other": "O12",
}


@dataclass
class Overlay:
    kind: str
    text: str = ""
    topic_id: str = "main_menu"
    scroll: int = 0
    link: int = 0
    selected: int = 0
    stack: list[str] = field(default_factory=list)


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

        if open_path is not None:
            self._open_entry(Path(open_path))
        else:
            self.state.refresh()
        self.base = "menu" if self.state.current else "directory"
        self.cursor = self.first = self._first_file_index()
        self._sync_input()

    # -- accesso alle schermate -----------------------------------------
    def view(self) -> View:
        if self.base == "directory":
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
        if overlay.kind == "submenu":
            return screens.submenu_overlay(base, list(DESKTOP_ITEMS),
                                           overlay.selected, self.theme)
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
        if self.base == "directory":
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
                self._activate_desktop()
        elif kind == "history" and self.overlay is not None:
            self.overlay.selected = int(value)
            if double:
                self._activate_history()
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
            self._notice("Create database is not available yet (wave O2).")
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
            self._notice("Sets are not available yet (wave O5).")
            return
        try:
            current = self.state.open(path)
        except (OSError, ValueError) as exc:
            self._notice(f"Cannot open {path.name}: {exc}")
            return
        self.state.change_directory(path.parent)
        self.base = "menu"
        self.menu_index = 0
        self.overlay = None
        self._sync_input()
        if current.records is None:
            self._notice(f"Opened {current.name} (record count unavailable).")

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
            self.overlay = Overlay("submenu")
            return
        wave = COMMAND_WAVES.get(topic_id, "a later wave")
        self._notice(f"{label} is not available yet (wave {wave}).")

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
            if name == "UP":
                overlay.selected = (overlay.selected - 1) % len(DESKTOP_ITEMS)
            elif name == "DOWN":
                overlay.selected = (overlay.selected + 1) % len(DESKTOP_ITEMS)
            elif name == "ENTER":
                self._activate_desktop()
            elif name == "ESC":
                self.overlay = None
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

    def _activate_desktop(self) -> None:
        overlay = self.overlay
        assert overlay is not None
        action = DESKTOP_ITEMS[overlay.selected][1]
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
    controller.base = "menu"
    return controller


__all__ = ["COMMAND_WAVES", "DESKTOP_ITEMS", "INPUT_COL", "Overlay",
           "ShellController", "demo_controller"]
