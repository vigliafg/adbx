"""Espressioni di Alpha Four: parser, valutazione e confronto di stringhe.

Le espressioni servono a tre ondate: qui (O3) per indici, range e
search/sort; in O4 per le regole di campo; in O7 per i calcoli dei report.
Il parser è quindi volutamente piccolo ma completo per gli operatori e le
funzioni documentate nell'inventario.

I valori sono tipizzati come in Alpha Four:

* testo → `str`;
* numerico → `Decimal`;
* data → `datetime.date`;
* logico → `bool`;
* vuoto → `None`.

Il confronto fra stringhe dipende dall'impostazione **Pattern matching**
(`Exact`, `Case`, `Case-insensitive`, predefinita `Exact`), come descritto
nel Reference Manual, capitolo 23.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import lru_cache
from typing import Any, Iterable

from .fields import Field, valid_date

PATTERN_EXACT = "exact"
PATTERN_CASE = "case"
PATTERN_INSENSITIVE = "insensitive"
PATTERN_MODES = (PATTERN_EXACT, PATTERN_CASE, PATTERN_INSENSITIVE)


class ExprError(ValueError):
    """Espressione non valida o non valutabile."""


# -- contesto ---------------------------------------------------------------


@dataclass
class Context:
    """Valori di un record durante la valutazione di un'espressione."""

    fields: tuple[Field, ...]
    values: dict[str, str] = field(default_factory=dict)
    pattern: str = PATTERN_EXACT
    padded: bool = False
    seq: int = 0
    deleted: bool = False
    count: int = 0

    def field(self, name: str) -> Field:
        upper = name.upper()
        for definition in self.fields:
            if definition.name == upper:
                return definition
        raise ExprError(f"Unknown field: {name}")


def evaluate(text: str, context: Context) -> Any:
    """Valuta un'espressione e ritorna il valore tipizzato."""
    if text is None or not text.strip():
        return None
    try:
        tree = _parse(text)
    except ExprError:
        raise
    return _eval(tree, context)


def evaluate_boolean(text: str, context: Context) -> bool:
    return truthy(evaluate(text, context))


def key_text(value: Any) -> str:
    """Rappresentazione testuale stabile di un valore, per le chiavi."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "T" if value else "F"
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    if isinstance(value, Decimal):
        return _decimal_text(value)
    return str(value)


def sort_key(value: Any, *, case_sensitive: bool = False) -> tuple:
    """Chiave di ordinamento tipizzata: numeri, date e testo non si mescolano."""
    if value is None:
        return (0,)
    if isinstance(value, Decimal):
        return (1, value)
    if isinstance(value, date):
        return (2, value.toordinal())
    if isinstance(value, bool):
        return (3, int(value))
    text = str(value).rstrip()
    return (4, text if case_sensitive else text.upper())


def truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return value != 0
    if isinstance(value, date):
        return True
    text = str(value).strip()
    if not text:
        return False
    return text.upper() in ("T", "TRUE", ".T.", "Y", "YES", "1")


# -- confronto --------------------------------------------------------------


def compare_values(left: Any, right: Any, pattern: str = PATTERN_EXACT, *,
                   exact_strings: bool = False) -> int:
    """Confronta due valori; -1, 0, 1. Le stringhe seguono Pattern matching."""
    if left is None and right is None:
        return 0
    if isinstance(left, bool) or isinstance(right, bool):
        lvalue = truthy(left)
        rvalue = truthy(right)
        return (lvalue > rvalue) - (lvalue < rvalue)
    if isinstance(left, date) or isinstance(right, date):
        ldate = _to_date(left)
        rdate = _to_date(right)
        if ldate is None or rdate is None:
            return _compare_optional(ldate, rdate)
        return (ldate > rdate) - (ldate < rdate)
    if _is_number(left) or _is_number(right):
        lnumber = _to_number(left)
        rnumber = _to_number(right)
        if lnumber is None or rnumber is None:
            return _compare_optional(lnumber, rnumber)
        return (lnumber > rnumber) - (lnumber < rnumber)
    ltext = "" if left is None else str(left)
    rtext = "" if right is None else str(right)
    if exact_strings:
        return (ltext > rtext) - (ltext < rtext)
    return _compare_text(ltext, rtext, pattern)


def equal_values(left: Any, right: Any, pattern: str = PATTERN_EXACT,
                 *, table: bool = False, exact_strings: bool = False) -> bool:
    if table:
        # Table mode: sempre case-insensitive ed esatto (manuale, cap. 4).
        if _is_number(left) or _is_number(right):
            return _numeric_equal(left, right)
        if isinstance(left, date) or isinstance(right, date):
            return _to_date(left) == _to_date(right) and left is not None
        if isinstance(left, bool) or isinstance(right, bool):
            return truthy(left) == truthy(right)
        ltext = "" if left is None else str(left).rstrip()
        rtext = "" if right is None else str(right).rstrip()
        return ltext.upper() == rtext.upper()
    return compare_values(left, right, pattern) == 0


def _numeric_equal(left: Any, right: Any) -> bool:
    lnumber = _to_number(left)
    rnumber = _to_number(right)
    if lnumber is None or rnumber is None:
        return lnumber is None and rnumber is None
    return lnumber == rnumber


def _compare_optional(left: Any, right: Any) -> int:
    if left is None and right is None:
        return 0
    if left is None:
        return -1
    if right is None:
        return 1
    return 0


def _compare_text(left: str, right: str, pattern: str) -> int:
    left = left.rstrip()
    right = right.rstrip()
    if pattern == PATTERN_EXACT:
        return (left > right) - (left < right)
    if pattern == PATTERN_CASE:
        lkey, rkey = left, right
    else:
        lkey, rkey = left.upper(), right.upper()
    # Case: confronto fino alla lunghezza della seconda stringa.
    if lkey[:len(rkey)] == rkey:
        return 0
    return (lkey > rkey) - (lkey < rkey)


def text_equal(left: str, right: str, pattern: str) -> bool:
    left = left.rstrip()
    right = right.rstrip()
    if pattern == PATTERN_EXACT:
        return left == right
    if pattern == PATTERN_CASE:
        return left[:len(right)] == right
    return left.upper()[:len(right)] == right.upper()


# -- conversioni di valore --------------------------------------------------


def value_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "T" if value else "F"
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    if isinstance(value, Decimal):
        return _decimal_text(value)
    return str(value)


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _to_number(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal(1 if value else 0)
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip().replace(",", "")
    for symbol in ("$", "€", "£", "¥", " "):
        text = text.replace(symbol, "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text):
        return _date_from_parts(text)
    match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})", text)
    if match:
        month, day, year = (int(part) for part in match.groups())
        if year < 100:
            year += 1900
        return _make_date(year, month, day)
    return None


def _date_from_parts(text: str) -> date | None:
    return _make_date(int(text[:4]), int(text[4:6]), int(text[6:8]))


def _make_date(year: int, month: int, day: int) -> date | None:
    if not valid_date(year, month, day):
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _padded_text(field: Field, value: str) -> str:
    if field.is_memo:
        return value
    if field.type == "C":
        return (value or "").ljust(field.length)
    if field.type == "N":
        number = _to_number(value)
        if number is None:
            return " " * field.length
        return f"{number:>{field.length}.{field.decimals}f}"
    if field.type == "D":
        return (value or "").ljust(field.length)
    if field.type == "L":
        return ("T" if value == "1" else "F" if value == "0" else " ").ljust(1)
    return value


def field_value(context: Context, name: str) -> Any:
    definition = context.field(name)
    raw = context.values.get(definition.name, "")
    if context.padded and not definition.is_memo:
        return _padded_text(definition, raw)
    if definition.type == "N":
        return _to_number(raw)
    if definition.type == "D":
        return _to_date(raw)
    if definition.type == "L":
        return None if raw == "" else raw == "1"
    return raw


# -- tokenizer --------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    (?P<space>\s+)
  | (?P<date>\{[^}]*\})
  | (?P<string>"[^"]*"|'[^']*')
  | (?P<number>\d+(?:\.\d*)?|\.\d+)
  | (?P<dotted>\.(?:AND|OR|NOT|T|F)\.)
  | (?P<wildcard>\*(?:ANY|FIRST|LEADING|WORD|CHAR|NUM|DATE|LOGIC|MEMO)\b)
  | (?P<operator><=|>=|<>|!=|==|=|<|>|\+|-|\*|/|\(|\)|,)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    position = 0
    while position < len(text):
        match = _TOKEN_RE.match(text, position)
        if match is None:
            raise ExprError(f"Invalid character at {position}: {text[position]!r}")
        position = match.end()
        kind = match.lastgroup
        value = match.group()
        if kind == "space":
            continue
        if kind == "date":
            tokens.append(("date", value[1:-1]))
        elif kind == "string":
            tokens.append(("string", value[1:-1]))
        elif kind == "number":
            tokens.append(("number", value))
        elif kind == "dotted":
            keyword = value.strip(".").upper()
            if keyword == "T":
                tokens.append(("logical", "T"))
            elif keyword == "F":
                tokens.append(("logical", "F"))
            else:
                tokens.append(("keyword", keyword))
        elif kind == "wildcard":
            tokens.append(("ident", value.upper()))
        elif kind == "operator":
            tokens.append(("operator", value))
        else:
            upper = value.upper()
            if upper in ("AND", "OR", "NOT"):
                tokens.append(("keyword", upper))
            elif upper in ("T", "F"):
                tokens.append(("logical", upper))
            else:
                tokens.append(("ident", upper))
    tokens.append(("end", ""))
    return tokens


# -- parser -----------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.tokens = tokens
        self.index = 0

    def peek(self) -> tuple[str, str]:
        return self.tokens[self.index]

    def take(self) -> tuple[str, str]:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def accept(self, kind: str, value: str | None = None) -> bool:
        current = self.peek()
        if current[0] == kind and (value is None or current[1] == value):
            self.index += 1
            return True
        return False

    def expect(self, kind: str, value: str | None = None) -> tuple[str, str]:
        token = self.peek()
        if token[0] != kind or (value is not None and token[1] != value):
            raise ExprError(f"Expected {value or kind}, found {token[1] or 'end'}")
        return self.take()

    def parse(self) -> tuple:
        tree = self.or_expression()
        if self.peek()[0] != "end":
            raise ExprError(f"Unexpected token: {self.peek()[1]}")
        return tree

    def or_expression(self) -> tuple:
        node = self.and_expression()
        while self.accept("keyword", "OR"):
            node = ("binop", "OR", node, self.and_expression())
        return node

    def and_expression(self) -> tuple:
        node = self.not_expression()
        while self.accept("keyword", "AND"):
            node = ("binop", "AND", node, self.not_expression())
        return node

    def not_expression(self) -> tuple:
        if self.accept("keyword", "NOT"):
            return ("unop", "NOT", self.not_expression())
        return self.comparison()

    def comparison(self) -> tuple:
        node = self.additive()
        current = self.peek()
        if current[0] == "operator" and current[1] in (
                "=", "==", "<>", "!=", "<", ">", "<=", ">="):
            operator = self.take()[1]
            return ("binop", operator, node, self.additive())
        return node

    def additive(self) -> tuple:
        node = self.term()
        while True:
            current = self.peek()
            if current[0] == "operator" and current[1] in ("+", "-"):
                operator = self.take()[1]
                node = ("binop", operator, node, self.term())
            else:
                return node

    def term(self) -> tuple:
        node = self.unary()
        while True:
            current = self.peek()
            if current[0] == "operator" and current[1] in ("*", "/"):
                operator = self.take()[1]
                node = ("binop", operator, node, self.unary())
            else:
                return node

    def unary(self) -> tuple:
        if self.accept("operator", "-"):
            return ("unop", "-", self.unary())
        return self.primary()

    def primary(self) -> tuple:
        kind, value = self.peek()
        if kind == "number":
            self.take()
            return ("literal", Decimal(value))
        if kind == "string":
            self.take()
            return ("literal", value)
        if kind == "date":
            self.take()
            return ("literal", _to_date(value))
        if kind == "logical":
            self.take()
            return ("literal", value == "T")
        if kind == "ident":
            self.take()
            if self.accept("operator", "("):
                arguments: list[tuple] = []
                if not self.accept("operator", ")"):
                    arguments.append(self.or_expression())
                    while self.accept("operator", ","):
                        arguments.append(self.or_expression())
                    self.expect("operator", ")")
                return ("call", value, arguments)
            return ("field", value)
        if self.accept("operator", "("):
            node = self.or_expression()
            self.expect("operator", ")")
            return node
        raise ExprError(f"Unexpected token: {value or 'end'}")


@lru_cache(maxsize=1024)
def _parse(text: str) -> tuple:
    if not text or not text.strip():
        raise ExprError("Empty expression.")
    return _Parser(tokenize(text)).parse()


def parse_expression(text: str) -> tuple:
    """Analizza un'espressione (per i test e per la cache)."""
    return _parse(text)


# -- valutazione ------------------------------------------------------------


def _eval(node: tuple, context: Context) -> Any:
    kind = node[0]
    if kind == "literal":
        return node[1]
    if kind == "field":
        return field_value(context, node[1])
    if kind == "call":
        return _call(node[1], node[2], context)
    if kind == "unop":
        value = _eval(node[2], context)
        if node[1] == "NOT":
            return not truthy(value)
        number = _to_number(value) or Decimal(0)
        return -number
    if kind == "binop":
        return _binop(node[1], _eval(node[2], context),
                      _eval(node[3], context), context)
    raise ExprError(f"Unknown node: {kind}")


def _binop(operator: str, left: Any, right: Any, context: Context) -> Any:
    if operator == "AND":
        return truthy(left) and truthy(right)
    if operator == "OR":
        return truthy(left) or truthy(right)
    if operator in ("=", "==", "<>", "!="):
        if operator == "==":
            if not isinstance(left, str) or not isinstance(right, str):
                raise ExprError("The == operator compares character strings.")
            return left == right
        equal = equal_values(left, right, context.pattern)
        return equal if operator == "=" else not equal
    if operator in ("<", ">", "<=", ">="):
        comparison = compare_values(left, right, context.pattern)
        return {"<": comparison < 0, ">": comparison > 0,
                "<=": comparison <= 0, ">=": comparison >= 0}[operator]
    if operator == "+":
        if isinstance(left, date) or isinstance(right, date):
            left_date = _to_date(left)
            right_date = _to_date(right)
            if left_date is not None and right_date is None:
                return left_date + timedelta(days=int(_to_number(right) or 0))
            if left_date is None and right_date is not None:
                return right_date + timedelta(days=int(_to_number(left) or 0))
            raise ExprError("Cannot add two dates.")
        if _is_number(left) and _is_number(right):
            return _to_number(left) + _to_number(right)
        return value_to_text(left) + value_to_text(right)
    if operator == "-":
        if isinstance(left, date):
            if isinstance(right, date):
                return Decimal((left - right).days)
            return left - timedelta(days=int(_to_number(right) or 0))
        return (_to_number(left) or Decimal(0)) - (_to_number(right) or Decimal(0))
    if operator == "*":
        return (_to_number(left) or Decimal(0)) * (_to_number(right) or Decimal(0))
    if operator == "/":
        divisor = _to_number(right)
        if not divisor:
            raise ExprError("Division by zero.")
        return (_to_number(left) or Decimal(0)) / divisor
    raise ExprError(f"Unknown operator: {operator}")


def _call(name: str, arguments: list[tuple], context: Context) -> Any:
    values = [_eval(argument, context) for argument in arguments]

    def text(index: int) -> str:
        return value_to_text(values[index]) if index < len(values) else ""

    def number(index: int) -> Decimal:
        if index < len(values):
            return _to_number(values[index]) or Decimal(0)
        return Decimal(0)

    # -- testo ---------------------------------------------------------
    if name in ("UPPER", "F_UPPER"):
        return text(0).upper()
    if name == "LOWER":
        return text(0).lower()
    if name == "TRIM":
        return text(0).strip()
    if name == "LTRIM":
        return text(0).lstrip()
    if name == "RTRIM":
        return text(0).rstrip()
    if name == "LEFT":
        return text(0)[: int(number(1))]
    if name == "RIGHT":
        size = int(number(1))
        return text(0)[-size:] if size else ""
    if name == "SUBSTR":
        start = max(1, int(number(1)))
        size = int(number(2))
        return text(0)[start - 1:start - 1 + size]
    if name in ("LEN", "LENGTH"):
        return Decimal(len(text(0)))
    if name == "AT":
        position = text(1).find(text(0))
        return Decimal(position + 1 if position >= 0 else 0)
    if name == "OCCURS":
        needle = text(0)
        if not needle:
            return Decimal(0)
        return Decimal(text(1).upper().count(needle.upper()))
    if name == "REPLICATE":
        return text(0) * int(number(1))
    if name == "SPACE":
        return " " * int(number(0))
    if name == "STUFF":
        original = text(0)
        start = max(1, int(number(1)))
        size = int(number(2))
        return original[:start - 1] + text(3) + original[start - 1 + size:]
    if name == "W_COUNT":
        return Decimal(len(re.findall(r"[^\s\W]+", text(0), re.UNICODE)))
    if name == "WORD":
        words = re.findall(r"[^\s\W]+", text(0), re.UNICODE)
        index = int(number(1))
        if index > 0:
            return words[index - 1] if index <= len(words) else ""
        if index < 0:
            return words[index] if -index <= len(words) else ""
        return ""
    if name in ("ISALPHA", "ISLOWER", "ISUPPER"):
        value = text(0)
        if name == "ISALPHA":
            return bool(value) and value.isalpha()
        if name == "ISLOWER":
            return bool(value) and value.islower()
        return bool(value) and value.isupper()
    if name == "CHR":
        try:
            return chr(int(number(0)))
        except ValueError as exc:
            raise ExprError("CHR: invalid code.") from exc
    if name == "ASC":
        return Decimal(ord(text(0)[0])) if text(0) else Decimal(0)
    if name == "VAL":
        return _to_number(text(0)) or Decimal(0)
    if name == "STR":
        size = int(number(1)) if len(values) > 1 else 10
        decimals = int(number(2)) if len(values) > 2 else 0
        return f"{number(0):>{size}.{decimals}f}"
    if name == "LIKE":
        return _like(text(0), text(1), context.pattern)
    if name == "SOUNDEX":
        return _soundex(text(0))
    if name == "DIFFERENCE":
        return Decimal(_difference(text(0), text(1)))

    # -- pattern matching ---------------------------------------------
    if name in ("*ANY", "*FIRST", "*LEADING", "*WORD"):
        haystack, needle = text(0), text(1)
        if not needle:
            return False
        flags = 0 if context.pattern in (PATTERN_EXACT, PATTERN_CASE) else re.IGNORECASE
        escaped = re.escape(needle)
        if name == "*ANY":
            pattern = escaped
        elif name == "*FIRST":
            pattern = "^" + escaped
        elif name == "*LEADING":
            pattern = r"(?<![0-9A-Za-z])" + escaped
        else:
            pattern = r"(?<![0-9A-Za-z])" + escaped + r"(?![0-9A-Za-z])"
        return re.search(pattern, haystack, flags) is not None

    # -- numeriche -----------------------------------------------------
    if name == "ABS":
        return abs(number(0))
    if name == "INT":
        return Decimal(int(number(0)))
    if name == "ROUND":
        decimals = int(number(1)) if len(values) > 1 else 0
        quantum = Decimal(1).scaleb(-decimals)
        return number(0).quantize(quantum, rounding=ROUND_HALF_UP)
    if name == "MOD":
        divisor = number(1)
        if not divisor:
            raise ExprError("MOD: division by zero.")
        return number(0) % divisor
    if name == "MAX":
        return max(number(0), number(1))
    if name == "MIN":
        return min(number(0), number(1))
    if name == "SIGN":
        return Decimal((number(0) > 0) - (number(0) < 0))
    if name == "FLOOR":
        return Decimal(number(0).to_integral_value(rounding="ROUND_FLOOR"))
    if name == "CEILING":
        return Decimal(number(0).to_integral_value(rounding="ROUND_CEILING"))
    if name == "SQRT":
        import math
        return Decimal(str(math.sqrt(float(number(0)))))
    if name == "EXP":
        import math
        return Decimal(str(math.exp(float(number(0)))))
    if name == "LOG":
        import math
        return Decimal(str(math.log(float(number(0)))))

    # -- date ----------------------------------------------------------
    if name == "DATE":
        return date.today()
    if name == "CTOD":
        parsed = _to_date(text(0))
        if parsed is None:
            raise ExprError("CTOD: invalid date.")
        return parsed
    if name in ("DTOS", "CDATE"):
        parsed = _to_date(values[0]) if values else None
        return parsed.strftime("%Y%m%d") if parsed else ""
    if name in ("YEAR", "MONTH", "DAY", "DOW", "CDOW", "CMONTH"):
        parsed = _to_date(values[0]) if values else None
        if parsed is None:
            return "" if name in ("CDOW", "CMONTH") else Decimal(0)
        if name == "YEAR":
            return Decimal(parsed.year)
        if name == "MONTH":
            return Decimal(parsed.month)
        if name == "DAY":
            return Decimal(parsed.day)
        if name == "DOW":
            return Decimal((parsed.weekday() + 1) % 7 + 1)
        if name == "CDOW":
            return parsed.strftime("%A")
        return parsed.strftime("%B")
    if name == "ADDMONTHS":
        parsed = _to_date(values[0]) if values else None
        months = int(number(1))
        if parsed is None:
            return None
        month = parsed.month - 1 + months
        year = parsed.year + month // 12
        month = month % 12 + 1
        day = min(parsed.day, 28)
        return _make_date(year, month, day)
    if name == "ADDYEARS":
        parsed = _to_date(values[0]) if values else None
        if parsed is None:
            return None
        return _make_date(parsed.year + int(number(1)), parsed.month, parsed.day)

    # -- logiche e di stato -------------------------------------------
    if name == "ISBLANK":
        return values[0] is None or value_to_text(values[0]).strip() == ""
    if name in ("IF", "IIF"):
        return values[1] if truthy(values[0]) else values[2]
    if name == "DELETED":
        return context.deleted
    if name == "RECNO":
        return Decimal(context.seq)
    if name == "RECCOUNT":
        return Decimal(context.count)
    if name == "BOF":
        return context.seq <= 1
    if name == "EOF":
        return context.count > 0 and context.seq >= context.count

    raise ExprError(f"Unknown function: {name}")


# -- funzioni di supporto ---------------------------------------------------


def _like(text: str, pattern: str, mode: str) -> bool:
    regex = "".join(".*" if char == "*" else "." if char == "?"
                    else re.escape(char) for char in pattern)
    flags = re.DOTALL
    if mode == PATTERN_INSENSITIVE:
        flags |= re.IGNORECASE
    return re.fullmatch(regex, text, flags) is not None


_SOUNDEX_GROUPS = {
    "B": "1", "F": "1", "P": "1", "V": "1",
    "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2",
    "X": "2", "Z": "2",
    "D": "3", "T": "3",
    "L": "4",
    "M": "5", "N": "5",
    "R": "6",
}


def _soundex(text: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", text).upper()
    if not letters:
        return ""
    result = letters[0]
    previous = _SOUNDEX_GROUPS.get(letters[0], "")
    for letter in letters[1:]:
        code = _SOUNDEX_GROUPS.get(letter, "")
        if code and code != previous:
            result += code
        if letter not in "HW":
            previous = code
        if len(result) == 4:
            break
    return (result + "000")[:4]


def _difference(left: str, right: str) -> int:
    first, second = _soundex(left), _soundex(right)
    if not first or not second:
        return 0
    return sum(1 for a, b in zip(first, second) if a == b)


# -- righe della tabella di ricerca ----------------------------------------


@dataclass
class SearchRow:
    """Una riga della Search Table (Table mode)."""

    field: str = ""
    operator: str = "="
    value: str = ""
    connector: str = "AND"

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "operator": self.operator,
                "value": self.value, "connector": self.connector}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "SearchRow":
        return cls(str(data.get("field", "")), str(data.get("operator", "=")),
                   str(data.get("value", "")), str(data.get("connector", "AND")))


def search_rows_expression(rows: Iterable[SearchRow]) -> str:
    """Genera l'espressione equivalente alla tabella, per la descrizione."""
    ordered = [row for row in rows if row.field]
    parts: list[str] = []
    for index, row in enumerate(ordered):
        if row.operator in ("*A", "*F", "*L", "*W"):
            function = {"*A": "*ANY", "*F": "*FIRST",
                        "*L": "*LEADING", "*W": "*WORD"}[row.operator]
            condition = f'{function}({row.field},"{row.value}")'
        else:
            condition = f'{row.field} {row.operator} "{row.value}"'
        if index == 0:
            parts.append(condition)
        else:
            connector = ordered[index - 1].connector or "AND"
            parts.append(f".{connector.upper()}. {condition}")
    return " ".join(parts)


def matches_search_rows(rows: Iterable[SearchRow], context: Context) -> bool:
    """Valuta la tabella: AND ha precedenza su OR (manuale, cap. 4)."""
    conditions: list[bool] = []
    connectors: list[str] = []
    for row in rows:
        if not row.field.strip():
            continue
        conditions.append(_match_row(row, context))
        connectors.append((row.connector or "AND").upper())
    if not conditions:
        return True
    # Connector sulla riga i unisce la riga i con la i+1: raggruppa i blocchi
    # AND e poi mette in OR i blocchi.
    groups: list[bool] = [conditions[0]]
    for index in range(1, len(conditions)):
        connector = connectors[index - 1]
        if connector == "OR":
            groups.append(conditions[index])
        else:
            groups[-1] = groups[-1] and conditions[index]
    return any(groups)


def _match_row(row: SearchRow, context: Context) -> bool:
    field_name = row.field.strip().upper()
    if field_name.startswith("*"):
        return _match_wildcard_field(field_name, row, context)
    try:
        definition = context.field(field_name)
    except ExprError:
        return False
    value = _row_value(definition, row.value)
    field = field_value(context, definition.name)
    return _apply_operator(field, row.operator, value, context)


def _match_wildcard_field(name: str, row: SearchRow, context: Context) -> bool:
    type_code = {"*CHAR": "C", "*NUM": "N", "*DATE": "D",
                 "*LOGIC": "L", "*MEMO": "M"}.get(name)
    if type_code is None:
        return False
    for definition in context.fields:
        if definition.type != type_code:
            continue
        value = _row_value(definition, row.value)
        field = field_value(context, definition.name)
        if _apply_operator(field, row.operator, value, context):
            return True
    return False


def _row_value(definition: Field, text: str) -> Any:
    if definition.type == "N":
        return _to_number(text)
    if definition.type == "D":
        return _to_date(text)
    if definition.type == "L":
        return truthy(text)
    return text


def _apply_operator(field: Any, operator: str, value: Any, context: Context) -> bool:
    operator = operator.strip().upper()
    if operator == "=":
        return equal_values(field, value, table=True)
    if operator == "<>":
        return not equal_values(field, value, table=True)
    if operator in (">", "<", ">=", "<="):
        ltext = value_to_text(field).upper()
        rtext = value_to_text(value).upper()
        if _is_number(field) or _is_number(value):
            lnumber, rnumber = _to_number(field), _to_number(value)
            if lnumber is None or rnumber is None:
                return False
            comparison = (lnumber > rnumber) - (lnumber < rnumber)
        elif isinstance(field, date) or isinstance(value, date):
            ldate, rdate = _to_date(field), _to_date(value)
            if ldate is None or rdate is None:
                return False
            comparison = (ldate > rdate) - (ldate < rdate)
        else:
            comparison = (ltext > rtext) - (ltext < rtext)
        return {"<": comparison < 0, ">": comparison > 0,
                "<=": comparison <= 0, ">=": comparison >= 0}[operator]
    if operator == "?":
        left = value_to_text(field)
        right = value_to_text(value)
        if not left or not right:
            return False
        return (left[:1].upper() == right[:1].upper()
                and _soundex(left) == _soundex(right))
    if operator in ("*A", "*F", "*L", "*W"):
        function = {"*A": "*ANY", "*F": "*FIRST",
                    "*L": "*LEADING", "*W": "*WORD"}[operator]
        table_context = Context(fields=context.fields, values=context.values,
                                pattern=PATTERN_INSENSITIVE)
        return bool(_call(function, [("literal", value_to_text(field)),
                                     ("literal", value_to_text(value))],
                          table_context))
    raise ExprError(f"Unknown search operator: {operator}")


__all__ = [
    "Context",
    "ExprError",
    "PATTERN_CASE",
    "PATTERN_EXACT",
    "PATTERN_INSENSITIVE",
    "PATTERN_MODES",
    "SearchRow",
    "compare_values",
    "equal_values",
    "evaluate",
    "evaluate_boolean",
    "field_value",
    "key_text",
    "matches_search_rows",
    "parse_expression",
    "search_rows_expression",
    "sort_key",
    "text_equal",
    "tokenize",
    "truthy",
    "value_to_text",
]
