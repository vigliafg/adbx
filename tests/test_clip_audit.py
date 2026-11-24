"""Audit del clipping: nessuna vista deve scrivere fuori dalla griglia 80x25.

`CellBuffer` taglia in silenzio, quindi un layout che sborda non fallisce mai:
questi test attivano `audit_clipping()` e pretende un elenco vuoto su tutte le
viste canoniche (le stesse della cattura UI) e sulle schermate del guscio.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from adbx.cell.buffer import (  # noqa: E402
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    CellBuffer,
    allow_clipping,
    audit_clipping,
)
from adbx.shell import screens  # noqa: E402
from adbx.shell.state import demo_state  # noqa: E402

import capture_ui  # noqa: E402


def _fmt(events) -> str:
    return "\n".join(
        f"{event.kind} riga {event.row} colonna {event.col}: "
        f"{event.detail!r} <- {event.where}"
        for event in events)


# Le viste della cattura canonica sono la copertura più ampia che abbiamo:
# ogni sessione del guscio con dati demo, overlay compresi.
@pytest.fixture(scope="module")
def canonical_views():
    with audit_clipping() as events:
        views = capture_ui.build_views()
    return views, list(events)


def test_canonical_views_do_not_write_outside_the_grid(canonical_views):
    views, events = canonical_views
    assert len(views) >= 50
    assert events == [], f"{len(events)} scritture fuori griglia:\n{_fmt(events)}"
    for name, view in views.items():
        assert (view.buffer.width, view.buffer.height) == (
            SCREEN_WIDTH, SCREEN_HEIGHT), name


def test_shell_screens_do_not_write_outside_the_grid():
    state = demo_state()
    entry = state.listing.entries[0]
    text = entry.selectable_text

    def build() -> dict[str, object]:
        menu = screens.main_menu(state)
        return {
            "main": lambda: screens.main_menu(state, selected=5),
            "directory": lambda: screens.directory(
                state, 0, text, len(text)),
            "structure": lambda: screens.structure(state),
            "status": lambda: screens.status_screen(state),
            "help": lambda: screens.help_overlay(menu, "choose")[0],
            "submenu": lambda: screens.submenu_overlay(
                menu, [("One", None), ("Two", None)], 0),
            "variables": lambda: screens.variables_overlay(
                menu, [("%NAME", "Wendy"), ("%SYS_DATE", "19930505")], 0),
            "history": lambda: screens.search_history_overlay(
                menu, [], 0),
        }

    for name, factory in build().items():
        with audit_clipping() as events:
            factory()
        assert events == [], f"{name}:\n{_fmt(events)}"


@pytest.mark.allow_clipping
def test_long_text_at_the_edge_is_reported():
    buffer = CellBuffer(10, 3)
    with audit_clipping() as events:
        buffer.write(0, 8, "abcdef")
        buffer.write(0, -2, "ab")
        buffer.write(3, 0, "x")
        buffer.write(1, 4, "abc", limit=3)
        buffer.fill_rect(2, 8, 3, 5)
    kinds = [event.kind for event in events]
    assert kinds == ["write-right", "write-left", "write-row", "fill-row",
                     "fill-col"]


def test_exact_fit_and_negative_offsets_are_not_reported():
    buffer = CellBuffer(10, 3)
    with audit_clipping() as events:
        buffer.write(0, 0, "0123456789")
        buffer.write(1, 7, "abc", limit=3)
        buffer.hline(2, 0, 10)
        buffer.box(0, 0, 3, 10)
        buffer.fill_rect(0, 0, 3, 10)
    assert events == [], _fmt(events)


@pytest.mark.allow_clipping
def test_allow_clipping_silences_the_audit():
    buffer = CellBuffer(6, 2)
    with audit_clipping() as events:
        with allow_clipping():
            buffer.write(0, 5, "xy")
        buffer.write(1, 5, "xy")
    assert [event.kind for event in events] == ["write-right"]
    assert events[0].row == 1


@pytest.mark.allow_clipping
def test_audit_is_off_by_default_and_nestable():
    buffer = CellBuffer(5, 2)
    with audit_clipping() as outer:
        with audit_clipping() as inner:
            buffer.write(0, 4, "xy")
        assert inner is outer
    assert [event.kind for event in outer] == ["write-right"]
    buffer.write(0, 4, "xy")  # fuori audit: silenzio
