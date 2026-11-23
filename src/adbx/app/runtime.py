"""Esecuzione di un'applicazione: stato dei menu, azioni e password.

Il runtime non conosce la UI: espone il menu corrente, il movimento, la
selezione e una richiesta (`request`) che il controller interpreta (macro,
sottomenu, Call-App, GotO-App, password, uscita). Così la simulazione e
l'esecuzione reale condividono esattamente lo stesso codice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import (
    MAX_LEVELS,
    AppItem,
    Application,
    AppMenu,
    check_password,
)
from .store import ApplicationStore


@dataclass
class Frame:
    menu: AppMenu
    index: int = 0


@dataclass
class ApplicationRuntime:
    app: Application
    store: ApplicationStore
    simulate: bool = False
    frames: list[Frame] = field(default_factory=list)
    call_stack: list[tuple[Application, list[Frame]]] = field(
        default_factory=list)
    status: str = ""
    request: str = ""
    requested_item: AppItem | None = None
    requested_app: str = ""
    banner_done: bool = False
    closed: bool = False

    def __post_init__(self) -> None:
        if not self.frames:
            self.frames = [Frame(self.app.menu)]

    @property
    def menu(self) -> AppMenu:
        return self.frames[-1].menu

    @property
    def index(self) -> int:
        return self.frames[-1].index

    @index.setter
    def index(self, value: int) -> None:
        self.frames[-1].index = value

    @property
    def item(self) -> AppItem | None:
        if 0 <= self.index < len(self.menu.items):
            return self.menu.items[self.index]
        return None

    @property
    def help_line(self) -> str:
        item = self.item
        return item.help_line if item is not None else self.status

    @property
    def nested(self) -> int:
        return len(self.frames) - 1

    def move(self, delta: int) -> None:
        if not self.menu.items:
            return
        self.index = (self.index + delta) % len(self.menu.items)
        self.status = ""

    def select(self, letter: str) -> bool:
        item = self.menu.item_by_hotkey(letter)
        if item is None:
            return False
        self.index = self.menu.items.index(item)
        self.activate()
        return True

    def activate(self) -> str:
        """Attiva la voce corrente; ritorna il tipo di richiesta."""
        item = self.item
        self.request = ""
        self.requested_item = None
        if item is None:
            self.status = "This menu has no choices."
            return ""
        if item.password_protected:
            self.request = "password"
            self.requested_item = item
            return self.request
        return self._perform(item)

    def provide_password(self, password: str) -> str:
        item = self.requested_item
        if item is None:
            return ""
        if not check_password(item.password_hash, password):
            self.status = "Incorrect password."
            self.request = ""
            self.requested_item = None
            return ""
        self.request = ""
        self.requested_item = None
        return self._perform(item)

    def _perform(self, item: AppItem) -> str:
        if self.simulate and item.action != "Sub-Menu":
            self.status = f"Simulation: {item.action} {item.target or item.text}"
            return ""
        if item.action == "Sub-Menu" and item.submenu is not None:
            self.frames.append(Frame(item.submenu))
            self.status = ""
            return "submenu"
        if item.action == "Macro":
            self.request = "macro"
            self.requested_item = item
            return self.request
        if item.action == "Call-App":
            self.request = "call"
            self.requested_item = item
            self.requested_app = item.target
            return self.request
        if item.action == "GotO-App":
            self.request = "goto"
            self.requested_item = item
            self.requested_app = item.target
            return self.request
        return ""

    def after_action(self) -> None:
        flow = self.menu.flow
        if flow == "Advance":
            if self.menu.items:
                self.index = min(len(self.menu.items) - 1, self.index + 1)
        elif flow == "Return" and len(self.frames) > 1:
            self.frames.pop()

    def back(self) -> str:
        """ESC: chiude il sottomenu o chiede di uscire dall'applicazione."""
        self.request = ""
        if len(self.frames) > 1:
            self.frames.pop()
            return "submenu"
        if self.app.allow_escape == "Yes":
            self.request = "exit"
        elif self.app.allow_escape == "Password":
            self.request = "escape-password"
        else:
            self.status = "Escape is disabled. Use an application exit."
        return self.request

    def escape_password(self, password: str) -> bool:
        if check_password(self.app.escape_password_hash, password):
            self.request = "exit"
            return True
        self.status = "Incorrect password."
        return False

    # -- applicazioni annidate -------------------------------------------
    def call(self, name: str) -> bool:
        if len(self.call_stack) >= MAX_LEVELS:
            self.status = "Applications nest at most 10 levels."
            return False
        target = self.store.get(name, missing_ok=True)
        if target is None:
            self.status = f"Application {name} not found."
            return False
        self.call_stack.append((self.app, self.frames))
        self.app = target
        self.frames = [Frame(target.menu)]
        self.status = f"Called {target.name}."
        return True

    def go_to(self, name: str) -> bool:
        target = self.store.get(name, missing_ok=True)
        if target is None:
            self.status = f"Application {name} not found."
            return False
        self.app = target
        self.frames = [Frame(target.menu)]
        self.call_stack.clear()
        self.status = f"Went to {target.name}."
        return True

    def return_from_call(self) -> bool:
        if not self.call_stack:
            return False
        self.app, self.frames = self.call_stack.pop()
        self.status = f"Returned to {self.app.name}."
        return True

    def current_item(self) -> AppItem | None:
        return self.item


__all__ = ["ApplicationRuntime", "Frame"]
