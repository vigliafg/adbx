"""Configurazione: default settings, colori e driver di stampa."""

from .colors import (
    COLOR_TOKENS,
    cycle_color,
    defaults_palette,
    load_colors,
    save_colors,
    theme_for,
)
from .defaults import CONFIG_FILE, ConfigError, ConfigStore, DefaultSettings
from .printers import (
    LETTERS,
    PAGE_ADVANCE,
    PRINTER_MODELS,
    PrinterConfig,
    PrinterDriver,
    PrinterError,
    PrinterModel,
    configure_printer,
    current_printer,
    driver_from_catalog,
    load_printers,
    save_printers,
)

__all__ = [
    "COLOR_TOKENS", "CONFIG_FILE", "ConfigError", "ConfigStore",
    "DefaultSettings", "LETTERS", "PAGE_ADVANCE", "PRINTER_MODELS",
    "PrinterConfig", "PrinterDriver", "PrinterError", "PrinterModel",
    "configure_printer", "current_printer", "cycle_color", "defaults_palette",
    "driver_from_catalog", "load_colors", "load_printers", "save_colors",
    "save_printers", "theme_for",
]
