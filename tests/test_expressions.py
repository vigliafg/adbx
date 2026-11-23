"""Espressioni, pattern matching e tabelle di ricerca (O3)."""

from datetime import date
from decimal import Decimal

import pytest

from adbx.data.expressions import (
    PATTERN_CASE,
    PATTERN_EXACT,
    PATTERN_INSENSITIVE,
    Context,
    ExprError,
    SearchRow,
    evaluate,
    evaluate_boolean,
    matches_search_rows,
    search_rows_expression,
    tokenize,
)
from adbx.data.fields import Field

FIELDS = (
    Field("NAME", "C", 10), Field("CITY", "C", 10), Field("AMOUNT", "N", 8, 2),
    Field("BORN", "D", 8), Field("ACTIVE", "L", 1), Field("NOTES", "M", 10),
)


def context(**values) -> Context:
    defaults = {"NAME": "Smithson", "CITY": "Boston", "AMOUNT": "10.00",
                "BORN": "19930102", "ACTIVE": "1", "NOTES": ""}
    defaults.update(values)
    return Context(fields=FIELDS, values=defaults, pattern=PATTERN_EXACT)


def test_pattern_matching_exact_case_insensitive():
    exact = context()
    assert evaluate_boolean('CITY = "Boston"', exact)
    assert not evaluate_boolean('CITY = "Bos"', exact)
    assert not evaluate_boolean('CITY = "BOSTON"', exact)

    case = context()
    case.pattern = PATTERN_CASE
    assert evaluate_boolean('CITY = "Bos"', case)
    assert not evaluate_boolean('CITY = "BOS"', case)

    insensitive = context()
    insensitive.pattern = PATTERN_INSENSITIVE
    assert evaluate_boolean('CITY = "BOS"', insensitive)
    assert evaluate_boolean('CITY = "bos"', insensitive)
    assert evaluate_boolean('CITY = "Bos"', insensitive)


def test_exact_match_operator_ignores_pattern_setting():
    for mode in (PATTERN_EXACT, PATTERN_CASE, PATTERN_INSENSITIVE):
        ctx = context(CITY="Boston")
        ctx.pattern = mode
        assert evaluate_boolean('CITY == "Boston"', ctx)
        assert not evaluate_boolean('CITY == "Bos"', ctx)
        assert not evaluate_boolean('CITY == "boston"', ctx)


def test_numbers_dates_logicals_and_blanks():
    assert evaluate_boolean("AMOUNT = 10", context())
    assert evaluate_boolean("AMOUNT > 9.99", context())
    assert evaluate_boolean("BORN = {01/02/93}", context())
    assert evaluate_boolean("BORN < {02/01/1993}", context())
    assert evaluate_boolean("ACTIVE", context())
    assert evaluate_boolean("NOT ACTIVE", context(ACTIVE="0"))
    assert evaluate_boolean("ISBLANK(NOTES)", context())
    assert not evaluate_boolean("ISBLANK(NAME)", context())


def test_and_has_precedence_over_or():
    values = context(NAME="Zed", CITY="Rome", AMOUNT="1.00")
    assert not evaluate_boolean(
        'NAME = "Smithson" .OR. CITY = "Rome" .AND. AMOUNT > 5', values)
    assert evaluate_boolean(
        'NAME = "Smithson" .OR. CITY = "Rome" .AND. AMOUNT > 0', values)
    assert evaluate_boolean(
        '(NAME = "Smithson" .OR. CITY = "Rome") .AND. AMOUNT > 0', values)


def test_functions_and_concatenation():
    ctx = context()
    assert evaluate('UPPER(NAME) + "!"', ctx) == "SMITHSON!"
    assert evaluate('LEFT(NAME,3)', ctx) == "Smi"
    assert evaluate("SUBSTR(NAME,2,3)", ctx) == "mit"
    assert evaluate("LEN(TRIM(NAME))", ctx) == Decimal(8)
    assert evaluate("AMOUNT * 2 + 1", ctx) == Decimal("21.00")
    assert evaluate('IF(ACTIVE,"yes","no")', ctx) == "yes"
    assert evaluate_boolean('AT("son",NAME) > 0', ctx)
    assert evaluate_boolean('*ANY(NAME,"son")', ctx)
    assert evaluate_boolean('*FIRST(NAME,"Smi")', ctx)
    assert evaluate_boolean('*LEADING(NAME,"son")', context(NAME="son of Sam"))
    assert not evaluate_boolean('*WORD(NAME,"son")', ctx)
    assert evaluate_boolean('LIKE(NAME,"Sm*son")', context())
    assert evaluate("RECNO()", context()) == Decimal(0)
    assert evaluate("DATE()", context()) == date.today()


def test_sounds_like_operator():
    row = SearchRow("NAME", "?", "Smith")
    assert matches_search_rows([row], context(NAME="Smyth"))
    assert not matches_search_rows([row], context(NAME="Jones"))


def test_table_mode_is_case_insensitive_and_exact():
    rows = [SearchRow("CITY", "=", "boston")]
    assert matches_search_rows(rows, context())
    assert not matches_search_rows(
        [SearchRow("CITY", "=", "Bos")], context())


def test_table_connectors_follow_and_precedence():
    rows = [
        SearchRow("CITY", "=", "ROME", "OR"),
        SearchRow("CITY", "=", "BOSTON", "AND"),
        SearchRow("ACTIVE", "=", "T", "AND"),
    ]
    assert matches_search_rows(
        rows, context(CITY="Rome", ACTIVE="0"))
    assert not matches_search_rows(
        rows, context(CITY="Boston", ACTIVE="0"))
    assert matches_search_rows(
        rows, context(CITY="Boston", ACTIVE="1"))


def test_wildcard_fields_and_operators():
    rows = [SearchRow("*CHAR", "*A", "bos")]
    assert matches_search_rows(rows, context())
    rows = [SearchRow("*MEMO", "*A", "needle")]
    assert matches_search_rows(rows, context(NOTES="a needle here"))
    rows = [SearchRow("NAME", "*A", "MIT")]
    assert matches_search_rows(rows, context())
    rows = [SearchRow("NAME", "*L", "smi")]
    assert matches_search_rows(rows, context())
    rows = [SearchRow("NAME", "*W", "son")]
    assert not matches_search_rows(rows, context())


def test_padded_keys_preserve_field_widths():
    ctx = Context(fields=(Field("A", "C", 5), Field("B", "C", 5)),
                  values={"A": "x", "B": "y"}, padded=True)
    assert evaluate("A+B", ctx) == "x    y    "


def test_generated_rows_expression():
    rows = [SearchRow("CITY", "=", "PLACID", "OR"),
            SearchRow("NAME", "*A", "smith")]
    text = search_rows_expression(rows)
    assert 'CITY = "PLACID"' in text
    assert '*ANY(NAME,"smith")' in text
    assert ".OR." in text


def test_tokenize_and_errors():
    tokens = tokenize('NAME = "x" .AND. AMOUNT >= 2')
    assert ("ident", "NAME") in tokens
    assert ("keyword", "AND") in tokens
    with pytest.raises(ExprError):
        evaluate('NAME = ', context())
    with pytest.raises(ExprError):
        evaluate('CITY = "x" AND', context())
    with pytest.raises(ExprError):
        evaluate("UNKNOWN(1)", context())
