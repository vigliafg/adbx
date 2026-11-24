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
    from adbx.cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
    from adbx.render.qt_renderer import CellRenderer
    from adbx.shell import screens
    from adbx.shell.state import demo_state

    renderer = CellRenderer(pixel_size=16)
    renderer.use_natural_size(16)
    view = screens.main_menu(demo_state())
    buffer = view.buffer
    width, height = renderer.size(buffer)
    assert width > 0 and height > 0

    image = renderer.to_image(buffer)
    assert not image.isNull()
    assert (image.width(), image.height()) == (buffer.width * round(renderer.cell_w),
                                               buffer.height * round(renderer.cell_h))


def test_rendering_produces_lit_pixels(qapp):
    from adbx.cell.buffer import CellBuffer
    from adbx.cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
    from adbx.render.qt_renderer import CellRenderer

    buffer = CellBuffer(4, 1)
    buffer.write(0, 0, "BBBB", fg=15, bg=0)
    renderer = CellRenderer(pixel_size=18)
    renderer.use_natural_size(18)
    image = renderer.to_image(buffer)
    lit = sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).value() > 40
    )
    assert lit > 20


def test_blink_phase_hides_glyph(qapp):
    from adbx.cell.buffer import CellBuffer
    from adbx.cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
    from adbx.render.qt_renderer import CellRenderer

    buffer = CellBuffer(2, 1)
    buffer.write(0, 0, "B", fg=15, bg=0, blink=True)
    renderer = CellRenderer(pixel_size=18)
    renderer.use_natural_size(18)
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


def test_underline_is_drawn(qapp):
    from adbx.cell.buffer import CellBuffer
    from adbx.cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
    from adbx.render.qt_renderer import CellRenderer

    plain = CellBuffer(6, 1)
    plain.write(0, 0, "TOKEN", fg=0, bg=7)
    underlined = CellBuffer(6, 1)
    underlined.write(0, 0, "TOKEN", fg=0, bg=7, underline=True)
    renderer = CellRenderer(pixel_size=20)
    renderer.use_natural_size(20)

    def dark(image):
        return sum(
            1
            for y in range(image.height())
            for x in range(image.width())
            if image.pixelColor(x, y).value() < 80
        )

    assert dark(renderer.to_image(underlined)) > dark(renderer.to_image(plain))


def test_fit_scales_with_window(qapp):
    from adbx.cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
    from adbx.render.qt_renderer import CellRenderer

    renderer = CellRenderer(pixel_size=12)
    renderer.fit(900, 600, SCREEN_WIDTH, SCREEN_HEIGHT)
    small = renderer.pixel_size
    small_w, small_h = renderer.grid_size(SCREEN_WIDTH, SCREEN_HEIGHT)
    assert small_w <= 900 and small_h <= 600

    renderer.fit(1800, 1200, SCREEN_WIDTH, SCREEN_HEIGHT)
    assert renderer.pixel_size >= small
    big_w, big_h = renderer.grid_size(SCREEN_WIDTH, SCREEN_HEIGHT)
    assert big_w <= 1800 and big_h <= 1200
    assert big_w > small_w and big_h > small_h


def test_fit_ceiling_leaves_margins(qapp):
    from adbx.cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
    from adbx.render.qt_renderer import CellRenderer

    renderer = CellRenderer(pixel_size=12)
    renderer.fit(3000, 2000, SCREEN_WIDTH, SCREEN_HEIGHT, ceiling=24)
    assert renderer.pixel_size == 24
    assert not renderer.zoom_limited
    width, height = renderer.grid_size(SCREEN_WIDTH, SCREEN_HEIGHT)
    assert width < 3000 and height < 2000


def test_fit_zoom_uses_slack_but_never_overflows(qapp):
    from adbx.cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
    from adbx.render.qt_renderer import CellRenderer

    renderer = CellRenderer(pixel_size=12)
    renderer.fit(3000, 2000, SCREEN_WIDTH, SCREEN_HEIGHT, ceiling=24, zoom=1.5)
    assert renderer.pixel_size > 24
    width, height = renderer.grid_size(SCREEN_WIDTH, SCREEN_HEIGHT)
    assert width <= 3000 and height <= 2000

    # Finestra che riempie esattamente la griglia al tetto di leggibilita':
    # lo zoom 150% non puo' crescere, lo zoom 50% si'.
    renderer.fit(3000, 2000, SCREEN_WIDTH, SCREEN_HEIGHT, ceiling=24)
    fit_w, fit_h = renderer.grid_size(SCREEN_WIDTH, SCREEN_HEIGHT)
    renderer.fit(fit_w, fit_h, SCREEN_WIDTH, SCREEN_HEIGHT, ceiling=24)
    base = renderer.pixel_size
    renderer.fit(fit_w, fit_h, SCREEN_WIDTH, SCREEN_HEIGHT, ceiling=24, zoom=1.5)
    assert renderer.pixel_size == base
    assert renderer.zoom_limited

    renderer.fit(fit_w, fit_h, SCREEN_WIDTH, SCREEN_HEIGHT, ceiling=24, zoom=0.5)
    assert renderer.pixel_size < base
    assert not renderer.zoom_limited


def test_cells_come_from_font_metrics(qapp):
    from adbx.cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
    from adbx.render.qt_renderer import CellRenderer

    renderer = CellRenderer(pixel_size=20)
    renderer.use_natural_size(20)
    assert renderer.advance > 0
    assert renderer.line_height == renderer.ascent + renderer.descent
    assert renderer.cell_w == pytest.approx(renderer.advance)
    assert renderer.cell_h == pytest.approx(renderer.line_height)


def test_geometric_line_is_continuous(qapp):
    from adbx.cell.buffer import CellBuffer
    from adbx.cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
    from adbx.render.qt_renderer import CellRenderer

    buffer = CellBuffer(1, 4)
    for row in range(4):
        buffer.write(row, 0, "│", fg=15, bg=0)
    renderer = CellRenderer(pixel_size=20)
    renderer.use_natural_size(20)
    image = renderer.to_image(buffer)
    boundary = round(renderer.cell_h)
    for y in (boundary - 1, boundary, boundary + 1):
        row_lit = [
            x for x in range(image.width())
            if image.pixelColor(x, y).value() > 40
        ]
        assert row_lit, f"riga {y} vuota sulla giunzione"
