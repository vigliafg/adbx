"""Font TrueType monospaziato: caricamento, scelta, metriche.

Il font e' incorporato nel pacchetto (DejaVu Sans Mono, licenza Bitstream
Vera) per avere lo stesso disegno su Linux, Windows e macOS. Se il
caricamento fallisce si ripiega sul monospace di sistema.
"""

from __future__ import annotations

from importlib import resources

from PyQt6.QtGui import QFont, QFontDatabase

# Famiglie preferite, in ordine. La prima disponibile vince.
PREFERRED_FAMILIES = (
    "DejaVu Sans Mono",
    "JetBrains Mono",
    "Cascadia Mono",
    "Consolas",
    "Liberation Mono",
    "Menlo",
    "Courier New",
)

BUNDLED_FILES = ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf")

_loaded = False
_family: str | None = None


def load_bundled() -> None:
    """Registra i TTF incorporati una sola volta, all'avvio dell'app."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    data = resources.files("adbx").joinpath("data/fonts")
    for name in BUNDLED_FILES:
        try:
            path = data.joinpath(name)
            with resources.as_file(path) as disk:
                QFontDatabase.addApplicationFont(str(disk))
        except (FileNotFoundError, OSError):  # pragma: no cover - ambiente anomalo
            continue


def monospace_family() -> str:
    """Prima famiglia monospaziata preferita realmente disponibile."""
    global _family
    if _family is not None:
        return _family
    load_bundled()
    available = set(QFontDatabase.families())
    for family in PREFERRED_FAMILIES:
        if family in available:
            _family = family
            return family
    fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
    _family = fixed or "monospace"
    return _family


def make_font(pixel_size: int, *, bold: bool = False, family: str | None = None) -> QFont:
    """Font per una cella alta `pixel_size` pixel di dispositivo."""
    font = QFont(family or monospace_family())
    font.setPixelSize(max(4, int(pixel_size)))
    font.setFixedPitch(True)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setBold(bold)
    # Il testo deve restare nitido alle dimensioni piccole.
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font


__all__ = ["BUNDLED_FILES", "PREFERRED_FAMILIES", "load_bundled", "make_font", "monospace_family"]
