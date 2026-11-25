#!/usr/bin/env python3
"""Costruisce e impacchetta adbx-legacy per Windows, macOS e Linux.

    python tools/package.py linux      # tar.gz + .deb + .AppImage
    python tools/package.py windows    # portable zip + installer NSIS
    python tools/package.py macos      # .dmg
    python tools/package.py auto       # piattaforma corrente
    python tools/package.py linux --skip-pyinstaller

Gli artefatti finiscono in `dist/artifacts/`; la build PyInstaller in
`dist/pyinstaller/<piattaforma>/`. Serve PyInstaller (`pip install pyinstaller`);
per il .deb `dpkg-deb`, per l'AppImage `appimagetool` (scaricato se assente),
per l'installer Windows NSIS 3 (`makensis`), per il .dmg `hdiutil`.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = DIST / "build"
ARTIFACTS = DIST / "artifacts"
ICONS = ROOT / "packaging" / "icons"
APP_NAME = "adbx-legacy"
APPIMAGE_TOOL_URL = (
    "https://github.com/AppImage/appimagetool/releases/download/continuous/"
    "appimagetool-{arch}.AppImage"
)

DEB_ARCH = {"x86_64": "amd64", "aarch64": "arm64", "armv7l": "armhf"}
DEB_DEPENDS = (
    "libgl1, libegl1, libxkbcommon0, libfontconfig1, libglib2.0-0, "
    "libdbus-1-3, libxcb-cursor0"
)


def version() -> str:
    text = (ROOT / "src" / "adbx" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def machine() -> str:
    name = platform.machine().lower()
    return {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}.get(name, name)


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(str(part) for part in cmd))
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def clean(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, symlinks=True)


def pyinstaller(plat: str) -> Path:
    if shutil.which("pyinstaller") is None:
        try:
            import PyInstaller  # noqa: F401
        except ImportError as exc:  # pragma: no cover - ambiente senza PyInstaller
            raise SystemExit(
                "PyInstaller assente: `python -m pip install pyinstaller`"
            ) from exc
    if plat == "windows":
        write_windows_version_info()
    distpath = DIST / "pyinstaller" / plat
    clean(distpath)
    run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", str(distpath),
        "--workpath", str(BUILD / "pyinstaller"),
        str(ROOT / "packaging" / "adbx.spec"),
    ])
    target = distpath / (APP_NAME + ".app" if plat == "macos" else APP_NAME)
    if not target.exists():  # pragma: no cover - build inattesa
        raise SystemExit(f"build PyInstaller assente: {target}")
    return target


def write_windows_version_info() -> Path:
    numbers = [int(part) for part in re.findall(r"\d+", version())]
    numbers += [0] * (4 - len(numbers))
    tuple_text = "(" + ", ".join(str(number) for number in numbers[:4]) + ")"
    text = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers={tuple_text}, prodvers={tuple_text}, mask=0x3f,
                    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'vigliafg'),
      StringStruct('FileDescription', 'adbx legacy - clone di Alpha Four v3'),
      StringStruct('FileVersion', '{version()}'),
      StringStruct('InternalName', 'adbx-legacy'),
      StringStruct('LegalCopyright', 'MIT'),
      StringStruct('OriginalFilename', 'adbx-legacy.exe'),
      StringStruct('ProductName', 'adbx legacy'),
      StringStruct('ProductVersion', '{version()}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    target = BUILD / "windows" / "version_info.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


# -- Linux ---------------------------------------------------------------


def linux_portable(app: Path) -> Path:
    target = ARTIFACTS / f"adbx-legacy-{version()}-linux-{machine()}.tar.gz"
    with tarfile.open(target, "w:gz") as archive:
        archive.add(app, arcname=APP_NAME)
    return target


def linux_deb(app: Path) -> Path:
    arch = DEB_ARCH.get(machine(), machine())
    tree = BUILD / "deb" / f"adbx-legacy_{version()}_{arch}"
    clean(tree)
    payload = tree / "opt" / APP_NAME
    copy_tree(app, payload)
    (tree / "usr" / "bin").mkdir(parents=True)
    wrapper = tree / "usr" / "bin" / APP_NAME
    wrapper.write_text(
        f'#!/bin/sh\nexec /opt/{APP_NAME}/{APP_NAME} "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    desktop_dir = tree / "usr" / "share" / "applications"
    desktop_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "packaging" / "linux" / "adbx-legacy.desktop", desktop_dir)
    icon_dir = tree / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps"
    icon_dir.mkdir(parents=True)
    shutil.copy2(ICONS / "adbx-legacy.png", icon_dir)
    docs = tree / "usr" / "share" / "doc" / APP_NAME
    docs.mkdir(parents=True)
    shutil.copy2(ROOT / "LICENSE", docs / "copyright")
    shutil.copy2(ROOT / "docs" / "CHANGELOG.md", docs / "changelog")
    control = tree / "DEBIAN" / "control"
    control.parent.mkdir(parents=True)
    size = sum(path.stat().st_size for path in tree.rglob("*") if path.is_file())
    control.write_text(f"""Package: adbx-legacy
Version: {version()}
Section: database
Priority: optional
Architecture: {arch}
Depends: {DEB_DEPENDS}
Installed-Size: {(size + 1023) // 1024}
Maintainer: vigliafg <vigliafg@users.noreply.github.com>
Homepage: https://github.com/vigliafg/adbx-legacy
Description: clone funzionale di Alpha Four v3 su griglia 80x25
 adbx-legacy replichera' il database relazionale di Alpha Four 3.0 in una
 finestra a celle di caratteri 80x25, con motore SQLite e file .DBF
 interoperabili. Variante legacy della linea principale 132x43.
""", encoding="utf-8")
    postinst = tree / "DEBIAN" / "postinst"
    postinst.write_text("""#!/bin/sh
set -e
if [ -x /usr/bin/update-desktop-database ]; then
    update-desktop-database -q /usr/share/applications || true
fi
if [ -x /usr/bin/gtk-update-icon-cache ]; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
exit 0
""", encoding="utf-8")
    postinst.chmod(0o755)
    target = ARTIFACTS / f"adbx-legacy_{version()}_{arch}.deb"
    run(["dpkg-deb", "--build", "--root-owner-group", str(tree), str(target)])
    return target


def ensure_appimagetool() -> Path:
    arch = machine()
    tool = BUILD / f"appimagetool-{arch}.AppImage"
    if tool.is_file():
        return tool
    tool.parent.mkdir(parents=True, exist_ok=True)
    url = APPIMAGE_TOOL_URL.format(arch=arch)
    print("scarico", url)
    urllib.request.urlretrieve(url, tool)
    tool.chmod(0o755)
    return tool


def linux_appimage(app: Path) -> Path:
    appdir = BUILD / "AppDir"
    clean(appdir)
    lib = appdir / "usr" / "lib" / APP_NAME
    copy_tree(app, lib)
    (appdir / "usr" / "bin").mkdir(parents=True)
    (appdir / "usr" / "bin" / APP_NAME).symlink_to(f"../lib/{APP_NAME}/{APP_NAME}")
    applications = appdir / "usr" / "share" / "applications"
    applications.mkdir(parents=True)
    icon_dir = appdir / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps"
    icon_dir.mkdir(parents=True)
    desktop = ROOT / "packaging" / "linux" / "adbx-legacy.desktop"
    for target in (applications / desktop.name, appdir / desktop.name):
        shutil.copy2(desktop, target)
    for target in (icon_dir / "adbx-legacy.png", appdir / "adbx-legacy.png"):
        shutil.copy2(ICONS / "adbx-legacy.png", target)
    apprun = appdir / "AppRun"
    shutil.copy2(ROOT / "packaging" / "linux" / "AppRun", apprun)
    apprun.chmod(0o755)

    tool = ensure_appimagetool()
    target = ARTIFACTS / f"adbx-legacy-{version()}-linux-{machine()}.AppImage"
    env = dict(os.environ, ARCH=machine(), APPIMAGE_EXTRACT_AND_RUN="1")
    run([str(tool), str(appdir), str(target)], env=env)
    target.chmod(0o755)
    return target


def build_linux(app: Path) -> list[Path]:
    return [linux_portable(app), linux_deb(app), linux_appimage(app)]


# -- Windows -------------------------------------------------------------


def windows_portable(app: Path) -> Path:
    target = ARTIFACTS / f"adbx-legacy-{version()}-windows-x64-portable.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        root = app.parent
        for path in sorted(app.rglob("*")):
            archive.write(path, path.relative_to(root).as_posix())
    return target


def find_makensis() -> str:
    found = shutil.which("makensis")
    if found:
        return found
    for candidate in (
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "NSIS" / "makensis.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "NSIS" / "makensis.exe",
    ):
        if candidate.is_file():
            return str(candidate)
    raise SystemExit("makensis assente: installare NSIS 3")


def windows_installer(app: Path) -> Path:
    target = ARTIFACTS / f"adbx-legacy-{version()}-windows-x64-setup.exe"
    script = ROOT / "packaging" / "windows" / "installer.nsi"
    run([
        find_makensis(), "-V2", "-NOCD",
        f"-DAPP_VERSION={version()}",
        f"-DSOURCE={app}",
        f"-DOUTFILE={target}",
        f"-DICON={ICONS / 'adbx-legacy.ico'}",
        f"-DLICENSE={ROOT / 'LICENSE'}",
        str(script),
    ])
    return target


def build_windows(app: Path) -> list[Path]:
    return [windows_portable(app), windows_installer(app)]


# -- macOS ---------------------------------------------------------------


def build_macos(app: Path) -> list[Path]:
    run(["codesign", "--force", "--deep", "--sign", "-", str(app)])
    staging = BUILD / "dmg"
    clean(staging)
    staging.mkdir(parents=True)
    copy_tree(app, staging / app.name)
    (staging / "Applications").symlink_to("/Applications")
    arch = "arm64" if machine() == "aarch64" else "x86_64"
    target = ARTIFACTS / f"adbx-legacy-{version()}-macos-{arch}.dmg"
    run([
        "hdiutil", "create", "-volname", f"adbx legacy {version()}",
        "-srcfolder", str(staging), "-ov", "-format", "UDZO", str(target),
    ])
    return [target]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default="auto",
                        choices=["auto", "linux", "windows", "macos"])
    parser.add_argument("--skip-pyinstaller", action="store_true",
                        help="riusa la build in dist/pyinstaller")
    args = parser.parse_args(argv)

    plat = args.target
    if plat == "auto":
        plat = {"linux": "linux", "win32": "windows", "darwin": "macos"}.get(
            sys.platform, sys.platform)
    if plat not in ("linux", "windows", "macos"):
        raise SystemExit(f"piattaforma non supportata: {plat}")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    if args.skip_pyinstaller:
        app = DIST / "pyinstaller" / plat / (
            APP_NAME + ".app" if plat == "macos" else APP_NAME)
        if not app.exists():
            raise SystemExit(f"build assente: {app}")
    else:
        app = pyinstaller(plat)

    builders = {"linux": build_linux, "windows": build_windows,
                "macos": build_macos}
    artifacts = builders[plat](app)
    print(f"\nadbx-legacy {version()} — {plat}:")
    for artifact in artifacts:
        print(f"  {artifact.relative_to(ROOT)}  "
              f"({artifact.stat().st_size // (1024 * 1024)} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
