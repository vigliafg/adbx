"""Stato del guscio: cartella corrente, database aperto, cronologia."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..data.dbf import DbfError, DbfField, DbfHeader, read_header
from .files import Entry, Listing, scan


@dataclass(frozen=True)
class CurrentFile:
    path: Path
    name: str
    ext: str
    records: int | None = None
    header: DbfHeader | None = None

    @property
    def fields(self) -> int | None:
        return self.header.field_count if self.header else None

    @property
    def index_label(self) -> str:
        return "by Record Number"


@dataclass
class ShellState:
    root: Path
    pattern: str = "*"
    detail: bool = False
    current: CurrentFile | None = None
    history: list[Path] = field(default_factory=list)
    listing: Listing | None = None

    # -- directory -------------------------------------------------------
    def refresh(self) -> Listing:
        self.listing = scan(self.root, self.pattern)
        return self.listing

    def change_directory(self, directory: str | Path, pattern: str = "*") -> None:
        path = Path(directory).expanduser()
        if not path.is_dir():
            raise NotADirectoryError(str(path))
        self.root = path.resolve()
        self.pattern = pattern or "*"
        self.refresh()

    # -- selezione -------------------------------------------------------
    def open(self, path: str | Path) -> CurrentFile:
        path = Path(path).expanduser()
        ext = path.suffix.lstrip(".").upper() or "DBF"
        if not path.exists() and not path.suffix:
            candidate = path.with_suffix(".DBF")
            if candidate.exists():
                path, ext = candidate, "DBF"
        if not path.exists():
            raise FileNotFoundError(str(path))
        if ext == "DBF":
            try:
                header = read_header(path)
            except DbfError:
                header = None
            current = CurrentFile(path.resolve(), path.stem.upper(), "DBF",
                                  records=header.records if header else None,
                                  header=header)
        else:
            current = CurrentFile(path.resolve(), path.stem.upper(), ext)
        self.current = current
        self.remember(path)
        return current

    def remember(self, path: str | Path) -> None:
        path = Path(path).resolve()
        self.history = [item for item in self.history if item != path]
        self.history.insert(0, path)
        del self.history[10:]

    # -- stato per le schermate -----------------------------------------
    @property
    def current_name(self) -> str:
        return self.current.name if self.current else ""

    @property
    def current_path_text(self) -> str:
        return str(self.current.path) if self.current else "(none)"

    @property
    def records_text(self) -> str:
        if not self.current or self.current.records is None:
            return ""
        return str(self.current.records)

    @property
    def default_types_text(self) -> str:
        return "*.SET, *.DBF"

    def path_text(self) -> str:
        return str(self.root / (self.pattern or "*"))


def default_root() -> Path:
    configured = os.environ.get("ADBX_DATA")
    return Path(configured).expanduser().resolve() if configured else Path.cwd()


def demo_state() -> ShellState:
    """Stato stabile per smoke test e screenshot canonici."""
    base = Path("/ALPHA4V3/TUTOR")
    state = ShellState(root=base)
    entries = [
        Entry("ALPHAVID", "file", base / "ALPHAVID.SET", ext="SET", date="06/01/1993"),
        Entry("AVMOVIES", "file", base / "AVMOVIES.DBF", ext="DBF",
              date="06/01/1993", records=50, fields=11),
        Entry("AVPATRON", "file", base / "AVPATRON.DBF", ext="DBF",
              date="06/01/1993", records=28, fields=17),
        Entry("AVSALES", "file", base / "AVSALES.DBF", ext="DBF",
              date="06/01/1993", records=109, fields=24),
        Entry("AVSALES2", "file", base / "AVSALES2.DBF", ext="DBF",
              date="06/01/1993", records=16, fields=9),
    ]
    state.listing = Listing(directory=base, pattern="*", entries=entries)
    fields = tuple(
        DbfField(name, ftype, length, decimals)
        for name, ftype, length, decimals in (
            ("TAPE_ID", "C", 4, 0), ("TAPE_TITLE", "C", 40, 0),
            ("TAPE_DESC", "M", 10, 0), ("SUBJECT", "C", 20, 0),
            ("RUNTIME", "N", 3, 0), ("RATING", "C", 5, 0),
            ("TAPETYPE", "C", 5, 0), ("AVAILABLE", "L", 1, 0),
            ("PRICE", "N", 6, 2), ("QUANTITY", "N", 3, 0),
            ("NOTES", "C", 20, 0),
        )
    )
    from datetime import date

    header = DbfHeader(version=3, updated=date(1993, 6, 1), records=50,
                       header_length=32 + 32 * len(fields) + 1,
                       record_length=106, fields=fields)
    state.current = CurrentFile(
        path=base / "AVMOVIES.DBF",
        name="AVMOVIES",
        ext="DBF",
        records=50,
        header=header,
    )
    return state


__all__ = ["CurrentFile", "ShellState", "default_root", "demo_state"]
