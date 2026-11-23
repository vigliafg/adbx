"""O3 — lezione 9: Range Settings dall'interfaccia."""

from support import make_movies

from adbx.data import indexing
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def open_browse(controller):
    controller.handle(Key("V"))
    for _ in range(3):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.records.mode == "browse"


def test_range_descending_order(tmp_path):
    path, _database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    open_browse(controller)
    ascending = list(controller.records._seqs)

    controller.handle(Key("R"))
    assert controller.base == "range"
    controller.handle(Key("DOWN"))  # Order
    controller.handle(Key("ENTER"))  # Ascending -> Descending
    controller.handle(Key("E", alt=True))
    assert controller.base == "records"
    assert controller.records._seqs == list(reversed(ascending))
    assert controller.records.order_indicator == "D"


def test_range_show_deleted(tmp_path):
    path, database = make_movies(tmp_path)
    database.delete(2)
    controller = ShellController(tmp_path, open_path=path)
    open_browse(controller)
    controller.handle(Key("R"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))  # Show
    controller.handle(Key("ENTER"))  # All
    controller.handle(Key("ENTER"))  # Deleted
    controller.handle(Key("E", alt=True))
    assert controller.records._seqs == [2]


def test_range_unique_keys(tmp_path):
    path, _database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    indexing.save_index(controller.database, indexing.IndexDefinition(
        "AVSUBJ", "SUBJECT"))
    controller.database.set_primary_index("AVSUBJ")
    open_browse(controller)
    controller.handle(Key("R"))
    for _ in range(5):
        controller.handle(Key("DOWN"))  # Unique keys
    controller.handle(Key("ENTER"))
    controller.handle(Key("E", alt=True))
    subjects = [controller.database.read(seq)["SUBJECT"]
                for seq in controller.records._seqs]
    assert len(subjects) == len(set(subjects))


def test_range_key_values_and_saved_range(tmp_path):
    path, _database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    indexing.save_index(controller.database, indexing.IndexDefinition(
        "AVRATING", "RATING", "Ordered by Rating"))
    controller.database.set_primary_index("AVRATING")
    open_browse(controller)

    controller.handle(Key("R"))
    controller.handle(Key("F2"))
    picker = controller.range_session.picker
    picker.selected = picker.items.index("Ordered by Rating")
    controller.handle(Key("ENTER"))

    for _ in range(3):
        controller.handle(Key("DOWN"))  # First record
    controller.handle(Key("F3"))
    picker = controller.range_session.picker
    picker.selected = picker.items.index("G")
    controller.handle(Key("ENTER"))

    controller.handle(Key("DOWN"))  # Last record
    controller.handle(Key("F3"))
    picker = controller.range_session.picker
    picker.selected = picker.items.index("PG")
    controller.handle(Key("ENTER"))

    controller.handle(Key("F10"))  # Save box
    controller.handle(Key("DOWN"))  # Exit
    controller.handle(Key("ENTER"))
    ratings = {controller.database.read(seq)["RATING"]
               for seq in controller.records._seqs}
    assert ratings == {"G", "NR", "PG"}
    if controller.overlay is not None:
        controller.handle(Key("ENTER"))

    # Salva il range con lettera e descrizione.
    controller.handle(Key("R"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Descending
    controller.handle(Key("F10"))
    controller.handle(Key("ENTER"))  # Save
    controller.handle(Key("B"))
    controller.handle(Key("DOWN"))
    for char in "Ratings backwards":
        controller.handle(Key("SPACE" if char == " " else char))
    controller.handle(Key("F10"))
    saved = {letter: description
             for letter, description, _settings
             in indexing.saved_ranges(controller.database)}
    assert saved["B"] == "ratings backwards"
    assert controller.database.current_range.order == \
        indexing.ORDER_DESCENDING


def test_range_retrieve_default(tmp_path):
    path, _database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    open_browse(controller)
    controller.handle(Key("R"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Descending
    controller.handle(Key("E", alt=True))
    assert controller.records.order_indicator == "D"
    if controller.overlay is not None:
        controller.handle(Key("ENTER"))

    controller.handle(Key("R"))
    controller.handle(Key("F7"))
    picker = controller.range_session.picker
    picker.selected = picker.items.index("Default Range")
    controller.handle(Key("ENTER"))
    controller.handle(Key("E", alt=True))
    assert controller.records.order_indicator == "A"
