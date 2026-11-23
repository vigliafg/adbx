"""Conversione degli eventi Qt nei tasti canonici del motore."""

from __future__ import annotations

from PyQt6.QtCore import Qt

from .keys import Key

_SPECIAL: dict[int, str] = {
    int(Qt.Key.Key_Return): "ENTER",
    int(Qt.Key.Key_Enter): "ENTER",
    int(Qt.Key.Key_Escape): "ESC",
    int(Qt.Key.Key_Tab): "TAB",
    int(Qt.Key.Key_Backtab): "TAB",
    int(Qt.Key.Key_Backspace): "BACKSPACE",
    int(Qt.Key.Key_Space): "SPACE",
    int(Qt.Key.Key_Up): "UP",
    int(Qt.Key.Key_Down): "DOWN",
    int(Qt.Key.Key_Left): "LEFT",
    int(Qt.Key.Key_Right): "RIGHT",
    int(Qt.Key.Key_Home): "HOME",
    int(Qt.Key.Key_End): "END",
    int(Qt.Key.Key_PageUp): "PGUP",
    int(Qt.Key.Key_PageDown): "PGDN",
    int(Qt.Key.Key_Insert): "INSERT",
    int(Qt.Key.Key_Delete): "DELETE",
}

for _n in range(1, 11):
    _SPECIAL[int(getattr(Qt.Key, f"Key_F{_n}"))] = f"F{_n}"

_TEXT_NAMES = {
    "-": "MINUS",
    "=": "EQUAL",
    "+": "PLUS",
    ",": "COMMA",
    ".": "PERIOD",
    ";": "SEMICOLON",
    ":": "COLON",
    "/": "SLASH",
    "\\": "BACKSLASH",
    "[": "LBRACKET",
    "]": "RBRACKET",
    "'": "QUOTE",
    '"': "DQUOTE",
    "`": "BACKTICK",
    "~": "TILDE",
    "!": "BANG",
    "?": "QUESTION",
    "*": "STAR",
    "&": "AMPERSAND",
    "^": "CARET",
    "%": "PERCENT",
    "$": "DOLLAR",
    "#": "HASH",
    "@": "AT",
    "<": "LT",
    ">": "GT",
    "(": "LPAREN",
    ")": "RPAREN",
    "_": "UNDERSCORE",
    "{": "LBRACE",
    "}": "RBRACE",
    "|": "PIPE",
}


def key_from_qt(event) -> Key | None:
    """Traduce un `QKeyEvent`; `None` se il tasto non e' gestito."""
    mods = event.modifiers()
    ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
    alt = bool(mods & Qt.KeyboardModifier.AltModifier)
    shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
    code = int(event.key())

    name = _SPECIAL.get(code)
    if name is None:
        text = event.text()
        if text and text.isprintable():
            name = _TEXT_NAMES.get(text, text.upper())
        elif 0x20 <= code <= 0x7E:
            name = chr(code).upper()
        else:
            return None
    return Key(name, ctrl=ctrl, alt=alt, shift=shift)
