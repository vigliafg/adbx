"""Dump golden delle schermate del guscio."""

from pathlib import Path

from adbx.shell import screens
from adbx.shell.state import demo_state

GOLDEN = Path(__file__).parent / "golden"


def _check(name: str, dump: str) -> None:
    path = GOLDEN / name
    if not path.exists():  # pragma: no cover - primo giro
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump, encoding="utf-8")
    assert dump == path.read_text(encoding="utf-8")


def test_main_menu_golden():
    state = demo_state()
    _check("main-menu.txt", screens.main_menu(state).buffer.dump())


def test_directory_golden():
    state = demo_state()
    entry = state.listing.entries[0]
    view = screens.directory(state, 0, entry.selectable_text, len(entry.selectable_text))
    _check("directory.txt", view.buffer.dump())


def test_help_golden():
    state = demo_state()
    view, _spans, _positions = screens.help_overlay(
        screens.main_menu(state, selected=5), "choose")
    _check("help.txt", view.buffer.dump())
