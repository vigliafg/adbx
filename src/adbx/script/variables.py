"""Variabili di script: `%NOME`, indirezione `@`, persistenza `.VAR`.

Una variabile ha nome lungo al massimo 24 caratteri e valore character di
al massimo 254. I valori sono sempre testo, come nel manuale; le conversioni
avvengono nelle espressioni. Le variabili di sistema sono normali variabili
con prefisso `%SYS_`, create dal motore all'avvio o dall'host.

La persistenza usa un file di testo leggibile, una variabile per riga:

    %NOME=valore

I caratteri di controllo e i ritorni a capo nel valore sono codificati con
`\\n`, `\\r` e `\\\\`, così il file resta una riga per variabile.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .model import ScriptError

NAME_RE = re.compile(r"^[A-Z0-9_]{1,24}$")
REFERENCE_RE = re.compile(r"@?%[A-Za-z0-9_]+")
MAX_VALUE = 254


def clean_name(name: str) -> str:
    text = name.strip().upper()
    if text.startswith("@"):
        text = text[1:]
    if text.startswith("%"):
        text = text[1:]
    if not NAME_RE.match(text):
        raise ScriptError("Variable names have 1-24 letters, digits or _.")
    return text


class Variables:
    """Archivio delle variabili di una sessione di script."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._values: dict[str, str] = {}
        for name, value in (values or {}).items():
            self.set(name, value)

    def __len__(self) -> int:
        return len(self._values)

    def __contains__(self, name: str) -> bool:
        try:
            return clean_name(name) in self._values
        except ScriptError:
            return False

    def names(self) -> list[str]:
        return sorted(self._values)

    def items(self) -> list[tuple[str, str]]:
        return [(f"%{name}", self._values[name]) for name in self.names()]

    def get(self, name: str, default: str = "") -> str:
        """Valore della variabile, con indirezione `@`."""
        text = name.strip()
        indirect = text.startswith("@")
        try:
            key = clean_name(text)
        except ScriptError:
            return default
        value = self._values.get(key, default)
        if indirect and value:
            target = value.strip()
            if target.startswith("%"):
                try:
                    return self._values.get(clean_name(target), default)
                except ScriptError:
                    return default
        return value

    def raw(self, name: str) -> str:
        """Valore memorizzato, senza applicare l'indirezione `@`."""
        try:
            return self._values.get(clean_name(name), "")
        except ScriptError:
            return ""

    def set(self, name: str, value: str) -> None:
        key = clean_name(name)
        text = "" if value is None else str(value)
        if len(text) > MAX_VALUE:
            text = text[:MAX_VALUE]
        self._values[key] = text

    def delete(self, name: str) -> bool:
        try:
            key = clean_name(name)
        except ScriptError:
            return False
        return self._values.pop(key, None) is not None

    def clear(self, pattern: str = "%*") -> int:
        """Cancella le variabili che corrispondono al pattern (`*`, `?`)."""
        wildcard = pattern.strip().upper() or "%*"
        if not wildcard.startswith("%"):
            wildcard = "%" + wildcard
        regex = "^" + re.escape(wildcard.replace("%", "", 1)) \
            .replace(r"\*", ".*").replace(r"\?", ".") + "$"
        matcher = re.compile(regex, re.IGNORECASE)
        removed = [name for name in self._values if matcher.match(name)]
        for name in removed:
            del self._values[name]
        return len(removed)

    def expand(self, text: str) -> str:
        """Sostituisce i riferimenti con i valori, indirezione compresa."""
        if not text or "%" not in text:
            return text

        def replace(match: re.Match[str]) -> str:
            return self.get(match.group(0))

        # Prima l'indirezione, poi i riferimenti semplici: il valore di
        # `@%X` può essere a sua volta `%Y`.
        result = re.sub(r"@%[A-Za-z0-9_]+", replace, text)
        return re.sub(r"%[A-Za-z0-9_]+", replace, result)

    def expand_expression(self, text: str) -> str:
        """Sostituisce i riferimenti con letterali adatti al valutatore."""
        if not text or "%" not in text:
            return text

        def replace(match: re.Match[str]) -> str:
            value = self.get(match.group(0))
            return expression_literal(value)

        return re.sub(r"@?%[A-Za-z0-9_]+", replace, text)

    def resolve_target(self, name: str) -> str:
        """Nome canonico, risolvendo `@%X` al valore di `%X`."""
        text = name.strip()
        if text.startswith("@") and text[1:].startswith("%"):
            value = self.get(text)
            if not value:
                return ""
            return "%" + clean_name(value)
        return "%" + clean_name(text)

    def save(self, path: Path, pattern: str = "%*") -> int:
        wildcard = pattern.strip().upper() or "%*"
        if not wildcard.startswith("%"):
            wildcard = "%" + wildcard
        regex = "^" + re.escape(wildcard.replace("%", "", 1)) \
            .replace(r"\*", ".*").replace(r"\?", ".") + "$"
        matcher = re.compile(regex, re.IGNORECASE)
        selected = [name for name in self.names() if matcher.match(name)]
        lines = []
        for name in selected:
            value = self._values[name]
            encoded = value.replace("\\", "\\\\").replace("\n", "\\n") \
                .replace("\r", "\\r")
            lines.append(f"%{name}={encoded}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + ("\n" if lines else ""),
                        encoding="utf-8")
        return len(lines)

    def load(self, path: Path) -> int:
        text = path.read_text(encoding="utf-8", errors="replace")
        count = 0
        for line in text.splitlines():
            if not line.startswith("%") or "=" not in line:
                continue
            name, _, encoded = line.partition("=")
            value = encoded.replace("\\n", "\n").replace("\\r", "\r") \
                .replace("\\\\", "\\")
            try:
                self.set(name, value)
                count += 1
            except ScriptError:
                continue
        return count

    @classmethod
    def from_items(cls, items: Iterable[tuple[str, str]]) -> "Variables":
        result = cls()
        for name, value in items:
            result.set(name, value)
        return result


def expression_literal(value: str) -> str:
    """Converte un valore character nel letterale di un'espressione."""
    text = value or ""
    stripped = text.strip()
    if stripped.upper() in (".T.", ".F.", "T", "F"):
        return ".T." if stripped.upper() in (".T.", "T") else ".F."
    if re.match(r"^-?\d+(\.\d+)?$", stripped):
        return stripped
    if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", stripped):
        return "{" + stripped + "}"
    return '"' + text.replace('"', '""') + '"'


__all__ = ["MAX_VALUE", "NAME_RE", "Variables", "clean_name",
           "expression_literal"]
