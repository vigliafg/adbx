"""Tastiera: rappresentazione dei tasti e notazione testuale.

Il motore di script digita tasti in questa stessa rappresentazione: e' il
punto in cui playback e input reale coincidono.
"""

from __future__ import annotations

from dataclasses import dataclass

# Nomi canonici dei tasti speciali
ENTER = "ENTER"
ESC = "ESC"
TAB = "TAB"
BACKSPACE = "BACKSPACE"
SPACE = "SPACE"
UP = "UP"
DOWN = "DOWN"
LEFT = "LEFT"
RIGHT = "RIGHT"
HOME = "HOME"
END = "END"
PGUP = "PGUP"
PGDN = "PGDN"
INSERT = "INSERT"
DELETE = "DELETE"

SPECIAL_KEYS = {
    ENTER, ESC, TAB, BACKSPACE, SPACE, UP, DOWN, LEFT, RIGHT, HOME, END,
    PGUP, PGDN, INSERT, DELETE,
    *{f"F{n}" for n in range(1, 11)},
}

_ALIASES = {
    "RETURN": ENTER,
    "CR": ENTER,
    "ESCAPE": ESC,
    "BS": BACKSPACE,
    "DEL": DELETE,
    "INS": INSERT,
    "PGUP": PGUP,
    "PAGEUP": PGUP,
    "PGDN": PGDN,
    "PAGEDOWN": PGDN,
}


@dataclass(frozen=True, order=True)
class Key:
    name: str
    ctrl: bool = False
    alt: bool = False
    shift: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", normalize_name(self.name))

    def with_shift(self, shift: bool = True) -> "Key":
        return Key(self.name, self.ctrl, self.alt, shift)


def normalize_name(name: str) -> str:
    upper = name.upper()
    return _ALIASES.get(upper, upper)


def parse(text: str) -> Key:
    """Accetta `f10`, `alt-f`, `ctrl-home`, `alt-ctrl-a`, `{ENTER}`."""
    cleaned = text.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        cleaned = cleaned[1:-1]
    if not cleaned or cleaned.endswith("-"):
        raise ValueError("tasto vuoto")
    parts = [part for part in cleaned.split("-") if part]
    if not parts:
        raise ValueError("tasto vuoto")
    ctrl = alt = shift = False
    *mods, name = parts
    for mod in mods:
        mod = mod.lower()
        if mod == "ctrl":
            ctrl = True
        elif mod == "alt":
            alt = True
        elif mod == "shift":
            shift = True
        else:
            raise ValueError(f"modificatore sconosciuto: {mod}")
    return Key(normalize_name(name), ctrl=ctrl, alt=alt, shift=shift)


def format(key: Key) -> str:
    parts = []
    if key.ctrl:
        parts.append("ctrl")
    if key.alt:
        parts.append("alt")
    if key.shift:
        parts.append("shift")
    parts.append(key.name)
    return "-".join(parts)


def is_special(name: str) -> bool:
    return normalize_name(name) in SPECIAL_KEYS
