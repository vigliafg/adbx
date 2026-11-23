"""Set: più database collegati come una sola vista (O5).

Un set è una definizione persistente (`adbx_sets` + `adbx_set_links`) con un
database primario e un albero di link. Il motore risolve i link in memoria:
niente copie dei dati, ogni campo resta nel suo `.DBF`. Le regole di
integrità e i cascading updates/deletes lavorano sui record collegati.

Il modello segue il capitolo 11 del Reference Manual: massimo 10 database,
un solo link 1:N (`All`) per livello, `First`/`Last`/`Closest` per i link
uno-a-uno.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import indexing
from .expressions import Context, ExprError, evaluate, sort_key, truthy
from .fields import Field, FieldError, parse_value
from .indexing import (
    RECORD_NUMBER,
    SHOW_ALL,
    SHOW_DELETED,
    SHOW_NOT_DELETED,
    RangeSettings,
)

LINK_MODES = ("All", "First", "Last", "Closest")
CHILD_MODES = ("Yes", "No", "Prompt")
INCLUDE_MODES = ("Always", "Has Related Child", "Has No Related Child")
MAX_SET_DATABASES = 10


class SetError(ValueError):
    """Definizione di set non valida."""


def _show_matches(deleted: bool, show: str) -> bool:
    if show == SHOW_ALL:
        return True
    if show == SHOW_DELETED:
        return deleted
    return not deleted


@dataclass
class Link:
    """Un link fra il database genitore e un database figlio."""

    parent: str = ""
    child: str = ""
    linking_index: str = ""
    common: str = ""
    link_to: str = "First"
    edit_child: str = "Yes"
    add_child: str = "Yes"
    referential: bool = False
    cascading_updates: bool = False
    cascading_deletes: bool = False
    include_parent: str = "Always"
    show_mode: str = SHOW_NOT_DELETED
    filter: str = ""
    filter_active: bool = False
    integrity: list[tuple[str, str]] = field(default_factory=list)

    def normalize(self) -> None:
        self.parent = self.parent.strip().upper()
        self.child = self.child.strip().upper()
        self.linking_index = self.linking_index.strip().upper()
        self.common = self.common.strip()
        if self.link_to not in LINK_MODES:
            self.link_to = "First"
        if self.edit_child not in CHILD_MODES:
            self.edit_child = "Yes"
        if self.add_child not in CHILD_MODES:
            self.add_child = "Yes"
        if self.include_parent not in INCLUDE_MODES:
            self.include_parent = "Always"
        if self.show_mode not in (SHOW_ALL, SHOW_DELETED, SHOW_NOT_DELETED):
            self.show_mode = SHOW_NOT_DELETED
        self.integrity = [(parent.strip().upper(), child.strip().upper())
                          for parent, child in self.integrity
                          if parent.strip() and child.strip()]

    @property
    def one_to_many(self) -> bool:
        return self.link_to == "All"

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent": self.parent, "child": self.child,
            "linking_index": self.linking_index, "common": self.common,
            "link_to": self.link_to, "edit_child": self.edit_child,
            "add_child": self.add_child, "referential": self.referential,
            "cascading_updates": self.cascading_updates,
            "cascading_deletes": self.cascading_deletes,
            "include_parent": self.include_parent,
            "show_mode": self.show_mode, "filter": self.filter,
            "filter_active": self.filter_active,
            "integrity": [[parent, child]
                          for parent, child in self.integrity],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Link":
        link = cls(
            str(data.get("parent", "")), str(data.get("child", "")),
            str(data.get("linking_index", "")), str(data.get("common", "")),
            str(data.get("link_to", "First")),
            str(data.get("edit_child", "Yes")),
            str(data.get("add_child", "Yes")),
            bool(data.get("referential", False)),
            bool(data.get("cascading_updates", False)),
            bool(data.get("cascading_deletes", False)),
            str(data.get("include_parent", "Always")),
            str(data.get("show_mode", SHOW_NOT_DELETED)),
            str(data.get("filter", "")), bool(data.get("filter_active", False)),
            [(str(item[0]), str(item[1]))
             for item in data.get("integrity", []) if len(item) >= 2])
        link.normalize()
        return link


@dataclass
class SetDefinition:
    workspace: Any
    name: str
    description: str = ""
    primary: str = ""
    show_mode: str = SHOW_NOT_DELETED
    filter: str = ""
    filter_active: bool = False
    links: list[Link] = field(default_factory=list)
    created: float = 0.0
    updated: float = 0.0

    def __post_init__(self) -> None:
        self.name = self.name.strip().upper()
        self.primary = self.primary.strip().upper()
        if self.show_mode not in (SHOW_ALL, SHOW_DELETED, SHOW_NOT_DELETED):
            self.show_mode = SHOW_NOT_DELETED
        for link in self.links:
            link.normalize()

    # -- catalogo --------------------------------------------------------
    def database(self, name: str):
        database = self.workspace.get(name.upper())
        if database is None:
            raise SetError(f"Database {name} does not exist.")
        return database

    @property
    def primary_database(self):
        return self.database(self.primary)

    def database_names(self) -> list[str]:
        names = [self.primary] if self.primary else []
        for link in self.links:
            if link.child and link.child not in names:
                names.append(link.child)
        return names

    def all_databases(self):
        return [self.database(name) for name in self.database_names()]

    def parent_names(self) -> list[str]:
        return [self.primary] + [link.child for link in self.links
                                 if link.child and not link.one_to_many]

    def children_of(self, parent: str) -> list[Link]:
        return [link for link in self.links if link.parent == parent.upper()]

    def link_for(self, child: str) -> Link | None:
        for link in self.links:
            if link.child == child.upper():
                return link
        return None

    # -- validazione -----------------------------------------------------
    def validate(self) -> None:
        if not self.primary:
            raise SetError("A set needs a primary database.")
        names = self.database_names()
        children = [link.child for link in self.links]
        if len(children) != len(set(children)):
            raise SetError("A database can appear only once in a set.")
        if len(names) > MAX_SET_DATABASES:
            raise SetError(f"A set holds at most {MAX_SET_DATABASES} databases.")
        databases = {name: self.database(name) for name in names}
        for link in self.links:
            if not link.parent or not link.child:
                raise SetError("Every link needs a parent and a child.")
            if link.parent not in names or link.child not in names:
                raise SetError("Link endpoints must belong to the set.")
            if link.parent == link.child:
                raise SetError("A database cannot link to itself.")
            parent = databases[link.parent]
            child = databases[link.child]
            if not link.common.strip():
                raise SetError(f"Link {link.parent}->{link.child} needs a "
                               "common field/expression.")
            try:
                evaluate(link.common,
                         Context(fields=parent.fields,
                                 values={field.name: ""
                                         for field in parent.fields}))
            except ExprError as exc:
                raise SetError(f"Link expression: {exc}") from exc
            if link.linking_index:
                definition = indexing.find_index(child, link.linking_index)
                if definition is None:
                    raise SetError(
                        f"Index {link.linking_index} not found in {link.child}.")
            if link.filter_active and link.filter.strip():
                try:
                    evaluate(link.filter,
                             Context(fields=child.fields,
                                     values={field.name: ""
                                             for field in child.fields}))
                except ExprError as exc:
                    raise SetError(f"Link filter: {exc}") from exc
        # Un solo link All per genitore.
        for parent in names:
            all_links = [link for link in self.links
                         if link.parent == parent and link.link_to == "All"]
            if len(all_links) > 1:
                raise SetError(f"{parent} has more than one one-to-many link.")
        # Cicli e raggiungibilità dalla radice.
        reachable = {self.primary} if self.primary else set()
        changed = True
        while changed:
            changed = False
            for link in self.links:
                if link.parent in reachable and link.child not in reachable:
                    reachable.add(link.child)
                    changed = True
        if reachable != set(names):
            raise SetError("Every database must be reachable from the primary.")
        if self.filter_active and self.filter.strip():
            try:
                evaluate(self.filter,
                         Context(fields=databases[self.primary].fields,
                                 values={field.name: ""
                                         for field in databases[self.primary].fields}))
            except ExprError as exc:
                raise SetError(f"Set filter: {exc}") from exc

    # -- persistenza -----------------------------------------------------
    def save(self) -> None:
        self.validate()
        self.workspace.save_set(self)

    def erase(self) -> None:
        self.workspace.delete_set(self.name)

    # -- record del genitore --------------------------------------------
    def _parent_context(self, database, values: dict[str, str]) -> Context:
        return Context(fields=database.fields, values=values,
                       pattern=self.workspace.pattern_mode)

    def parent_sequences(self, settings: RangeSettings | None = None) -> list[int]:
        database = self.primary_database
        range_settings = (settings or database.current_range).copy()
        range_settings.show = self.show_mode
        try:
            seqs = indexing.ordered_sequences(database, range_settings)
        except indexing.IndexError_ as exc:
            raise SetError(str(exc)) from exc
        if self.filter_active and self.filter.strip():
            kept: list[int] = []
            for seq in seqs:
                values = database.read(seq)
                try:
                    if truthy(evaluate(self.filter,
                                       self._parent_context(database, values))):
                        kept.append(seq)
                except ExprError:
                    continue
            seqs = kept
        return seqs

    def include_parent(self, values: dict[str, str]) -> bool:
        """Applica Include Parent If e i filtri dei link al record genitore."""
        for link in self.children_of(self.primary):
            if link.include_parent == "Always":
                continue
            related = self.linked_rows(link, values)
            if link.include_parent == "Has Related Child" and not related:
                return False
            if link.include_parent == "Has No Related Child" and related:
                return False
        return True

    def visible_parent_sequences(self,
                                 settings: RangeSettings | None = None) -> list[int]:
        database = self.primary_database
        return [seq for seq in self.parent_sequences(settings)
                if self.include_parent(database.read(seq))]

    # -- link ------------------------------------------------------------
    def _target_value(self, link: Link, parent_values: dict[str, str]):
        parent_db = self.database(link.parent)
        try:
            return evaluate(link.common,
                            self._parent_context(parent_db, parent_values))
        except ExprError:
            return None

    def _child_key(self, link: Link, child, values: dict[str, str], seq: int,
                   deleted: bool, definition):
        if definition is not None:
            try:
                if not indexing.index_filter_passes(
                        child, definition, values, seq=seq, deleted=deleted):
                    return None
                return evaluate(
                    definition.expression,
                    Context(fields=child.fields, values=values,
                            pattern=self.workspace.pattern_mode, seq=seq,
                            deleted=deleted))
            except ExprError:
                return None
        name = link.common.strip().upper()
        if name in {field.name for field in child.fields}:
            return values.get(name, "")
        return None

    def linked_rows(self, link: Link,
                    parent_values: dict[str, str], *,
                    include_deleted: bool = False
                    ) -> list[tuple[int, dict[str, str]]]:
        """Record figli che soddisfano il link, nell'ordine dell'indice."""
        child = self.database(link.child)
        definition = (indexing.find_index(child, link.linking_index)
                      if link.linking_index else None)
        if definition is not None:
            settings = RangeSettings(primary=definition.name, show=SHOW_ALL)
        else:
            settings = RangeSettings(primary=RECORD_NUMBER, show=SHOW_ALL)
        try:
            seqs = indexing.ordered_sequences(child, settings)
        except indexing.IndexError_:
            seqs = child.sequences(include_deleted=True)
        target = self._target_value(link, parent_values)
        if target is None:
            return []
        case_sensitive = bool(definition and definition.case_sensitive)
        target_key = sort_key(target, case_sensitive=case_sensitive)
        rows: list[tuple[int, dict[str, str]]] = []
        closest: tuple[tuple, int, dict[str, str]] | None = None
        for seq in seqs:
            values = child.read(seq)
            deleted = child.is_deleted(seq)
            if not include_deleted and not _show_matches(deleted,
                                                         link.show_mode):
                continue
            if link.filter_active and link.filter.strip():
                try:
                    if not truthy(evaluate(
                            link.filter,
                            Context(fields=child.fields, values=values,
                                    pattern=self.workspace.pattern_mode,
                                    seq=seq, deleted=deleted))):
                        continue
                except ExprError:
                    continue
            key_value = self._child_key(link, child, values, seq, deleted,
                                        definition)
            if key_value is None:
                continue
            key = sort_key(key_value, case_sensitive=case_sensitive)
            if key == target_key:
                rows.append((seq, values))
                if link.link_to in ("First", "Closest"):
                    break
                continue
            if link.link_to == "Closest" and key > target_key and closest is None:
                closest = (key, seq, values)
        if link.link_to == "Closest" and not rows and closest is not None:
            rows.append((closest[1], closest[2]))
        if link.link_to == "First" and rows:
            return rows[:1]
        if link.link_to == "Last" and rows:
            return rows[-1:]
        return rows

    def linked_records(self, parent_values: dict[str, str]) -> list[Link]:
        return self.children_of(self.primary)

    def child_rows_all(self, parent_values: dict[str, str]
                       ) -> list[tuple[Link, list[tuple[int, dict[str, str]]]]]:
        return [(link, self.linked_rows(link, parent_values))
                for link in self.children_of(self.primary)
                if link.one_to_many]

    # -- campi combinati -------------------------------------------------
    def flat_fields(self) -> list[tuple[str, Field, str]]:
        """Campi del genitore e dei figli 1:1, con etichetta unica."""
        result: list[tuple[str, Field, str]] = []
        primary = self.primary_database
        for definition in primary.fields:
            result.append((self.primary, definition, definition.name))
        for link in self.children_of(self.primary):
            if link.one_to_many:
                continue
            child = self.database(link.child)
            for definition in child.fields:
                result.append((link.child, definition,
                               f"{link.child}.{definition.name}"))
        return result

    def flat_values(self, parent_values: dict[str, str]) -> dict[tuple[str, str], str]:
        values: dict[tuple[str, str], str] = {}
        for definition in self.primary_database.fields:
            values[(self.primary, definition.name)] = parent_values.get(
                definition.name, "")
        for link in self.children_of(self.primary):
            if link.one_to_many:
                continue
            rows = self.linked_rows(link, parent_values)
            child = self.database(link.child)
            row = rows[0][1] if rows else {}
            for definition in child.fields:
                values[(link.child, definition.name)] = row.get(
                    definition.name, "")
        return values

    # -- integrità e cascading ------------------------------------------
    def integrity_rows(self, link: Link) -> list[tuple[str, str]]:
        if link.integrity:
            return list(link.integrity)
        parent = self.database(link.parent)
        child = self.database(link.child)
        child_names = {field.name for field in child.fields}
        rows = [(field.name, field.name) for field in parent.fields
                if field.name in child_names]
        common = link.common.strip().upper()
        if common in {field.name for field in parent.fields} \
                and common not in {before for before, _after in rows}:
            rows.append((common, common))
        return rows

    def _apply_integrity(self, link: Link, matrix: list[tuple[str, str]],
                         parent_values: dict[str, str],
                         target: dict[str, str]) -> None:
        child = self.database(link.child)
        for parent_name, child_name in matrix:
            if parent_name not in parent_values:
                continue
            try:
                field = child.field(child_name)
            except KeyError:
                continue
            try:
                target[child_name] = parse_value(
                    field, parent_values.get(parent_name, ""))
            except FieldError:
                continue

    def add_child(self, link: Link, parent_values: dict[str, str]) -> int:
        child = self.database(link.child)
        values = {field.name: "" for field in child.fields}
        self._apply_integrity(link, self.integrity_rows(link), parent_values,
                              values)
        seq = child.append(values)
        self.workspace.save_database(child)
        return seq

    def cascade_update(self, link: Link, old_values: dict[str, str],
                       new_values: dict[str, str]) -> int:
        if not link.referential or not link.cascading_updates:
            return 0
        if not link.common.strip():
            return 0
        rows = self.linked_rows(link, old_values, include_deleted=True)
        child = self.database(link.child)
        matrix = self.integrity_rows(link)
        changed = 0
        for seq, values in rows:
            target = dict(values)
            self._apply_integrity(link, matrix, new_values, target)
            if target != values:
                child.update(seq, target)
                changed += 1
        if changed:
            self.workspace.save_database(child)
        return changed

    def cascade_delete(self, link: Link, parent_values: dict[str, str],
                       deleted: bool = True) -> int:
        if not link.referential or not link.cascading_deletes:
            return 0
        rows = self.linked_rows(link, parent_values, include_deleted=True)
        child = self.database(link.child)
        changed = 0
        for seq, _values in rows:
            if child.is_deleted(seq) != deleted:
                child.set_deleted(seq, deleted)
                changed += 1
        if changed:
            self.workspace.save_database(child)
        return changed

    def delete_parent(self, seq: int) -> int:
        """Marca cancellato il genitore e applica i cascading deletes."""
        database = self.primary_database
        values = database.read(seq)
        database.delete(seq)
        changed = 0
        for link in self.children_of(self.primary):
            changed += self.cascade_delete(link, values, True)
        self.workspace.save_database(database)
        return changed

    def undelete_parent(self, seq: int) -> int:
        database = self.primary_database
        values = database.read(seq)
        database.undelete(seq)
        changed = 0
        for link in self.children_of(self.primary):
            changed += self.cascade_delete(link, values, False)
        self.workspace.save_database(database)
        return changed

    def update_parent(self, seq: int, values: dict[str, str]) -> int:
        """Aggiorna il genitore e propaga i cascading updates."""
        database = self.primary_database
        old_values = database.read(seq)
        database.update(seq, values)
        changed = 0
        for link in self.children_of(self.primary):
            changed += self.cascade_update(link, old_values, values)
        self.workspace.save_database(database)
        return changed


# -- workspace ---------------------------------------------------------------


def _set_from_row(workspace, row) -> SetDefinition:
    definition = SetDefinition(
        workspace, str(row["name"]), str(row["description"]),
        str(row["primary_database"]), str(row["show_mode"]),
        str(row["filter"]), bool(row["filter_active"]),
        created=float(row["created"]), updated=float(row["updated"]))
    for link_row in workspace.connection.execute(
            "SELECT * FROM adbx_set_links WHERE set_name = ? ORDER BY position",
            (definition.name,)):
        definition.links.append(link_from_row(link_row))
    return definition


def link_from_row(row) -> Link:
    import json

    return Link.from_dict({
        "parent": row["parent"], "child": row["child"],
        "linking_index": row["linking_index"], "common": row["common"],
        "link_to": row["link_to"], "edit_child": row["edit_child"],
        "add_child": row["add_child"], "referential": row["referential"],
        "cascading_updates": row["cascading_updates"],
        "cascading_deletes": row["cascading_deletes"],
        "include_parent": row["include_parent"],
        "show_mode": row["show_mode"], "filter": row["filter"],
        "filter_active": row["filter_active"],
        "integrity": json.loads(row["integrity"] or "[]")})


__all__ = [
    "CHILD_MODES",
    "INCLUDE_MODES",
    "LINK_MODES",
    "Link",
    "MAX_SET_DATABASES",
    "SetDefinition",
    "SetError",
]
