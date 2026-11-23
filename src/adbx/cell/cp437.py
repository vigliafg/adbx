"""Mappa CP437: byte <-> carattere Unicode e glifi grafici.

Python fornisce il codec `cp437`; qui lo si espone come tabella indicizzata per
byte, che e' l'indice usato dal renderer per l'atlante dei glifi.

I codici 0x00-0x1F in CP437 sono simboli grafici (faccine, semi, frecce), ma il
codec Python li mappa sui caratteri di controllo: adottiamo lo spazio, come fa
la maggior parte dei terminali moderni.
"""

from __future__ import annotations

CHARS: tuple[str, ...] = tuple(
    " " if byte < 0x20 else bytes([byte]).decode("cp437") for byte in range(256)
)

TO_BYTE: dict[str, int] = {}
for _byte, _char in enumerate(CHARS):
    TO_BYTE.setdefault(_char, _byte)

# Cornici
SINGLE = {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│"}
DOUBLE = {"tl": "╔", "tr": "╗", "bl": "╚", "br": "╝", "h": "═", "v": "║"}
SHADE_LIGHT = "░"
SHADE_MEDIUM = "▒"
SHADE_DARK = "▓"
BLOCK_FULL = "█"

# Set di caratteri che il motore usa per disegnare senza dipendere dal font
DRAWING_CHARS = (
    set(SINGLE.values()) | set(DOUBLE.values())
    | {SHADE_LIGHT, SHADE_MEDIUM, SHADE_DARK, BLOCK_FULL}
)


def to_byte(char: str) -> int:
    """Indice di cella del carattere; `?` per i caratteri non rappresentabili."""
    if not char:
        return TO_BYTE[" "]
    return TO_BYTE.get(char[0], TO_BYTE["?"])


def is_drawing(char: str) -> bool:
    return char in DRAWING_CHARS
