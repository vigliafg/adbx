"""Finestra principale: ospita la griglia di celle e la tastiera."""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from .cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH
from .cell.font import BitmapFont
from .render.qt_renderer import CellRenderer
from .screen.demo import build_demo_scene
from .screen.keys import format as format_key
from .screen.qt_input import key_from_qt


class ScreenWidget(QWidget):
    """Superficie di disegno: nessun widget figlio, solo celle."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.renderer = CellRenderer(BitmapFont.load_default(), scale=2)
        self.scene = build_demo_scene()
        self.blink_on = True
        self.last_key = ""
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(SCREEN_WIDTH * self.renderer.cell_w,
                            SCREEN_HEIGHT * self.renderer.cell_h)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._toggle_blink)
        self._timer.start(500)

    def _toggle_blink(self) -> None:
        self.blink_on = not self.blink_on
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor(0, 0, 0))
            self.renderer.paint(painter, self.scene.composite(), blink_on=self.blink_on)
        finally:
            painter.end()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = key_from_qt(event)
        if key is None:
            super().keyPressEvent(event)
            return
        self.last_key = format_key(key)
        scene = self.scene
        if key.name == "ESC":
            self.close()
            return
        base = scene.get("base")
        if base is not None:
            base.buffer.write(22, 1, f"Key {self.last_key:<16}", fg=0, bg=3)
        scene.remove("popup")
        self.update()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("adbx")
        self.setCentralWidget(ScreenWidget(self))
        self.statusBar().hide()


def run(argv: list[str] | None = None) -> int:
    app = QApplication(sys.argv if argv is None else argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
