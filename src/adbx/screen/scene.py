"""Scene: composizione di strati su un buffer di celle.

Una schermata non e' una gerarchia di widget ma una pila di strati: il fondo
(form o browse), eventuali popup, la barra di stato. Ogni strato e' un
`CellBuffer` con un'origine; il compositore li sovrappone in ordine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..cell.buffer import SCREEN_HEIGHT, SCREEN_WIDTH, Cell, CellBuffer
from ..cell.cp437 import SHADE_LIGHT


@dataclass
class Layer:
    name: str
    buffer: CellBuffer
    row: int = 0
    col: int = 0
    visible: bool = True

    def contains(self, row: int, col: int) -> bool:
        return (
            self.visible
            and self.row <= row < self.row + self.buffer.height
            and self.col <= col < self.col + self.buffer.width
        )


@dataclass
class Scene:
    width: int = SCREEN_WIDTH
    height: int = SCREEN_HEIGHT
    background: Cell = field(default_factory=lambda: Cell())
    layers: list[Layer] = field(default_factory=list)

    def add(self, name: str, buffer: CellBuffer, row: int = 0, col: int = 0) -> Layer:
        layer = Layer(name, buffer, row, col)
        self.layers = [item for item in self.layers if item.name != name]
        self.layers.append(layer)
        return layer

    def get(self, name: str) -> Layer | None:
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def remove(self, name: str) -> None:
        self.layers = [item for item in self.layers if item.name != name]

    def bring_to_front(self, name: str) -> None:
        layer = self.get(name)
        if layer is not None:
            self.layers.remove(layer)
            self.layers.append(layer)

    def layer_at(self, row: int, col: int) -> Layer | None:
        for layer in reversed(self.layers):
            if layer.contains(row, col):
                return layer
        return None

    def composite(self) -> CellBuffer:
        canvas = CellBuffer(self.width, self.height, self.background)
        for layer in self.layers:
            if not layer.visible:
                continue
            for r in range(layer.buffer.height):
                target_row = layer.row + r
                if not 0 <= target_row < self.height:
                    continue
                for c in range(layer.buffer.width):
                    target_col = layer.col + c
                    if not 0 <= target_col < self.width:
                        continue
                    canvas.put(target_row, target_col, layer.buffer.get(r, c))
        return canvas


def popup(width: int, height: int, *, title: str = "", double: bool = False,
          shadow: bool = True, fg: int = 15, bg: int = 1,
          title_fg: int = 0, title_bg: int = 7,
          shadow_fg: int = 0, shadow_bg: int = 1) -> CellBuffer:
    """Costruisce un popup con cornice, titolo e ombra.

    Il buffer restituito e' `width + 1` per `height + 1`: la cornice occupa
    `width x height`, la riga e la colonna finali contengono l'ombra.
    """
    width = max(width, 4)
    height = max(height, 3)
    extra = 1 if shadow else 0
    buffer = CellBuffer(width + extra, height + extra, Cell(fg=fg, bg=bg))
    buffer.fill_rect(0, 0, height, width, " ", fg=fg, bg=bg)
    buffer.box(0, 0, height, width, double=double, fg=fg, bg=bg)
    if title:
        text = f" {title} "[: width - 4]
        buffer.write(0, 2, text, fg=title_fg, bg=title_bg, bold=True)
    if shadow:
        for col in range(1, width + 1):
            buffer.put(height, col, Cell(SHADE_LIGHT, fg=shadow_fg, bg=shadow_bg))
        for row in range(1, height + 1):
            buffer.put(row, width, Cell(SHADE_LIGHT, fg=shadow_fg, bg=shadow_bg))
    return buffer


def centered(scene_width: int, scene_height: int, width: int, height: int,
             top: int | None = None) -> tuple[int, int]:
    row = (scene_height - height) // 2 if top is None else top
    col = (scene_width - width) // 2
    return max(row, 0), max(col, 0)
