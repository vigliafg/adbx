from adbx.cell.cp437 import (
    BLOCK_FULL,
    CHARS,
    DOUBLE,
    SINGLE,
    TO_BYTE,
    is_drawing,
    to_byte,
)


def test_table_has_256_entries():
    assert len(CHARS) == 256
    assert len(TO_BYTE) >= 220  # 0x00-0x1F collassano nello spazio


def test_ascii_identity():
    assert CHARS[ord("A")] == "A"
    assert to_byte("A") == 65


def test_control_codes_are_blank():
    assert CHARS[0x00] == " "
    assert CHARS[0x07] == " "


def test_high_range_graphics():
    assert to_byte("─") == 0xC4
    assert to_byte("│") == 0xB3
    assert to_byte("┌") == 0xDA
    assert to_byte("█") == 0xDB
    assert to_byte("░") == 0xB0


def test_accents_and_symbols():
    assert to_byte("é") == 0x82
    assert to_byte("±") == 0xF1


def test_unknown_char_falls_back_to_question_mark():
    assert to_byte("€") == to_byte("?")
    assert to_byte("") == to_byte(" ")


def test_drawing_detection():
    assert is_drawing("┌")
    assert is_drawing(BLOCK_FULL)
    assert not is_drawing("A")
    assert set(SINGLE.values()) | set(DOUBLE.values()) <= {c for c in CHARS if is_drawing(c)}
