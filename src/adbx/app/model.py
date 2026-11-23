"""Modello delle applicazioni: menu, voci, banner e parametri.

Un'applicazione sostituisce il main menu di Alpha Four con un albero di menu.
Ogni voce può aprire un sottomenu, eseguire una macro, chiamare un'altra
applicazione (e tornarvi) oppure saltare a un'altra applicazione. Le voci
possono avere password, help file e help line. Il banner è una schermata a
celle mostrata all'avvio.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

APP_NAME_RE = re.compile(r"^[A-Z0-9_]{1,8}$")
MAX_MACRO = 3000
MAX_APPS = 400
MAX_LEVELS = 10
ACTIONS = ("Sub-Menu", "Macro", "Call-App", "GotO-App")
FLOWS = ("Return", "Stay", "Advance")
COLUMNS = ("Single", "Double")
SPACINGS = ("Single", "Double", "Triple", "Quadruple")
ALLOW_ESCAPE = ("Yes", "No", "Password")


class AppError(ValueError):
    """Applicazione non valida."""


def normalize_app_name(name: str) -> str:
    text = name.strip().upper()
    if text.endswith(".APP"):
        text = text[:-4]
    if not APP_NAME_RE.match(text):
        raise AppError("Application names have 1-8 letters, digits or _.")
    return text


def password_hash(password: str) -> str:
    """Hash stabile, case-insensitive, delle password delle voci."""
    text = (password or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.upper().encode("utf-8")).hexdigest()


def check_password(stored: str, password: str) -> bool:
    return bool(stored) and password_hash(password) == stored


@dataclass
class BannerScreen:
    """Schermata di banner: righe di testo, colori di base e override."""

    lines: list[str] = field(default_factory=list)
    foreground: int = 15
    background: int = 1
    colors: dict[str, list[int]] = field(default_factory=dict)

    def text(self, row: int, col: int) -> str:
        if 0 <= row < len(self.lines) and 0 <= col < len(self.lines[row]):
            return self.lines[row][col]
        return " "

    def put(self, row: int, col: int, char: str,
            foreground: int | None = None,
            background: int | None = None) -> None:
        while len(self.lines) <= row:
            self.lines.append("")
        line = self.lines[row]
        if len(line) <= col:
            line += " " * (col + 1 - len(line))
        self.lines[row] = line[:col] + char + line[col + 1:]
        if foreground is not None and background is not None:
            if foreground == self.foreground and background == self.background:
                self.colors.pop(f"{row},{col}", None)
            else:
                self.colors[f"{row},{col}"] = [foreground, background]

    def cell_colors(self, row: int, col: int) -> tuple[int, int]:
        pair = self.colors.get(f"{row},{col}")
        if pair:
            return pair[0], pair[1]
        return self.foreground, self.background

    @property
    def enabled(self) -> bool:
        return any(line.strip() for line in self.lines)

    def to_dict(self) -> dict[str, Any]:
        return {"lines": list(self.lines), "foreground": self.foreground,
                "background": self.background, "colors": dict(self.colors)}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BannerScreen":
        if not data:
            return cls()
        colors = {str(key): [int(pair[0]), int(pair[1])]
                  for key, pair in (data.get("colors") or {}).items()}
        return cls(lines=[str(line) for line in data.get("lines", [])],
                   foreground=int(data.get("foreground", 15)),
                   background=int(data.get("background", 1)),
                   colors=colors)


@dataclass
class AppMenu:
    """Un menu dell'applicazione, con il suo titolo e il flusso."""

    title: str = "MAIN MENU"
    flow: str = "Return"
    columns: str = "Single"
    spacing: str = "Single"
    items: list["AppItem"] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = (self.title or "MAIN MENU")[:40]
        if self.flow not in FLOWS:
            raise AppError(f"Unknown menu flow: {self.flow}")
        if self.columns not in COLUMNS:
            raise AppError(f"Unknown menu columns: {self.columns}")
        if self.spacing not in SPACINGS:
            raise AppError(f"Unknown menu spacing: {self.spacing}")

    def item_by_hotkey(self, letter: str) -> "AppItem | None":
        needle = letter.upper()
        for item in self.items:
            hot = hot_letter(item.text)
            if hot == needle:
                return item
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "flow": self.flow,
                "columns": self.columns, "spacing": self.spacing,
                "items": [item.to_dict() for item in self.items]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppMenu":
        return cls(title=str(data.get("title", "MAIN MENU")),
                   flow=str(data.get("flow", "Return")),
                   columns=str(data.get("columns", "Single")),
                   spacing=str(data.get("spacing", "Single")),
                   items=[AppItem.from_dict(item)
                          for item in data.get("items", [])])


@dataclass
class AppItem:
    """Voce di menu: testo, aiuto, azione e destinazione."""

    text: str = "Undefined menu choice"
    help_line: str = ""
    action: str = "Macro"
    target: str = ""
    macro: str = ""
    password_hash: str = ""
    help_file: str = ""
    submenu: AppMenu | None = None

    def __post_init__(self) -> None:
        self.text = (self.text or "Undefined menu choice")[:60]
        self.help_line = (self.help_line or "")[:79]
        if self.action not in ACTIONS:
            raise AppError(f"Unknown menu action: {self.action}")
        if len(self.macro) > MAX_MACRO:
            raise AppError(f"A macro is limited to {MAX_MACRO} characters.")
        if self.action == "Sub-Menu" and self.submenu is None:
            self.submenu = AppMenu(title=self.target or self.text)

    @property
    def password_protected(self) -> bool:
        return bool(self.password_hash)

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "help_line": self.help_line,
                "action": self.action, "target": self.target,
                "macro": self.macro, "password_hash": self.password_hash,
                "help_file": self.help_file,
                "submenu": self.submenu.to_dict() if self.submenu else None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppItem":
        return cls(text=str(data.get("text", "")),
                   help_line=str(data.get("help_line", "")),
                   action=str(data.get("action", "Macro")),
                   target=str(data.get("target", "")),
                   macro=str(data.get("macro", "")),
                   password_hash=str(data.get("password_hash", "")),
                   help_file=str(data.get("help_file", "")),
                   submenu=(AppMenu.from_dict(data["submenu"])
                            if data.get("submenu") else None))


def hot_letter(text: str) -> str:
    for char in text:
        if char.isalpha() and char.isupper():
            return char
    for char in text:
        if char.isalpha():
            return char.upper()
    return ""


@dataclass
class Application:
    """Un'applicazione completa."""

    name: str
    description: str = ""
    startup: str = ""
    startup_macro: str = ""
    script_path: str = ""
    banner_enabled: bool = True
    allow_escape: str = "Yes"
    escape_password_hash: str = ""
    menu: AppMenu = field(default_factory=AppMenu)
    banner: BannerScreen = field(default_factory=BannerScreen)
    updated: float = 0.0

    def __post_init__(self) -> None:
        self.name = normalize_app_name(self.name)
        self.description = (self.description or "")[:60]
        if self.allow_escape not in ALLOW_ESCAPE:
            raise AppError(f"Unknown escape option: {self.allow_escape}")
        if len(self.startup_macro) > MAX_MACRO:
            raise AppError(f"A macro is limited to {MAX_MACRO} characters.")

    @property
    def label(self) -> str:
        return f"{self.name} - {self.description or 'Application'}"

    def validate(self) -> None:
        def check(menu: AppMenu, depth: int) -> None:
            if depth > MAX_LEVELS:
                raise AppError("Applications nest at most 10 menus deep.")
            for item in menu.items:
                if item.action == "Sub-Menu":
                    if item.submenu is None:
                        raise AppError(f"Menu {item.text} has no sub-menu.")
                    check(item.submenu, depth + 1)
                elif item.action in ("Call-App", "GotO-App") and not item.target:
                    raise AppError(f"{item.text} needs an application name.")

        check(self.menu, 0)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description,
                "startup": self.startup, "startup_macro": self.startup_macro,
                "script_path": self.script_path,
                "banner_enabled": self.banner_enabled,
                "allow_escape": self.allow_escape,
                "escape_password_hash": self.escape_password_hash,
                "menu": self.menu.to_dict(), "banner": self.banner.to_dict(),
                "updated": self.updated}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Application":
        return cls(name=str(data.get("name", "")),
                   description=str(data.get("description", "")),
                   startup=str(data.get("startup", "")),
                   startup_macro=str(data.get("startup_macro", "")),
                   script_path=str(data.get("script_path", "")),
                   banner_enabled=bool(data.get("banner_enabled", True)),
                   allow_escape=str(data.get("allow_escape", "Yes")),
                   escape_password_hash=str(
                       data.get("escape_password_hash", "")),
                   menu=AppMenu.from_dict(data.get("menu") or {}),
                   banner=BannerScreen.from_dict(data.get("banner")),
                   updated=float(data.get("updated", 0.0)))


@dataclass(frozen=True)
class OutlineRow:
    """Riga dell'outline: intestazione di menu oppure voce."""

    depth: int
    kind: str  # "menu" | "item"
    menu: AppMenu
    item: AppItem | None = None

    @property
    def text(self) -> str:
        if self.kind == "menu":
            return "= " + self.menu.title
        assert self.item is not None
        return self.item.text


def outline(app: Application) -> list[OutlineRow]:
    """Appiattisce l'albero per l'editor: intestazioni e voci indentate."""
    rows: list[OutlineRow] = []

    def walk(menu: AppMenu, depth: int) -> None:
        rows.append(OutlineRow(depth, "menu", menu))
        for item in menu.items:
            rows.append(OutlineRow(depth + 1, "item", menu, item))
            if item.action == "Sub-Menu" and item.submenu is not None:
                walk(item.submenu, depth + 1)

    walk(app.menu, 0)
    return rows


def find_menu(app: Application, title: str) -> AppMenu | None:
    def walk(menu: AppMenu) -> AppMenu | None:
        if menu.title == title:
            return menu
        for item in menu.items:
            if item.submenu is not None:
                found = walk(item.submenu)
                if found is not None:
                    return found
        return None

    return walk(app.menu)


__all__ = [
    "ACTIONS", "ALLOW_ESCAPE", "AppError", "AppItem", "AppMenu",
    "Application", "BannerScreen", "COLUMNS", "FLOWS", "MAX_APPS",
    "MAX_LEVELS", "MAX_MACRO", "OutlineRow", "SPACINGS", "check_password",
    "find_menu", "hot_letter", "normalize_app_name", "outline",
    "password_hash",
]
