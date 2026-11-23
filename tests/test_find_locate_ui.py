"""O3 — lezione 8: Find, Locate, sostituzione e duplicati."""

from support import make_movies

from adbx.data import indexing
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def type_text(controller, text):
    for char in text:
        controller.handle(Key("SPACE" if char == " " else char,
                             shift=char.isupper()))


def open_mode(controller, down=3):
    controller.handle(Key("V"))
    for _ in range(down):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.base == "records"


def title_of(controller, seq):
    return controller.database.read(seq)["TAPE_TITLE"]


def test_find_uses_primary_index(tmp_path):
    path, _database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    indexing.save_index(controller.database, indexing.IndexDefinition(
        "AVMOVTLE", "TAPE_TITLE", "Alphabetically by Title"))
    controller.database.set_primary_index("AVMOVTLE")
    open_mode(controller, down=3)

    controller.handle(Key("F"))
    assert controller.overlay.kind == "prompt"
    assert "Alphabetically by Title" in controller.overlay.text
    type_text(controller, "Benji")
    controller.handle(Key("ENTER"))
    assert title_of(controller, controller.records.current_seq) == "Benji"

    # La ricerca parziale trova il primo titolo che inizia con le lettere.
    controller.handle(Key("F"))
    type_text(controller, "Moon")
    controller.handle(Key("ENTER"))
    assert title_of(controller, controller.records.current_seq) == "Moonstruck"

    # Una chiave assente porta al record più vicino, non a un errore.
    controller.handle(Key("F"))
    type_text(controller, "Zzz")
    controller.handle(Key("ENTER"))
    assert "closest" in controller.records.status.lower()


def test_locate_in_field_and_memo(tmp_path):
    path, _database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    open_mode(controller, down=3)

    controller.handle(Key("L"))
    type_text(controller, "Bunny")
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "fields"
    controller.handle(Key("F10"))
    seq = controller.records.current_seq
    assert "Bunny" in title_of(controller, seq)
    assert "Locate" in controller.records.status
    controller.handle(Key("ESC"))
    assert controller.records.locate is None

    # Locate nei memo: F4 seleziona anche i campi memo.
    controller.handle(Key("L"))
    type_text(controller, "bone-chilling")
    controller.handle(Key("ENTER"))
    controller.handle(Key("F4"))
    controller.handle(Key("F10"))
    seq = controller.records.current_seq
    assert "Bone-chilling" in controller.database.read(seq)["TAPE_DESC"]
    assert "Memo" in controller.records.status


def test_search_and_replace_in_view(tmp_path):
    path, _database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    open_mode(controller, down=0)
    assert controller.records.mode == "view"

    controller.handle(Key("S"))
    type_text(controller, "Dumbo")
    controller.handle(Key("ENTER"))
    assert controller.overlay.action == "replace-with"
    type_text(controller, "Dumbo 2")
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "fields"
    controller.handle(Key("F10"))
    assert controller.overlay.kind == "confirm"
    controller.handle(Key("ENTER"))
    assert controller.overlay is not None
    assert "Replaced 1" in controller.overlay.text
    assert any(controller.database.read(seq)["TAPE_TITLE"] == "Dumbo 2"
               for seq in controller.database.sequences())


def test_delete_duplicate_records(tmp_path):
    path, _database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    indexing.save_index(controller.database, indexing.IndexDefinition(
        "AVSUBJ", "SUBJECT"))
    controller.database.set_primary_index("AVSUBJ")
    before = controller.database.count(include_deleted=True)

    controller.handle(Key("G"))
    assert controller.overlay.kind == "submenu"
    controller.handle(Key("DOWN"))
    for _ in range(3):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "message"
    assert "duplicate" in controller.overlay.text
    assert controller.database.count(include_deleted=True) == before
    assert controller.database.count() < before
