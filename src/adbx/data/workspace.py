"""Workspace SQLite: database, record, memo, riconfigurazione e password.

Un *workspace* è una cartella di dati. Dentro la cartella, il file nascosto
`.adbx.sqlite` conserva le tabelle descritte nel PLAN §3.3:

* `adbx_databases` — catalogo: nome, campi, sorgente `.DBF`, password;
* `t_<db>` — una colonna per campo più `__seq` e `__deleted`;
* `m_<db>` — i memo, per `(seq, field)`.

Il `.DBF` resta la sorgente e il formato di scambio: viene importato al primo
accesso e riscritto a ogni salvataggio esplicito. In questo modo il file si
può ancora aprire con gli strumenti dBASE, mentre il motore usa SQLite.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .dbf import (
    DbfError,
    canonical_row,
    memo_path,
    read_header,
    read_rows,
    write_rows,
)
from .fields import (
    Field,
    FieldError,
    convert_value,
    format_value,
    parse_value,
    validate_fields,
)

WORKSPACE_FILE = ".adbx.sqlite"
NAME_RE = re.compile(r"^[A-Z0-9_]{1,8}$")
PASSWORD_ITERATIONS = 120_000


class WorkspaceError(ValueError):
    """Operazione impossibile sul workspace."""


@dataclass
class Database:
    """Un database del workspace, con i suoi campi e la sua sorgente .DBF."""

    workspace: "Workspace"
    name: str
    table: str
    memo_table: str
    fields: tuple[Field, ...]
    source: Path
    origin: str = "imported"
    password_hash: str | None = None
    password_salt: str | None = None
    unlocked: bool = True

    # -- struttura -------------------------------------------------------
    @property
    def locked(self) -> bool:
        return bool(self.password_hash) and not self.unlocked

    def field(self, name: str) -> Field:
        for field in self.fields:
            if field.name == name:
                return field
        raise KeyError(name)

    @property
    def memo_fields(self) -> tuple[Field, ...]:
        return tuple(field for field in self.fields if field.is_memo)

    def record_length(self) -> int:
        return sum(field.length for field in self.fields)

    # -- stato del database (indice primario, range, revisione) ----------
    def revision(self) -> int:
        return self.workspace.database_revision(self.name)

    def bump_revision(self) -> None:
        self.workspace.bump_revision(self.name)

    @property
    def primary_index(self) -> str:
        return self.workspace.primary_index(self.name)

    def set_primary_index(self, value: str) -> None:
        self.workspace.set_primary_index(self.name, value)

    @property
    def current_range(self):
        return self.workspace.current_range(self.name)

    def save_current_range(self, settings) -> None:
        self.workspace.save_current_range(self.name, settings)

    # -- regole di campo -------------------------------------------------
    def field_rules(self) -> dict:
        return self.workspace.field_rules(self.name)

    def field_rule(self, field_name: str):
        return self.workspace.field_rules(self.name).get(field_name.upper())

    def save_field_rule(self, rule) -> None:
        self.workspace.save_field_rule(self.name, rule)

    def delete_field_rule(self, field_name: str) -> None:
        self.workspace.delete_field_rule(self.name, field_name)

    def clear_field_rules(self) -> None:
        self.workspace.clear_field_rules(self.name)

    # -- lettura ---------------------------------------------------------
    def count(self, *, include_deleted: bool = False) -> int:
        sql = f'SELECT COUNT(*) FROM "{self.table}"'
        if not include_deleted:
            sql += " WHERE __deleted = 0"
        row = self.workspace._connection.execute(sql).fetchone()
        return int(row[0])

    def sequences(self, *, include_deleted: bool = False) -> list[int]:
        sql = f'SELECT __seq FROM "{self.table}"'
        if not include_deleted:
            sql += " WHERE __deleted = 0"
        sql += " ORDER BY __seq"
        return [int(row[0]) for row in self.workspace._connection.execute(sql)]

    def is_deleted(self, seq: int) -> bool:
        row = self.workspace._connection.execute(
            f'SELECT __deleted FROM "{self.table}" WHERE __seq = ?', (seq,)
        ).fetchone()
        return bool(row[0]) if row else False

    def read(self, seq: int) -> dict[str, str]:
        """Legge un record; per i campi memo il valore è il testo del memo."""
        row = self.workspace._connection.execute(
            f'SELECT * FROM "{self.table}" WHERE __seq = ?', (seq,)
        ).fetchone()
        if row is None:
            raise WorkspaceError(f"Record {seq} does not exist.")
        values: dict[str, str] = {}
        for field in self.fields:
            values[field.name] = str(row[field.name] or "")
        if self.memo_fields:
            for field_name, body in self.workspace._connection.execute(
                    f'SELECT field, body FROM "{self.memo_table}" WHERE seq = ?', (seq,)):
                values[field_name] = body
        return values

    def iter_values(self, *, include_deleted: bool = True) -> Iterable[tuple[int, bool, dict[str, str]]]:
        """Scorre i record in ordine di `__seq` (per il salvataggio su DBF)."""
        sql = f'SELECT * FROM "{self.table}"'
        if not include_deleted:
            sql += " WHERE __deleted = 0"
        sql += " ORDER BY __seq"
        memo_rows: dict[tuple[int, str], str] = {}
        if self.memo_fields:
            for seq, field_name, body in self.workspace._connection.execute(
                    f'SELECT seq, field, body FROM "{self.memo_table}"'):
                memo_rows[(int(seq), field_name)] = body
        for row in self.workspace._connection.execute(sql):
            seq = int(row["__seq"])
            values = {field.name: str(row[field.name] or "") for field in self.fields}
            for field in self.memo_fields:
                values[field.name] = memo_rows.get((seq, field.name), "")
            yield seq, bool(row["__deleted"]), values

    def browse(self, *, include_deleted: bool = False) -> list[tuple[int, bool, dict[str, str]]]:
        """Righe per la browse table, senza caricare i memo uno per uno."""
        rows: list[tuple[int, bool, dict[str, str]]] = []
        for seq, deleted, values in self.iter_values(include_deleted=include_deleted):
            for field in self.memo_fields:
                values[field.name] = "<Memo>" if values.get(field.name) else ""
            rows.append((seq, deleted, values))
        return rows

    # -- scrittura -------------------------------------------------------
    def memo(self, seq: int, field_name: str) -> str:
        self.field(field_name)
        row = self.workspace._connection.execute(
            f'SELECT body FROM "{self.memo_table}" WHERE seq = ? AND field = ?',
            (seq, field_name),
        ).fetchone()
        return str(row[0]) if row else ""

    def append(self, values: dict[str, str]) -> int:
        """Inserisce un record; i campi memo finiscono nella tabella memo."""
        clean = self._clean_values(values)
        columns = ["__deleted"] + [self._quote(field.name) for field in self.fields]
        placeholders = ["0"] + ["?" for _ in self.fields]
        params = [clean[field.name] if not field.is_memo else ""
                  for field in self.fields]
        sql = (f'INSERT INTO "{self.table}" ({", ".join(columns)}) '
               f'VALUES ({", ".join(placeholders)})')
        cursor = self.workspace._connection.execute(sql, params)
        seq = int(cursor.lastrowid)
        for field in self.memo_fields:
            body = clean.get(field.name, "")
            if body:
                self._write_memo(seq, field.name, body)
        self.workspace._connection.commit()
        self.bump_revision()
        return seq

    def update(self, seq: int, values: dict[str, str]) -> None:
        clean = self._clean_values(values)
        normal_fields = [field for field in self.fields if not field.is_memo]
        if normal_fields:
            assignments = ", ".join(f'{self._quote(field.name)} = ?'
                                    for field in normal_fields)
            params = [clean[field.name] for field in normal_fields] + [seq]
            self.workspace._connection.execute(
                f'UPDATE "{self.table}" SET {assignments} WHERE __seq = ?', params
            )
        for field in self.memo_fields:
            self._write_memo(seq, field.name, clean.get(field.name, ""))
        self.workspace._connection.commit()
        self.bump_revision()

    def set_deleted(self, seq: int, deleted: bool) -> None:
        self.workspace._connection.execute(
            f'UPDATE "{self.table}" SET __deleted = ? WHERE __seq = ?',
            (1 if deleted else 0, seq),
        )
        self.workspace._connection.commit()
        self.bump_revision()

    def delete(self, seq: int) -> None:
        self.set_deleted(seq, True)

    def undelete(self, seq: int) -> None:
        self.set_deleted(seq, False)

    def pack(self) -> int:
        """Elimina fisicamente i record cancellati e rinumera `__seq`."""
        rows = list(self.iter_values(include_deleted=False))
        self.workspace._connection.execute(f'DELETE FROM "{self.table}"')
        self.workspace._connection.execute(f'DELETE FROM "{self.memo_table}"')
        self.workspace._connection.execute(
            "DELETE FROM sqlite_sequence WHERE name = ?", (self.table,)
        )
        for new_seq, (_old_seq, _deleted, values) in enumerate(rows, start=1):
            clean = self._clean_values(values)
            columns = ["__seq", "__deleted"] + [self._quote(field.name)
                                                 for field in self.fields]
            placeholders = ["?", "0"] + ["?" for _ in self.fields]
            params = [new_seq] + [clean[field.name] if not field.is_memo else ""
                                  for field in self.fields]
            self.workspace._connection.execute(
                f'INSERT INTO "{self.table}" ({", ".join(columns)}) '
                f'VALUES ({", ".join(placeholders)})', params)
            for field in self.memo_fields:
                body = clean.get(field.name, "")
                if body:
                    self._write_memo(new_seq, field.name, body)
        self.workspace._connection.commit()
        self.bump_revision()
        return len(rows)

    def zap(self) -> None:
        self.workspace._connection.execute(f'DELETE FROM "{self.table}"')
        self.workspace._connection.execute(f'DELETE FROM "{self.memo_table}"')
        self.workspace._connection.execute(
            "DELETE FROM sqlite_sequence WHERE name = ?", (self.table,))
        self.workspace._connection.commit()
        self.bump_revision()

    # -- interni ---------------------------------------------------------
    def _clean_values(self, values: dict[str, str]) -> dict[str, str]:
        clean: dict[str, str] = {}
        for field in self.fields:
            value = values.get(field.name, "")
            try:
                clean[field.name] = parse_value(field, value)
            except FieldError as exc:
                raise WorkspaceError(f"{field.name}: {exc}") from exc
        return clean

    def _write_memo(self, seq: int, field_name: str, body: str) -> None:
        self.workspace._connection.execute(
            f'DELETE FROM "{self.memo_table}" WHERE seq = ? AND field = ?',
            (seq, field_name),
        )
        if body:
            self.workspace._connection.execute(
                f'INSERT INTO "{self.memo_table}" (seq, field, body) VALUES (?, ?, ?)',
                (seq, field_name, body),
            )

    @staticmethod
    def _quote(name: str) -> str:
        return '"' + name.replace('"', '""') + '"'


class Workspace:
    """Catalogo SQLite di una cartella di dati."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory).expanduser().resolve()
        self.path = self.directory / WORKSPACE_FILE
        self._connection = self._connect()
        self._ensure_schema()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    # -- connessione -----------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise WorkspaceError(f"Cannot use {self.directory}: {exc}") from exc
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def close(self) -> None:
        self._connection.close()

    def _ensure_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS adbx_databases (
                name TEXT PRIMARY KEY,
                table_name TEXT NOT NULL UNIQUE,
                memo_table TEXT NOT NULL,
                fields TEXT NOT NULL,
                source TEXT NOT NULL,
                origin TEXT NOT NULL DEFAULT 'imported',
                created REAL NOT NULL,
                updated REAL NOT NULL,
                password_hash TEXT,
                password_salt TEXT
            );
            CREATE TABLE IF NOT EXISTS adbx_database_state (
                database TEXT PRIMARY KEY,
                primary_index TEXT NOT NULL DEFAULT 'RECORD NUMBER',
                range_json TEXT NOT NULL DEFAULT '',
                revision INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS adbx_indexes (
                database TEXT NOT NULL,
                name TEXT NOT NULL,
                definition TEXT NOT NULL,
                PRIMARY KEY (database, name)
            );
            CREATE TABLE IF NOT EXISTS adbx_ranges (
                database TEXT NOT NULL,
                letter TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                settings TEXT NOT NULL,
                PRIMARY KEY (database, letter)
            );
            CREATE TABLE IF NOT EXISTS adbx_searches (
                database TEXT NOT NULL,
                letter TEXT NOT NULL,
                definition TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (database, letter)
            );
            CREATE TABLE IF NOT EXISTS adbx_search_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                database TEXT NOT NULL,
                letter TEXT,
                description TEXT NOT NULL DEFAULT '',
                search_expression TEXT NOT NULL DEFAULT '',
                sort_expression TEXT NOT NULL DEFAULT '',
                sort_rows TEXT NOT NULL DEFAULT '[]',
                show TEXT NOT NULL DEFAULT 'not_deleted',
                case_sensitive INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 0,
                created REAL NOT NULL,
                seqs TEXT NOT NULL DEFAULT '[]',
                range_json TEXT NOT NULL DEFAULT '{}',
                def_version INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS adbx_forms (
                owner TEXT NOT NULL,
                letter TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                definition TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 0,
                updated REAL NOT NULL,
                PRIMARY KEY (owner, letter)
            );
            CREATE TABLE IF NOT EXISTS adbx_letters (
                owner TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL,
                updated REAL NOT NULL,
                PRIMARY KEY (owner, name)
            );
            CREATE TABLE IF NOT EXISTS adbx_labels (
                owner TEXT NOT NULL,
                letter TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                definition TEXT NOT NULL,
                updated REAL NOT NULL,
                PRIMARY KEY (owner, letter)
            );
            CREATE TABLE IF NOT EXISTS adbx_reports (
                owner TEXT NOT NULL,
                letter TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                definition TEXT NOT NULL,
                updated REAL NOT NULL,
                PRIMARY KEY (owner, letter)
            );
            CREATE TABLE IF NOT EXISTS adbx_sets (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL DEFAULT '',
                primary_database TEXT NOT NULL,
                show_mode TEXT NOT NULL DEFAULT 'not_deleted',
                filter TEXT NOT NULL DEFAULT '',
                filter_active INTEGER NOT NULL DEFAULT 0,
                created REAL NOT NULL,
                updated REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS adbx_set_links (
                set_name TEXT NOT NULL,
                position INTEGER NOT NULL,
                parent TEXT NOT NULL,
                child TEXT NOT NULL,
                linking_index TEXT NOT NULL DEFAULT '',
                common TEXT NOT NULL DEFAULT '',
                link_to TEXT NOT NULL DEFAULT 'First',
                edit_child TEXT NOT NULL DEFAULT 'Yes',
                add_child TEXT NOT NULL DEFAULT 'Yes',
                referential INTEGER NOT NULL DEFAULT 0,
                cascading_updates INTEGER NOT NULL DEFAULT 0,
                cascading_deletes INTEGER NOT NULL DEFAULT 0,
                include_parent TEXT NOT NULL DEFAULT 'Always',
                show_mode TEXT NOT NULL DEFAULT 'not_deleted',
                filter TEXT NOT NULL DEFAULT '',
                filter_active INTEGER NOT NULL DEFAULT 0,
                integrity TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (set_name, position)
            );
            CREATE TABLE IF NOT EXISTS adbx_field_rules (
                owner TEXT NOT NULL,
                field TEXT NOT NULL,
                rules TEXT NOT NULL,
                PRIMARY KEY (owner, field)
            );
            CREATE TABLE IF NOT EXISTS adbx_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        for row in self._connection.execute("SELECT name FROM adbx_databases"):
            self._ensure_database_state(row["name"])
        self._connection.commit()

    def _ensure_database_state(self, name: str) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO adbx_database_state (database) VALUES (?)",
            (name,))
        self._connection.commit()

    # -- impostazioni globali --------------------------------------------
    def setting(self, key: str, default: str = "") -> str:
        row = self._connection.execute(
            "SELECT value FROM adbx_settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row is not None else default

    def set_setting(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT INTO adbx_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value))
        self._connection.commit()

    @property
    def pattern_mode(self) -> str:
        from .expressions import PATTERN_EXACT, PATTERN_MODES
        value = self.setting("pattern_matching", PATTERN_EXACT)
        return value if value in PATTERN_MODES else PATTERN_EXACT

    @pattern_mode.setter
    def pattern_mode(self, value: str) -> None:
        from .expressions import PATTERN_EXACT, PATTERN_MODES
        self.set_setting("pattern_matching",
                         value if value in PATTERN_MODES else PATTERN_EXACT)

    # -- stato del database ----------------------------------------------
    def database_revision(self, name: str) -> int:
        row = self._connection.execute(
            "SELECT revision FROM adbx_database_state WHERE database = ?",
            (name,)).fetchone()
        return int(row["revision"]) if row is not None else 0

    def bump_revision(self, name: str) -> None:
        self._ensure_database_state(name)
        self._connection.execute(
            "UPDATE adbx_database_state SET revision = revision + 1 "
            "WHERE database = ?", (name,))
        self._connection.commit()

    def primary_index(self, name: str) -> str:
        row = self._connection.execute(
            "SELECT primary_index FROM adbx_database_state WHERE database = ?",
            (name,)).fetchone()
        return str(row["primary_index"]) if row is not None else "RECORD NUMBER"

    def set_primary_index(self, name: str, value: str) -> None:
        self._ensure_database_state(name)
        row = self._connection.execute(
            "SELECT range_json FROM adbx_database_state WHERE database = ?",
            (name,)).fetchone()
        data = {}
        if row is not None and row["range_json"]:
            try:
                data = json.loads(row["range_json"])
            except ValueError:
                data = {}
        data["primary"] = value
        self._connection.execute(
            "UPDATE adbx_database_state SET primary_index = ?, range_json = ? "
            "WHERE database = ?", (value, json.dumps(data), name))
        self._connection.commit()

    def current_range(self, name: str):
        from .indexing import RangeSettings

        row = self._connection.execute(
            "SELECT range_json FROM adbx_database_state WHERE database = ?",
            (name,)).fetchone()
        raw = row["range_json"] if row is not None else ""
        if not raw:
            return RangeSettings()
        return RangeSettings.from_dict(json.loads(raw))

    def save_current_range(self, name: str, settings) -> None:
        self._ensure_database_state(name)
        self._connection.execute(
            "UPDATE adbx_database_state SET range_json = ?, primary_index = ? "
            "WHERE database = ?",
            (json.dumps(settings.to_dict()), settings.primary, name))
        self._connection.commit()

    # -- form ------------------------------------------------------------
    def forms(self, owner: str) -> list:
        from .forms import FormDefinition

        owner = owner.strip().upper()
        result = []
        for row in self._connection.execute(
                "SELECT definition FROM adbx_forms WHERE owner = ? "
                "ORDER BY letter", (owner,)):
            try:
                import json
                result.append(FormDefinition.from_dict(
                    self, json.loads(row["definition"])))
            except (ValueError, TypeError):
                continue
        return result

    def form_names(self, owner: str) -> list[str]:
        return [form.label for form in self.forms(owner)]

    def get_form(self, owner: str, letter: str):
        import json

        from .forms import FormDefinition

        row = self._connection.execute(
            "SELECT definition FROM adbx_forms WHERE owner = ? AND letter = ?",
            (owner.strip().upper(), letter.strip().upper())).fetchone()
        if row is None:
            return None
        return FormDefinition.from_dict(self, json.loads(row["definition"]))

    def active_form(self, owner: str):
        import json

        from .forms import FormDefinition

        row = self._connection.execute(
            "SELECT definition FROM adbx_forms WHERE owner = ? AND active = 1",
            (owner.strip().upper(),)).fetchone()
        if row is None:
            return None
        return FormDefinition.from_dict(self, json.loads(row["definition"]))

    def save_form(self, form) -> None:
        import json

        form.validate()
        self._connection.execute(
            "UPDATE adbx_forms SET active = 0 WHERE owner = ?", (form.owner,))
        self._connection.execute(
            "INSERT INTO adbx_forms (owner, letter, description, definition, "
            "active, updated) VALUES (?, ?, ?, ?, 1, ?) "
            "ON CONFLICT(owner, letter) DO UPDATE SET "
            "description = excluded.description, "
            "definition = excluded.definition, active = 1, "
            "updated = excluded.updated",
            (form.owner, form.letter, form.description,
             json.dumps(form.to_dict()), time.time()))
        self._connection.commit()

    def set_active_form(self, owner: str, letter: str) -> bool:
        owner = owner.strip().upper()
        letter = letter.strip().upper()
        row = self._connection.execute(
            "SELECT 1 FROM adbx_forms WHERE owner = ? AND letter = ?",
            (owner, letter)).fetchone()
        if row is None:
            return False
        self._connection.execute(
            "UPDATE adbx_forms SET active = 0 WHERE owner = ?", (owner,))
        self._connection.execute(
            "UPDATE adbx_forms SET active = 1 WHERE owner = ? AND letter = ?",
            (owner, letter))
        self._connection.commit()
        return True

    def delete_form(self, owner: str, letter: str) -> bool:
        owner = owner.strip().upper()
        letter = letter.strip().upper()
        cursor = self._connection.execute(
            "DELETE FROM adbx_forms WHERE owner = ? AND letter = ?",
            (owner, letter))
        self._connection.commit()
        return cursor.rowcount > 0

    # -- letter ----------------------------------------------------------
    def letters(self, owner: str) -> list:
        from .letters import LetterDefinition

        result = []
        for row in self._connection.execute(
                "SELECT name, description, body FROM adbx_letters "
                "WHERE owner = ? ORDER BY name", (owner.strip().upper(),)):
            result.append(LetterDefinition(
                self, owner, str(row["name"]), str(row["description"]),
                str(row["body"]).splitlines() or [""]))
        return result

    def letter_names(self, owner: str) -> list[str]:
        return [letter.label for letter in self.letters(owner)]

    def get_letter(self, owner: str, name: str):
        from .letters import LetterDefinition

        row = self._connection.execute(
            "SELECT description, body FROM adbx_letters "
            "WHERE owner = ? AND name = ?",
            (owner.strip().upper(), name.strip().upper())).fetchone()
        if row is None:
            return None
        return LetterDefinition(self, owner, name, str(row["description"]),
                                str(row["body"]).splitlines() or [""])

    def save_letter(self, letter) -> None:
        letter.validate()
        self._connection.execute(
            "INSERT INTO adbx_letters (owner, name, description, body, updated) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(owner, name) DO UPDATE SET "
            "description = excluded.description, body = excluded.body, "
            "updated = excluded.updated",
            (letter.owner, letter.name, letter.description, letter.text,
             time.time()))
        self._connection.commit()

    def delete_letter(self, owner: str, name: str) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM adbx_letters WHERE owner = ? AND name = ?",
            (owner.strip().upper(), name.strip().upper()))
        self._connection.commit()
        return cursor.rowcount > 0

    # -- label -----------------------------------------------------------
    def labels(self, owner: str) -> list:
        from .labels import LabelDefinition

        owner = owner.strip().upper()
        result = []
        for row in self._connection.execute(
                "SELECT definition FROM adbx_labels WHERE owner = ? "
                "ORDER BY letter", (owner,)):
            try:
                result.append(LabelDefinition.from_dict(
                    self, json.loads(row["definition"])))
            except (ValueError, TypeError):
                continue
        return result

    def label_names(self, owner: str) -> list[str]:
        return [label.label for label in self.labels(owner)]

    def get_label(self, owner: str, letter: str):
        from .labels import LabelDefinition

        row = self._connection.execute(
            "SELECT definition FROM adbx_labels WHERE owner = ? AND letter = ?",
            (owner.strip().upper(), letter.strip().upper())).fetchone()
        if row is None:
            return None
        return LabelDefinition.from_dict(self, json.loads(row["definition"]))

    def save_label(self, label) -> None:
        label.validate()
        self._connection.execute(
            "INSERT INTO adbx_labels (owner, letter, description, definition, "
            "updated) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(owner, letter) DO UPDATE SET "
            "description = excluded.description, "
            "definition = excluded.definition, updated = excluded.updated",
            (label.owner, label.letter, label.description,
             json.dumps(label.to_dict()), time.time()))
        self._connection.commit()

    def delete_label(self, owner: str, letter: str) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM adbx_labels WHERE owner = ? AND letter = ?",
            (owner.strip().upper(), letter.strip().upper()))
        self._connection.commit()
        return cursor.rowcount > 0

    # -- report ----------------------------------------------------------
    def reports(self, owner: str) -> list:
        from .reports import ReportDefinition

        owner = owner.strip().upper()
        result = []
        for row in self._connection.execute(
                "SELECT definition FROM adbx_reports WHERE owner = ? "
                "ORDER BY letter", (owner,)):
            try:
                result.append(ReportDefinition.from_dict(
                    self, json.loads(row["definition"])))
            except (ValueError, TypeError):
                continue
        return result

    def report_names(self, owner: str) -> list[str]:
        return [report.label for report in self.reports(owner)]

    def get_report(self, owner: str, letter: str):
        from .reports import ReportDefinition

        row = self._connection.execute(
            "SELECT definition FROM adbx_reports WHERE owner = ? AND letter = ?",
            (owner.strip().upper(), letter.strip().upper())).fetchone()
        if row is None:
            return None
        return ReportDefinition.from_dict(self, json.loads(row["definition"]))

    def save_report(self, report) -> None:
        report.validate()
        self._connection.execute(
            "INSERT INTO adbx_reports (owner, letter, description, definition, "
            "updated) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(owner, letter) DO UPDATE SET "
            "description = excluded.description, "
            "definition = excluded.definition, updated = excluded.updated",
            (report.owner, report.letter, report.description,
             json.dumps(report.to_dict()), time.time()))
        self._connection.commit()

    def delete_report(self, owner: str, letter: str) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM adbx_reports WHERE owner = ? AND letter = ?",
            (owner.strip().upper(), letter.strip().upper()))
        self._connection.commit()
        return cursor.rowcount > 0

    # -- set -------------------------------------------------------------
    def set_names(self) -> list[str]:
        return [str(row[0]) for row in self._connection.execute(
            "SELECT name FROM adbx_sets ORDER BY name")]

    def get_set(self, name: str):
        from .sets import _set_from_row

        row = self._connection.execute(
            "SELECT * FROM adbx_sets WHERE name = ?",
            (name.strip().upper(),)).fetchone()
        if row is None:
            return None
        return _set_from_row(self, row)

    def save_set(self, definition) -> None:
        import json

        now = time.time()
        created = definition.created or now
        self._connection.execute(
            "INSERT INTO adbx_sets (name, description, primary_database, "
            "show_mode, filter, filter_active, created, updated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET description = excluded.description, "
            "primary_database = excluded.primary_database, "
            "show_mode = excluded.show_mode, filter = excluded.filter, "
            "filter_active = excluded.filter_active, updated = excluded.updated",
            (definition.name, definition.description, definition.primary,
             definition.show_mode, definition.filter,
             1 if definition.filter_active else 0, created, now))
        self._connection.execute(
            "DELETE FROM adbx_set_links WHERE set_name = ?", (definition.name,))
        for position, link in enumerate(definition.links):
            link.normalize()
            self._connection.execute(
                "INSERT INTO adbx_set_links (set_name, position, parent, child, "
                "linking_index, common, link_to, edit_child, add_child, "
                "referential, cascading_updates, cascading_deletes, "
                "include_parent, show_mode, filter, filter_active, integrity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (definition.name, position, link.parent, link.child,
                 link.linking_index, link.common, link.link_to,
                 link.edit_child, link.add_child,
                 1 if link.referential else 0,
                 1 if link.cascading_updates else 0,
                 1 if link.cascading_deletes else 0, link.include_parent,
                 link.show_mode, link.filter,
                 1 if link.filter_active else 0,
                 json.dumps([[parent, child]
                             for parent, child in link.integrity])))
        self._connection.commit()
        definition.created = created
        definition.updated = now

    def delete_set(self, name: str) -> bool:
        name = name.strip().upper()
        if self.get_set(name) is None:
            return False
        self._connection.execute(
            "DELETE FROM adbx_set_links WHERE set_name = ?", (name,))
        self._connection.execute(
            "DELETE FROM adbx_sets WHERE name = ?", (name,))
        self._connection.execute(
            "DELETE FROM adbx_field_rules WHERE owner = ?", (name,))
        self._connection.execute(
            "DELETE FROM adbx_forms WHERE owner = ?", (name,))
        self._connection.execute(
            "DELETE FROM adbx_reports WHERE owner = ?", (name,))
        self._connection.execute(
            "DELETE FROM adbx_labels WHERE owner = ?", (name,))
        self._connection.execute(
            "DELETE FROM adbx_letters WHERE owner = ?", (name,))
        self._connection.commit()
        return True

    # -- regole di campo -------------------------------------------------
    def field_rules(self, owner: str) -> dict:
        from .rules import FieldRule

        rules: dict[str, FieldRule] = {}
        for row in self._connection.execute(
                "SELECT field, rules FROM adbx_field_rules WHERE owner = ? "
                "ORDER BY field", (owner.strip().upper(),)):
            try:
                rule = FieldRule.from_dict(json.loads(row["rules"]))
            except (ValueError, TypeError):
                continue
            rules[rule.field_name] = rule
        return rules

    def save_field_rule(self, owner: str, rule) -> None:
        owner = owner.strip().upper()
        if rule.is_empty:
            self.delete_field_rule(owner, rule.field_name)
            return
        self._connection.execute(
            "INSERT INTO adbx_field_rules (owner, field, rules) "
            "VALUES (?, ?, ?) ON CONFLICT(owner, field) DO UPDATE SET "
            "rules = excluded.rules",
            (owner, rule.field_name.upper(), json.dumps(rule.to_dict())))
        self._connection.commit()

    def delete_field_rule(self, owner: str, field_name: str) -> None:
        self._connection.execute(
            "DELETE FROM adbx_field_rules WHERE owner = ? AND field = ?",
            (owner.strip().upper(), field_name.upper()))
        self._connection.commit()

    def clear_field_rules(self, owner: str) -> None:
        self._connection.execute(
            "DELETE FROM adbx_field_rules WHERE owner = ?",
            (owner.strip().upper(),))
        self._connection.commit()

    # -- catalogo --------------------------------------------------------
    def names(self) -> list[str]:
        return [row[0] for row in self._connection.execute(
            "SELECT name FROM adbx_databases ORDER BY name")]

    def get(self, name: str) -> Database | None:
        row = self._connection.execute(
            "SELECT * FROM adbx_databases WHERE name = ?", (name.strip().upper(),)
        ).fetchone()
        if row is None:
            return None
        fields = tuple(Field.from_dict(item) for item in json.loads(row["fields"]))
        return Database(
            workspace=self,
            name=row["name"],
            table=row["table_name"],
            memo_table=row["memo_table"],
            fields=fields,
            source=Path(row["source"]),
            origin=row["origin"],
            password_hash=row["password_hash"],
            password_salt=row["password_salt"],
            unlocked=not bool(row["password_hash"]),
        )

    def open_database(self, path: str | Path) -> Database:
        """Apre il database indicato, importandolo dal .DBF la prima volta."""
        path = Path(path).expanduser()
        name = path.stem.upper()
        existing = self.get(name)
        if existing is not None:
            return existing
        return self.import_dbf(path)

    def create_database(self, name: str, fields: Sequence[Field],
                        *, password: str | None = None) -> Database:
        name = name.strip().upper()
        if name.endswith(".DBF"):
            name = name[:-4]
        if not NAME_RE.match(name):
            raise WorkspaceError("Database names use 1-8 letters, digits or _.")
        if self.get(name) is not None:
            raise WorkspaceError(f"Database {name} already exists.")
        try:
            validate_fields(list(fields))
        except FieldError as exc:
            raise WorkspaceError(str(exc)) from exc
        source = self.directory / f"{name}.DBF"
        if source.exists():
            raise WorkspaceError(f"File {source.name} already exists.")
        table = self._table_name(name)
        memo_table = self._memo_table_name(name)
        self._create_tables(table, memo_table, fields)
        salt = hash_value = None
        if password:
            salt, hash_value = _password_hash(password)
        now = time.time()
        self._connection.execute(
            "INSERT INTO adbx_databases (name, table_name, memo_table, fields, "
            "source, origin, created, updated, password_hash, password_salt) "
            "VALUES (?, ?, ?, ?, ?, 'created', ?, ?, ?, ?)",
            (name, table, memo_table,
             json.dumps([field.to_dict() for field in fields]),
             str(source), now, now, hash_value, salt),
        )
        self._connection.commit()
        self._ensure_database_state(name)
        write_rows(source, fields, [])
        return self.get(name)  # type: ignore[return-value]

    def import_dbf(self, path: str | Path) -> Database:
        path = Path(path).expanduser().resolve()
        name = path.stem.upper()
        existing = self.get(name)
        if existing is not None:
            return existing
        if not path.exists():
            raise WorkspaceError(f"File not found: {path}")
        try:
            header = read_header(path)
        except DbfError as exc:
            raise WorkspaceError(str(exc)) from exc
        if not header.fields:
            raise WorkspaceError(f"{path.name} has no fields.")
        fields = tuple(Field(field.name, field.type, field.length, field.decimals)
                       for field in header.fields)
        try:
            validate_fields(list(fields))
        except FieldError as exc:
            raise WorkspaceError(str(exc)) from exc
        try:
            rows = read_rows(path, header)
        except DbfError as exc:
            raise WorkspaceError(str(exc)) from exc

        table = self._table_name(name)
        memo_table = self._memo_table_name(name)
        self._create_tables(table, memo_table, fields)
        now = time.time()
        self._connection.execute(
            "INSERT INTO adbx_databases (name, table_name, memo_table, fields, "
            "source, origin, created, updated) VALUES (?, ?, ?, ?, ?, 'imported', ?, ?)",
            (name, table, memo_table,
             json.dumps([field.to_dict() for field in fields]),
             str(path), now, now),
        )
        for row in rows:
            clean = canonical_row(path, row, fields)
            columns = ["__deleted"] + [Database._quote(field.name) for field in fields]
            placeholders = ["?"] + ["?" for _ in fields]
            params = [1 if row.deleted else 0] + [
                clean[field.name] if not field.is_memo else "" for field in fields]
            cursor = self._connection.execute(
                f'INSERT INTO "{table}" ({", ".join(columns)}) '
                f'VALUES ({", ".join(placeholders)})', params)
            seq = int(cursor.lastrowid)
            for field in fields:
                if field.is_memo and clean.get(field.name):
                    self._connection.execute(
                        f'INSERT INTO "{memo_table}" (seq, field, body) VALUES (?, ?, ?)',
                        (seq, field.name, clean[field.name]))
        self._connection.commit()
        self._ensure_database_state(name)
        return self.get(name)  # type: ignore[return-value]

    def alter_database(self, name: str,
                       mapping: Sequence[tuple[str | None, Field]]) -> Database:
        """Riconfigura un database applicando la tabella di conversione.

        `mapping` elenca i nuovi campi nell'ordine voluto; il primo elemento
        è il nome originale (None per un campo nuovo). I campi spariti dal
        mapping vengono eliminati; un nome cambiato conserva i valori.
        """
        database = self.get(name)
        if database is None:
            raise WorkspaceError(f"Database {name} does not exist.")
        new_fields = [field for _old, field in mapping]
        try:
            validate_fields(new_fields)
        except FieldError as exc:
            raise WorkspaceError(str(exc)) from exc
        old_fields = {field.name: field for field in database.fields}
        old_rows = list(database.iter_values())
        old_memos = {(seq, field.name): values[field.name]
                     for seq, _deleted, values in old_rows
                     for field in database.memo_fields}

        new_table = self._table_name(name, suffix="_new")
        new_memo = self._memo_table_name(name, suffix="_new")
        self._create_tables(new_table, new_memo, new_fields)
        try:
            for seq, deleted, values in old_rows:
                converted: dict[str, str] = {}
                memos: dict[str, str] = {}
                for old_name, new_field in mapping:
                    if old_name is None or old_name not in old_fields:
                        converted[new_field.name] = ""
                        continue
                    old_field = old_fields[old_name]
                    if old_field.is_memo:
                        old_value = old_memos.get((seq, old_name), "")
                    else:
                        old_value = values.get(old_name, "")
                    if new_field.is_memo:
                        converted[new_field.name] = ""
                        memos[new_field.name] = old_value
                    else:
                        converted[new_field.name] = convert_value(
                            old_field, new_field, old_value)
                columns = ["__seq", "__deleted"] + [
                    Database._quote(field.name) for field in new_fields]
                placeholders = ["?", "?"] + ["?" for _ in new_fields]
                params = [seq, 1 if deleted else 0] + [
                    converted[field.name] if not field.is_memo else ""
                    for field in new_fields]
                self._connection.execute(
                    f'INSERT INTO "{new_table}" ({", ".join(columns)}) '
                    f'VALUES ({", ".join(placeholders)})', params)
                for field in new_fields:
                    if field.is_memo and memos.get(field.name):
                        self._connection.execute(
                            f'INSERT INTO "{new_memo}" (seq, field, body) '
                            "VALUES (?, ?, ?)",
                            (seq, field.name, memos[field.name]))
            self._connection.execute(f'DROP TABLE "{database.table}"')
            self._connection.execute(f'DROP TABLE "{database.memo_table}"')
            self._connection.execute(
                f'ALTER TABLE "{new_table}" RENAME TO "{database.table}"')
            self._connection.execute(
                f'ALTER TABLE "{new_memo}" RENAME TO "{database.memo_table}"')
            self._connection.execute(
                "UPDATE adbx_databases SET fields = ?, updated = ? WHERE name = ?",
                (json.dumps([field.to_dict() for field in new_fields]),
                 time.time(), database.name))
            self._migrate_field_rules(database.name, mapping)
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            self._drop_tables(new_table, new_memo)
            raise
        updated = self.get(database.name)
        assert updated is not None
        self.save_database(updated)
        updated.bump_revision()
        return updated

    def _migrate_field_rules(self, owner: str,
                             mapping: Sequence[tuple[str | None, Field]]) -> None:
        """Segue i campi rinominati e cancella le regole dei campi rimossi."""
        existing = self.field_rules(owner)
        wanted: dict[str, tuple[str, object]] = {}
        for old_name, new_field in mapping:
            if old_name is None or old_name not in existing:
                continue
            wanted[new_field.name] = (new_field.name, existing[old_name])
        self._connection.execute(
            "DELETE FROM adbx_field_rules WHERE owner = ?", (owner,))
        for field_name, (_name, rule) in wanted.items():
            rule.field_name = field_name
            self._connection.execute(
                "INSERT OR REPLACE INTO adbx_field_rules (owner, field, rules) "
                "VALUES (?, ?, ?)",
                (owner, field_name, json.dumps(rule.to_dict())))

    def drop_database(self, name: str) -> bool:
        database = self.get(name)
        if database is None:
            return False
        self._drop_tables(database.table, database.memo_table)
        self._connection.execute("DELETE FROM adbx_databases WHERE name = ?", (name,))
        self._connection.execute("DELETE FROM adbx_database_state WHERE database = ?", (name,))
        self._connection.execute("DELETE FROM adbx_indexes WHERE database = ?", (name,))
        self._connection.execute("DELETE FROM adbx_ranges WHERE database = ?", (name,))
        self._connection.execute("DELETE FROM adbx_searches WHERE database = ?", (name,))
        self._connection.execute("DELETE FROM adbx_search_lists WHERE database = ?", (name,))
        self._connection.execute("DELETE FROM adbx_field_rules WHERE owner = ?", (name,))
        self._connection.execute("DELETE FROM adbx_reports WHERE owner = ?", (name,))
        self._connection.execute("DELETE FROM adbx_labels WHERE owner = ?", (name,))
        self._connection.execute("DELETE FROM adbx_letters WHERE owner = ?", (name,))
        for set_row in self._connection.execute(
                "SELECT name, primary_database FROM adbx_sets"):
            if str(set_row["primary_database"]) == name or any(
                    str(link_row[0]) == name for link_row in self._connection.execute(
                        "SELECT child FROM adbx_set_links WHERE set_name = ?",
                        (set_row["name"],))):
                self._connection.execute(
                    "DELETE FROM adbx_set_links WHERE set_name = ?",
                    (set_row["name"],))
                self._connection.execute(
                    "DELETE FROM adbx_sets WHERE name = ?", (set_row["name"],))
        self._connection.commit()
        if database.origin == "created" and database.source.parent == self.directory:
            try:
                database.source.unlink(missing_ok=True)
                memo_path(database.source).unlink(missing_ok=True)
            except OSError:
                pass
        return True

    def save_database(self, database: Database) -> None:
        """Riscrive il .DBF con tutti i record, nell'ordine di `__seq`."""
        rows = [(deleted, values)
                for _seq, deleted, values in database.iter_values(include_deleted=True)]
        write_rows(database.source, database.fields, rows)
        self._connection.execute(
            "UPDATE adbx_databases SET updated = ? WHERE name = ?",
            (time.time(), database.name))
        self._connection.commit()

    # -- password --------------------------------------------------------
    def set_password(self, name: str, password: str | None) -> None:
        database = self.get(name)
        if database is None:
            raise WorkspaceError(f"Database {name} does not exist.")
        if password:
            salt, hashed = _password_hash(password)
        else:
            salt = hashed = None
        self._connection.execute(
            "UPDATE adbx_databases SET password_hash = ?, password_salt = ? "
            "WHERE name = ?", (hashed, salt, database.name))
        self._connection.commit()
        database.password_hash = hashed
        database.password_salt = salt
        database.unlocked = not bool(hashed)

    def check_password(self, database: Database, password: str) -> bool:
        if not database.password_hash or not database.password_salt:
            return True
        if _password_hash(password, database.password_salt)[1] == database.password_hash:
            database.unlocked = True
            return True
        return False

    # -- interni ---------------------------------------------------------
    def _table_name(self, name: str, suffix: str = "") -> str:
        base = "t_" + re.sub(r"[^a-z0-9_]", "_", name.lower()) + suffix
        candidate = base
        counter = 2
        while self._table_exists(candidate):
            candidate = f"{base}_{counter}"
            counter += 1
        return candidate

    def _memo_table_name(self, name: str, suffix: str = "") -> str:
        base = "m_" + re.sub(r"[^a-z0-9_]", "_", name.lower()) + suffix
        candidate = base
        counter = 2
        while self._table_exists(candidate):
            candidate = f"{base}_{counter}"
            counter += 1
        return candidate

    def _table_exists(self, name: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,)).fetchone()
        return row is not None

    def _create_tables(self, table: str, memo_table: str,
                       fields: Sequence[Field]) -> None:
        columns = ['"__seq" INTEGER PRIMARY KEY AUTOINCREMENT',
                   '"__deleted" INTEGER NOT NULL DEFAULT 0']
        for field in fields:
            columns.append(f'{Database._quote(field.name)} TEXT NOT NULL DEFAULT \'\'')
        self._connection.execute(f'CREATE TABLE "{table}" ({", ".join(columns)})')
        self._connection.execute(
            f'CREATE TABLE "{memo_table}" (seq INTEGER NOT NULL, '
            "field TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY (seq, field))")
        self._connection.commit()

    def _drop_tables(self, table: str, memo_table: str) -> None:
        self._connection.execute(f'DROP TABLE IF EXISTS "{table}"')
        self._connection.execute(f'DROP TABLE IF EXISTS "{memo_table}"')
        self._connection.commit()


def _password_hash(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PASSWORD_ITERATIONS)
    return salt, digest.hex()


def format_field(database: Database, field: Field, seq: int,
                 values: dict[str, str]) -> str:
    """Testo mostrato in un form, con il memo indicato e non riversato."""
    if field.is_memo:
        return "<Memo>" if values.get(field.name) else ""
    return format_value(field, values.get(field.name, ""))


__all__ = [
    "Database",
    "PASSWORD_ITERATIONS",
    "WORKSPACE_FILE",
    "Workspace",
    "WorkspaceError",
    "format_field",
]
