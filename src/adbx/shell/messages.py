"""Messaggi comuni del guscio, in uno stile unico.

Le schermate possono ancora comporre messaggi specifici, ma i testi generali
(selezione mancante, protezione, disponibilità, esito) passano da qui: una
sola formulazione, una sola punteggiatura, nessuno spazio doppio.
"""

from __future__ import annotations

SELECT_FIRST = "Select a database or set first."
OPEN_FIRST = "Open a database or set first."
NO_SCRIPTS = "There are no scripts in the script path."
NO_APPLICATIONS = "There are no applications in this directory."
NOT_AVAILABLE = "This command is not available yet (wave {wave})."


def protected(kind: str, owner: str) -> str:
    return (f"{kind} for {owner} are protected. "
            "Use Applications, Prevent/allow file alterations.")


def unavailable(feature: str, wave: str) -> str:
    return f"{feature} is not available yet (wave {wave})."


def saved(name: str) -> str:
    return f"{name} saved."


def erased(name: str) -> str:
    return f"{name} erased."


def error(action: str, detail: str) -> str:
    return f"Cannot {action}: {detail}."


def check_style(text: str) -> str:
    """Normalizza gli spazi e assicura il punto finale."""
    body = " ".join(text.split())
    if body and body[-1] not in ".!?":
        body += "."
    return body


__all__ = [
    "NO_APPLICATIONS", "NO_SCRIPTS", "NOT_AVAILABLE", "OPEN_FIRST",
    "SELECT_FIRST", "check_style", "erased", "error", "protected",
    "saved", "unavailable",
]
