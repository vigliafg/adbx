from adbx.__main__ import main


def test_smoke_runs_headless(capsys):
    assert main(["--smoke"]) == 0
    out = capsys.readouterr().out
    assert "griglia 80x25" in out
    assert "digest" in out


def test_smoke_dump(capsys):
    assert main(["--smoke", "--dump"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("adbx 80x25")
    # 1 intestazione + 25 righe di testo + 25 righe di run attributi.
    assert out.count("\n") >= 51


def test_legacy_identity():
    from adbx import GRID_HEIGHT, GRID_WIDTH, VARIANT, WINDOW_TITLE, __version__

    assert __version__ == "1.0.0"
    assert VARIANT == "legacy"
    assert (GRID_WIDTH, GRID_HEIGHT) == (80, 25)
    assert WINDOW_TITLE == "adbx — legacy (80×25)"


def test_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0


def test_window_module_is_not_shadowed_by_the_app_package():
    from adbx.app.window import MainWindow, ScreenWidget, run

    assert callable(run)
    assert MainWindow.__name__ == "MainWindow"
    assert ScreenWidget.__name__ == "ScreenWidget"
