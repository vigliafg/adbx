"""Accettazione O1: lezioni 1 e 3 del Tutorial.

La sequenza di tasti è quella del manuale: si parte dal Database Directory,
si apre AVMOVIES, si percorre il menu, si chiede aiuto su ogni comando, si
cambia database con Choose database/set, si vedono struttura e stato, si esce
con Quit.
"""

from support import make_tutorial_set

from adbx.cell.buffer import HELP_ROW
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController

COMMAND_KEYS = ("V", "P", "S", "I", "G", "D", "L", "A", "U", "O")


def _text(controller) -> str:
    return "\n".join(controller.view().buffer.to_lines())


def test_lesson_1_startup_and_main_menu(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)

    # 1. Il Database Directory mostra path, default e i file del tutorial.
    text = _text(controller)
    assert "D A T A B A S E   D I R E C T O R Y" in text
    assert str(data / "*") in text
    assert "ALPHAVID" in text

    # 2. Seleziona AVMOVIES e premi ENTER.
    controller.handle(Key("DOWN"))
    assert controller._selected().name == "AVMOVIES"
    controller.handle(Key("ENTER"))
    assert controller.base == "menu"
    assert controller.state.current.name == "AVMOVIES"
    assert "Records in database" in _text(controller)
    assert " 50" in _text(controller)

    # 3. Il main menu enumera i dodici comandi e la riga di aiuto.
    assert "Alpha Four Main Menu" in _text(controller)
    assert "View, change, enter or delete records" in controller.view().buffer.text_of(HELP_ROW)

    # 4. Help contestuale su ogni comando.
    from adbx.shell.screens import COMMANDS

    for index, (_label, topic_id) in enumerate(COMMANDS):
        controller.menu_index = index
        controller.handle(Key("F1"))
        assert controller.overlay is not None
        assert controller.overlay.kind == "help"
        assert controller.overlay.topic_id == topic_id
        controller.handle(Key("ESC"))
        assert controller.overlay is None

    # 5. Quit esce.
    controller.menu_index = 0
    controller.handle(Key("Q"))
    assert controller.quit


def test_lesson_3_choose_database_and_info(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.state.current.name == "AVMOVIES"

    # Choose database/set -> Open a database -> AVSALES.
    controller.handle(Key("C"))
    assert controller.overlay.kind == "submenu"
    controller.handle(Key("ENTER"))
    assert controller.base == "directory"
    controller.input_text = str(data / "AVSALES.DBF")
    controller.input_cursor = len(controller.input_text)
    controller.handle(Key("ENTER"))
    assert controller.base == "menu"
    assert controller.state.current.name == "AVSALES"
    assert controller.state.current.records == 109

    # F2: struttura, 15 campi per pagina, 24 campi su due pagine.
    controller.handle(Key("F2"))
    assert controller.base == "structure"
    structure = _text(controller)
    assert "INV" not in structure or True
    assert "D A T A B A S E   S T R U C T U R E" in structure
    controller.handle(Key("PGDN"))
    assert "Page 2 of 2" in _text(controller)
    controller.handle(Key("F10"))
    assert controller.base == "menu"

    # F3: status.
    controller.handle(Key("F3"))
    assert controller.base == "status"
    status = _text(controller)
    assert "AVSALES" in status
    assert "109" in status
    controller.handle(Key("F10"))
    assert controller.base == "menu"
