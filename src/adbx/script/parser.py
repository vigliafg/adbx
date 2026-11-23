"""Lettura di uno script: tasti, comandi e blocchi annidati.

Il formato è quello del manuale: i caratteri comuni sono tasti, le parentesi
graffe racchiudono comandi, `{* ... *}` è un commento e `:A` è una label.
Le graffe possono annidarsi (blocchi di `IF`, `CASE`, `ONKEY`), quindi la
scansione tiene un contatore di profondità e rispetta le stringhe fra
virgolette.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import MAX_COMMAND_CHARS, ScriptError


@dataclass(frozen=True)
class Token:
    kind: str  # "key" | "command"
    value: str
    position: int

    @property
    def is_comment(self) -> bool:
        return self.kind == "command" and self.value.lstrip().startswith("*")


def _starts_comment(text: str, index: int) -> bool:
    return index + 1 < len(text) and text[index] == "{" and text[index + 1] == "*"


def _scan_braces(text: str, start: int) -> tuple[str, int]:
    """Ritorna (contenuto, indice dopo la graffa) per una graffa aperta."""
    depth = 1
    index = start + 1
    quote = ""
    while index < len(text):
        char = text[index]
        if quote:
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ('"', "'"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
        index += 1
    raise ScriptError(f"Unclosed script command at character {start + 1}.")


def tokenize(source: str) -> list[Token]:
    """Scompone lo script in tasti e comandi, scartando i commenti."""
    tokens: list[Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char in "\r\n\t":
            index += 1
            continue
        if char == "{":
            content, after = _scan_braces(source, index)
            if len(content) > MAX_COMMAND_CHARS + 2:
                raise ScriptError(
                    f"Script commands are limited to {MAX_COMMAND_CHARS} "
                    "characters.")
            token = Token("command", content, index)
            if not token.is_comment:
                tokens.append(token)
            index = after
            continue
        if char == "}":
            raise ScriptError(f"Unexpected }} at character {index + 1}.")
        tokens.append(Token("key", char, index))
        index += 1
    return tokens


def split_args(text: str) -> list[str]:
    """Separa gli argomenti di un comando su virgole di primo livello."""
    args: list[str] = []
    current: list[str] = []
    depth = 0
    quote = ""
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ('"', "'"):
            quote = char
            current.append(char)
        elif char == "{":
            depth += 1
            current.append(char)
        elif char == "}":
            depth = max(0, depth - 1)
            current.append(char)
        elif char == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    args.append("".join(current).strip())
    return args


def command_name(raw: str) -> str:
    """Nome del comando, senza argomenti, in maiuscolo."""
    text = raw.strip()
    if not text:
        return ""
    end = 0
    while end < len(text) and (text[end].isalnum()
                               or text[end] in "_@%"):
        end += 1
    return text[:end].upper()


def command_body(raw: str) -> str:
    """Testo dopo il nome del comando, senza la virgola iniziale."""
    name = command_name(raw)
    return raw.strip()[len(name):].lstrip(" ,")


def unquote(text: str) -> str:
    """Toglie le virgolette esterne, se presenti e appaiate."""
    value = text.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        body = value[1:-1]
        quote = value[0]
        return body.replace(quote + quote, quote)
    return value


def is_block(text: str) -> bool:
    value = text.strip()
    return len(value) >= 2 and value.startswith("{") and value.endswith("}")


def block_body(text: str) -> str:
    value = text.strip()
    if is_block(value):
        return value[1:-1]
    return value


def find_labels(source: str) -> dict[str, int]:
    """Mappa `:A` → indice del token successivo alla label."""
    labels: dict[str, int] = {}
    tokens = tokenize(source)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "key" and token.value == ":" and index + 1 < len(tokens):
            following = tokens[index + 1]
            if following.kind == "key" and following.value.isalpha():
                labels[following.value.upper()] = index + 2
                index += 2
                continue
        index += 1
    return labels


__all__ = [
    "Token", "block_body", "command_body", "command_name", "find_labels",
    "is_block", "split_args", "tokenize", "unquote",
]
