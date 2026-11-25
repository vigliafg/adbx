# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller di adbx-legacy: build onedir per Windows, macOS e Linux.

Il nome dell'eseguibile è `adbx-legacy`; la finestra non ha console (su
Windows l'eseguibile è `windows`), quindi `--smoke` e `--version` scrivono su
un devnull gestito da `adbx.__main__.prepare_frozen_environment`.
"""

import re
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICONS = ROOT / "packaging" / "icons"
VERSION = re.search(
    r'__version__\s*=\s*"([^"]+)"',
    (ROOT / "src" / "adbx" / "__init__.py").read_text(encoding="utf-8"),
).group(1)

icon = None
if sys.platform.startswith("win"):
    icon = str(ICONS / "adbx-legacy.ico")
elif sys.platform == "darwin":
    icon = str(ICONS / "adbx-legacy.icns")

version_file = ROOT / "build" / "windows" / "version_info.txt"
version = (str(version_file)
           if sys.platform.startswith("win") and version_file.is_file() else None)

analysis = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(str(ROOT / "src" / "adbx" / "data"), "adbx/data")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="adbx-legacy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=icon,
    version=version,
)

collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="adbx-legacy",
)

if sys.platform == "darwin":
    app = BUNDLE(
        collect,
        name="adbx-legacy.app",
        icon=str(ICONS / "adbx-legacy.icns"),
        bundle_identifier="it.vigliafg.adbx-legacy",
        info_plist={
            "CFBundleName": "adbx-legacy",
            "CFBundleDisplayName": "adbx legacy",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "MIT — vigliafg",
        },
    )
