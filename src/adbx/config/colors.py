"""Colori per database o set: override del tema Newport."""

from __future__ import annotations

import json
from dataclasses import replace

COLOR_TOKENS = (
    ("Background", "bg"), ("Text", "text"), ("Labels", "label"),
    ("Muted", "muted"), ("Title background", "title_bg"),
    ("Title text", "title_fg"), ("Window background", "window_bg"),
    ("Window text", "window_fg"), ("Border", "border"),
    ("Selected background", "selected_bg"), ("Selected text", "selected_fg"),
    ("Status background", "status_bg"), ("Status text", "status_fg"),
    ("Help background", "help_bg"), ("Help text", "help_fg"),
    ("Menu background", "menu_bg"), ("Menu text", "menu_fg"),
    ("Accent", "accent"),
)

TOKEN_FIELDS = dict(COLOR_TOKENS)


def _key(owner: str) -> str:
    return f"colors:{owner.strip().upper()}"


def load_colors(workspace, owner: str) -> dict[str, int]:
    raw = workspace.setting(_key(owner), "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return {name: int(value) for name, value in data.items()
            if name in TOKEN_FIELDS and 0 <= int(value) <= 15}


def save_colors(workspace, owner: str, colors: dict[str, int]) -> None:
    clean = {name: int(value) for name, value in colors.items()
             if name in TOKEN_FIELDS and 0 <= int(value) <= 15}
    workspace.set_setting(_key(owner), json.dumps(clean, sort_keys=True))


def theme_for(workspace, owner: str, base=None):
    from ..shell.theme import NEWPORT

    if base is None:
        base = NEWPORT
    colors = load_colors(workspace, owner)
    if not colors:
        return base
    values = {field: colors[name] for name, field in COLOR_TOKENS
              if name in colors}
    return replace(base, **values)


def defaults_palette() -> dict[str, int]:
    from ..shell.theme import NEWPORT

    return {name: int(getattr(NEWPORT, field)) for name, field in COLOR_TOKENS}


def cycle_color(value: int, delta: int = 1) -> int:
    return (int(value) + delta) % 16


__all__ = [
    "COLOR_TOKENS", "TOKEN_FIELDS", "cycle_color", "defaults_palette",
    "load_colors", "save_colors", "theme_for",
]
