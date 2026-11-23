"""Finestra principale: griglia di celle scalata alla finestra, tastiera, mouse."""

from __future__ import annotations

import sys

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from .cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
from .render.qt_renderer import CellRenderer
from .screen.qt_input import key_from_qt
from .shell.controller import ShellController

MIN_WIDTH = 660
MIN_HEIGHT = 420


class ScreenWidget(QWidget):
    """Superficie di disegno: nessun widget figlio, solo celle."""

    def __init__(self, controller: ShellController, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.renderer = CellRenderer(pixel_size=16)
        self.blink_on = True
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._toggle_blink)
        self._timer.start(500)

    # -- scalabilita' ----------------------------------------------------
    def refit(self) -> None:
        """Sceglie il corpo del font piu' grande che riempie la finestra."""
        dpr = self.devicePixelRatioF()
        self.renderer.fit(self.width(), self.height(), SCREEN_WIDTH, SCREEN_HEIGHT, dpr)
        self.update()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
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
        key = key_from_qt(event)
        if key is None:
            super().keyPressEvent(event)
            return
        self.controller.handle(key)
        if self.controller.quit:
            self.window().close()
            return
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

    def _size_to_screen(self) -> None:
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        width, height = 1452, 903
        if available is not None:
            width = min(width, int(available.width() * 0.92))
            height = min(height, int(available.height() * 0.92))
        self.resize(max(MIN_WIDTH, width), max(MIN_HEIGHT, height))


def run(argv: list[str] | None = None, *, data: str | None = None,
        open_path: str | None = None) -> int:
    app = QApplication(sys.argv if argv is None else argv)
    controller = ShellController(data, open_path=open_path)
    window = MainWindow(controller)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
