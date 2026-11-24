"""Set: editor dei link e modalità di consultazione (O5).

Il designer ha due finestre: l'albero del set in alto e i parametri del link
in basso. Il visualizzatore combina il database primario con i figli uno-a-uno
e mostra i figli uno-a-molti in una regione separata, con zoom sul figlio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..cell.buffer import (
    Cell,
    CellBuffer,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    STATUS_ROW,
    clipping_allowed,
)
from ..data import indexing
from ..data.fields import Field, FieldError, format_value, parse_value
from ..data.rules import FieldRule
from ..data.sets import (
    CHILD_MODES,
    INCLUDE_MODES,
    LINK_MODES,
    Link,
    SetDefinition,
    SetError,
)
from ..data.workspace import Database, Workspace
from ..screen.keys import Key, character
from .dialogs import Picker, picker_view
from .records import RecordSession
from .theme import NEWPORT, Theme
from .widgets import (
    View,
    clip_text,
    visible_rows,
    draw_help_line,
    draw_menu_line,
    draw_status_line,
    title_bar,
)

SET_KEYS = [("F1", "Help"), ("F5", "Detach"), ("F6", "Add link"),
            ("F7", "Integrity"), ("F9", "Switch"), ("F10", "Save"),
            ("ESC", "Cancel")]
SET_FIELDS = [("F1", "Help"), ("F2", "Databases"), ("F5", "Delete field"),
              ("F6", "Insert field"), ("F10", "Save"), ("ESC", "Cancel")]
SET_SESSION_KEYS = [("F1", "Help"), ("F6", "Child region"), ("Alt-Z", "Zoom"),
                    ("F10", "Continue"), ("ESC", "Cancel")]
TOP_TOP = 3
LINK_TOP = 14


@dataclass(frozen=True)
class LinkRow:
    key: str
    label: str
    kind: str = "text"
    choices: tuple[str, ...] = ()


@dataclass
class SetDesigner:
    workspace: Workspace
    database: Database | None = None
    definition: SetDefinition | None = None
    theme: Theme = NEWPORT
    stage: str = "name"
    name_text: str = ""
    description_text: str = ""
    primary: str = ""
    show_mode: str = "not_deleted"
    filter: str = ""
    filter_active: bool = False
    window: str = "top"
    selected: int = 0
    row: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    editing: bool = False
    picker: Picker | None = None
    picker_kind: str = ""
    integrity_editor: Any = None
    status: str = ""
    close: bool = False
    saved: bool = False
    saved_definition: SetDefinition | None = None
    help_topic: str = "sets"

    def __post_init__(self) -> None:
        if self.definition is not None:
            self.stage = "editor"
            self.primary = self.definition.primary
            self.description_text = self.definition.description
            self.show_mode = self.definition.show_mode
            self.filter = self.definition.filter
            self.filter_active = self.definition.filter_active
            self.name_text = self.definition.name
        else:
            self.definition = SetDefinition(
                self.workspace, "", "", self.database.name
                if self.database is not None else "")
            if self.database is not None:
                self.primary = self.database.name
            self.stage = "name"

    @property
    def title(self) -> str:
        if self.stage == "name":
            return "Create a Set Design"
        return f"Set Editor - {self.definition.name if self.definition else ''}"

    @property
    def links(self) -> list[Link]:
        return self.definition.links if self.definition else []

    def top_rows(self) -> list[tuple[int, str, Link | None]]:
        rows: list[tuple[int, str, Link | None]] = []
        if self.definition is None:
            return rows
        rows.append((0, self.definition.primary, None))
        for link in self.definition.links:
            depth = 1
            parent = link.parent
            seen = 0
            while parent != self.definition.primary and seen < 10:
                parent_link = self.definition.link_for(parent)
                if parent_link is None:
                    break
                depth += 1
                parent = parent_link.parent
                seen += 1
            rows.append((depth, link.child, link))
        return rows

    # -- fasi iniziali ---------------------------------------------------
    def _handle_prompt(self, key: Key) -> None:
        name = key.name
        if name == "ENTER":
            if self.stage == "name":
                value = self.name_text.strip().upper()
                if not value:
                    self.status = "Enter a set name."
                    return
                if len(value) > 8:
                    self.status = "Set names use at most 8 characters."
                    return
                if self.workspace.get_set(value) is not None:
                    self.status = f"Set {value} already exists."
                    return
                self.definition.name = value
                self.stage = "description"
                self.edit_text = self.description_text
                self.edit_cursor = len(self.edit_text)
            elif self.stage == "description":
                self.definition.description = self.description_text.strip()
                self.stage = "primary"
                self._open_database_picker()
            return
        if name == "ESC":
            self.close = True
            return
        if name == "BACKSPACE":
            if self.stage == "name":
                self.name_text = self.name_text[:-1]
            else:
                self.description_text = self.description_text[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            if self.stage == "name":
                self.name_text += text.upper()
            else:
                self.description_text += text

    def _open_database_picker(self) -> None:
        names = self.workspace.names()
        self.picker = Picker("Databases", names, purpose="primary",
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "primary"

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
        elif key.name == "ENTER":
            value = picker.value()
            self.picker = None
            if not value:
                return
            if self.picker_kind == "primary":
                self.primary = value
                self.definition.primary = value
                self.stage = "settings"
                self.window = "top"
                self.selected = 0
                self.row = 0
                self._load_row()
            elif self.picker_kind == "child":
                self._current_link().child = value
                self.editing = False
                self._load_row()
            elif self.picker_kind == "index":
                self._current_link().linking_index = value
                self.editing = False
                self._load_row()
            elif self.picker_kind == "parent":
                self._current_link().parent = value
                self.editing = False
                self._load_row()
        elif key.name == "ESC":
            if self.picker_kind == "primary" and self.stage == "primary":
                self.stage = "description"
            self.picker = None

    # -- dispatch --------------------------------------------------------
    def handle(self, key: Key) -> None:
        self.status = ""
        if self.integrity_editor is not None:
            self._handle_editor(key)
            return
        if self.picker is not None:
            self._handle_picker(key)
            return
        if self.stage in ("name", "description"):
            self._handle_prompt(key)
            return
        if self.stage == "primary":
            if key.name in ("ENTER", "F2"):
                self._open_database_picker()
            elif key.name == "ESC":
                self.stage = "description"
            return
        self._handle_editor(key)

    # -- editor ----------------------------------------------------------
    def _current_link(self) -> Link:
        rows = self.top_rows()
        if 0 <= self.selected < len(rows):
            link = rows[self.selected][2]
            if link is not None:
                return link
        if self.links:
            self.selected = min(self.selected, len(rows) - 1)
            link = rows[self.selected][2]
            if link is not None:
                return link
        link = Link(parent=self.primary)
        if self.definition is not None:
            self.definition.links.append(link)
        return link

    def _current_database(self, name: str) -> Database | None:
        return self.workspace.get(name) if name else None

    def _link_rows(self) -> list[LinkRow]:
        if self.definition is None:
            return []
        if self.selected == 0:
            return [
                LinkRow("description", "Set Description"),
                LinkRow("primary", "Primary Database"),
                LinkRow("show_mode", "Show Mode", "cycle",
                        ("All", "Deleted", "Not deleted")),
                LinkRow("filter", "Filter"),
                LinkRow("filter_active", "Filter status", "bool"),
                LinkRow("summary", "Add links with F6", "hint"),
            ]
        link = self._current_link()
        rows = [
            LinkRow("parent", "Link from"),
            LinkRow("child", "Linked Database/Set"),
            LinkRow("linking_index", "Linking Index"),
            LinkRow("common", "Common Field/Expression"),
            LinkRow("link_to", "Link to?", "cycle", LINK_MODES),
            LinkRow("edit_child", "Can edit child database?", "cycle",
                    CHILD_MODES),
            LinkRow("add_child", "Can add new records to child database?",
                    "cycle", CHILD_MODES),
            LinkRow("referential", "Referential Integrity?", "bool"),
        ]
        if link.referential:
            rows.extend([
                LinkRow("cascading_updates", "Cascading Updates?", "bool"),
                LinkRow("cascading_deletes", "Cascading Deletes?", "bool"),
            ])
        rows.extend([
            LinkRow("include_parent", "Include Parent If?", "cycle",
                    INCLUDE_MODES),
            LinkRow("show_mode", "Show Mode", "cycle",
                    ("All", "Deleted", "Not deleted")),
            LinkRow("filter", "Filter"),
            LinkRow("filter_active", "Filter status", "bool"),
            LinkRow("integrity", f"Integrity rule ({len(link.integrity)} "
                                 "mapping(s), F7)", "hint"),
        ])
        return rows

    def _value(self, key: str) -> str:
        if self.definition is None:
            return ""
        if self.selected == 0:
            if key == "description":
                return self.definition.description
            if key == "primary":
                return self.definition.primary
            if key == "show_mode":
                return {"all": "All", "deleted": "Deleted",
                        "not_deleted": "Not deleted"}.get(
                            self.definition.show_mode,
                            self.definition.show_mode)
            if key == "filter":
                return self.definition.filter
            if key == "filter_active":
                return ("Active" if self.definition.filter_active
                        else "Inactive")
            if key == "summary":
                return "F6 adds a link from the selected database"
            return ""
        link = self._current_link()
        if key == "integrity":
            return f"{len(link.integrity)} mapping(s)"
        if key in ("referential", "cascading_updates", "cascading_deletes"):
            return "Yes" if getattr(link, key) else "No"
        if key == "filter_active":
            return "Active" if link.filter_active else "Inactive"
        if key == "show_mode":
            return {"all": "All", "deleted": "Deleted",
                    "not_deleted": "Not deleted"}.get(
                        link.show_mode, link.show_mode)
        return str(getattr(link, key, ""))

    def _set_text(self, key: str, text: str) -> None:
        if self.definition is None:
            return
        if self.selected == 0:
            if key == "description":
                self.definition.description = text
            elif key == "primary":
                self.definition.primary = text.strip().upper()
            elif key == "filter":
                self.definition.filter = text
            return
        link = self._current_link()
        if key in ("parent", "child", "linking_index"):
            setattr(link, key, text.strip().upper())
        elif key == "common":
            link.common = text
        elif key == "filter":
            link.filter = text

    def _cycle(self, row: LinkRow, delta: int) -> None:
        if self.definition is None:
            return
        if self.selected == 0:
            if row.key == "show_mode":
                modes = ("all", "deleted", "not_deleted")
                current = self.definition.show_mode
                index = modes.index(current) if current in modes else 2
                self.definition.show_mode = modes[(index + delta) % 3]
            elif row.key == "filter_active":
                self.definition.filter_active = not self.definition.filter_active
            return
        link = self._current_link()
        if row.key in ("referential", "cascading_updates",
                       "cascading_deletes", "filter_active"):
            setattr(link, row.key, not getattr(link, row.key))
        elif row.key == "show_mode":
            modes = ("all", "deleted", "not_deleted")
            index = modes.index(link.show_mode) if link.show_mode in modes else 2
            link.show_mode = modes[(index + delta) % 3]
        elif row.choices:
            choices = list(row.choices)
            current = getattr(link, row.key, choices[0])
            index = choices.index(current) if current in choices else 0
            setattr(link, row.key, choices[(index + delta) % len(choices)])
        self._clamp_row()

    def _clamp_row(self) -> None:
        self.row = max(0, min(self.row, max(0, len(self._link_rows()) - 1)))

    def _load_row(self) -> None:
        self._clamp_row()
        rows = self._link_rows()
        if not rows:
            self.edit_text = ""
            return
        row = rows[self.row]
        self.edit_text = self._value(row.key)
        self.edit_cursor = len(self.edit_text)

    def _handle_editor(self, key: Key) -> None:
        if self.integrity_editor is not None:
            self.integrity_editor.handle(key)
            if self.integrity_editor.close:
                editor = self.integrity_editor
                self.integrity_editor = None
                if editor.saved and self.selected > 0:
                    self._current_link().integrity = list(editor.rows)
                return
            return
        if self.picker is not None:
            self._handle_picker(key)
            return
        name = key.name
        if self.editing:
            if name == "ENTER":
                rows = self._link_rows()
                self._set_text(rows[self.row].key, self.edit_text)
                self.editing = False
                return
            if name == "ESC":
                self.editing = False
                self._load_row()
                return
            if name == "F2":
                self._open_editor_picker()
                return
            if name == "BACKSPACE":
                if self.edit_cursor:
                    self.edit_text = (self.edit_text[:self.edit_cursor - 1]
                                      + self.edit_text[self.edit_cursor:])
                    self.edit_cursor -= 1
                return
            if name in ("LEFT", "RIGHT"):
                self.edit_cursor = max(0, min(
                    len(self.edit_text), self.edit_cursor
                    + (-1 if name == "LEFT" else 1)))
                return
            text = character(key)
            if text:
                if text.isalpha() and not key.shift:
                    text = text.lower()
                if self.edit_cursor >= len(self.edit_text):
                    self.edit_text += text
                else:
                    self.edit_text = (self.edit_text[:self.edit_cursor] + text
                                      + self.edit_text[self.edit_cursor + 1:])
                self.edit_cursor += len(text)
            return
        if name == "F1":
            return
        if name == "F9":
            self.window = "bottom" if self.window == "top" else "top"
            if self.window == "bottom":
                self.row = 0
                self._load_row()
            return
        if name == "F10":
            self.save()
            return
        if name == "ESC":
            self.close = True
            return
        if self.window == "top":
            if name in ("UP", "DOWN"):
                self.selected = max(0, min(len(self.top_rows()) - 1,
                                           self.selected
                                           + (-1 if name == "UP" else 1)))
                self.row = 0
                self._load_row()
                return
            if name == "F6":
                self._add_link()
                return
            if name == "F5":
                self._detach_link()
                return
            if name == "F7":
                self._open_integrity()
                return
            if name == "ENTER":
                self.window = "bottom"
                self.row = 0
                self._load_row()
                return
            return
        # finestra basso
        if name in ("UP", "DOWN"):
            self._commit_edit()
            self.row = max(0, min(len(self._link_rows()) - 1,
                                  self.row + (-1 if name == "UP" else 1)))
            self._load_row()
            return
        if name == "TAB":
            self._commit_edit()
            self.row = (self.row + (1 if not key.shift else -1)) \
                % max(1, len(self._link_rows()))
            self._load_row()
            return
        if name == "ENTER":
            row = self._link_rows()[self.row]
            if row.kind == "hint":
                if row.key == "integrity":
                    self._open_integrity()
                return
            if row.kind in ("bool", "cycle"):
                self._cycle(row, -1 if key.shift else 1)
                return
            self.edit_text = self._value(row.key)
            self.edit_cursor = len(self.edit_text)
            self.editing = True
            return
        if name in ("LEFT", "RIGHT", "SPACE"):
            row = self._link_rows()[self.row]
            if row.kind in ("bool", "cycle"):
                self._cycle(row, -1 if name == "LEFT" else 1)
            return
        if name == "F6":
            self._add_link()
            return
        if name == "F5":
            self._detach_link()
            return
        if name == "F7":
            self._open_integrity()
            return

    def _commit_edit(self) -> None:
        if self.editing:
            rows = self._link_rows()
            self._set_text(rows[self.row].key, self.edit_text)
            self.editing = False

    def _add_link(self) -> None:
        if self.definition is None:
            return
        rows = self.top_rows()
        parent = self.definition.primary
        if 0 <= self.selected < len(rows) and rows[self.selected][2] is not None:
            parent = rows[self.selected][1]
        self.definition.links.append(Link(parent=parent))
        self.selected = len(self.top_rows()) - 1
        self.window = "bottom"
        self.row = 1  # Linked Database/Set
        self._load_row()

    def _detach_link(self) -> None:
        if self.definition is None or self.selected == 0:
            return
        rows = self.top_rows()
        link = rows[self.selected][2]
        if link is None:
            return
        removed = {link.child}
        changed = True
        while changed:
            changed = False
            for item in list(self.definition.links):
                if item.parent in removed and item.child not in removed:
                    removed.add(item.child)
                    changed = True
        self.definition.links = [item for item in self.definition.links
                                 if item.child not in removed]
        self.selected = min(self.selected, len(self.top_rows()) - 1)
        self.row = 0
        self._load_row()

    def _open_editor_picker(self) -> None:
        row = self._link_rows()[self.row]
        if self.selected == 0:
            if row.key == "primary":
                self.picker = Picker("Databases", self.workspace.names(),
                                     purpose="primary")
                self.picker_kind = "primary"
            return
        link = self._current_link()
        if row.key == "parent":
            self.picker = Picker("Databases", self.definition.database_names(),
                                 purpose="parent")
            self.picker_kind = "parent"
        elif row.key == "child":
            self.picker = Picker("Databases", self.workspace.names(),
                                 purpose="child")
            self.picker_kind = "child"
        elif row.key == "linking_index":
            child = self._current_database(link.child)
            if child is not None:
                self.picker = Picker(
                    "Indexes", [item.name for item in indexing.indexes(child)],
                    purpose="index")
                self.picker_kind = "index"

    def _open_integrity(self) -> None:
        if self.selected == 0 or self.definition is None:
            return
        link = self._current_link()
        parent = self._current_database(link.parent)
        child = self._current_database(link.child)
        if parent is None or child is None:
            self.status = "Choose parent and child database first."
            return
        rows = self.definition.integrity_rows(link)
        self.integrity_editor = IntegrityEditor(
            rows, parent, child, self.theme)

    def save(self) -> bool:
        if self.definition is None:
            return False
        self._commit_edit()
        self.definition.description = self.definition.description.strip()
        self.definition.name = (self.definition.name or self.name_text).upper()
        try:
            self.definition.save()
        except Exception as exc:
            self.status = str(exc)
            return False
        self.saved = True
        self.saved_definition = self.definition
        self.close = True
        self.status = "Set saved."
        return True

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        if self.integrity_editor is not None:
            return self.integrity_editor.view()
        if self.stage in ("name", "description"):
            self._view_prompt(buffer)
        elif self.stage == "primary":
            self._view_primary(buffer)
        else:
            self._view_editor(buffer)
        view = View(buffer, [])
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        return view

    def _view_prompt(self, buffer: CellBuffer) -> None:
        label = "Set name" if self.stage == "name" else "Set description"
        value = self.name_text if self.stage == "name" else self.description_text
        buffer.write(4, 2, label, fg=self.theme.label, bg=self.theme.bg)
        buffer.write(4, 20, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.fill_rect(4, 22, 1, 60, " ", fg=self.theme.selected_fg,
                         bg=self.theme.selected_bg)
        buffer.write(4, 22, clip_text(value, 60), fg=self.theme.selected_fg,
                     bg=self.theme.selected_bg, underline=True)
        draw_status_line(buffer, self.theme,
                         self.status or ("Set name, then ENTER"
                                         if self.stage == "name"
                                         else "Description, then ENTER"))
        draw_help_line(buffer, self.theme, "ENTER accept   ESC cancel")

    def _view_primary(self, buffer: CellBuffer) -> None:
        buffer.write(4, 2, "Primary Database", fg=self.theme.label,
                     bg=self.theme.bg)
        buffer.write(4, 22, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(4, 24, self.primary, fg=self.theme.text, bg=self.theme.bg,
                     bold=True)
        draw_status_line(buffer, self.theme,
                         self.status or "ENTER or F2 choose the primary database")
        draw_help_line(buffer, self.theme, "ENTER databases   ESC back")

    def _view_editor(self, buffer: CellBuffer) -> None:
        buffer.write(1, 2, "Set", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(1, 10, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(1, 12, self.definition.name if self.definition else "",
                     fg=self.theme.text, bg=self.theme.bg, bold=True)
        buffer.write(1, 28, "Description", fg=self.theme.label,
                     bg=self.theme.bg)
        buffer.write(1, 42, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.write(1, 44, clip_text(self.definition.description
                                      if self.definition else "", 60),
                     fg=self.theme.text, bg=self.theme.bg)
        rows = self.top_rows()
        for index, (depth, label, link) in enumerate(rows[:9]):
            screen_row = TOP_TOP + index
            selected = index == self.selected
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(screen_row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            text = "  " * depth + ("-> " if depth else "") + label
            buffer.write(screen_row, 2, clip_text(text, 46), fg=fg, bg=bg,
                         bold=depth == 0)
            if link is not None:
                buffer.write(screen_row, 40, link.link_to, fg=fg, bg=bg)
                buffer.write(screen_row, 50, link.common, fg=fg, bg=bg)
                if link.linking_index:
                    buffer.write(screen_row, 66, clip_text(
                        link.linking_index, 12), fg=fg, bg=bg)
        rows = self._link_rows()
        for index, row in enumerate(rows):
            screen_row = LINK_TOP + index
            if screen_row >= STATUS_ROW - 3:
                break
            selected = index == self.row and self.window == "bottom"
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(screen_row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            buffer.write(screen_row, 2, clip_text(row.label, 32), fg=fg, bg=bg,
                         bold=selected)
            buffer.write(screen_row, 35, ":", fg=fg, bg=bg)
            value = self.edit_text if selected and self.editing \
                else self._value(row.key)
            buffer.write(screen_row, 37, clip_text(value, SCREEN_WIDTH - 39),
                         fg=fg, bg=bg, underline=selected and self.editing,
                         bold=selected and row.kind in ("bool", "cycle"))
        draw_status_line(buffer, self.theme,
                         self.status or "F6 add link   F5 detach   "
                                       "F7 integrity   F10 save")
        draw_help_line(buffer, self.theme,
                       "UP/DOWN select   ENTER edit   F9 switch   "
                       "F10 save   ESC cancel")
        draw_menu_line(buffer, self.theme, SET_KEYS)


# -- integrity rule ---------------------------------------------------------


@dataclass
class IntegrityEditor:
    rows: list[tuple[str, str]] = field(default_factory=list)
    parent: Database | None = None
    child: Database | None = None
    theme: Theme = NEWPORT
    row: int = 0
    col: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    picker: Picker | None = None
    status: str = ""
    close: bool = False
    saved: bool = False

    def __post_init__(self) -> None:
        if not self.rows:
            self.rows = [("", "")]
        self._load_cell()

    def _load_cell(self) -> None:
        self.row = max(0, min(self.row, len(self.rows) - 1))
        self.col = max(0, min(self.col, 1))
        self.edit_text = self.rows[self.row][self.col]
        self.edit_cursor = len(self.edit_text)

    def _commit(self) -> None:
        parent, child = self.rows[self.row]
        if self.col == 0:
            parent = self.edit_text.strip().upper()
        else:
            child = self.edit_text.strip().upper()
        self.rows[self.row] = (parent, child)

    def handle(self, key: Key) -> None:
        self.status = ""
        if self.picker is not None:
            self._handle_picker(key)
            return
        name = key.name
        if name == "F1":
            return
        if name == "F2":
            items = ([field.name for field in self.parent.fields]
                     if self.col == 0 and self.parent is not None
                     else [field.name for field in self.child.fields]
                     if self.child is not None else [])
            self.picker = Picker("Fieldnames", items,
                                 footer="ENTER select   ESC cancel")
            return
        if name == "F5":
            self._commit()
            del self.rows[self.row]
            if not self.rows:
                self.rows = [("", "")]
            self.row = min(self.row, len(self.rows) - 1)
            self._load_cell()
            return
        if name == "F6":
            self._commit()
            self.rows.insert(self.row + 1, ("", ""))
            self.row += 1
            self._load_cell()
            return
        if name == "F10":
            self._commit()
            self.saved = True
            self.close = True
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN"):
            self._commit()
            self.row = max(0, min(len(self.rows) - 1,
                                  self.row + (-1 if name == "UP" else 1)))
            self._load_cell()
            return
        if name == "TAB":
            self._commit()
            self.col = 1 - self.col
            self._load_cell()
            return
        if name in ("LEFT", "RIGHT"):
            self._commit()
            self.col = 0 if name == "LEFT" else 1
            self._load_cell()
            return
        if name == "BACKSPACE":
            if self.edit_cursor:
                self.edit_text = (self.edit_text[:self.edit_cursor - 1]
                                  + self.edit_text[self.edit_cursor:])
                self.edit_cursor -= 1
                self._commit()
            return
        text = character(key)
        if not text:
            return
        if text.isalpha() and not key.shift:
            text = text.lower()
        if self.edit_cursor >= len(self.edit_text):
            self.edit_text += text
        else:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor + 1:])
        self.edit_cursor += len(text)
        self._commit()

    def _handle_picker(self, key: Key) -> None:
        picker = self.picker
        assert picker is not None
        if key.name == "UP":
            picker.move(-1)
        elif key.name == "DOWN":
            picker.move(1)
        elif key.name == "ENTER":
            value = picker.value()
            self.picker = None
            if value:
                self.edit_text = value
                self.edit_cursor = len(value)
                self._commit()
        elif key.name == "ESC":
            self.picker = None

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, "Integrity Rule - Field Mapping", self.theme)
        buffer.write(2, 2, "Parent field", fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        buffer.write(2, 28, "Child field", fg=self.theme.text,
                     bg=self.theme.bg, bold=True)
        for index, (parent, child) in enumerate(self.rows[:visible_rows(3)]):
            screen_row = 3 + index
            selected = index == self.row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(screen_row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            parent_text = self.edit_text if selected and self.col == 0 \
                else parent
            child_text = self.edit_text if selected and self.col == 1 \
                else child
            buffer.write(screen_row, 2, clip_text(parent_text, 24), fg=fg,
                         bg=bg, underline=selected and self.col == 0)
            buffer.write(screen_row, 28, clip_text(child_text, 24), fg=fg,
                         bg=bg, underline=selected and self.col == 1)
        draw_status_line(buffer, self.theme,
                         self.status or "TAB next column   F10 continue")
        draw_help_line(buffer, self.theme,
                       "F2 fields   F5 delete row   F6 insert row   "
                       "F10 continue   ESC cancel")
        view = View(buffer, [])
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        return view


# -- consultazione di un set -------------------------------------------------


MODE_TITLES = {
    "view": "View Set",
    "browse": "Browse Set",
    "change": "Change Set",
    "enter": "Enter Set",
}


@dataclass
class SetSession:
    set_definition: SetDefinition
    mode: str
    theme: Theme = NEWPORT
    index: int = 0
    top: int = 0
    field_index: int = 0
    edit_text: str = ""
    edit_cursor: int = 0
    insert_mode: bool = False
    draft: dict[tuple[str, str], str] = field(default_factory=dict)
    seq: int | None = None
    dirty: bool = False
    focus: str = "form"
    child_link: int = 0
    child_index: int = 0
    zoom: RecordSession | None = None
    zoom_link: Link | None = None
    form: object | None = None
    form_page: int = 0
    status: str = ""
    close: bool = False
    _seqs: list[int] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._reload()
        if self.mode == "enter":
            self._start_new()
        elif self._seqs:
            self._load_record()
        else:
            self.status = "This set has no records."

    @property
    def title(self) -> str:
        return f"{MODE_TITLES.get(self.mode, 'Set')} - {self.set_definition.name}"

    @property
    def primary(self) -> Database:
        return self.set_definition.primary_database

    @property
    def current_seq(self) -> int | None:
        if 0 <= self.index < len(self._seqs):
            return self._seqs[self.index]
        return None

    @property
    def fields(self) -> list[tuple[str, Field, str]]:
        if self.form is None:
            return self.set_definition.flat_fields()
        result: list[tuple[str, Field, str]] = []
        databases = self.set_definition.all_databases()
        by_name = {database.name: database for database in databases}
        for item in self.form.fields:
            if item.kind != "field" or item.database not in by_name:
                continue
            try:
                definition = by_name[item.database].field(item.field)
            except KeyError:
                continue
            label = item.title or (
                definition.name if item.database == self.set_definition.primary
                else f"{item.database}.{definition.name}")
            result.append((item.database, definition, label))
        return result or self.set_definition.flat_fields()

    @property
    def child_links(self) -> list[Link]:
        return [link for link in self.set_definition.children_of(
            self.set_definition.primary) if link.one_to_many]

    @property
    def current_child_link(self) -> Link | None:
        links = self.child_links
        if not links:
            return None
        self.child_link = max(0, min(self.child_link, len(links) - 1))
        return links[self.child_link]

    def child_rows(self) -> list[tuple[int, dict[str, str]]]:
        link = self.current_child_link
        if link is None:
            return []
        return self.set_definition.linked_rows(link, self._parent_values())

    def _reload(self, keep: int | None = None) -> None:
        try:
            self._seqs = self.set_definition.visible_parent_sequences()
        except SetError as exc:
            self.status = str(exc)
            self._seqs = []
        if keep is not None and keep in self._seqs:
            self.index = self._seqs.index(keep)
        self.index = max(0, min(self.index, max(0, len(self._seqs) - 1)))
        self.child_index = 0

    def _parent_values(self) -> dict[str, str]:
        values = {}
        for definition in self.primary.fields:
            values[definition.name] = self.draft.get(
                (self.set_definition.primary, definition.name), "")
        return values

    def _load_record(self) -> None:
        seq = self.current_seq
        if seq is None:
            self.draft = {}
            self.seq = None
            return
        self.seq = seq
        self.draft = self.set_definition.flat_values(
            self.primary.read(seq))
        self.dirty = False
        self._load_field()

    def _start_new(self) -> None:
        self.seq = None
        self.draft = {(database, field.name): ""
                      for database, field, _label
                      in self.set_definition.flat_fields()}
        self.field_index = 0
        self.dirty = False
        self._apply_primary_rules()
        self._load_field()

    def _primary_rules(self) -> dict[str, FieldRule]:
        return self.primary.field_rules()

    def _apply_primary_rules(self) -> None:
        rules = self._primary_rules()
        values = self._parent_values()
        for definition in self.primary.fields:
            rule = rules.get(definition.name)
            if rule is None or rule.value in ("Calculated", "Summary"):
                continue
            if rule.default_mode != "None":
                from ..data.rules import default_value
                value = default_value(rule, self.primary, values)
                if value:
                    self.draft[(self.set_definition.primary,
                                definition.name)] = value
                    values[definition.name] = value
            if rule.increment == "Records":
                from ..data.rules import next_increment
                value = next_increment(rule, self.primary, definition)
                self.draft[(self.set_definition.primary,
                            definition.name)] = value
                values[definition.name] = value
        self._recalculate()

    def _recalculate(self) -> None:
        from ..data.rules import recalculate
        values = self._parent_values()
        recalculate(self._primary_rules(), self.primary, values)
        for name, value in values.items():
            self.draft[(self.set_definition.primary, name)] = value

    def _field_pair(self) -> tuple[str, Field, str] | None:
        fields = self.fields
        if not fields:
            return None
        self.field_index = max(0, min(self.field_index, len(fields) - 1))
        return fields[self.field_index]

    def _link_for_database(self, name: str) -> Link | None:
        return self.set_definition.link_for(name)

    def _field_editable(self, database: str, field: Field) -> bool:
        if database == self.set_definition.primary:
            rule = self._primary_rules().get(field.name)
            return not (rule is not None
                        and rule.value in ("Calculated", "Summary"))
        link = self._link_for_database(database)
        return bool(link is not None and link.edit_child == "Yes")

    def _load_field(self) -> None:
        pair = self._field_pair()
        if pair is None:
            self.edit_text = ""
            return
        database, field, _label = pair
        if self.form is not None:
            for item in self.form.fields:
                if item.kind == "field" and item.database == database \
                        and item.field == field.name:
                    self.form_page = item.page
                    break
        value = self.draft.get((database, field.name), "")
        if database == self.set_definition.primary:
            rule = self._primary_rules().get(field.name)
            if rule is not None and rule.template:
                from ..data.rules import template_display
                self.edit_text = template_display(rule.template, value)
                self.edit_cursor = len(self.edit_text)
                return
        self.edit_text = format_value(field, value)
        self.edit_cursor = len(self.edit_text)

    def _commit_field(self) -> bool:
        if self.mode not in ("enter", "change"):
            return True
        pair = self._field_pair()
        if pair is None:
            return True
        database, field, _label = pair
        if not self._field_editable(database, field):
            return True
        try:
            value = parse_value(field, self.edit_text)
        except FieldError as exc:
            self.status = str(exc)
            return False
        if database == self.set_definition.primary:
            rule = self._primary_rules().get(field.name)
            if rule is not None and rule.case != "None":
                from ..data.rules import apply_case
                value = apply_case(value, rule.case)
        previous = self.draft.get((database, field.name), "")
        self.draft[(database, field.name)] = value
        if previous != value:
            self.dirty = True
        self.edit_text = format_value(field, value)
        self.edit_cursor = min(self.edit_cursor, len(self.edit_text))
        if database == self.set_definition.primary:
            self._recalculate()
        return True

    def _move_field(self, delta: int, *, wrap: bool = False) -> None:
        if not self._commit_field():
            return
        count = len(self.fields)
        if not count:
            return
        target = self.field_index
        for _step in range(count):
            target = target + delta
            if wrap:
                target %= count
            elif target < 0 or target >= count:
                return
            database, field, _label = self.fields[target]
            if self._field_editable(database, field):
                break
        else:
            return
        if target != self.field_index:
            self.field_index = target
            self._load_field()

    def _typed(self, key: Key) -> None:
        if self.mode not in ("enter", "change"):
            return
        pair = self._field_pair()
        if pair is None:
            return
        database, field, _label = pair
        if not self._field_editable(database, field) or field.is_memo:
            return
        text = _typed_char(key)
        if not text:
            return
        if self.insert_mode:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor:])
        else:
            self.edit_text = (self.edit_text[:self.edit_cursor] + text
                              + self.edit_text[self.edit_cursor + 1:])
        self.edit_cursor += len(text)
        self.dirty = True

    # -- salvataggio -----------------------------------------------------
    def _save(self) -> bool:
        if self.mode not in ("enter", "change"):
            return True
        if not self._commit_field():
            return False
        parent_values = {definition.name: self.draft.get(
            (self.set_definition.primary, definition.name), "")
            for definition in self.primary.fields}
        if not any(value.strip() for value in parent_values.values()):
            self.status = "Enter at least one value before saving."
            return False
        from ..data.rules import lookup_validation_error, missing_required, validation_error
        rules = self._primary_rules()
        for definition in self.primary.fields:
            rule = rules.get(definition.name)
            if rule is None:
                continue
            if missing_required(rule, self.primary, parent_values):
                self.status = f"{definition.name} is required."
                return False
            error = validation_error(rule, self.primary, parent_values)
            if error:
                self.status = f"{definition.name}: {error}"
                return False
            error = lookup_validation_error(rule, self.primary,
                                            parent_values)
            if error and not rule.lookup_allow_exceptions:
                self.status = f"{definition.name}: {error}"
                return False
        old_values = (self.primary.read(self.seq)
                      if self.seq is not None else {})
        try:
            if self.seq is None:
                self.seq = self.primary.append(parent_values)
            else:
                self.set_definition.update_parent(self.seq, parent_values)
        except Exception as exc:
            self.status = str(exc)
            return False
        # Aggiorna o crea i figli uno-a-uno modificabili.
        for link in self.set_definition.children_of(
                self.set_definition.primary):
            if link.one_to_many:
                continue
            child = self.set_definition.database(link.child)
            rows = self.set_definition.linked_rows(
                link, old_values if old_values else parent_values,
                include_deleted=True)
            child_values = {field.name: self.draft.get(
                (link.child, field.name), "")
                for field in child.fields}
            if rows:
                seq = rows[0][0]
                if link.edit_child == "Yes":
                    child_values[link.common.strip().upper()] = (
                        parent_values.get(link.common.strip().upper(), ""))
                    try:
                        child.update(seq, child_values)
                    except Exception as exc:
                        self.status = str(exc)
                        return False
            elif link.add_child != "No":
                seq = self.set_definition.add_child(link, parent_values)
                if link.edit_child == "Yes":
                    child.update(seq, child_values)
        self.primary.workspace.save_database(self.primary)
        self.status = "Set record saved."
        self.dirty = False
        self._reload(keep=self.seq)
        return True

    def _delete_parent(self) -> None:
        seq = self.current_seq
        if seq is None:
            return
        self.set_definition.delete_parent(seq)
        self._reload()
        self.status = "Record marked for deletion; children cascaded."

    def _undelete_parent(self) -> None:
        seq = self.current_seq
        if seq is None:
            return
        self.set_definition.undelete_parent(seq)
        self._reload(keep=seq)
        self.status = "Record recalled; children recalled."

    def _open_zoom(self) -> None:
        link = self.current_child_link
        rows = self.child_rows()
        if link is None or not rows:
            self.status = "No child record to zoom."
            return
        self.child_index = max(0, min(self.child_index, len(rows) - 1))
        child = self.set_definition.database(link.child)
        session = RecordSession(child, "browse")
        target = rows[self.child_index][0]
        if target in session._seqs:
            session.index = session._seqs.index(target)
        self.zoom = session
        self.zoom_link = link
        self.status = ""

    def handle(self, key: Key) -> None:
        self.status = ""
        if self.form is not None and key.ctrl \
                and key.name in ("PGUP", "PGDN"):
            self.form_page = max(0, min(self.form.pages - 1,
                                        self.form_page
                                        + (-1 if key.name == "PGUP" else 1)))
            return
        if self.zoom is not None:
            self.zoom.handle(key)
            if self.zoom.close:
                self.zoom = None
                self._reload(keep=self.current_seq)
            return
        name = key.name
        if name == "F1":
            return
        if name == "F10":
            if self.mode in ("view", "browse"):
                self.close = True
            elif self._save():
                self.close = True
            return
        if name == "ESC":
            self.close = True
            return
        if name == "F6":
            if not self.child_links:
                self.status = "This set has no one-to-many link."
                return
            self.focus = "child" if self.focus == "form" else "form"
            return
        if key.alt and name == "Z":
            self._open_zoom()
            return
        if key.alt:
            if name == "D" and self.mode in ("view", "browse"):
                self._delete_parent()
            elif name == "U" and self.mode in ("view", "browse"):
                self._undelete_parent()
            return
        if self.mode == "browse":
            if name == "UP":
                self._move_record(-1)
            elif name == "DOWN":
                self._move_record(1)
            elif name == "PGUP":
                self._move_record(-self.page_rows)
            elif name == "PGDN":
                self._move_record(self.page_rows)
            elif name == "HOME":
                self.index = 0
            elif name == "END":
                self.index = max(0, len(self._seqs) - 1)
            return
        if self.focus == "child":
            if name == "UP":
                self.child_index = max(0, self.child_index - 1)
            elif name == "DOWN":
                rows = self.child_rows()
                self.child_index = min(max(0, len(rows) - 1),
                                       self.child_index + 1)
            elif name == "PGUP":
                self.child_index = max(0, self.child_index - 8)
            elif name == "PGDN":
                self.child_index = max(0, self.child_index + 8)
            return
        if self.mode in ("view", "browse"):
            if name == "UP":
                self._move_record(-1)
            elif name == "DOWN":
                self._move_record(1)
            elif name == "PGUP":
                self._move_record(-self.page_rows)
            elif name == "PGDN":
                self._move_record(self.page_rows)
            elif name == "HOME":
                self.index = 0
            elif name == "END":
                self.index = max(0, len(self._seqs) - 1)
            return
        # enter/change
        if name in ("TAB", "DOWN"):
            self._move_field(1, wrap=True)
        elif name == "UP":
            self._move_field(-1)
        elif name == "LEFT":
            self.edit_cursor = max(0, self.edit_cursor - 1)
        elif name == "RIGHT":
            self.edit_cursor = min(len(self.edit_text), self.edit_cursor + 1)
        elif name == "HOME":
            self.edit_cursor = 0
        elif name == "END":
            self.edit_cursor = len(self.edit_text)
        elif name == "BACKSPACE":
            if self.edit_cursor:
                self.edit_text = (self.edit_text[:self.edit_cursor - 1]
                                  + self.edit_text[self.edit_cursor:])
                self.edit_cursor -= 1
                self.dirty = True
        elif name == "DELETE":
            self.edit_text = (self.edit_text[:self.edit_cursor]
                              + self.edit_text[self.edit_cursor + 1:])
            self.dirty = True
        elif name == "INSERT":
            self.insert_mode = not self.insert_mode
        elif name == "ENTER":
            self._move_field(1, wrap=True)
        elif name == "SPACE" or character(key):
            self._typed(key)

    def _move_record(self, delta: int) -> None:
        if self.mode == "change" and self.dirty:
            self.status = "Save the record with F10 or cancel with ESC first."
            return
        self.index = max(0, min(len(self._seqs) - 1, self.index + delta))
        self._load_record()

    @property
    def page_rows(self) -> int:
        return max(1, STATUS_ROW - 15)

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        if self.zoom is not None:
            return self.zoom.view()
        if self.mode == "browse":
            return self._browse_view()
        return self._form_view()

    def _status_line(self) -> str:
        if self.mode == "enter" and self.seq is None:
            return "New record"
        if not self._seqs:
            return "No records"
        return f"Record {self.index + 1} of {len(self._seqs)}"

    def _form_view(self) -> View:
        if self.form is not None:
            return self._custom_set_form()
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        draw_status_line(buffer, self.theme,
                         self.status or self._status_line())
        fields = self.fields
        rows = 10
        columns = max(1, (len(fields) + rows - 1) // rows)
        per_column = max(1, (len(fields) + columns - 1) // columns)
        width = SCREEN_WIDTH // max(1, columns)
        for index, (database, definition, label) in enumerate(fields):
            group = index // per_column
            row = 3 + index % per_column
            col = 1 + group * width
            active = index == self.field_index and self.focus == "form"
            label_fg = self.theme.accent if active else self.theme.label
            buffer.write(row, col, clip_text(label, 16), fg=label_fg,
                         bg=self.theme.bg, bold=active)
            buffer.write(row, col + 16, ":", fg=self.theme.label,
                         bg=self.theme.bg)
            value = self.draft.get((database, definition.name), "")
            text = format_value(definition, value)
            value_col = col + 18
            value_width = max(4, width - 20)
            if active and self.mode in ("enter", "change"):
                buffer.fill_rect(row, value_col, 1, value_width, " ",
                                 fg=self.theme.selected_fg,
                                 bg=self.theme.selected_bg)
                buffer.write(row, value_col, clip_text(self.edit_text,
                                                       value_width),
                             fg=self.theme.selected_fg,
                             bg=self.theme.selected_bg, underline=True)
            else:
                buffer.write(row, value_col, clip_text(text, value_width),
                             fg=self.theme.text, bg=self.theme.bg,
                             bold=active)
        child_row = 14
        links = self.child_links
        if links:
            link = self.current_child_link
            assert link is not None
            buffer.write(child_row, 2,
                         clip_text(f"{link.child} (one-to-many)", 30),
                         fg=self.theme.accent, bg=self.theme.bg, bold=True)
            child = self.set_definition.database(link.child)
            headers = [field.name for field in child.fields]
            for column, header in enumerate(headers):
                buffer.write(child_row + 1, 2 + column * 18,
                             clip_text(header, 16), fg=self.theme.label,
                             bg=self.theme.bg, bold=True)
            rows = self.child_rows()
            self.child_index = max(0, min(self.child_index,
                                          max(0, len(rows) - 1)))
            for offset, (seq, values) in enumerate(rows[:visible_rows(child_row + 2)]):
                screen_row = child_row + 2 + offset
                selected = (offset == self.child_index
                            and self.focus == "child")
                fg = self.theme.selected_fg if selected else self.theme.text
                bg = self.theme.selected_bg if selected else self.theme.bg
                if selected:
                    buffer.fill_rect(screen_row, 1, 1, SCREEN_WIDTH - 2, " ",
                                     fg=fg, bg=bg)
                for column, field in enumerate(child.fields):
                    buffer.write(screen_row, 2 + column * 18,
                                 clip_text(values.get(field.name, ""), 16),
                                 fg=fg, bg=bg)
        draw_help_line(buffer, self.theme,
                       self.status or ("F6 child region   Alt-Z zoom   "
                                       "F10 save" if self.mode in
                                       ("enter", "change") else
                                       "F6 child region   Alt-Z zoom   "
                                       "F10 continue"))
        draw_menu_line(buffer, self.theme, SET_SESSION_KEYS)
        return View(buffer, [])

    @clipping_allowed
    def _custom_set_form(self) -> View:
        form = self.form
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        draw_status_line(buffer, self.theme,
                         self.status or self._status_line())
        page = max(0, min(self.form_page, form.pages - 1))
        for box in form.page_boxes(page):
            buffer.box(box.row, box.col, box.height, box.width,
                       fg=self.theme.border, bg=self.theme.bg,
                       double=box.double)
        for label in form.page_labels(page):
            buffer.write(label.row, label.col, clip_text(
                label.text, max(0, SCREEN_WIDTH - label.col)),
                fg=self.theme.text, bg=self.theme.bg)
        pairs = self.fields
        active_pair = pairs[self.field_index] if pairs else None
        for item in form.page_fields(page):
            if item.kind == "summary":
                link = None
                for candidate in self.child_links:
                    if candidate.child == (item.summary_database
                                           or item.database):
                        link = candidate
                        break
                rows = (self.set_definition.linked_rows(link,
                                                        self._parent_values())
                        if link is not None else [])
                text = form.summary_value(item, [values for _seq, values in rows])
            elif item.kind == "calculated":
                database = self.set_definition.database(item.database)
                text = form.value_for(item, self._parent_values(), database)
            else:
                text = self.draft.get((item.database, item.field), "")
            width = max(1, item.window or item.length or 1)
            if item.show_title and item.title:
                buffer.write(item.row - 1, item.col,
                             clip_text(item.title, max(20, width)),
                             fg=self.theme.label, bg=self.theme.bg)
            active = (active_pair is not None
                      and item.kind == "field"
                      and item.database == active_pair[0]
                      and item.field == active_pair[1].name
                      and self.focus == "form")
            if active and self.mode in ("enter", "change"):
                buffer.fill_rect(item.row, item.col, 1, width, " ",
                                 fg=self.theme.selected_fg,
                                 bg=self.theme.selected_bg)
                buffer.write(item.row, item.col,
                             clip_text(self.edit_text, width),
                             fg=self.theme.selected_fg,
                             bg=self.theme.selected_bg, underline=True)
            else:
                if item.justification == "R":
                    text = text.rjust(width)
                elif item.justification == "C":
                    text = text.center(width)
                buffer.write(item.row, item.col, clip_text(text, width),
                             fg=self.theme.text, bg=self.theme.bg,
                             bold=item.kind in ("calculated", "summary"))
        # regioni
        for region in form.page_regions(page):
            link = next((candidate for candidate in self.child_links
                         if candidate.child == region.database), None)
            if link is None:
                continue
            rows = self.set_definition.linked_rows(link,
                                                   self._parent_values())
            buffer.box(region.row, region.col, region.height, region.width,
                       fg=self.theme.accent, bg=self.theme.bg)
            buffer.write(region.row, region.col + 2,
                         clip_text(f" {region.title or region.database} ",
                                   region.width - 4),
                         fg=self.theme.accent, bg=self.theme.bg, bold=True)
            child = self.set_definition.database(region.database)
            fields = child.fields
            if self.focus == "child" and link is self.current_child_link:
                selected = self.child_index
            else:
                selected = -1
            visible = region.height - 2
            top = max(0, min(selected - visible + 1,
                             max(0, len(rows) - visible)))
            for offset, (seq, child_values) in enumerate(rows[top:top + visible]):
                screen_row = region.row + 1 + offset
                if screen_row >= region.row + region.height - 1:
                    break
                current = top + offset == selected
                fg = self.theme.selected_fg if current else self.theme.text
                bg = self.theme.selected_bg if current else self.theme.bg
                if current:
                    buffer.fill_rect(screen_row, region.col + 1, 1,
                                     region.width - 2, " ", fg=fg, bg=bg)
                col = region.col + 1
                for definition in fields:
                    text = child_values.get(definition.name, "")
                    buffer.write(screen_row, col,
                                 clip_text(text, max(1, definition.length)),
                                 fg=fg, bg=bg)
                    col += max(1, definition.length) + 1
                    if col >= region.col + region.width - 1:
                        break
        draw_help_line(buffer, self.theme,
                       self.status or ("F6 child region   Alt-Z zoom   "
                                       "F10 save" if self.mode in
                                       ("enter", "change") else
                                       "F6 child region   Alt-Z zoom   "
                                       "F10 continue"))
        draw_menu_line(buffer, self.theme, SET_SESSION_KEYS)
        return View(buffer, [])

    def _browse_view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        title_bar(buffer, self.title, self.theme)
        draw_status_line(buffer, self.theme,
                         self.status or self._status_line())
        fields = self.fields
        widths = [max(10, min(22, len(label) + 2)) for _d, _f, label in fields]
        col = 2
        for (database, definition, label), width in zip(fields, widths):
            buffer.write(2, col, clip_text(label, width - 1),
                         fg=self.theme.text, bg=self.theme.bg, bold=True)
            col += width
        visible = STATUS_ROW - 6
        top = max(0, min(self.index - visible + 1,
                         max(0, len(self._seqs) - visible)))
        for offset in range(visible):
            position = top + offset
            if position >= len(self._seqs):
                break
            seq = self._seqs[position]
            values = self.set_definition.flat_values(self.primary.read(seq))
            selected = position == self.index
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            row = 3 + offset
            if selected:
                buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            col = 2
            for (database, definition, _label), width in zip(fields, widths):
                text = values.get((database, definition.name), "")
                buffer.write(row, col, clip_text(text, width - 1), fg=fg,
                             bg=bg)
                col += width
        draw_help_line(buffer, self.theme,
                       self.status or "UP/DOWN record   F10 continue")
        draw_menu_line(buffer, self.theme, SET_SESSION_KEYS)
        return View(buffer, [])


def _typed_char(key: Key) -> str:
    text = character(key)
    if not text:
        return ""
    if len(text) == 1 and text.isalpha():
        return text if key.shift else text.lower()
    return text


__all__ = ["IntegrityEditor", "SetDesigner", "SetSession"]
