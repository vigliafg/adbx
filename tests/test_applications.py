"""O11 — modello, store, runtime e protezioni delle applicazioni."""

from adbx.app.model import (
    AppItem,
    Application,
    AppMenu,
    BannerScreen,
    check_password,
    hot_letter,
    outline,
    password_hash,
)
from adbx.app.protection import (
    PROTECTION_TYPES,
    is_protected,
    protected_types,
    set_protection,
    toggle_protection,
)
from adbx.app.runtime import ApplicationRuntime
from adbx.app.store import ApplicationStore
from adbx.data.fields import Field
from adbx.data.workspace import Workspace


def make_app(name="DEMO"):
    return Application(name, description="Demo application",
                       menu=AppMenu(title="MAIN", items=[
                           AppItem("Customers", action="Sub-Menu",
                                   submenu=AppMenu(title="CUSTOMERS", items=[
                                       AppItem("Enter", action="Macro",
                                               macro="{SET %X,1}")])),
                           AppItem("Print", action="Macro",
                                   macro='{WRITE 1,1,"print"}'),
                       ]))


def test_application_outline_and_hotkeys():
    app = make_app()
    rows = outline(app)
    assert [row.text for row in rows] == [
        "= MAIN", "Customers", "= CUSTOMERS", "Enter", "Print"]
    assert hot_letter("Print reports") == "P"
    assert app.menu.item_by_hotkey("P").text == "Print"
    app.validate()


def test_application_passwords_are_case_insensitive():
    stored = password_hash("Secret")
    assert check_password(stored, "secret")
    assert not check_password(stored, "wrong")
    item = AppItem("Hidden", password_hash=stored)
    assert item.password_protected


def test_store_roundtrip(tmp_path):
    store = ApplicationStore(tmp_path / "apps")
    app = make_app()
    app.banner.put(0, 0, "H", 15, 1)
    store.save(app)
    assert store.names() == ["DEMO"]
    restored = store.get("DEMO")
    assert restored.menu.items[0].text == "Customers"
    assert restored.menu.items[0].submenu.title == "CUSTOMERS"
    assert restored.banner.text(0, 0) == "H"
    assert store.delete("DEMO")
    assert not store.delete("DEMO")


def test_runtime_navigation_and_submenu():
    store = ApplicationStore("/tmp/opencode/not-used")
    app = make_app()
    runtime = ApplicationRuntime(app, store)
    assert runtime.menu.title == "MAIN"
    runtime.move(1)
    assert runtime.item.text == "Print"
    runtime.move(-1)
    request = runtime.activate()
    assert request == "submenu"
    assert runtime.menu.title == "CUSTOMERS"
    assert runtime.nested == 1
    runtime.back()
    assert runtime.menu.title == "MAIN"


def test_runtime_macro_and_flow():
    store = ApplicationStore("/tmp/opencode/not-used")
    app = make_app()
    app.menu.flow = "Advance"
    runtime = ApplicationRuntime(app, store)
    runtime.index = 1
    assert runtime.activate() == "macro"
    assert runtime.requested_item.text == "Print"
    runtime.after_action()
    assert runtime.index == 1
    app.menu.flow = "Return"
    runtime.frames.append(type(runtime.frames[0])(runtime.menu))
    runtime.frames[-1].menu = app.menu.items[0].submenu
    runtime.after_action()
    assert runtime.nested == 0


def test_runtime_password_request():
    store = ApplicationStore("/tmp/opencode/not-used")
    app = make_app()
    app.menu.items[0].password_hash = password_hash("open")
    runtime = ApplicationRuntime(app, store)
    assert runtime.activate() == "password"
    assert runtime.provide_password("wrong") == ""
    assert runtime.status == "Incorrect password."
    assert runtime.activate() == "password"
    assert runtime.provide_password("OPEN") == "submenu"


def test_runtime_call_and_goto(tmp_path):
    store = ApplicationStore(tmp_path / "apps")
    store.save(make_app("MAIN"))
    store.save(make_app("OTHER"))
    runtime = ApplicationRuntime(store.get("MAIN"), store)
    assert runtime.call("OTHER")
    assert runtime.app.name == "OTHER"
    assert runtime.call_stack
    assert runtime.return_from_call()
    assert runtime.app.name == "MAIN"
    assert runtime.go_to("OTHER")
    assert runtime.app.name == "OTHER"
    assert not runtime.call_stack


def test_runtime_escape_policies():
    store = ApplicationStore("/tmp/opencode/not-used")
    app = make_app()
    runtime = ApplicationRuntime(app, store)
    assert runtime.back() == "exit"
    app.allow_escape = "No"
    runtime = ApplicationRuntime(app, store)
    assert runtime.back() == ""
    assert "disabled" in runtime.status
    app.allow_escape = "Password"
    app.escape_password_hash = password_hash("esc")
    runtime = ApplicationRuntime(app, store)
    assert runtime.back() == "escape-password"
    assert runtime.escape_password("wrong") is False
    assert runtime.escape_password("esc") is True
    assert runtime.request == "exit"


def test_runtime_simulation_does_not_run_macro():
    store = ApplicationStore("/tmp/opencode/not-used")
    runtime = ApplicationRuntime(make_app(), store, simulate=True)
    runtime.index = 1
    assert runtime.activate() == ""
    assert "Simulation" in runtime.status


def test_protection_roundtrip(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create_database("DEMO", [Field("NAME", "C", 5)])
    assert not is_protected(workspace, "DEMO", "Reports")
    assert toggle_protection(workspace, "DEMO", "Reports")
    assert is_protected(workspace, "DEMO", "Reports")
    assert protected_types(workspace, "DEMO") == {"Reports"}
    set_protection(workspace, "DEMO", "Reports", False)
    assert not is_protected(workspace, "DEMO", "Reports")
    assert set(PROTECTION_TYPES) >= {"Forms", "Reports", "Letters"}
    workspace.close()


def test_banner_screen_colors():
    banner = BannerScreen()
    banner.put(2, 3, "A", 12, 4)
    assert banner.text(2, 3) == "A"
    assert banner.cell_colors(2, 3) == (12, 4)
    assert banner.enabled
