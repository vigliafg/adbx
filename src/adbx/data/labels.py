"""Mail label: modello dei layout di etichetta (O8).

Un layout appartiene a un database o set, ha una lettera A-Z e definisce una
griglia di etichette: larghezza, altezza, quante per riga, spaziatura, copie
per record e margini. Campi e testi stanno su righe e colonne della singola
etichetta; le giustificazioni includono le opzioni avanzate del manuale
(Suppress, Float, Trim, Join, Before, After).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .expressions import ExprError, parse_expression
from .fields import NAME_RE, Field

LABEL_LETTERS = tuple(chr(code) for code in range(ord("A"), ord("Z") + 1))
MAX_LABELS = len(LABEL_LETTERS)
MIN_LABEL_WIDTH = 10
MAX_LABEL_WIDTH = 78
MIN_LABEL_HEIGHT = 1
MAX_LABEL_HEIGHT = 20
MAX_ACROSS = 6
MAX_CALCS = 128
JUSTIFICATIONS = ("Suppress", "Left", "Right", "Center", "None", "Float",
                  "Trim", "Join", "Before", "After")
BASIC_JUSTIFICATIONS = ("Suppress", "Left", "Right", "Center", "None")

PREDEFINED_LABELS = (
    ("3-1/2 x 15/16, one across", 35, 5, 1, 1, 1),
    ("3-1/2 x 15/16, two across", 35, 5, 2, 2, 1),
    ("4 x 1-7/16, three across", 40, 7, 3, 2, 1),
    ("2-5/8 x 1, four across", 26, 6, 4, 2, 1),
    ("1 x 2-5/8, envelope", 40, 8, 1, 1, 1),
)


class LabelError(ValueError):
    """Etichetta non valida."""


@dataclass
class LabelField:
    row: int = 1
    col: int = 1
    source: str = ""
    database: str = ""
    name: str = ""
    length: int = 0
    justification: str = "Suppress"
    format: str = ""
    decimals: int | None = None
    delete_line_if_empty: bool = False

    def __post_init__(self) -> None:
        self.database = self.database.strip().upper()
        self.name = self.name.strip().upper()
        self.source = (self.source or "").strip().upper()
        if self.source and (not self.database or not self.name):
            database, _, name = self.source.partition(".")
            if name:
                self.database = self.database or database
                self.name = self.name or name
            else:
                self.name = self.name or self.source
        if self.database and self.name and "." not in self.source:
            self.source = f"{self.database}.{self.name}"
        self.row = max(1, int(self.row))
        self.col = max(1, int(self.col))
        self.length = max(0, int(self.length))
        if self.justification not in JUSTIFICATIONS:
            self.justification = "Suppress"
        if self.decimals is not None:
            self.decimals = max(0, min(14, int(self.decimals)))

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LabelField":
        return cls(int(data.get("row", 1)), int(data.get("col", 1)),
                   str(data.get("source", "")), str(data.get("database", "")),
                   str(data.get("name", "")), int(data.get("length", 0)),
                   str(data.get("justification", "Suppress")),
                   str(data.get("format", "")), data.get("decimals"),
                   bool(data.get("delete_line_if_empty", False)))


@dataclass
class LabelText:
    row: int = 1
    col: int = 1
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LabelText":
        return cls(max(1, int(data.get("row", 1))),
                   max(1, int(data.get("col", 1))),
                   str(data.get("text", "")))


@dataclass
class LabelCalc:
    name: str = "CALC1"
    expression: str = ""

    def __post_init__(self) -> None:
        self.name = self.name.strip().upper()
        if not NAME_RE.match(self.name):
            raise LabelError(
                "Calculated field names start with a letter, use A-Z 0-9 _ "
                "and are at most 10 characters.")
        try:
            parse_expression(self.expression)
        except ExprError as exc:
            raise LabelError(f"Calculated field: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LabelCalc":
        return cls(str(data.get("name", "CALC1")),
                   str(data.get("expression", "")))


@dataclass
class LabelDefinition:
    workspace: Any
    owner: str
    letter: str = "A"
    description: str = ""
    width: int = 35
    height: int = 5
    across: int = 1
    columns_between: int = 2
    lines_between: int = 1
    copies: str = "1"
    left_margin: int = 0
    continuous_feed: bool = True
    rows_per_page: int = 7
    top_margin: int = 0
    fields: list[LabelField] = field(default_factory=list)
    texts: list[LabelText] = field(default_factory=list)
    calcs: list[LabelCalc] = field(default_factory=list)
    updated: float = 0.0

    def __post_init__(self) -> None:
        self.owner = self.owner.strip().upper()
        self.letter = (self.letter or "A").strip().upper()[:1]
        if self.letter not in LABEL_LETTERS:
            raise LabelError("Label ids are letters A-Z.")
        self.width = max(MIN_LABEL_WIDTH, min(MAX_LABEL_WIDTH, int(self.width)))
        self.height = max(MIN_LABEL_HEIGHT, min(MAX_LABEL_HEIGHT,
                                                int(self.height)))
        self.across = max(1, min(MAX_ACROSS, int(self.across)))
        self.columns_between = max(1, min(20, int(self.columns_between)))
        self.lines_between = max(0, min(15, int(self.lines_between)))
        self.copies = (self.copies or "1").strip()
        self.left_margin = max(0, min(40, int(self.left_margin)))
        self.rows_per_page = max(1, min(99, int(self.rows_per_page)))
        self.top_margin = max(0, min(20, int(self.top_margin)))

    @property
    def label(self) -> str:
        return f"{self.letter} - {self.description or 'Label ' + self.letter}"

    # -- proprietario ----------------------------------------------------
    def owner_databases(self) -> dict[str, Any]:
        database = self.workspace.get(self.owner)
        if database is not None:
            return {database.name: database}
        definition = self.workspace.get_set(self.owner)
        if definition is None:
            raise LabelError(f"Owner {self.owner} not found.")
        return {name: definition.database(name)
                for name in definition.database_names()}

    def field_definition(self, item: LabelField) -> Field | None:
        if item.database in ("CALC", "SYSTEM"):
            return None
        try:
            return self.owner_databases()[item.database].field(item.name)
        except (KeyError, LabelError):
            return None

    # -- validazione -----------------------------------------------------
    def validate(self) -> None:
        databases = self.owner_databases()
        calc_names = set()
        for calc in self.calcs:
            if calc.name in calc_names:
                raise LabelError(f"Duplicate calculated field {calc.name}.")
            calc_names.add(calc.name)
        if len(self.calcs) > MAX_CALCS:
            raise LabelError(f"A label has at most {MAX_CALCS} calculated fields.")
        for item in self.fields:
            if item.database == "CALC":
                if item.name not in calc_names:
                    raise LabelError(f"Calculated field {item.name} is not defined.")
            elif item.database == "SYSTEM":
                if item.name not in ("DATE", "TIME", "REC_NUMBER",
                                     "CNTR_GRAND", "DELETED", "INDEX_NAME",
                                     "INDEX_DESC", "INDEX_EQN", "DB_NAME",
                                     "DB_DESC", "SET_NAME", "SET_DESC"):
                    raise LabelError(f"Unknown system field {item.name}.")
            else:
                if item.database not in databases:
                    raise LabelError(
                        f"Database {item.database} is outside the label owner.")
                try:
                    definition = databases[item.database].field(item.name)
                except KeyError as exc:
                    raise LabelError(
                        f"Field {item.name} not found in {item.database}.") from exc
                if definition.is_memo:
                    raise LabelError("Memo fields cannot be placed on a label.")
            if item.col < 1 or item.col + item.length - 1 > self.width:
                raise LabelError(
                    f"Field {item.source} does not fit in {self.width} columns.")
            if not 1 <= item.row <= self.height:
                raise LabelError(f"Field {item.source} is outside the label.")
        for text in self.texts:
            if not 1 <= text.row <= self.height:
                raise LabelError("Text is outside the label.")
            if text.col < 1 or text.col + len(text.text) - 1 > self.width:
                raise LabelError("Text does not fit in the label width.")
        if not self.copies:
            raise LabelError("Enter the number of copies.")

    def expression_fields(self) -> tuple[Field, ...]:
        fields: list[Field] = []
        seen: set[str] = set()
        for database in self.owner_databases().values():
            for definition in database.fields:
                if definition.name not in seen:
                    fields.append(definition)
                    seen.add(definition.name)
        for calc in self.calcs:
            if calc.name not in seen:
                fields.append(Field(calc.name, "C", 30))
                seen.add(calc.name)
        return tuple(fields)

    # -- persistenza -----------------------------------------------------
    def save(self) -> None:
        self.validate()
        self.workspace.save_label(self)

    def erase(self) -> None:
        self.workspace.delete_label(self.owner, self.letter)

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner, "letter": self.letter,
            "description": self.description, "width": self.width,
            "height": self.height, "across": self.across,
            "columns_between": self.columns_between,
            "lines_between": self.lines_between, "copies": self.copies,
            "left_margin": self.left_margin,
            "continuous_feed": self.continuous_feed,
            "rows_per_page": self.rows_per_page,
            "top_margin": self.top_margin,
            "fields": [item.to_dict() for item in self.fields],
            "texts": [item.to_dict() for item in self.texts],
            "calcs": [item.to_dict() for item in self.calcs],
        }

    @classmethod
    def from_dict(cls, workspace, data: dict[str, Any]) -> "LabelDefinition":
        return cls(
            workspace, str(data.get("owner", "")),
            str(data.get("letter", "A")), str(data.get("description", "")),
            int(data.get("width", 35)), int(data.get("height", 5)),
            int(data.get("across", 1)), int(data.get("columns_between", 2)),
            int(data.get("lines_between", 1)), str(data.get("copies", "1")),
            int(data.get("left_margin", 0)),
            bool(data.get("continuous_feed", True)),
            int(data.get("rows_per_page", 7)),
            int(data.get("top_margin", 0)),
            [LabelField.from_dict(item) for item in data.get("fields", [])],
            [LabelText.from_dict(item) for item in data.get("texts", [])],
            [LabelCalc.from_dict(item) for item in data.get("calcs", [])])


__all__ = [
    "BASIC_JUSTIFICATIONS",
    "JUSTIFICATIONS",
    "LABEL_LETTERS",
    "LabelCalc",
    "LabelDefinition",
    "LabelError",
    "LabelField",
    "LabelText",
    "MAX_ACROSS",
    "MAX_LABEL_HEIGHT",
    "MAX_LABEL_WIDTH",
    "MAX_LABELS",
    "MIN_LABEL_HEIGHT",
    "MIN_LABEL_WIDTH",
    "PREDEFINED_LABELS",
]
