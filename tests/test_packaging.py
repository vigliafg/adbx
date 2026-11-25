"""O13 — packaging e documentazione della release."""

from pathlib import Path

from adbx import __version__
from adbx.shell import messages

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_consistent():
    assert __version__ == "0.10.0"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.10.0"' in pyproject
    assert 'adbx = "adbx.__main__:main"' in pyproject


def test_user_documentation_and_changelog():
    manual = ROOT / "docs" / "manuale-utente.md"
    changelog = ROOT / "docs" / "CHANGELOG.md"
    assert manual.is_file() and manual.stat().st_size > 4000
    assert changelog.is_file()
    assert "0.10.0" in changelog.read_text(encoding="utf-8")
    text = manual.read_text(encoding="utf-8")
    for topic in ("Installazione", "Script", "Applicazioni", "Backup",
                  "Differenze dichiarate"):
        assert topic in text


def test_screenshots_and_specs_are_present():
    render = ROOT / "docs" / "render"
    names = {path.name for path in render.glob("*.png")}
    for number in range(1, 57):
        assert any(name.startswith(f"{number:02d}-") for name in names), number
    specs = list((ROOT / "docs" / "spec").glob("*.md"))
    assert len(specs) >= 13
    assert (ROOT / "docs" / "spec" / "14-config-stampa.md").is_file()


def test_ci_runs_conformance_and_benchmark():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8")
    assert "python -m pytest" in workflow
    assert "benchmark.py" in workflow
    assert "3.11" in workflow and "3.13" in workflow


def test_release_build_script_is_executable():
    script = ROOT / "tools" / "build_release.sh"
    assert script.is_file()
    assert script.stat().st_mode & 0o111
    assert "pip wheel" in script.read_text(encoding="utf-8")


def test_message_style_is_uniform():
    assert messages.check_style("  Select   a database. ") == \
        "Select a database."
    assert messages.check_style("Saved") == "Saved."
    assert messages.check_style("Really?") == "Really?"
    for text in (
            messages.SELECT_FIRST, messages.OPEN_FIRST, messages.NO_SCRIPTS,
            messages.NO_APPLICATIONS,
            messages.protected("Reports", "DEMO"),
            messages.unavailable("Feature", "O12"),
            messages.saved("X"), messages.erased("Y"),
            messages.error("save", "disk full")):
        assert text == messages.check_style(text)
        assert "  " not in text
        assert text.endswith(".") or text.endswith("?") or text.endswith("!")


def test_packaging_assets_and_release_workflow():
    for name in ("packaging/adbx.spec", "packaging/entry.py",
                 "packaging/windows/installer.nsi",
                 "packaging/linux/AppRun",
                 "packaging/linux/adbx-legacy.desktop",
                 "packaging/icons/adbx-legacy.ico",
                 "packaging/icons/adbx-legacy.icns",
                 "packaging/icons/adbx-legacy.png",
                 "tools/package.py"):
        assert (ROOT / name).is_file(), name
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8")
    for token in ("ubuntu-22.04", "windows-2022", "macos-latest",
                  "tools/package.py", "SHA256SUMS"):
        assert token in workflow, token
    script = ROOT / "tools" / "package.py"
    assert script.stat().st_mode & 0o111


def test_frozen_user_data_dir():
    from pathlib import Path

    from adbx.config.paths import user_data_dir

    assert user_data_dir("win32", {"APPDATA": "C:/Roaming"}) == \
        Path("C:/Roaming") / "adbx-legacy"
    assert user_data_dir("linux", {"XDG_DATA_HOME": "/data"}) == \
        Path("/data") / "adbx-legacy"
    assert user_data_dir("linux", {}).parts[-3:] == \
        (".local", "share", "adbx-legacy")
    assert user_data_dir("darwin", {}).name == "adbx-legacy"


def test_frozen_environment_is_noop_outside_bundle(monkeypatch):
    from adbx import __main__

    monkeypatch.delattr(__main__.sys, "frozen", raising=False)
    assert __main__.prepare_frozen_environment() is False
