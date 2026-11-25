"""Cartella dati dell'utente per l'app pacchettizzata.

Quando adbx gira da un eseguibile PyInstaller (installer Windows, `.app`
macOS, `.AppImage` o `.deb`) la directory di lavoro non è scrivibile — su
Windows sta sotto `Program Files` — quindi `config.json` e i dati di default
si spostano nella cartella utente della piattaforma. `ADBX_DATA` e `--data`
restano prioritari.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIRNAME = "adbx-legacy"


def user_data_dir(platform: str | None = None,
                  environ: dict[str, str] | None = None) -> Path:
    """Cartella dati per piattaforma: APPDATA, Application Support, XDG."""
    system = sys.platform if platform is None else platform
    env = os.environ if environ is None else environ
    if system.startswith("win"):
        base = env.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    elif system == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        base = env.get("XDG_DATA_HOME")
        root = Path(base).expanduser() if base else (Path.home() / ".local" / "share")
    return root / APP_DIRNAME


__all__ = ["APP_DIRNAME", "user_data_dir"]
