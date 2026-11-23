"""Prevent/allow file alterations per database o set.

Le protezioni sono impostazioni del workspace, una per proprietario, salvate
come JSON nella tabella `adbx_settings`. Non modificano i file: bloccano
l'apertura dei designer finché la protezione non viene tolta.
"""

from __future__ import annotations

import json

PROTECTION_TYPES = (
    "Forms", "Browse tables", "Reports", "Mail labels", "Letters",
    "Ranges", "Search/Sort lists", "Field rules",
)


def _key(owner: str) -> str:
    return f"protect:{owner.strip().upper()}"


def protected_types(workspace, owner: str) -> set[str]:
    raw = workspace.setting(_key(owner), "")
    if not raw:
        return set()
    try:
        data = json.loads(raw)
    except ValueError:
        return set()
    return {str(item) for item in data if str(item) in PROTECTION_TYPES}


def is_protected(workspace, owner: str, kind: str) -> bool:
    return kind in protected_types(workspace, owner)


def set_protection(workspace, owner: str, kind: str, prevent: bool) -> None:
    if kind not in PROTECTION_TYPES:
        raise ValueError(f"Unknown protection type: {kind}")
    current = protected_types(workspace, owner)
    if prevent:
        current.add(kind)
    else:
        current.discard(kind)
    workspace.set_setting(_key(owner), json.dumps(sorted(current)))


def toggle_protection(workspace, owner: str, kind: str) -> bool:
    value = not is_protected(workspace, owner, kind)
    set_protection(workspace, owner, kind, value)
    return value


__all__ = ["PROTECTION_TYPES", "is_protected", "protected_types",
           "set_protection", "toggle_protection"]
