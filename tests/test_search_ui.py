"""O3 — lezione 15: search/sort lists dall'interfaccia."""

from support import make_patrons

from adbx.data import indexing
from adbx.data.expressions import SearchRow
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def type_text(controller, text):
    for char in text:
        controller.handle(Key("SPACE" if char == " " else char,
                             shift=char.isupper()))


def open_browse(controller):
    controller.handle(Key("V"))
    for _ in range(3):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.records.mode == "browse"


def dismiss(controller):
    if controller.overlay is not None and controller.overlay.kind == "message":
        controller.handle(Key("ENTER"))


def test_one_time_search_with_range(tmp_path):
    path, _database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=path)

    controller.handle(Key("S"))
    assert controller.overlay.kind == "submenu"
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.base == "search"

    controller.handle(Key("F2"))
    picker = controller.search_session.picker
    picker.selected = picker.items.index("CITY")
    controller.handle(Key("ENTER"))
    controller.handle(Key("TAB"))
    controller.handle(Key("TAB"))
    type_text(controller, "placid")
    controller.handle(Key("F10"))

    # Senza criteri di ordinamento compare Range Settings.
    assert controller.base == "range"
    controller.handle(Key("F10"))
    assert controller.base == "search"
    assert controller.search_session.stage == "runbox"
    controller.handle(Key("ENTER"))

    assert controller.base == "menu"
    assert controller.overlay.kind == "message"
    assert "3 record(s)" in controller.overlay.text
    primary = controller.database.primary_index
    assert primary.startswith(indexing.SEARCH_PREFIX)

    dismiss(controller)
    open_browse(controller)
    cities = [controller.database.read(seq)["CITY"]
              for seq in controller.records._seqs]
    assert cities == ["Placid", "Placid", "Placid"]


def test_saved_search_with_sort_and_history(tmp_path):
    path, _database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=path)

    controller.handle(Key("S"))
    controller.handle(Key("ENTER"))  # Create/edit a saved search/sort
    assert controller.overlay.action == "search-letter"
    type_text(controller, "A")
    controller.handle(Key("ENTER"))
    assert controller.base == "search"

    controller.handle(Key("F2"))
    picker = controller.search_session.picker
    picker.selected = picker.items.index("STATE")
    controller.handle(Key("ENTER"))
    controller.handle(Key("TAB"))
    controller.handle(Key("TAB"))
    type_text(controller, "NY")

    controller.handle(Key("F4"))  # Sort order
    controller.handle(Key("F2"))  # Fields, crea la prima riga
    picker = controller.search_session.picker
    picker.selected = picker.items.index("CITY")
    controller.handle(Key("ENTER"))
    controller.handle(Key("F10"))
    assert controller.search_session.stage == "runbox"
    controller.handle(Key("ENTER"))

    assert controller.base == "menu"
    saved = indexing.saved_search(controller.database, "A")
    assert saved is not None
    assert saved.search_rows[0].field == "STATE"
    assert saved.sort_rows == [("CITY", "A")]
    result = indexing.search_history(controller.database)[0]
    assert result.letter == "A"
    ordered = [controller.database.read(seq)["CITY"] for seq in result.seqs]
    assert ordered == sorted(ordered, key=str.upper)

    dismiss(controller)
    controller.handle(Key("S"))
    controller.handle(Key("DOWN"))
    for _ in range(3):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # History
    assert controller.overlay.kind == "search-history"
    controller.handle(Key("ENTER"))
    assert controller.database.primary_index == \
        f"{indexing.SEARCH_PREFIX}{result.id}"


def test_out_of_date_and_refresh(tmp_path):
    path, _database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    result = indexing.run_search(
        controller.database,
        search_rows=[SearchRow("CITY", "=", "Placid")],
        description="Placid")
    assert not result.out_of_date(controller.database)

    controller.database.update(1, {**controller.database.read(1),
                                   "CITY": "Rome"})
    open_browse(controller)
    text = "\n".join(controller.view().buffer.to_lines())
    assert "\u2666" in text

    controller.handle(Key("F10"))  # torna al menu
    controller.handle(Key("S"))
    for _ in range(4):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # History
    controller.handle(Key("F5"))  # Refresh
    latest = indexing.search_history(controller.database)[0]
    assert not latest.out_of_date(controller.database)


def test_run_and_erase_saved_search(tmp_path):
    path, _database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    indexing.save_saved_search(controller.database, indexing.SavedSearch(
        "C", "New Yorkers",
        search_rows=[SearchRow("STATE", "=", "NY")],
        sort_rows=[("NAME", "A")]))

    controller.handle(Key("S"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Run a saved search/sort
    assert controller.overlay.kind == "choose"
    controller.overlay.selected = 0
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "message"
    assert "4 record(s)" in controller.overlay.text

    dismiss(controller)
    controller.handle(Key("S"))
    for _ in range(3):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Erase a saved search/sort
    controller.overlay.selected = 0
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "confirm"
    controller.handle(Key("ENTER"))
    assert indexing.saved_search(controller.database, "C") is None


def test_run_saved_without_sort_asks_range(tmp_path):
    path, _database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    indexing.save_saved_search(controller.database, indexing.SavedSearch(
        "D", "New Yorkers",
        search_rows=[SearchRow("STATE", "=", "NY")]))

    controller.handle(Key("S"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    controller.overlay.selected = 0
    controller.handle(Key("ENTER"))
    assert controller.base == "range"
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert controller.overlay.kind == "message"
    assert "4 record(s)" in controller.overlay.text


def test_pattern_matching_setting_from_other_menu(tmp_path):
    path, _database = make_patrons(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    assert controller.workspace.pattern_mode == "exact"
    controller.handle(Key("O"))
    assert controller.overlay.kind == "submenu"
    controller.handle(Key("ENTER"))
    assert controller.workspace.pattern_mode == "case"
    assert "Pattern matching: Case" in controller.overlay.text
    controller.handle(Key("ENTER"))
    controller.handle(Key("O"))
    controller.handle(Key("ENTER"))
    assert controller.workspace.pattern_mode == "insensitive"
