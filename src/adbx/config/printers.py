"""Driver di stampa: 26 configurazioni A–Z, codici e avanzamento carta.

I driver non parlano direttamente a una stampante DOS: descrivono i codici e
le geometrie che Alpha Four avrebbe inviato. Il PDF usa margini e interruzioni
di pagina; l'esportazione `.PRN` applica i codici decimali e il carattere di
avanzamento (formfeed, sheetfeeder o linefeed).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LETTERS = tuple(chr(code) for code in range(ord("A"), ord("Z") + 1))
PAGE_ADVANCE = ("Formfeed", "Sheetfeeder", "Linefeed")


class PrinterError(ValueError):
    """Configurazione di stampa non valida."""


@dataclass(frozen=True)
class PrinterModel:
    name: str
    lines_per_page: int = 66
    page_advance: str = "Formfeed"
    setup: tuple[int, ...] = ()
    close: tuple[int, ...] = ()
    normal: tuple[int, ...] = (27, 69)
    bold: tuple[int, ...] = (27, 69)
    italic: tuple[int, ...] = (27, 52)
    underline_on: tuple[int, ...] = (27, 45, 49)
    underline_off: tuple[int, ...] = (27, 45, 48)
    compressed_on: tuple[int, ...] = (15,)
    compressed_off: tuple[int, ...] = (18,)
    page1: tuple[int, ...] = (12,)
    new_page: tuple[int, ...] = (12,)
    column_offset: int = 0


# Catalogo dei modelli supportati; i codici sono quelli tipici delle famiglie
# ESC/P, PCL e PostScript. Le installazioni scelgono una lettera A–Z.
PRINTER_MODELS: tuple[PrinterModel, ...] = (
    PrinterModel("Generic parallel printer", normal=(), bold=(), italic=(),
                 underline_on=(), underline_off=(), compressed_on=(),
                 compressed_off=()),
    PrinterModel("Epson FX-850", setup=(27, 64), bold=(27, 69),
                 italic=(27, 52), compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Epson FX-1050", setup=(27, 64), bold=(27, 69),
                 italic=(27, 52), compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Epson LQ-570", setup=(27, 64), bold=(27, 69),
                 italic=(27, 52), compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Epson LQ-1070", setup=(27, 64), bold=(27, 69),
                 italic=(27, 52), compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Epson LX-810", setup=(27, 64), bold=(27, 69),
                 italic=(27, 52), compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("IBM Proprinter II", setup=(27, 91, 0), bold=(27, 69),
                 italic=(27, 52), compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("IBM Proprinter XL", setup=(27, 91, 0), bold=(27, 69),
                 italic=(27, 52), compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("IBM Quietwriter III", bold=(27, 69), italic=(27, 52),
                 compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Okidata ML-320", setup=(27, 33), bold=(27, 33),
                 italic=(27, 52), compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Okidata ML-321", setup=(27, 33), bold=(27, 33),
                 italic=(27, 52), compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Okidata ML-390", setup=(27, 33), bold=(27, 33),
                 italic=(27, 52), compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Panasonic KX-P1124", bold=(27, 69), italic=(27, 52),
                 compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Panasonic KX-P2124", bold=(27, 69), italic=(27, 52),
                 compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Star Micronics NX-1000", bold=(27, 69), italic=(27, 52),
                 compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Star Micronics NX-2420", bold=(27, 69), italic=(27, 52),
                 compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Toshiba P321", bold=(27, 69), italic=(27, 52),
                 compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("Citizen GSX-140", bold=(27, 69), italic=(27, 52),
                 compressed_on=(15,), compressed_off=(18,)),
    PrinterModel("HP LaserJet II", lines_per_page=60,
                 setup=(27, 69), bold=(27, 40, 115, 51, 66),
                 italic=(27, 40, 115, 49, 73), compressed_on=(27, 38, 107, 50, 83),
                 compressed_off=(27, 38, 107, 48, 83)),
    PrinterModel("HP LaserJet III", lines_per_page=60,
                 setup=(27, 69), bold=(27, 40, 115, 51, 66),
                 italic=(27, 40, 115, 49, 73)),
    PrinterModel("HP LaserJet 4", lines_per_page=60, setup=(27, 69),
                 bold=(27, 40, 115, 51, 66), italic=(27, 40, 115, 49, 73)),
    PrinterModel("HP DeskJet 500", lines_per_page=60, setup=(27, 69),
                 bold=(27, 69), italic=(27, 52)),
    PrinterModel("HP DeskJet 1200C", lines_per_page=60, setup=(27, 69),
                 bold=(27, 69), italic=(27, 52)),
    PrinterModel("Canon BubbleJet BJ-200", bold=(27, 69), italic=(27, 52)),
    PrinterModel("PostScript printer", page_advance="Linefeed",
                 setup=(), close=(), bold=(), italic=(), underline_on=(),
                 underline_off=(), compressed_on=(), compressed_off=(),
                 page1=(), new_page=()),
    PrinterModel("Generic text printer", normal=(), bold=(), italic=(),
                 underline_on=(), underline_off=(), compressed_on=(),
                 compressed_off=(), page_advance="Linefeed", page1=(),
                 new_page=()),
)


@dataclass
class PrinterDriver:
    """Configurazione installata sotto una lettera A–Z."""

    letter: str
    name: str = "Generic parallel printer"
    lines_per_page: int = 66
    page_advance: str = "Formfeed"
    setup: list[int] = field(default_factory=list)
    close: list[int] = field(default_factory=list)
    normal: list[int] = field(default_factory=lambda: [27, 69])
    bold: list[int] = field(default_factory=lambda: [27, 69])
    italic: list[int] = field(default_factory=lambda: [27, 52])
    underline_on: list[int] = field(default_factory=lambda: [27, 45, 49])
    underline_off: list[int] = field(default_factory=lambda: [27, 45, 48])
    compressed_on: list[int] = field(default_factory=lambda: [15])
    compressed_off: list[int] = field(default_factory=lambda: [18])
    page1: list[int] = field(default_factory=lambda: [12])
    new_page: list[int] = field(default_factory=lambda: [12])
    column_offset: int = 0
    margin_left: int = 0
    margin_right: int = 0
    margin_top: int = 0
    margin_bottom: int = 0
    port: str = "LPT1"
    description: str = ""

    def __post_init__(self) -> None:
        self.letter = self.letter.strip().upper()[:1]
        if self.letter not in LETTERS:
            raise PrinterError("Printer drivers use letters A-Z.")
        if self.page_advance not in PAGE_ADVANCE:
            raise PrinterError(f"Unknown page advance: {self.page_advance}")
        self.lines_per_page = max(1, min(200, int(self.lines_per_page)))
        for name in ("setup", "close", "normal", "bold", "italic",
                     "underline_on", "underline_off", "compressed_on",
                     "compressed_off", "page1", "new_page"):
            value = [max(0, min(255, int(code))) for code in getattr(self, name)]
            setattr(self, name, value)
        for name in ("margin_left", "margin_right", "margin_top",
                     "margin_bottom", "column_offset"):
            setattr(self, name, max(0, min(200, int(getattr(self, name)))))

    @classmethod
    def from_model(cls, letter: str, model: PrinterModel) -> "PrinterDriver":
        return cls(letter, model.name, model.lines_per_page,
                   model.page_advance, list(model.setup), list(model.close),
                   list(model.normal), list(model.bold), list(model.italic),
                   list(model.underline_on), list(model.underline_off),
                   list(model.compressed_on), list(model.compressed_off),
                   list(model.page1), list(model.new_page),
                   model.column_offset)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PrinterDriver":
        known = {field_name for field_name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in data.items()
                      if key in known})

    def advance_bytes(self, first_page: bool = False) -> bytes:
        if self.page_advance == "Linefeed":
            return b"\n" * self.lines_per_page
        codes = self.page1 if first_page else self.new_page
        return bytes(codes) if codes else b"\f"


@dataclass
class PrinterConfig:
    drivers: dict[str, PrinterDriver] = field(default_factory=dict)
    default: str = ""

    def __post_init__(self) -> None:
        self.drivers = {letter.upper(): driver
                        for letter, driver in self.drivers.items()
                        if letter.upper() in LETTERS}
        if self.default and self.default.upper() not in self.drivers:
            self.default = ""
        elif self.default:
            self.default = self.default.upper()

    @property
    def active(self) -> PrinterDriver | None:
        if not self.drivers:
            return None
        letter = self.default or sorted(self.drivers)[0]
        return self.drivers.get(letter)

    def install(self, driver: PrinterDriver) -> PrinterDriver:
        self.drivers[driver.letter] = driver
        if not self.default:
            self.default = driver.letter
        return driver

    def erase(self, letter: str) -> bool:
        letter = letter.upper()
        removed = self.drivers.pop(letter, None) is not None
        if self.default == letter:
            self.default = sorted(self.drivers)[0] if self.drivers else ""
        return removed

    def select(self, letter: str) -> bool:
        letter = letter.upper()
        if letter not in self.drivers:
            return False
        self.default = letter
        return True

    def to_dict(self) -> dict[str, Any]:
        return {"drivers": {letter: driver.to_dict()
                            for letter, driver in self.drivers.items()},
                "default": self.default}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PrinterConfig":
        if not data:
            return cls()
        drivers = {letter: PrinterDriver.from_dict(item)
                   for letter, item in (data.get("drivers") or {}).items()
                   if letter.upper() in LETTERS}
        return cls(drivers, str(data.get("default", "")))

    def render_text(self, lines: list[str], *, first_page: bool = True) -> bytes:
        """Applica codici, margini e avanzamento a un flusso di stampa."""
        driver = self.active
        if driver is None:
            return ("\n".join(lines) + "\n").encode("latin-1", "replace")
        prefix = bytes(driver.setup)
        left = " " * driver.margin_left
        body = []
        for index, line in enumerate(lines):
            body.append(left + line)
            if driver.lines_per_page and (index + 1) % driver.lines_per_page == 0:
                body.append("")
        text = "\n".join(body) + "\n"
        advance = driver.advance_bytes(first_page)
        return prefix + text.encode("latin-1", "replace") + advance + \
            bytes(driver.close)


ACTIVE_PRINTER: PrinterDriver | None = None


def configure_printer(driver: PrinterDriver | None) -> None:
    """Imposta il driver usato dal generatore PDF."""
    global ACTIVE_PRINTER
    ACTIVE_PRINTER = driver


def current_printer() -> PrinterDriver | None:
    return ACTIVE_PRINTER


def driver_from_catalog(letter: str, model_index: int) -> PrinterDriver:
    if not 0 <= model_index < len(PRINTER_MODELS):
        raise PrinterError("Unknown printer model.")
    return PrinterDriver.from_model(letter, PRINTER_MODELS[model_index])


def save_printers(path: Path, config: PrinterConfig) -> None:
    payload = json.dumps(config.to_dict(), indent=2, ensure_ascii=False)
    path.write_text(payload + "\n", encoding="utf-8")


def load_printers(path: Path) -> PrinterConfig:
    if not path.is_file():
        return PrinterConfig()
    try:
        return PrinterConfig.from_dict(json.loads(
            path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return PrinterConfig()


__all__ = [
    "ACTIVE_PRINTER", "LETTERS", "PAGE_ADVANCE", "PRINTER_MODELS",
    "PrinterConfig", "PrinterDriver", "PrinterError", "PrinterModel",
    "configure_printer", "current_printer", "driver_from_catalog",
    "load_printers", "save_printers",
]
