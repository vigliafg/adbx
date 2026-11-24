"""Report designer e anteprima (O7).

Il designer ricalca il flusso del manuale: lettera A-Z, Quick setup o Custom
report, parametri su due pagine, parametri di raggruppamento, layout a
sezioni, campi calcolati, summary e opzioni di formattazione. `F10` salva,
salva e stampa l'anteprima o produce un PDF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..cell.buffer import (
    Cell,
    CellBuffer,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    STATUS_ROW,
    clipping_allowed,
)
from ..data.fields import Field
from ..data.report_engine import ReportOutput
from ..data.reports import (
    DEFAULT_SECTIONS,
    IGNORE_OPTIONS,
    MAX_GROUP_LEVELS,
    MAX_WIDTH,
    MIN_WIDTH,
    REPORT_LETTERS,
    SECTION_TITLES,
    SUMMARY_LEVELS,
    SUMMARY_MODES,
    SUMMARY_ONLY,
    SUMMARY_TYPES,
    SYSTEM_FIELDS,
    ReportCalc,
    ReportDefinition,
    ReportError,
    ReportField,
    ReportSummary,
    ReportText,
    summary_type_for_section,
)
from ..data.sets import SetDefinition
from ..data.workspace import Database, Workspace
from ..render.report_pdf import write_report_pdf
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

# Compatte per stare in 80 colonne: Alt-O resta nella help line.
REPORT_KEYS = [("F1", "Help"), ("F2", "Flds"), ("F3", "Sect"),
               ("F4", "Calc"), ("F5", "Del"), ("F6", "Grp"),
               ("F7", "Goto"), ("F9", "Line"), ("F10", "Save")]
CONTENT_TOP = 3


@dataclass
class ReportDesigner:
    workspace: Workspace
    database: Database | None = None
    owner: str = ""
    report: ReportDefinition | None = None
    theme: Theme = NEWPORT
    stage: str = "letter"
    letter_text: str = ""
    description_text: str = ""
    edit_existing: bool = False
    quick: bool = False
    page_rows: int = 0
    param_row: int = 0
    param_page: int = 1
    edit_text: str = ""
    edit_key: str = ""
    editing: bool = False
    section: str = "titles"
    row: int = 1
    col: int = 1
    picker: Picker | None = None
    picker_kind: str = ""
    pending_database: str = ""
    pending_field: str = ""
    pending_definition: Field | None = None
    pending_summary: ReportSummary | None = None
    pending_calc: ReportCalc | None = None
    summary_row: int = 0
    summary_return: str = "layout"
    calc_row: int = 0
    format_row: int = 0
    format_col: int = 1
    line_row: int = 0
    group_row: int = 0
    group_flag_row: int = 0
    group_focus: int = 0
    pending_place: bool = True
    status: str = ""
    close: bool = False
    saved: bool = False
    saved_report: ReportDefinition | None = None
    preview_request: bool = False
    pdf_request: bool = False
    help_topic: str = "reports"
    section_tops: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.owner:
            self.owner = (self.database.name if self.database is not None
                          else "")
        if self.report is None:
            self.stage = "letter"

    # -- proprietario ----------------------------------------------------
    @property
    def owner_databases(self) -> dict[str, Database]:
        database = self.workspace.get(self.owner)
        if database is not None:
            return {database.name: database}
        definition = self.set_definition
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
            return "Create/Edit a Report"
        if self.report is None:
            return "Report Designer"
        return f"Report Layout - {self.report.letter} - {self.owner}"

    def handle(self, key: Key) -> None:
        self.status = ""
        if self.picker is not None:
            self._handle_picker(key)
            return
        handler = {
            "letter": self._handle_letter,
            "type": self._handle_type,
            "params1": self._handle_params,
            "params2": self._handle_params,
            "grouping": self._handle_grouping,
            "layout": self._handle_layout,
            "calc": self._handle_calc,
            "calc_name": self._handle_calc,
            "calc_expression": self._handle_calc,
            "summary": self._handle_summary,
            "formatting": self._handle_formatting,
            "borrow_letter": self._handle_borrow_letter,
        }.get(self.stage, self._handle_layout)
        handler(key)

    # -- creazione -------------------------------------------------------
    def _handle_letter(self, key: Key) -> None:
        if key.name == "ENTER":
            letter = self.letter_text.strip().upper()[:1] or "A"
            if letter not in REPORT_LETTERS:
                self.status = "Choose a report id A-Z."
                return
            existing = self.workspace.get_report(self.owner, letter)
            if existing is not None:
                self.report = existing
                self.edit_existing = True
                self.stage = "layout"
                self.section = self.report.sections[0]
                self.row = 1
                self.col = 1
                self.status = "Editing an existing report."
            else:
                self.report = ReportDefinition(self.workspace, self.owner,
                                                letter)
                self.stage = "type"
                self.page_rows = 0
            return
        if key.name == "ESC":
            self.close = True
            return
        text = character(key)
        if text and text.isalpha():
            self.letter_text = text.upper()

    def _handle_type(self, key: Key) -> None:
        assert self.report is not None
        if self.picker is not None:
            return
        if key.name in ("DOWN", "UP"):
            self.page_rows = 1 - self.page_rows
            return
        if key.name == "ENTER":
            self.quick = self.page_rows == 0
            if self.quick:
                self._quick_setup()
            else:
                self.stage = "params1"
                self.param_page = 1
                self.param_row = 0
        elif key.name == "ESC":
            self.close = True

    def _quick_setup(self) -> None:
        report = self.report
        assert report is not None
        report.description = "Quick report"
        report.sections = ["titles", "detail", "summary"]
        report.section_lines = {name: 1 for name in report.sections}
        report.texts = [ReportText("titles", 1, 1, "Quick Report")]
        report.fields = []
        col = 1
        for database in self.owner_databases.values():
            for definition in database.fields:
                if definition.is_memo:
                    continue
                report.texts.append(ReportText("titles", 1, col,
                                               definition.name))
                report.fields.append(ReportField(
                    "detail", 1, col, f"{database.name}.{definition.name}",
                    length=min(definition.length, 20),
                    window=min(definition.length, 20),
                    justification="R" if definition.type == "N" else "L"))
                col += min(definition.length, 20) + 1
                if col > report.width - 10:
                    break
            break
        report.width = min(MAX_WIDTH, max(MIN_WIDTH, col + 10))
        self.section = "detail"
        self.row = 1
        self.col = 1
        self.stage = "layout"

    # -- parametri -------------------------------------------------------
    def _parameter_rows(self) -> list[tuple[str, str, str, str]]:
        report = self.report
        assert report is not None
        if self.param_page == 1:
            return [
                ("description", "Report description", report.description, "text"),
                ("width", "Report width (columns)", str(report.width), "int"),
                ("groups", "Number of grouping levels",
                 str(report.group_count), "int"),
                ("titles_first", "Print titles only on page 1",
                 _yes(report.print_titles_first_page_only), "bool"),
                ("footer_odd", "Print page footer only on odd pages",
                 _yes(report.print_footer_odd_pages_only), "bool"),
                ("summary_page", "Print summary section on separate page",
                 _yes(report.summary_on_separate_page), "bool"),
                ("suppress", "Suppress blank lines",
                 _yes(report.suppress_blank_lines), "bool"),
                ("blank_after", "Blank line after how many records",
                 str(report.blank_line_after), "int"),
                ("page_breaks", "Page breaks", _yes(report.page_breaks), "bool"),
                ("widow", "Widow record count", str(report.widow_count), "int"),
                ("orphan", "Orphan record count", str(report.orphan_count), "int"),
                ("split", "Split lines count", str(report.split_lines), "int"),
                ("max_records", "Max records per page (0 = no maximum)",
                 str(report.max_records_page), "int"),
                ("reset_page", "Reset page number after a group",
                 _yes(report.reset_page_after_group), "bool"),
                ("reprint", "Re-print group header after a page break",
                 _yes(report.reprint_group_header), "bool"),
            ]
        return [
            ("left", "Left margin", str(report.left_margin), "int"),
            ("top", "Top margin", str(report.top_margin), "int"),
            ("standard", "Standard page length",
             _yes(report.standard_page_length), "bool"),
            ("length", "Page length", str(report.page_length), "int"),
        ]

    def _handle_params(self, key: Key) -> None:
        rows = self._parameter_rows()
        name = key.name
        if self.editing:
            if name == "ENTER":
                self._commit_parameter()
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
                if text.isalpha() and not key.shift:
                    text = text.lower()
                self.edit_text += text
            return
        if name == "F10":
            self._commit_parameter()
            if self.param_page == 1:
                self.param_page = 2
                self.param_row = 0
            elif self.report is not None and self.report.group_count:
                self.stage = "grouping"
                self.group_row = 0
                self.group_focus = 0
            else:
                self._open_layout()
            return
        if name == "PGUP" and self.param_page == 2:
            self._commit_parameter()
            self.param_page = 1
            self.param_row = 0
            return
        if name == "PGDN" and self.param_page == 1:
            self._commit_parameter()
            self.param_page = 2
            self.param_row = 0
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
            kind = rows[self.param_row][3]
            if kind == "bool":
                self._toggle_parameter(rows[self.param_row][0])
                return
            self.edit_text = rows[self.param_row][2]
            self.edit_key = rows[self.param_row][0]
            self.editing = True

    def _toggle_parameter(self, name: str) -> None:
        report = self.report
        assert report is not None
        attribute = {
            "titles_first": "print_titles_first_page_only",
            "footer_odd": "print_footer_odd_pages_only",
            "summary_page": "summary_on_separate_page",
            "suppress": "suppress_blank_lines",
            "page_breaks": "page_breaks",
            "reset_page": "reset_page_after_group",
            "reprint": "reprint_group_header",
            "standard": "standard_page_length",
        }.get(name)
        if attribute:
            setattr(report, attribute, not getattr(report, attribute))

    def _commit_parameter(self) -> None:
        report = self.report
        if report is None:
            return
        rows = self._parameter_rows()
        if not rows:
            return
        name = rows[self.param_row][0]
        if self.edit_key != name:
            return
        self.edit_key = ""
        value = self.edit_text.strip()
        if name == "description":
            report.description = value
        elif name == "width":
            try:
                report.width = max(MIN_WIDTH, min(MAX_WIDTH, int(value)))
            except ValueError:
                pass
        elif name == "groups":
            try:
                report.set_group_count(int(value))
            except ValueError:
                pass
        elif name == "blank_after":
            try:
                report.blank_line_after = max(0, min(100, int(value)))
            except ValueError:
                pass
        elif name in ("widow", "orphan", "split", "max_records"):
            try:
                number = max(0, min(99, int(value)))
            except ValueError:
                number = 0
            setattr(report, {"widow": "widow_count", "orphan": "orphan_count",
                             "split": "split_lines",
                             "max_records": "max_records_page"}[name], number)
        elif name in ("left", "top"):
            try:
                number = max(0, min(40, int(value)))
            except ValueError:
                number = 0
            setattr(report, "left_margin" if name == "left" else "top_margin",
                    number)
        elif name == "length":
            try:
                report.page_length = max(10, min(99, int(value)))
            except ValueError:
                pass

    # -- gruppi ----------------------------------------------------------
    def _handle_grouping(self, key: Key) -> None:
        report = self.report
        assert report is not None
        name = key.name
        if name == "F10":
            self.stage = "layout"
            self._open_layout()
            return
        if name == "ESC":
            self.stage = "params1"
            self.param_page = 1
            self.param_row = 0
            return
        if name == "F6":
            if report.group_count < MAX_GROUP_LEVELS:
                report.set_group_count(report.group_count + 1)
                self.group_row = report.group_count - 1
            return
        if name == "F5":
            if report.group_count:
                report.set_group_count(report.group_count - 1)
                self.group_row = max(0, min(self.group_row,
                                            report.group_count - 1))
            return
        if name == "F2":
            self._open_break_picker()
            return
        if name == "TAB":
            self.group_focus = 1 - self.group_focus
            return
        if name == "F9":
            self.group_focus = 1 - self.group_focus
            return
        if not report.groups:
            return
        group = report.groups[max(0, min(self.group_row,
                                         report.group_count - 1))]
        if self.group_focus == 0:
            if name in ("UP", "DOWN"):
                self.group_row = max(0, min(report.group_count - 1,
                                            self.group_row
                                            + (-1 if name == "UP" else 1)))
                return
            if self.editing:
                if name == "ENTER":
                    group.break_field = self.edit_text.strip().upper()
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
                    self.edit_text += text.upper() if text.isalpha() else text
                return
            if name == "ENTER":
                self.edit_text = group.break_field
                self.editing = True
            return
        rows = ["reprint_titles", "start_header_new_page",
                "substitute_header", "start_footer_new_page",
                "substitute_footer", "case_sensitive"]
        if name in ("UP", "DOWN"):
            self.group_flag_row = max(0, min(len(rows) - 1,
                                            self.group_flag_row
                                            + (-1 if name == "UP" else 1)))
            return
        if name == "ENTER":
            attribute = rows[self.group_flag_row]
            setattr(group, attribute, not getattr(group, attribute))

    def _open_break_picker(self) -> None:
        items: list[str] = []
        values: list[str] = []
        assert self.report is not None
        for name, database in self.owner_databases.items():
            prefix = f"{name}." if len(self.owner_databases) > 1 else ""
            for definition in database.fields:
                items.append(prefix + definition.name)
                values.append(f"{name}.{definition.name}")
        for calc in self.report.calcs:
            items.append(f"CALC.{calc.name}")
            values.append(f"CALC.{calc.name}")
        self.picker = Picker("Break field", items, values,
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "break_field"

    # -- layout ----------------------------------------------------------
    def _open_layout(self) -> None:
        report = self.report
        assert report is not None
        if not report.sections:
            report.sections = list(DEFAULT_SECTIONS)
        if self.section not in report.sections:
            self.section = report.sections[0]
        self.row = max(1, min(self.report.section_height(self.section),
                              self.row))
        self.stage = "layout"

    def _handle_layout(self, key: Key) -> None:
        report = self.report
        assert report is not None
        name = key.name
        if name == "F2":
            self._open_field_picker()
            return
        if name == "F3":
            self._open_sections_picker()
            return
        if name == "F4":
            self._open_synthetic_picker()
            return
        if name == "F5":
            self._delete_at_cursor()
            return
        if name == "F6":
            report.set_group_count(report.group_count + 1)
            self.status = f"Group {report.group_count} added."
            return
        if name == "F7":
            self.picker = Picker("Goto", ["Report parameters",
                                          "Grouping parameters",
                                          "Range and print settings"],
                                 values=["params", "grouping", "range"],
                                 footer="ENTER select   ESC cancel")
            self.picker_kind = "goto"
            return
        if name == "F9":
            self.picker = Picker(
                "Line", ["Left justify", "Center justify", "Right justify",
                         "Insert line", "Delete line", "Add line at end",
                         "Fill to end with -"],
                values=["left", "center", "right", "insert", "delete", "add",
                        "fill"],
                footer="ENTER select   ESC cancel")
            self.picker_kind = "line"
            return
        if name == "F10":
            self._open_save()
            return
        if key.alt and name == "O":
            self.stage = "formatting"
            self.format_row = self._field_at_cursor_index()
            self.format_col = 2
            return
        if name == "ESC":
            self.close = True
            return
        if name == "PGUP":
            self._move_section(-1)
            return
        if name == "PGDN":
            self._move_section(1)
            return
        if name == "UP":
            if self.row > 1:
                self.row -= 1
            else:
                self._move_section(-1, last=True)
            return
        if name == "DOWN":
            if self.row < report.section_height(self.section):
                self.row += 1
            else:
                self._move_section(1)
            return
        if name == "LEFT":
            self.col = max(1, self.col - 1)
            return
        if name == "RIGHT":
            self.col = min(report.width, self.col + 1)
            return
        if name == "HOME":
            self.col = 1
            return
        if name == "END":
            self.col = report.width
            return
        if name == "BACKSPACE":
            self._backspace_text()
            return
        if name == "DELETE":
            self._delete_text_char()
            return
        if name == "SPACE":
            self._type_text(" ")
            return
        text = character(key)
        if text:
            if text.isalpha() and not key.shift:
                text = text.lower()
            self._type_text(text)

    def _move_section(self, direction: int, *, last: bool = False) -> None:
        report = self.report
        assert report is not None
        index = report.sections.index(self.section)
        index = max(0, min(len(report.sections) - 1, index + direction))
        self.section = report.sections[index]
        self.row = (report.section_height(self.section) if last else 1)
        self.col = 1

    def _type_text(self, text: str) -> None:
        report = self.report
        assert report is not None
        item = self._text_at(self.row, self.col)
        if item is None:
            before = next((entry for entry in report.texts
                           if entry.section == self.section
                           and entry.row == self.row
                           and entry.col + len(entry.text) == self.col), None)
            if before is not None:
                before.text += text
            else:
                report.texts.append(ReportText(self.section, self.row,
                                               self.col, text))
        else:
            offset = self.col - item.col
            item.text = item.text[:offset] + text + item.text[offset + 1:]
        self.col = min(report.width, self.col + 1)

    def _text_at(self, row: int, col: int) -> ReportText | None:
        assert self.report is not None
        for item in self.report.texts:
            if item.section == self.section and item.row == row \
                    and item.col <= col < item.col + len(item.text):
                return item
        return None

    def _backspace_text(self) -> None:
        assert self.report is not None
        item = self._text_at(self.row, self.col - 1)
        if item is None:
            self.col = max(1, self.col - 1)
            return
        offset = self.col - 1 - item.col
        if 0 <= offset < len(item.text):
            item.text = item.text[:offset] + item.text[offset + 1:]
        if not item.text:
            self.report.texts.remove(item)
        self.col = max(1, self.col - 1)

    def _delete_text_char(self) -> None:
        assert self.report is not None
        item = self._text_at(self.row, self.col)
        if item is None:
            return
        offset = self.col - item.col
        item.text = item.text[:offset] + item.text[offset + 1:]
        if not item.text:
            self.report.texts.remove(item)

    def _field_at(self, row: int, col: int) -> ReportField | None:
        assert self.report is not None
        for item in self.report.fields:
            if item.section != self.section or item.row != row:
                continue
            if item.col <= col < item.col + max(1, item.window
                                                or item.length):
                return item
        return None

    def _field_at_cursor_index(self) -> int:
        item = self._field_at(self.row, self.col)
        if item is None:
            return 0
        assert self.report is not None
        try:
            return self.report.fields.index(item)
        except ValueError:
            return 0

    def _delete_at_cursor(self) -> None:
        assert self.report is not None
        item = self._field_at(self.row, self.col)
        if item is not None:
            self.report.fields.remove(item)
            return
        item_text = self._text_at(self.row, self.col)
        if item_text is not None:
            self.report.texts.remove(item_text)

    # -- picker ----------------------------------------------------------
    def _open_field_picker(self) -> None:
        items = list(self.owner_databases) + ["SYSTEM"]
        values = list(self.owner_databases) + ["SYSTEM"]
        if self.report is not None and self.report.calcs:
            items.append("CALC")
            values.append("CALC")
        if self.report is not None and self.report.summaries:
            items.append("SUMMARY")
            values.append("SUMMARY")
        self.picker = Picker("Database", items, values,
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "database"

    def _open_synthetic_picker(self) -> None:
        self.picker = Picker("Form field", ["Calculated field", "Summary field"],
                             values=["calculated", "summary"],
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "synthetic"

    def _open_sections_picker(self) -> None:
        assert self.report is not None
        available = [name for name in SECTION_TITLES
                     if name not in self.report.sections]
        self.picker = Picker("Sections",
                             ["Insert section", "Delete section"],
                             values=["insert", "delete"],
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "sections_menu"
        self._available_sections = available

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
                self._picker_selected(kind, value)

    def _picker_selected(self, kind: str, value: str) -> None:
        report = self.report
        assert report is not None
        if kind == "database":
            self.pending_database = value
            self._open_database_fields(value)
        elif kind == "field":
            database, field = value.split(":", 1)
            self.pending_database = database
            self.pending_field = field
            definition = None
            if database not in ("CALC", "SUMMARY", "SYSTEM"):
                definition = self.owner_databases[database].field(field)
            self.pending_definition = definition
            self.picker = Picker("Summary Type", list(SUMMARY_TYPES),
                                 values=list(SUMMARY_TYPES),
                                 footer="ENTER select   ESC cancel")
            self.picker_kind = "display"
        elif kind == "display":
            self._place_field(value)
        elif kind == "synthetic":
            if value == "calculated":
                self.stage = "calc"
                self.pending_calc = None
                self.status = "F2 adds a calculated field."
            else:
                self.summary_return = "layout"
                self._start_field_summary_picker()
        elif kind == "goto":
            if value == "params":
                self.stage = "params1"
                self.param_page = 1
                self.param_row = 0
            elif value == "grouping":
                self.stage = "grouping"
                self.group_row = 0
                self.group_focus = 0
            else:
                self.status = "Range and print settings are stored in O12."
        elif kind == "line":
            self._line_action(value)
        elif kind == "sections_menu":
            self._sections_action(value)
        elif kind == "sections_add":
            if report.add_section(value):
                self.section = value
                self.row = 1
                self.col = 1
        elif kind == "sections_delete":
            if report.remove_section(value) and self.section == value:
                self.section = report.sections[0]
                self.row = 1
                self.col = 1
        elif kind == "break_field":
            if report.group_count:
                report.groups[max(0, min(self.group_row,
                                         report.group_count - 1))].break_field = value
        elif kind == "save":
            self._save_action(value)
        elif kind == "calc_field":
            self.pending_calc = ReportCalc(value, "0")
            self.edit_text = ""
            self.stage = "calc_expression"
        elif kind == "calc_delete":
            report.calcs = [calc for calc in report.calcs if calc.name != value]
        elif kind == "summary_field":
            self._start_advanced_summary(value)
        elif kind == "summary_level":
            if self.pending_summary is not None:
                self.pending_summary.level = value
                self._ask_summary_ignore()
        elif kind == "summary_ignore":
            if self.pending_summary is not None:
                self.pending_summary.ignore = value
                self._ask_summary_mode()
        elif kind == "summary_mode":
            if self.pending_summary is not None:
                self.pending_summary.mode = value
                self._finish_summary()
        elif kind == "summary_type_adv":
            if self.pending_summary is not None:
                self.pending_summary.summary_type = value
                self._ask_summary_level()
        elif kind == "borrow_report":
            source = self.workspace.get_report(self.owner, value)
            if source is not None:
                self.report = ReportDefinition.from_dict(
                    self.workspace, source.to_dict())
                self.report.owner = self.owner
                self.report.letter = ""
                self.stage = "borrow_letter"
                self.letter_text = ""
        elif kind == "borrow_letter":
            pass
        elif kind == "print_report":
            pass

    def _open_database_fields(self, database_name: str) -> None:
        report = self.report
        assert report is not None
        items: list[str] = []
        values: list[str] = []
        if database_name == "SYSTEM":
            items = list(SYSTEM_FIELDS)
            values = [f"SYSTEM:{name}" for name in SYSTEM_FIELDS]
        elif database_name == "CALC":
            items = [calc.name for calc in report.calcs]
            values = [f"CALC:{calc.name}" for calc in report.calcs]
        elif database_name == "SUMMARY":
            items = [summary.name for summary in report.summaries]
            values = [f"SUMMARY:{summary.name}" for summary in report.summaries]
        else:
            database = self.owner_databases[database_name]
            for definition in database.fields:
                items.append(definition.name)
                values.append(f"{database_name}:{definition.name}")
        if not items:
            self.status = f"No fields available in {database_name}."
            return
        self.picker = Picker("Fieldnames", items, values,
                             footer="ENTER place field   ESC cancel")
        self.picker_kind = "field"

    def _place_field(self, display: str) -> None:
        report = self.report
        assert report is not None
        database = self.pending_database
        name = self.pending_field
        if not database or not name:
            return
        source = f"{database}.{name}"
        if display in SUMMARY_ONLY:
            summary = self._create_summary(source, display)
            self._place_summary_field(summary)
            return
        definition = self.pending_definition
        length = 12
        justification = "R"
        format_ = ""
        decimals = None
        if definition is not None:
            length = definition.length
            justification = "R" if definition.type == "N" else "L"
            if definition.is_memo:
                length, format_ = 300, "X"
                justification = "L"
        elif database == "SYSTEM":
            length = 10
            justification = "L" if name in ("DATE", "TIME") else "R"
            if name == "DATE":
                format_ = "1"
                length = 10
        elif database == "SUMMARY":
            length = 12
            justification = "R"
        elif database == "CALC":
            length = 12
            justification = "R"
            decimals = 2
        item = ReportField(self.section, self.row, self.col, source,
                           database, name, length, length, justification,
                           format_, decimals, display)
        report.fields.append(item)
        self.col = min(report.width, self.col + max(1, length) + 1)
        self.status = f"{source} placed."

    def _create_summary(self, source: str, summary_type: str,
                        level: str | None = None) -> ReportSummary:
        report = self.report
        assert report is not None
        if level is None:
            _kind, level = summary_type_for_section(self.section)
        field_name = source.split(".")[-1][:7]
        code = {"First": "F", "Last": "L", "Count": "C", "Biggest": "B",
                "Smallest": "S", "Total": "T", "Average": "A"}[summary_type]
        level_code = ("G" if level == "Grand" else "P" if level == "Page"
                      else level.split()[1])
        base = f"{field_name}_{code}{level_code}"[:10].upper()
        name = base
        index = 1
        while name in {summary.name for summary in report.summaries}:
            suffix = str(index)
            name = (base[:10 - len(suffix)] + suffix).upper()
            index += 1
        summary = ReportSummary(name, source, summary_type, level,
                                "None", "Running")
        report.summaries.append(summary)
        return summary

    def _place_summary_field(self, summary: ReportSummary) -> None:
        report = self.report
        assert report is not None
        item = ReportField(self.section, self.row, self.col,
                           f"SUMMARY.{summary.name}", "SUMMARY",
                           summary.name, 12, 12, "R", "", 2, "Value")
        report.fields.append(item)
        self.col = min(report.width, self.col + 13)
        self.status = f"SUMMARY.{summary.name} placed."

    def _start_advanced_summary(self, source: str = "") -> None:
        if not source:
            self.stage = "summary"
            self.status = "F2 chooses the field to summarize."
            return
        summary_type, level = summary_type_for_section(self.section)
        summary = self._create_summary(source, summary_type, level)
        self.pending_summary = summary
        self.pending_place = True
        self._ask_summary_type()

    def _ask_summary_type(self) -> None:
        self.picker = Picker("Summary type", list(SUMMARY_ONLY),
                             values=list(SUMMARY_ONLY),
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "summary_type_adv"

    def _ask_summary_level(self) -> None:
        levels = list(SUMMARY_LEVELS[:2]) + [
            level for level in SUMMARY_LEVELS[2:]
            if int(level.split()[1]) <= (self.report.group_count
                                         if self.report else 0)]
        self.picker = Picker("Summary level", levels, values=levels,
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "summary_level"

    def _ask_summary_ignore(self) -> None:
        self.picker = Picker("Ignore", list(IGNORE_OPTIONS),
                             values=list(IGNORE_OPTIONS),
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "summary_ignore"

    def _ask_summary_mode(self) -> None:
        self.picker = Picker("Summary mode", list(SUMMARY_MODES),
                             values=list(SUMMARY_MODES),
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "summary_mode"

    def _finish_summary(self) -> None:
        summary = self.pending_summary
        if summary is None:
            return
        if self.pending_place:
            self._place_summary_field(summary)
        self.pending_summary = None
        self.stage = self.summary_return

    # -- linee e sezioni -------------------------------------------------
    def _line_action(self, action: str) -> None:
        report = self.report
        assert report is not None
        if action == "add":
            report.section_lines[self.section] = (
                report.section_height(self.section) + 1)
            return
        if action == "insert":
            for item in report.fields:
                if item.section == self.section and item.row >= self.row:
                    item.row += 1
            for item in report.texts:
                if item.section == self.section and item.row >= self.row:
                    item.row += 1
            report.section_lines[self.section] = (
                report.section_height(self.section) + 1)
            return
        if action == "delete":
            report.fields = [item for item in report.fields
                             if not (item.section == self.section
                                     and item.row == self.row)]
            report.texts = [item for item in report.texts
                            if not (item.section == self.section
                                    and item.row == self.row)]
            for item in report.fields:
                if item.section == self.section and item.row > self.row:
                    item.row -= 1
            for item in report.texts:
                if item.section == self.section and item.row > self.row:
                    item.row -= 1
            height = max(1, report.section_height(self.section) - 1)
            report.section_lines[self.section] = height
            self.row = min(self.row, height)
            return
        if action == "fill":
            text = "-" * max(0, report.width - self.col + 1)
            report.texts.append(ReportText(self.section, self.row, self.col,
                                           text))
            return
        texts = [item for item in report.texts
                 if item.section == self.section and item.row == self.row]
        if not texts:
            return
        start = min(item.col for item in texts)
        end = max(item.col + len(item.text) for item in texts)
        if action == "left":
            shift = 1 - start
        elif action == "center":
            shift = (report.width - (end - start)) // 2 + 1 - start
        else:
            shift = report.width - (end - start) + 1 - start
        for item in texts:
            item.col = max(1, item.col + shift)

    def _sections_action(self, action: str) -> None:
        report = self.report
        assert report is not None
        if action == "insert":
            available = [name for name in SECTION_TITLES
                         if name not in report.sections]
            if not available:
                self.status = "All sections are already in the report."
                return
            self.picker = Picker("Insert section", available,
                                 values=available,
                                 footer="ENTER insert   ESC cancel")
            self.picker_kind = "sections_add"
        else:
            self.picker = Picker("Delete section", list(report.sections),
                                 values=list(report.sections),
                                 footer="ENTER delete   ESC cancel")
            self.picker_kind = "sections_delete"

    # -- calcolati e summary --------------------------------------------
    def _handle_calc(self, key: Key) -> None:
        report = self.report
        assert report is not None
        name = key.name
        if self.stage == "calc_name":
            if name == "ENTER":
                candidate = self.edit_text.strip().upper()
                if not candidate.replace("_", "").isalnum() or not candidate[:1].isalpha():
                    self.status = "Invalid calculated field name."
                    return
                if candidate in {calc.name for calc in report.calcs}:
                    self.status = "That calculated field already exists."
                    return
                try:
                    self.pending_calc = ReportCalc(candidate, "0")
                except ReportError as exc:
                    self.status = str(exc)
                    return
                self.edit_text = ""
                self.stage = "calc_expression"
                self.status = "Enter the expression."
                return
            if name == "ESC":
                self.stage = "calc"
                return
            if name == "BACKSPACE":
                self.edit_text = self.edit_text[:-1]
                return
            text = character(key)
            if text and (text.isalnum() or text == "_"):
                self.edit_text += text.upper()
            return
        if self.stage == "calc_expression":
            if name == "ENTER":
                expression = self.edit_text.strip()
                if not expression:
                    self.status = "Enter an expression."
                    return
                if self.pending_calc is None:
                    self.pending_calc = ReportCalc(
                        self._next_calc_name(), expression)
                    report.calcs.append(self.pending_calc)
                elif self.pending_calc in report.calcs:
                    self.pending_calc.expression = expression
                else:
                    self.pending_calc.expression = expression
                    report.calcs.append(self.pending_calc)
                self.pending_calc = None
                self.stage = "calc"
                self.status = "Calculated field saved."
                return
            if name == "ESC":
                self.pending_calc = None
                self.stage = "calc"
                return
            if name == "BACKSPACE":
                self.edit_text = self.edit_text[:-1]
                return
            text = character(key)
            if text:
                if text.isalpha() and not key.shift:
                    text = text.lower()
                self.edit_text += text
            return
        if name == "F10":
            self._open_layout()
            return
        if name == "ESC":
            self.close = True
            return
        if name == "F2":
            self.pending_calc = None
            self.edit_text = ""
            self.stage = "calc_name"
            return
        if name in ("UP", "DOWN") and report.calcs:
            self.calc_row = max(0, min(len(report.calcs) - 1,
                                       self.calc_row
                                       + (-1 if name == "UP" else 1)))
            return
        if name == "F5" and report.calcs:
            removed = report.calcs.pop(self.calc_row)
            report.fields = [item for item in report.fields
                             if item.source != f"CALC.{removed.name}"]
            self.calc_row = max(0, min(self.calc_row, len(report.calcs) - 1))
            return
        if name == "ENTER" and report.calcs:
            self.pending_calc = report.calcs[self.calc_row]
            self.edit_text = self.pending_calc.expression
            self.stage = "calc_expression"

    def _handle_summary(self, key: Key) -> None:
        report = self.report
        assert report is not None
        name = key.name
        if name == "F10":
            self._open_layout()
            return
        if name == "ESC":
            self.close = True
            return
        if name == "F2":
            self.summary_return = "summary"
            self._start_field_summary_picker()
            return
        if name in ("UP", "DOWN") and report.summaries:
            self.summary_row = max(0, min(len(report.summaries) - 1,
                                          self.summary_row
                                          + (-1 if name == "UP" else 1)))
            return
        if name == "F5" and report.summaries:
            report.summaries.pop(self.summary_row)
            self.summary_row = max(0, min(self.summary_row,
                                          len(report.summaries) - 1))
            return
        if name == "ENTER" and report.summaries:
            summary = report.summaries[self.summary_row]
            self.pending_summary = summary
            self.pending_place = False
            self._ask_summary_type()

    def _start_field_summary_picker(self) -> None:
        items: list[str] = []
        values: list[str] = []
        report = self.report
        assert report is not None
        for name, database in self.owner_databases.items():
            prefix = f"{name}." if len(self.owner_databases) > 1 else ""
            for definition in database.fields:
                items.append(prefix + definition.name)
                values.append(f"{name}.{definition.name}")
        for calc in report.calcs:
            items.append(f"CALC.{calc.name}")
            values.append(f"CALC.{calc.name}")
        self.picker = Picker("Field to summarize", items, values,
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "summary_field"

    def _next_calc_name(self) -> str:
        assert self.report is not None
        used = {calc.name for calc in self.report.calcs}
        index = len(self.report.calcs) + 1
        while f"CALC{index}" in used:
            index += 1
        return f"CALC{index}"

    # -- formatting ------------------------------------------------------
    def _format_rows(self) -> list[ReportField]:
        assert self.report is not None
        return list(self.report.fields)

    def _handle_formatting(self, key: Key) -> None:
        report = self.report
        assert report is not None
        rows = self._format_rows()
        name = key.name
        if name == "F10":
            self.stage = "layout"
            return
        if name == "ESC":
            self.close = True
            return
        if name in ("UP", "DOWN") and rows:
            self.format_row = max(0, min(len(rows) - 1,
                                         self.format_row
                                         + (-1 if name == "UP" else 1)))
            return
        if name == "TAB":
            self.format_col = self.format_col % 8 + 1
            return
        if name in ("LEFT", "RIGHT"):
            self.format_col = max(1, min(8, self.format_col
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
        if name == "SPACE" and self.format_col in (3, 4):
            self._cycle_data(item)
        elif name == "SPACE" and self.format_col == 5:
            modes = ["L", "R", "C", "N"]
            index = modes.index(item.justification) if item.justification in modes else 0
            item.justification = modes[(index + 1) % len(modes)]

    def _cycle_data(self, item: ReportField) -> None:
        item.data = "Unique" if item.data == "Value" else "Value"

    def _format_value(self, item: ReportField, column: int) -> str:
        return {
            1: item.section, 2: item.source, 3: item.data,
            4: str(item.length), 5: item.justification, 6: item.format,
            7: "" if item.decimals is None else str(item.decimals),
            8: str(item.window),
        }.get(column, "")

    def _set_format_value(self, item: ReportField, column: int,
                          value: str) -> None:
        if column == 2:
            if value.strip():
                item.source = value.strip().upper()
                database, _, name = item.source.partition(".")
                item.database = database
                item.name = name or item.source
        elif column == 3:
            item.data = "Unique" if value.strip().upper().startswith("U") else "Value"
        elif column == 4:
            try:
                item.length = max(0, int(value))
                if item.window > item.length:
                    item.window = item.length
            except ValueError:
                pass
        elif column == 5:
            if value.strip().upper()[:1] in ("L", "R", "C", "N"):
                item.justification = value.strip().upper()[:1]
        elif column == 6:
            item.format = value.strip()
        elif column == 7:
            try:
                item.decimals = max(0, min(14, int(value)))
            except ValueError:
                item.decimals = None
        elif column == 8:
            try:
                item.window = max(0, int(value))
                if item.window > item.length and item.length:
                    item.window = item.length
            except ValueError:
                pass

    # -- salvataggio -----------------------------------------------------
    def _open_save(self) -> None:
        options = ["Save", "Save and preview", "Save and continue editing",
                   "Save as a new letter"]
        self.picker = Picker("Save", options,
                             values=["save", "preview", "continue", "as"],
                             footer="ENTER select   ESC cancel")
        self.picker_kind = "save"

    def _save_action(self, action: str) -> None:
        if action == "as":
            self.stage = "borrow_letter"
            self.letter_text = ""
            return
        if self.save():
            if action == "preview":
                self.preview_request = True
                self.close = True
            elif action == "continue":
                self.close = False
                self.stage = "layout"
            else:
                self.close = True

    def _handle_borrow_letter(self, key: Key) -> None:
        report = self.report
        if report is None:
            return
        if key.name == "ENTER":
            letter = self.letter_text.strip().upper()[:1]
            if letter not in REPORT_LETTERS:
                self.status = "Choose a report id A-Z."
                return
            if self.workspace.get_report(self.owner, letter) is not None:
                self.status = "That report id is already used."
                return
            report.letter = letter
            if self.save():
                self.close = True
            return
        if key.name == "ESC":
            self.close = True
            return
        text = character(key)
        if text and text.isalpha():
            self.letter_text = text.upper()

    def save(self) -> bool:
        report = self.report
        if report is None:
            return False
        try:
            report.save()
        except ReportError as exc:
            self.status = str(exc)
            return False
        self.saved = True
        self.saved_report = report
        self.status = f"Report {report.letter} saved."
        return True

    # -- rendering -------------------------------------------------------
    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        if self.stage == "letter":
            self._view_letter(buffer)
        elif self.stage == "type":
            self._view_type(buffer)
        elif self.stage in ("params1", "params2"):
            self._view_parameters(buffer)
        elif self.stage == "grouping":
            self._view_grouping(buffer)
        elif self.stage in ("calc", "calc_name", "calc_expression"):
            self._view_calc(buffer)
        elif self.stage == "summary":
            self._view_summary(buffer)
        elif self.stage == "formatting":
            self._view_formatting(buffer)
        elif self.stage == "borrow_letter":
            self._view_letter(buffer, "Save as a new letter")
        else:
            self._view_layout(buffer)
        view = View(buffer, [])
        if self.picker is not None:
            return picker_view(view, self.picker, self.theme)
        return view

    def _view_letter(self, buffer: CellBuffer, title: str | None = None) -> None:
        title_bar(buffer, title or "Create/Edit a Report", self.theme)
        buffer.write(4, 2, "Report id (A-Z)", fg=self.theme.label,
                     bg=self.theme.bg)
        buffer.write(4, 20, ":", fg=self.theme.label, bg=self.theme.bg)
        buffer.fill_rect(4, 22, 1, 4, " ", fg=self.theme.selected_fg,
                         bg=self.theme.selected_bg)
        buffer.write(4, 22, self.letter_text or "_", fg=self.theme.selected_fg,
                     bg=self.theme.selected_bg, underline=True)
        draw_status_line(buffer, self.theme,
                         self.status or "Type a report id and press ENTER")
        draw_help_line(buffer, self.theme, "ENTER accept   ESC cancel")

    def _view_type(self, buffer: CellBuffer) -> None:
        title_bar(buffer, "Report Type", self.theme)
        options = [("Quick setup", "All fields on the detail line"),
                   ("Custom report", "Design the layout section by section")]
        for index, (label, note) in enumerate(options):
            row = 4 + index * 2
            selected = index == self.page_rows
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(row, 2, 1, 60, " ", fg=fg, bg=bg)
            buffer.write(row, 4, label, fg=fg, bg=bg, bold=selected)
            buffer.write(row, 22, note, fg=fg, bg=bg)
        draw_status_line(buffer, self.theme,
                         self.status or "UP/DOWN choose   ENTER continue")
        draw_help_line(buffer, self.theme, "ENTER accept   ESC cancel")

    def _view_parameters(self, buffer: CellBuffer) -> None:
        report = self.report
        assert report is not None
        title_bar(buffer, f"Report Parameters - {report.letter} - page "
                          f"{self.param_page} of 2", self.theme)
        for index, (_key, label, value, _kind) in enumerate(
                self._parameter_rows()):
            row = 3 + index
            selected = index == self.param_row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ", fg=fg, bg=bg)
            buffer.write(row, 2, clip_text(label, 52), fg=fg, bg=bg,
                         bold=selected)
            buffer.write(row, 56, ":", fg=fg, bg=bg)
            text = self.edit_text if selected and self.editing else value
            buffer.write(row, 58, clip_text(text, 30), fg=fg, bg=bg,
                         underline=selected and self.editing)
        draw_status_line(buffer, self.theme,
                         self.status or "F10 next page / continue")
        draw_help_line(buffer, self.theme,
                       "ENTER edit/toggle   PgUp/PgDn page   F10 continue   "
                       "ESC cancel")

    def _view_grouping(self, buffer: CellBuffer) -> None:
        report = self.report
        assert report is not None
        title_bar(buffer, f"Grouping Parameters - {report.letter}", self.theme)
        for index, group in enumerate(report.groups):
            row = 3 + index
            selected = index == self.group_row and self.group_focus == 0
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(row, 1, 1, 58, " ", fg=fg, bg=bg)
            text = self.edit_text if selected and self.editing \
                else group.break_field
            buffer.write(row, 3, f"Group {group.level}", fg=fg, bg=bg,
                         bold=selected)
            buffer.write(row, 14, "break:", fg=fg, bg=bg)
            buffer.write(row, 21, clip_text(text, 30), fg=fg, bg=bg,
                         underline=selected and self.editing)
        if report.groups:
            group = report.groups[min(self.group_row, len(report.groups) - 1)]
            flags = [("Re-print titles at group break", group.reprint_titles),
                     ("Start group header on new page",
                      group.start_header_new_page),
                     ("Substitute group header for page header",
                      group.substitute_header),
                     ("Start group footer on new page",
                      group.start_footer_new_page),
                     ("Substitute group footer for page footer",
                      group.substitute_footer),
                     ("Case-sensitive test for group breaks",
                      group.case_sensitive)]
            top = 7 + report.group_count
            for index, (label, active) in enumerate(flags):
                row = top + index
                selected = self.group_focus == 1 and index == self.group_flag_row
                fg = self.theme.selected_fg if selected else self.theme.text
                bg = self.theme.selected_bg if selected else self.theme.bg
                if selected:
                    buffer.fill_rect(row, 1, 1, 60, " ", fg=fg, bg=bg)
                buffer.write(row, 3, clip_text(label, 50), fg=fg, bg=bg,
                             bold=selected)
                buffer.write(row, 56, _yes(active), fg=fg, bg=bg)
        draw_status_line(buffer, self.theme,
                         self.status or "F6 add group   F5 delete group")
        draw_help_line(buffer, self.theme,
                       "TAB window   ENTER edit/toggle   F2 fields   "
                       "F10 continue   ESC cancel")

    def _view_calc(self, buffer: CellBuffer) -> None:
        report = self.report
        assert report is not None
        title_bar(buffer, "Calculated Fields", self.theme)
        headers = ("Name", "Expression")
        buffer.write(2, 4, headers[0], fg=self.theme.text, bg=self.theme.bg,
                     bold=True)
        buffer.write(2, 16, headers[1], fg=self.theme.text, bg=self.theme.bg,
                     bold=True)
        for index, calc in enumerate(report.calcs[:22]):
            row = 3 + index
            selected = index == self.calc_row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ", fg=fg, bg=bg)
            buffer.write(row, 4, calc.name, fg=fg, bg=bg, bold=selected)
            buffer.write(row, 16, clip_text(calc.expression, 90), fg=fg, bg=bg)
        if self.stage == "calc_name":
            buffer.write(4, 4, "Name:", fg=self.theme.label, bg=self.theme.bg)
            buffer.write(4, 12, self.edit_text, fg=self.theme.selected_fg,
                         bg=self.theme.selected_bg, underline=True)
        if self.stage == "calc_expression":
            buffer.write(4, 4, "Expression:", fg=self.theme.label,
                         bg=self.theme.bg)
            buffer.write(4, 18, clip_text(self.edit_text, 100),
                         fg=self.theme.selected_fg, bg=self.theme.selected_bg,
                         underline=True)
        draw_status_line(buffer, self.theme,
                         self.status or "F2 add   ENTER edit   F5 delete")
        draw_help_line(buffer, self.theme,
                       "F2 add   ENTER edit expression   F5 delete   "
                       "F10 continue   ESC cancel")

    def _view_summary(self, buffer: CellBuffer) -> None:
        report = self.report
        assert report is not None
        title_bar(buffer, "Summary Fields", self.theme)
        headers = ("Name", "Field", "Type", "Level", "Ignore", "Mode")
        columns = (2, 14, 32, 44, 54, 64)
        for header, column in zip(headers, columns):
            buffer.write(2, column, header, fg=self.theme.text,
                         bg=self.theme.bg, bold=True)
        for index, summary in enumerate(report.summaries[:22]):
            row = 3 + index
            selected = index == self.summary_row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ", fg=fg, bg=bg)
            values = (summary.name, summary.source, summary.summary_type,
                      summary.level, summary.ignore, summary.mode)
            for value, column in zip(values, columns):
                buffer.write(row, column, clip_text(value, 16), fg=fg, bg=bg,
                             bold=selected and column == 2)
        draw_status_line(buffer, self.theme,
                         self.status or "F2 add   ENTER options   F5 delete")
        draw_help_line(buffer, self.theme,
                       "F2 add summary   ENTER options   F5 delete   "
                       "F10 continue   ESC cancel")

    def _view_formatting(self, buffer: CellBuffer) -> None:
        assert self.report is not None
        title_bar(buffer, "Formatting Options", self.theme)
        headers = ("Section", "Field", "Data", "Len", "Just", "Fmt", "Dec",
                   "Window")
        columns = (2, 16, 54, 62, 67, 73, 79, 84)
        for header, column in zip(headers, columns):
            buffer.write(2, column, header, fg=self.theme.text,
                         bg=self.theme.bg, bold=True)
        for index, item in enumerate(self._format_rows()[:22]):
            row = 3 + index
            selected = index == self.format_row
            fg = self.theme.selected_fg if selected else self.theme.text
            bg = self.theme.selected_bg if selected else self.theme.bg
            if selected:
                buffer.fill_rect(row, 1, 1, SCREEN_WIDTH - 2, " ", fg=fg, bg=bg)
            values = (SECTION_TITLES.get(item.section, item.section),
                      item.source, item.data, str(item.length),
                      item.justification, item.format,
                      "" if item.decimals is None else str(item.decimals),
                      str(item.window))
            widths = (14, 38, 8, 5, 6, 6, 5, 8)
            for column, (value, x) in enumerate(zip(values, columns)):
                text = self.edit_text if selected and self.editing \
                    and column + 1 == self.format_col else value
                buffer.write(row, x, clip_text(text, widths[column]),
                             fg=fg, bg=bg,
                             underline=selected and self.editing
                             and column + 1 == self.format_col)
        draw_status_line(buffer, self.theme,
                         self.status or "TAB column   ENTER edit   F10 back")
        draw_help_line(buffer, self.theme,
                       "UP/DOWN field   TAB column   ENTER edit   "
                       "F10 back")

    @clipping_allowed  # il canvas di stampa può superare le 80 colonne
    def _view_layout(self, buffer: CellBuffer) -> None:
        report = self.report
        assert report is not None
        title_bar(buffer, f"{self.title}   {report.width} columns", self.theme)
        screen_row = CONTENT_TOP
        self.section_tops = {}
        for section in report.sections:
            if screen_row >= STATUS_ROW:
                break
            self.section_tops[section] = screen_row
            selected = section == self.section
            fg = self.theme.accent if not selected else self.theme.selected_fg
            bg = self.theme.bg if not selected else self.theme.selected_bg
            label = f" {SECTION_TITLES[section]} "
            buffer.write(screen_row, 0, label, fg=fg, bg=bg, bold=True)
            screen_row += 1
            height = report.section_height(section)
            for line in range(1, height + 1):
                if screen_row >= STATUS_ROW:
                    break
                for text in report.section_texts(section):
                    if text.row != line:
                        continue
                    buffer.write(screen_row, text.col - 1,
                                 clip_text(text.text,
                                           max(0, SCREEN_WIDTH - text.col + 1)),
                                 fg=self.theme.text, bg=self.theme.bg)
                for item in report.section_fields(section):
                    if item.row != line:
                        continue
                    width = max(1, item.window or item.length)
                    label = item.name or item.source.split(".")[-1]
                    placeholder = f"[{label}]"
                    if item.data == "Unique":
                        placeholder = f"[{label}:U]"
                    buffer.write(screen_row, item.col - 1,
                                 clip_text(placeholder, width),
                                 fg=self.theme.accent, bg=self.theme.bg,
                                 underline=True)
                screen_row += 1
        cursor_row = self.section_tops.get(self.section, CONTENT_TOP) + self.row
        buffer.write(cursor_row, self.col - 1, "_", fg=self.theme.selected_fg,
                     bg=self.theme.selected_bg, blink=True)
        draw_status_line(
            buffer, self.theme,
            self.status or f"{SECTION_TITLES[self.section]}  Row {self.row}  "
                           f"Col {self.col}  {report.group_count} group(s)")
        draw_help_line(
            buffer, self.theme,
            "F2 fields   F3 sections   F4 calc/summary   F9 line   "
            "F10 save   Alt-O format")
        draw_menu_line(buffer, self.theme, REPORT_KEYS)


@dataclass
class ReportPreview:
    output: ReportOutput
    title: str = "Report"
    theme: Theme = NEWPORT
    page: int = 0
    top: int = 0
    left: int = 0
    status: str = ""
    close: bool = False
    pdf_path: Path | None = None

    def handle(self, key: Key) -> None:
        self.status = ""
        name = key.name
        if name == "ESC":
            self.close = True
            return
        if name == "PGDN":
            self.page = min(len(self.output.pages) - 1, self.page + 1)
            self.top = 0
            return
        if name == "PGUP":
            self.page = max(0, self.page - 1)
            self.top = 0
            return
        if name == "DOWN":
            self.top += 1
            return
        if name == "UP":
            self.top = max(0, self.top - 1)
            return
        if name == "RIGHT":
            self.left += 1
            return
        if name == "LEFT":
            self.left = max(0, self.left - 1)
            return
        if name == "HOME":
            self.top = 0
            self.left = 0
            return
        if name == "END":
            page = self.output.pages[self.page]
            self.top = max(0, len(page.lines) - (SCREEN_HEIGHT - 6))
            return
        if name == "F10" or (character(key) or "").upper() == "P":
            self.write_pdf()
            return
        if name == "F1":
            return

    def write_pdf(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path is not None else self.pdf_path
        if target is None:
            target = Path("report.pdf")
        self.pdf_path = write_report_pdf(self.output, target, self.title)
        self.status = f"PDF written to {self.pdf_path}"
        return self.pdf_path

    def view(self) -> View:
        buffer = CellBuffer(SCREEN_WIDTH, SCREEN_HEIGHT,
                            Cell(fg=self.theme.text, bg=self.theme.bg))
        buffer.fill_rect(0, 0, SCREEN_HEIGHT, SCREEN_WIDTH, " ",
                         fg=self.theme.text, bg=self.theme.bg)
        total = len(self.output.pages)
        page = self.output.pages[self.page] if self.output.pages else None
        title_bar(buffer, f"{self.title} - Preview", self.theme)
        visible = STATUS_ROW - CONTENT_TOP
        lines = page.lines if page is not None else []
        for offset, line in enumerate(lines[self.top:self.top + visible]):
            text = line[self.left:self.left + SCREEN_WIDTH - 2]
            buffer.write(CONTENT_TOP + offset, 1, text, fg=self.theme.text,
                         bg=self.theme.bg)
        draw_status_line(
            buffer, self.theme,
            self.status or f"Page {self.page + 1} of {total}   "
                           f"Line {self.top + 1}   Col {self.left + 1}")
        draw_help_line(buffer, self.theme,
                       "PgUp/PgDn page   arrows scroll   P/F10 write PDF   "
                       "ESC return")
        draw_menu_line(buffer, self.theme,
                       [("F1", "Help"), ("PgUp/PgDn", "Page"),
                        ("Arrows", "Scroll"), ("F10", "PDF"), ("ESC", "Back")])
        return View(buffer, [])


def _yes(value: bool) -> str:
    return "Yes" if value else "No"


__all__ = ["ReportDesigner", "ReportPreview"]
