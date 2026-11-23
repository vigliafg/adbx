"""Guscio di adbx: main menu, Database Directory, aiuto contestuale."""

from .controller import ShellController, demo_controller
from .state import CurrentFile, ShellState, default_root
from .theme import NEWPORT, Theme, get_theme

__all__ = [
    "NEWPORT",
    "CurrentFile",
    "ShellController",
    "ShellState",
    "Theme",
    "default_root",
    "demo_controller",
    "get_theme",
]
