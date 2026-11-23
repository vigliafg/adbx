from support import make_tutorial_set

from adbx.cell.buffer import HELP_ROW
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def _lines(controller) -> str:
    return "\n".join(controller.view().buffer.to_lines())


def test_startup_shows_directory_with_files(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    assert controller.base == "directory"
    text = _lines(controller)
    for name in ("ALPHAVID", "AVMOVIES", "AVSALES"):
        assert name in text
    assert "D A T A B A S E   D I R E C T O R Y" in text
    assert str(data) in text
    assert "*.SET, *.DBF" in text
    assert "Enter name of the database/set" in text_of(controller)


def text_of(controller):
    return controller.view().buffer.text_of(HELP_ROW)


def test_cursor_starts_on_first_file_and_moves(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    assert controller._selected().name == "ALPHAVID"
    controller.handle(Key("DOWN"))
    assert controller._selected().name == "AVMOVIES"
    assert controller.input_text.endswith("AVMOVIES.DBF")
    assert controller.input_cursor == len(controller.input_text)


def test_typing_edits_input_text(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    controller.input_text = ""
    controller.input_cursor = 0
    for name in ("S", "T", "A", "R"):
        controller.handle(Key(name))
    assert controller.input_text == "STAR"
    controller.handle(Key("BACKSPACE"))
    assert controller.input_text == "STA"


def test_wildcard_filter(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    controller.input_text = "AVS*"
    controller.input_cursor = 4
    controller.handle(Key("ENTER"))
    names = [entry.name for entry in controller.state.listing.entries if entry.is_file]
    assert names == ["AVSALES", "AVSALES2"]
    assert "AVS*" in _lines(controller)


def test_enter_opens_database_and_shows_main_menu(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    controller.handle(Key("DOWN"))  # AVMOVIES
    controller.handle(Key("ENTER"))
    assert controller.base == "menu"
    assert controller.state.current.name == "AVMOVIES"
    assert controller.state.current.records == 50
    text = _lines(controller)
    assert "Alpha Four Main Menu" in text
    assert " 50" in text


def test_detail_toggle_adds_columns(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    assert "Records" not in controller.view().buffer.to_lines()[5]
    controller.handle(Key("F8"))
    header = controller.view().buffer.to_lines()[5]
    assert "Records" in header and "Fields" in header


def test_refresh_finds_new_file(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    assert "NEWFILE" not in _lines(controller)
    from support import write_dbf

    write_dbf(data / "NEWFILE.DBF", records=3)
    controller.handle(Key("F6"))
    assert "NEWFILE" in _lines(controller)


def test_history_popup_and_reopen(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.base == "menu"
    controller.handle(Key("C"))
    controller.handle(Key("ENTER"))  # Open a database
    assert controller.base == "directory"
    controller.handle(Key("F4"))
    assert controller.overlay is not None and controller.overlay.kind == "history"
    assert "AVMOVIES" in _lines(controller)
    controller.handle(Key("ENTER"))
    assert controller.base == "menu"


def test_escape_returns_to_menu_only_when_a_database_is_open(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    controller.handle(Key("ESC"))
    assert controller.base == "directory"
    assert controller.overlay is not None  # messaggio "select a database"
    controller.handle(Key("ESC"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("C"))
    controller.handle(Key("ENTER"))
    assert controller.base == "directory"
    controller.handle(Key("ESC"))
    assert controller.base == "menu"


def test_parent_entry_changes_directory(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    controller._move_to(0)
    assert controller._selected().name == "<Parent>"
    controller.handle(Key("ENTER"))
    assert controller.state.root == tmp_path.resolve()


def test_mouse_click_and_double_click(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    view = controller.view()
    region = next(region for region in view.regions if region.action == "dir:2")
    controller.click(region.row, region.col)
    assert controller._selected().name == "AVMOVIES"
    controller.click(region.row, region.col, double=True)
    assert controller.base == "menu"
    assert controller.state.current.name == "AVMOVIES"


def test_right_click_cancels(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("C"))
    controller.handle(Key("ENTER"))
    controller.click(0, 0, button="right")
    assert controller.base == "menu"


def test_unavailable_commands_explain_the_wave(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    controller = ShellController(data)
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("V"))
    assert controller.overlay.kind == "message"
    assert "wave O2" in controller.overlay.text
