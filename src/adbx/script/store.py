"""Persistenza degli script in file JSON leggibili.

La directory predefinita è `objects/scripts` sotto la cartella dati, ma il
comando *Set script path* può cambiarla. Ogni script è un file
`<NOME>.JSON`; è possibile anche esportare la sola sequenza di tasti in un
`.SCP` testuale e reimportarla. Il limite del manuale è 400 script per
directory.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .model import (
    KIND_DIALOG,
    KIND_KEYSTROKE,
    KIND_MENU,
    DialogBox,
    MenuBarScript,
    Script,
    ScriptError,
    normalize_name,
)

MAX_SCRIPTS = 400
DEFAULT_SUBDIRECTORY = Path("objects") / "scripts"


def script_template(name: str, kind: str) -> Script:
    """Script vuoto con un contenuto iniziale utile."""
    name = normalize_name(name)
    if kind == KIND_DIALOG:
        dialog = DialogBox(title=name)
        return Script(name, kind=kind, dialog=dialog)
    if kind == KIND_MENU:
        return Script(name, kind=KIND_MENU, menu=MenuBarScript())
    return Script(name, kind=KIND_KEYSTROKE, source="")


class ScriptStore:
    """Directory di script, con ricerca per nome e scrittura atomica."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory).expanduser()

    # -- accesso ---------------------------------------------------------
    @property
    def exists(self) -> bool:
        return self.directory.is_dir()

    def ensure(self) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ScriptError(f"Cannot use script path {self.directory}: {exc}")

    def path_for(self, name: str) -> Path:
        return self.directory / f"{normalize_name(name)}.JSON"

    def scp_path_for(self, name: str) -> Path:
        return self.directory / f"{normalize_name(name)}.SCP"

    def names(self, kind: str | None = None) -> list[str]:
        if not self.directory.is_dir():
            return []
        result: list[str] = []
        for path in sorted(self.directory.iterdir()):
            if path.suffix.upper() not in (".JSON",):
                continue
            try:
                script = self.get(path.stem, missing_ok=True)
            except ScriptError:
                continue
            if script is None:
                continue
            if kind is None or script.kind == kind:
                result.append(script.name)
        return result

    def all(self, kind: str | None = None) -> list[Script]:
        result: list[Script] = []
        for name in self.names(kind):
            script = self.get(name)
            if script is not None:
                result.append(script)
        return result

    def count(self) -> int:
        return len(self.names())

    def get(self, name: str, *, missing_ok: bool = False) -> Script | None:
        try:
            path = self.path_for(name)
        except ScriptError:
            if missing_ok:
                return None
            raise
        if not path.is_file():
            if missing_ok:
                return None
            raise ScriptError(f"Script {normalize_name(name)} not found.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Script.from_dict(data)
        except (OSError, ValueError, TypeError) as exc:
            raise ScriptError(f"Cannot read script {path.name}: {exc}") from exc

    def exists_name(self, name: str) -> bool:
        try:
            return self.path_for(name).is_file()
        except ScriptError:
            return False

    # -- scrittura -------------------------------------------------------
    def save(self, script: Script) -> Script:
        if not isinstance(script, Script):
            raise ScriptError("Only scripts can be saved.")
        if not script.name:
            raise ScriptError("The script needs a name.")
        if not self.path_for(script.name).exists() and self.count() >= MAX_SCRIPTS:
            raise ScriptError(
                f"A script path holds at most {MAX_SCRIPTS} scripts.")
        self.ensure()
        script.updated = time.time()
        path = self.path_for(script.name)
        temporary = path.with_suffix(".JSON.tmp")
        payload = json.dumps(script.to_dict(), indent=2, ensure_ascii=False)
        try:
            temporary.write_text(payload + "\n", encoding="utf-8")
            os.replace(temporary, path)
        except OSError as exc:
            raise ScriptError(f"Cannot save script {script.name}: {exc}") from exc
        return script

    def delete(self, name: str) -> bool:
        path = self.path_for(name)
        try:
            if path.is_file():
                path.unlink()
                return True
        except OSError as exc:
            raise ScriptError(f"Cannot erase script {name}: {exc}") from exc
        return False

    def rename(self, old: str, new: str) -> Script:
        script = self.get(old)
        assert script is not None
        target = normalize_name(new)
        if target == script.name:
            return script
        if self.exists_name(target):
            raise ScriptError(f"Script {target} already exists.")
        script.name = target
        self.save(script)
        self.delete(old)
        return script

    # -- import/export ---------------------------------------------------
    def export_scp(self, name: str, path: Path | None = None) -> Path:
        script = self.get(name)
        assert script is not None
        target = path or self.scp_path_for(script.name)
        header = [
            "{*adbx script export*}",
            f"{{*name {script.name}*}}",
            f"{{*description {script.description}*}}",
        ]
        try:
            target.write_text("\n".join(header) + "\n" + script.source,
                              encoding="utf-8")
        except OSError as exc:
            raise ScriptError(f"Cannot export {script.name}: {exc}") from exc
        return target

    def import_scp(self, path: Path, name: str | None = None) -> Script:
        if not path.is_file():
            raise ScriptError(f"File not found: {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        description = ""
        source_lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("{*name ") and stripped.endswith("*}"):
                continue
            if stripped.startswith("{*description ") and stripped.endswith("*}"):
                description = stripped[len("{*description "):-2].strip()
                continue
            if stripped == "{*adbx script export*}":
                continue
            source_lines.append(line)
        script = Script(name or path.stem, description=description,
                        kind=KIND_KEYSTROKE, source="\n".join(source_lines))
        return self.save(script)


__all__ = ["DEFAULT_SUBDIRECTORY", "MAX_SCRIPTS", "ScriptStore",
           "script_template"]
