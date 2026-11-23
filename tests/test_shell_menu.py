from adbx.cell.buffer import HELP_ROW
from adbx.screen.keys import Key
from adbx.shell import screens
from adbx.shell.controller import demo_controller
from adbx.shell.state import demo_state


def _lines(view) -> str:
    return "\n".join(view.buffer.to_lines())


def test_all_commands_and_status_box():
    view = screens.main_menu(demo_state())
    text = _lines(view)
    for label, _topic in screens.COMMANDS:
        assert label in text, label
    assert "Alpha Four Main Menu" in text
    assert "Records in database" in text
    assert " 50" in text
    assert "Current database" in text
    assert "AVMOVIES" in text
    assert "by Record Number" in text


def test_help_line_follows_selection():
    first = screens.main_menu(demo_state(), selected=0)
    third = screens.main_menu(demo_state(), selected=2)
    assert "View, change, enter or delete records" in first.buffer.text_of(HELP_ROW)
    assert "Search and/or sort" in third.buffer.text_of(HELP_ROW)


def test_selected_command_is_reversed():
    view = screens.main_menu(demo_state(), selected=0)
    text = view.buffer.to_lines()
    # La riga selezionata ha celle con sfondo nero.
    row = next(row for row, line in enumerate(text) if "View/enter records" in line)
    col = text[row].index("View/enter records")
    assert view.buffer.get(row, col).bg == 0


def test_controller_navigation_and_notice():
    controller = demo_controller()
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    assert controller.menu_index == 2
    controller.handle(Key("ENTER"))
    assert controller.overlay is not None and controller.overlay.kind == "message"
    assert "wave O3" in controller.overlay.text
    controller.handle(Key("ESC"))
    assert controller.overlay is None


def test_hot_key_opens_submenu():
    controller = demo_controller()
    controller.handle(Key("C"))
    assert controller.overlay is not None
    assert controller.overlay.kind == "submenu"
    assert "Open a database" in _lines(controller.view())


def test_quit_sets_flag():
    controller = demo_controller()
    controller.handle(Key("Q"))
    assert controller.quit


def test_f1_opens_context_help_and_esc_closes():
    controller = demo_controller()
    controller.handle(Key("F1"))
    assert controller.overlay is not None
    assert controller.overlay.kind == "help"
    assert controller.overlay.topic_id == "view"
    assert "View/enter records" in _lines(controller.view())
    controller.handle(Key("ESC"))
    assert controller.overlay is None


def test_f2_and_f3_screens():
    controller = demo_controller()
    controller.handle(Key("F2"))
    assert controller.base == "structure"
    assert "TAPE_ID" in _lines(controller.view())
    controller.handle(Key("F10"))
    assert controller.base == "menu"
    controller.handle(Key("F3"))
    assert controller.base == "status"
    assert "AVMOVIES" in _lines(controller.view())


def test_mouse_selects_and_double_click_executes():
    controller = demo_controller()
    view = controller.view()
    region = next(region for region in view.regions if region.action == "menu:5")
    controller.click(region.row, region.col, double=False)
    assert controller.menu_index == 5
    controller.click(region.row, region.col, double=True)
    assert controller.overlay is not None
    assert controller.overlay.kind == "submenu"


def test_menu_line_is_clickable():
    controller = demo_controller()
    view = controller.view()
    region = next(region for region in view.regions if region.action == "key:F1")
    controller.click(region.row, region.col)
    assert controller.overlay is not None
    assert controller.overlay.kind == "help"
