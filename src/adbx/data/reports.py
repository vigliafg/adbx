"""Report: modello dei layout di stampa (O7).

Un report appartiene a un database o a un set, ha una lettera A-Z e fino a
240 colonne. Il layout è diviso in sezioni (report header, page header,
titles, group header/footer, detail, page footer, summary); ogni sezione ha
testi e campi posizionati per riga e colonna. I campi possono essere reali,
calcolati o summary e usano le opzioni di formattazione del manuale.

La definizione vive nel workspace SQLite (`adbx_reports`), non in file
`.RPx`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .expressions import ExprError, parse_expression
from .fields import NAME_RE, Field, parse_value

REPORT_LETTERS = tuple(chr(code) for code in range(ord("A"), ord("Z") + 1))
MAX_REPORTS = len(REPORT_LETTERS)
MIN_WIDTH = 40
MAX_WIDTH = 240
MAX_GROUP_LEVELS = 9
MAX_PAGE_LINES = 99
MAX_CALCS = 128

SECTION_ORDER = (
    "report_header", "page_header", "titles",
    *[f"group{level}_header" for level in range(1, MAX_GROUP_LEVELS + 1)],
    "detail",
    *[f"group{level}_footer" for level in range(MAX_GROUP_LEVELS, 0, -1)],
    "page_footer", "summary",
)
SECTION_TITLES = {
    "report_header": "Report Header",
    "page_header": "Page Header",
    "titles": "Titles",
    "detail": "Detail",
    "page_footer": "Page Footer",
    "summary": "Summary",
    **{f"group{level}_header": f"Group {level} Header"
       for level in range(1, MAX_GROUP_LEVELS + 1)},
    **{f"group{level}_footer": f"Group {level} Footer"
       for level in range(1, MAX_GROUP_LEVELS + 1)},
}
DEFAULT_SECTIONS = ("page_header", "titles", "detail", "page_footer", "summary")

SUMMARY_TYPES = ("Value", "Unique", "First", "Last", "Count", "Biggest",
                 "Smallest", "Total", "Average")
SUMMARY_ONLY = SUMMARY_TYPES[2:]
SUMMARY_LEVELS = ("Grand", "Page") + tuple(
    f"Group {level}" for level in range(1, MAX_GROUP_LEVELS + 1))
IGNORE_OPTIONS = ("None", "Empty", "Zero", "Both")
SUMMARY_MODES = ("Running", "Pre-processed")
JUSTIFICATIONS = ("L", "R", "C", "N")


class ReportError(ValueError):
    """Report non valido."""


@dataclass
class ReportText:
    section: str = "titles"
    row: int = 1
    col: int = 1
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReportText":
        section = str(data.get("section", "titles"))
        if section not in SECTION_TITLES:
            section = "titles"
        return cls(section, max(1, int(data.get("row", 1))),
                   max(1, int(data.get("col", 1))),
                   str(data.get("text", "")))


@dataclass
class ReportField:
    section: str = "detail"
    row: int = 1
    col: int = 1
    source: str = ""          # DB.FIELD, CALC.NAME, SUMMARY.NAME, SYSTEM.X
    database: str = ""
    name: str = ""
    length: int = 0
    window: int = 0
    justification: str = ""
    format: str = ""
    decimals: int | None = None
    data: str = "Value"       # Value, Unique

    def __post_init__(self) -> None:
        self.database = self.database.strip().upper()
        self.name = self.name.strip().upper()
        self.source = (self.source or "").strip().upper()
        if not self.source and self.database and self.name:
            self.source = f"{self.database}.{self.name}"
        if self.source and (not self.database or not self.name):
            database, _, name = self.source.partition(".")
            if name:
                self.database = self.database or database
                self.name = self.name or name
            else:
                self.name = self.name or self.source
        if self.database and self.name and "." not in self.source:
            self.source = f"{self.database}.{self.name}"
        if self.section not in SECTION_TITLES:
            self.section = "detail"
        self.row = max(1, int(self.row))
        self.col = max(1, int(self.col))
        self.length = max(0, int(self.length))
        self.window = max(0, int(self.window or self.length))
        if self.window > self.length and self.length:
            self.window = self.length
        self.justification = (self.justification or "").upper()[:1]
        if self.justification not in JUSTIFICATIONS:
            self.justification = ""
        if self.data not in ("Value", "Unique"):
            self.data = "Value"
        if self.decimals is not None:
            self.decimals = max(0, min(14, int(self.decimals)))

    @property
    def multi_line(self) -> bool:
        return bool(self.window and self.length and self.window < self.length)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReportField":
        return cls(str(data.get("section", "detail")),
                   int(data.get("row", 1)), int(data.get("col", 1)),
                   str(data.get("source", "")),
                   str(data.get("database", "")),
                   str(data.get("name", "")),
                   int(data.get("length", 0)), int(data.get("window", 0)),
                   str(data.get("justification", "")),
                   str(data.get("format", "")),
                   data.get("decimals"),
                   str(data.get("data", "Value")))


@dataclass
class ReportCalc:
    name: str = "CALC1"
    expression: str = ""

    def __post_init__(self) -> None:
        self.name = self.name.strip().upper()
        if not NAME_RE.match(self.name):
            raise ReportError(
                "Calculated field names start with a letter, use A-Z 0-9 _ "
                "and are at most 10 characters.")
        if not self.expression.strip():
            raise ReportError(f"Calculated field {self.name} needs an expression.")

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReportCalc":
        return cls(str(data.get("name", "CALC1")),
                   str(data.get("expression", "")))


@dataclass
class ReportSummary:
    name: str = "SUMMARY1"
    source: str = ""
    summary_type: str = "Total"
    level: str = "Grand"
    ignore: str = "None"
    mode: str = "Running"

    def __post_init__(self) -> None:
        self.name = self.name.strip().upper()
        if not NAME_RE.match(self.name):
            raise ReportError(
                "Summary field names start with a letter, use A-Z 0-9 _ "
                "and are at most 10 characters.")
        if self.summary_type not in SUMMARY_ONLY:
            raise ReportError(f"Unknown summary type: {self.summary_type}")
        if self.level not in SUMMARY_LEVELS:
            raise ReportError(f"Unknown summary level: {self.level}")
        if self.ignore not in IGNORE_OPTIONS:
            raise ReportError(f"Unknown ignore option: {self.ignore}")
        if self.mode not in SUMMARY_MODES:
            raise ReportError(f"Unknown summary mode: {self.mode}")

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReportSummary":
        return cls(str(data.get("name", "SUMMARY1")),
                   str(data.get("source", "")),
                   str(data.get("summary_type", "Total")),
                   str(data.get("level", "Grand")),
                   str(data.get("ignore", "None")),
                   str(data.get("mode", "Running")))


@dataclass
class ReportGroup:
    level: int = 1
    break_field: str = ""
    reprint_titles: bool = False
    start_header_new_page: bool = False
    substitute_header: bool = False
    start_footer_new_page: bool = False
    substitute_footer: bool = False
    case_sensitive: bool = False

    def __post_init__(self) -> None:
        self.level = max(1, min(MAX_GROUP_LEVELS, int(self.level)))
        self.break_field = self.break_field.strip().upper()

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReportGroup":
        return cls(int(data.get("level", 1)),
                   str(data.get("break_field", "")),
                   bool(data.get("reprint_titles", False)),
                   bool(data.get("start_header_new_page", False)),
                   bool(data.get("substitute_header", False)),
                   bool(data.get("start_footer_new_page", False)),
                   bool(data.get("substitute_footer", False)),
                   bool(data.get("case_sensitive", False)))


@dataclass
class ReportDefinition:
    workspace: Any
    owner: str
    letter: str = "A"
    description: str = ""
    width: int = 80
    fields: list[ReportField] = field(default_factory=list)
    texts: list[ReportText] = field(default_factory=list)
    calcs: list[ReportCalc] = field(default_factory=list)
    summaries: list[ReportSummary] = field(default_factory=list)
    groups: list[ReportGroup] = field(default_factory=list)
    sections: list[str] = field(default_factory=lambda: list(DEFAULT_SECTIONS))
    section_lines: dict[str, int] = field(default_factory=dict)
    # page 1
    print_titles_first_page_only: bool = False
    print_footer_odd_pages_only: bool = False
    summary_on_separate_page: bool = False
    suppress_blank_lines: bool = True
    blank_line_after: int = 0
    page_breaks: bool = True
    widow_count: int = 0
    orphan_count: int = 0
    split_lines: int = 0
    max_records_page: int = 0
    reset_page_after_group: bool = False
    reprint_group_header: bool = False
    # page 2
    left_margin: int = 0
    top_margin: int = 0
    standard_page_length: bool = True
    page_length: int = 66
    updated: float = 0.0

    def __post_init__(self) -> None:
        self.owner = self.owner.strip().upper()
        self.letter = (self.letter or "A").strip().upper()[:1]
        if self.letter not in REPORT_LETTERS:
            raise ReportError("Report ids are letters A-Z.")
        self.width = max(MIN_WIDTH, min(MAX_WIDTH, int(self.width or 80)))
        self.groups = sorted(self.groups, key=lambda item: item.level)
        self.blank_line_after = max(0, min(100, int(self.blank_line_after)))
        self.widow_count = max(0, min(99, int(self.widow_count)))
        self.orphan_count = max(0, min(99, int(self.orphan_count)))
        self.split_lines = max(0, min(99, int(self.split_lines)))
        self.max_records_page = max(0, min(99, int(self.max_records_page)))
        self.left_margin = max(0, min(40, int(self.left_margin)))
        self.top_margin = max(0, min(40, int(self.top_margin)))
        self.page_length = max(10, min(MAX_PAGE_LINES, int(self.page_length)))
        self.sections = [name for name in SECTION_ORDER
                         if name in set(self.sections)] or list(DEFAULT_SECTIONS)
        for name in self._group_section_names():
            if name not in self.sections:
                self.sections.append(name)
        self.sections.sort(key=SECTION_ORDER.index)
        for name in self.sections:
            self.section_lines.setdefault(name, 1)
        self.section_lines = {name: max(1, min(200, int(lines)))
                              for name, lines in self.section_lines.items()
                              if name in self.sections}

    # -- gruppi ----------------------------------------------------------
    @property
    def group_count(self) -> int:
        return len(self.groups)

    def group(self, level: int) -> ReportGroup | None:
        for item in self.groups:
            if item.level == level:
                return item
        return None

    def set_group_count(self, count: int) -> None:
        count = max(0, min(MAX_GROUP_LEVELS, int(count)))
        while len(self.groups) > count:
            removed = self.groups.pop()
            for name in (f"group{removed.level}_header",
                         f"group{removed.level}_footer"):
                self.sections = [item for item in self.sections if item != name]
                self.section_lines.pop(name, None)
        while len(self.groups) < count:
            level = len(self.groups) + 1
            self.groups.append(ReportGroup(level))
            for name in (f"group{level}_header", f"group{level}_footer"):
                if name not in self.sections:
                    self.sections.append(name)
                    self.section_lines[name] = 1
        self.sections.sort(key=SECTION_ORDER.index)

    def _group_section_names(self) -> list[str]:
        names: list[str] = []
        for group in self.groups:
            names += [f"group{group.level}_header",
                      f"group{group.level}_footer"]
        return names

    # -- sezioni ---------------------------------------------------------
    def add_section(self, section: str) -> bool:
        if section not in SECTION_TITLES or section in self.sections:
            return False
        if section.startswith("group"):
            level = int(re.match(r"group(\d)_", section).group(1))  # type: ignore[union-attr]
            if level > self.group_count:
                return False
        self.sections.append(section)
        self.sections.sort(key=SECTION_ORDER.index)
        self.section_lines[section] = 1
        return True

    def remove_section(self, section: str) -> bool:
        if section not in self.sections:
            return False
        self.sections = [item for item in self.sections if item != section]
        self.section_lines.pop(section, None)
        self.fields = [item for item in self.fields if item.section != section]
        self.texts = [item for item in self.texts if item.section != section]
        return True

    def section_height(self, section: str) -> int:
        height = self.section_lines.get(section, 1 if section in self.sections
                                        else 0)
        for item in self.fields:
            if item.section == section:
                extra = max(1, self.field_lines(item))
                height = max(height, item.row + extra - 1)
        for text in self.texts:
            if text.section == section:
                height = max(height, text.row)
        return height

    def field_lines(self, item: ReportField) -> int:
        if item.window and item.length and item.window < item.length:
            return (item.length + item.window - 1) // item.window
        return 1

    def section_fields(self, section: str) -> list[ReportField]:
        return [item for item in self.fields if item.section == section]

    def section_texts(self, section: str) -> list[ReportText]:
        return [item for item in self.texts if item.section == section]

    # -- riferimenti -----------------------------------------------------
    def _owner_databases(self) -> dict[str, Any]:
        database = self.workspace.get(self.owner)
        if database is not None:
            return {database.name: database}
        definition = self.workspace.get_set(self.owner)
        if definition is None:
            raise ReportError(f"Owner {self.owner} not found.")
        return {name: definition.database(name)
                for name in definition.database_names()}

    def owner_databases(self) -> dict[str, Any]:
        return self._owner_databases()

    def field_definition(self, item: ReportField) -> Field | None:
        database = item.database
        if database in ("CALC", "SUMMARY", "SYSTEM"):
            return None
        try:
            return self._owner_databases()[database].field(item.name)
        except (KeyError, ReportError):
            return None

    def resolve_source(self, source: str) -> tuple[str, str, Field | None]:
        """Divide `DB.FIELD` e ritorna (database, nome, definizione)."""
        source = (source or "").strip().upper()
        if "." in source:
            database, name = source.split(".", 1)
        else:
            database, name = self.owner, source
        if database in ("CALC", "SUMMARY", "SYSTEM"):
            return database, name, None
        databases = self._owner_databases()
        if database not in databases:
            raise ReportError(f"Database {database} is outside the report owner.")
        return database, name, databases[database].field(name)

    # -- validazione -----------------------------------------------------
    def validate(self) -> None:
        if len(self.groups) > MAX_GROUP_LEVELS:
            raise ReportError(f"A report has at most {MAX_GROUP_LEVELS} groups.")
        levels = [group.level for group in self.groups]
        if levels != list(range(1, len(levels) + 1)):
            raise ReportError("Group levels must be 1..n without gaps.")
        for item in self.fields:
            if item.section not in self.sections:
                raise ReportError(
                    f"Field {item.source} is on a missing section.")
        for text in self.texts:
            if text.section not in self.sections:
                raise ReportError("Text is on a missing section.")
        calc_names = set()
        if len(self.calcs) > MAX_CALCS:
            raise ReportError(f"A report has at most {MAX_CALCS} calculated fields.")
        for calc in self.calcs:
            if calc.name in calc_names:
                raise ReportError(f"Duplicate calculated field {calc.name}.")
            calc_names.add(calc.name)
            self._check_expression(calc.expression, "Calculated field")
        summary_names = set()
        for summary in self.summaries:
            if summary.name in summary_names:
                raise ReportError(f"Duplicate summary field {summary.name}.")
            summary_names.add(summary.name)
            if summary.level.startswith("Group"):
                level = int(summary.level.split()[1])
                if level > self.group_count:
                    raise ReportError(
                        f"Summary {summary.name} uses missing group {level}.")
            self.resolve_summary_source(summary.source)
        for group in self.groups:
            if not group.break_field:
                raise ReportError(f"Group {group.level} needs a break field.")
            self.resolve_break(group.break_field)
        for item in self.fields:
            try:
                database, name, definition = self.resolve_source(item.source)
            except KeyError as exc:
                raise ReportError(
                    f"Field {item.source} not found in {self.owner}.") from exc
            if database == "CALC" and name not in calc_names:
                raise ReportError(f"Calculated field {name} is not defined.")
            if database == "SUMMARY" and name not in summary_names:
                raise ReportError(f"Summary field {name} is not defined.")
            if database == "SYSTEM" and name not in SYSTEM_FIELDS:
                raise ReportError(f"Unknown system field {name}.")
            if definition is None and database not in (
                    "CALC", "SUMMARY", "SYSTEM"):
                raise ReportError(f"Field {item.source} not found.")
            if item.col + max(1, item.window or item.length) - 1 > self.width:
                raise ReportError(
                    f"Field {item.source} extends past column {self.width}.")
        for text in self.texts:
            if text.col + len(text.text) - 1 > self.width:
                raise ReportError(
                    f"Text at row {text.row} extends past column {self.width}.")
        if not self.sections:
            raise ReportError("A report needs at least one section.")

    def _check_expression(self, expression: str, label: str) -> None:
        from .report_engine import prepare_expression

        try:
            parse_expression(prepare_expression(expression))
        except ExprError as exc:
            raise ReportError(f"{label}: {exc}") from exc

    def resolve_break(self, source: str) -> tuple[str, str, Field | None]:
        source = source.strip().upper()
        if "." in source:
            database, name = source.split(".", 1)
        else:
            database, name = self.owner, source
        if database == "CALC":
            if name not in {calc.name for calc in self.calcs}:
                raise ReportError(f"Calculated break field {name} is not defined.")
            return database, name, None
        databases = self._owner_databases()
        if database not in databases:
            database = self.owner
            if database not in databases:
                raise ReportError(f"Database {database} is outside the report owner.")
        try:
            return database, name, databases[database].field(name)
        except KeyError as exc:
            raise ReportError(f"Break field {source} not found.") from exc

    def resolve_summary_source(self, source: str) -> tuple[str, str, Field | None]:
        source = (source or "").strip().upper()
        if not source:
            raise ReportError("A summary field needs a field to summarize.")
        if "." in source:
            database, name = source.split(".", 1)
        else:
            database, name = self.owner, source
        if database == "CALC":
            if name not in {calc.name for calc in self.calcs}:
                raise ReportError(f"Calculated field {name} is not defined.")
            return database, name, None
        if database == "SUMMARY":
            raise ReportError("A summary field cannot summarize another summary.")
        databases = self._owner_databases()
        if database not in databases:
            raise ReportError(f"Database {database} is outside the report owner.")
        try:
            return database, name, databases[database].field(name)
        except KeyError as exc:
            raise ReportError(f"Summary source {source} not found.") from exc

    def expression_fields(self) -> tuple[Field, ...]:
        """Campi disponibili nelle espressioni di calcolo."""
        fields: list[Field] = []
        seen: set[str] = set()
        for database in self._owner_databases().values():
            for definition in database.fields:
                if definition.name not in seen:
                    fields.append(definition)
                    seen.add(definition.name)
        for index, calc in enumerate(self.calcs, 1):
            if calc.name not in seen:
                fields.append(Field(calc.name, "C", 30))
                seen.add(calc.name)
        for index, summary in enumerate(self.summaries, 1):
            if summary.name not in seen:
                fields.append(Field(summary.name, "N", 19, 4))
                seen.add(summary.name)
        return tuple(fields)

    # -- persistenza -----------------------------------------------------
    def save(self) -> None:
        self.validate()
        self.workspace.save_report(self)

    def erase(self) -> None:
        self.workspace.delete_report(self.owner, self.letter)

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner, "letter": self.letter,
            "description": self.description, "width": self.width,
            "fields": [item.to_dict() for item in self.fields],
            "texts": [item.to_dict() for item in self.texts],
            "calcs": [item.to_dict() for item in self.calcs],
            "summaries": [item.to_dict() for item in self.summaries],
            "groups": [item.to_dict() for item in self.groups],
            "sections": list(self.sections),
            "section_lines": dict(self.section_lines),
            "print_titles_first_page_only": self.print_titles_first_page_only,
            "print_footer_odd_pages_only": self.print_footer_odd_pages_only,
            "summary_on_separate_page": self.summary_on_separate_page,
            "suppress_blank_lines": self.suppress_blank_lines,
            "blank_line_after": self.blank_line_after,
            "page_breaks": self.page_breaks,
            "widow_count": self.widow_count,
            "orphan_count": self.orphan_count,
            "split_lines": self.split_lines,
            "max_records_page": self.max_records_page,
            "reset_page_after_group": self.reset_page_after_group,
            "reprint_group_header": self.reprint_group_header,
            "left_margin": self.left_margin,
            "top_margin": self.top_margin,
            "standard_page_length": self.standard_page_length,
            "page_length": self.page_length,
        }

    @classmethod
    def from_dict(cls, workspace, data: dict[str, Any]) -> "ReportDefinition":
        report = cls(
            workspace, str(data.get("owner", "")),
            str(data.get("letter", "A")),
            str(data.get("description", "")),
            int(data.get("width", 80)),
            [ReportField.from_dict(item) for item in data.get("fields", [])],
            [ReportText.from_dict(item) for item in data.get("texts", [])],
            [ReportCalc.from_dict(item) for item in data.get("calcs", [])],
            [ReportSummary.from_dict(item)
             for item in data.get("summaries", [])],
            [ReportGroup.from_dict(item) for item in data.get("groups", [])],
            list(data.get("sections", DEFAULT_SECTIONS)),
            dict(data.get("section_lines", {})),
            bool(data.get("print_titles_first_page_only", False)),
            bool(data.get("print_footer_odd_pages_only", False)),
            bool(data.get("summary_on_separate_page", False)),
            bool(data.get("suppress_blank_lines", True)),
            int(data.get("blank_line_after", 0)),
            bool(data.get("page_breaks", True)),
            int(data.get("widow_count", 0)),
            int(data.get("orphan_count", 0)),
            int(data.get("split_lines", 0)),
            int(data.get("max_records_page", 0)),
            bool(data.get("reset_page_after_group", False)),
            bool(data.get("reprint_group_header", False)),
            int(data.get("left_margin", 0)),
            int(data.get("top_margin", 0)),
            bool(data.get("standard_page_length", True)),
            int(data.get("page_length", 66)),
        )
        return report

    @property
    def label(self) -> str:
        return f"{self.letter} - {self.description or 'Report ' + self.letter}"


SYSTEM_FIELDS = (
    "DATE", "TIME", "PAGENUMBER", "REC_NUMBER", "CNTR_GRAND", "CNTR_PAGE",
    *[f"CNTR_GRP{level}" for level in range(1, MAX_GROUP_LEVELS + 1)],
)


def _expression_sentinel_fields(report: ReportDefinition) -> list[Field]:
    try:
        return list(report.expression_fields())
    except ReportError:
        return [Field("SENTINEL", "C", 1)]


def summary_type_for_section(section: str) -> tuple[str, str]:
    """Tipo e livello summary proposti per la sezione corrente."""
    if section == "summary":
        return "Total", "Grand"
    if section == "page_footer":
        return "Total", "Page"
    match = re.match(r"group(\d)_footer", section)
    if match:
        return "Total", f"Group {match.group(1)}"
    return "Count", "Grand"


def default_length(field: Field) -> int:
    return max(1, field.length)


def canonical_number(text: str, decimals: int | None) -> Decimal | None:
    try:
        number = Decimal((text or "").strip())
    except Exception:
        return None
    if decimals is not None:
        number = number.quantize(Decimal(1).scaleb(-decimals))
    return number


def parse_report_value(definition: Field | None, text: str) -> str:
    if definition is None:
        return text or ""
    try:
        return parse_value(definition, text or "")
    except Exception:
        return text or ""


__all__ = [
    "DEFAULT_SECTIONS",
    "IGNORE_OPTIONS",
    "JUSTIFICATIONS",
    "MAX_CALCS",
    "MAX_GROUP_LEVELS",
    "MAX_REPORTS",
    "MAX_WIDTH",
    "MIN_WIDTH",
    "REPORT_LETTERS",
    "ReportCalc",
    "ReportDefinition",
    "ReportError",
    "ReportField",
    "ReportGroup",
    "ReportSummary",
    "ReportText",
    "SECTION_ORDER",
    "SECTION_TITLES",
    "SUMMARY_LEVELS",
    "SUMMARY_MODES",
    "SUMMARY_ONLY",
    "SUMMARY_TYPES",
    "SYSTEM_FIELDS",
    "summary_type_for_section",
]
