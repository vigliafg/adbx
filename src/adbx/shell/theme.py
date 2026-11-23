"""Tema colori dell'interfaccia.

I nomi dei token descrivono il ruolo, non il colore: il tema predefinito
riproduce lo schema blu di Alpha Four (fondo blu, finestre chiare con testo
nero, barra del titolo scura). La scelta di altri schemi arriverà con
l'import della palette originale.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..cell.attrs import Color


@dataclass(frozen=True)
class Theme:
    bg: int = int(Color.BLUE)
    text: int = int(Color.BRIGHT_WHITE)
    label: int = int(Color.CYAN)
    muted: int = int(Color.GRAY)
    title_bg: int = int(Color.BLACK)
    title_fg: int = int(Color.BRIGHT_WHITE)
    window_bg: int = int(Color.WHITE)
    window_fg: int = int(Color.BLACK)
    border: int = int(Color.BLACK)
    selected_bg: int = int(Color.BLACK)
    selected_fg: int = int(Color.BRIGHT_WHITE)
    status_bg: int = int(Color.BLACK)
    status_fg: int = int(Color.BRIGHT_WHITE)
    help_bg: int = int(Color.BLUE)
    help_fg: int = int(Color.BRIGHT_WHITE)
    menu_bg: int = int(Color.BLUE)
    menu_fg: int = int(Color.BRIGHT_WHITE)
    accent: int = int(Color.YELLOW)


NEWPORT = Theme()

THEMES = {"newport": NEWPORT}


def get_theme(name: str = "newport") -> Theme:
    return THEMES.get(name, NEWPORT)


__all__ = ["NEWPORT", "THEMES", "Theme", "get_theme"]
