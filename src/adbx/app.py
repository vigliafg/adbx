"""Finestra principale: griglia di celle scalata alla finestra, tastiera."""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from .cell.attrs import Color
from .cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, STATUS_ROW
from .render.qt_renderer import CellRenderer
from .screen.demo import build_demo_scene
from .screen.keys import format as format_key
from .screen.qt_input import key_from_qt

# Sotto questa dimensione la griglia non e' piu' leggibile.
MIN_WIDTH = 660
MIN_HEIGHT = 420


class ScreenWidget(QWidget):
    """Superficie di disegno: nessun widget figlio, solo celle."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.renderer = CellRenderer(pixel_size=16)
        self.scene = build_demo_scene()
        self.blink_on = True
        self.last_key = ""
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
            background = QColor(*self.renderer.palette[int(Color.BLUE)])
            painter.fillRect(self.rect(), background)
            painter.translate(*self._origin())
            self.renderer.paint(painter, self.scene.composite(), blink_on=self.blink_on)
        finally:
            painter.end()

    # -- tastiera --------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = key_from_qt(event)
        if key is None:
            super().keyPressEvent(event)
            return
        self.last_key = format_key(key)
        if key.name == "ESC":
            self.close()
            return
        if key.name == "F11":
            window = self.window()
            window.showNormal() if window.isFullScreen() else window.showFullScreen()
            return
        base = self.scene.get("base")
        if base is not None:
            base.buffer.write(STATUS_ROW, 60, f"Key {self.last_key:<16}", fg=0, bg=3)
        self.scene.remove("popup")
        self.update()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("adbx")
        self.setCentralWidget(ScreenWidget(self))
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


def run(argv: list[str] | None = None) -> int:
    app = QApplication(sys.argv if argv is None else argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
