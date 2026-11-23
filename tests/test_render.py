import os
import sys

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtGui import QGuiApplication

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    return app


def test_renderer_size_and_image(qapp):
    from adbx.render.qt_renderer import CellRenderer
    from adbx.screen.demo import demo_buffer

    renderer = CellRenderer(scale=2)
    buffer = demo_buffer(show_popup=False)
    width, height = renderer.size(buffer)
    assert (width, height) == (80 * 16, 25 * 32)

    image = renderer.to_image(buffer)
    assert not image.isNull()
    assert (image.width(), image.height()) == (width, height)


def test_rendering_produces_lit_pixels(qapp):
    from adbx.cell.buffer import CellBuffer
    from adbx.render.qt_renderer import CellRenderer

    buffer = CellBuffer(4, 1)
    buffer.write(0, 0, "BBBB", fg=15, bg=0)
    image = CellRenderer(scale=1).to_image(buffer)
    lit = sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).value() > 40
    )
    assert lit > 20


def test_blink_phase_hides_glyph(qapp):
    from adbx.cell.buffer import CellBuffer
    from adbx.render.qt_renderer import CellRenderer

    buffer = CellBuffer(2, 1)
    buffer.write(0, 0, "B", fg=15, bg=0, blink=True)
    renderer = CellRenderer(scale=1)
    visible = renderer.to_image(buffer, blink_on=True)
    hidden = renderer.to_image(buffer, blink_on=False)

    def lit(image):
        return sum(
            1
            for y in range(image.height())
            for x in range(image.width())
            if image.pixelColor(x, y).value() > 40
        )

    assert lit(visible) > lit(hidden)
