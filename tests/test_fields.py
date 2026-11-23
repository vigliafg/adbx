"""Tipi di campo, valori canonici e tabella di conversione (O2)."""

import pytest

from adbx.data.fields import (
    Field,
    FieldError,
    convert_value,
    date_display,
    format_value,
    make_field,
    parse_value,
    validate_fields,
)


def test_field_names_and_fixed_lengths():
    assert Field("price", "n", 6, 2).name == "PRICE"
    assert make_field("when", "d").length == 8
    assert make_field("ok", "l").length == 1
    assert make_field("notes", "m").length == 10
    for bad in ("1ABC", "A-B", "A" * 11):
        with pytest.raises(FieldError):
            Field(bad, "C", 10)
    with pytest.raises(FieldError):
        Field("A", "N", 4, 4)
    with pytest.raises(FieldError):
        Field("A", "C", 10, 2)


def test_validate_limits_and_duplicates():
    validate_fields([Field("A", "C", 10), Field("B", "N", 5, 2)])
    with pytest.raises(FieldError):
        validate_fields([Field("A", "C", 10), Field("A", "C", 10)])
    with pytest.raises(FieldError):
        validate_fields([])


def test_numeric_canonical_and_rounding():
    field = Field("PRICE", "N", 6, 2)
    assert parse_value(field, "2.4") == "2.40"
    assert parse_value(Field("PRICE", "N", 8, 2), "$ 1,234.5") == "1234.50"
    assert parse_value(field, "2.345") == "2.35"  # half-up
    assert parse_value(field, "") == ""
    assert format_value(field, "2.4") == "2.4"
    with pytest.raises(FieldError):
        parse_value(field, "123456")
    with pytest.raises(FieldError):
        parse_value(field, "abc")


def test_dates_and_logical():
    date_field = Field("D", "D", 8)
    assert parse_value(date_field, "12/31/1993") == "19931231"
    assert parse_value(date_field, "12-31-93") == "19931231"
    assert parse_value(date_field, "19931231") == "19931231"
    assert date_display("19931231") == "12/31/1993"
    assert parse_value(date_field, "") == ""
    with pytest.raises(FieldError):
        parse_value(date_field, "02/30/1993")

    logical = Field("L", "L", 1)
    for text, expected in (("T", "1"), ("y", "1"), ("F", "0"), ("no", "0"),
                           ("", "")):
        assert parse_value(logical, text) == expected
    with pytest.raises(FieldError):
        parse_value(logical, "maybe")
    assert format_value(logical, "1") == ".T."
    assert format_value(logical, "0") == ".F."


# -- conversione alla riconfigurazione ------------------------------------


def _convert(old: Field, new: Field, value: str) -> str:
    return convert_value(old, new, value)


def test_character_conversions():
    char = Field("C", "C", 20)
    assert _convert(char, Field("D", "D", 8), "12/31/1993") == "19931231"
    assert _convert(char, Field("D", "D", 8), "31/12/1993") == ""
    assert _convert(char, Field("L", "L", 1), "yes") == "1"
    assert _convert(char, Field("L", "L", 1), "maybe") == ""
    assert _convert(char, Field("N", "N", 8, 2), "$ 1,234.5abc") == "1234.50"
    assert _convert(char, Field("N", "N", 6, 2), "abc") == "0.00"
    assert _convert(char, Field("N", "N", 6, 2), "") == "0.00"


def test_numeric_conversions():
    number = Field("N", "N", 6, 2)
    assert _convert(number, Field("C", "C", 10), "2.49") == "2.49"
    assert _convert(number, Field("L", "L", 1), "0.00") == "0"
    assert _convert(number, Field("L", "L", 1), "1.00") == "1"
    assert _convert(number, Field("L", "L", 1), "-1.00") == ""
    assert _convert(number, Field("D", "D", 8), "2.49") == ""


def test_date_and_logical_conversions():
    date = Field("D", "D", 8)
    assert _convert(date, Field("C", "C", 10), "19931231") == "19931231"
    assert _convert(date, Field("N", "N", 8), "19931231") == ""
    assert _convert(date, Field("L", "L", 1), "19931231") == ""

    logical = Field("L", "L", 1)
    assert _convert(logical, Field("C", "C", 2), "1") == "T"
    assert _convert(logical, Field("C", "C", 2), "0") == "F"
    assert _convert(logical, Field("C", "C", 2), "") == ""
    assert _convert(logical, Field("D", "D", 8), "1") == ""
    assert _convert(logical, Field("N", "N", 5), "1") == ""


def test_widening_and_narrowing_character():
    wide = Field("C", "C", 10)
    assert _convert(wide, Field("C", "C", 4), "abcdefgh") == "abcd"
    assert _convert(Field("C", "C", 4), Field("C", "C", 10), "abc") == "abc"
