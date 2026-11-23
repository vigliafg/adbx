"""Form letter: modello, parser dei comandi e stampa (O8).

Una lettera è un testo con marcatori:

* `[CAMPO]`, `[DB->CAMPO]` con opzioni `.S/.L/.R/.C/.N`, `D` (cancella la
  riga se il campo è vuoto), formati numerici e data;
* `[{espressione}]` per un valore calcolato;
* `[?testo]` per un campo richiesto a stampa;
* `[.IF expr]`, `[.ELSEIF expr]`, `[.ELSE]`, `[.ENDIF]`;
* `[.WIDTH n]`, `[.LEFT n]`, `[.TOP n]`, `[.BOTTOM n]`, `[.FILL+]`,
  `[.FILL-]`, `[.EJECT]`, `[.INCLUDE file]`, `[@codici]`.

Il testo viene riscritto a capo alla larghezza corrente quando il fill mode
è attivo; i campi vuoti con `D` eliminano l'intera riga.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from .expressions import Context, ExprError, evaluate, key_text
from .fields import Field
from .indexing import ordered_sequences
from .report_engine import (
    ReportOutput,
    ReportPage,
    _attributes,
    format_report_value,
    prepare_expression,
)

LETTER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]{0,7}$")
MAX_LETTER_LINES = 10000
COMMAND_RE = re.compile(r"^\[\.([A-Za-z]+[+-]?)\s*(.*?)\]$")
MARKER_RE = re.compile(r"\[([^\[\]]+)\]")
INCLUDE_DEPTH = 10


class LetterError(ValueError):
    """Lettera non valida."""


@dataclass
class LetterDefinition:
    workspace: Any
    owner: str
    name: str = "LETTER"
    description: str = ""
    body: list[str] = field(default_factory=lambda: [""])
    updated: float = 0.0

    def __post_init__(self) -> None:
        self.owner = self.owner.strip().upper()
        self.name = self.name.strip().upper()
        if not LETTER_NAME_RE.match(self.name):
            raise LetterError(
                "Letter names have 1-8 letters, digits or underscores.")
        if not self.body:
            self.body = [""]

    @property
    def label(self) -> str:
        return f"{self.name} - {self.description}" if self.description \
            else self.name

    @property
    def text(self) -> str:
        return "\n".join(self.body)

    def validate(self) -> None:
        if self.workspace.get(self.owner) is None \
                and self.workspace.get_set(self.owner) is None:
            raise LetterError(f"Owner {self.owner} not found.")
        if not self.name:
            raise LetterError("A letter needs a name.")
        if len(self.body) > MAX_LETTER_LINES:
            raise LetterError("Letter is too long.")

    def save(self) -> None:
        self.validate()
        self.workspace.save_letter(self)

    def erase(self) -> None:
        self.workspace.delete_letter(self.owner, self.name)

    def to_dict(self) -> dict[str, Any]:
        return {"owner": self.owner, "name": self.name,
                "description": self.description, "body": list(self.body)}

    @classmethod
    def from_dict(cls, workspace, data: dict[str, Any]) -> "LetterDefinition":
        return cls(workspace, str(data.get("owner", "")),
                   str(data.get("name", "LETTER")),
                   str(data.get("description", "")),
                   list(data.get("body", [""])))


@dataclass
class LetterRow:
    seq: int
    sources: dict[str, dict[str, str]]
    primary: str

    def value(self, database: str, name: str) -> str:
        return self.sources.get(database, {}).get(name, "")


@dataclass
class _Options:
    justification: str = "S"
    delete_line: bool = False
    length: int | None = None
    decimals: int | None = None
    extended: bool = False
    currency: bool = False
    thousands: bool = False


def parse_options(text: str) -> _Options:
    options = _Options()
    text = (text or "").strip()
    if not text:
        return options
    head, _, tail = text.partition(":")
    for char in head.upper():
        if char in "SLRCN":
            options.justification = char
        elif char == "D":
            options.delete_line = True
        elif char == "X":
            options.extended = True
        elif char == "$":
            options.currency = True
        elif char == ",":
            options.thousands = True
        elif char.isdigit() and options.length is None:
            options.length = int(char)
    if tail:
        bits = tail.split(".")
        if bits[0].strip().isdigit():
            options.length = int(bits[0])
        if len(bits) > 1 and bits[1].strip().isdigit():
            options.decimals = int(bits[1])
    return options


class LetterEngine:
    def __init__(self, letter: LetterDefinition, workspace,
                 *, prompts: dict[str, str] | None = None,
                 today: date | None = None,
                 settings: Any | None = None) -> None:
        self.letter = letter
        self.workspace = workspace
        self.prompts = prompts or {}
        self.today = today or date.today()
        self.settings = settings
        self.width = 60
        self.left = 0
        self.top = 0
        self.bottom = 0
        self.fill = True
        self.page_length = 66
        self.rows: list[LetterRow] = []

    # -- dati ------------------------------------------------------------
    def build_rows(self) -> list[LetterRow]:
        database = self.workspace.get(self.letter.owner)
        rows: list[LetterRow] = []
        if database is not None:
            try:
                sequences = ordered_sequences(
                    database, self.settings or database.current_range)
            except Exception as exc:
                raise LetterError(str(exc)) from exc
            for seq in sequences:
                rows.append(LetterRow(seq, {database.name: database.read(seq)},
                                      database.name))
        else:
            definition = self.workspace.get_set(self.letter.owner)
            if definition is None:
                raise LetterError(f"Owner {self.letter.owner} not found.")
            primary = definition.primary_database
            for seq in definition.visible_parent_sequences(self.settings):
                values = primary.read(seq)
                sources: dict[str, dict[str, str]] = {primary.name: values}
                for link in definition.children_of(primary.name):
                    if link.one_to_many:
                        continue
                    linked = definition.linked_rows(link, values)
                    if linked:
                        sources[link.child] = linked[0][1]
                rows.append(LetterRow(seq, sources, primary.name))
        self.rows = rows
        return rows

    def _context(self, row: LetterRow) -> Context:
        values: dict[str, str] = {}
        for database in [row.primary] + [name for name in row.sources
                                         if name != row.primary]:
            for name, value in row.sources[database].items():
                values.setdefault(name, value)
        return Context(fields=tuple(self._fields(row)),
                       values=values, pattern=self.workspace.pattern_mode)

    def _fields(self, row: LetterRow) -> list[Field]:
        fields: list[Field] = []
        for database in row.sources.values():
            for name in database:
                try:
                    fields.append(Field(name, "C", 254))
                except Exception:
                    continue
        if not fields:
            fields = [Field("SENTINEL", "C", 1)]
        return fields

    # -- marcatori -------------------------------------------------------
    def _field_value(self, row: LetterRow, database: str, name: str,
                     options: _Options) -> str:
        if database == "SYSTEM":
            raw = (self.today.strftime("%Y%m%d") if name == "DATE"
                   else str(row.seq) if name == "REC_NUMBER" else "")
            definition = Field("DATE", "D", 8) if name == "DATE" else None
        elif database == "CALC":
            try:
                result = evaluate(prepare_expression(name),
                                  self._context(row))
            except ExprError:
                result = ""
            raw = key_text(result)
            definition = (Field("CALC", "N", 19, options.decimals or 0)
                          if isinstance(result, (int, float, Decimal))
                          else Field("CALC", "C", 254))
        else:
            raw = row.value(database, name)
            database_obj = self.workspace.get(database)
            try:
                definition = database_obj.field(name) if database_obj else None
            except KeyError:
                definition = None
        return self._format_value(raw, definition, options)

    def _format_value(self, raw: str, definition: Field | None,
                      options: _Options) -> str:
        fmt = ""
        if options.extended:
            fmt = "X$" if options.currency else "X"
        elif options.currency:
            fmt = "$"
        elif options.thousands:
            fmt = ","
        if definition is not None and definition.type == "D" and not fmt:
            fmt = "1"
        default_length = (10 if definition is not None
                          and definition.type == "D" else
                          definition.length if definition else max(1, len(raw)))
        if options.extended and options.length is None:
            length = 60
        else:
            length = options.length or default_length
        rendered = format_report_value(raw, definition, fmt, options.decimals,
                                       length, length, "N")
        text = rendered.lines[0] if rendered.lines else ""
        if options.justification == "R":
            text = text.rjust(length)
        elif options.justification == "C":
            text = text.center(length)
        elif options.justification == "L":
            text = text.ljust(length)
        else:
            text = text.rstrip()
        return text

    def _substitute(self, text: str, row: LetterRow) -> tuple[str, bool]:
        delete = False

        def replace(match: re.Match[str]) -> str:
            nonlocal delete
            inner = match.group(1)
            if inner.startswith("?"):
                prompt = inner[1:]
                return self.prompts.get(prompt, "")
            if inner.startswith("{"):
                end = inner.find("}")
                if end < 0:
                    expression, option_text = inner[1:], ""
                else:
                    expression = inner[1:end]
                    option_text = inner[end + 1:].lstrip(".")
                try:
                    result = evaluate(prepare_expression(expression),
                                      self._context(row))
                except ExprError:
                    return ""
                options = parse_options(option_text)
                numeric = isinstance(result, (int, float, Decimal))
                definition = (Field("CALC", "N", 19, options.decimals or 0)
                              if numeric else Field("CALC", "C", 254))
                return self._format_value(key_text(result), definition, options)
            if inner.startswith(".") or inner.startswith("@"):
                return ""
            field_part, _, option_text = inner.partition(".")
            if "->" in field_part:
                database, name = field_part.split("->", 1)
            elif "." in field_part:
                database, name = field_part.split(".", 1)
            else:
                database, name = row.primary, field_part
            options = parse_options(option_text)
            value = self._field_value(row, database.upper(), name.upper(),
                                      options)
            if options.delete_line and not value.strip():
                delete = True
            return value

        result = MARKER_RE.sub(replace, text)
        result = re.sub(r"\[@[^\]]*\]", "", result)
        return _attributes(result), delete

    # -- elaborazione ----------------------------------------------------
    def _expand_body(self, row: LetterRow,
                     lines: list[str] | None = None, depth: int = 0
                     ) -> list[str | None]:
        source = lines if lines is not None else self.letter.body
        output: list[str | None] = []
        frames: list[dict[str, Any]] = []
        paragraph: list[str] = []

        def active() -> bool:
            return all(frame["active"] for frame in frames)

        def flush() -> None:
            if not paragraph:
                return
            text = " ".join(part.strip() for part in paragraph if part.strip())
            paragraph.clear()
            if not text:
                output.append("")
                return
            output.extend(self._wrap(text))

        def process_content(text: str) -> None:
            substituted, delete = self._substitute(text, row)
            if delete:
                return
            if self.fill:
                if not substituted.strip():
                    flush()
                    output.append("")
                elif "[" in text:
                    flush()
                    output.extend(self._wrap(substituted))
                else:
                    paragraph.append(substituted)
            else:
                output.append(" " * self.left + substituted.rstrip())

        def handle(line: str) -> None:
            stripped = line.strip()
            command = COMMAND_RE.match(stripped)
            if command:
                name = command.group(1).upper()
                argument = command.group(2).strip()
                if name == "IF":
                    parent = active()
                    condition = parent and self._condition(argument, row)
                    frames.append({"parent": parent, "active": condition,
                                   "taken": condition})
                    flush()
                    return
                if name == "ELSEIF":
                    if frames:
                        frame = frames[-1]
                        condition = (frame["parent"] and not frame["taken"]
                                     and self._condition(argument, row))
                        frame["active"] = condition
                        frame["taken"] = frame["taken"] or condition
                    flush()
                    return
                if name == "ELSE":
                    if frames:
                        frame = frames[-1]
                        frame["active"] = frame["parent"] and not frame["taken"]
                        frame["taken"] = True
                    flush()
                    return
                if name == "ENDIF":
                    if frames:
                        frames.pop()
                    flush()
                    return
                if name == "WIDTH":
                    self.width = _clamp(argument, 10, 254, self.width)
                    flush()
                    return
                if name == "LEFT":
                    self.left = _clamp(argument, 0, 80, self.left)
                    flush()
                    return
                if name == "TOP":
                    self.top = _clamp(argument, 0, 40, self.top)
                    flush()
                    return
                if name == "BOTTOM":
                    self.bottom = _clamp(argument, 0, 40, self.bottom)
                    flush()
                    return
                if name == "FILL+" or name == "FILL-":
                    flush()
                    self.fill = name == "FILL+"
                    return
                if name == "EJECT":
                    flush()
                    output.append(None)
                    return
                if name == "INCLUDE":
                    flush()
                    if depth < INCLUDE_DEPTH:
                        path = Path(argument)
                        if not path.is_absolute():
                            path = Path(self.workspace.directory) / path
                        try:
                            included = path.read_text(
                                encoding="utf-8", errors="replace").splitlines()
                        except OSError:
                            included = []
                        output.extend(self._expand_body(row, included,
                                                        depth + 1))
                    return
                if name in ("IF", "ELSEIF", "ELSE", "ENDIF"):
                    return
                return
            if not active():
                return
            process_content(line)

        for line in source:
            if line.strip().startswith("[."):
                handle(line)
            elif active():
                process_content(line)
        flush()
        return output

    def _condition(self, expression: str, row: LetterRow) -> bool:
        try:
            value = evaluate(prepare_expression(expression),
                             self._context(row))
        except ExprError:
            return False
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        text = str(value).strip().upper()
        return text in ("1", "T", "TRUE", ".T.", "Y", "YES")

    def _wrap(self, text: str) -> list[str]:
        prefix = " " * self.left
        width = max(1, self.width - self.left)
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= width:
                current += " " + word
            else:
                lines.append(prefix + current)
                current = word
        lines.append(prefix + current)
        return lines

    # -- pagine ----------------------------------------------------------
    def render(self) -> ReportOutput:
        if not self.rows:
            self.build_rows()
        if not self.rows:
            return ReportOutput([ReportPage(1, [])], 0, self.width)
        all_pages: list[ReportPage] = []
        page_number = 1
        for row in self.rows:
            content = self._expand_body(row)
            page_lines: list[str] = []
            capacity = self.page_length - self.top - self.bottom
            started = False

            def new_page() -> None:
                nonlocal started
                if started or page_lines:
                    all_pages.append(ReportPage(page_number, list(page_lines)))
                page_lines.clear()
                page_lines.extend([""] * self.top)
                started = True

            new_page()
            for line in content:
                if line is None:
                    if page_lines and any(page_lines[self.top:]):
                        all_pages.append(ReportPage(page_number,
                                                    list(page_lines)))
                        page_number += 1
                    page_lines = [""] * self.top
                    started = True
                    continue
                if len(page_lines) >= capacity + self.top:
                    all_pages.append(ReportPage(page_number, list(page_lines)))
                    page_number += 1
                    page_lines = [""] * self.top
                page_lines.append(line)
            all_pages.append(ReportPage(page_number, list(page_lines)))
            page_number += 1
        width = max(self.width, max((len(line) for page in all_pages
                                     for line in page.lines), default=0))
        return ReportOutput(all_pages, len(self.rows), width)


def _clamp(text: str, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(text)))
    except (TypeError, ValueError):
        return default


def render_letters(letter: LetterDefinition, workspace, *,
                   prompts: dict[str, str] | None = None,
                   today: date | None = None,
                   settings: Any | None = None) -> ReportOutput:
    return LetterEngine(letter, workspace, prompts=prompts, today=today,
                        settings=settings).render()


__all__ = [
    "LETTER_NAME_RE",
    "LetterDefinition",
    "LetterEngine",
    "LetterError",
    "LetterRow",
    "parse_options",
    "render_letters",
]
