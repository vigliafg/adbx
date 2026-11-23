"""Browser di directory: elenco di database e set come in Alpha Four.

Legge il filesystem vero e produce una lista già filtrata e ordinata. La
logica è pura (nessun accesso a Qt) così può essere testata e riusata dagli
script di accettazione.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ..data.dbf import DbfError, read_header

DEFAULT_TYPES = ("SET", "DBF")
PARENT_LABEL = "<Parent>"


@dataclass(frozen=True)
class Entry:
    name: str
    kind: str  # "parent" | "dir" | "drive" | "file"
    path: Path
    ext: str = ""
    date: str = ""
    records: int | None = None
    fields: int | None = None

    @property
    def is_file(self) -> bool:
        return self.kind == "file"

    @property
    def selectable_text(self) -> str:
        """Testo che finisce nel campo nome quando la riga è evidenziata."""
        if self.kind == "file":
            return str(self.path)
        return str(self.path / "*")


@dataclass
class Listing:
    directory: Path
    pattern: str = "*"
    entries: list[Entry] = field(default_factory=list)
    error: str | None = None

    @property
    def path_text(self) -> str:
        return str(self.directory / self.pattern) if self.pattern != "*" else str(self.directory / "*")

    def files(self) -> list[Entry]:
        return [entry for entry in self.entries if entry.is_file]

    def index_of(self, path: Path) -> int:
        for index, entry in enumerate(self.entries):
            if entry.path == path:
                return index
        return -1


def _format_date(value: date) -> str:
    return f"{value.month:02d}/{value.day:02d}/{value.year:04d}"


def _mtime(path: Path) -> str:
    try:
        return _format_date(date.fromtimestamp(path.stat().st_mtime))
    except OSError:
        return ""


def _matches(filename: str, pattern: str) -> bool:
    """Confronto DOS: maiuscole indifferenti, pattern largo o con estensione."""
    pattern = pattern or "*"
    if "." in pattern or "?" in pattern:
        return fnmatch.fnmatch(filename.upper(), pattern.upper())
    stem = filename.rsplit(".", 1)[0]
    return fnmatch.fnmatch(stem.upper(), pattern.upper())


def scan(directory: str | Path, pattern: str = "*",
         types: tuple[str, ...] = DEFAULT_TYPES) -> Listing:
    """Elenca set/database e sottodirectory della cartella."""
    directory = Path(directory).expanduser()
    listing = Listing(directory=directory, pattern=pattern or "*")
    try:
        children = list(directory.iterdir())
    except OSError as exc:
        listing.error = f"Cannot open {directory}: {exc.strerror or exc}"
        return listing

    parent = directory.parent
    if parent != directory:
        listing.entries.append(Entry(PARENT_LABEL, "parent", parent))

    directories = []
    files = []
    suffixes = {"." + item.upper() for item in types}
    for child in children:
        try:
            if child.name.startswith("."):
                continue
            if child.is_dir():
                if _matches(child.name, listing.pattern):
                    directories.append(Entry(child.name.upper(), "dir", child,
                                             date=_mtime(child)))
                continue
            suffix = child.suffix.upper()
            if suffix not in suffixes:
                continue
            if not _matches(child.name, listing.pattern):
                continue
            display = child.stem.upper()
            if suffix == ".DBF":
                try:
                    header = read_header(child)
                except DbfError:
                    files.append(Entry(display, "file", child, ext="DBF",
                                       date=_mtime(child)))
                else:
                    files.append(Entry(
                        display, "file", child, ext="DBF", date=_mtime(child),
                        records=header.records, fields=header.field_count,
                    ))
            else:
                files.append(Entry(display, "file", child, ext=suffix.lstrip("."),
                                   date=_mtime(child)))
        except OSError:
            continue

    directories.sort(key=lambda entry: entry.name.upper())
    files.sort(key=lambda entry: (entry.name.upper(), entry.ext))
    listing.entries.extend(directories)
    listing.entries.extend(files)
    return listing


def siblings(path: str | Path, pattern: str = "*",
             types: tuple[str, ...] = DEFAULT_TYPES) -> Listing:
    return scan(Path(path).parent, pattern, types)


def strip_wildcard(text: str) -> tuple[str, str | None]:
    """Divide `C:\\DATA\\*` in cartella e pattern; `None` se non c'è wildcard."""
    if not any(char in text for char in "*?"):
        return text, None
    expanded = os.path.expanduser(text)
    cut = max(expanded.rfind(os.sep), expanded.rfind("/"))
    if cut < 0:
        return "", expanded
    directory = expanded[:cut] or os.sep
    return directory, expanded[cut + 1:]


__all__ = [
    "DEFAULT_TYPES",
    "Entry",
    "Listing",
    "PARENT_LABEL",
    "scan",
    "siblings",
    "strip_wildcard",
]
