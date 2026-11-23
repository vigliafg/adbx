"""Motore di stampa dei report (O7).

Il motore trasforma una `ReportDefinition` in pagine di testo. Le sezioni
seguono il manuale: report header, page header, titles, group header/footer,
detail, page footer e summary. I valori possono essere campi reali,
calcolati o summary; i summary hanno tipo (First/Last/Count/Biggest/
Smallest/Total/Average), livello (Grand/Page/Group n), ignore
(None/Empty/Zero/Both) e modo (Running/Pre-processed).

Il calcolo è iterativo: i calcoli possono usare summary e i summary possono
aggregare calcoli. Il motore ripete calcolo, raggruppamento, paginazione e
summary finché le pagine assegnate ai record non si stabilizzano (al massimo
quattro passate), come il multipass del manuale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .expressions import Context, ExprError, evaluate, key_text
from .fields import Field
from .indexing import ordered_sequences
from .reports import (
    ReportDefinition,
    ReportField,
    ReportSummary,
    ReportText,
)

DEFAULT_CURRENCY = "Dollars"
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
MONTHS_SHORT = tuple(month[:3] for month in MONTHS)
ONES = ("", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen")
TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety")


class ReportEngineError(ValueError):
    """Report non stampabile."""


@dataclass
class ReportPage:
    number: int
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass
class ReportOutput:
    pages: list[ReportPage]
    rows: int = 0
    width: int = 80

    @property
    def text(self) -> str:
        return "\n\f\n".join(page.text for page in self.pages)

    def to_text(self, separator: str = "\f") -> str:
        return separator.join(page.text for page in self.pages)


@dataclass
class ReportRow:
    seq: int
    sources: dict[str, dict[str, str]]
    primary: str
    calc: dict[str, str] = field(default_factory=dict)
    group_keys: list[str] = field(default_factory=list)
    group_instances: dict[int, int] = field(default_factory=dict)
    page: int = 1

    def source(self, database: str, name: str) -> str:
        return self.sources.get(database, {}).get(name, "")


@dataclass
class _Rendered:
    lines: list[str]
    suppress: bool = False


@dataclass
class _Aggregate:
    summary: ReportSummary
    count: int = 0
    total: Decimal = Decimal(0)
    first: str = ""
    last: str = ""
    has_first: bool = False
    biggest: Decimal | None = None
    smallest: Decimal | None = None

    def add(self, raw: str) -> None:
        if not self._keep(raw):
            return
        self.count += 1
        if not self.has_first:
            self.first = raw
            self.has_first = True
        self.last = raw
        number = _decimal(raw)
        if number is not None:
            self.total += number
            if self.biggest is None or number > self.biggest:
                self.biggest = number
            if self.smallest is None or number < self.smallest:
                self.smallest = number

    def _keep(self, raw: str) -> bool:
        ignore = self.summary.ignore
        if ignore in ("Empty", "Both") and not raw.strip():
            return False
        if ignore in ("Zero", "Both"):
            number = _decimal(raw)
            if number is not None and number == 0:
                return False
        return True

    def value(self) -> str:
        kind = self.summary.summary_type
        if kind == "Count":
            return str(self.count)
        if kind == "First":
            return self.first
        if kind == "Last":
            return self.last
        if kind == "Biggest":
            return _decimal_text(self.biggest) if self.biggest is not None else ""
        if kind == "Smallest":
            return _decimal_text(self.smallest) if self.smallest is not None else ""
        if kind == "Average":
            if not self.count:
                return ""
            return _decimal_text(self.total / self.count)
        return _decimal_text(self.total)


def prepare_expression(text: str) -> str:
    """Rende compatibili `SUMMARY->X`, `CALC->X` e `DB->FIELD` col parser."""
    return re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*->", "", text or "")


class ReportEngine:
    def __init__(self, report: ReportDefinition, workspace,
                 *, today: date | None = None,
                 settings: Any | None = None) -> None:
        self.report = report
        self.workspace = workspace
        self.today = today or date.today()
        self.now = datetime.now()
        self.settings = settings
        self.rows: list[ReportRow] = []
        self._group_names: list[str] = []
        self._detail_link = None

    # -- dati ------------------------------------------------------------
    def build_rows(self) -> list[ReportRow]:
        report = self.report
        database = self.workspace.get(report.owner)
        rows: list[ReportRow] = []
        if database is not None:
            try:
                sequences = ordered_sequences(
                    database, self.settings or database.current_range)
            except Exception as exc:  # IndexError_ e range non validi
                raise ReportEngineError(str(exc)) from exc
            for seq in sequences:
                values = database.read(seq)
                rows.append(ReportRow(seq, {database.name: values},
                                      database.name))
            self.rows = rows
            return rows

        definition = self.workspace.get_set(report.owner)
        if definition is None:
            raise ReportEngineError(f"Owner {report.owner} not found.")
        primary = definition.primary_database
        try:
            sequences = definition.visible_parent_sequences(self.settings)
        except Exception as exc:
            raise ReportEngineError(str(exc)) from exc
        detail_link = next((link for link in
                            definition.children_of(definition.primary)
                            if link.one_to_many), None)
        self._detail_link = detail_link
        for seq in sequences:
            parent_values = primary.read(seq)
            sources: dict[str, dict[str, str]] = {primary.name: parent_values}
            for link in definition.children_of(definition.primary):
                if link.one_to_many:
                    continue
                linked = definition.linked_rows(link, parent_values)
                if linked:
                    sources[link.child] = linked[0][1]
            if detail_link is None:
                rows.append(ReportRow(seq, sources, primary.name))
                continue
            detail_rows = definition.linked_rows(detail_link, parent_values)
            if not detail_rows:
                rows.append(ReportRow(seq, sources, primary.name))
                continue
            for child_seq, child_values in detail_rows:
                child_sources = dict(sources)
                child_sources[detail_link.child] = child_values
                rows.append(ReportRow(child_seq, child_sources,
                                      primary.name))
        self.rows = rows
        return rows

    # -- calcoli ---------------------------------------------------------
    def _calc_context(self, row: ReportRow,
                      summary_values: dict[tuple, str]) -> Context:
        values: dict[str, str] = {}
        for database in [row.primary] + [name for name in row.sources
                                         if name != row.primary]:
            for name, value in row.sources.get(database, {}).items():
                values.setdefault(name, value)
        for calc in self.report.calcs:
            values[calc.name] = row.calc.get(calc.name, "")
        for summary in self.report.summaries:
            values[summary.name] = summary_values.get(
                self._scope_for(summary, row), "")
        return Context(fields=self.report.expression_fields(), values=values,
                       pattern=self.workspace.pattern_mode)

    def _scope_for(self, summary: ReportSummary, row: ReportRow
                   ) -> tuple:
        if summary.level == "Grand":
            return ("grand",)
        if summary.level == "Page":
            return ("page", row.page)
        level = int(summary.level.split()[1])
        return ("group", level, row.group_instances.get(level, 0))

    def _compute_calcs(self, summary_values: dict[tuple, str]) -> None:
        for row in self.rows:
            for calc in self.report.calcs:
                try:
                    result = evaluate(prepare_expression(calc.expression),
                                      self._calc_context(row, summary_values))
                except ExprError:
                    result = ""
                row.calc[calc.name] = key_text(result)

    def _break_value(self, row: ReportRow, source: str) -> str:
        source = source.strip().upper()
        database, name = (source.split(".", 1) if "." in source
                          else (self.report.owner, source))
        if database == "CALC":
            return row.calc.get(name, "")
        return row.source(database, name)

    def _assign_groups(self) -> None:
        for row in self.rows:
            keys: list[str] = []
            for group in self.report.groups:
                value = self._break_value(row, group.break_field)
                keys.append(value if group.case_sensitive else value.upper())
            row.group_keys = keys

    def _assign_group_instances(self) -> None:
        """Assegna un id stabile per ogni prefisso di chiavi di gruppo."""
        names: dict[tuple, int] = {}
        for row in self.rows:
            for level in range(1, self.report.group_count + 1):
                prefix = tuple(row.group_keys[:level])
                if prefix not in names:
                    names[prefix] = len(names) + 1
                row.group_instances[level] = names[prefix]

    def _group_rows(self) -> dict[tuple[int, int], list[ReportRow]]:
        result: dict[tuple[int, int], list[ReportRow]] = {}
        for row in self.rows:
            for level in range(1, self.report.group_count + 1):
                key = (level, row.group_instances[level])
                result.setdefault(key, []).append(row)
        return result

    def _page_rows(self) -> dict[int, list[ReportRow]]:
        result: dict[int, list[ReportRow]] = {}
        for row in self.rows:
            result.setdefault(row.page, []).append(row)
        return result

    def _source_value(self, row: ReportRow, source: str) -> str:
        source = source.strip().upper()
        database, name = (source.split(".", 1) if "." in source
                          else (self.report.owner, source))
        if database == "CALC":
            return row.calc.get(name, "")
        return row.source(database, name)

    def _compute_summaries(self) -> dict[tuple, str]:
        values: dict[tuple, str] = {}
        row_groups = self._group_rows()
        page_groups = self._page_rows()
        for summary in self.report.summaries:
            if summary.level == "Grand":
                scopes = [(("grand",), self.rows)]
            elif summary.level == "Page":
                scopes = [(("page", page), rows)
                          for page, rows in page_groups.items()]
            else:
                level = int(summary.level.split()[1])
                scopes = [(("group", level, instance), rows)
                          for (group_level, instance), rows in row_groups.items()
                          if group_level == level]
            for scope, rows in scopes:
                aggregate = _Aggregate(summary)
                for row in rows:
                    aggregate.add(self._source_value(row, summary.source))
                values[scope] = aggregate.value()
        return values

    # -- stampa ----------------------------------------------------------
    def render(self) -> ReportOutput:
        if not self.rows:
            self.build_rows()
        summary_values: dict[tuple, str] = {}
        previous_pages: dict[int, int] = {}
        layout: _Layout | None = None
        for _pass in range(4):
            self._compute_calcs(summary_values)
            self._assign_groups()
            self._assign_group_instances()
            layout = _Layout(self, summary_values)
            layout.run()
            pages = {index: row.page for index, row in enumerate(self.rows)}
            if pages == previous_pages:
                break
            previous_pages = pages
            summary_values = self._compute_summaries()
        assert layout is not None
        if not layout.pages:
            layout.pages.append(ReportPage(1, []))
        return ReportOutput(layout.pages, len(self.rows), self.report.width)


class _Layout:
    def __init__(self, engine: ReportEngine,
                 summary_values: dict[tuple, str]) -> None:
        self.engine = engine
        self.report = engine.report
        self.summary_values = summary_values
        self.width = self.report.width
        self.pages: list[ReportPage] = []
        self.lines: list[str] = []
        self.page_number = 1
        self.open_instances: dict[int, int] = {}
        self.group_first: dict[int, ReportRow] = {}
        self.running: dict[tuple, _Aggregate] = {}
        self.unique_previous: dict[str, str] = {}
        self.grand_count = 0
        self.page_count = 0
        self.group_count: dict[int, int] = {}
        self.detail_on_page = 0
        self.records_done = 0

    # -- pagina ----------------------------------------------------------
    @property
    def capacity(self) -> int:
        length = self.report.page_length
        return max(1, length - self.report.top_margin)

    def _page_full(self) -> bool:
        return self.report.page_breaks and len(self.lines) >= self.capacity

    def _start_page(self) -> None:
        self.lines = []
        if self.report.top_margin:
            self.lines.extend([""] * self.report.top_margin)
        self.page_count = 0
        report = self.report
        if self.page_number == 1 and "report_header" in report.sections:
            self._emit_section("report_header")
        elif "page_header" in report.sections:
            self._emit_section("page_header")
        if "titles" in report.sections:
            if self.page_number == 1 or not report.print_titles_first_page_only:
                self._emit_section("titles")
        self._reset_scope(("page", self.page_number))

    def _finish_page(self) -> None:
        if not self.lines and not self.pages:
            return
        report = self.report
        if getattr(self, "skip_page_footer", False):
            self.skip_page_footer = False
        elif "page_footer" in report.sections:
            if not (report.print_footer_odd_pages_only
                    and self.page_number % 2 == 0):
                self._emit_section("page_footer")
        self.pages.append(ReportPage(self.page_number, list(self.lines)))
        self.page_number += 1
        self.detail_on_page = 0

    def _new_page(self, *, reprint_group: bool = False) -> None:
        self._finish_page()
        self._start_page()
        if reprint_group and self.report.reprint_group_header:
            for level in range(1, self.report.group_count + 1):
                if level in self.open_instances:
                    header = f"group{level}_header"
                    if header in self.report.sections:
                        self._emit_section(header,
                                           self.group_first.get(level), level)

    def _ensure(self, needed: int, *, reprint_group: bool = False) -> None:
        if not self.report.page_breaks:
            return
        if self.lines and len(self.lines) + needed > self.capacity:
            self._new_page(reprint_group=reprint_group)

    def _emit(self, lines: list[str]) -> None:
        self.lines.extend(lines)

    # -- sezioni ---------------------------------------------------------
    def _emit_section(self, section: str, row: ReportRow | None = None,
                      _group_level: int | None = None) -> None:
        lines = self._render_section(section, row, _group_level)
        self._emit(lines)

    def _render_section(self, section: str, row: ReportRow | None,
                        group_level: int | None) -> list[str]:
        report = self.report
        height = report.section_height(section)
        cells = [[" "] * self.width for _ in range(height)]
        suppressed = [False] * height
        forced = [False] * height

        for text in report.section_texts(section):
            self._place_text(cells, forced, text)
        for item in report.section_fields(section):
            rendered = self._render_field(item, row, section, group_level,
                                          force_text=False)
            if rendered.suppress:
                for offset in range(max(1, len(rendered.lines))):
                    index = item.row - 1 + offset
                    if 0 <= index < height:
                        suppressed[index] = True
            for offset, text in enumerate(rendered.lines):
                index = item.row - 1 + offset
                while index >= len(cells):
                    cells.append([" "] * self.width)
                    suppressed.append(False)
                    forced.append(False)
                    height += 1
                if index < 0:
                    continue
                self._place_value(cells[index], item, text, index)
                if CHR127 in text:
                    forced[index] = True
        lines: list[str] = []
        for index in range(len(cells)):
            text = "".join(cells[index]).replace(CHR127, " ")
            blank = not text.strip()
            if suppressed[index]:
                lines.append("")
            elif report.suppress_blank_lines and blank and not forced[index]:
                continue
            else:
                lines.append(text.rstrip())
        return lines

    def _place_text(self, cells: list[list[str]], forced: list[bool],
                    text: ReportText) -> None:
        value = _attributes(text.text)
        row = text.row - 1
        if not 0 <= row < len(cells):
            return
        if CHR127 in text.text:
            forced[row] = True
            value = value.replace(CHR127, " ")
        for offset, char in enumerate(value):
            col = text.col - 1 + offset
            if 0 <= col < self.width:
                cells[row][col] = char

    def _place_value(self, line: list[str], item: ReportField, text: str,
                     index: int) -> None:
        value = _attributes(text)
        col = item.col - 1
        for offset, char in enumerate(value):
            if 0 <= col + offset < self.width:
                line[col + offset] = char

    # -- campi -----------------------------------------------------------
    def _raw(self, item: ReportField, row: ReportRow | None) -> str:
        source = item.source.strip().upper()
        database, name = (source.split(".", 1) if "." in source
                          else (self.report.owner, source))
        if database == "SYSTEM":
            return self._system_value(name, row)
        if database == "CALC":
            return row.calc.get(name, "") if row is not None else ""
        if database == "SUMMARY":
            return self._summary_value(name, row)
        if item.data == "Unique" and row is not None:
            value = row.source(database, name)
            previous = self.unique_previous.get(source, "")
            self.unique_previous[source] = value
            if value == previous:
                return ""
            return value
        return row.source(database, name) if row is not None else ""

    def _system_value(self, name: str, row: ReportRow | None) -> str:
        if name == "DATE":
            return self.engine.today.strftime("%Y%m%d")
        if name == "TIME":
            return self.engine.now.strftime("%H:%M:%S")
        if name == "PAGENUMBER":
            return str(self.page_number)
        if name == "REC_NUMBER":
            return str(row.seq) if row is not None else ""
        if name == "CNTR_GRAND":
            return str(self.grand_count)
        if name == "CNTR_PAGE":
            return str(self.page_count)
        if name.startswith("CNTR_GRP"):
            level = int(name[len("CNTR_GRP"):] or 1)
            return str(self.group_count.get(level, 0))
        return ""

    def _summary_value(self, name: str, row: ReportRow | None) -> str:
        summary = next((item for item in self.report.summaries
                        if item.name == name), None)
        if summary is None:
            return ""
        if summary.mode == "Pre-processed":
            scope = self._summary_scope(summary, row)
            return self.summary_values.get(scope, "")
        scope = self._summary_scope(summary, row) + (summary.name,)
        aggregate = self.running.get(scope)
        return aggregate.value() if aggregate is not None else ""

    def _summary_scope(self, summary: ReportSummary,
                       row: ReportRow | None) -> tuple:
        if summary.level == "Grand":
            return ("grand",)
        if summary.level == "Page":
            return ("page", self.page_number)
        level = int(summary.level.split()[1])
        instance = self.open_instances.get(level)
        if instance is None and row is not None:
            instance = row.group_instances.get(level)
        return ("group", level, instance or 0)

    def _render_field(self, item: ReportField, row: ReportRow | None,
                      section: str, group_level: int | None,
                      *, force_text: bool = False) -> _Rendered:
        raw = self._raw(item, row)
        source = item.source.upper()
        if source.startswith("CALC."):
            numeric = (item.decimals is not None
                       or any(code in item.format.upper()
                              for code in ("$", ",", "X")))
            definition = (Field("CALC", "N", 19, item.decimals or 0)
                          if numeric else Field("CALC", "C", 254))
        elif source.startswith("SUMMARY."):
            decimals = 2
            summary = next((item for item in self.report.summaries
                            if f"SUMMARY.{item.name}" == source), None)
            if summary is not None:
                try:
                    _db, _name, source_field = self.report.resolve_summary_source(
                        summary.source)
                    if source_field is not None and source_field.type == "N":
                        decimals = source_field.decimals
                except Exception:
                    pass
            definition = Field("SUMMARY", "N", 19, decimals)
        elif source.startswith("SYSTEM.DATE"):
            definition = Field("DATE", "D", 8)
        elif source.startswith("SYSTEM."):
            name = source.split(".", 1)[1]
            definition = (Field("SYSTEM", "C", 12)
                          if name == "TIME" else Field("SYSTEM", "N", 12))
        else:
            definition = self.report.field_definition(item)
        return format_report_value(
            raw, definition, item.format, item.decimals, item.length,
            item.window, item.justification, data=item.data)

    # -- impaginazione ---------------------------------------------------
    def run(self) -> None:
        report = self.report
        if not report.page_breaks:
            self._start_page()
            self.unique_previous = {}
            for index, row in enumerate(self.engine.rows):
                self._emit_group_open(row, index)
                self._emit_detail(row, index)
            self._close_groups()
            self._emit_summary()
            self._finish_page()
            return
        self._start_page()
        for index, row in enumerate(self.engine.rows):
            self._emit_group_open(row, index)
            self._emit_detail(row, index)
        self._close_groups()
        self._emit_summary()
        self._finish_page()

    def _emit_group_open(self, row: ReportRow, index: int) -> None:
        report = self.report
        changed: list[int] = []
        for level in range(1, report.group_count + 1):
            instance = row.group_instances.get(level)
            if self.open_instances.get(level) != instance:
                changed.append(level)
                break
        if not changed:
            return
        level = changed[0]
        for close_level in range(report.group_count, level - 1, -1):
            if close_level in self.open_instances:
                self._close_group(close_level)
        group = report.group(level)
        assert group is not None
        if group.start_header_new_page:
            self._new_page()
            if report.reset_page_after_group:
                self.page_number = 1
                self._reset_scope(("page", 1))
        header = f"group{level}_header"
        if header in report.sections:
            if group.substitute_header and self.detail_on_page == 0:
                self._remove_page_header_from_current()
            self._ensure(report.section_height(header))
            if report.widow_count:
                needed = report.section_height(header)
                for offset in range(min(report.widow_count,
                                        len(self.engine.rows) - index)):
                    needed += report.section_height("detail")
                if self.lines and len(self.lines) + needed > self.capacity:
                    self._new_page()
            self.open_instances[level] = row.group_instances[level]
            self.group_first[level] = row
            self.group_count[level] = 0
            self._reset_scope(("group", level, row.group_instances[level]))
            self._emit_section(header, row, level)
            if group.reprint_titles and "titles" in report.sections:
                self._emit_section("titles", row)
        else:
            self.open_instances[level] = row.group_instances[level]
            self.group_first[level] = row
            self.group_count[level] = 0
            self._reset_scope(("group", level, row.group_instances[level]))

    def _close_group(self, level: int) -> None:
        report = self.report
        group = report.group(level)
        assert group is not None
        row = self.group_first.get(level)
        footer = f"group{level}_footer"
        if group.start_footer_new_page:
            self._new_page()
        elif footer in report.sections:
            if self.lines and len(self.lines) + report.section_height(footer) > self.capacity:
                self._new_page()
        if group.substitute_footer and footer in report.sections:
            target = max(0, self.capacity - report.section_height(footer))
            while self.lines and len(self.lines) < target:
                self.lines.append("")
            self._emit_section(footer, row, level)
            self.skip_page_footer = True
        elif footer in report.sections:
            self._emit_section(footer, row, level)
        self.open_instances.pop(level, None)
        self.group_first.pop(level, None)
        self.group_count.pop(level, None)

    def _remove_page_header_from_current(self) -> None:
        report = self.report
        if "page_header" not in report.sections or not self.lines:
            return
        height = report.section_height("page_header")
        offset = report.top_margin
        del self.lines[offset:offset + height]

    def _close_groups(self) -> None:
        for level in range(self.report.group_count, 0, -1):
            if level in self.open_instances:
                self._close_group(level)

    def _detail_lines(self, row: ReportRow) -> list[str]:
        return self._render_section("detail", row, None)

    def _emit_detail(self, row: ReportRow, index: int) -> None:
        report = self.report
        lines = self._detail_lines(row)
        if not lines:
            return
        if (report.max_records_page
                and self.detail_on_page >= report.max_records_page):
            self._new_page()
        remaining = self.capacity - len(self.lines)
        if (report.page_breaks and self.lines
                and remaining < len(lines)
                and (remaining < report.split_lines or remaining <= 0)):
            self._new_page(reprint_group=True)
            remaining = self.capacity
        row.page = self.page_number
        self.grand_count += 1
        self.page_count += 1
        self.records_done += 1
        for level in range(1, report.group_count + 1):
            if level in self.group_count:
                self.group_count[level] += 1
        self._update_running(row)
        while lines:
            if (not report.page_breaks
                    or len(self.lines) + len(lines) <= self.capacity):
                self._emit(lines)
                break
            remaining = self.capacity - len(self.lines)
            if remaining > 0 and remaining >= report.split_lines:
                self._emit(lines[:remaining])
                lines = lines[remaining:]
            self._new_page(reprint_group=True)
        self.detail_on_page += 1
        if (report.blank_line_after
                and self.records_done % report.blank_line_after == 0):
            if report.page_breaks and len(self.lines) >= self.capacity:
                self._new_page()
            self._emit([""])

    def _emit_summary(self) -> None:
        report = self.report
        if "summary" not in report.sections:
            return
        if report.summary_on_separate_page and self.lines:
            self._new_page()
        self._ensure(report.section_height("summary"))
        self._emit_section("summary", self.engine.rows[-1]
                           if self.engine.rows else None)
        self._update_output_pages()

    def _update_output_pages(self) -> None:
        return

    # -- summary running -------------------------------------------------
    def _update_running(self, row: ReportRow) -> None:
        for summary in self.report.summaries:
            if summary.mode != "Running":
                continue
            scope = self._summary_scope(summary, row) + (summary.name,)
            aggregate = self.running.get(scope)
            if aggregate is None:
                aggregate = _Aggregate(summary)
                self.running[scope] = aggregate
            aggregate.add(self.engine._source_value(row, summary.source))

    def _reset_scope(self, scope: tuple) -> None:
        for summary in self.report.summaries:
            if summary.mode == "Running":
                self.running[scope + (summary.name,)] = _Aggregate(summary)


CHR127 = chr(127)
_ATTRIBUTE_RE = re.compile(r"!([bBinNuUoO])")


def _attributes(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        code = match.group(1)
        return "  " if code.isupper() else ""

    return _ATTRIBUTE_RE.sub(replace, text or "")


def _decimal(text: str) -> Decimal | None:
    try:
        return Decimal((text or "").strip())
    except (InvalidOperation, ValueError):
        return None


def _decimal_text(number: Decimal | None) -> str:
    if number is None:
        return ""
    text = format(number.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _number_words(number: Decimal) -> str:
    negative = number < 0
    number = abs(number)
    whole = int(number)
    cents = int((number - whole) * 100 + Decimal("0.5"))
    if cents >= 100:
        whole += 1
        cents -= 100
    words = _spell_int(whole) or "zero"
    text = f"{words} and {cents:02d}/100"
    return ("minus " + text) if negative else text


def _spell_int(number: int) -> str:
    if number == 0:
        return ""
    scales = ((1_000_000_000_000, "trillion"),
              (1_000_000_000, "billion"),
              (1_000_000, "million"),
              (1_000, "thousand"))
    parts: list[str] = []
    remaining = number
    for value, name in scales:
        if remaining >= value:
            count = remaining // value
            remaining %= value
            parts.append(f"{_spell_int(count)} {name}")
    if remaining >= 100:
        hundreds = remaining // 100
        remaining %= 100
        parts.append(f"{ONES[hundreds]} hundred")
    if remaining >= 20:
        tens = remaining // 10
        ones = remaining % 10
        parts.append(TENS[tens] + (f" {ONES[ones]}" if ones else ""))
    elif remaining:
        parts.append(ONES[remaining])
    return " ".join(parts)


def _apply_case(text: str, codes: str) -> str:
    for code in codes.upper():
        if code == "C":
            text = text.upper()
        elif code == "L":
            text = text.lower()
        elif code == "F":
            text = text[:1].upper() + text[1:]
        elif code in ("W", "Z"):
            text = " ".join(word[:1].upper() + word[1:]
                            for word in text.split(" "))
        elif code == "Y":
            text = text[:1].upper() + text[1:].lower()
    return text


def _justify(text: str, width: int, mode: str) -> str:
    if mode == "R":
        return text.rjust(width)
    if mode == "C":
        return text.center(width)
    if mode == "N":
        return text
    return text.ljust(width)


def _wrap(text: str, width: int, word_wrap: bool) -> list[str]:
    if width <= 0:
        return [text]
    if not word_wrap:
        return [text[index:index + width]
                for index in range(0, len(text), width)] or [""]
    lines: list[str] = []
    remaining = text
    while len(remaining) > width:
        cut = remaining.rfind(" ", 0, width + 1)
        if cut <= 0:
            cut = width
        lines.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    lines.append(remaining)
    return lines or [""]


def _format_date(raw: str, fmt: str) -> str:
    if len(raw) < 8:
        return raw
    try:
        value = date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    except ValueError:
        return raw
    codes = fmt.upper()
    match = re.match(r"(\d+)", fmt)
    number = int(match.group(1)) if match else 1
    sep = "/"
    month = MONTHS[value.month - 1]
    month_short = MONTHS_SHORT[value.month - 1]
    day = value.day
    ordinal = "th" if 10 <= day % 100 <= 20 else {
        1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    patterns = {
        1: f"{value.month:02d}{sep}{day:02d}{sep}{value.year:04d}",
        2: f"{day:02d}{sep}{value.month:02d}{sep}{value.year:04d}",
        3: f"{month} {day:02d}, {value.year:04d}",
        4: f"{month} {day}, {value.year:04d}",
        5: f"{day:02d} {month_short} {value.year:04d}",
        6: f"{day:02d} {month} {value.year:04d}",
        7: f"{value.month:02d}{sep}{day:02d}{sep}{value.year % 100:02d}",
        8: f"{month} {day}{ordinal}, {value.year:04d}",
        9: f"{day:02d}{sep}{month_short}{sep}{value.year % 100:02d}",
        10: f"{day:02d} {month_short} {value.year:04d}",
    }
    text = patterns.get(number, patterns[1])
    return _apply_case(text, codes[1:] if codes[:1].isdigit() else codes)


def format_report_value(raw: str, definition: Field | None, fmt: str,
                        decimals: int | None, length: int, window: int,
                        justification: str, *, data: str = "Value"
                        ) -> _Rendered:
    """Applica le opzioni di formattazione e ritorna le righe da stampare."""
    fmt = (fmt or "").strip()
    codes = fmt.upper()
    numeric = bool(definition is not None and definition.type == "N")
    memo = bool(definition is not None and definition.is_memo)
    suppress = False

    if memo:
        text = raw or ""
        if "@" not in codes:
            text = text[:length] if length else text
        width = max(1, window or length or 50)
        lines = _wrap(text, width, "X" in codes or "@" in codes)
        if "-" in codes and not raw.strip():
            suppress = True
        return _Rendered(lines or [""], suppress)

    if numeric or (definition is None and _decimal(raw) is not None):
        number = _decimal(raw)
        places = decimals
        if places is None and definition is not None:
            places = definition.decimals
        places = 0 if places is None else places
        if number is None:
            text = ""
        elif "X" in codes:
            text = _number_words(number)
            if "$" in codes:
                text = f"{text} {DEFAULT_CURRENCY}"
            case_codes = "".join(code for code in codes if code in "CLFWYZ")
            text = _apply_case(text, case_codes) if case_codes else (
                text[:1].upper() + text[1:])
        else:
            if "$" in codes:
                body = f"{number:,.{places}f}"
                text = f"${body}"
            elif "," in codes:
                text = f"{number:,.{places}f}"
            else:
                text = f"{number:.{places}f}"
            if "B" in codes and number == 0:
                text = ""
        if "-" in codes and not raw.strip():
            suppress = True
        text = text[:length] if length else text
        width = max(1, window or length or len(text))
        if "*" in codes and text:
            text = text.rjust(width, "*")
        mode = justification or "R"
        lines = _wrap(text, width, False)
        lines = [_justify(line, width, mode) for line in lines]
        return _Rendered(lines, suppress)

    if definition is not None and definition.type == "D":
        text = _format_date(raw, fmt or "1")
        if "-" in codes and not raw.strip():
            suppress = True
        text = text[:length] if length else text
        width = max(1, window or length or len(text))
        lines = _wrap(text, width, False)
        lines = [_justify(line, width, justification or "L") for line in lines]
        return _Rendered(lines, suppress)

    text = raw or ""
    if "C" in codes:
        text = text.upper()
    elif "L" in codes:
        text = text.lower()
    elif "F" in codes:
        text = text[:1].upper() + text[1:]
    elif "W" in codes:
        text = " ".join(word[:1].upper() + word[1:] for word in text.split(" "))
    elif "Y" in codes:
        text = text[:1].upper() + text[1:].lower()
    elif "Z" in codes:
        text = " ".join(word[:1].upper() + word[1:].lower()
                        for word in text.split(" "))
    if "-" in codes and not raw.strip():
        suppress = True
    text = text[:length] if length else text
    width = max(1, window or length or len(text))
    lines = _wrap(text, width, "X" in codes)
    mode = justification or "L"
    lines = [_justify(line, width, mode) for line in lines]
    return _Rendered(lines, suppress)


def render_report(report: ReportDefinition, workspace, *,
                  today: date | None = None, settings: Any | None = None
                  ) -> ReportOutput:
    return ReportEngine(report, workspace, today=today,
                        settings=settings).render()


__all__ = [
    "DEFAULT_CURRENCY",
    "ReportEngine",
    "ReportEngineError",
    "ReportOutput",
    "ReportPage",
    "ReportRow",
    "format_report_value",
    "prepare_expression",
    "render_report",
]
