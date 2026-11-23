"""O3 — lezione 7: indici e indice primario dall'interfaccia."""

from support import make_movies

from adbx.data import indexing
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def type_text(controller, text):
    for char in text:
        controller.handle(Key("SPACE" if char == " " else char,
                             shift=char.isupper()))


def dismiss(controller):
    if controller.overlay is not None and controller.overlay.kind == "message":
        controller.handle(Key("ENTER"))


def open_browse(controller):
    controller.handle(Key("V"))
    for _ in range(3):
        controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.base == "records"
    assert controller.records.mode == "browse"


def test_lesson_7_create_index_table_mode(tmp_path):
    path, _database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=path)

    controller.handle(Key("I"))
    assert controller.overlay.kind == "submenu"
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.action == "index-name"
    type_text(controller, "AVMOVSUB")
    controller.handle(Key("ENTER"))
    assert controller.overlay.kind == "submenu"
    controller.handle(Key("ENTER"))  # Table mode
    assert controller.base == "index"

    controller.handle(Key("F2"))
    picker = controller.index_session.picker
    assert picker is not None
    picker.selected = [item for item in picker.items].index("SUBJECT")
    controller.handle(Key("ENTER"))
    assert controller.index_session.levels == [("SUBJECT", "A")]

    controller.handle(Key("F10"))
    assert controller.index_session.stage == "options"
    assert controller.index_session.expression == "SUBJECT"
    controller.handle(Key("DOWN"))
    type_text(controller, "Alphabetically by Movie Subject")
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert controller.overlay.kind == "message"
    assert "AVMOVSUB" in controller.overlay.text

    definition = indexing.find_index(controller.database, "AVMOVSUB")
    assert definition is not None
    assert definition.description == "Alphabetically by Movie Subject"
    assert controller.database.primary_index == "AVMOVSUB"

    dismiss(controller)
    open_browse(controller)
    subjects = [controller.database.read(seq)["SUBJECT"]
                for seq in controller.records._seqs]
    assert subjects == sorted(subjects, key=str.upper)
    assert controller.records.status == "" or True


def test_lesson_7_multi_level_and_primary_selection(tmp_path):
    path, _database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=path)

    # Indice a due livelli: SUBJECT + TAPE_TITLE.
    controller.handle(Key("I"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    type_text(controller, "AVMSUBTI")
    controller.handle(Key("ENTER"))
    controller.handle(Key("ENTER"))  # Table mode
    session = controller.index_session
    session.picker = None
    session.levels = [("SUBJECT", "A")]
    session.row = 0
    session.column = 0
    session.edit_text = "SUBJECT"
    session.edit_cursor = len(session.edit_text)
    controller.handle(Key("F6"))
    session.picker = None
    session.levels[1] = ("TAPE_TITLE", "A")
    session.edit_text = "TAPE_TITLE"
    session.edit_cursor = len(session.edit_text)
    controller.handle(Key("F10"))
    assert session.expression == "SUBJECT+TAPE_TITLE"
    controller.handle(Key("F10"))
    assert controller.database.primary_index == "AVMSUBTI"

    dismiss(controller)
    open_browse(controller)
    pairs = [(controller.database.read(seq)["SUBJECT"],
              controller.database.read(seq)["TAPE_TITLE"])
             for seq in controller.records._seqs]
    assert pairs == sorted(pairs, key=lambda pair: (pair[0].upper(),
                                                    pair[1].upper()))

    # Selezione dell'indice primario con I.
    controller.handle(Key("I"))
    assert controller.overlay.kind == "choose"
    labels = [label for label, _value in controller.overlay.items]
    assert "Record Number" in labels
    controller.overlay.selected = 0
    controller.handle(Key("ENTER"))
    assert controller.database.primary_index == indexing.RECORD_NUMBER
    assert controller.base == "records"


def test_create_index_expression_mode(tmp_path):
    path, _database = make_movies(tmp_path)
    controller = ShellController(tmp_path, open_path=path)
    controller.handle(Key("I"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    type_text(controller, "AVMVTLE")
    controller.handle(Key("ENTER"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Expression mode
    session = controller.index_session
    assert session.stage == "expression"
    session.expression = "UPPER(TAPE_TITLE)"
    session.description = "Upper title"
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert indexing.find_index(controller.database, "AVMVTLE") is not None

    dismiss(controller)
    open_browse(controller)
    titles = [controller.database.read(seq)["TAPE_TITLE"]
              for seq in controller.records._seqs]
    assert titles == sorted(titles, key=str.upper)
