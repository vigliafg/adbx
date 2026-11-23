from adbx.cell.font import FONT_BYTES, GLYPH_H, GLYPH_W, BitmapFont


def test_default_font_loads():
    font = BitmapFont.load_default()
    assert len(font.data) == FONT_BYTES == 4096


def test_space_is_empty():
    font = BitmapFont.load_default()
    assert font.rows(0x20) == b"\x00" * GLYPH_H


def test_capital_a_has_pixels():
    font = BitmapFont.load_default()
    rows = font.rows(ord("A"))
    assert any(rows)
    assert font.pixel(ord("A"), 0, 0) in (True, False)
    assert any(font.pixel(ord("A"), x, y) for y in range(GLYPH_H) for x in range(GLYPH_W))


def test_horizontal_rule_is_single_row():
    font = BitmapFont.load_default()
    rows = font.rows(0xC4)
    full = [index for index, bits in enumerate(rows) if bits == 0xFF]
    assert full, "il glifo ─ deve avere una riga piena"
    assert all(bin(bits).count("1") <= 1 for index, bits in enumerate(rows) if index not in full)


def test_vertical_rule_spans_full_height():
    font = BitmapFont.load_default()
    rows = font.rows(0xB3)
    assert all(bits for bits in rows)
    columns = {x for x in range(GLYPH_W) if font.pixel(0xB3, x, 0)}
    assert len(columns) <= 3


def test_invalid_table_size():
    try:
        BitmapFont(b"\x00" * 100)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("atteso ValueError")
