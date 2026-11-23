#!/usr/bin/env python3
"""Test end-to-end con conferma visiva per adbx (e, opzionalmente, DOSBox).

Ogni scenario guida il `ShellController` vero, renderizza la griglia con il
renderer Qt e salva un PNG in `docs/e2e/adbx/`. Il manifest JSON contiene
testo atteso, dimensioni, hash e numero di colori: un test automatico può
verificare che le schermate esistano e non siano vuote.

Uso:
    python tools/e2e_visual.py
    python tools/e2e_visual.py --out /tmp/e2e
    python tools/e2e_visual.py --dosbox   # richiede dosbox-automation
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtGui import QGuiApplication, QImage  # noqa: E402

from adbx.app.model import AppItem, Application, AppMenu  # noqa: E402
from adbx.app.store import ApplicationStore  # noqa: E402
from adbx.data.fields import Field  # noqa: E402
from adbx.data.forms import FormDefinition, FormField  # noqa: E402
from adbx.data.reports import ReportDefinition, ReportField  # noqa: E402
from adbx.data.workspace import Workspace  # noqa: E402
from adbx.render.qt_renderer import CellRenderer  # noqa: E402
from adbx.screen.keys import Key  # noqa: E402
from adbx.script import DialogBox, DialogControl, Script  # noqa: E402
from adbx.script.store import ScriptStore  # noqa: E402
from adbx.shell.controller import ShellController  # noqa: E402


@dataclass
class Scenario:
    name: str
    expected: str
    view: object


def build_workspace(directory: Path):
    workspace = Workspace(directory)
    patrons = workspace.create_database("AVPATRON", [
        Field("CUST_ID", "C", 4), Field("NAME", "C", 20),
        Field("CITY", "C", 15), Field("STATE", "C", 2),
        Field("ACTIVE", "L", 1)])
    for row in (("1001", "Ada", "Placid", "NY", "1"),
                ("1002", "Bob", "Placid", "CA", "0"),
                ("1003", "Cara", "Snowville", "NY", "1")):
        patrons.append(dict(zip(
            ["CUST_ID", "NAME", "CITY", "STATE", "ACTIVE"], row)))
    movies = workspace.create_database("AVMOVIES", [
        Field("TAPE_ID", "C", 4), Field("TITLE", "C", 30),
        Field("SUBJECT", "C", 15)])
    movies.append({"TAPE_ID": "1006", "TITLE": "Dumbo",
                   "SUBJECT": "Children"})
    movies.append({"TAPE_ID": "1007", "TITLE": "For Your Eyes Only",
                   "SUBJECT": "Action"})
    form = FormDefinition(workspace, "AVPATRON", "A", "Patron form")
    form.fields = [FormField("AVPATRON", "NAME", row=2, col=2, length=20),
                   FormField("AVPATRON", "CITY", row=3, col=2, length=15)]
    workspace.save_form(form)
    report = ReportDefinition(workspace, "AVPATRON", "A", "Patron list", 80)
    report.sections = ["detail"]
    report.fields = [
        ReportField("detail", 1, 1, "AVPATRON.NAME", length=20),
        ReportField("detail", 1, 24, "AVPATRON.CITY", length=15)]
    workspace.save_report(report)
    store = ScriptStore(directory / "objects" / "scripts")
    store.save(Script("E2E", description="E2E script",
                      source='{WRITE 1,1,"Hello from adbx"}'))
    store.save(Script(
        "BOX", kind="dialog", description="E2E dialog",
        dialog=DialogBox(title="E2E", row=4, col=20, height=8, width=44,
                         controls=[
                             DialogControl("Prompt", row=3, col=2, width=20,
                                           label="Name:", variable="%NAME"),
                             DialogControl("Button", row=6, col=12, width=10,
                                           label="OK")])))
    apps = ApplicationStore(directory / "objects" / "apps")
    apps.save(Application("E2EAPP", description="E2E application",
                          menu=AppMenu(title="E2E MAIN MENU", items=[
                              AppItem("Patrons", action="Macro", macro="C"),
                              AppItem("Movies", action="Sub-Menu",
                                      submenu=AppMenu(title="MOVIES", items=[
                                          AppItem("By title", action="Macro",
                                                  macro="B")]))])))
    workspace.save_database(patrons)
    workspace.save_database(movies)
    return workspace, patrons, store, apps


def scenarios(directory: Path) -> list[Scenario]:
    workspace, patrons, store, apps = build_workspace(directory)
    result: list[Scenario] = []

    controller = ShellController(directory, open_path=patrons.source)
    result.append(Scenario("01-adbx-main-menu", "Alpha Four Main Menu",
                           controller.view()))

    controller.handle(Key("V"))
    controller.handle(Key("ENTER"))
    result.append(Scenario("02-adbx-view-records", "Ada",
                           controller.view()))
    controller.handle(Key("F10"))
    controller.handle(Key("F10"))

    controller._start_records("browse")
    result.append(Scenario("03-adbx-browse", "CUST_ID",
                           controller.view()))
    controller.handle(Key("F10"))

    controller._open_script("E2E")
    result.append(Scenario("04-adbx-script-editor", "Description:",
                           controller.view()))
    controller.handle(Key("ESC"))

    controller._open_script("BOX")
    controller.handle(Key("ESC"))
    controller._play_script("BOX")
    result.append(Scenario("05-adbx-dialog", "Name:",
                           controller.view()))
    controller.handle(Key("ESC"))

    controller._open_application_session_by_name("E2EAPP")
    result.append(Scenario("06-adbx-application", "E2E MAIN MENU",
                           controller.view()))
    controller.handle(Key("ESC"))
    controller.handle(Key("ESC"))

    report = workspace.get_report("AVPATRON", "A")
    controller._open_report_preview(report)
    result.append(Scenario("07-adbx-report-preview", "Ada",
                           controller.view()))

    controller._other_action("documentation")
    controller.handle(Key("ENTER"))  # Database structure
    controller.handle(Key("DOWN"))   # AVMOVIES -> AVPATRON
    controller.handle(Key("ENTER"))  # AVPATRON
    controller.handle(Key("F10"))    # generate
    result.append(Scenario("08-adbx-documentation", "Structure of AVPATRON",
                           controller.view()))
    return result


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def image_stats(image) -> dict:
    colors = set()
    for y in range(0, image.height(), 12):
        for x in range(0, image.width(), 12):
            colors.add(image.pixel(x, y))
    return {"width": image.width(), "height": image.height(),
            "sampled_colors": len(colors)}


def run_adbx(out: Path) -> list[dict]:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841
    renderer = CellRenderer(pixel_size=16)
    target = out / "adbx"
    target.mkdir(parents=True, exist_ok=True)
    manifest = []
    with tempfile.TemporaryDirectory(prefix="adbx-e2e-") as temporary:
        for scenario in scenarios(Path(temporary)):
            text = "\n".join(scenario.view.buffer.to_lines())
            if scenario.expected.upper() not in text.upper():
                raise SystemExit(
                    f"{scenario.name}: atteso {scenario.expected!r}")
            image = renderer.to_image(scenario.view.buffer)
            path = target / f"{scenario.name}.png"
            image.save(str(path))
            payload = path.read_bytes()
            stats = image_stats(image)
            if stats["sampled_colors"] < 2:
                raise SystemExit(f"{scenario.name}: immagine vuota")
            manifest.append({
                "scenario": scenario.name,
                "file": str(path.relative_to(out)),
                "expected": scenario.expected,
                "sha256": hashlib.sha256(payload).hexdigest(),
                **stats,
            })
            print(f"{_display(path)} {stats['width']}x"
                  f"{stats['height']} colors={stats['sampled_colors']}")
    return manifest


def run_dosbox(out: Path) -> list[dict]:
    from dosbox_automation import DosBoxAutomation, find_binary

    if find_binary() is None:
        raise SystemExit(
            "dosbox-automation non trovato: usa "
            "tools/dosbox_automation.py --download oppure imposta "
            "ADBX_DOSBOX_AUTOMATION.")
    target = out / "dosbox"
    target.mkdir(parents=True, exist_ok=True)
    manifest = []
    with DosBoxAutomation(port=8410) as session:
        session.wait_for_text("Alpha Four Main Menu")
        main = session.frame(target / "01-alpha4-main-menu.png")
        text = session.text()
        if "Alpha Four Main Menu" not in text:
            raise SystemExit("DOSBox: main menu non visibile")
        image = QImage(str(main))
        manifest.append({
            "scenario": "01-alpha4-main-menu",
            "file": str(main.relative_to(out)),
            "expected": "Alpha Four Main Menu",
            "sha256": hashlib.sha256(main.read_bytes()).hexdigest(),
            **image_stats(image),
        })
        session.keys("enter")
        session.wait_for_text("TAPE_ID")
        records = session.frame(target / "02-alpha4-view-records.png")
        image = QImage(str(records))
        manifest.append({
            "scenario": "02-alpha4-view-records",
            "file": str(records.relative_to(out)),
            "expected": "TAPE_ID",
            "sha256": hashlib.sha256(records.read_bytes()).hexdigest(),
            **image_stats(image),
        })
        print(_display(records))
    return manifest


def write_report(out: Path, manifest: list[dict]) -> None:
    (out / "manifest.json").write_text(
        json.dumps({"scenarios": manifest}, indent=2,
                   ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Conferma visiva end-to-end",
        "",
        "Immagini generate da `tools/e2e_visual.py`. Ogni scenario guida il",
        "controller reale, verifica il testo atteso e salva il PNG.",
        "",
        "```bash",
        "python tools/e2e_visual.py",
        "python tools/e2e_visual.py --dosbox   # richiede dosbox-automation",
        "```",
        "",
        "- `adbx/` — rendering della griglia 132×43 tramite il renderer Qt;",
        "- `dosbox/` — Alpha Four 3.0 originale in dosbox-automation,",
        "  catturato via REST API (`/api/v1/video/frame`);",
        "- `manifest.json` — testo atteso, dimensioni, colori e SHA-256.",
        "",
        "| Scenario | Atteso | Immagine | Dimensioni |",
        "|---|---|---|---|",
    ]
    for item in manifest:
        size = (f"{item['width']}x{item['height']}"
                if "width" in item else "DOSBox")
        lines.append(f"| {item['scenario']} | `{item['expected']}` | "
                     f"![{item['scenario']}]({item['file']}) | {size} |")
    lines.append("")
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "docs" / "e2e"))
    parser.add_argument("--dosbox", action="store_true",
                        help="esegue anche Alpha Four originale")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = run_adbx(out)
    if args.dosbox:
        manifest.extend(run_dosbox(out))
    write_report(out, manifest)
    print(f"manifest: {out / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
