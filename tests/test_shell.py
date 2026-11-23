"""Lezione 1 del Tutorial: la shell si apre e mostra il chrome.

Il dump della schermata e' golden: se cambia anche un solo carattere o un solo
attributo, il test lo segnala.
"""

from pathlib import Path

from adbx.cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
from adbx.screen.demo import demo_buffer

GOLDEN = Path(__file__).parent / "golden" / "main-menu.txt"


def test_grid_is_80x25():
    buffer = demo_buffer(show_popup=False)
    assert (buffer.width, buffer.height) == (SCREEN_WIDTH, SCREEN_HEIGHT)
    assert len(buffer.to_lines()) == SCREEN_HEIGHT


def test_chrome_rows():
    buffer = demo_buffer(show_popup=False)
    assert "Current database" in buffer.text_of(0)
    assert "Primary index" in buffer.text_of(1)
    assert buffer.text_of(22).strip().startswith("View")
    assert "Display records" in buffer.text_of(23)
    assert "F1 Help" in buffer.text_of(24)


def test_all_twelve_commands_present():
    buffer = demo_buffer(show_popup=False)
    text = "\n".join(buffer.to_lines())
    for command in (
        "View/enter records",
        "Print",
        "Search/sort lists",
        "Indexes/ranges",
        "Global update/delete",
        "Choose database/set",
        "Database/set design",
        "Layouts",
        "Applications",
        "Utilities",
        "Other",
        "Quit",
    ):
        assert command in text, command


def test_selection_changes_help_line():
    idle = demo_buffer(selected=0, show_popup=False)
    selected = demo_buffer(selected=3, show_popup=False)
    assert idle.text_of(23) != selected.text_of(23)


def test_popup_is_composited_over_base():
    plain = demo_buffer(show_popup=False)
    with_popup = demo_buffer(show_popup=True)
    assert plain.to_lines() != with_popup.to_lines()
    assert "Open Databases" in "\n".join(with_popup.to_lines())


def test_golden_screen():
    dump = demo_buffer(show_popup=False).dump()
    if not GOLDEN.exists():  # pragma: no cover
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(dump, encoding="utf-8")
    assert dump == GOLDEN.read_text(encoding="utf-8")
