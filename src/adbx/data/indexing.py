"""Indici, range e search/sort list del motore dati.

Un indice è una definizione persistente: espressione, eventuali livelli in
Table mode, filtro, politica sui duplicati, distinzione maiuscole/minuscole.
L'ordine si calcola al volo sui record: i database di Alpha Four sono piccoli
e il file `.DBF` resta la sorgente; non manteniamo file `.NDX` proprietari.

Un *range* è l'insieme di impostazioni che decide quali record un comando
vede: indice primario, verso, cancellati, prima/ultima chiave, chiavi uniche,
filtro. Il range corrente è persistito per database.

Una *search/sort list* è un elenco di numeri di record costruito una volta e
poi riusato. Diventa «out of date» quando il database viene modificato: il
confronto è fra la revisione salvata nella lista e quella corrente.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from functools import cmp_to_key
from typing import Sequence

from .expressions import (
    Context,
    ExprError,
    SearchRow,
    evaluate,
    field_value,
    key_text,
    matches_search_rows,
    sort_key,
)
from .workspace import Database, Workspace, WorkspaceError

RECORD_NUMBER = "RECORD NUMBER"
SEARCH_LIST = "SEARCH LIST"
SEARCH_PREFIX = "SEARCH:"
MAX_INDEXES_ATTACHED = 15
MAX_KEY_LENGTH = 100

ALLOW_ALL = "all"
ALLOW_UNIQUE = "unique"
ALLOW_EXCEPTIONS = "exceptions"
ALLOW_MODES = (ALLOW_ALL, ALLOW_UNIQUE, ALLOW_EXCEPTIONS)

SHOW_ALL = "all"
SHOW_DELETED = "deleted"
SHOW_NOT_DELETED = "not_deleted"
SHOW_MODES = (SHOW_ALL, SHOW_DELETED, SHOW_NOT_DELETED)

ORDER_ASCENDING = "ascending"
ORDER_DESCENDING = "descending"
ORDER_MODES = (ORDER_ASCENDING, ORDER_DESCENDING)


class IndexError_(WorkspaceError):
    """Indice o range non valido."""


@dataclass
class IndexDefinition:
    name: str
    expression: str
    description: str = ""
    filter: str = ""
    allow: str = ALLOW_ALL
    case_sensitive: bool = False
    attached: bool = True
    levels: list[tuple[str, str]] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.description or self.expression

    @property
    def key_expression(self) -> str:
        if self.expression:
            return self.expression
        return "+".join(name for name, _direction in self.levels)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "expression": self.expression,
            "description": self.description, "filter": self.filter,
            "allow": self.allow, "case_sensitive": self.case_sensitive,
            "attached": self.attached,
            "levels": [list(level) for level in self.levels],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IndexDefinition":
        return cls(
            name=str(data["name"]), expression=str(data.get("expression", "")),
            description=str(data.get("description", "")),
            filter=str(data.get("filter", "")),
            allow=str(data.get("allow", ALLOW_ALL)),
            case_sensitive=bool(data.get("case_sensitive", False)),
            attached=bool(data.get("attached", True)),
            levels=[(str(level[0]), str(level[1]))
                    for level in data.get("levels", [])],
        )


@dataclass
class RangeSettings:
    primary: str = RECORD_NUMBER
    order: str = ORDER_ASCENDING
    show: str = SHOW_NOT_DELETED
    first_key: str = ""
    last_key: str = ""
    unique_keys: bool = False
    filter: str = ""
    filter_active: bool = False

    @property
    def search_id(self) -> int | None:
        if self.primary.startswith(SEARCH_PREFIX):
            try:
                return int(self.primary[len(SEARCH_PREFIX):])
            except ValueError:
                return None
        return None

    def to_dict(self) -> dict:
        return {
            "primary": self.primary, "order": self.order, "show": self.show,
            "first_key": self.first_key, "last_key": self.last_key,
            "unique_keys": self.unique_keys, "filter": self.filter,
            "filter_active": self.filter_active,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "RangeSettings":
        data = data or {}
        primary = str(data.get("primary", RECORD_NUMBER))
        order = str(data.get("order", ORDER_ASCENDING))
        show = str(data.get("show", SHOW_NOT_DELETED))
        return cls(
            primary=primary,
            order=order if order in ORDER_MODES else ORDER_ASCENDING,
            show=show if show in SHOW_MODES else SHOW_NOT_DELETED,
            first_key=str(data.get("first_key", "")),
            last_key=str(data.get("last_key", "")),
            unique_keys=bool(data.get("unique_keys", False)),
            filter=str(data.get("filter", "")),
            filter_active=bool(data.get("filter_active", False)),
        )

    def copy(self) -> "RangeSettings":
        return RangeSettings.from_dict(self.to_dict())

    @property
    def is_default(self) -> bool:
        return (self.primary == RECORD_NUMBER
                and self.order == ORDER_ASCENDING
                and self.show == SHOW_NOT_DELETED
                and not self.first_key and not self.last_key
                and not self.unique_keys and not self.filter)


@dataclass
class SavedSearch:
    letter: str
    description: str = ""
    mode: str = "table"
    search_rows: list[SearchRow] = field(default_factory=list)
    search_expression: str = ""
    sort_rows: list[tuple[str, str]] = field(default_factory=list)
    sort_expression: str = ""
    show: str = SHOW_NOT_DELETED
    case_sensitive: bool = False
    version: int = 1

    def to_dict(self) -> dict:
        return {
            "letter": self.letter, "description": self.description,
            "mode": self.mode,
            "search_rows": [row.to_dict() for row in self.search_rows],
            "search_expression": self.search_expression,
            "sort_rows": [list(row) for row in self.sort_rows],
            "sort_expression": self.sort_expression,
            "show": self.show, "case_sensitive": self.case_sensitive,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SavedSearch":
        return cls(
            letter=str(data["letter"]),
            description=str(data.get("description", "")),
            mode=str(data.get("mode", "table")),
            search_rows=[SearchRow.from_dict(row)
                         for row in data.get("search_rows", [])],
            search_expression=str(data.get("search_expression", "")),
            sort_rows=[(str(row[0]), str(row[1]))
                       for row in data.get("sort_rows", [])],
            sort_expression=str(data.get("sort_expression", "")),
            show=str(data.get("show", SHOW_NOT_DELETED)),
            case_sensitive=bool(data.get("case_sensitive", False)),
            version=int(data.get("version", 1)),
        )


@dataclass
class SearchList:
    id: int
    database: str
    letter: str | None
    description: str
    search_expression: str
    sort_expression: str
    sort_rows: list[tuple[str, str]]
    show: str
    case_sensitive: bool
    revision: int
    created: float
    seqs: list[int]
    range_json: dict = field(default_factory=dict)
    def_version: int = 0

    @property
    def label(self) -> str:
        return self.description or self.search_expression or "Search/Sort List"

    def matches_criteria(self, database: Database,
                         search: SavedSearch | None = None) -> bool:
        if database.revision() != self.revision:
            return False
        if self.letter and search is not None and search.version != self.def_version:
            return False
        return True

    def out_of_date(self, database: Database) -> bool:
        search = (saved_search(database, self.letter)
                  if self.letter else None)
        return not self.matches_criteria(database, search)


# -- creazione e lettura di indici ------------------------------------------


def index_context(database: Database, values: dict[str, str], *,
                  definition: IndexDefinition | None = None,
                  seq: int = 0, deleted: bool = False) -> Context:
    return Context(
        fields=database.fields, values=values,
        pattern=database.workspace.pattern_mode,
        padded=True, seq=seq, deleted=deleted, count=database.count())


def index_key(database: Database, definition: IndexDefinition,
              values: dict[str, str], *, seq: int = 0,
              deleted: bool = False) -> str:
    context = index_context(database, values, definition=definition,
                            seq=seq, deleted=deleted)
    try:
        return key_text(evaluate(definition.key_expression, context))
    except ExprError as exc:
        raise IndexError_(f"Index {definition.name}: {exc}") from exc


def index_filter_passes(database: Database, definition: IndexDefinition,
                        values: dict[str, str], *, seq: int = 0,
                        deleted: bool = False) -> bool:
    if not definition.filter.strip():
        return True
    context = index_context(database, values, definition=definition,
                            seq=seq, deleted=deleted)
    try:
        return bool(evaluate(definition.filter, context))
    except ExprError as exc:
        raise IndexError_(f"Index {definition.name} filter: {exc}") from exc


def level_value(database: Database, field_name: str,
                values: dict[str, str], *, case_sensitive: bool) -> tuple:
    definition = database.field(field_name)
    context = index_context(database, values)
    value = field_value(context, definition.name)
    return sort_key(value, case_sensitive=case_sensitive)


def _compare_index_rows(database: Database, definition: IndexDefinition,
                        left: tuple[int, dict[str, str]],
                        right: tuple[int, dict[str, str]]) -> int:
    for field_name, direction in definition.levels:
        lvalue = level_value(database, field_name, left[1],
                             case_sensitive=definition.case_sensitive)
        rvalue = level_value(database, field_name, right[1],
                             case_sensitive=definition.case_sensitive)
        comparison = (lvalue > rvalue) - (lvalue < rvalue)
        if comparison:
            return -comparison if direction.upper().startswith("D") else comparison
    return 0


def ordered_sequences(database: Database,
                      settings: RangeSettings | None = None) -> list[int]:
    """Record visibili secondo il range, nell'ordine dell'indice primario."""
    settings = settings or database.current_range
    records = [(seq, deleted, values)
               for seq, deleted, values in database.iter_values(include_deleted=True)]
    by_seq = {seq: (deleted, values) for seq, deleted, values in records}

    # Ricerca: la lista attiva restringe i record e impone il suo ordine.
    search = (get_search_list(database, settings.search_id)
              if settings.search_id else None)
    if search is not None:
        candidates = [seq for seq in search.seqs if seq in by_seq]
    else:
        candidates = [seq for seq, _deleted, _values in records]

    filtered: list[tuple[int, dict[str, str]]] = []
    for seq in candidates:
        deleted, values = by_seq[seq]
        if settings.show == SHOW_NOT_DELETED and deleted:
            continue
        if settings.show == SHOW_DELETED and not deleted:
            continue
        if settings.filter_active and settings.filter.strip():
            context = Context(
                fields=database.fields, values=values,
                pattern=database.workspace.pattern_mode,
                seq=seq, deleted=deleted, count=len(records))
            try:
                if not evaluate(settings.filter, context):
                    continue
            except ExprError:
                continue
        filtered.append((seq, values))

    definition = None
    if settings.primary not in (RECORD_NUMBER, SEARCH_LIST) \
            and not settings.primary.startswith(SEARCH_PREFIX):
        definition = find_index(database, settings.primary)
        if definition is None:
            raise IndexError_(f"Index {settings.primary} does not exist.")

    if search is not None:
        order = {seq: index for index, seq in enumerate(search.seqs)}
        filtered.sort(key=lambda item: order.get(item[0], len(order)))
        if settings.order == ORDER_DESCENDING:
            filtered.reverse()
    elif definition is not None:
        filtered = [item for item in filtered
                    if index_filter_passes(database, definition, item[1],
                                           seq=item[0])]
        if definition.levels:
            filtered.sort(key=cmp_to_key(
                lambda left, right: _compare_index_rows(
                    database, definition, left, right)))
        else:
            decorated = [
                (index_key(database, definition, values, seq=seq), seq, values)
                for seq, values in filtered]
            decorated.sort(key=lambda item: item[0]
                           if definition.case_sensitive else item[0].upper())
            filtered = [(seq, values) for _key, seq, values in decorated]
        if settings.order == ORDER_DESCENDING:
            filtered.reverse()
    else:
        filtered.sort(key=lambda item: item[0],
                      reverse=settings.order == ORDER_DESCENDING)

    if definition is not None and (settings.first_key or settings.last_key):
        bound_rows = []
        for seq, values in filtered:
            key = index_key(database, definition, values, seq=seq)
            if _within_bounds(key, settings.first_key, settings.last_key,
                              definition.case_sensitive):
                bound_rows.append((seq, values))
        filtered = bound_rows

    if definition is not None and settings.unique_keys:
        seen: set[str] = set()
        unique_rows = []
        for seq, values in filtered:
            key = index_key(database, definition, values, seq=seq)
            marker = key if definition.case_sensitive else key.upper()
            if marker in seen:
                continue
            seen.add(marker)
            unique_rows.append((seq, values))
        filtered = unique_rows

    return [seq for seq, _values in filtered]


def _within_bounds(key: str, first: str, last: str,
                   case_sensitive: bool) -> bool:
    marker = key if case_sensitive else key.upper()
    if first:
        boundary = first if case_sensitive else first.upper()
        if not (marker >= boundary or marker.startswith(boundary)):
            return False
    if last:
        boundary = last if case_sensitive else last.upper()
        if not (marker <= boundary or marker.startswith(boundary)):
            return False
    return True


def key_values(database: Database, definition: IndexDefinition) -> list[str]:
    """Valori di chiave unici dell'indice, in ordine ascendente."""
    seen: set[str] = set()
    values: list[str] = []
    records = list(database.iter_values(include_deleted=False))
    for seq, deleted, row in records:
        if not index_filter_passes(database, definition, row, seq=seq,
                                   deleted=deleted):
            continue
        key = index_key(database, definition, row, seq=seq, deleted=deleted)
        marker = key if definition.case_sensitive else key.upper()
        if marker in seen:
            continue
        seen.add(marker)
        values.append(key)
    values.sort(key=None if definition.case_sensitive else str.upper)
    return values


def primary_label(database: Database) -> str:
    primary = database.primary_index
    if primary.startswith(SEARCH_PREFIX):
        search = get_search_list(database, _search_id(primary))
        if search is None:
            return "Search/Sort List"
        marker = "\u2666 " if search.out_of_date(database) else ""
        return f"{marker}Search/Sort: {search.label}"
    if primary == RECORD_NUMBER or primary == SEARCH_LIST:
        return "Record Number"
    definition = find_index(database, primary)
    return definition.label if definition is not None else primary


def _search_id(primary: str) -> int | None:
    if not primary.startswith(SEARCH_PREFIX):
        return None
    try:
        return int(primary[len(SEARCH_PREFIX):])
    except ValueError:
        return None


# -- persistenza degli indici ----------------------------------------------


def _connection(workspace: Workspace):
    return workspace.connection


def find_index(database: Database, name: str) -> IndexDefinition | None:
    row = _connection(database.workspace).execute(
        "SELECT definition FROM adbx_indexes WHERE database = ? AND name = ?",
        (database.name, name.upper())).fetchone()
    if row is None:
        return None
    return IndexDefinition.from_dict(json.loads(row["definition"]))


def indexes(database: Database, *, attached: bool | None = None
            ) -> list[IndexDefinition]:
    rows = _connection(database.workspace).execute(
        "SELECT definition FROM adbx_indexes WHERE database = ? "
        "ORDER BY name", (database.name,)).fetchall()
    definitions = [IndexDefinition.from_dict(json.loads(row["definition"]))
                   for row in rows]
    if attached is not None:
        definitions = [item for item in definitions if item.attached == attached]
    return definitions


def save_index(database: Database, definition: IndexDefinition, *,
               replace: bool = False) -> IndexDefinition:
    connection = _connection(database.workspace)
    existing = find_index(database, definition.name)
    if existing is not None and not replace:
        raise IndexError_(f"Index {definition.name} already exists.")
    attached = len(indexes(database, attached=True))
    if existing is None and definition.attached and attached >= MAX_INDEXES_ATTACHED:
        raise IndexError_(
            f"At most {MAX_INDEXES_ATTACHED} indexes can be attached.")
    connection.execute(
        "INSERT INTO adbx_indexes (database, name, definition) VALUES (?, ?, ?) "
        "ON CONFLICT(database, name) DO UPDATE SET definition = excluded.definition",
        (database.name, definition.name, json.dumps(definition.to_dict())))
    connection.commit()
    return definition


def delete_index(database: Database, name: str) -> bool:
    connection = _connection(database.workspace)
    cursor = connection.execute(
        "DELETE FROM adbx_indexes WHERE database = ? AND name = ?",
        (database.name, name.upper()))
    connection.commit()
    if database.primary_index == name.upper():
        database.set_primary_index(RECORD_NUMBER)
    return cursor.rowcount > 0


def set_index_attached(database: Database, name: str, attached: bool) -> None:
    definition = find_index(database, name)
    if definition is None:
        raise IndexError_(f"Index {name} does not exist.")
    if attached:
        attached_count = len(indexes(database, attached=True))
        if not definition.attached and attached_count >= MAX_INDEXES_ATTACHED:
            raise IndexError_(
                f"At most {MAX_INDEXES_ATTACHED} indexes can be attached.")
    definition.attached = attached
    save_index(database, definition, replace=True)


# -- range ------------------------------------------------------------------


def save_range(database: Database, letter: str, description: str,
               settings: RangeSettings) -> None:
    letter = letter.upper()[:1]
    if not letter.isalpha():
        raise IndexError_("Range names are letters A-Z.")
    connection = _connection(database.workspace)
    connection.execute(
        "INSERT INTO adbx_ranges (database, letter, description, settings) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(database, letter) DO UPDATE SET "
        "description = excluded.description, settings = excluded.settings",
        (database.name, letter, description, json.dumps(settings.to_dict())))
    connection.commit()


def saved_ranges(database: Database) -> list[tuple[str, str, RangeSettings]]:
    rows = _connection(database.workspace).execute(
        "SELECT letter, description, settings FROM adbx_ranges "
        "WHERE database = ? ORDER BY letter", (database.name,)).fetchall()
    return [(row["letter"], row["description"],
             RangeSettings.from_dict(json.loads(row["settings"])))
            for row in rows]


def get_range(database: Database, letter: str) -> tuple[str, RangeSettings] | None:
    for name, description, settings in saved_ranges(database):
        if name == letter.upper():
            return description, settings
    return None


def delete_range(database: Database, letter: str) -> bool:
    connection = _connection(database.workspace)
    cursor = connection.execute(
        "DELETE FROM adbx_ranges WHERE database = ? AND letter = ?",
        (database.name, letter.upper()))
    connection.commit()
    return cursor.rowcount > 0


def default_range() -> RangeSettings:
    return RangeSettings()


# -- search/sort: definizioni salvate ---------------------------------------


def save_saved_search(database: Database, search: SavedSearch) -> SavedSearch:
    connection = _connection(database.workspace)
    previous = saved_search(database, search.letter)
    if previous is not None:
        search.version = previous.version + 1
    connection.execute(
        "INSERT INTO adbx_searches (database, letter, definition, version) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(database, letter) DO UPDATE SET "
        "definition = excluded.definition, version = excluded.version",
        (database.name, search.letter.upper(), json.dumps(search.to_dict()),
         search.version))
    connection.commit()
    return search


def saved_search(database: Database, letter: str) -> SavedSearch | None:
    row = _connection(database.workspace).execute(
        "SELECT definition FROM adbx_searches WHERE database = ? AND letter = ?",
        (database.name, letter.upper())).fetchone()
    if row is None:
        return None
    return SavedSearch.from_dict(json.loads(row["definition"]))


def saved_searches(database: Database) -> list[SavedSearch]:
    rows = _connection(database.workspace).execute(
        "SELECT definition FROM adbx_searches WHERE database = ? ORDER BY letter",
        (database.name,)).fetchall()
    return [SavedSearch.from_dict(json.loads(row["definition"])) for row in rows]


def delete_saved_search(database: Database, letter: str) -> bool:
    connection = _connection(database.workspace)
    cursor = connection.execute(
        "DELETE FROM adbx_searches WHERE database = ? AND letter = ?",
        (database.name, letter.upper()))
    connection.commit()
    return cursor.rowcount > 0


# -- search/sort: esecuzione e liste ---------------------------------------


def _database_revision(database: Database) -> int:
    return database.revision()


def _records_by_seq(database: Database) -> dict[int, tuple[bool, dict[str, str]]]:
    return {seq: (deleted, values)
            for seq, deleted, values in database.iter_values(include_deleted=True)}


def _context_for(database: Database, seq: int, deleted: bool,
                 values: dict[str, str]) -> Context:
    return Context(
        fields=database.fields, values=values,
        pattern=database.workspace.pattern_mode,
        seq=seq, deleted=deleted, count=database.count(include_deleted=True))


def sort_sequences(database: Database, seqs: list[int], *,
                   sort_rows: Sequence[tuple[str, str]] = (),
                   sort_expression: str = "",
                   case_sensitive: bool = False,
                   records: dict[int, tuple[bool, dict[str, str]]] | None = None
                   ) -> list[int]:
    records = records or _records_by_seq(database)
    if sort_rows:
        def key(seq: int) -> tuple:
            deleted, values = records[seq]
            context = _context_for(database, seq, deleted, values)
            return tuple(
                (sort_key(field_value(context, database.field(name).name),
                          case_sensitive=case_sensitive),
                 direction.upper().startswith("A"))
                for name, direction in sort_rows)
        return sorted(seqs, key=key)
    if sort_expression.strip():
        def expression_key(seq: int) -> tuple:
            deleted, values = records[seq]
            context = Context(
                fields=database.fields, values=values,
                pattern=database.workspace.pattern_mode, padded=True,
                seq=seq, deleted=deleted,
                count=database.count(include_deleted=True))
            try:
                return sort_key(evaluate(sort_expression, context),
                                case_sensitive=case_sensitive)
            except ExprError as exc:
                raise IndexError_(f"Sort expression: {exc}") from exc
        return sorted(seqs, key=expression_key)
    return list(seqs)


def run_search(database: Database, *,
               search_rows: Sequence[SearchRow] = (),
               search_expression: str = "",
               sort_rows: Sequence[tuple[str, str]] = (),
               sort_expression: str = "",
               show: str = SHOW_NOT_DELETED,
               case_sensitive: bool = False,
               range_settings: RangeSettings | None = None,
               letter: str | None = None,
               def_version: int = 0,
               description: str = "") -> SearchList:
    settings = (range_settings or database.current_range).copy()
    settings.show = show
    candidates = ordered_sequences(database, settings)
    records = _records_by_seq(database)

    matched: list[int] = []
    for seq in candidates:
        deleted, values = records[seq]
        context = _context_for(database, seq, deleted, values)
        try:
            if search_rows:
                ok = matches_search_rows(search_rows, context)
            elif search_expression.strip():
                ok = bool(evaluate(search_expression, context))
            else:
                ok = True
        except ExprError as exc:
            raise IndexError_(f"Search expression: {exc}") from exc
        if ok:
            matched.append(seq)

    matched = sort_sequences(
        database, matched, sort_rows=sort_rows,
        sort_expression=sort_expression, case_sensitive=case_sensitive,
        records=records)

    effective_search = (search_expression.strip()
                        or _rows_text(search_rows))
    effective_sort = sort_expression.strip() or _sort_rows_text(sort_rows)
    if not description:
        description = effective_search or "All records"
        if effective_sort:
            description += f" sorted by {effective_sort}"

    connection = _connection(database.workspace)
    cursor = connection.execute(
        "INSERT INTO adbx_search_lists (database, letter, description, "
        "search_expression, sort_expression, sort_rows, show, case_sensitive, "
        "revision, created, seqs, range_json, def_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (database.name, letter, description, effective_search, effective_sort,
         json.dumps([list(row) for row in sort_rows]), show,
         1 if case_sensitive else 0, _database_revision(database), time.time(),
         json.dumps(matched), json.dumps(settings.to_dict()), def_version))
    connection.commit()
    search_id = int(cursor.lastrowid)
    database.set_primary_index(f"{SEARCH_PREFIX}{search_id}")
    _trim_history(database)
    return get_search_list(database, search_id)  # type: ignore[return-value]


def refresh_search_list(database: Database, search_id: int) -> SearchList:
    search = get_search_list(database, search_id)
    if search is None:
        raise IndexError_(f"Search list {search_id} does not exist.")
    saved = saved_search(database, search.letter) if search.letter else None
    rows = saved.search_rows if saved else []
    range_settings = RangeSettings.from_dict(search.range_json)
    rebuilt = run_search(
        database, search_rows=rows,
        search_expression=search.search_expression,
        sort_rows=search.sort_rows,
        sort_expression=search.sort_expression,
        show=search.show, case_sensitive=search.case_sensitive,
        range_settings=range_settings, letter=search.letter,
        def_version=saved.version if saved else 0,
        description=search.description)
    if search.id != rebuilt.id:
        delete_search_list(database, search.id)
    return rebuilt


def get_search_list(database: Database, search_id: int | None) -> SearchList | None:
    if search_id is None:
        return None
    row = _connection(database.workspace).execute(
        "SELECT * FROM adbx_search_lists WHERE id = ? AND database = ?",
        (search_id, database.name)).fetchone()
    if row is None:
        return None
    return SearchList(
        id=int(row["id"]), database=row["database"], letter=row["letter"],
        description=row["description"],
        search_expression=row["search_expression"],
        sort_expression=row["sort_expression"],
        sort_rows=[(str(item[0]), str(item[1]))
                   for item in json.loads(row["sort_rows"])],
        show=row["show"], case_sensitive=bool(row["case_sensitive"]),
        revision=int(row["revision"]), created=float(row["created"]),
        seqs=[int(seq) for seq in json.loads(row["seqs"])],
        range_json=json.loads(row["range_json"] or "{}"),
        def_version=int(row["def_version"] or 0))


def search_history(database: Database, limit: int = 10) -> list[SearchList]:
    rows = _connection(database.workspace).execute(
        "SELECT id FROM adbx_search_lists WHERE database = ? "
        "ORDER BY created DESC, id DESC LIMIT ?",
        (database.name, limit)).fetchall()
    return [item for item in (get_search_list(database, int(row["id"]))
                              for row in rows) if item is not None]


def delete_search_list(database: Database, search_id: int) -> bool:
    connection = _connection(database.workspace)
    cursor = connection.execute(
        "DELETE FROM adbx_search_lists WHERE id = ? AND database = ?",
        (search_id, database.name))
    connection.commit()
    if database.primary_index == f"{SEARCH_PREFIX}{search_id}":
        database.set_primary_index(RECORD_NUMBER)
    return cursor.rowcount > 0


def _trim_history(database: Database) -> None:
    rows = _connection(database.workspace).execute(
        "SELECT id FROM adbx_search_lists WHERE database = ? "
        "ORDER BY created DESC, id DESC", (database.name,)).fetchall()
    for row in rows[10:]:
        delete_search_list(database, int(row["id"]))


def _rows_text(rows: Sequence[SearchRow]) -> str:
    from .expressions import search_rows_expression
    return search_rows_expression(rows)


def _sort_rows_text(rows: Sequence[tuple[str, str]]) -> str:
    return "+".join(name for name, _direction in rows)


def run_saved_search(database: Database, letter: str, *,
                     range_settings: RangeSettings | None = None
                     ) -> SearchList:
    search = saved_search(database, letter)
    if search is None:
        raise IndexError_(f"Search/sort {letter.upper()} does not exist.")
    return run_search(
        database, search_rows=search.search_rows,
        search_expression=search.search_expression,
        sort_rows=search.sort_rows, sort_expression=search.sort_expression,
        show=search.show, case_sensitive=search.case_sensitive,
        range_settings=range_settings, letter=search.letter,
        def_version=search.version, description=search.description)


__all__ = [
    "ALLOW_ALL",
    "ALLOW_EXCEPTIONS",
    "ALLOW_MODES",
    "ALLOW_UNIQUE",
    "IndexDefinition",
    "IndexError_",
    "MAX_INDEXES_ATTACHED",
    "ORDER_ASCENDING",
    "ORDER_DESCENDING",
    "RECORD_NUMBER",
    "RangeSettings",
    "SEARCH_LIST",
    "SEARCH_PREFIX",
    "SHOW_ALL",
    "SHOW_DELETED",
    "SHOW_MODES",
    "SHOW_NOT_DELETED",
    "SavedSearch",
    "SearchList",
    "default_range",
    "delete_index",
    "delete_range",
    "delete_saved_search",
    "delete_search_list",
    "find_index",
    "get_range",
    "get_search_list",
    "index_filter_passes",
    "index_key",
    "indexes",
    "key_values",
    "ordered_sequences",
    "primary_label",
    "refresh_search_list",
    "run_saved_search",
    "run_search",
    "save_index",
    "save_range",
    "save_saved_search",
    "saved_ranges",
    "saved_search",
    "saved_searches",
    "search_history",
    "set_index_attached",
    "sort_sequences",
]
