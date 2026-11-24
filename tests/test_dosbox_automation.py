"""Test dell'automazione DOSBox e della conferma visiva end-to-end."""

from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import dosbox_automation  # noqa: E402
import e2e_visual  # noqa: E402


def test_ensure_drive_extracts_only_drivec(tmp_path, monkeypatch):
    archive = tmp_path / "alpha.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("drivec/ALPHA4V3/A4.EXE", b"MZ")
        bundle.writestr("drivec/ALPHA4V3/A4.OVR", b"data")
        bundle.writestr("readme.txt", "not extracted")
    drive = tmp_path / "cache" / "drivec"
    monkeypatch.setattr(dosbox_automation, "DRIVE_CACHE", drive)
    assert dosbox_automation.ensure_drive(archive) == drive
    assert (drive / "ALPHA4V3" / "A4.EXE").is_file()
    assert not (drive / "readme.txt").exists()


def test_key_event_payload_and_name_normalization(monkeypatch):
    session = dosbox_automation.DosBoxAutomation.__new__(
        dosbox_automation.DosBoxAutomation)
    captured = {}

    def fake_request(path, *, method="GET", payload=None, raw=False):
        captured.update(path=path, method=method, payload=payload)
        return {}

    monkeypatch.setattr(session, "request", fake_request)
    session.key("enter")
    assert captured["path"] == "/api/v1/input/sequence"
    events = captured["payload"]["events"]
    assert [event["type"] for event in events] == ["key", "key"]
    assert events[0]["key"] == "KBD_enter"
    assert events[0]["pressed"] is True
    assert events[1]["pressed"] is False


def test_find_binary_uses_environment(tmp_path, monkeypatch):
    binary = tmp_path / "dosbox"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("ADBX_DOSBOX_AUTOMATION", str(binary))
    assert dosbox_automation.find_binary() == binary


def test_visual_e2e_scenarios_produce_screenshots(tmp_path):
    out = tmp_path / "e2e"
    manifest = e2e_visual.run_adbx(out)
    e2e_visual.write_report(out, manifest)
    assert len(manifest) == 8
    names = [entry["scenario"] for entry in manifest]
    assert names[0] == "01-adbx-main-menu"
    assert "08-adbx-documentation" in names
    hashes = set()
    for entry in manifest:
        path = out / entry["file"]
        assert path.is_file() and path.stat().st_size > 5000
        assert entry["width"] == 800 and entry["height"] == 475
        assert entry["sampled_colors"] >= 2
        hashes.add(entry["sha256"])
    assert len(hashes) == len(manifest)
    assert (out / "manifest.json").is_file()
    report = (out / "README.md").read_text(encoding="utf-8")
    assert "Conferma visiva end-to-end" in report
    for expected in ("Alpha Four Main Menu", "CUST_ID", "E2E MAIN MENU"):
        assert expected in report


def test_committed_visual_confirmation_is_valid():
    out = ROOT / "docs" / "e2e"
    manifest = (out / "manifest.json").read_text(encoding="utf-8")
    assert "Alpha Four Main Menu" in manifest
    for path in (out / "adbx").glob("*.png"):
        assert path.stat().st_size > 5000
    for path in (out / "dosbox").glob("*.png"):
        assert path.stat().st_size > 5000
    assert (out / "README.md").is_file()
