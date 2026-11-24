"""Scala del carattere nella finestra: leggibilità e livelli di zoom."""

from __future__ import annotations

#: Tetto del corpo scelto automaticamente, in pixel logici. Su schermi molto
#: grandi il testo si ferma qui e la griglia lascia margini, invece di
#: diventare enorme.
COMFORT_FONT_PX = 24

ZOOM_DEFAULT = 100
ZOOM_MIN = 50
ZOOM_MAX = 200
ZOOM_STEP = 10


def base_pixel_size(best: int, ceiling: int) -> int:
    """Corpo al 100%: il massimo che entra, entro il tetto di leggibilità."""
    return max(1, min(int(best), int(ceiling)))


def zoom_pixel_size(base: int, zoom: int) -> int:
    """Corpo per un livello di zoom, a partire dal corpo al 100%."""
    return max(1, round(int(base) * int(zoom) / 100))


def clamp_zoom(value: object) -> int:
    """Riporta uno zoom percentuale nell'intervallo ammesso."""
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ZOOM_DEFAULT
    return max(ZOOM_MIN, min(ZOOM_MAX, number))


__all__ = [
    "COMFORT_FONT_PX",
    "ZOOM_DEFAULT",
    "ZOOM_MAX",
    "ZOOM_MIN",
    "ZOOM_STEP",
    "base_pixel_size",
    "clamp_zoom",
    "zoom_pixel_size",
]
