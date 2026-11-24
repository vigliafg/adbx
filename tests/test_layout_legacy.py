"""Vincoli della griglia legacy 80x25 e delle righe di menu."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import adbx.shell as shell_package
from adbx.cell.buffer import (
    HELP_ROW,
    MENU_ROW,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    STATUS_ROW,
    WORK_ROWS,
    CellBuffer,
)
from adbx.shell import screens
from adbx.shell.state import demo_state


def test_grid_is_the_original_80x25():
    assert SCREEN_WIDTH == 80
    assert SCREEN_HEIGHT == 25
    assert STATUS_ROW == 22
    assert HELP_ROW == 23
    assert MENU_ROW == 24
    assert WORK_ROWS == 22

    buffer = CellBuffer()
    assert (buffer.width, buffer.height) == (80, 25)
    assert buffer.dump().splitlines()[0] == "adbx 80x25"


def menu_width(items: list[tuple[str, str]]) -> int:
    """Larghezza della riga disegnata da `draw_menu_line` (colonna iniziale 1)."""
    columns = 1
    for key, label in items:
        columns += len(key) + len(label) + 3
    return columns - 3


def _menu_lists() -> list[tuple[str, list[tuple[str, str]]]]:
    found: list[tuple[str, list[tuple[str, str]]]] = []
    for module_info in pkgutil.iter_modules(shell_package.__path__):
        module = importlib.import_module(f"adbx.shell.{module_info.name}")
        for name in dir(module):
            if not name.endswith("_KEYS") or name.startswith("_"):
                continue
            value = getattr(module, name)
            if (isinstance(value, list) and value
                    and isinstance(value[0], tuple) and len(value[0]) == 2):
                found.append((f"{module_info.name}.{name}", value))
    return found


def test_every_function_key_line_fits_the_grid():
    too_wide = [(name, menu_width(items), items)
                for name, items in _menu_lists() if menu_width(items) > SCREEN_WIDTH]
    assert too_wide == [], (
        "menu line oltre 80 colonne: "
        + ", ".join(f"{name} ({width})" for name, width, _items in too_wide))


def test_menu_lists_cover_the_shell_modules():
    names = {name for name, _items in _menu_lists()}
    # Se un modulo perde tutte le liste di tasti il test qui sopra non se ne
    # accorgerebbe: ancori almeno le principali.
    for expected in ("screens.MAIN_MENU_KEYS", "screens.DIRECTORY_KEYS",
                     "forms.FORM_KEYS", "reports.REPORT_KEYS",
                     "searching.SEARCH_KEYS"):
        assert expected in names


def test_shell_screens_stay_inside_the_buffer():
    state = demo_state()
    entry = state.listing.entries[0]
    views = {
        "main": screens.main_menu(state),
        "directory": screens.directory(
            state, 0, entry.selectable_text, len(entry.selectable_text)),
        "structure": screens.structure(state),
        "status": screens.status_screen(state),
        "help": screens.help_overlay(screens.main_menu(state), "choose")[0],
        "submenu": screens.submenu_overlay(
            screens.main_menu(state), [("One", None), ("Two", None)], 0),
        "variables": screens.variables_overlay(
            screens.main_menu(state), [("%NAME", "Wendy")], 0),
        "history": screens.search_history_overlay(
            screens.main_menu(state), [], 0),
    }
    for name, view in views.items():
        assert (view.buffer.width, view.buffer.height) == (80, 25), name
        for region in view.regions:
            assert region.col >= 0, f"{name}: region a colonna {region.col}"
            assert region.col + region.width <= SCREEN_WIDTH, name
            assert region.row >= 0, name
            assert region.row + region.height <= SCREEN_HEIGHT, name


def test_overlays_are_not_clipped_at_the_edges():
    state = demo_state()
    for width in (30, 66, 76):
        panel = CellBuffer(width, 6)
        view = screens.overlay_view(screens.main_menu(state), panel, 3, 2, [])
        assert view.buffer.width == SCREEN_WIDTH


def test_buffer_copy_is_independent():
    source = CellBuffer(4, 3)
    source.write(0, 0, "abcd")
    clone = source.copy()
    clone.write(0, 0, "WXYZ")
    assert source.to_lines()[0] == "abcd"
    assert clone.to_lines()[0] == "WXYZ"


@pytest.mark.parametrize("name", ["main-menu", "directory", "help"])
def test_golden_snapshots_use_the_legacy_grid(name):
    from pathlib import Path

    text = (Path(__file__).parent / "golden" / f"{name}.txt").read_text(
        encoding="utf-8")
    assert text.splitlines()[0] == "adbx 80x25"
    assert len(text.splitlines()) == 1 + 2 * SCREEN_HEIGHT


def test_visible_rows_stop_at_the_status_line():
    from adbx.shell.widgets import visible_rows

    assert visible_rows(3) == STATUS_ROW - 3
    assert visible_rows(STATUS_ROW) == 0
    assert visible_rows(STATUS_ROW + 2) == 0


def test_memo_editor_fits_between_the_borders():
    from adbx.shell.records import MemoEditor

    editor = MemoEditor("TAPE_DESC", "hello")
    # L'ombra del popup cade sulla riga subito sotto il pannello.
    assert editor.width <= SCREEN_WIDTH - 4
    assert editor.height <= STATUS_ROW - 2


def test_lookup_table_columns_fit_the_grid():
    from adbx.data.rules import LookupTable
    from adbx.shell.rules import LookupTableEditor

    table = LookupTable(columns=["A", "B", "C", "D", "E"],
                        rows=[["x"] * 6])
    editor = LookupTableEditor(table, field_name="CHOICE")
    widths = [width for _name, width in editor.columns]
    assert len(widths) == 6
    assert sum(widths) <= SCREEN_WIDTH - 4
    assert widths[0] == 24
