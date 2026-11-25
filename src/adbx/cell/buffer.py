"""Buffer di celle: l'unica primitiva grafica del programma.

Non esistono widget: una schermata e' una matrice `width x height` di `Cell`.
Tutto il resto (form, popup, regioni, report) scrive in un buffer.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import wraps
from typing import Iterator

from .attrs import DEFAULT_BG, DEFAULT_FG, bright, resolve_color
from .cp437 import DOUBLE, SHADE_LIGHT, SINGLE

# Griglia logica originale Alpha Four: 80 colonne per 25 righe.
# Questa e' la variante "legacy": il font resta TrueType scalabile, la
# geometria torna quella della console DOS.
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 25

# Le tre righe di chrome sono ancorate in fondo, come nella console originale.
STATUS_ROW = SCREEN_HEIGHT - 3
HELP_ROW = SCREEN_HEIGHT - 2
MENU_ROW = SCREEN_HEIGHT - 1
WORK_ROWS = SCREEN_HEIGHT - 3  # righe 0..STATUS_ROW-1


@dataclass(frozen=True, slots=True)
class Cell:
    ch: str = " "
    fg: int = DEFAULT_FG
    bg: int = DEFAULT_BG
    blink: bool = False
    bold: bool = False
    underline: bool = False

    def styled(self, *, fg: int | None = None, bg: int | None = None,
               blink: bool | None = None, bold: bool | None = None,
               underline: bool | None = None) -> "Cell":
        return replace(
            self,
            fg=self.fg if fg is None else resolve_color(fg),
            bg=self.bg if bg is None else resolve_color(bg),
            blink=self.blink if blink is None else blink,
            bold=self.bold if bold is None else bold,
            underline=self.underline if underline is None else underline,
        )


BLANK = Cell()
SHADOW = Cell(SHADE_LIGHT, fg=8, bg=0)


@dataclass(frozen=True, slots=True)
class ClipEvent:
    """Scrittura richiesta fuori dalla griglia, registrata solo nei test.

    Il video originale taglia in silenzio: qui il taglio resta silenzioso in
    produzione, ma con l'audit attivo ogni scrittura oltre i bordi finisce in
    un elenco, così un layout che sborda viene scoperto dai test.
    """

    kind: str  # "write" | "fill"
    row: int
    col: int
    detail: str
    where: str = ""  # modulo:funzione:riga del primo chiamante fuori dal buffer


_CLIP_LOG: list[ClipEvent] | None = None
_CLIP_ALLOWED = 0


@contextmanager
def allow_clipping() -> Iterator[None]:
    """Dichiara voluto il taglio: canvas più larghi dello schermo (form, label).

    Le definizioni salvate da versioni a 132 colonne possono eccedere la
    griglia 80x25: il disegno viene tagliato dal bordo, come sul video
    originale, senza che l'audit lo segnali come errore di layout.
    """
    global _CLIP_ALLOWED
    _CLIP_ALLOWED += 1
    try:
        yield
    finally:
        _CLIP_ALLOWED -= 1


@contextmanager
def audit_clipping() -> Iterator[list[ClipEvent]]:
    """Raccoglie le scritture fuori bordo finché il contesto è aperto."""
    global _CLIP_LOG
    if _CLIP_LOG is not None:  # audit annidato: usa l'elenco esterno
        yield _CLIP_LOG
        return
    log: list[ClipEvent] = []
    _CLIP_LOG = log
    try:
        yield log
    finally:
        _CLIP_LOG = None


def _record_clip(event: ClipEvent) -> None:
    if _CLIP_LOG is not None and not _CLIP_ALLOWED:
        _CLIP_LOG.append(event)


def clipping_allowed(func):
    """Decoratore: il taglio prodotto dalla funzione è voluto (canvas 132→80)."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with allow_clipping():
            return func(*args, **kwargs)
    return wrapper


def _caller() -> str:
    """Primo fotogramma fuori da questo file, per attribuire il clipping."""
    frame = sys._getframe(1)
    while frame is not None:
        if not frame.f_code.co_filename.endswith("cell/buffer.py"):
            return (f"{frame.f_globals.get('__name__', '?')}:"
                    f"{frame.f_code.co_name}:{frame.f_lineno}")
        frame = frame.f_back
    return "?"


def audit_active() -> bool:
    return _CLIP_LOG is not None


class CellBuffer:
    """Matrice di celle con clipping silenzioso, come il video originale."""

    __slots__ = ("width", "height", "_cells")

    def __init__(self, width: int = SCREEN_WIDTH, height: int = SCREEN_HEIGHT,
                 fill: Cell = BLANK) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("dimensioni non valide")
        self.width = width
        self.height = height
        self._cells: list[list[Cell]] = [[fill] * width for _ in range(height)]

    # -- accesso ---------------------------------------------------------
    def get(self, row: int, col: int) -> Cell:
        if 0 <= row < self.height and 0 <= col < self.width:
            return self._cells[row][col]
        return BLANK

    def put(self, row: int, col: int, cell: Cell) -> None:
        if 0 <= row < self.height and 0 <= col < self.width:
            self._cells[row][col] = cell

    def clear(self, cell: Cell = BLANK) -> None:
        for row in range(self.height):
            self._cells[row] = [cell] * self.width

    def copy(self) -> "CellBuffer":
        """Copia indipendente del buffer (le celle sono immutabili)."""
        clone = CellBuffer(self.width, self.height)
        clone._cells = [row[:] for row in self._cells]
        return clone

    # -- scrittura -------------------------------------------------------
    def write(self, row: int, col: int, text: str, *,
              fg: int | None = None, bg: int | None = None,
              blink: bool | None = None, bold: bool | None = None,
              underline: bool | None = None,
              limit: int | None = None) -> int:
        """Scrive testo e ritorna la colonna successiva (clippata)."""
        if _CLIP_LOG is not None and text:
            if not 0 <= row < self.height:
                _record_clip(ClipEvent("write-row", row, col, text, _caller()))
            elif col < 0:
                _record_clip(ClipEvent("write-left", row, col, text, _caller()))
            else:
                shown = text if limit is None else text[:limit]
                if col + len(shown) > self.width:
                    _record_clip(ClipEvent("write-right", row, col, text, _caller()))
        if not 0 <= row < self.height:
            return col
        style = self.get(row, col).styled(
            fg=fg, bg=bg, blink=blink, bold=bold, underline=underline
        )
        count = 0
        for offset, char in enumerate(text):
            if limit is not None and offset >= limit:
                break
            target = col + offset
            if target >= self.width:
                break
            if target >= 0:
                self._cells[row][target] = replace(style, ch=char)
            count = offset + 1
        return col + count

    def fill_rect(self, row: int, col: int, height: int, width: int,
                  char: str = " ", *, fg: int | None = None, bg: int | None = None,
                  blink: bool | None = None, bold: bool | None = None,
                  underline: bool | None = None) -> None:
        if _CLIP_LOG is not None and height > 0 and width > 0:
            if row < 0 or row + height > self.height:
                _record_clip(ClipEvent("fill-row", row, col,
                                       f"{height}x{width}", _caller()))
            if col < 0 or col + width > self.width:
                _record_clip(ClipEvent("fill-col", row, col,
                                       f"{height}x{width}", _caller()))
        for r in range(row, min(row + height, self.height)):
            if r < 0:
                continue
            for c in range(col, min(col + width, self.width)):
                if c < 0:
                    continue
                self._cells[r][c] = self._cells[r][c].styled(
                    fg=fg, bg=bg, blink=blink, bold=bold, underline=underline
                )
                self._cells[r][c] = replace(self._cells[r][c], ch=char)

    # -- disegno ---------------------------------------------------------
    def hline(self, row: int, col: int, width: int, char: str = "─", **style) -> None:
        self.write(row, col, char * max(width, 0), **style)

    def vline(self, row: int, col: int, height: int, char: str = "│", **style) -> None:
        for r in range(row, row + height):
            self.write(r, col, char, **style)

    def box(self, row: int, col: int, height: int, width: int, *,
            double: bool = False, **style) -> None:
        """Cornice di `height` righe per `width` colonne (bordi inclusi)."""
        if height < 2 or width < 2:
            return
        set_ = DOUBLE if double else SINGLE
        self.write(row, col, set_["tl"] + set_["h"] * (width - 2) + set_["tr"], **style)
        for r in range(row + 1, row + height - 1):
            self.write(r, col, set_["v"], **style)
            self.write(r, col + width - 1, set_["v"], **style)
        self.write(row + height - 1, col,
                   set_["bl"] + set_["h"] * (width - 2) + set_["br"], **style)

    def shadow(self, row: int, col: int, height: int, width: int) -> None:
        """Ombra in basso a destra, come i popup originali."""
        for c in range(col + 1, col + width + 1):
            self.put(row + height, c, SHADOW)
        for r in range(row + 1, row + height + 1):
            self.put(r, col + width, SHADOW)

    # -- output ----------------------------------------------------------
    def to_lines(self) -> list[str]:
        return ["".join(cell.ch for cell in row) for row in self._cells]

    def dump(self) -> str:
        """Rappresentazione testuale stabile per i test golden."""
        out = [f"adbx {self.width}x{self.height}"]
        for row in self._cells:
            out.append("".join(cell.ch for cell in row))
            runs: list[str] = []
            current = row[0]
            count = 1
            for cell in row[1:]:
                key = (cell.fg, cell.bg, cell.bold, cell.blink, cell.underline)
                other = (current.fg, current.bg, current.bold, current.blink,
                         current.underline)
                if key == other:
                    count += 1
                    continue
                runs.append(self._run(count, current))
                current = cell
                count = 1
            runs.append(self._run(count, current))
            out.append(" ".join(runs))
        return "\n".join(out) + "\n"

    @staticmethod
    def _run(count: int, cell: Cell) -> str:
        return (f"{count}@{cell.fg},{cell.bg},{int(cell.bold)},"
                f"{int(cell.blink)},{int(cell.underline)}")

    # -- utilita' --------------------------------------------------------
    def text_of(self, row: int, col: int = 0, width: int | None = None) -> str:
        width = self.width - col if width is None else width
        return "".join(self.get(row, c).ch for c in range(col, min(col + width, self.width))).rstrip()


def styled_text(cell: Cell, text: str) -> list[Cell]:
    return [replace(cell, ch=ch) for ch in text]


def bold_color(color: int) -> int:
    return bright(color)
