from adbx.cell.buffer import Cell, CellBuffer
from adbx.screen.scene import Scene, centered, popup


def test_scene_composites_on_background():
    scene = Scene(10, 4, Cell(fg=7, bg=0))
    layer = CellBuffer(4, 1)
    layer.write(0, 0, "abcd", fg=15)
    scene.add("top", layer, row=1, col=2)
    out = scene.composite()
    assert out.text_of(1) == "  abcd"
    assert out.get(1, 2).fg == 15


def test_layers_are_ordered_and_replaceable():
    scene = Scene(6, 2)
    first = CellBuffer(2, 1)
    first.write(0, 0, "AA")
    second = CellBuffer(2, 1)
    second.write(0, 0, "BB")
    scene.add("x", first)
    scene.add("x", second)
    assert len(scene.layers) == 1
    assert scene.composite().text_of(0) == "BB"


def test_bring_to_front():
    scene = Scene(4, 1)
    a = CellBuffer(4, 1)
    a.write(0, 0, "1111")
    b = CellBuffer(4, 1)
    b.write(0, 0, "2222")
    scene.add("a", a)
    scene.add("b", b)
    assert scene.composite().text_of(0) == "2222"
    scene.bring_to_front("a")
    assert scene.composite().text_of(0) == "1111"


def test_layer_at_uses_topmost():
    scene = Scene(10, 5)
    scene.add("base", CellBuffer(10, 5))
    small = CellBuffer(4, 2)
    scene.add("popup", small, row=1, col=2)
    assert scene.layer_at(1, 2).name == "popup"
    assert scene.layer_at(0, 0).name == "base"
    assert scene.layer_at(20, 20) is None


def test_invisible_layer_is_skipped():
    scene = Scene(4, 1)
    hidden = CellBuffer(4, 1)
    hidden.write(0, 0, "ZZZZ")
    layer = scene.add("h", hidden)
    layer.visible = False
    assert scene.composite().to_lines()[0] == "    "


def test_popup_has_box_title_and_shadow():
    box = popup(20, 5, title="Test")
    assert box.get(0, 0).ch == "┌"
    assert box.get(0, 19).ch == "┐"
    assert box.get(4, 0).ch == "└"
    assert box.get(4, 19).ch == "┘"
    assert "Test" in box.text_of(0)
    assert box.get(5, 19).ch == "░"
    assert box.get(4, 20).ch == "░"


def test_popup_without_shadow_has_exact_size():
    box = popup(10, 4, shadow=False)
    assert (box.width, box.height) == (10, 4)


def test_popup_minimum_size():
    box = popup(1, 1)
    assert box.width >= 4 and box.height >= 3


def test_centered():
    assert centered(80, 25, 20, 5) == (10, 30)
    assert centered(80, 25, 20, 5, top=2) == (2, 30)
