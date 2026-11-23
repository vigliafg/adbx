"""Default settings e file `config.json` (equivalente di `A4.DFL`)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .display import ZOOM_DEFAULT, clamp_zoom
from .printers import PrinterConfig, load_printers, save_printers

CONFIG_FILE = "config.json"
PATTERNS = ("exact", "case", "insensitive")


class ConfigError(ValueError):
    """Configurazione non valida."""


@dataclass
class DefaultSettings:
    date_separator: str = "/"
    date_format: str = "American"
    auto_flush: bool = True
    pattern: str = "exact"
    prevent_change: bool = False
    prevent_enter: bool = False
    single_step_enters: bool = False
    utilities_lock: bool = True
    dbase4: bool = False
    monochrome: bool = False
    script_path: str = ""
    data_path: str = ""
    last_database: str = ""
    printer_default: str = ""
    screen_zoom: int = ZOOM_DEFAULT

    def __post_init__(self) -> None:
        self.date_separator = (self.date_separator or "/")[:1]
        self.date_format = ("European"
                            if self.date_format.lower().startswith("e")
                            else "American")
        if self.pattern not in PATTERNS:
            raise ConfigError(f"Unknown pattern matching: {self.pattern}")
        self.screen_zoom = clamp_zoom(self.screen_zoom)

    @property
    def european_dates(self) -> bool:
        return self.date_format == "European"

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DefaultSettings":
        if not data:
            return cls()
        known = set(cls.__dataclass_fields__)
        values = {key: value for key, value in data.items() if key in known}
        for name in ("auto_flush", "prevent_change", "prevent_enter",
                     "single_step_enters", "utilities_lock", "dbase4",
                     "monochrome"):
            if name in values:
                values[name] = bool(values[name])
        return cls(**values)


@dataclass
class ConfigStore:
    """File unico di configurazione nella cartella di avvio."""

    directory: Path
    defaults: DefaultSettings = field(default_factory=DefaultSettings)
    printers: PrinterConfig = field(default_factory=PrinterConfig)

    def __post_init__(self) -> None:
        self.directory = Path(self.directory).expanduser()
        self.load()

    @property
    def path(self) -> Path:
        return self.directory / CONFIG_FILE

    def load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.defaults = DefaultSettings.from_dict(data.get("defaults"))
        self.printers = PrinterConfig.from_dict(data.get("printers"))

    def save(self) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ConfigError(f"Cannot write configuration: {exc}") from exc
        payload = {"defaults": self.defaults.to_dict(),
                   "printers": self.printers.to_dict()}
        temporary = self.path.with_suffix(".json.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            temporary.replace(self.path)
        except OSError as exc:
            raise ConfigError(f"Cannot write configuration: {exc}") from exc

    # -- compatibilità con i file separati ------------------------------
    def load_legacy_printers(self, path: Path) -> None:
        self.printers = load_printers(path)

    def save_legacy_printers(self, path: Path) -> None:
        save_printers(path, self.printers)


__all__ = ["CONFIG_FILE", "ConfigError", "ConfigStore", "DefaultSettings",
           "PATTERNS"]
