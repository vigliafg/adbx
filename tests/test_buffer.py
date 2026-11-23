import pytest

from adbx.cell.buffer import BLANK, SCREEN_HEIGHT, SCREEN_WIDTH, Cell, CellBuffer
from adbx.cell.cp437 import SHADE_LIGHT


def test_default_size_is_screen():
    buffer = CellBuffer()
    assert (buffer.width, buffer.height) == (SCREEN_WIDTH, SCREEN_HEIGHT)
    assert buffer.get(0, 0) == BLANK


def test_invalid_size():
    with pytest.raises(ValueError):
        CellBuffer(0, 10)


def test_write_returns_next_column():
    buffer = CellBuffer(20, 3)
    end = buffer.write(0, 2, "abc")
    assert end == 5
    assert buffer.text_of(0) == "  abc"


def test_write_clips_at_right_edge():
    buffer = CellBuffer(5, 1)
    end = buffer.write(0, 3, "abcdef")
    assert buffer.text_of(0) == "   ab"
    assert end == 5


def test_write_clips_negative_column():
    buffer = CellBuffer(5, 1)
    buffer.write(0, -2, "abcd")
    assert buffer.text_of(0) == "cd"


def test_write_limit():
    buffer = CellBuffer(10, 1)
    buffer.write(0, 0, "abcdef", limit=3)
    assert buffer.text_of(0) == "abc"


def test_style_applies_to_all_cells():
    buffer = CellBuffer(4, 1)
    buffer.write(0, 0, "ab", fg=14, bg=1, bold=True)
    cell = buffer.get(0, 1)
    assert (cell.ch, cell.fg, cell.bg, cell.bold) == ("b", 14, 1, True)


def test_write_outside_rows_is_noop():
    buffer = CellBuffer(4, 2)
    assert buffer.write(9, 0, "x") == 0
    assert buffer.text_of(1) == ""


def test_fill_rect_and_clear():
    buffer = CellBuffer(6, 3)
    buffer.fill_rect(1, 1, 1, 3, "*", fg=4)
    assert buffer.to_lines()[1] == " ***  "
    buffer.clear()
    assert buffer.to_lines() == ["      "] * 3


@pytest.mark.parametrize("double", [False, True])
def test_box_corners(double):
    buffer = CellBuffer(10, 4)
    buffer.box(0, 0, 4, 6, double=double)
    lines = buffer.to_lines()
    tl, tr = ("╔", "╗") if double else ("┌", "┐")
    bl, br = ("╚", "╝") if double else ("└", "┘")
    v = "║" if double else "│"
    assert lines[0][:6] == tl + ("═" if double else "─") * 4 + tr
    assert lines[1][0] == v and lines[1][5] == v
    assert lines[3][:6] == bl + ("═" if double else "─") * 4 + br


def test_box_too_small_is_ignored():
    buffer = CellBuffer(4, 4)
    buffer.box(0, 0, 1, 5)
    assert buffer.to_lines() == ["    "] * 4


def test_shadow_uses_shade():
    buffer = CellBuffer(8, 6)
    buffer.shadow(1, 1, 3, 4)
    assert buffer.get(4, 2).ch == SHADE_LIGHT
    assert buffer.get(2, 5).ch == SHADE_LIGHT


def test_horizontal_and_vertical_lines():
    buffer = CellBuffer(6, 4)
    buffer.hline(0, 0, 6)
    buffer.vline(1, 5, 3)
    assert buffer.to_lines()[0] == "──────"
    assert buffer.to_lines()[3] == "     │"


def test_dump_is_deterministic_and_coded():
    buffer = CellBuffer(4, 2)
    buffer.write(0, 0, "hi", fg=15, bg=1)
    dump = buffer.dump()
    assert dump.splitlines()[0] == "adbx 4x2"
    assert dump.splitlines()[1] == "hi  "
    assert dump.splitlines()[2] == "2@15,1,0,0 2@7,1,0,0"
    assert buffer.dump() == dump


def test_cell_styled_is_immutable():
    cell = Cell(ch="x", fg=7, bg=1)
    other = cell.styled(fg=12, bold=True)
    assert cell.fg == 7 and not cell.bold
    assert other.fg == 12 and other.bold and other.ch == "x"


def test_colors_are_resolved_to_16():
    buffer = CellBuffer(2, 1)
    buffer.write(0, 0, "x", fg=300, bg=17)
    cell = buffer.get(0, 0)
    assert 0 <= cell.fg < 16 and 0 <= cell.bg < 16
