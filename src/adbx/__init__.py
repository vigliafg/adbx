"""adbx — clone funzionale di Alpha Four v3 su griglia di caratteri e SQLite.

`VARIANT` distingue la variante legacy (griglia 80x25) dalla principale
(132x43) senza cambiare nome del pacchetto ne' versione.
"""

__version__ = "1.0.0"
VARIANT = "legacy"
GRID_WIDTH = 80
GRID_HEIGHT = 25

WINDOW_TITLE = f"adbx — legacy ({GRID_WIDTH}×{GRID_HEIGHT})"
