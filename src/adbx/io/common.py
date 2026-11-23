"""Strutture comuni di import/export (O9).

Il trasferimento avviene sempre in due passi: il lettore produce una tabella
di testo con una proposta di campi, l'utente può correggerla, poi lo strato
dati converte i valori nel testo canonico dei campi. In uscita i valori
canonici vengono formattati secondo il formato scelto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from ..data.fields import (
    MAX_CHARACTER,
    MAX_DECIMALS,
    MAX_NUMERIC,
    Field,
    FieldError,
    parse_value,
)

DATE_FORMATS = (
    re.compile(r"^\d{8}$"),
    re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$"),
    re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2})$"),
)
NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
LOGICAL_TRUE = {"1", "T", "Y", "YES", "TRUE", ".T."}
LOGICAL_FALSE = {"0", "F", "N", "NO", "FALSE", ".F."}


@dataclass
class TableData:
    """Tabella letta da un file, prima della conversione nei tipi."""

    fields: list[Field]
    rows: list[list[str]]
    notes: list[str] = field(default_factory=list)

    @property
    def width(self) -> int:
        return len(self.fields)

    def records(self) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for row in self.rows:
            result.append({
                field.name: row[index] if index < len(row) else ""
                for index, field in enumerate(self.fields)
            })
        return result


@dataclass
class ImportOptions:
    fieldnames: bool = True
    examine: bool = True
    skip_header: int = 0
    decimal_places: int = 0
    encoding: str = "cp437"
    # ASCII carattere-separato
    separator: str = ","
    quote: str = '"'
    record_separator: str = "\r\n"
    # ASCII tabellare
    field_count: int = 1
    width: int = 10
    spacing: int = 1
    linefeeds: bool = True
    record_length: int = 80


@dataclass
class ExportOptions:
    fieldnames: bool = True
    quote_character: bool = True
    suppress_trailing: bool = True
    record_separator: str = "\r\n"
    trailing_separator: bool = False
    encoding: str = "cp437"
    separator: str = ","
    quote: str = '"'
    width: int = 10
    spacing: int = 1
    date_format: str = "MM/DD/YYYY"


def display_value(field: Field, value: str, *,
                  date_format: str = "MM/DD/YYYY") -> str:
    """Valore canonico → testo leggibile per il file di scambio."""
    if field.type == "D":
        text = (value or "").strip()
        if len(text) == 8 and text.isdigit():
            year, month, day = text[:4], text[4:6], text[6:]
            if date_format == "YYYYMMDD":
                return text
            if date_format == "MM/DD/YY":
                return f"{month}/{day}/{year[2:]}"
            return f"{month}/{day}/{year}"
        return text
    if field.type == "L":
        if value == "1":
            return "T"
        if value == "0":
            return "F"
        return ""
    return value or ""


def import_text(field: Field, text: str) -> str:
    """Testo del file → valore canonico, senza sollevare errori."""
    text = text if text is not None else ""
    if field.type == "C":
        return text[: field.length]
    if field.type == "M":
        return text
    if field.type == "N":
        cleaned = text.strip().replace(",", "")
        for symbol in ("$", "€", "£", "¥"):
            cleaned = cleaned.replace(symbol, "")
        try:
            return parse_value(field, cleaned)
        except FieldError:
            return ""
    if field.type == "D":
        return _date_canonical(text)
    if field.type == "L":
        marker = text.strip().upper()
        if marker in LOGICAL_TRUE:
            return "1"
        if marker in LOGICAL_FALSE:
            return "0"
        return ""
    return text[: field.length]


def _date_canonical(text: str) -> str:
    text = text.strip()
    if len(text) == 8 and text.isdigit():
        return text
    for pattern in DATE_FORMATS[1:]:
        match = pattern.match(text)
        if not match:
            continue
        month, day, year = match.groups()
        if len(year) == 2:
            value = int(year)
            year = str(1900 + value if value >= 50 else 2000 + value)
        try:
            return date(int(year), int(month), int(day)).strftime("%Y%m%d")
        except ValueError:
            return ""
    return ""


def infer_fields(columns: Sequence[Sequence[str]], names: Sequence[str] = (),
                 *, decimal_places: int = 0) -> list[Field]:
    """Suggerisce tipo e lunghezza di ogni colonna, come `Examine file`."""
    fields: list[Field] = []
    used: set[str] = set()
    for index, column in enumerate(columns):
        values = [str(value or "").strip() for value in column]
        nonempty = [value for value in values if value]
        name = _field_name(names[index] if index < len(names) else "",
                           index, used)
        if nonempty and all(_looks_date(value) for value in nonempty):
            fields.append(Field(name, "D", 8, 0))
            continue
        if nonempty and all(_looks_logical(value) for value in nonempty):
            fields.append(Field(name, "L", 1, 0))
            continue
        if nonempty and all(_looks_number(value) for value in nonempty):
            decimals = decimal_places
            if decimal_places <= 0:
                decimals = max(_decimal_places(value) for value in nonempty)
            decimals = min(MAX_DECIMALS, max(0, decimals))
            length = max(len(value.replace(",", "").replace(" ", ""))
                         for value in nonempty)
            length = max(length, decimals + 2 if decimals else 1)
            length = min(MAX_NUMERIC, max(1, length))
            if decimals >= length:
                decimals = max(0, length - 1)
            fields.append(Field(name, "N", length, decimals))
            continue
        length = max((len(value) for value in nonempty), default=1)
        fields.append(Field(name, "C", min(MAX_CHARACTER, max(1, length)), 0))
    return fields


def _field_name(raw: str, index: int, used: set[str]) -> str:
    text = "".join(char if char.isalnum() or char == "_" else "_"
                   for char in str(raw or "").upper()).strip("_")
    if not text:
        text = f"FIELD{index + 1}"
    if text[0].isdigit():
        text = "F" + text
    text = text[:10]
    candidate = text
    counter = 2
    while candidate in used:
        suffix = str(counter)
        candidate = text[: max(1, 10 - len(suffix))] + suffix
        counter += 1
    used.add(candidate)
    return candidate


def _looks_date(value: str) -> bool:
    if not value:
        return False
    for pattern in DATE_FORMATS:
        match = pattern.match(value)
        if not match:
            continue
        if len(match.groups()) == 3:
            month, day, _year = (int(part) for part in match.groups())
            if not (1 <= month <= 12 and 1 <= day <= 31):
                continue
        return True
    return False


def _looks_logical(value: str) -> bool:
    marker = value.strip().upper()
    return marker in LOGICAL_TRUE or marker in LOGICAL_FALSE


def _looks_number(value: str) -> bool:
    cleaned = value.replace(",", "").replace(" ", "")
    for symbol in ("$", "€", "£", "¥"):
        cleaned = cleaned.replace(symbol, "")
    return bool(NUMBER_RE.match(cleaned))


def _decimal_places(value: str) -> int:
    cleaned = value.replace(",", "").replace(" ", "")
    for symbol in ("$", "€", "£", "¥"):
        cleaned = cleaned.replace(symbol, "")
    if "." not in cleaned:
        return 0
    return len(cleaned.rsplit(".", 1)[1])


def rows_for_export(fields: Sequence[Field],
                    records: Iterable[dict[str, str]],
                    options: ExportOptions) -> list[list[str]]:
    rows: list[list[str]] = []
    for record in records:
        rows.append([
            display_value(field, record.get(field.name, ""),
                          date_format=options.date_format)
            for field in fields
        ])
    return rows


def default_columns(rows: Sequence[Sequence[str]]) -> list[list[str]]:
    width = max((len(row) for row in rows), default=0)
    return [[row[index] if index < len(row) else "" for row in rows]
            for index in range(width)]


def write_text(path: str | Path, text: str, encoding: str = "cp437") -> None:
    Path(path).write_bytes(text.encode(encoding, "replace"))


def read_text(path: str | Path, encoding: str = "cp437") -> str:
    return Path(path).read_bytes().decode(encoding, "replace")
