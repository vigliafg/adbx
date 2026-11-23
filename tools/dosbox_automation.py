#!/usr/bin/env python3
"""Automazione di Alpha Four in dosbox-automation (REST API + frame).

Uso tipico:

    python tools/dosbox_automation.py --probe
    python tools/dosbox_automation.py --screenshot docs/e2e/alpha4-main-menu.png
    python tools/dosbox_automation.py --type "AVMOVIES" --keys enter --text

Il binario di dosbox-automation non è versionato (GPL-2.0, ~130 MB). Lo
script lo cerca in `ADBX_DOSBOX_AUTOMATION`, nella cache
`~/.cache/adbx/dosbox-automation/` oppure lo scarica con `--download`.

L'archivio Alpha Four resta fuori dal repository, come per
`tools/run_alpha4_dosbox.sh`.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "adbx"
DOSBOX_CACHE = CACHE / "dosbox-automation"
DRIVE_CACHE = CACHE / "alpha4-dos" / "drivec"
DEFAULT_ZIP = ROOT / "DRIVEC TERZA VERSIONE.zip"
RELEASE_VERSION = "0.85.1"
API_TIMEOUT = 15.0


class AutomationError(RuntimeError):
    pass


def find_binary() -> Path | None:
    configured = os.environ.get("ADBX_DOSBOX_AUTOMATION", "").strip()
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_file() else None
    for candidate in sorted(DOSBOX_CACHE.glob("*/bin/dosbox")):
        if candidate.is_file():
            return candidate
    return None


def _release_asset(version: str) -> tuple[str, str]:
    """Trova nome e URL dell'asset Linux compat della release."""
    api = (f"https://api.github.com/repos/dosbox-automation/"
           f"dosbox-automation/releases/tags/v{version}")
    try:
        with urllib.request.urlopen(api, timeout=30) as response:
            release = json.load(response)
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if "linux-x86_64-compat" in name and name.endswith(".tar.xz"):
                return name, asset["browser_download_url"]
    except (OSError, ValueError, KeyError) as exc:
        raise AutomationError(f"Release non leggibile: {exc}") from exc
    raise AutomationError(
        f"Nessun asset linux-x86_64-compat nella release {version}.")


def download_binary(version: str = RELEASE_VERSION) -> Path:
    """Scarica e estrae la build Linux compat nella cache."""
    DOSBOX_CACHE.mkdir(parents=True, exist_ok=True)
    existing = find_binary()
    if existing is not None:
        return existing
    asset, url = _release_asset(version)
    archive = DOSBOX_CACHE / asset
    print(f"adbx: scarico {url}", file=sys.stderr)
    temporary = archive.with_suffix(".part")
    try:
        with urllib.request.urlopen(url, timeout=120) as response, \
                temporary.open("wb") as target:
            shutil.copyfileobj(response, target)
        temporary.replace(archive)
        with tarfile.open(archive, "r:xz") as bundle:
            try:
                bundle.extractall(DOSBOX_CACHE, filter="data")
            except TypeError:  # Python 3.11 senza filtro tar
                bundle.extractall(DOSBOX_CACHE)
    except (OSError, tarfile.TarError) as exc:
        raise AutomationError(f"Download fallito: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    binary = find_binary()
    if binary is None:
        raise AutomationError("Il binario scaricato non contiene bin/dosbox.")
    return binary


def ensure_drive(zip_path: Path = DEFAULT_ZIP) -> Path:
    """Estrae `drivec/` dallo zip originale nella cache utente."""
    executable = DRIVE_CACHE / "ALPHA4V3" / "A4.EXE"
    if executable.is_file():
        return DRIVE_CACHE
    if not zip_path.is_file():
        raise AutomationError(
            f"Archivio Alpha Four non trovato: {zip_path}\n"
            "Indica il percorso con --zip o ADBX_ALPHA4_ZIP.")
    DRIVE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [name for name in archive.namelist()
                       if name.lower().startswith("drivec/")]
            archive.extractall(DRIVE_CACHE.parent, members)
    except (OSError, zipfile.BadZipFile) as exc:
        raise AutomationError(f"Estrazione fallita: {exc}") from exc
    if not executable.is_file():
        raise AutomationError("Lo zip non contiene drivec/ALPHA4V3/A4.EXE.")
    return DRIVE_CACHE


class DosBoxAutomation:
    """Una sessione dosbox-automation con API REST e screenshot."""

    def __init__(self, *, binary: Path | None = None, port: int = 8400,
                 drive: Path | None = None, zip_path: Path = DEFAULT_ZIP,
                 cache: Path | None = None, visible: bool = False) -> None:
        self.binary = Path(binary) if binary else find_binary()
        if self.binary is None or not self.binary.is_file():
            raise AutomationError(
                "dosbox-automation non trovato. Usa --download o imposta "
                "ADBX_DOSBOX_AUTOMATION.")
        self.port = port
        self.drive = Path(drive) if drive else ensure_drive(zip_path)
        self.cache = Path(cache) if cache else CACHE / "e2e"
        self.visible = visible
        self.token = os.environ.get("DOSBOX_API_TOKEN") or secrets.token_hex(32)
        self.process: subprocess.Popen | None = None
        self.log_path = self.cache / "dosbox.log"
        self._config_home = self.cache / "config"

    # -- processo --------------------------------------------------------
    def _write_config(self) -> None:
        conf_dir = self._config_home / "dosbox-automation"
        conf_dir.mkdir(parents=True, exist_ok=True)
        conf = conf_dir / "dosbox-automation.conf"
        conf.write_text(
            "[sdl]\n"
            "output = texture\n"
            "autolock = false\n"
            "\n"
            "[webserver]\n"
            "webserver_enabled = true\n"
            "webserver_bind_address = 127.0.0.1\n"
            f"webserver_port = {self.port}\n"
            f"mount_allowed_bases = {self.drive.resolve()}\n"
            "\n"
            "[autoexec]\n"
            f"mount c {self.drive.resolve()}\n"
            "c:\n"
            "cd \\ALPHA4V3\n"
            "A4.EXE\n",
            encoding="utf-8")

    def start(self) -> None:
        self.cache.mkdir(parents=True, exist_ok=True)
        self._write_config()
        command = [str(self.binary)]
        if not self.visible and not os.environ.get("DISPLAY"):
            command = ["xvfb-run", "-a", "-s", "-screen 0 1024x768x24",
                       *command]
        environment = os.environ.copy()
        environment["DOSBOX_API_TOKEN"] = self.token
        environment["XDG_CONFIG_HOME"] = str(self._config_home)
        self.log = self.log_path.open("ab")
        self.process = subprocess.Popen(
            command, stdout=self.log, stderr=subprocess.STDOUT,
            env=environment, cwd=str(self.cache))
        self._wait_api()

    def _wait_api(self, timeout: float = 25.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise AutomationError(
                    f"dosbox-automation è terminato. Log: {self.log_path}")
            try:
                self.status()
                return
            except (urllib.error.URLError, AutomationError):
                time.sleep(0.25)
        raise AutomationError(
            f"API non disponibile su localhost:{self.port}. "
            f"Log: {self.log_path}")

    def close(self) -> None:
        try:
            if self.process is not None and self.process.poll() is None:
                try:
                    self.request("/api/v1/dosbox/shutdown", method="POST")
                except AutomationError:
                    pass
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.terminate()
        finally:
            if self.process is not None:
                self.process = None
            log = getattr(self, "log", None)
            if log is not None:
                log.close()

    def __enter__(self) -> "DosBoxAutomation":
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # -- API -------------------------------------------------------------
    def request(self, path: str, *, method: str = "GET",
                payload: dict | None = None, raw: bool = False):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = None
        headers = {"Authorization": f"Bearer {self.token}"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers,
                                         method=method)
        try:
            with urllib.request.urlopen(request, timeout=API_TIMEOUT) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise AutomationError(f"{path}: HTTP {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise AutomationError(f"{path}: {exc.reason}") from exc
        if raw:
            return body
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except ValueError:
            return body.decode("utf-8", "replace")

    def status(self) -> dict:
        return self.request("/api/v1/status")

    def program(self) -> dict:
        return self.request("/api/v1/program/state")

    def text(self) -> str:
        data = self.request("/api/v1/video/text")
        return data.get("text", "") if isinstance(data, dict) else str(data)

    def wait_for_text(self, needle: str, *, timeout: float = 20.0,
                      interval: float = 0.3) -> str:
        deadline = time.time() + timeout
        last = ""
        while time.time() < deadline:
            last = self.text()
            if needle.upper() in last.upper():
                return last
            time.sleep(interval)
        raise AutomationError(
            f"Testo {needle!r} non comparso entro {timeout}s. "
            f"Ultimo schermo:\n{last[-800:]}")

    def frame(self, path: str | Path, *, mode: str = "raw") -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        image = self.request(
            f"/api/v1/video/frame?format=png&mode={mode}", raw=True)
        if not image.startswith(b"\x89PNG"):
            raise AutomationError("Il frame non è un PNG.")
        target.write_bytes(image)
        return target

    def type_text(self, text: str, *, cps: float = 25.0) -> None:
        self.request("/api/v1/input/type", method="POST",
                     payload={"text": text, "cps": cps})

    def key(self, name: str, *, hold_ms: int = 60) -> None:
        """Preme un tasto; accetta `enter` oppure `KBD_enter`."""
        key_name = name if name.upper().startswith("KBD_") else f"KBD_{name.lower()}"
        events = [
            {"type": "key", "key": key_name, "pressed": True, "delay_ms": 0},
            {"type": "key", "key": key_name, "pressed": False,
             "delay_ms": hold_ms},
        ]
        self.request("/api/v1/input/sequence", method="POST",
                     payload={"events": events})

    def keys(self, *names: str, pause: float = 0.25) -> None:
        for name in names:
            self.key(name)
            time.sleep(pause)

    def type_and_enter(self, text: str, *, pause: float = 0.5) -> None:
        self.type_text(text)
        time.sleep(pause)
        self.key("enter")


def screenshot_main_menu(session: DosBoxAutomation, path: Path) -> Path:
    session.wait_for_text("Alpha Four Main Menu")
    return session.frame(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Automa Alpha Four in dosbox-automation")
    parser.add_argument("--download", action="store_true",
                        help="scarica il binario nella cache se assente")
    parser.add_argument("--zip", default=os.environ.get(
        "ADBX_ALPHA4_ZIP", str(DEFAULT_ZIP)))
    parser.add_argument("--port", type=int, default=8400)
    parser.add_argument("--screenshot", metavar="PNG")
    parser.add_argument("--probe", action="store_true",
                        help="stampa lo schermo corrente")
    parser.add_argument("--text", action="store_true",
                        help="stampa il testo dopo i comandi")
    parser.add_argument("--type", dest="typed", metavar="TEXT",
                        help="digita un testo")
    parser.add_argument("--keys", metavar="LIST",
                        help="tasti separati da virgola (enter,down,...)")
    parser.add_argument("--visible", action="store_true",
                        help="non usare Xvfb, mostra la finestra")
    parser.add_argument("--keep", action="store_true",
                        help="lascia dosbox in esecuzione")
    args = parser.parse_args(argv)

    try:
        binary = download_binary() if args.download else find_binary()
        with DosBoxAutomation(binary=binary, port=args.port,
                              zip_path=Path(args.zip),
                              visible=args.visible) as session:
            session.wait_for_text("Alpha Four Main Menu")
            if args.typed:
                session.type_and_enter(args.typed)
            if args.keys:
                session.keys(*[item.strip() for item in args.keys.split(",")
                               if item.strip()])
            if args.screenshot:
                target = session.frame(args.screenshot)
                print(target)
            if args.text or args.probe:
                print(session.text())
    except AutomationError as exc:
        print(f"adbx: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
