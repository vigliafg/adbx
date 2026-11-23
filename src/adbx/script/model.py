"""Modello degli script di Alpha Four: keystroke, dialog box e menu bar.

I tre tipi condividono nome (8.3) e descrizione, ma hanno contenuti diversi:

* **keystroke** — una sequenza di tasti e comandi, con un eventuale
  *Screen Test*;
* **dialog box** — una finestra con controlli Prompt, Button e Display;
* **menu bar** — le voci di un menu personalizzato per form e browse table.

Il modello è indipendente dalla UI e dalla persistenza: si serializza in JSON
leggibile, così gli script restano ispezionabili e trasferibili.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SCRIPT_NAME_RE = re.compile(r"^[A-Z0-9_]{1,8}$|^[A-Z0-9_]{1,7}!$")
MAX_SCRIPT_CHARS = 3000
MAX_COMMAND_CHARS = 1000
MAX_VARIABLES = 10_000
MAX_DIALOG_CONTROLS = 128
MAX_MENU_ITEMS = 64

KIND_KEYSTROKE = "keystroke"
KIND_DIALOG = "dialog"
KIND_MENU = "menu"
SCRIPT_KINDS = (KIND_KEYSTROKE, KIND_DIALOG, KIND_MENU)
KIND_LABELS = {
    KIND_KEYSTROKE: "Keystroke",
    KIND_DIALOG: "Dialog Box",
    KIND_MENU: "Menu Bar",
}

CONTROL_PROMPT = "Prompt"
CONTROL_BUTTON = "Button"
CONTROL_DISPLAY = "Display"
CONTROL_TYPES = (CONTROL_PROMPT, CONTROL_BUTTON, CONTROL_DISPLAY)


class ScriptError(ValueError):
    """Script non valido: nome, dimensione, comando o definizione."""


def normalize_name(name: str) -> str:
    """Nome script DOS 8.3, maiuscolo, senza estensione."""
    text = name.strip().upper()
    if text.endswith(".SCP"):
        text = text[:-4]
    if not SCRIPT_NAME_RE.match(text):
        raise ScriptError("Script names have 1-8 letters, digits or _.")
    return text


@dataclass
class ScreenTest:
    """Testo che deve comparire sullo schermo prima del playback.

    Il manuale marca un'area rettangolare; qui si conservano le righe attese
    e, se nota, l'area. Il confronto è case-insensitive e ignora gli spazi
    iniziali e finali di ogni riga.
    """

    lines: list[str] = field(default_factory=list)
    top: int = 0
    left: int = 0
    bottom: int = 0
    right: int = 0

    @property
    def enabled(self) -> bool:
        return bool([line for line in self.lines if line.strip()])

    @classmethod
    def from_text(cls, text: str) -> "ScreenTest":
        lines = [line.strip() for line in text.replace("\r", "").split("\n")]
        return cls(lines=[line for line in lines if line])

    def matches(self, screen_lines: list[str]) -> bool:
        if not self.enabled:
            return True
        haystack = [" ".join(line.split()).upper() for line in screen_lines]
        for line in self.lines:
            needle = " ".join(line.split()).upper()
            if not needle:
                continue
            if not any(needle in item for item in haystack):
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {"lines": list(self.lines), "top": self.top, "left": self.left,
                "bottom": self.bottom, "right": self.right}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ScreenTest":
        if not data:
            return cls()
        return cls(lines=[str(item) for item in data.get("lines", [])],
                   top=int(data.get("top", 0)), left=int(data.get("left", 0)),
                   bottom=int(data.get("bottom", 0)),
                   right=int(data.get("right", 0)))


@dataclass
class DialogControl:
    """Controllo di un dialog box: Prompt, Button o Display."""

    kind: str = CONTROL_PROMPT
    row: int = 3
    col: int = 2
    width: int = 20
    label: str = ""
    variable: str = ""
    length: int = 20
    default: str = ""
    action: str = ""
    color: int = 0

    def __post_init__(self) -> None:
        if self.kind not in CONTROL_TYPES:
            raise ScriptError(f"Unknown dialog control: {self.kind}")
        self.row = max(1, int(self.row))
        self.col = max(1, int(self.col))
        self.width = max(1, min(70, int(self.width)))
        self.length = max(1, min(254, int(self.length)))
        self.variable = normalize_variable(self.variable)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "row": self.row, "col": self.col,
            "width": self.width, "label": self.label,
            "variable": self.variable, "length": self.length,
            "default": self.default, "action": self.action,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogControl":
        return cls(kind=str(data.get("kind", CONTROL_PROMPT)),
                   row=int(data.get("row", 3)), col=int(data.get("col", 2)),
                   width=int(data.get("width", 20)),
                   label=str(data.get("label", "")),
                   variable=str(data.get("variable", "")),
                   length=int(data.get("length", 20)),
                   default=str(data.get("default", "")),
                   action=str(data.get("action", "")),
                   color=int(data.get("color", 0)))


def normalize_variable(name: str) -> str:
    """Nome variabile canonico `%NOME`; stringa vuota ammessa."""
    text = (name or "").strip().upper()
    if not text:
        return ""
    if not text.startswith("%"):
        text = "%" + text
    body = text[1:]
    if not re.match(r"^[A-Z0-9_]{1,24}$", body):
        raise ScriptError("Variable names have 1-24 letters, digits or _.")
    return text


@dataclass
class DialogBox:
    """Definizione di un dialog box."""

    title: str = ""
    row: int = 4
    col: int = 10
    height: int = 10
    width: int = 48
    foreground: int = 7
    background: int = 1
    border: int = 3
    shadow: bool = True
    no_clear: bool = False
    controls: list[DialogControl] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.row = max(1, min(40, int(self.row)))
        self.col = max(1, min(130, int(self.col)))
        self.height = max(4, min(38, int(self.height)))
        self.width = max(12, min(128, int(self.width)))
        if len(self.controls) > MAX_DIALOG_CONTROLS:
            raise ScriptError("A dialog box has at most 128 controls.")
        for control in self.controls:
            self._fit(control)

    def _fit(self, control: DialogControl) -> None:
        control.row = max(1, min(self.height - 2, control.row))
        control.col = max(1, min(self.width - 2, control.col))
        control.width = max(1, min(self.width - control.col - 1, control.width))

    def add(self, control: DialogControl) -> DialogControl:
        if len(self.controls) >= MAX_DIALOG_CONTROLS:
            raise ScriptError("A dialog box has at most 128 controls.")
        self._fit(control)
        self.controls.append(control)
        return control

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.controls):
            self.controls.pop(index)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title, "row": self.row, "col": self.col,
            "height": self.height, "width": self.width,
            "foreground": self.foreground, "background": self.background,
            "border": self.border, "shadow": self.shadow,
            "no_clear": self.no_clear,
            "controls": [control.to_dict() for control in self.controls],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DialogBox":
        if not data:
            return cls()
        return cls(title=str(data.get("title", "")),
                   row=int(data.get("row", 4)), col=int(data.get("col", 10)),
                   height=int(data.get("height", 10)),
                   width=int(data.get("width", 48)),
                   foreground=int(data.get("foreground", 7)),
                   background=int(data.get("background", 1)),
                   border=int(data.get("border", 3)),
                   shadow=bool(data.get("shadow", True)),
                   no_clear=bool(data.get("no_clear", False)),
                   controls=[DialogControl.from_dict(item)
                             for item in data.get("controls", [])])


@dataclass
class MenuItem:
    """Voce di un menu bar personalizzato."""

    key: str = "F10"
    label: str = "Continue"
    action: str = "{ENTER}"
    standard: bool = True

    def __post_init__(self) -> None:
        self.key = self.key.strip().upper() or "F10"
        self.label = self.label.strip() or self.key

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "label": self.label,
                "action": self.action, "standard": self.standard}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MenuItem":
        return cls(key=str(data.get("key", "F10")),
                   label=str(data.get("label", "Continue")),
                   action=str(data.get("action", "{ENTER}")),
                   standard=bool(data.get("standard", True)))


@dataclass
class MenuBarScript:
    """Menu bar alternativo per un form o una browse table."""

    items: list[MenuItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.items) > MAX_MENU_ITEMS:
            raise ScriptError("A menu bar has at most 64 items.")

    def add(self, item: MenuItem) -> MenuItem:
        if len(self.items) >= MAX_MENU_ITEMS:
            raise ScriptError("A menu bar has at most 64 items.")
        self.items.append(item)
        return item

    def to_dict(self) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in self.items]}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MenuBarScript":
        if not data:
            return cls()
        return cls(items=[MenuItem.from_dict(item)
                          for item in data.get("items", [])])


@dataclass
class Script:
    """Uno script completo, di uno dei tre tipi."""

    name: str
    description: str = ""
    kind: str = KIND_KEYSTROKE
    source: str = ""
    screen_test: ScreenTest = field(default_factory=ScreenTest)
    dialog: DialogBox | None = None
    menu: MenuBarScript | None = None
    updated: float = 0.0

    def __post_init__(self) -> None:
        self.name = normalize_name(self.name)
        if self.kind not in SCRIPT_KINDS:
            raise ScriptError(f"Unknown script type: {self.kind}")
        self.description = self.description[:80]
        if len(self.source) > MAX_SCRIPT_CHARS:
            raise ScriptError(
                f"Scripts are limited to {MAX_SCRIPT_CHARS} characters.")
        if self.kind == KIND_DIALOG and self.dialog is None:
            self.dialog = DialogBox()
        if self.kind == KIND_KEYSTROKE and self.dialog is not None:
            self.dialog = None
        if self.kind == KIND_MENU and self.menu is None:
            self.menu = MenuBarScript()

    @property
    def kind_label(self) -> str:
        return KIND_LABELS[self.kind]

    @property
    def playable(self) -> bool:
        return self.kind != KIND_MENU

    @property
    def has_screen_test(self) -> bool:
        return self.screen_test.enabled

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "description": self.description,
            "kind": self.kind, "source": self.source,
            "screen_test": self.screen_test.to_dict(),
            "dialog": self.dialog.to_dict() if self.dialog else None,
            "menu": self.menu.to_dict() if self.menu else None,
            "updated": self.updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Script":
        return cls(name=str(data.get("name", "")),
                   description=str(data.get("description", "")),
                   kind=str(data.get("kind", KIND_KEYSTROKE)),
                   source=str(data.get("source", "")),
                   screen_test=ScreenTest.from_dict(data.get("screen_test")),
                   dialog=(DialogBox.from_dict(data.get("dialog"))
                           if data.get("dialog") is not None else None),
                   menu=(MenuBarScript.from_dict(data.get("menu"))
                         if data.get("menu") is not None else None),
                   updated=float(data.get("updated", 0.0)))


__all__ = [
    "CONTROL_BUTTON", "CONTROL_DISPLAY", "CONTROL_PROMPT", "CONTROL_TYPES",
    "DialogBox", "DialogControl", "KIND_DIALOG", "KIND_KEYSTROKE",
    "KIND_LABELS", "KIND_MENU", "MAX_COMMAND_CHARS", "MAX_DIALOG_CONTROLS",
    "MAX_MENU_ITEMS", "MAX_SCRIPT_CHARS", "MenuItem", "MenuBarScript",
    "SCRIPT_KINDS", "SCRIPT_NAME_RE", "Script", "ScriptError", "ScreenTest",
    "normalize_name", "normalize_variable",
]
