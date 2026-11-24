"""Form designer: layout a celle per database e set (O6).

La schermata è una griglia di caratteri: il cursore sceglie la posizione,
F2 inserisce un campo, F8 un riquadro, F6 una regione uno-a-molti, F9 le
opzioni di formattazione, F7 i parametri del form. Il form salvato diventa
subito attivo e viene usato da View/Enter/Change.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..cell.buffer import (
    Cell,
    CellBuffer,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    STATUS_ROW,
    clipping_allowed,
)
from ..data.forms import (
    FORM_LETTERS,
    SUMMARY_TYPES,
    FormBox,
    FormDefinition,
    FormError,
    FormField,
    FormLabel,
    FormRegion,
)
from ..data.sets import SetDefinition
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

# Limiti della pagina di design nella griglia legacy 80x25.
MAX_ROW = STATUS_ROW - 2   # righe 0..20, la 21 resta libera sotto il cursore
MAX_COL = SCREEN_WIDTH - 2

# Compatte per stare in 80 colonne: F6/PgUp restano nella help line.
FORM_KEYS = [("F1", "Help"), ("F2", "Fields"), ("F4", "Calc"),
             ("F5", "Del"), ("F7", "Params"), ("F8", "Box"),
             ("F9", "Fmt"), ("F10", "Save")]
LAYOUT_TOP = 3


@dataclass
class FormDesigner:
    workspace: Workspace
    database: Database | None = None
    owner: str = ""
    form: FormDefinition | None = None
    theme: Theme = NEWPORT
    stage: str = "letter"
    letter_text: str = ""
    description_text: str = ""
    edit_existing: bool = False
    page: int = 0
    row: int = 1
    col: int = 1
    param_row: int = 0
    format_row: int = 0
    format_col: int = 1
    edit_text: str = ""
    edit_cursor: int = 0
    editing: bool = False
    picker: Picker | None = None
    picker_kind: str = ""
    summary_database: str = ""
    summary_type: str = ""
    status: str = ""
    close: bool = False
    saved: bool = False
    saved_form: FormDefinition | None = None
    help_topic: str = "forms"

    def __post_init__(self) -> None:
        if not self.owner:
            self.owner = (self.database.name if self.database is not None
                          else "")

    # -- owner -----------------------------------------------------------
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
    def set_definition(self) -> SetDefinition | None:
        return self.workspace.get_set(self.owner)

    @property
    def title(self) -> str:
        if self.stage == "letter":
            return "Create/Edit a Form"
        if self.form is None:
            return "Form Designer"
        return f"Form Layout - {self.form.letter} - {self.owner}"

    # -- handle ----------------------------------------------------------
    def handle(self, key: Key) -> None:
        self.status = ""
        if self.picker is not None:
            self._handle_picker(key)
            return
        if self.stage == "letter":
            self._handle_letter(key)
        elif self.stage == "description":
            self._handle_description(key)
        elif self.stage == "parameters":
            self._handle_parameters(key)
        elif self.stage == "formatting":
            self._handle_formatting(key)
        elif self.stage == "calc":
            self._handle_calculated(key)
        else:
            self._handle_layout(key)

    def _handle_letter(self, key: Key) -> None:
        if key.name == "ENTER":
            letter = self.letter_text.strip().upper()[:1] or "A"
            if letter not in FORM_LETTERS:
                self.status = "Choose a form id A-Z."
                return
            existing = self.workspace.get_form(self.owner, letter)
            if existing is not None:
                self.form = existing
                self.edit_existing = True
                self.stage = "layout"
                self.description_text = existing.description
                self.page = 0
                self.status = "Editing an existing form."
            else:
                self.form = FormDefinition(self.workspace, self.owner, letter)
                self.stage = "description"
                self.edit_cursor = 0
            return
        if key.name == "ESC":
            self.close = True
            return
        text = character(key)
        if text and text.isalpha():
            self.letter_text = text.upper()

    def _handle_description(self, key: Key) -> None:
        if key.name == "ENTER":
            self.form.description = self.description_text.strip()
            self.stage = "parameters"
            self.param_row = 0
            return
        if key.name == "ESC":
            self.close = True
            return
        if key.name == "BACKSPACE":
            self.description_text = self.description_text[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self.description_text += text

    # -- parameters ------------------------------------------------------
    def _parameter_rows(self) -> list[tuple[str, str, str]]:
        form = self.form
        assert form is not None
        return [
            ("description", "Description", form.description),
            ("menu", "Custom menu bar", form.custom_menu),
            ("restrict", "Restrict access", form.restrict),
            ("printable", "Printable", "Yes" if form.printable else "No"),
            ("print_width", "Print width", str(form.print_width)),
            ("margins", "Margins", form.margins),
        ]

    def _handle_parameters(self, key: Key) -> None:
        rows = self._parameter_rows()
        name = key.name
        if self.editing:
            if name == "ENTER":
                self._commit_parameter()
                self.editing = False
                return
            if name == "ESC":
                self.editing = False
                self.edit_text = ""
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
                self.edit_text += text
                self.edit_cursor += len(text)
            return
        if name == "F1":
            return
        if name == "F10":
            self._commit_parameter()
            self.stage = "layout"
            self.page = 0
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN"):
            self._commit_parameter()
            self.param_row = max(0, min(len(rows) - 1,
                                        self.param_row
                                        + (-1 if name == "UP" else 1)))
            return
        if name == "ENTER":
            key_name = rows[self.param_row][0]
            if key_name == "printable":
                self.form.printable = not self.form.printable
                return
            self.edit_text = rows[self.param_row][2]
            self.edit_cursor = len(self.edit_text)
            self.editing = True

    def _commit_parameter(self) -> None:
        if self.form is None:
            return
        rows = self._parameter_rows()
        name = rows[self.param_row][0]
        if name == "description":
            self.form.description = self.edit_text
        elif name == "menu":
            self.form.custom_menu = self.edit_text
        elif name == "restrict":
            self.form.restrict = self.edit_text
        elif name == "print_width":
            try:
                self.form.print_width = max(40, min(240, int(self.edit_text)))
            except ValueError:
                self.form.print_width = 80
        elif name == "margins":
            self.form.margins = self.edit_text

    # -- layout ----------------------------------------------------------
    def _handle_layout(self, key: Key) -> None:
        assert self.form is not None
        name = key.name
        if name == "F1":
            return
        if name == "F2":
            self._open_field_picker()
            return
        if name == "F4":
            self.picker = Picker(
                "Form field", ["Calculated field", "Summary field"],
                values=["calculated", "summary"],
                footer="ENTER select   ESC cancel")
            self.picker_kind = "synthetic"
            return
        if name == "F5":
            self._delete_at_cursor()
            return
        if name == "F6":
            self._add_region()
            return
        if name == "F7":
            self.stage = "parameters"
            self.param_row = 0
            return
        if name == "F8":
            self._add_box()
            return
        if name == "F9":
            self.stage = "formatting"
            self.format_row = 0
            self.format_col = 1
            return
        if name == "F10":
            self.save()
            return
        if name == "ESC":
            self.close = True
            return
        if name == "PGUP":
            self._commit_layout()
            self.page = max(0, self.page - 1)
            return
        if name == "PGDN":
            self._commit_layout()
            self.page = min(9, self.page + 1)
            self.form.pages = max(self.form.pages, self.page + 1)
            return
        if name == "UP":
            self._commit_layout()
            self.row = max(1, self.row - 1)
            return
        if name == "DOWN":
            self._commit_layout()
            self.row = min(MAX_ROW, self.row + 1)
            return
        if name == "LEFT":
            self._commit_layout()
            self.col = max(1, self.col - 1)
            return
        if name == "RIGHT":
            self._commit_layout()
            self.col = min(MAX_COL, self.col + 1)
            return
        if name == "HOME":
            self._commit_layout()
            self.col = 1
            return
        if name == "END":
            self._commit_layout()
            self.col = MAX_COL
            return
        if name == "BACKSPACE":
            self._backspace_label()
            return
        if name == "DELETE":
            self._delete_label_char()
            return
        if name == "SPACE":
            self._type_label(" ")
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self._type_label(text)

    def _commit_layout(self) -> None:
        self.editing = False

    def _type_label(self, text: str) -> None:
        if self.form is None:
            return
        label = self._label_at(self.row, self.col)
        if label is None:
            before = next((item for item in self.form.labels
                           if item.page == self.page and item.row == self.row
                           and item.col + len(item.text) == self.col), None)
            if before is not None:
                before.text += text
                self.col = min(MAX_COL, self.col + 1)
                return
            label = FormLabel(self.page, self.row, self.col, text)
            self.form.labels.append(label)
        else:
            offset = self.col - label.col
            label.text = label.text[:offset] + text + label.text[offset + 1:]
        self.col = min(MAX_COL, self.col + 1)

    def _label_at(self, row: int, col: int) -> FormLabel | None:
        if self.form is None:
            return None
        for label in self.form.labels:
            if label.page == self.page and label.row == row \
                    and label.col <= col < label.col + len(label.text):
                return label
        return None

    def _backspace_label(self) -> None:
        if self.form is None:
            return
        label = self._label_at(self.row, self.col - 1)
        if label is None:
            self.col = max(1, self.col - 1)
            return
        offset = self.col - 1 - label.col
        if 0 <= offset < len(label.text):
            label.text = label.text[:offset] + label.text[offset + 1:]
        if not label.text:
            self.form.labels.remove(label)
        self.col = max(1, self.col - 1)

    def _delete_label_char(self) -> None:
        if self.form is None:
            return
        label = self._label_at(self.row, self.col)
        if label is None:
            return
        offset = self.col - label.col
        label.text = label.text[:offset] + label.text[offset + 1:]
        if not label.text:
            self.form.labels.remove(label)

    def _delete_at_cursor(self) -> None:
        if self.form is None:
            return
        for item in list(self.form.fields):
            if item.page == self.page and item.row == self.row \
                    and item.col <= self.col < item.col + max(1, item.length):
                self.form.fields.remove(item)
                return
        for region in list(self.form.regions):
            if region.page == self.page and region.row <= self.row < \
                    region.row + region.height and region.col <= self.col < \
                    region.col + region.width:
                self.form.regions.remove(region)
                return
        for box in list(self.form.boxes):
            if box.page == self.page and box.row <= self.row < \
                    box.row + box.height and box.col <= self.col < \
                    box.col + box.width:
                self.form.boxes.remove(box)
                return
        self._delete_label_char()

    def _add_box(self) -> None:
        self.form.boxes.append(FormBox(self.page, self.row, self.col,
                                       4, 30))
        self.status = "Box drawn; F5 deletes it."

    def _add_region(self) -> None:
        definition = self.set_definition
        if definition is None:
            self.status = "Regions are available only on sets."
            return
        links = [link for link in definition.children_of(definition.primary)
                 if link.one_to_many]
        if not links:
            self.status = "This set has no one-to-many link."
            return
        self.picker = Picker("Region database",
                             [link.child for link in links],
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "region"
        self.picker.selected = 0

    def _open_field_picker(self) -> None:
        items: list[str] = []
        values: list[str] = []
        self.picker_kind = "field"
        for name, database in self.owner_databases.items():
            prefix = f"{name}." if len(self.owner_databases) > 1 else ""
            for definition in database.fields:
                items.append(prefix + definition.name)
                values.append(f"{name}:{definition.name}")
        self.picker = Picker("Fieldnames", items, values,
                             footer="ENTER place field   ESC cancel")

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
            kind = self.picker_kind
            self.picker = None
            if not value:
                return
            if kind == "field":
                database_name, field_name = value.split(":", 1)
                database = self.owner_databases.get(database_name)
                if database is None:
                    return
                definition = database.field(field_name)
                length = definition.length
                window = definition.length
                fmt = ""
                if definition.is_memo:
                    length, window, fmt = 300, 50, "!X"
                self.form.fields.append(FormField(
                    database_name, field_name, self.page, self.row, self.col,
                    length, window, field_name, False, "L", "", fmt))
                self.col = min(MAX_COL, self.col + max(1, length) + 1)
            elif kind == "region":
                region = FormRegion(value, self.page, self.row, self.col,
                                    10, 70, f"{value} items")
                self.form.regions.append(region)
                self.status = "Region added; F5 deletes it."
            elif kind == "synthetic":
                if value == "calculated":
                    self.stage = "calc"
                    self.edit_text = ""
                    self.edit_cursor = 0
                else:
                    definition = self.set_definition
                    links = ([link for link in definition.children_of(
                        definition.primary) if link.one_to_many]
                        if definition is not None else [])
                    if not links:
                        self.status = "Summary fields need a one-to-many child."
                        return
                    self.summary_database = links[0].child
                    self.picker = Picker(
                        "Summary type",
                        [item for item in SUMMARY_TYPES if item],
                        footer="ENTER select   ESC cancel")
                    self.picker_kind = "summary_type"
            elif kind == "summary_type":
                self.summary_type = value
                child = self.workspace.get(self.summary_database)
                if child is None:
                    return
                self.picker = Picker(
                    "Summary field", [item.name for item in child.fields],
                    footer="ENTER select   ESC cancel")
                self.picker_kind = "summary_field"
            elif kind == "summary_field":
                child = self.workspace.get(self.summary_database)
                if child is None:
                    return
                field = child.field(value)
                self.form.fields.append(FormField(
                    "CALC", f"SUM{len(self.form.fields) + 1}", self.page,
                    self.row, self.col, 12, 12, f"{self.summary_type} {value}",
                    True, "R", "", "", "summary", summary=self.summary_type,
                    summary_database=self.summary_database,
                    summary_field=field.name))
                self.status = "Summary field added."
        elif key.name == "ESC":
            self.picker = None

    def _handle_calculated(self, key: Key) -> None:
        if key.name == "ENTER":
            expression = self.edit_text.strip()
            if not expression:
                self.status = "Enter an expression."
                return
            name = f"CALC{len(self.form.fields) + 1}"
            self.form.fields.append(FormField(
                "CALC", name, self.page, self.row, self.col, 12, 12,
                "Calculated", True, "R", "", "", "calculated",
                expression=expression))
            self.stage = "layout"
            self.status = "Calculated field added."
            return
        if key.name == "ESC":
            self.stage = "layout"
            return
        if key.name == "BACKSPACE":
            self.edit_text = self.edit_text[:-1]
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self.edit_text += text

    # -- formatting ------------------------------------------------------
    def _formatting_rows(self) -> list[FormField]:
        assert self.form is not None
        return list(self.form.fields)

    def _handle_formatting(self, key: Key) -> None:
        rows = self._formatting_rows()
        name = key.name
        if name == "F1":
            return
        if name == "F10":
            self.stage = "layout"
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN"):
            self.format_row = max(0, min(len(rows) - 1,
                                         self.format_row
                                         + (-1 if name == "UP" else 1)))
            return
        if name == "TAB":
            self.format_col = self.format_col % 7 + 1
            return
        if name in ("LEFT", "RIGHT"):
            self.format_col = max(1, min(7, self.format_col
                                         + (-1 if name == "LEFT" else 1)))
            return
        if not rows:
            return
        item = rows[self.format_row]
        if self.editing:
            if name == "ENTER":
                self._set_format_value(item, self.format_col, self.edit_text)
                self.editing = False
                return
            if name == "ESC":
                self.editing = False
                return
            if name == "BACKSPACE":
                self.edit_text = self.edit_text[:-1]
                return
            text = character(key)
            if text:
                self.edit_text += text
            return
        if name == "ENTER":
            self.edit_text = self._format_value(item, self.format_col)
            self.editing = True
            return
        if name in ("LEFT", "RIGHT", "SPACE"):
            current = self._format_value(item, self.format_col)
            if self.format_col == 5:
                modes = ["L", "R", "C"]
                index = modes.index(current) if current in modes else 0
                self._set_format_value(item, 5, modes[(index + 1) % 3])
            elif self.format_col == 6 and name in ("SPACE", "RIGHT"):
                self._set_format_value(item, 6,
                                       "!X" if not current else "")

    def _format_value(self, item: FormField, column: int) -> str:
        return {1: item.field, 2: str(item.length), 3: str(item.window),
                4: str(item.page + 1), 5: item.justification, 6: item.format,
                7: item.title}.get(column, "")

    def _set_format_value(self, item: FormField, column: int,
                          value: str) -> None:
        if column == 2:
            try:
                item.length = max(0, int(value))
            except ValueError:
                pass
        elif column == 3:
            try:
                item.window = max(0, int(value))
            except ValueError:
                pass
        elif column == 5:
            item.justification = value.upper()[:1] if value else "L"
        elif column == 6:
            item.format = value
        elif column == 7:
            item.title = value
            item.show_title = bool(value)

    # -- save ------------------------------------------------------------
    def save(self) -> bool:
        self._commit_parameter()
        if self.form is None:
            return False
        self.form.description = self.form.description or self.description_text
        try:
            self.form.save()
        except FormError as exc:
            self.status = str(exc)
            return False
        self.saved = True
        self.saved_form = self.form
        self.close = True
        self.status = f"Form {self.form.letter} saved."
        return True

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        if self.stage == "letter":
            title_bar(buffer, "Create/Edit a Form", self.theme)
            buffer.write(4, 2, "Form id (A-Z)", fg=self.theme.label,
                         bg=self.theme.bg)
            buffer.write(4, 20, ":", fg=self.theme.label, bg=self.theme.bg)
            buffer.fill_rect(4, 22, 1, 4, " ", fg=self.theme.selected_fg,
                             bg=self.theme.selected_bg)
            buffer.write(4, 22, self.letter_text or "_", fg=self.theme.selected_fg,
                         bg=self.theme.selected_bg, underline=True)
            draw_status_line(buffer, self.theme,
                             self.status or "Type a form id and press ENTER")
            draw_help_line(buffer, self.theme, "ENTER accept   ESC cancel")
        elif self.stage == "description":
            title_bar(buffer, "Form Description", self.theme)
            buffer.write(4, 2, "Description", fg=self.theme.label,
                         bg=self.theme.bg)
            buffer.write(4, 20, ":", fg=self.theme.label, bg=self.theme.bg)
            buffer.fill_rect(4, 22, 1, 60, " ", fg=self.theme.selected_fg,
                             bg=self.theme.selected_bg)
            buffer.write(4, 22, clip_text(self.description_text, 60),
                         fg=self.theme.selected_fg, bg=self.theme.selected_bg,
                         underline=True)
            draw_status_line(buffer, self.theme,
                             "Description, then ENTER")
            draw_help_line(buffer, self.theme, "ENTER accept   ESC cancel")
        elif self.stage == "parameters":
            self._view_parameters(buffer)
        elif self.stage == "formatting":
            self._view_formatting(buffer)
        elif self.stage == "calc":
            title_bar(buffer, "Calculated Form Field", self.theme)
            buffer.write(4, 2, "Expression", fg=self.theme.label,
                         bg=self.theme.bg)
            buffer.write(4, 20, ":", fg=self.theme.label, bg=self.theme.bg)
            buffer.fill_rect(4, 22, 1, 80, " ", fg=self.theme.selected_fg,
                             bg=self.theme.selected_bg)
            buffer.write(4, 22, clip_text(self.edit_text, 80),
                         fg=self.theme.selected_fg, bg=self.theme.selected_bg,
                         underline=True)
            draw_status_line(buffer, self.theme,
                             self.status or "ENTER accept   ESC cancel")
            draw_help_line(buffer, self.theme, "ENTER accept   ESC cancel")
        else:
            self._view_layout(buffer)
        view = View(buffer, [])
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        return view

    def _view_parameters(self, buffer: CellBuffer) -> None:
        title_bar(buffer, f"Form Parameters - {self.form.letter}", self.theme)
        for index, (key_name, label, value) in enumerate(
                self._parameter_rows()):
            row = 3 + index
            selected = index == self.param_row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            buffer.write(row, 2, label, fg=fg, bg=bg, bold=selected)
            buffer.write(row, 26, ":", fg=fg, bg=bg)
            text = self.edit_text if selected and self.editing else value
            buffer.write(row, 28, clip_text(text, 80), fg=fg, bg=bg,
                         underline=selected and self.editing)
        draw_status_line(buffer, self.theme,
                         self.status or "F10 continue to the layout")
        draw_help_line(buffer, self.theme,
                       "ENTER edit/toggle   F10 continue   ESC cancel")
        draw_menu_line(buffer, self.theme, FORM_KEYS)

    @clipping_allowed
    def _view_layout(self, buffer: CellBuffer) -> None:
        assert self.form is not None
        title_bar(buffer, f"{self.title}   Page {self.page + 1} of "
                          f"{self.form.pages}", self.theme)
        # riquadri
        for box in self.form.page_boxes(self.page):
            buffer.box(box.row, box.col, box.height, box.width,
                       fg=self.theme.border, bg=self.theme.bg,
                       double=box.double)
        for region in self.form.page_regions(self.page):
            buffer.box(region.row, region.col, region.height, region.width,
                       fg=self.theme.accent, bg=self.theme.bg)
            buffer.write(region.row, region.col + 2,
                         clip_text(f" {region.title or region.database} ",
                                   region.width - 4),
                         fg=self.theme.accent, bg=self.theme.bg, bold=True)
        # etichette
        for label in self.form.page_labels(self.page):
            buffer.write(label.row, label.col, clip_text(
                label.text, SCREEN_WIDTH - label.col), fg=self.theme.text,
                bg=self.theme.bg)
        # campi
        for item in self.form.page_fields(self.page):
            if item.show_title and item.title:
                buffer.write(item.row - 1, item.col,
                             clip_text(item.title, max(20, item.length)),
                             fg=self.theme.label, bg=self.theme.bg)
            placeholder = f"[{item.field}]"
            buffer.write(item.row, item.col,
                         clip_text(placeholder, max(1, item.length)),
                         fg=self.theme.accent, bg=self.theme.bg,
                         underline=True)
        # cursore
        buffer.write(self.row, self.col, "_", fg=self.theme.selected_fg,
                     bg=self.theme.selected_bg, blink=True)
        draw_status_line(buffer, self.theme,
                         self.status or f"Row {self.row} Col {self.col}   "
                                        f"F2 field   F8 box   F6 region")
        draw_help_line(buffer, self.theme,
                       "F2 fields   F5 delete   F6 region   F7 params   "
                       "F8 box   F9 format   F10 save")
        draw_menu_line(buffer, self.theme, FORM_KEYS)

    def _view_formatting(self, buffer: CellBuffer) -> None:
        title_bar(buffer, "Formatting Options", self.theme)
        headers = ("Field", "Page", "Len", "Window", "Just", "Fmt",
                   "Title")
        columns = (2, 24, 32, 39, 46, 53, 60)
        for header, col in zip(headers, columns):
            buffer.write(2, col, header, fg=self.theme.text, bg=self.theme.bg,
                         bold=True)
        for index, item in enumerate(self._formatting_rows()[:18]):
            row = 3 + index
            selected = index == self.format_row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ",
                                 fg=fg, bg=bg)
            values = (f"{item.database}.{item.field}", str(item.page + 1),
                      str(item.length), str(item.window), item.justification,
                      item.format, item.title)
            widths = (28, 5, 7, 7, 5, 6, 20)
            for column, (value, col) in enumerate(zip(values, columns)):
                text = self.edit_text if selected and self.editing \
                    and column + 1 == self.format_col else value
                buffer.write(row, col, clip_text(text, widths[column]),
                             fg=fg, bg=bg,
                             underline=selected and self.editing
                             and column + 1 == self.format_col)
        draw_status_line(buffer, self.theme,
                         self.status or "TAB next column   ENTER edit   "
                                        "F10 back to layout")
        draw_help_line(buffer, self.theme,
                       "UP/DOWN field   F10 continue   ESC cancel")
        draw_menu_line(buffer, self.theme, FORM_KEYS)


__all__ = ["FormDesigner"]
