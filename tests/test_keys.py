import pytest

from adbx.screen.keys import Key, is_special, parse
from adbx.screen.keys import format as fmt


@pytest.mark.parametrize(
    "text,expected",
    [
        ("f10", Key("F10")),
        ("F1", Key("F1")),
        ("alt-f", Key("F", alt=True)),
        ("ctrl-home", Key("HOME", ctrl=True)),
        ("alt-ctrl-a", Key("A", alt=True, ctrl=True)),
        ("{ENTER}", Key("ENTER")),
        ("return", Key("ENTER")),
        ("esc", Key("ESC")),
        ("pgdn", Key("PGDN")),
        ("del", Key("DELETE")),
    ],
)
def test_parse(text, expected):
    assert parse(text) == expected


@pytest.mark.parametrize("text", ["alt-", "hyper-a", ""])
def test_parse_errors(text):
    with pytest.raises(ValueError):
        parse(text)


def test_format_roundtrip():
    for text in ("alt-f", "ctrl-home", "ctrl-alt-shift-a", "f10", "enter"):
        assert parse(fmt(parse(text))) == parse(text)


def test_name_is_normalized():
    assert Key("enter").name == "ENTER"
    assert Key("Return").name == "ENTER"


def test_aliases_are_shared():
    assert Key("del") == Key("delete")
    assert Key("escape") == Key("esc")
    assert Key("bs") == Key("backspace")


def test_specials():
    assert is_special("F10")
    assert is_special("enter")
    assert not is_special("A")
    assert not is_special("5")


def test_keys_are_hashable_and_ordered():
    assert len({Key("ALT"), Key("alt", alt=True)}) == 2
    assert Key("A") < Key("B")
