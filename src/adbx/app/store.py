"""Persistenza delle applicazioni in `objects/apps/<NOME>.JSON`."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .model import (
    MAX_APPS,
    AppError,
    Application,
    normalize_app_name,
)

DEFAULT_SUBDIRECTORY = Path("objects") / "apps"


class ApplicationStore:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory).expanduser()

    def ensure(self) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AppError(f"Cannot use application path {self.directory}: "
                           f"{exc}") from exc

    def path_for(self, name: str) -> Path:
        return self.directory / f"{normalize_app_name(name)}.JSON"

    def names(self) -> list[str]:
        if not self.directory.is_dir():
            return []
        result = []
        for path in sorted(self.directory.iterdir()):
            if path.suffix.upper() != ".JSON":
                continue
            try:
                app = self.get(path.stem, missing_ok=True)
            except AppError:
                continue
            if app is not None:
                result.append(app.name)
        return result

    def all(self) -> list[Application]:
        result = []
        for name in self.names():
            app = self.get(name, missing_ok=True)
            if app is not None:
                result.append(app)
        return result

    def count(self) -> int:
        return len(self.names())

    def exists_name(self, name: str) -> bool:
        try:
            return self.path_for(name).is_file()
        except AppError:
            return False

    def get(self, name: str, *, missing_ok: bool = False) -> Application | None:
        try:
            path = self.path_for(name)
        except AppError:
            if missing_ok:
                return None
            raise
        if not path.is_file():
            if missing_ok:
                return None
            raise AppError(f"Application {normalize_app_name(name)} not found.")
        try:
            return Application.from_dict(json.loads(
                path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as exc:
            raise AppError(f"Cannot read application {path.name}: {exc}") from exc

    def save(self, app: Application) -> Application:
        app.validate()
        if not self.path_for(app.name).exists() and self.count() >= MAX_APPS:
            raise AppError(f"An application path holds at most {MAX_APPS} "
                           "applications.")
        self.ensure()
        app.updated = time.time()
        path = self.path_for(app.name)
        temporary = path.with_suffix(".JSON.tmp")
        payload = json.dumps(app.to_dict(), indent=2, ensure_ascii=False)
        try:
            temporary.write_text(payload + "\n", encoding="utf-8")
            os.replace(temporary, path)
        except OSError as exc:
            raise AppError(f"Cannot save application {app.name}: {exc}") from exc
        return app

    def delete(self, name: str) -> bool:
        try:
            path = self.path_for(name)
            if path.is_file():
                path.unlink()
                return True
        except OSError as exc:
            raise AppError(f"Cannot erase application {name}: {exc}") from exc
        return False


__all__ = ["ApplicationStore", "DEFAULT_SUBDIRECTORY"]
