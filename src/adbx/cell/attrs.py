"""Colori e attributi delle celle.

Alpha Four lavora su 16 colori DOS piu' gli attributi bold e blink; i form
ammettono valori di colore 0-255. La mappatura 0-255 -> 16 colori e' fissata
qui (vedi `resolve_color`) ed e' provvisoria finche' non si importa la palette
originale `A4.PAL`.
"""

from __future__ import annotations

from enum import IntEnum

CellRGB = tuple[int, int, int]


class Color(IntEnum):
    BLACK = 0
    BLUE = 1
    GREEN = 2
    CYAN = 3
    RED = 4
    MAGENTA = 5
    BROWN = 6
    WHITE = 7
    GRAY = 8
    BRIGHT_BLUE = 9
    BRIGHT_GREEN = 10
    BRIGHT_CYAN = 11
    BRIGHT_RED = 12
    BRIGHT_MAGENTA = 13
    YELLOW = 14
    BRIGHT_WHITE = 15


# Palette VGA/DOS classica
DOS_PALETTE: tuple[CellRGB, ...] = (
    (0, 0, 0),
    (0, 0, 170),
    (0, 170, 0),
    (0, 170, 170),
    (170, 0, 0),
    (170, 0, 170),
    (170, 85, 0),
    (170, 170, 170),
    (85, 85, 85),
    (85, 85, 255),
    (85, 255, 85),
    (85, 255, 255),
    (255, 85, 85),
    (255, 85, 255),
    (255, 255, 85),
    (255, 255, 255),
)

# Schema predefinito di Alpha Four su monitor colore: "Newport", blu
# monocromatico. Usato dal tema `newport`.
NEWPORT_PALETTE: tuple[CellRGB, ...] = (
    (0, 0, 0),
    (0, 0, 96),
    (24, 24, 128),
    (48, 48, 176),
    (72, 72, 208),
    (96, 96, 224),
    (136, 136, 232),
    (176, 176, 240),
    (208, 208, 248),
    (0, 0, 128),
    (0, 0, 160),
    (208, 208, 248),
    (232, 232, 252),
    (255, 255, 255),
    (248, 248, 255),
    (255, 255, 255),
)

DEFAULT_FG = int(Color.WHITE)
DEFAULT_BG = int(Color.BLUE)


def resolve_color(index: int) -> int:
    """Riporta un colore 0-255 di Alpha Four a uno dei 16 colori DOS.

    Regola provvisoria e deterministica: 0-15 identita', 16-255 modulo 16.
    La mappatura definitiva arrivera' con l'import della palette originale.
    """
    if index < 0:
        return 0
    return index % 16


def bright(color: int) -> int:
    """Versione intensa di un colore (bold DOS)."""
    color = resolve_color(color)
    if color < 8:
        return color + 8
    return color
