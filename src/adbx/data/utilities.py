"""Utility sui dati (O9): copia, append, summarize, crosstab e relazionali.

Le operazioni lavorano sullo strato record del workspace e producono, quando
il manuale lo richiede, un nuovo database. Il range attivo decide quali
record leggere; il nuovo database viene creato con la stessa semantica dei
database normali (tabella SQLite, indici calcolati al volo, `.DBF` riscritto).

Riferimenti: Reference Manual, capitoli 19 (Utilities) e 21 (Relational
Commands). Le deviazioni sono elencate in `docs/spec/11-utility-io.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Iterable, Sequence

from . import indexing
from .expressions import (
    Context,
    ExprError,
    evaluate,
    key_text,
    sort_key,
    truthy,
)
from .fields import Field, FieldError, validate_fields
from .workspace import Database, WorkspaceError

SUMMARY_OPERATIONS = (
    "Group", "Total", "Count", "Average", "Biggest", "Smallest",
    "First", "Last", "Null",
)
CROSSTAB_OPERATIONS = (
    "Count", "Biggest", "Smallest", "Null", "First", "Last", "Total",
    "Average",
)
APPEND_MODES = (
    "All",
    "Unique",
    "Replace existing, add unique",
    "Replace existing, mark unique",
)
POST_OPERATIONS = ("Add", "Subtract", "Replace")
RELATIONAL_MODES = ("Join", "Intersect", "Subtract")


class UtilityError(ValueError):
    """Operazione utility non eseguibile."""


@dataclass
class UtilityResult:
    """Esito di un'operazione, con i conteggi mostrati dal manuale."""

    operation: str
    output: Database | None = None
    read: int = 0
    written: int = 0
    updated: int = 0
    replaced: int = 0
    skipped: int = 0
    unmatched: int = 0
    marked: int = 0

    def message(self) -> str:
        parts = [f"{self.operation}: {self.written} record(s) written"]
        if self.read and self.read != self.written:
            parts.append(f"{self.read} read")
        if self.updated:
            parts.append(f"{self.updated} updated")
        if self.replaced:
            parts.append(f"{self.replaced} replaced")
        if self.unmatched:
            parts.append(f"{self.unmatched} unmatched")
        if self.marked:
            parts.append(f"{self.marked} marked deleted")
        if self.skipped:
            parts.append(f"{self.skipped} skipped")
        if self.output is not None:
            parts.append(f"new database {self.output.name}")
        return "; ".join(parts) + "."


# -- campi e valori ---------------------------------------------------------


def summary_field(source: Field, operation: str) -> Field:
    """Campo del database di summary per una data operazione."""
    operation = operation.strip().title()
    if operation not in SUMMARY_OPERATIONS:
        raise UtilityError(f"Unknown summary operation: {operation}")
    if operation in ("Total", "Average"):
        if source.type != "N":
            raise UtilityError(
                f"{operation} needs a numeric field: {source.name}.")
        length = min(19, source.length + 2)
        decimals = source.decimals
        if decimals >= length:
            decimals = max(0, length - 2)
        return Field(source.name, "N", length, decimals)
    if operation == "Count":
        return Field(source.name, "N", min(19, max(6, source.length)), 0)
    return Field(source.name, source.type, source.length, source.decimals)


def crosstab_field(source: Field, operation: str, name: str) -> Field:
    operation = operation.strip().title()
    if operation not in CROSSTAB_OPERATIONS:
        raise UtilityError(f"Unknown crosstab operation: {operation}")
    if operation == "Count":
        return Field(name, "N", 8, 0)
    if operation in ("Total", "Average"):
        if source.type != "N":
            raise UtilityError(
                f"{operation} needs a numeric field: {source.name}.")
        length = min(19, source.length + 2)
        decimals = source.decimals
        if decimals >= length:
            decimals = max(0, length - 2)
        return Field(name, "N", length, decimals)
    return Field(name, source.type, source.length, source.decimals)


def _decimal(value: str | Decimal | None) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value or "0").strip() or "0")
    except InvalidOperation as exc:
        raise UtilityError(f"Not a number: {value}") from exc


def _number_text(value: Decimal, decimals: int, length: int) -> str:
    with localcontext() as context:
        context.prec = 40
        quantum = Decimal(1).scaleb(-decimals)
        number = value.quantize(quantum, rounding=ROUND_HALF_UP)
    if number == 0:
        number = abs(number)
    text = f"{number:.{decimals}f}"
    if len(text) > length:
        # Il manuale avverte: un totale troppo grande mostra zero.
        text = f"{Decimal(0):.{decimals}f}"
    return text


def _numeric_value(field: Field, value: str) -> Decimal:
    try:
        return Decimal((value or "0").strip() or "0")
    except InvalidOperation:
        return Decimal(0)


def _canonical(field: Field, value: object) -> str:
    """Converte un valore tipizzato nel testo canonico del campo."""
    if value is None:
        return ""
    if field.type == "N":
        number = _decimal(value) if not isinstance(value, bool) else Decimal(int(value))
        return _number_text(number, field.decimals, field.length)
    if field.type == "D":
        if hasattr(value, "strftime"):
            return value.strftime("%Y%m%d")
        text = str(value).strip()
        return text if len(text) == 8 and text.isdigit() else ""
    if field.type == "L":
        if isinstance(value, bool):
            return "1" if value else "0"
        text = str(value).strip().upper()
        if text in ("1", "T", "Y", "YES", "TRUE"):
            return "1"
        if text in ("0", "F", "N", "NO", "FALSE"):
            return "0"
        return ""
    text = str(value)
    if field.type == "C":
        return text[:field.length]
    return text


def _context(database: Database, values: dict[str, str], *, padded: bool = True,
             seq: int = 0, deleted: bool = False) -> Context:
    return Context(
        fields=database.fields, values=values,
        pattern=database.workspace.pattern_mode, padded=padded,
        seq=seq, deleted=deleted,
        count=database.count(include_deleted=True),
    )


def _ordered(database: Database, settings: indexing.RangeSettings | None = None
             ) -> list[int]:
    try:
        return indexing.ordered_sequences(database, settings)
    except indexing.IndexError_ as exc:
        raise UtilityError(str(exc)) from exc


def _primary_key(database: Database, seq: int, values: dict[str, str]) -> str:
    definition = _grouping_index(database)
    return indexing.index_key(database, definition, values, seq=seq)


def _grouping_index(database: Database) -> indexing.IndexDefinition:
    primary = database.primary_index
    if primary in (indexing.RECORD_NUMBER, indexing.SEARCH_LIST) \
            or primary.startswith(indexing.SEARCH_PREFIX):
        raise UtilityError(
            "Select a real index as primary index: Record Number and "
            "Search/Sort lists cannot group records.")
    definition = indexing.find_index(database, primary)
    if definition is None:
        raise UtilityError(f"Index {primary} does not exist.")
    return definition


def _unique_name(name: str, used: set[str]) -> str:
    base = "".join(char if char.isalnum() or char == "_" else "_"
                   for char in name.upper()).lstrip("_")
    if not base:
        base = "FIELD"
    if base[0].isdigit():
        base = "F" + base
    base = base[:10]
    candidate = base
    counter = 2
    while candidate in used:
        suffix = str(counter)
        candidate = (base[: max(1, 10 - len(suffix))] + suffix)
        counter += 1
    used.add(candidate)
    return candidate


def _create_output(database: Database, name: str,
                   fields: Sequence[Field], *, description: str = "") -> Database:
    fields = list(fields)
    try:
        validate_fields(fields)
    except FieldError as exc:
        raise UtilityError(str(exc)) from exc
    try:
        output = database.workspace.create_database(
            name, fields, description=description)
    except (WorkspaceError, OSError) as exc:
        raise UtilityError(str(exc)) from exc
    return output


def _write_output(output: Database, rows: Iterable[dict[str, str]],
                  *, deleted: bool = False) -> int:
    count = 0
    for values in rows:
        seq = output.append(values)
        if deleted:
            output.set_deleted(seq, True)
        count += 1
    output.workspace.save_database(output)
    return count


# -- copy -------------------------------------------------------------------


@dataclass(frozen=True)
class CopyField:
    database: str
    field: str


@dataclass
class CopyOptions:
    name: str
    description: str = ""
    inherit_support: bool = False
    fields: list[CopyField] | None = None
    settings: indexing.RangeSettings | None = None
    set_definition: object | None = None


def copy_database(database: Database, options: CopyOptions) -> UtilityResult:
    """Copia record (e campi scelti) in un nuovo database."""
    sources: list[tuple[CopyField, Field]] = []
    set_definition = options.set_definition
    if options.fields is not None:
        for item in options.fields:
            source_db = (set_definition.database(item.database)
                         if set_definition is not None
                         else (database if item.database.upper() == database.name
                               else database.workspace.get(item.database)))
            if source_db is None:
                raise UtilityError(f"Database {item.database} does not exist.")
            try:
                sources.append((item, source_db.field(item.field)))
            except KeyError as exc:
                raise UtilityError(f"Field {item.field} does not exist.") from exc
    else:
        source_db = (set_definition.primary_database
                     if set_definition is not None else database)
        for definition in source_db.fields:
            sources.append((CopyField(source_db.name, definition.name),
                            definition))

    used: set[str] = set()
    output_fields: list[Field] = []
    names: list[str] = []
    for _item, definition in sources:
        name = _unique_name(definition.name, used)
        names.append(name)
        output_fields.append(definition.with_name(name))

    output = _create_output(database, options.name, output_fields,
                            description=options.description)
    seqs = _ordered(database, options.settings)
    rows: list[dict[str, str]] = []
    for seq in seqs:
        values = database.read(seq)
        flat: dict[tuple[str, str], str] | None = None
        if set_definition is not None:
            flat = set_definition.flat_values(values)
        record: dict[str, str] = {}
        for (item, _definition), target in zip(sources, output_fields):
            if flat is not None and item.database.upper() != database.name.upper():
                value = flat.get((item.database.upper(), item.field.upper()), "")
            else:
                value = values.get(item.field.upper(), "")
            record[target.name] = value
        rows.append(record)
    written = _write_output(output, rows)
    if options.inherit_support and set_definition is None:
        database.workspace.copy_support_files(database.name, output.name)
    return UtilityResult("Copy", output=output, read=len(seqs), written=written)


# -- append -----------------------------------------------------------------


@dataclass(frozen=True)
class AppendMapping:
    target: str
    source: str = ""


@dataclass
class AppendOptions:
    mode: str = "All"
    filter: str = ""
    mappings: list[AppendMapping] | None = None


def default_mappings(target: Database, source: Database) -> list[AppendMapping]:
    source_names = {field.name for field in source.fields}
    return [AppendMapping(field.name,
                          field.name if field.name in source_names else "")
            for field in target.fields]


def append_database(target: Database, source: Database,
                    options: AppendOptions) -> UtilityResult:
    """Aggiunge i record del database esterno al database corrente."""
    mode = options.mode
    if mode not in APPEND_MODES:
        raise UtilityError(f"Unknown append mode: {mode}")
    mappings = options.mappings or default_mappings(target, source)
    known = {field.name for field in target.fields}
    for mapping in mappings:
        if mapping.target.upper() not in known:
            raise UtilityError(f"Field {mapping.target} does not exist.")
        if mapping.source and mapping.source.upper() not in {
                field.name for field in source.fields}:
            raise UtilityError(f"Field {mapping.source} does not exist.")

    grouping = None
    if mode != "All":
        grouping = _grouping_index(target)

    existing: dict[str, list[int]] = {}
    if grouping is not None:
        for seq in target.sequences(include_deleted=True):
            values = target.read(seq)
            try:
                key = indexing.index_key(target, grouping, values, seq=seq)
            except indexing.IndexError_:
                continue
            marker = key if grouping.case_sensitive else key.upper()
            existing.setdefault(marker, []).append(seq)

    result = UtilityResult("Append", output=target)
    source_seqs = source.sequences(include_deleted=False)
    result.read = len(source_seqs)
    replaced: set[int] = set()
    appended: list[int] = []
    for seq in source_seqs:
        values = source.read(seq)
        if options.filter.strip():
            try:
                if not truthy(evaluate(options.filter,
                                       _context(source, values, padded=False,
                                                seq=seq))):
                    continue
            except ExprError:
                continue
        record: dict[str, str] = {}
        for mapping in mappings:
            if not mapping.source:
                continue
            try:
                record[mapping.target.upper()] = values.get(
                    mapping.source.upper(), "")
            except KeyError:
                record[mapping.target.upper()] = ""
        key = None
        if grouping is not None:
            # La chiave si calcola sui valori che il record avrà nel master;
            # i campi non mappati restano vuoti.
            merged = {field.name: "" for field in target.fields}
            merged.update(record)
            try:
                key = indexing.index_key(target, grouping, merged)
            except indexing.IndexError_:
                key = None
            if key is not None and not grouping.case_sensitive:
                key = key.upper()
        if mode == "All" or key is None:
            appended.append(target.append(record))
            continue
        matches = existing.get(key, [])
        if not matches:
            new_seq = target.append(record)
            appended.append(new_seq)
            existing.setdefault(key, []).append(new_seq)
            if mode == "Replace existing, mark unique":
                source.set_deleted(seq, True)
                result.marked += 1
            continue
        if mode in ("Replace existing, add unique",
                    "Replace existing, mark unique"):
            for master_seq in matches:
                current = target.read(master_seq)
                for mapping in mappings:
                    if mapping.source:
                        current[mapping.target.upper()] = record.get(
                            mapping.target.upper(), "")
                target.update(master_seq, current)
                replaced.add(master_seq)
            result.replaced = len(replaced)
        # Unique e Replace...: i duplicati esterni non si aggiungono.
        result.skipped += 1
    target.workspace.save_database(target)
    if result.marked:
        source.workspace.save_database(source)
    result.written = len(appended)
    result.updated = len(replaced)
    result.output = target
    return result


# -- summarize --------------------------------------------------------------


@dataclass(frozen=True)
class SummaryField:
    field: str
    operation: str = "Group"


@dataclass
class SummarizeOptions:
    name: str
    fields: list[SummaryField]
    description: str = ""
    settings: indexing.RangeSettings | None = None
    set_definition: object | None = None


def _summary_value(source: Field, operation: str, values: list[str]) -> str:
    if operation == "Count":
        return _number_text(Decimal(len(values)), 0, min(19, max(6, source.length)))
    if operation == "Null":
        return ""
    if operation == "Group" or operation == "First":
        return values[0] if values else ""
    if operation == "Last":
        return values[-1] if values else ""
    if operation in ("Total", "Average"):
        total = sum((_numeric_value(source, value) for value in values),
                    Decimal(0))
        if operation == "Average":
            total = total / len(values) if values else Decimal(0)
        return _number_text(total, source.decimals, min(19, source.length + 2))
    if operation in ("Biggest", "Smallest"):
        if source.type == "N":
            numbers = [_numeric_value(source, value) for value in values]
            chosen = max(numbers) if operation == "Biggest" else min(numbers)
            return _number_text(chosen, source.decimals, source.length)
        texts = [value for value in values]
        chosen = max(texts) if operation == "Biggest" else min(texts)
        return chosen
    raise UtilityError(f"Unknown summary operation: {operation}")


def summarize(database: Database, options: SummarizeOptions) -> UtilityResult:
    """Crea un database con un record per chiave dell'indice primario."""
    definition = _grouping_index(database)
    sources: list[tuple[Field, str]] = []
    used: set[str] = set()
    output_fields: list[Field] = []
    for item in options.fields:
        operation = item.operation.strip().title()
        try:
            source = database.field(item.field)
        except KeyError as exc:
            raise UtilityError(f"Field {item.field} does not exist.") from exc
        target = summary_field(source, operation)
        name = _unique_name(target.name, used)
        output_fields.append(target.with_name(name))
        sources.append((source, operation))
    output = _create_output(database, options.name, output_fields,
                            description=options.description)
    rows = _summary_rows(database, definition, sources, options.settings)
    written = _write_output(output, rows)
    return UtilityResult("Summarize", output=output, read=len(
        _ordered(database, options.settings)), written=written)


def _summary_rows(database: Database, definition: indexing.IndexDefinition,
                  sources: list[tuple[Field, str]],
                  settings: indexing.RangeSettings | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: str | None = None
    bucket: list[dict[str, str]] = []
    for seq in _ordered(database, settings):
        values = database.read(seq)
        try:
            key = indexing.index_key(database, definition, values, seq=seq)
        except indexing.IndexError_:
            key = ""
        marker = key if definition.case_sensitive else key.upper()
        if current is None or marker != current:
            if bucket:
                rows.append(_summary_record(sources, bucket))
            current = marker
            bucket = []
        bucket.append(values)
    if bucket:
        rows.append(_summary_record(sources, bucket))
    return rows


def _summary_record(sources: list[tuple[Field, str]],
                    bucket: list[dict[str, str]]) -> dict[str, str]:
    record: dict[str, str] = {}
    used: set[str] = set()
    for source, operation in sources:
        name = _unique_name(source.name, used)
        values = [item.get(source.name, "") for item in bucket]
        record[name] = _summary_value(source, operation, values)
    return record


# -- crosstab ---------------------------------------------------------------


@dataclass(frozen=True)
class CrosstabColumn:
    name: str
    expression: str = ""


@dataclass
class CrosstabOptions:
    name: str
    row_field: str
    column_field: str
    tabulation_field: str
    operation: str = "Count"
    columns: list[CrosstabColumn] | None = None
    create_names: bool = False
    names_name: str = ""
    see_results: bool = False
    settings: indexing.RangeSettings | None = None


def crosstab(database: Database, options: CrosstabOptions) -> UtilityResult:
    """Riepiloga un campo su due dimensioni."""
    operation = options.operation.strip().title()
    if operation not in CROSSTAB_OPERATIONS:
        raise UtilityError(f"Unknown crosstab operation: {operation}")
    try:
        row_field = database.field(options.row_field)
        column_field = database.field(options.column_field)
        tab_field = database.field(options.tabulation_field)
    except KeyError as exc:
        raise UtilityError(f"Field {exc.args[0]} does not exist.") from exc

    seqs = _ordered(database, options.settings)
    records = [(seq, database.read(seq)) for seq in seqs]
    column_specs: list[tuple[str, str]] = []
    if options.columns:
        column_specs = [(item.name, item.expression) for item in options.columns]
    else:
        seen: dict[str, str] = {}
        for _seq, values in records:
            value = values.get(column_field.name, "")
            marker = key_text(_typed(column_field, value))
            if marker not in seen:
                seen[marker] = value
        for marker in sorted(seen, key=lambda item: sort_key(
                _typed(column_field, seen[item]))):
            column_specs.append((seen[marker], ""))

    used: set[str] = {row_field.name}
    output_fields = [row_field]
    column_names: list[str] = []
    for value, _expression in column_specs:
        name = _unique_name(value or "BLANK", used)
        column_names.append(name)
        output_fields.append(crosstab_field(tab_field, operation, name))

    row_groups: dict[str, tuple[str, list[dict[str, str]]]] = {}
    for _seq, values in records:
        row_value = values.get(row_field.name, "")
        marker = key_text(_typed(row_field, row_value))
        if marker not in row_groups:
            row_groups[marker] = (row_value, [])
        row_groups[marker][1].append(values)

    output = _create_output(database, options.name, output_fields)
    rows: list[dict[str, str]] = []
    for marker in sorted(row_groups, key=lambda item: sort_key(
            _typed(row_field, row_groups[item][0]))):
        row_value, group = row_groups[marker]
        record = {row_field.name: row_value}
        for (value, expression), name in zip(column_specs, column_names):
            selected: list[str] = []
            for values in group:
                if options.columns:
                    if not expression.strip():
                        continue
                    try:
                        if not truthy(evaluate(expression,
                                               _context(database, values,
                                                        padded=False))):
                            continue
                    except ExprError:
                        continue
                elif key_text(_typed(column_field,
                                     values.get(column_field.name, ""))) \
                        != key_text(_typed(column_field, value)):
                    continue
                selected.append(values.get(tab_field.name, ""))
            if operation == "Null":
                record[name] = ""
            elif operation == "Count":
                record[name] = _number_text(Decimal(len(selected)), 0, 8)
            else:
                record[name] = _summary_value(tab_field, operation, selected) \
                    if selected else ""
        rows.append(record)
    written = _write_output(output, rows)
    if options.create_names:
        names_name = options.names_name or f"{options.name}N"
        names_fields = [Field("SHORT", "C", 10), Field("FULL", "C", 60)]
        names_db = _create_output(database, names_name, names_fields)
        _write_output(names_db, [
            {"SHORT": name, "FULL": value}
            for (value, _expr), name in zip(column_specs, column_names)
        ])
    return UtilityResult("Crosstab", output=output, read=len(seqs),
                         written=written)


def _typed(field: Field, value: str):
    from .expressions import field_value

    return field_value(Context(fields=(field,), values={field.name: value}),
                       field.name)


# -- relational: post -------------------------------------------------------


@dataclass(frozen=True)
class PostField:
    master: str
    transaction: str = ""
    operation: str = "Replace"
    condition: str = ""


@dataclass
class PostOptions:
    common_expression: str = ""
    filter: str = ""
    status_field: str = ""
    mark_unmatched: bool = False
    fields: list[PostField] = field(default_factory=list)


def post(master: Database, transaction: Database,
         options: PostOptions) -> UtilityResult:
    """Aggiorna il master con i movimenti del database transazioni."""
    definition = _grouping_index(master)
    common = options.common_expression.strip() or definition.expression
    master_rows: dict[str, list[int]] = {}
    for seq in master.sequences(include_deleted=False):
        values = master.read(seq)
        try:
            key = key_text(evaluate(common, _context(master, values, seq=seq)))
        except ExprError as exc:
            raise UtilityError(f"Common expression: {exc}") from exc
        master_rows.setdefault(key, []).append(seq)

    fields: list[tuple[Field, Field, str, str]] = []
    for item in options.fields:
        try:
            master_field = master.field(item.master)
            transaction_field = transaction.field(item.transaction or item.master)
        except KeyError as exc:
            raise UtilityError(f"Field {exc.args[0]} does not exist.") from exc
        operation = item.operation.strip().title()
        if operation not in POST_OPERATIONS:
            raise UtilityError(f"Unknown post operation: {operation}")
        fields.append((master_field, transaction_field, operation,
                       item.condition))

    result = UtilityResult("Post", output=master)
    touched: set[int] = set()
    for seq in transaction.sequences(include_deleted=False):
        values = transaction.read(seq)
        if options.filter.strip():
            try:
                if not truthy(evaluate(options.filter,
                                       _context(transaction, values,
                                                padded=False, seq=seq))):
                    continue
            except ExprError:
                continue
        try:
            key = key_text(evaluate(
                options.common_expression.strip() or option_key(definition, transaction),
                _context(transaction, values, padded=True, seq=seq)))
        except ExprError:
            key = ""
        matches = master_rows.get(key, [])
        result.read += 1
        if not matches:
            result.unmatched += 1
            if options.mark_unmatched:
                transaction.set_deleted(seq, True)
                result.marked += 1
            continue
        for master_seq in matches:
            current = master.read(master_seq)
            for master_field, transaction_field, operation, condition in fields:
                if condition.strip():
                    try:
                        if not truthy(evaluate(condition,
                                               _context(transaction, values,
                                                        padded=False, seq=seq))):
                            continue
                    except ExprError:
                        continue
                source_value = values.get(transaction_field.name, "")
                if operation == "Replace":
                    current[master_field.name] = _canonical(
                        master_field, _typed(transaction_field, source_value))
                elif master_field.type == "N":
                    base = _numeric_value(master_field,
                                          current.get(master_field.name, ""))
                    delta = _numeric_value(transaction_field, source_value)
                    if operation == "Subtract":
                        delta = -delta
                    current[master_field.name] = _number_text(
                        base + delta, master_field.decimals,
                        master_field.length)
            master.update(master_seq, current)
            touched.add(master_seq)
        if options.status_field:
            try:
                status = transaction.field(options.status_field)
            except KeyError as exc:
                raise UtilityError(
                    f"Status field {options.status_field} does not exist.") from exc
            values[status.name] = "1"
            transaction.update(seq, values)
        result.written += 1
    result.updated = len(touched)
    result.output = master
    master.workspace.save_database(master)
    if options.status_field or options.mark_unmatched:
        transaction.workspace.save_database(transaction)
    return result


def option_key(definition: indexing.IndexDefinition,
               transaction: Database) -> str:
    """Espressione comune di default: quella dell'indice, se i campi esistono."""
    names = {field.name for field in transaction.fields}
    for field_name in _expression_fields(definition.expression):
        if field_name not in names:
            raise UtilityError(
                f"Transaction database has no field {field_name}; "
                "enter a common expression.")
    return definition.expression


def _expression_fields(expression: str) -> list[str]:
    from .expressions import tokenize

    return [value for kind, value in tokenize(expression)
            if kind == "ident" and value.upper() not in {
                "AND", "OR", "NOT", "T", "F"}]


# -- relational: join, intersect, subtract ---------------------------------


@dataclass(frozen=True)
class JoinField:
    database: str
    field: str


@dataclass
class RelationalOptions:
    mode: str
    name: str
    secondary_index: str
    common_expression: str = ""
    primary_fields: list[JoinField] | None = None
    secondary_fields: list[JoinField] | None = None
    settings: indexing.RangeSettings | None = None
    description: str = ""


def relational(primary: Database, secondary: Database,
               options: RelationalOptions) -> UtilityResult:
    """Join, Intersect o Subtract fra due database."""
    mode = options.mode.strip().title()
    if mode not in RELATIONAL_MODES:
        raise UtilityError(f"Unknown relational mode: {mode}")
    definition = indexing.find_index(secondary, options.secondary_index)
    if definition is None:
        raise UtilityError(
            f"Index {options.secondary_index} does not exist in "
            f"{secondary.name}.")
    common = options.common_expression.strip() or definition.expression
    primary_items = options.primary_fields or [
        JoinField(primary.name, field.name) for field in primary.fields]
    secondary_items = options.secondary_fields or [
        JoinField(secondary.name, field.name) for field in secondary.fields]

    used: set[str] = set()
    output_fields: list[Field] = []
    selected: list[tuple[str, str, Field]] = []
    for item in primary_items:
        source = primary if item.database.upper() == primary.name else None
        if source is None:
            raise UtilityError(f"Unknown database: {item.database}")
        try:
            field_def = primary.field(item.field)
        except KeyError as exc:
            raise UtilityError(f"Field {item.field} does not exist.") from exc
        name = _unique_name(field_def.name, used)
        output_fields.append(field_def.with_name(name))
        selected.append(("primary", field_def.name, output_fields[-1]))
    for item in secondary_items:
        try:
            field_def = secondary.field(item.field)
        except KeyError as exc:
            raise UtilityError(f"Field {item.field} does not exist.") from exc
        name = _unique_name(field_def.name, used)
        output_fields.append(field_def.with_name(name))
        selected.append(("secondary", field_def.name, output_fields[-1]))
    if not output_fields:
        raise UtilityError("Select at least one field for the result database.")
    if len(output_fields) > 128:
        raise UtilityError("The result database holds at most 128 fields.")

    buckets: dict[str, list[dict[str, str]]] = {}
    case_sensitive = definition.case_sensitive
    for seq in secondary.sequences(include_deleted=False):
        values = secondary.read(seq)
        try:
            if not indexing.index_filter_passes(
                    secondary, definition, values, seq=seq):
                continue
            key = indexing.index_key(secondary, definition, values, seq=seq)
        except indexing.IndexError_:
            continue
        if not case_sensitive:
            key = key.upper()
        buckets.setdefault(key, []).append(values)

    output = _create_output(primary, options.name, output_fields,
                            description=options.description)
    rows: list[dict[str, str]] = []
    read = 0
    for seq in _ordered(primary, options.settings):
        values = primary.read(seq)
        read += 1
        try:
            key = key_text(evaluate(common,
                                    _context(primary, values, seq=seq)))
        except ExprError as exc:
            raise UtilityError(f"Common expression: {exc}") from exc
        if not case_sensitive:
            key = key.upper()
        matches = buckets.get(key, [])
        if mode == "Subtract":
            if matches:
                continue
            rows.append(_relational_record(selected, values, {}))
        elif mode == "Intersect":
            for match in matches:
                rows.append(_relational_record(selected, values, match))
        else:
            if not matches:
                rows.append(_relational_record(selected, values, {}))
            else:
                for match in matches:
                    rows.append(_relational_record(selected, values, match))
    written = _write_output(output, rows)
    return UtilityResult(mode, output=output, read=read, written=written)


def _relational_record(selected: list[tuple[str, str, Field]],
                       primary: dict[str, str],
                       secondary: dict[str, str]) -> dict[str, str]:
    record: dict[str, str] = {}
    for side, source_name, target in selected:
        values = primary if side == "primary" else secondary
        record[target.name] = values.get(source_name, "")
    return record


# -- global update/delete ---------------------------------------------------


@dataclass(frozen=True)
class UpdateExpression:
    field: str
    expression: str


CASE_MODES = ("Upper case", "Lower case", "First character",
              "Word", "X Lower & First", "Z Lower & Word")


def update_fields(database: Database, updates: Sequence[UpdateExpression],
                  settings: indexing.RangeSettings | None = None) -> UtilityResult:
    if not updates:
        raise UtilityError("Enter at least one update expression.")
    if len(updates) > 20:
        raise UtilityError("Update at most 20 fields at a time.")
    parsed: list[tuple[Field, str]] = []
    for item in updates:
        try:
            field_def = database.field(item.field)
        except KeyError as exc:
            raise UtilityError(f"Field {item.field} does not exist.") from exc
        if field_def.is_memo:
            raise UtilityError("Memo fields cannot be updated globally.")
        parsed.append((field_def, item.expression))
    seqs = _ordered(database, settings)
    result = UtilityResult("Update", output=database, read=len(seqs))
    for seq in seqs:
        values = database.read(seq)
        changed = False
        for field_def, expression in parsed:
            try:
                value = evaluate(expression, _context(database, values,
                                                      padded=False, seq=seq))
            except ExprError:
                continue
            values[field_def.name] = _canonical(field_def, value)
            changed = True
        if changed:
            database.update(seq, values)
            result.updated += 1
    result.written = result.updated
    database.workspace.save_database(database)
    return result


def change_case(database: Database, fields: Sequence[str], mode: str,
                settings: indexing.RangeSettings | None = None) -> UtilityResult:
    if mode not in CASE_MODES:
        raise UtilityError(f"Unknown case mode: {mode}")
    targets: list[Field] = []
    for name in fields:
        try:
            field_def = database.field(name)
        except KeyError as exc:
            raise UtilityError(f"Field {name} does not exist.") from exc
        if field_def.type != "C":
            raise UtilityError("Change case works on character fields only.")
        targets.append(field_def)
    if not targets:
        raise UtilityError("Select at least one character field.")
    seqs = _ordered(database, settings)
    result = UtilityResult("Change case", output=database, read=len(seqs))
    for seq in seqs:
        values = database.read(seq)
        for field_def in targets:
            values[field_def.name] = _convert_case(
                values.get(field_def.name, ""), mode)[:field_def.length]
        database.update(seq, values)
        result.updated += 1
    result.written = result.updated
    database.workspace.save_database(database)
    return result


def _convert_case(text: str, mode: str) -> str:
    if mode == "Upper case":
        return text.upper()
    if mode == "Lower case":
        return text.lower()
    if mode == "First character":
        return text[:1].upper() + text[1:]
    if mode == "Word":
        return " ".join(word[:1].upper() + word[1:]
                        for word in text.split(" "))
    lowered = text.lower()
    if mode == "X Lower & First":
        return lowered[:1].upper() + lowered[1:]
    return " ".join(word[:1].upper() + word[1:]
                    for word in lowered.split(" "))


def mark_range(database: Database, deleted: bool,
               settings: indexing.RangeSettings | None = None) -> UtilityResult:
    seqs = _ordered(database, settings)
    for seq in seqs:
        database.set_deleted(seq, deleted)
    database.workspace.save_database(database)
    return UtilityResult(
        "Delete range" if deleted else "Undelete range",
        output=database, read=len(seqs), written=len(seqs),
        updated=len(seqs))
