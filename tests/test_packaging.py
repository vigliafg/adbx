"""O13 — packaging e documentazione della release 1.0."""

from pathlib import Path

from adbx import __version__
from adbx.shell import messages

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_one_zero():
    assert __version__ == "1.0.0"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "1.0.0"' in pyproject
    assert 'adbx = "adbx.__main__:main"' in pyproject


def test_user_documentation_and_changelog():
    manual = ROOT / "docs" / "manuale-utente.md"
    changelog = ROOT / "docs" / "CHANGELOG.md"
    assert manual.is_file() and manual.stat().st_size > 4000
    assert changelog.is_file()
    assert "1.0.0" in changelog.read_text(encoding="utf-8")
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
