"""Tipi di campo, valori canonici e conversioni alla riconfigurazione.

Lo strato dati conserva i valori come testo canonico (PLAN §3.3): i numerici
con segno, punto e decimali fissi; le date come `YYYYMMDD`; i logici come
`1`, `0` o vuoto. Qui vivono le regole che trasformano quello che l'utente
digita in questa forma e viceversa.

La tabella di conversione segue `docs/reference/00-inventario.md` §2: quando
un campo cambia tipo, Alpha Four converte i valori esistenti secondo una
matrice fissa, non secondo il buon senso del momento.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

MAX_FIELDS = 128
MAX_RECORD_LENGTH = 4000
MAX_CHARACTER = 254
MAX_NUMERIC = 19
MAX_DECIMALS = 14
MAX_MEMO = 5000

FIELD_TYPES = {
    "C": "Character",
    "N": "Numeric",
    "D": "Date",
    "L": "Logical",
    "M": "Memo",
}

FIXED_LENGTHS = {"D": 8, "L": 1, "M": 10}
NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,9}$")


class FieldError(ValueError):
    """Definizione o valore di campo non valido."""


@dataclass(frozen=True)
class Field:
    """Definizione di un campo, già normalizzata."""

    name: str
    type: str
    length: int
    decimals: int = 0

    def __post_init__(self) -> None:
        name = self.name.strip().upper()
        if not NAME_RE.match(name):
            raise FieldError(
                "Field names start with a letter, use A-Z 0-9 _ and are at most 10 characters."
            )
        type_ = self.type.strip().upper()
        if type_ not in FIELD_TYPES:
            raise FieldError(f"Unknown field type: {self.type}")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "type", type_)
        if self.type in FIXED_LENGTHS:
            object.__setattr__(self, "length", FIXED_LENGTHS[self.type])
            object.__setattr__(self, "decimals", 0)
        if not 1 <= self.length <= MAX_CHARACTER:
            raise FieldError(f"Field length must be between 1 and {MAX_CHARACTER}.")
        if self.type == "C" and self.decimals:
            raise FieldError("Character fields have no decimal places.")
        if self.type == "N":
            if self.length > MAX_NUMERIC:
                raise FieldError(f"A numeric field is at most {MAX_NUMERIC} characters.")
            if not 0 <= self.decimals <= MAX_DECIMALS:
                raise FieldError(f"Decimal places must be between 0 and {MAX_DECIMALS}.")
            if self.decimals >= self.length:
                raise FieldError("Decimal places must be less than the field length.")

    @property
    def type_name(self) -> str:
        return FIELD_TYPES[self.type]

    @property
    def is_memo(self) -> bool:
        return self.type == "M"

    def with_name(self, name: str) -> "Field":
        return Field(name, self.type, self.length, self.decimals)

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "type": self.type,
                "length": self.length, "decimals": self.decimals}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Field":
        return cls(str(data["name"]), str(data["type"]),
                   int(data["length"]), int(data["decimals"]))


def make_field(name: str, type_: str, length: int | str | None = None,
               decimals: int | str | None = None) -> Field:
    """Crea un campo applicando le lunghezze fisse dei tipi D/L/M."""
    type_ = (type_ or "").strip().upper()[:1]
    if type_ in FIXED_LENGTHS:
        return Field(name, type_, FIXED_LENGTHS[type_], 0)
    return Field(name, type_, _as_int(length, 1), _as_int(decimals, 0))


def _as_int(value: int | str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise FieldError(f"Not a number: {value}") from exc


def validate_fields(fields: list[Field] | tuple[Field, ...]) -> None:
    if not fields:
        raise FieldError("A database needs at least one field.")
    if len(fields) > MAX_FIELDS:
        raise FieldError(f"A database has at most {MAX_FIELDS} fields.")
    seen: set[str] = set()
    for field in fields:
        if field.name in seen:
            raise FieldError(f"Duplicate field name: {field.name}")
        seen.add(field.name)
    length = sum(field.length for field in fields if not field.is_memo)
    if length > MAX_RECORD_LENGTH:
        raise FieldError(f"A record is at most {MAX_RECORD_LENGTH} characters.")


def record_length(fields: list[Field] | tuple[Field, ...]) -> int:
    return sum(field.length for field in fields)


# -- valori ---------------------------------------------------------------


def blank_value(field: Field) -> str:
    return ""


def parse_value(field: Field, text: str) -> str:
    """Converte testo digitato nel valore canonico del campo."""
    text = text if text is not None else ""
    if field.type == "C":
        if len(text) > field.length:
            raise FieldError(f"Value is longer than {field.length} characters.")
        return text
    if field.type == "N":
        return _parse_numeric(field, text)
    if field.type == "D":
        return _parse_date(text)
    if field.type == "L":
        return _parse_logical(text)
    if field.type == "M":
        if len(text) > MAX_MEMO:
            raise FieldError(f"A memo is at most {MAX_MEMO} characters.")
        return text
    return text


def format_value(field: Field, value: str) -> str:
    """Valore canonico → testo da mostrare nel form."""
    if field.type == "D":
        return date_display(value)
    if field.type == "L":
        return ".T." if value == "1" else ".F." if value == "0" else ""
    return value or ""


def _parse_numeric(field: Field, text: str) -> str:
    if not text.strip():
        return ""
    cleaned = _clean_numeric(text)
    try:
        number = Decimal(cleaned)
    except InvalidOperation as exc:
        raise FieldError(f"Not a numeric value: {text.strip()}") from exc
    with localcontext() as context:
        context.prec = 30
        quantum = Decimal(1).scaleb(-field.decimals)
        number = number.quantize(quantum, rounding=ROUND_HALF_UP)
    if number == 0:
        number = abs(number)
    canonical = f"{number:.{field.decimals}f}"
    if len(canonical) > field.length:
        raise FieldError(f"Value does not fit in {field.length} characters.")
    return canonical


def _clean_numeric(text: str) -> str:
    """Rimuove spazi, valuta e separatori delle migliaia."""
    text = text.strip().replace(",", "").replace(" ", "")
    for symbol in ("$", "€", "£", "¥"):
        text = text.replace(symbol, "")
    if not text or text in ("-", "+", "."):
        raise FieldError("Not a numeric value.")
    sign = ""
    if text[0] in "+-":
        sign, text = text[0], text[1:]
    if text.count(".") > 1:
        raise FieldError("Not a numeric value.")
    if not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)", text):
        raise FieldError("Not a numeric value.")
    return sign + text


def numeric_prefix(text: str) -> str:
    """Parte numerica iniziale di un testo, per la conversione C → N.

    Valuta e separatori si perdono, come da manuale: `$ 1,234.50` diventa
    `1234.50`; `12ABC` diventa `12`; un testo senza cifre diventa `0`.
    """
    text = text.strip().replace(" ", "").replace(",", "")
    for symbol in ("$", "€", "£", "¥"):
        text = text.replace(symbol, "")
    sign = ""
    if text[:1] in ("-", "+"):
        sign, text = text[0], text[1:]
    match = re.match(r"(?:\d+(?:\.\d*)?|\.\d+)", text)
    if not match:
        return "0"
    return sign + match.group(0)


_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def valid_date(year: int, month: int, day: int) -> bool:
    if not 0 <= year <= 9999 or not 1 <= month <= 12:
        return False
    days = _MONTH_DAYS[month - 1]
    if month == 2 and _leap(year):
        days = 29
    return 1 <= day <= days


def _parse_date(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    match = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})$", text)
    if match:
        month, day, year = (int(part) for part in match.groups())
        if year < 100:
            year += 1900
    else:
        match = re.match(r"^(\d{4})(\d{2})(\d{2})$", text)
        if not match:
            raise FieldError("Enter a date as MM/DD/YYYY.")
        year, month, day = (int(part) for part in match.groups())
    if not valid_date(year, month, day):
        raise FieldError("That date does not exist.")
    return f"{year:04d}{month:02d}{day:02d}"


def date_display(value: str, separator: str = "/") -> str:
    if not value or len(value) != 8 or not value.isdigit():
        return ""
    year, month, day = value[:4], value[4:6], value[6:8]
    return f"{month}{separator}{day}{separator}{year}"


def _parse_logical(text: str) -> str:
    value = text.strip().upper()
    if not value:
        return ""
    if value in ("T", "TRUE", ".T.", "Y", "YES", "1"):
        return "1"
    if value in ("F", "FALSE", ".F.", "N", "NO", "0"):
        return "0"
    raise FieldError("Enter T or F, Y or N, or leave the field blank.")


# -- conversioni ----------------------------------------------------------


def convert_value(old: Field, new: Field, value: str) -> str:
    """Converte un valore quando un campo cambia tipo.

    La matrice è quella del manuale; i casi non elencati (per esempio
    Date → Memo) perdono il valore, che è la scelta più prudente.
    """
    if old.type == new.type:
        if new.type == "C":
            return (value or "")[: new.length]
        if new.type == "N":
            return _renormalize_numeric(new, value)
        return value or ""

    if old.type == "C":
        if new.type == "M":
            return value or ""
        if new.type == "D":
            try:
                return _parse_date(value or "")
            except FieldError:
                return ""
        if new.type == "L":
            first = (value or "").strip()[:1].upper()
            if first in "TFYN":
                return "1" if first in "TY" else "0"
            return ""
        if new.type == "N":
            try:
                return _renormalize_numeric(new, numeric_prefix(value or ""))
            except FieldError:
                return ""
        return ""

    if old.type == "N":
        if new.type == "C":
            return (value or "")[: new.length]
        if new.type == "L":
            number = _decimal_or_zero(value)
            if number > 0:
                return "1"
            if number == 0:
                return "0"
            return ""
        if new.type == "M":
            return value or ""
        return ""

    if old.type == "D":
        if new.type == "C":
            return (value or "")[: new.length]
        if new.type == "M":
            return value or ""
        return ""

    if old.type == "L":
        if new.type == "C":
            text = "T" if value == "1" else "F" if value == "0" else ""
            return text[: new.length]
        if new.type == "M":
            return "T" if value == "1" else "F" if value == "0" else ""
        return ""

    if old.type == "M":
        if new.type == "C":
            return (value or "")[: new.length]
        if new.type == "N":
            try:
                return _renormalize_numeric(new, numeric_prefix(value or ""))
            except FieldError:
                return ""
        return ""

    return ""


def _decimal_or_zero(value: str) -> Decimal:
    try:
        return Decimal(value) if value else Decimal(0)
    except InvalidOperation:
        return Decimal(0)


def _renormalize_numeric(field: Field, value: str) -> str:
    if not value:
        return ""
    try:
        return _parse_numeric(field, value)
    except FieldError:
        return ""
