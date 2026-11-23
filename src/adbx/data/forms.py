"""Form: layout a celle per database e set (O6).

Un form è una sequenza di pagine (fino a 10) con campi, testi, riquadri e
regioni uno-a-molti. I campi possono essere reali, calcolati o summary; i
form dei set possono mostrare campi di più database e una regione per ogni
link 1:N. La definizione vive nel workspace SQLite, non in file `.INx`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .expressions import Context, ExprError, evaluate
from .fields import Field, FieldError, format_value, parse_value

FORM_LETTERS = tuple(chr(code) for code in range(ord("A"), ord("Z") + 1))
MAX_FORMS = len(FORM_LETTERS)
MAX_PAGES = 10
MAX_FORM_ROW = 41
MAX_FORM_COL = 130
JUSTIFICATIONS = ("L", "R", "C")
SUMMARY_TYPES = ("", "First", "Last", "Count", "Biggest", "Smallest",
                 "Total", "Average")


class FormError(ValueError):
    """Form non valido."""


@dataclass
class FormField:
    database: str = ""
    field: str = ""
    page: int = 0
    row: int = 1
    col: int = 1
    length: int = 0
    window: int = 0
    title: str = ""
    show_title: bool = False
    justification: str = "L"
    color: str = ""
    format: str = ""
    kind: str = "field"      # field, calculated, summary
    expression: str = ""
    summary: str = ""
    summary_database: str = ""
    summary_field: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FormField":
        item = cls()
        for name in item.__dict__:
            if name in data:
                setattr(item, name, data[name])
        item.page = max(0, min(MAX_PAGES - 1, int(item.page)))
        item.row = max(0, min(MAX_FORM_ROW, int(item.row)))
        item.col = max(0, min(MAX_FORM_COL, int(item.col)))
        item.length = max(0, int(item.length))
        item.window = max(0, int(item.window))
        item.justification = (str(item.justification or "L").upper()[:1]
                              if str(item.justification or "L").upper()[:1]
                              in JUSTIFICATIONS else "L")
        if item.kind not in ("field", "calculated", "summary"):
            item.kind = "field"
        if item.summary not in SUMMARY_TYPES:
            item.summary = ""
        return item


@dataclass
class FormLabel:
    page: int = 0
    row: int = 1
    col: int = 1
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FormLabel":
        return cls(max(0, min(MAX_PAGES - 1, int(data.get("page", 0)))),
                   max(0, min(MAX_FORM_ROW, int(data.get("row", 1)))),
                   max(0, min(MAX_FORM_COL, int(data.get("col", 1)))),
                   str(data.get("text", "")))


@dataclass
class FormBox:
    page: int = 0
    row: int = 1
    col: int = 1
    height: int = 3
    width: int = 20
    double: bool = True
    color: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FormBox":
        return cls(max(0, min(MAX_PAGES - 1, int(data.get("page", 0)))),
                   max(0, min(MAX_FORM_ROW, int(data.get("row", 1)))),
                   max(0, min(MAX_FORM_COL, int(data.get("col", 1)))),
                   max(2, int(data.get("height", 3))),
                   max(2, int(data.get("width", 20))),
                   bool(data.get("double", True)),
                   str(data.get("color", "")))


@dataclass
class FormRegion:
    database: str = ""
    page: int = 0
    row: int = 1
    col: int = 1
    height: int = 8
    width: int = 60
    title: str = ""
    maximum: int = 100
    filter: str = ""
    filter_active: bool = False
    show_mode: str = "not_deleted"

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FormRegion":
        return cls(str(data.get("database", "")).upper(),
                   max(0, min(MAX_PAGES - 1, int(data.get("page", 0)))),
                   max(0, min(MAX_FORM_ROW, int(data.get("row", 1)))),
                   max(0, min(MAX_FORM_COL, int(data.get("col", 1)))),
                   max(3, int(data.get("height", 8))),
                   max(10, int(data.get("width", 60))),
                   str(data.get("title", "")),
                   max(1, min(9999, int(data.get("maximum", 100)))),
                   str(data.get("filter", "")),
                   bool(data.get("filter_active", False)),
                   str(data.get("show_mode", "not_deleted")))


@dataclass
class FormDefinition:
    workspace: Any
    owner: str
    letter: str = "A"
    description: str = ""
    pages: int = 1
    fields: list[FormField] = field(default_factory=list)
    labels: list[FormLabel] = field(default_factory=list)
    boxes: list[FormBox] = field(default_factory=list)
    regions: list[FormRegion] = field(default_factory=list)
    custom_menu: str = ""
    restrict: str = ""
    printable: bool = True
    print_width: int = 80
    margins: str = ""
    updated: float = 0.0

    def __post_init__(self) -> None:
        self.owner = self.owner.strip().upper()
        self.letter = (self.letter or "A").strip().upper()[:1]
        if self.letter not in FORM_LETTERS:
            raise FormError("Form ids are letters A-Z.")
        self.pages = max(1, min(MAX_PAGES, int(self.pages or 1)))
        if not self.printable:
            self.printable = False
        for item in self.fields:
            item.database = item.database.upper()
        for item in self.regions:
            item.database = item.database.upper()

    @property
    def label(self) -> str:
        return f"{self.letter} - {self.description or 'Form ' + self.letter}"

    def validate(self) -> None:
        databases = self._owner_databases()
        for item in self.fields:
            if item.kind == "field":
                if item.database not in databases:
                    raise FormError(
                        f"Field {item.field} refers to database "
                        f"{item.database} outside the form owner.")
                try:
                    databases[item.database].field(item.field)
                except KeyError as exc:
                    raise FormError(
                        f"Field {item.field} not found in {item.database}."
                    ) from exc
            if item.kind == "calculated" and not item.expression.strip():
                raise FormError(
                    f"Calculated field {item.title or item.field} needs an "
                    "expression.")
        for region in self.regions:
            if region.database not in databases:
                raise FormError(
                    f"Region database {region.database} is outside the set.")
            if region.filter_active and region.filter.strip():
                database = databases[region.database]
                try:
                    evaluate(region.filter, Context(
                        fields=database.fields,
                        values={field.name: "" for field in database.fields}))
                except ExprError as exc:
                    raise FormError(f"Region filter: {exc}") from exc
        pages = [0]
        pages += [item.page for item in self.fields]
        pages += [item.page for item in self.labels]
        pages += [item.page for item in self.boxes]
        pages += [item.page for item in self.regions]
        self.pages = max(1, min(MAX_PAGES, max(pages) + 1))

    def _owner_databases(self) -> dict[str, Any]:

        database = self.workspace.get(self.owner)
        if database is not None:
            return {database.name: database}
        definition = self.workspace.get_set(self.owner)
        if definition is None:
            raise FormError(f"Owner {self.owner} not found.")
        return {name: definition.database(name)
                for name in definition.database_names()}

    def owner_databases(self) -> dict[str, Any]:
        return self._owner_databases()

    def field_definitions(self, page: int | None = None
                          ) -> list[FormField]:
        fields = [item for item in self.fields if item.kind == "field"]
        if page is not None:
            fields = [item for item in fields if item.page == page]
        return fields

    def page_fields(self, page: int) -> list[FormField]:
        return [item for item in self.fields if item.page == page]

    def page_labels(self, page: int) -> list[FormLabel]:
        return [item for item in self.labels if item.page == page]

    def page_boxes(self, page: int) -> list[FormBox]:
        return [item for item in self.boxes if item.page == page]

    def page_regions(self, page: int) -> list[FormRegion]:
        return [item for item in self.regions if item.page == page]

    # -- valori ---------------------------------------------------------
    def value_for(self, item: FormField, values: dict[str, str],
                  database) -> str:
        if item.kind == "field":
            return values.get(item.field, "")
        if item.kind == "calculated":
            try:
                result = evaluate(item.expression, Context(
                    fields=database.fields, values=values,
                    pattern=self.workspace.pattern_mode))
            except ExprError:
                return ""
            try:
                return parse_value(database.field(item.field), str(result))
            except (FieldError, KeyError):
                return str(result) if result is not None else ""
        return ""

    def summary_value(self, item: FormField, rows: list[dict[str, str]]) -> str:
        if item.summary == "Count":
            return str(len(rows))
        values: list[str] = []
        for row in rows:
            values.append(row.get(item.summary_field, ""))
        if not values:
            return ""
        if item.summary == "First":
            return values[0]
        if item.summary == "Last":
            return values[-1]
        if item.summary in ("Biggest", "Smallest", "Total", "Average"):
            numbers: list[float] = []
            for value in values:
                try:
                    numbers.append(float(value))
                except (TypeError, ValueError):
                    continue
            if not numbers:
                return ""
            if item.summary == "Biggest":
                return format_value(_number_field(numbers), str(max(numbers)))
            if item.summary == "Smallest":
                return format_value(_number_field(numbers), str(min(numbers)))
            if item.summary == "Total":
                return f"{sum(numbers):g}"
            return f"{sum(numbers) / len(numbers):g}"
        return ""

    # -- persistenza -----------------------------------------------------
    def save(self) -> None:
        self.validate()
        self.workspace.save_form(self)

    def erase(self) -> None:
        self.workspace.delete_form(self.owner, self.letter)

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner, "letter": self.letter,
            "description": self.description, "pages": self.pages,
            "fields": [item.to_dict() for item in self.fields],
            "labels": [item.to_dict() for item in self.labels],
            "boxes": [item.to_dict() for item in self.boxes],
            "regions": [item.to_dict() for item in self.regions],
            "custom_menu": self.custom_menu, "restrict": self.restrict,
            "printable": self.printable, "print_width": self.print_width,
            "margins": self.margins,
        }

    @classmethod
    def from_dict(cls, workspace, data: dict[str, Any]) -> "FormDefinition":
        form = cls(
            workspace, str(data.get("owner", "")),
            str(data.get("letter", "A")),
            str(data.get("description", "")),
            int(data.get("pages", 1)),
            [FormField.from_dict(item) for item in data.get("fields", [])],
            [FormLabel.from_dict(item) for item in data.get("labels", [])],
            [FormBox.from_dict(item) for item in data.get("boxes", [])],
            [FormRegion.from_dict(item) for item in data.get("regions", [])],
            str(data.get("custom_menu", "")),
            str(data.get("restrict", "")),
            bool(data.get("printable", True)),
            int(data.get("print_width", 80)),
            str(data.get("margins", "")))
        return form


def _number_field(numbers: list[float]) -> Field:
    return Field("SUMMARY", "N", 10, 2)


__all__ = [
    "FORM_LETTERS",
    "FormBox",
    "FormDefinition",
    "FormError",
    "FormField",
    "FormLabel",
    "FormRegion",
    "JUSTIFICATIONS",
    "MAX_FORMS",
    "MAX_PAGES",
    "SUMMARY_TYPES",
]
