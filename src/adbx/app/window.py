"""Finestra principale: griglia di celle scalata alla finestra, tastiera, mouse."""

from __future__ import annotations

import sys

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
from ..config.display import (
    COMFORT_FONT_PX,
    ZOOM_DEFAULT,
    ZOOM_STEP,
    base_pixel_size,
    clamp_zoom,
    zoom_pixel_size,
)
from ..render.qt_renderer import MAX_PIXEL_SIZE, MIN_PIXEL_SIZE, CellRenderer
from ..screen.qt_input import key_from_qt
from ..shell.controller import ShellController

MIN_WIDTH = 660
MIN_HEIGHT = 420
BANNER_DELAY_MS = 4000


class ScreenWidget(QWidget):
    """Superficie di disegno: nessun widget figlio, solo celle."""

    def __init__(self, controller: ShellController, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.renderer = CellRenderer(pixel_size=16)
        self.blink_on = True
        self._applied_zoom = clamp_zoom(controller.screen_zoom)
        self._zoom_base: int | None = None
        self._initial_zoom_done = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._toggle_blink)
        self._timer.start(500)

    # -- scalabilita' ----------------------------------------------------
    def refit(self) -> None:
        """Corpo di riferimento al 100% e zoom esplicito sopra quel corpo."""
        dpr = self.devicePixelRatioF()
        zoom = self._zoom_percent()
        self.renderer.fit(
            self.width(), self.height(), SCREEN_WIDTH, SCREEN_HEIGHT, dpr,
            ceiling=COMFORT_FONT_PX * dpr, zoom=1.0)
        if self._zoom_base is None or zoom == ZOOM_DEFAULT:
            self._zoom_base = base_pixel_size(
                self.renderer.best_pixel_size,
                round(COMFORT_FONT_PX * dpr))
        target = max(MIN_PIXEL_SIZE,
                     min(MAX_PIXEL_SIZE,
                         zoom_pixel_size(self._zoom_base, zoom)))
        best = self.renderer.best_pixel_size
        limited = target > best
        if limited:
            target = best
        if target != self.renderer.pixel_size:
            self.renderer.use_natural_size(target, dpr)
            self.renderer.base_pixel_size = self._zoom_base
        self.renderer.zoom_limited = limited
        self._applied_zoom = zoom
        self._update_title()
        self.update()

    def _zoom_percent(self) -> int:
        return clamp_zoom(self.controller.screen_zoom)

    def _zoom_target_pixel_size(self, zoom: int) -> int:
        base = self._zoom_base or self.renderer.pixel_size
        return max(MIN_PIXEL_SIZE,
                   min(MAX_PIXEL_SIZE, zoom_pixel_size(base, zoom)))

    def _grow_window_for(self, pixel_size: int) -> None:
        """Allarga la finestra quanto serve per un corpo più grande."""
        window = self.window()
        current = self.renderer.pixel_size
        dpr = self.devicePixelRatioF()
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        if available is not None:
            # Corpo massimo ottenibile sullo schermo: oltre non ha senso
            # continuare ad allargare la finestra.
            self.renderer.fit(
                available.width(), available.height(), SCREEN_WIDTH,
                SCREEN_HEIGHT, dpr, ceiling=COMFORT_FONT_PX * dpr, zoom=1.0)
            best_screen = self.renderer.best_pixel_size
            if current >= best_screen:
                return
            pixel_size = min(pixel_size, best_screen)
        cell_w, cell_h = self.renderer.measure(pixel_size)
        chrome_w = max(0, window.width() - self.width())
        chrome_h = max(0, window.height() - self.height())
        width = round(cell_w * SCREEN_WIDTH) + chrome_w + 4
        height = round(cell_h * SCREEN_HEIGHT) + chrome_h + 4
        if available is not None:
            width = min(width, available.width())
            height = min(height, available.height())
        width = max(MIN_WIDTH, width)
        height = max(MIN_HEIGHT, height)
        if width > window.width() or height > window.height():
            window.resize(max(window.width(), width),
                          max(window.height(), height))

    def _update_title(self) -> None:
        zoom = self._zoom_percent()
        if zoom == ZOOM_DEFAULT:
            self.window().setWindowTitle("adbx")
            return
        suffix = " (max)" if self.renderer.zoom_limited else ""
        self.window().setWindowTitle(f"adbx — zoom {zoom}%{suffix}")

    def _zoom(self, delta: int) -> None:
        """Cambia il livello di zoom e lo salva; 0 ripristina il default."""
        current = self._zoom_percent()
        target = ZOOM_DEFAULT if delta == 0 else clamp_zoom(current + delta)
        if target != current:
            self.controller.set_screen_zoom(target)
        if target > current:
            self._grow_window_for(self._zoom_target_pixel_size(target))
        self.refit()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refit()
        if not self._initial_zoom_done:
            self._initial_zoom_done = True
            zoom = self._zoom_percent()
            if zoom != ZOOM_DEFAULT:
                self._grow_window_for(self._zoom_target_pixel_size(zoom))
                self.refit()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.refit()

    # -- disegno ---------------------------------------------------------
    def _toggle_blink(self) -> None:
        self.blink_on = not self.blink_on
        self.update()

    def _origin(self) -> tuple[float, float]:
        grid_w, grid_h = self.renderer.grid_size(SCREEN_WIDTH, SCREEN_HEIGHT)
        return max(0.0, (self.width() - grid_w) / 2), max(0.0, (self.height() - grid_h) / 2)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        try:
            background = QColor(*self.renderer.palette[self.controller.theme.bg])
            painter.fillRect(self.rect(), background)
            painter.translate(*self._origin())
            self.renderer.paint(painter, self.controller.view().buffer,
                                blink_on=self.blink_on)
        finally:
            painter.end()

    # -- input -----------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_F11:
            window = self.window()
            window.showNormal() if window.isFullScreen() else window.showFullScreen()
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._zoom(ZOOM_STEP)
                return
            if event.key() == Qt.Key.Key_Minus:
                self._zoom(-ZOOM_STEP)
                return
            if event.key() == Qt.Key.Key_0:
                self._zoom(0)
                return
        key = key_from_qt(event)
        if key is None:
            super().keyPressEvent(event)
            return
        self.controller.handle(key)
        if self.controller.quit:
            self.window().close()
            return
        if self._zoom_percent() != self._applied_zoom:
            self.refit()
        else:
            self.update()

    def _cell_at(self, position: QPoint) -> tuple[int, int]:
        origin_x, origin_y = self._origin()
        col = int((position.x() - origin_x) / self.renderer.cell_w)
        row = int((position.y() - origin_y) / self.renderer.cell_h)
        return row, col

    def mousePressEvent(self, event) -> None:  # noqa: N802
        row, col = self._cell_at(event.position().toPoint())
        button = "right" if event.button() == Qt.MouseButton.RightButton else "left"
        self.controller.click(row, col, button=button)
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        row, col = self._cell_at(event.position().toPoint())
        button = "right" if event.button() == Qt.MouseButton.RightButton else "left"
        self.controller.click(row, col, button=button, double=True)
        self.update()


class MainWindow(QMainWindow):
    def __init__(self, controller: ShellController | None = None) -> None:
        super().__init__()
        self.setWindowTitle("adbx")
        self.controller = controller or ShellController()
        self.setCentralWidget(ScreenWidget(self.controller, self))
        self.statusBar().hide()
        self._size_to_screen()
        if self.controller.base == "banner":
            QTimer.singleShot(BANNER_DELAY_MS, self._banner_continue)

    def _banner_continue(self) -> None:
        """Dopo la pausa il banner prosegue, come l'originale."""
        if self.controller.base != "banner":
            return
        self.controller.banner_continue()
        self.centralWidget().update()

    def _size_to_screen(self) -> None:
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        width, height = 1452, 903
        if available is not None:
            width = min(width, int(available.width() * 0.92))
            height = min(height, int(available.height() * 0.92))
        self.resize(max(MIN_WIDTH, width), max(MIN_HEIGHT, height))


def run(argv: list[str] | None = None, *, data: str | None = None,
        open_path: str | None = None, application: str | None = None) -> int:
    app = QApplication(sys.argv if argv is None else argv)
    controller = ShellController(data, open_path=open_path,
                                 application=application)
    window = MainWindow(controller)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
