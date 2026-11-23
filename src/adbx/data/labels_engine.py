"""Motore di stampa delle etichette (O8).

Riusa le conversioni dei campi e i formati dei report, ma compone una griglia:
più etichette per riga, copie per record, righe vuote soppresse. Le
giustificazioni avanzate spostano il testo che segue (Suppress, Trim),
lasciano il testo ancorato (Float), seguono il campo (Join) o eliminano il
testo associato quando il campo è vuoto (Before, After).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from .expressions import Context, ExprError, evaluate, key_text
from .fields import Field
from .indexing import ordered_sequences
from .labels import LabelDefinition, LabelField, LabelText
from .report_engine import (
    CHR127,
    ReportOutput,
    ReportPage,
    _attributes,
    format_report_value,
    prepare_expression,
)


@dataclass
class LabelRow:
    seq: int
    sources: dict[str, dict[str, str]]
    primary: str

    def source(self, database: str, name: str) -> str:
        return self.sources.get(database, {}).get(name, "")


@dataclass
class _RenderedField:
    item: LabelField
    raw: str
    value: str
    delete_line: bool = False


class LabelEngine:
    def __init__(self, definition: LabelDefinition, workspace,
                 *, today: date | None = None,
                 settings: Any | None = None) -> None:
        self.definition = definition
        self.workspace = workspace
        self.today = today or date.today()
        self.settings = settings
        self.rows: list[LabelRow] = []

    def build_rows(self) -> list[LabelRow]:
        definition = self.definition
        database = self.workspace.get(definition.owner)
        rows: list[LabelRow] = []
        if database is not None:
            try:
                sequences = ordered_sequences(
                    database, self.settings or database.current_range)
            except Exception as exc:
                raise ValueError(str(exc)) from exc
            for seq in sequences:
                rows.append(LabelRow(seq, {database.name: database.read(seq)},
                                     database.name))
        else:
            set_definition = self.workspace.get_set(definition.owner)
            if set_definition is None:
                raise ValueError(f"Owner {definition.owner} not found.")
            primary = set_definition.primary_database
            for seq in set_definition.visible_parent_sequences(self.settings):
                values = primary.read(seq)
                sources: dict[str, dict[str, str]] = {primary.name: values}
                for link in set_definition.children_of(primary.name):
                    if link.one_to_many:
                        continue
                    linked = set_definition.linked_rows(link, values)
                    if linked:
                        sources[link.child] = linked[0][1]
                rows.append(LabelRow(seq, sources, primary.name))
        self.rows = rows
        return rows

    # -- valori ----------------------------------------------------------
    def _context(self, row: LabelRow) -> Context:
        values: dict[str, str] = {}
        for database in [row.primary] + [name for name in row.sources
                                         if name != row.primary]:
            for name, value in row.sources[database].items():
                values.setdefault(name, value)
        for calc in self.definition.calcs:
            try:
                result = evaluate(prepare_expression(calc.expression),
                                  Context(fields=self.definition.expression_fields(),
                                          values=dict(values)))
            except ExprError:
                result = ""
            values[calc.name] = key_text(result)
        return Context(fields=self.definition.expression_fields(),
                       values=values)

    def _raw(self, item: LabelField, row: LabelRow) -> str:
        database, name = item.database, item.name
        if database == "CALC":
            return self._context(row).values.get(name, "")
        if database == "SYSTEM":
            if name == "DATE":
                return self.today.strftime("%Y%m%d")
            if name == "TIME":
                return ""
            if name == "REC_NUMBER":
                return str(row.seq)
            if name == "CNTR_GRAND":
                return str(self._counter)
            if name in ("DB_NAME", "SET_NAME"):
                return self.definition.owner
            if name == "DB_DESC":
                owner = self.workspace.get(self.definition.owner)
                return getattr(owner, "description", "") if owner else ""
            if name == "SET_DESC":
                owner = self.workspace.get_set(self.definition.owner)
                return getattr(owner, "description", "") if owner else ""
            return ""
        return row.source(database, name)

    def _field(self, item: LabelField, row: LabelRow) -> _RenderedField:
        raw = self._raw(item, row)
        definition = self.definition.field_definition(item)
        if item.database == "CALC":
            numeric = (item.decimals is not None
                       or any(code in item.format.upper()
                              for code in ("$", ",", "X")))
            definition = (Field("CALC", "N", 19, item.decimals or 0)
                          if numeric else Field("CALC", "C", 254))
        elif item.database == "SYSTEM":
            definition = (Field("DATE", "D", 8)
                          if item.name == "DATE" else Field("SYSTEM", "C", 254))
        rendered = format_report_value(
            raw, definition, item.format, item.decimals, item.length,
            item.length, "N")
        value = rendered.lines[0] if rendered.lines else ""
        delete_line = (item.delete_line_if_empty and not raw.strip())
        return _RenderedField(item, raw, value, delete_line)

    # -- etichetta -------------------------------------------------------
    def render_label(self, row: LabelRow, counter: int = 1) -> list[str]:
        self._counter = counter
        definition = self.definition
        fields: dict[int, list[_RenderedField]] = {}
        texts: dict[int, list[LabelText]] = {}
        skips: set[int] = set()
        for item in definition.texts:
            texts.setdefault(item.row, []).append(item)
        for item in definition.fields:
            rendered = self._field(item, row)
            fields.setdefault(item.row, []).append(rendered)
            if item.justification == "Before" and not rendered.raw.strip():
                candidates = [text for text in texts.get(item.row, [])
                              if text.col + len(text.text) <= item.col]
                if candidates:
                    skips.add(id(max(candidates, key=lambda text: text.col)))
            if item.justification == "After" and not rendered.raw.strip():
                candidates = [text for text in texts.get(item.row, [])
                              if text.col >= item.col + max(1, item.length)]
                if candidates:
                    skips.add(id(min(candidates, key=lambda text: text.col)))
        lines: list[str] = []
        for row_index in range(1, definition.height + 1):
            line = self._render_line(row_index, texts.get(row_index, []),
                                     fields.get(row_index, []), skips)
            if line is not None:
                lines.append(line)
        return lines

    def _render_line(self, row: int, texts: list[LabelText],
                     fields: list[_RenderedField],
                     skips: set[int]) -> str | None:
        cells = [" "] * self.definition.width
        carry = 0
        forced = False
        items: list[tuple[int, int, Any]] = []
        for text in texts:
            if id(text) in skips:
                continue
            items.append((text.col, 0, text))
        for rendered in fields:
            items.append((rendered.item.col, 1, rendered))
        items.sort(key=lambda entry: (entry[0], entry[1]))
        for _col, kind, value in items:
            if kind == 0:
                text = _attributes(value.text)
                if CHR127 in value.text:
                    forced = True
                    text = text.replace(CHR127, " ")
                position = max(0, value.col - 1 - carry)
                self._put(cells, position, text)
                continue
            rendered: _RenderedField = value
            item = rendered.item
            if rendered.delete_line:
                return None
            text = rendered.value
            if CHR127 in text:
                forced = True
                text = text.replace(CHR127, " ")
            if item.justification in ("Suppress", "Before", "After"):
                trimmed = text.rstrip()
                position = max(0, item.col - 1 - carry)
                self._put(cells, position, trimmed)
                carry += max(0, item.length - len(trimmed))
            elif item.justification == "Trim":
                trimmed = text.rstrip()
                self._put(cells, item.col - 1, trimmed)
                carry = max(0, item.length - len(trimmed))
            elif item.justification == "Float":
                padded = text.ljust(item.length)
                self._put(cells, max(0, item.col - 1 - carry), padded)
                carry = 0
            elif item.justification == "Join":
                padded = text.ljust(item.length)
                self._put(cells, max(0, item.col - 1 - carry), padded)
            elif item.justification == "Right":
                self._put(cells, max(0, item.col - 1 - carry),
                          text.rjust(item.length))
            elif item.justification == "Center":
                self._put(cells, max(0, item.col - 1 - carry),
                          text.center(item.length))
            elif item.justification == "Left":
                self._put(cells, max(0, item.col - 1 - carry),
                          text.ljust(item.length))
            else:
                self._put(cells, max(0, item.col - 1 - carry), text)
        line = "".join(cells).rstrip()
        if not line and not forced:
            return None
        return line

    def _put(self, cells: list[str], start: int, text: str) -> None:
        for offset, char in enumerate(text):
            col = start + offset
            if 0 <= col < len(cells):
                cells[col] = char

    # -- copie e pagine --------------------------------------------------
    def copies_for(self, row: LabelRow) -> int:
        text = self.definition.copies.strip()
        if not text:
            return 1
        if text.isdigit():
            return max(0, int(text))
        try:
            context = self._context(row)
            if text.upper() in context.values:
                value = context.values[text.upper()]
                return max(0, int(Decimal(value or "1")))
            result = evaluate(prepare_expression(text), context)
            return max(0, int(Decimal(result or 0)))
        except (ExprError, ValueError, ArithmeticError):
            return 1

    def render(self) -> ReportOutput:
        if not self.rows:
            self.build_rows()
        blocks: list[list[str]] = []
        for index, row in enumerate(self.rows, 1):
            block = self.render_label(row, index)
            for _copy in range(self.copies_for(row)):
                blocks.append(block)
        definition = self.definition
        columns = definition.across
        if not blocks:
            blocks = [[]]
        grid: list[list[list[str]]] = []
        for index in range(0, len(blocks), columns):
            grid.append(blocks[index:index + columns])
        lines: list[str] = []
        for grid_row in grid:
            height = max((len(block) for block in grid_row), default=0)
            for line_index in range(height):
                parts: list[str] = []
                for block in grid_row:
                    text = block[line_index] if line_index < len(block) else ""
                    parts.append(text.ljust(definition.width))
                line = " " * definition.left_margin
                line += (" " * definition.columns_between).join(parts)
                lines.append(line.rstrip())
            lines.extend([""] * definition.lines_between)
        if lines and lines[-1] == "":
            lines.pop()
        width = (definition.left_margin + definition.width * definition.across
                 + definition.columns_between * (definition.across - 1))
        if definition.continuous_feed:
            pages = [ReportPage(1, lines)]
        else:
            rows_per_page = definition.rows_per_page
            per_page = rows_per_page * (definition.height
                                        + definition.lines_between)
            pages = []
            start = 0
            number = 1
            while start < len(lines) or not pages:
                chunk = lines[start:start + max(1, per_page)]
                pages.append(ReportPage(
                    number, [""] * definition.top_margin + chunk))
                start += max(1, per_page)
                number += 1
        return ReportOutput(pages, len(self.rows), max(width, 1))


def render_labels(definition: LabelDefinition, workspace, *,
                  today: date | None = None, settings: Any | None = None
                  ) -> ReportOutput:
    return LabelEngine(definition, workspace, today=today,
                       settings=settings).render()


__all__ = ["LabelEngine", "LabelRow", "render_labels"]
