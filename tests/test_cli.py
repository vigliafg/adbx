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
    assert out.count("\n") >= 51


def test_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
