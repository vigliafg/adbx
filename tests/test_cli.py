from adbx.__main__ import main


def test_smoke_runs_headless(capsys):
    assert main(["--smoke"]) == 0
    out = capsys.readouterr().out
    assert "griglia 132x43" in out
    assert "digest" in out


def test_smoke_dump(capsys):
    assert main(["--smoke", "--dump"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("adbx 132x43")
    assert out.count("\n") >= 87


def test_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
