"""Regole di campo (O4): valori, maschere, validazioni e lookup.

Il modulo è il motore puro delle regole del capitolo 10 del Reference Manual.
La sessione di data entry lo interroga per default, incrementi, campi
calcolati, obbligatorietà, validazioni, doppia immissione, skip, lookup e
post data. Le regole sono serializzate in JSON nel workspace SQLite; il
`.DBF` resta la sola sorgente dei dati.

Le regole possono essere definite a livello di database e, in futuro, di set.
Quando esiste una regola di set per un campo, quella di database viene
ignorata per intero: è la regola di risoluzione del manuale (cap. 10).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from .expressions import Context, ExprError, evaluate, key_text, truthy
from .fields import Field, FieldError, parse_value

CASE_MODES = ("None", "Caps", "Lower", "First", "Word", "X")
VALUE_MODES = ("User-entered", "Calculated", "Summary")
DEFAULT_MODES = ("None", "Value", "Expression")
INCREMENT_MODES = ("None", "Records", "Updates")
REQUIRED_MODES = ("No", "Yes", "Expression")
DOUBLE_ENTRY_MODES = ("No", "Yes", "Expression")
LOOKUP_VALIDATIONS = ("None", "Exists", "Doesn't Exist")
LOOKUP_SOURCES = ("Table", "Database", "Advanced")
ADVANCED_OPTIONS = ("Cascading table", "Conditional table",
                    "Conditional database")
AUTO_POPUP_MODES = ("No", "Yes", "Expression")
POST_MODES = ("Add", "Subtract", "Replace")
LOOKUP_LOCATIONS = tuple(str(number) for number in range(1, 10)) + ("Hidden",)

MAX_LOOKUP_ROWS = 255
MAX_LOOKUP_COLUMNS = 6
MAX_CASCADING_LINES = 255
TEMPLATE_BLANK = "|"
PATH_MARKER = "^"
VALUE_MARKER = "~"


class RuleError(ValueError):
    """Regola di campo non valida."""


@dataclass
class LookupTable:
    """Tabella di lookup: prima colonna scelta, fino a 5 colonne riempite."""

    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)

    def normalize(self) -> None:
        self.columns = [name.upper() for name in self.columns[:MAX_LOOKUP_COLUMNS - 1]]
        width = 1 + len(self.columns)
        clean: list[list[str]] = []
        for row in self.rows[:MAX_LOOKUP_ROWS]:
            cells = [str(cell) for cell in row[:width]]
            cells += ["" for _ in range(width - len(cells))]
            if any(cell.strip() for cell in cells):
                clean.append(cells)
        self.rows = clean

    def choices(self) -> list[str]:
        return [row[0] for row in self.rows if row and row[0].strip()]

    def find(self, value: str) -> list[str] | None:
        needle = value.strip().upper()
        for row in self.rows:
            if row and row[0].strip().upper() == needle:
                return row
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"columns": list(self.columns),
                "rows": [list(row) for row in self.rows]}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LookupTable":
        data = data or {}
        return cls([str(item) for item in data.get("columns", [])],
                   [[str(cell) for cell in row]
                    for row in data.get("rows", [])])


@dataclass
class MappingRow:
    """Riga della Lookup Mapping: campo scelto, campo riempito, condizione."""

    choice_field: str = ""
    filled_field: str = ""
    condition: str = ".T."
    expression: str = ""
    display: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"choice": self.choice_field, "filled": self.filled_field,
                "condition": self.condition, "expression": self.expression,
                "display": self.display}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MappingRow":
        return cls(str(data.get("choice", "")), str(data.get("filled", "")),
                   str(data.get("condition", ".T.")) or ".T.",
                   str(data.get("expression", "")),
                   bool(data.get("display", True)))


@dataclass
class PostingRule:
    """Regola di post data verso un database esterno o figlio."""

    database: str = ""
    field: str = ""
    mode: str = "Add"
    condition: str = ""
    expression: str = ""
    linking_index: str = ""
    common: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"database": self.database, "field": self.field,
                "mode": self.mode, "condition": self.condition,
                "expression": self.expression,
                "linking_index": self.linking_index, "common": self.common}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PostingRule":
        mode = str(data.get("mode", "Add"))
        return cls(str(data.get("database", "")), str(data.get("field", "")),
                   mode if mode in POST_MODES else "Add",
                   str(data.get("condition", "")),
                   str(data.get("expression", "")),
                   str(data.get("linking_index", "")),
                   str(data.get("common", "")))


@dataclass
class CascadingEntry:
    """Riga dell'outline di una cascading table."""

    depth: int = 0
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"depth": self.depth, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CascadingEntry":
        return cls(max(0, int(data.get("depth", 0))), str(data.get("text", "")))


@dataclass
class ConditionalGroup:
    """Gruppo condizionale per una tabella di lookup."""

    expression: str = ""
    filter: str = ""
    table: LookupTable = field(default_factory=LookupTable)

    def to_dict(self) -> dict[str, Any]:
        return {"expression": self.expression, "filter": self.filter,
                "table": self.table.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConditionalGroup":
        return cls(str(data.get("expression", "")),
                   str(data.get("filter", "")),
                   LookupTable.from_dict(data.get("table")))


@dataclass
class ConditionalDatabase:
    """Gruppo condizionale per una lookup database."""

    expression: str = ""
    database: str = ""
    linking_index: str = ""
    display_index: str = ""
    filter: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"expression": self.expression, "database": self.database,
                "linking_index": self.linking_index,
                "display_index": self.display_index, "filter": self.filter}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConditionalDatabase":
        return cls(str(data.get("expression", "")),
                   str(data.get("database", "")),
                   str(data.get("linking_index", "")),
                   str(data.get("display_index", "")),
                   str(data.get("filter", "")))


@dataclass
class FieldRule:
    """Tutte le regole di un campo; i valori vuoti significano "non definita"."""

    field_name: str
    value: str = "User-entered"
    expression: str = ""
    case: str = "None"
    template: str = ""
    mask: str = ""
    allow_exceptions: bool = False
    default_mode: str = "None"
    default: str = ""
    increment: str = "None"
    auto_advance: bool = False
    prompt: str = ""
    required: str = "No"
    required_expression: str = ""
    validation: str = ""
    validation_message: str = ""
    double_entry: str = "No"
    double_entry_expression: str = ""
    skip_expression: str = ""
    post_data: bool = False
    postings: list[PostingRule] = field(default_factory=list)
    lookup: bool = False
    lookup_validation: str = "None"
    lookup_allow_exceptions: bool = False
    location: str = "3"
    window_rows: int = 10
    auto_popup: str = "No"
    popup_entry: str = ""
    popup_exit: str = ""
    lookup_source: str = "Table"
    lookup_database: str = ""
    linking_index: str = ""
    display_index: str = ""
    table: LookupTable = field(default_factory=LookupTable)
    mapping: list[MappingRow] = field(default_factory=list)
    advanced: str = ""
    cascading: list[CascadingEntry] = field(default_factory=list)
    conditional_tables: list[ConditionalGroup] = field(default_factory=list)
    conditional_databases: list[ConditionalDatabase] = field(
        default_factory=list)

    @property
    def field(self) -> str:
        return self.field_name

    @property
    def calculated(self) -> bool:
        return self.value == "Calculated"

    @property
    def is_empty(self) -> bool:
        return self.to_dict() == FieldRule(self.field_name).to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field_name,
            "value": self.value,
            "expression": self.expression,
            "case": self.case,
            "template": self.template,
            "mask": self.mask,
            "allow_exceptions": self.allow_exceptions,
            "default_mode": self.default_mode,
            "default": self.default,
            "increment": self.increment,
            "auto_advance": self.auto_advance,
            "prompt": self.prompt,
            "required": self.required,
            "required_expression": self.required_expression,
            "validation": self.validation,
            "validation_message": self.validation_message,
            "double_entry": self.double_entry,
            "double_entry_expression": self.double_entry_expression,
            "skip_expression": self.skip_expression,
            "post_data": self.post_data,
            "postings": [rule.to_dict() for rule in self.postings],
            "lookup": self.lookup,
            "lookup_validation": self.lookup_validation,
            "lookup_allow_exceptions": self.lookup_allow_exceptions,
            "location": self.location,
            "window_rows": self.window_rows,
            "auto_popup": self.auto_popup,
            "popup_entry": self.popup_entry,
            "popup_exit": self.popup_exit,
            "lookup_source": self.lookup_source,
            "lookup_database": self.lookup_database,
            "linking_index": self.linking_index,
            "display_index": self.display_index,
            "table": self.table.to_dict(),
            "mapping": [row.to_dict() for row in self.mapping],
            "advanced": self.advanced,
            "cascading": [entry.to_dict() for entry in self.cascading],
            "conditional_tables": [group.to_dict()
                                   for group in self.conditional_tables],
            "conditional_databases": [group.to_dict()
                                      for group in self.conditional_databases],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldRule":
        rule = cls(str(data.get("field", "")).upper())
        for name in ("value", "expression", "case", "template", "mask",
                     "default_mode", "default", "increment", "prompt",
                     "required", "required_expression", "validation",
                     "validation_message", "double_entry",
                     "double_entry_expression", "skip_expression",
                     "lookup_validation", "location", "auto_popup",
                     "popup_entry", "popup_exit", "lookup_source",
                     "lookup_database", "linking_index", "display_index",
                     "advanced"):
            if name in data:
                setattr(rule, name, str(data[name]))
        for name in ("allow_exceptions", "auto_advance", "post_data",
                     "lookup", "lookup_allow_exceptions"):
            if name in data:
                setattr(rule, name, bool(data[name]))
        if "window_rows" in data:
            rule.window_rows = max(1, min(15, int(data["window_rows"])))
        rule.postings = [PostingRule.from_dict(item)
                         for item in data.get("postings", [])]
        rule.table = LookupTable.from_dict(data.get("table"))
        rule.mapping = [MappingRow.from_dict(item)
                        for item in data.get("mapping", [])]
        rule.cascading = [CascadingEntry.from_dict(item)
                          for item in data.get("cascading", [])]
        rule.conditional_tables = [ConditionalGroup.from_dict(item)
                                   for item in data.get("conditional_tables", [])]
        rule.conditional_databases = [
            ConditionalDatabase.from_dict(item)
            for item in data.get("conditional_databases", [])]
        rule.normalize()
        return rule

    def normalize(self) -> None:
        self.field_name = self.field_name.upper()
        if self.value not in VALUE_MODES:
            self.value = "User-entered"
        if self.case not in CASE_MODES:
            self.case = "None"
        if self.default_mode not in DEFAULT_MODES:
            self.default_mode = "None"
        if self.increment not in INCREMENT_MODES:
            self.increment = "None"
        if self.required not in REQUIRED_MODES:
            self.required = "No"
        if self.double_entry not in DOUBLE_ENTRY_MODES:
            self.double_entry = "No"
        if self.lookup_validation not in LOOKUP_VALIDATIONS:
            self.lookup_validation = "None"
        if self.lookup_source not in LOOKUP_SOURCES:
            self.lookup_source = "Table"
        if self.auto_popup not in AUTO_POPUP_MODES:
            self.auto_popup = "No"
        if self.location not in LOOKUP_LOCATIONS:
            self.location = "3"
        if self.advanced not in ("",) + ADVANCED_OPTIONS:
            self.advanced = ""
        self.window_rows = max(1, min(15, int(self.window_rows or 10)))
        self.table.normalize()
        for group in self.conditional_tables:
            group.table.normalize()


def resolve_rule(database_rule: FieldRule | None,
                 set_rule: FieldRule | None) -> FieldRule | None:
    """Risoluzione set/database: una regola di set sostituisce quella intera."""
    if set_rule is not None and not set_rule.is_empty:
        return set_rule
    return database_rule


def resolve_rules(database_rules: dict[str, FieldRule],
                  set_rules: dict[str, FieldRule] | None = None
                  ) -> dict[str, FieldRule]:
    """Applica `resolve_rule` a tutte le regole conosciute."""
    set_rules = set_rules or {}
    result = dict(database_rules)
    for name, rule in set_rules.items():
        if not rule.is_empty:
            result[name.upper()] = rule
    return result


# -- contesto ---------------------------------------------------------------


def context_for(database, values: dict[str, str], *, seq: int = 0,
                deleted: bool = False) -> Context:
    return Context(fields=database.fields, values=values,
                   pattern=database.workspace.pattern_mode, seq=seq,
                   deleted=deleted, count=database.count(include_deleted=True))


def _canonical(field: Field, value: Any) -> str:
    text = key_text(value) if not isinstance(value, str) else value
    try:
        return parse_value(field, text)
    except FieldError:
        return ""


def _evaluate_text(text: str, database, values: dict[str, str], *,
                   seq: int = 0) -> Any:
    return evaluate(text, context_for(database, values, seq=seq))


def _evaluate_boolean(text: str, database, values: dict[str, str], *,
                      seq: int = 0, default: bool = False) -> bool:
    text = (text or "").strip()
    if not text:
        return default
    try:
        return truthy(evaluate(text, context_for(database, values, seq=seq)))
    except ExprError:
        return default


# -- conversione di maiuscole ----------------------------------------------


def apply_case(value: str, mode: str) -> str:
    text = value or ""
    if mode == "Caps":
        return text.upper()
    if mode == "Lower":
        return text.lower()
    if mode == "First":
        return text[:1].upper() + text[1:]
    if mode == "Word":
        return re.sub(r"\b\w", lambda match: match.group(0).upper(), text)
    if mode == "X":
        return text.lower()[:1].upper() + text.lower()[1:]
    return text


# -- template e maschere ----------------------------------------------------


def editable_positions(template: str) -> list[int]:
    """Posizioni non fisse del template; `|` è uno spazio fisso."""
    return [index for index, char in enumerate(template)
            if char == " "]


def template_display(template: str, value: str) -> str:
    """Sovrappone i caratteri del valore alle posizioni libere del template."""
    if not template:
        return value or ""
    positions = editable_positions(template)
    chars = list(template.replace(TEMPLATE_BLANK, " "))
    data = list(value or "")
    for slot, position in enumerate(positions):
        if slot < len(data):
            chars[position] = data[slot]
    return "".join(chars)


def template_data(template: str, text: str) -> str:
    """Estrae i soli caratteri variabili da un valore con template."""
    if not template:
        return text or ""
    positions = editable_positions(template)
    text = text or ""
    if len(text) != len(template):
        return text
    return "".join(text[position] for position in positions)


def template_is_blank(template: str, text: str) -> bool:
    return not template_data(template, text).strip()


def mask_slots(template: str, mask: str) -> dict[int, str]:
    """Posizione → carattere di maschera, saltando i caratteri del template."""
    if not mask:
        return {}
    if template:
        positions = editable_positions(template)
        slot_chars = [char for char in mask if char != " "]
        return {position: slot_chars[index]
                for index, position in enumerate(positions)
                if index < len(slot_chars)}
    return {index: char for index, char in enumerate(mask) if char != " "}


def mask_error(template: str, mask: str, text: str) -> str:
    """Messaggio se un valore viola la maschera, altrimenti stringa vuota."""
    slots = mask_slots(template, mask)
    if not slots:
        return ""
    for position, mask_char in slots.items():
        char = text[position] if position < len(text) else ""
        if not char:
            continue
        if mask_char == "9" and not char.isdigit():
            return "This position accepts digits only."
        if mask_char == "A" and not (char.isalpha() and char.isupper()):
            return "This position accepts uppercase letters only."
        if mask_char == "a" and not char.isalpha():
            return "This position accepts letters only."
    return ""


# -- default, incremento, calcoli ------------------------------------------


def default_value(rule: FieldRule, database, values: dict[str, str]) -> str:
    """Valore proposto per un nuovo record; stringa vuota se non c'è regola."""
    if rule.default_mode == "Value":
        try:
            return parse_value(database.field(rule.field_name), rule.default)
        except FieldError:
            return ""
    if rule.default_mode == "Expression" and rule.default.strip():
        try:
            value = _evaluate_text(rule.default, database, values)
        except ExprError:
            return ""
        return _canonical(database.field(rule.field_name), value)
    return ""


def next_increment(rule: FieldRule, database, field: Field) -> str:
    """Prossimo valore per Increment = Records, dall'ultimo record fisico."""
    last = ""
    for _seq, _deleted, values in database.iter_values(include_deleted=True):
        last = values.get(field.name, "")
    return increment_value(field, last, rule.template)


def increment_value(field: Field, value: str, template: str = "") -> str:
    """Incrementa un valore numerico, data o alfanumerico (base 36)."""
    value = value or ""
    if field.type == "D":
        if not value:
            return date.today().strftime("%Y%m%d")
        try:
            current = date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        except (ValueError, IndexError):
            return date.today().strftime("%Y%m%d")
        return (current + timedelta(days=1)).strftime("%Y%m%d")
    if field.type == "N":
        try:
            number = Decimal(value) if value.strip() else Decimal(0)
        except InvalidOperation:
            number = Decimal(0)
        number += 1
        return f"{number:.{field.decimals}f}"
    if field.type != "C":
        return value

    positions = editable_positions(template)
    data = template_data(template, value) if template else value
    if template and not data:
        data = " " * len(positions)
    if not data:
        data = ""
    incremented = _increment_alphanumeric(data)
    if template:
        return template_display(template, incremented)
    return incremented


def _increment_alphanumeric(text: str) -> str:
    if not text:
        return "1"
    chars = list(text.upper())
    carry = True
    for index in range(len(chars) - 1, -1, -1):
        char = chars[index]
        if not char.isalnum():
            continue
        if char.isdigit():
            if char == "9":
                chars[index] = "0"
            else:
                chars[index] = chr(ord(char) + 1)
                carry = False
                break
        elif "A" <= char <= "Z":
            if char == "Z":
                chars[index] = "A"
            else:
                chars[index] = chr(ord(char) + 1)
                carry = False
                break
    if carry:
        chars.insert(0, "1" if text[:1].isdigit() else "A")
    return "".join(chars)


def recalculate(rules: dict[str, FieldRule], database,
                values: dict[str, str]) -> dict[str, str]:
    """Ricalcola i campi Calculated, ripetendo per le dipendenze a catena."""
    calculated = [(name, rule) for name, rule in rules.items()
                  if rule.calculated]
    for _pass in range(4):
        changed = False
        for name, rule in calculated:
            if name not in {item.name for item in database.fields}:
                continue
            if not rule.expression.strip():
                continue
            try:
                value = _evaluate_text(rule.expression, database, values)
            except ExprError:
                continue
            canonical = _canonical(database.field(name), value)
            if canonical != values.get(name, ""):
                values[name] = canonical
                changed = True
        if not changed:
            break
    return values


# -- obbligatorietà, validazione, skip -------------------------------------


def is_required(rule: FieldRule, database, values: dict[str, str]) -> bool:
    """La regola richiede il campo (indipendentemente dal fatto che sia pieno)."""
    if rule.required == "Yes":
        return True
    if rule.required == "Expression" and rule.required_expression.strip():
        return _evaluate_boolean(rule.required_expression, database, values)
    return False


def missing_required(rule: FieldRule, database,
                     values: dict[str, str]) -> bool:
    return (is_required(rule, database, values)
            and not (values.get(rule.field_name, "") or "").strip())


def validation_error(rule: FieldRule, database,
                     values: dict[str, str]) -> str:
    """Messaggio di errore o stringa vuota se la validazione passa."""
    expression = (rule.validation or "").strip()
    if not expression:
        return ""
    try:
        valid = truthy(evaluate(expression,
                                context_for(database, values)))
    except ExprError as exc:
        return f"Validation expression: {exc}"
    if valid:
        return ""
    return rule.validation_message.strip() or "The value does not pass validation."


def double_entry_required(rule: FieldRule, database,
                          values: dict[str, str]) -> bool:
    if rule.double_entry == "Yes":
        return True
    if rule.double_entry == "Expression" \
            and rule.double_entry_expression.strip():
        return _evaluate_boolean(rule.double_entry_expression, database, values)
    return False


def should_skip(rule: FieldRule, database, values: dict[str, str]) -> bool:
    if not rule.skip_expression.strip():
        return False
    return _evaluate_boolean(rule.skip_expression, database, values)


def auto_popup(rule: FieldRule, database, values: dict[str, str], *,
               mode: str) -> bool:
    if not rule.lookup:
        return False
    if rule.auto_popup == "Yes":
        return mode == "enter"
    if rule.auto_popup == "Expression" and rule.popup_entry.strip():
        return _evaluate_boolean(rule.popup_entry, database, values)
    return False


# -- lookup -----------------------------------------------------------------


@dataclass
class LookupChoices:
    """Vista pronta per la finestra di lookup."""

    headers: list[str]
    rows: list[list[str]]
    values: list[str]
    source: str
    table: bool = False
    path: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.values


def _active_table(rule: FieldRule, database,
                  values: dict[str, str]) -> tuple[LookupTable, str]:
    if rule.advanced == "Conditional table":
        for group in rule.conditional_tables:
            if not group.expression.strip() or _evaluate_boolean(
                    group.expression, database, values):
                return group.table, group.filter
    return rule.table, ""


def _filter_table_rows(database, values: dict[str, str], table: LookupTable,
                       filter_expression: str) -> list[list[str]]:
    table.normalize()
    if not filter_expression.strip():
        return [list(row) for row in table.rows]
    fields = list(database.fields)
    mapping: dict[str, str] = {}
    for index, name in enumerate([database.fields[0].name if database.fields
                                  else "LOOKUP"] + table.columns):
        synthetic = f"LKU{index}"
        mapping[name.upper()] = synthetic
        fields.append(Field(synthetic, "C", 1))
    expression = re.sub(
        r"LOOKUP\s*->\s*([A-Za-z][A-Za-z0-9_]*)",
        lambda match: mapping.get(match.group(1).upper(), match.group(0)),
        filter_expression)
    kept: list[list[str]] = []
    for row in table.rows:
        row_values = dict(values)
        names = ([database.fields[0].name if database.fields else "LOOKUP"]
                 + table.columns)
        for name, cell in zip(names, row):
            row_values[mapping.get(name.upper(), name.upper())] = cell
            row_values[name.upper()] = values.get(name.upper(), "")
        try:
            keep = truthy(evaluate(expression,
                                   Context(fields=tuple(fields),
                                           values=row_values,
                                           pattern=database.workspace.pattern_mode)))
        except ExprError:
            keep = True
        if keep:
            kept.append(list(row))
    return kept


def _cascading_tree(rule: FieldRule) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    stack: list[tuple[int, dict[str, Any]]] = []
    for entry in rule.cascading[:MAX_CASCADING_LINES]:
        text = entry.text
        if not text.strip():
            continue
        node = {"text": text, "depth": entry.depth, "children": []}
        while stack and stack[-1][0] >= entry.depth:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            roots.append(node)
        stack.append((entry.depth, node))
    return roots


def _node_parts(text: str) -> tuple[str, str | None, bool]:
    path = text.endswith(PATH_MARKER)
    if path:
        text = text[:-1]
    if VALUE_MARKER in text:
        label, value = text.split(VALUE_MARKER, 1)
        return label, value, path
    return text, None, path


def cascading_choices(rule: FieldRule, path: tuple[str, ...]
                      ) -> tuple[list[str], list[bool]]:
    """Etichette visibili al livello `path` e se sono endpoint."""
    nodes = _cascading_tree(rule)
    for part in path:
        selected = next((node for node in nodes
                         if _node_parts(node["text"])[0] == part), None)
        if selected is None:
            nodes = []
            break
        nodes = selected["children"]
    labels = [_node_parts(node["text"])[0] for node in nodes]
    endpoints = [not node["children"] for node in nodes]
    return labels, endpoints


def cascading_value(rule: FieldRule, path: tuple[str, ...],
                    label: str) -> tuple[str, bool]:
    """Valore da scrivere e se la scelta è un endpoint."""
    nodes = _cascading_tree(rule)
    exit_path = path
    for part in path:
        selected = next((node for node in nodes
                         if _node_parts(node["text"])[0] == part), None)
        if selected is None:
            return "", False
        nodes = selected["children"]
    selected = next((node for node in nodes
                     if _node_parts(node["text"])[0] == label), None)
    if selected is None:
        return "", False
    _label, value, full_path = _node_parts(selected["text"])
    if selected["children"]:
        return "", False
    if full_path:
        return ". ".join(list(exit_path) + [label]), True
    return (value if value is not None else label), True


def _cascading_values(rule: FieldRule) -> list[str]:
    values: list[str] = []

    def walk(nodes: list[dict[str, Any]], path: list[str]) -> None:
        for node in nodes:
            label, value, full_path = _node_parts(node["text"])
            if node["children"]:
                walk(node["children"], path + [label])
            elif full_path:
                values.append(". ".join(path + [label]))
            else:
                values.append(value if value is not None else label)

    walk(_cascading_tree(rule), [])
    return values


def _lookup_key_field(rule: FieldRule, target) -> str:
    for row in rule.mapping:
        if row.filled_field.upper() == rule.field_name:
            return row.choice_field.upper()
    if rule.field_name in {item.name for item in target.fields}:
        return rule.field_name
    return target.fields[0].name


def _lookup_database(rule: FieldRule, database,
                     values: dict[str, str]) -> tuple[str, str, str, str]:
    name = rule.lookup_database
    linking = rule.linking_index
    display = rule.display_index
    filter_expression = ""
    if rule.advanced == "Conditional database":
        for group in rule.conditional_databases:
            if group.expression.strip() and _evaluate_boolean(
                    group.expression, database, values):
                name = group.database or name
                linking = group.linking_index or linking
                display = group.display_index or display
                filter_expression = group.filter
                break
    return name, linking, display, filter_expression


def _open_lookup_database(workspace, name: str):
    name = (name or "").strip().upper()
    if name.endswith(".DBF"):
        name = name[:-4]
    if not name:
        return None
    database = workspace.get(name)
    if database is not None:
        return database
    path = workspace.directory / f"{name}.DBF"
    if path.exists():
        try:
            return workspace.open_database(path)
        except Exception:
            return None
    return None


def _database_rows(rule: FieldRule, database, values: dict[str, str],
                   target, linking: str, display: str,
                   filter_expression: str) -> tuple[list[str], list[list[str]],
                                                    list[str]]:
    from . import indexing

    key_field = _lookup_key_field(rule, target)
    mapped = [row for row in rule.mapping if row.display]
    if not any(row.filled_field.upper() == rule.field_name
               for row in mapped):
        mapped.insert(0, MappingRow(key_field, rule.field_name))
    headers = [row.choice_field or row.filled_field for row in mapped]
    order = display or linking
    seqs = list(target.sequences())
    if order:
        definition = indexing.find_index(target, order)
        if definition is not None:
            try:
                seqs = indexing.ordered_sequences(
                    target, indexing.RangeSettings(primary=definition.name))
            except indexing.IndexError_:
                pass
    rows: list[list[str]] = []
    choice_values: list[str] = []
    for seq in seqs:
        record = target.read(seq)
        if filter_expression.strip():
            try:
                if not truthy(evaluate(
                        filter_expression,
                        Context(fields=target.fields, values=record,
                                pattern=target.workspace.pattern_mode,
                                seq=seq))):
                    continue
            except ExprError:
                pass
        key = record.get(key_field, "")
        cells: list[str] = []
        for row in mapped:
            name = (row.expression or row.choice_field).strip()
            cell = record.get(name.upper(), "") if name else ""
            if row.expression.strip():
                try:
                    cell = key_text(evaluate(
                        row.expression,
                        Context(fields=target.fields, values=record,
                                pattern=target.workspace.pattern_mode,
                                seq=seq)))
                except ExprError:
                    cell = ""
            cells.append(cell)
        rows.append(cells)
        choice_values.append(key)
    for index, value in enumerate(choice_values):
        if not rows[index]:
            rows[index] = [value]
        else:
            rows[index][0] = value
    return headers, rows, choice_values


def lookup_choices(rule: FieldRule, database, values: dict[str, str],
                   path: tuple[str, ...] = ()) -> LookupChoices:
    """Scelte da mostrare nella finestra di lookup per il campo."""
    source = rule.lookup_source
    if source == "Table":
        labels, endpoints = cascading_choices(rule, path)
        if labels:
            return LookupChoices(["Choice"], [[label] for label in labels],
                                 labels, "Cascading", table=True, path=path)
        table, filter_expression = _active_table(rule, database, values)
        rows = _filter_table_rows(database, values, table, filter_expression)
        headers = [rule.field_name] + list(table.columns)
        return LookupChoices(headers, rows, [row[0] for row in rows],
                             "Table", table=True)
    if source == "Database":
        name, linking, display, filter_expression = _lookup_database(
            rule, database, values)
        target = _open_lookup_database(database.workspace, name)
        if target is None:
            return LookupChoices([], [], [], "Database")
        headers, rows, choice_values = _database_rows(
            rule, database, values, target, linking, display,
            filter_expression)
        return LookupChoices(headers, rows, choice_values, "Database")
    # Advanced: cascading ha la precedenza; poi tabelle/database condizionali.
    if rule.advanced == "Cascading table":
        labels, _endpoints = cascading_choices(rule, path)
        return LookupChoices(["Choice"], [[label] for label in labels],
                             labels, "Cascading", table=True, path=path)
    if rule.advanced == "Conditional database":
        name, linking, display, filter_expression = _lookup_database(
            rule, database, values)
        target = _open_lookup_database(database.workspace, name)
        if target is None:
            return LookupChoices([], [], [], "Database")
        headers, rows, choice_values = _database_rows(
            rule, database, values, target, linking, display,
            filter_expression)
        return LookupChoices(headers, rows, choice_values, "Database")
    table, filter_expression = _active_table(rule, database, values)
    rows = _filter_table_rows(database, values, table, filter_expression)
    headers = [rule.field_name] + list(table.columns)
    return LookupChoices(headers, rows, [row[0] for row in rows],
                         "Table", table=True)


def lookup_fill(rule: FieldRule, database, values: dict[str, str],
                choice: str, path: tuple[str, ...] = ()) -> dict[str, str]:
    """Campi da riempire scegliendo `choice` dalla finestra di lookup."""
    filled: dict[str, str] = {rule.field_name: choice}
    if rule.lookup_source == "Table" or rule.advanced in (
            "Cascading table", "Conditional table"):
        if rule.advanced == "Cascading table":
            value, endpoint = cascading_value(rule, path, choice)
            if not endpoint:
                return {}
            choice = value
            filled[rule.field_name] = value
        table, _filter_expression = _active_table(rule, database, values)
        row = table.find(choice)
        if row is not None:
            for name, cell in zip(table.columns, row[1:]):
                try:
                    filled[name] = parse_value(database.field(name), cell)
                except (FieldError, KeyError):
                    continue
        return filled
    if rule.lookup_source == "Database" \
            or rule.advanced == "Conditional database":
        name, linking, display, filter_expression = _lookup_database(
            rule, database, values)
        target = _open_lookup_database(database.workspace, name)
        if target is None:
            return filled
        key_field = _lookup_key_field(rule, target)
        record = None
        for seq in target.sequences():
            candidate = target.read(seq)
            if candidate.get(key_field, "").strip().upper() == choice.strip().upper():
                record = candidate
                break
        if record is None:
            return filled
        for mapping in rule.mapping:
            if not mapping.condition.strip() or not _evaluate_boolean(
                    mapping.condition, database, values, default=True):
                continue
            if mapping.expression.strip():
                try:
                    value = key_text(evaluate(
                        mapping.expression,
                        Context(fields=target.fields, values=record,
                                pattern=target.workspace.pattern_mode)))
                except ExprError:
                    continue
            else:
                value = record.get(mapping.choice_field.upper(), "")
            if mapping.filled_field.upper() == rule.field_name:
                filled[rule.field_name] = value
                continue
            try:
                filled[mapping.filled_field] = parse_value(
                    database.field(mapping.filled_field), value)
            except (FieldError, KeyError):
                continue
        return filled
    return filled


def lookup_validation_error(rule: FieldRule, database,
                            values: dict[str, str]) -> str:
    """Errore quando il valore viola Lookup Validation Exists/Doesn't Exist."""
    if not rule.lookup or rule.lookup_validation == "None":
        return ""
    value = values.get(rule.field_name, "")
    if not value.strip():
        return ""
    choices = lookup_choices(rule, database, values)
    possible = (choices.values if not rule.cascading
                else _cascading_values(rule))
    present = any(item.strip().upper() == value.strip().upper()
                  for item in possible)
    if rule.lookup_validation == "Exists" and not present:
        return (f"{value} is not in the lookup "
                f"{'table' if choices.table else 'database'}.")
    if rule.lookup_validation == "Doesn't Exist" and present:
        return (f"{value} is already in the lookup "
                f"{'table' if choices.table else 'database'}.")
    return ""


# -- post data --------------------------------------------------------------


def post_values(rule: FieldRule, database, old_values: dict[str, str],
                new_values: dict[str, str], field_rule: FieldRule) -> list[str]:
    """Esegue le regole di post data del campo; ritorna avvisi."""
    warnings: list[str] = []
    if not field_rule.post_data:
        return warnings
    for posting in field_rule.postings:
        if not posting.database.strip() or not posting.field.strip():
            continue
        if posting.condition.strip() and not _evaluate_boolean(
                posting.condition, database, new_values):
            continue
        target = _open_lookup_database(database.workspace, posting.database)
        if target is None:
            warnings.append(f"Post data: database {posting.database} not found.")
            continue
        try:
            target.field(posting.field)
        except KeyError:
            warnings.append(
                f"Post data: field {posting.field} not found in "
                f"{posting.database}.")
            continue
        if posting.expression.strip():
            try:
                posted = _evaluate_text(posting.expression, database,
                                        new_values)
            except ExprError as exc:
                warnings.append(f"Post data: {exc}")
                continue
        else:
            posted = new_values.get(rule.field_name, "")
        old = old_values.get(rule.field_name, "")
        amount = _decimal(posted)
        if old_values and _decimal(old) is not None and amount is not None:
            amount = amount - _decimal(old)
        seq = _find_post_target(target, database, new_values, posting,
                                rule.field_name)
        if seq is None:
            warnings.append(
                f"Post data: no matching record in {posting.database}.")
            continue
        record = target.read(seq)
        current = _decimal(record.get(posting.field, ""))
        if posting.mode == "Replace" or current is None or amount is None:
            new_value = key_text(posted) if posting.mode == "Replace" else (
                record.get(posting.field, ""))
        elif posting.mode == "Add":
            new_value = f"{current + amount:.{target.field(posting.field).decimals}f}"
        else:
            new_value = f"{current - amount:.{target.field(posting.field).decimals}f}"
        try:
            record[posting.field] = parse_value(
                target.field(posting.field), new_value)
            target.update(seq, record)
            target.workspace.save_database(target)
        except Exception as exc:  # pragma: no cover - I/O
            warnings.append(f"Post data: {exc}")
    return warnings


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    text = key_text(value).strip()
    if not text:
        return Decimal(0)
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _find_post_target(target, database, values: dict[str, str],
                      posting: PostingRule,
                      source_field: str = "") -> int | None:
    common = (posting.common or "").strip()
    if common:
        try:
            value = _evaluate_text(common, database, values)
        except ExprError:
            return None
    else:
        value = values.get(source_field, "")
    marker = key_text(value).strip().upper()
    definition = None
    if posting.linking_index.strip():
        from . import indexing
        definition = indexing.find_index(target, posting.linking_index)
    if definition is None:
        seqs = target.sequences()
        return seqs[0] if seqs else None
    for seq in target.sequences():
        record = target.read(seq)
        try:
            key = indexing.index_key(target, definition, record, seq=seq)
        except indexing.IndexError_:
            continue
        if key.strip().upper() == marker:
            return seq
    return None


# -- rievaluazione ----------------------------------------------------------


def re_evaluate(database, rules: dict[str, FieldRule]) -> tuple[int, list[str]]:
    """Applica le regole correnti ai record esistenti (calcoli e maiuscole)."""
    changed = 0
    problems: list[str] = []
    for seq, _deleted, values in list(database.iter_values()):
        updated = dict(values)
        recalculate(rules, database, updated)
        for name, rule in rules.items():
            if name not in updated or name not in {
                    item.name for item in database.fields}:
                continue
            field = database.field(name)
            if field.type == "C" and rule.case != "None":
                updated[name] = apply_case(updated[name], rule.case)
            if rule.template and not updated[name].strip():
                updated[name] = ""
            error = validation_error(rule, database, updated)
            if error:
                problems.append(f"Record {seq}, {name}: {error}")
        if updated != values:
            database.update(seq, updated)
            changed += 1
    if changed:
        database.workspace.save_database(database)
    return changed, problems


__all__ = [
    "ADVANCED_OPTIONS",
    "AUTO_POPUP_MODES",
    "CASE_MODES",
    "CascadingEntry",
    "ConditionalDatabase",
    "ConditionalGroup",
    "DEFAULT_MODES",
    "DOUBLE_ENTRY_MODES",
    "FieldRule",
    "INCREMENT_MODES",
    "LOOKUP_LOCATIONS",
    "LOOKUP_SOURCES",
    "LOOKUP_VALIDATIONS",
    "LookupChoices",
    "LookupTable",
    "MAX_CASCADING_LINES",
    "MAX_LOOKUP_COLUMNS",
    "MAX_LOOKUP_ROWS",
    "MappingRow",
    "POST_MODES",
    "PostingRule",
    "REQUIRED_MODES",
    "RuleError",
    "VALUE_MODES",
    "apply_case",
    "auto_popup",
    "cascading_choices",
    "context_for",
    "default_value",
    "double_entry_required",
    "editable_positions",
    "increment_value",
    "is_required",
    "lookup_choices",
    "lookup_fill",
    "lookup_validation_error",
    "mask_error",
    "missing_required",
    "mask_slots",
    "next_increment",
    "post_values",
    "re_evaluate",
    "recalculate",
    "resolve_rule",
    "resolve_rules",
    "should_skip",
    "template_data",
    "template_display",
    "template_is_blank",
    "validation_error",
]
