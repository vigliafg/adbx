"""Genera i rendering canonici della griglia di celle.

Uso:
    python tools/capture_ui.py                     # docs/render/
    python tools/capture_ui.py --pixel-size 24 --out /tmp/adbx
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PyQt6.QtGui import QGuiApplication  # noqa: E402

from adbx.data import indexing  # noqa: E402
from adbx.data.expressions import SearchRow  # noqa: E402
from adbx.data.fields import Field  # noqa: E402
from adbx.data.rules import FieldRule, LookupTable, PostingRule  # noqa: E402
from adbx.data.sets import Link, SetDefinition  # noqa: E402
from adbx.data.workspace import Workspace  # noqa: E402
from adbx.render.qt_renderer import CellRenderer  # noqa: E402
from adbx.shell import screens  # noqa: E402
from adbx.shell.designer import DesignerSession  # noqa: E402
from adbx.shell.indexes import IndexSession, RangeSession  # noqa: E402
from adbx.shell.records import RecordSession  # noqa: E402
from adbx.shell.rules import (  # noqa: E402
    LookupTableEditor,
    PostingEditor,
    RulesSession,
)
from adbx.shell.searching import SearchSession  # noqa: E402
from adbx.shell.sets import SetDesigner, SetSession  # noqa: E402
from adbx.shell.state import demo_state  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "docs" / "render"))
    parser.add_argument("--pixel-size", type=int, default=18,
                        help="altezza del font in pixel; la cella ne deriva")
    args = parser.parse_args(argv)

    app = QGuiApplication(sys.argv[:1])  # noqa: F841
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    renderer = CellRenderer(pixel_size=args.pixel_size)
    renderer.use_natural_size(args.pixel_size, dpr=1.0)
    print(f"font {renderer.family}, corpo {args.pixel_size}px, "
          f"cella {renderer.cell_w:.2f}x{renderer.cell_h:.2f}")

    state = demo_state()
    menu = screens.main_menu(state, selected=0)
    directory = screens.directory(
        state, cursor=0,
        input_text=state.listing.entries[0].selectable_text,
        input_cursor=len(state.listing.entries[0].selectable_text))
    help_view, _spans, _positions = screens.help_overlay(
        screens.main_menu(state, selected=5), "choose")
    structure = screens.structure(state)
    status = screens.status_screen(state)

    with tempfile.TemporaryDirectory(prefix="adbx-capture-") as temporary:
        workspace = Workspace(temporary)
        database = workspace.create_database("AVMOVIES", [
            Field("TAPE_ID", "C", 4), Field("TAPE_TITLE", "C", 40),
            Field("TAPE_DESC", "M", 10), Field("SUBJECT", "C", 20),
            Field("RUNTIME", "N", 3, 0), Field("RATING", "C", 5),
            Field("AVAILABLE", "L", 1), Field("RENTPRICE", "N", 4, 2),
        ])
        for values in (
            {"TAPE_ID": "1006", "TAPE_TITLE": "Dumbo", "TAPE_DESC":
             "A Disney cartoon favorite.", "SUBJECT": "Children's",
             "RUNTIME": "64", "RATING": "NR", "AVAILABLE": "1",
             "RENTPRICE": "2.49"},
            {"TAPE_ID": "1007", "TAPE_TITLE": "For Your Eyes Only",
             "TAPE_DESC": "James Bond - 007.", "SUBJECT": "Action/Adventure",
             "RUNTIME": "127", "RATING": "PG", "AVAILABLE": "1",
             "RENTPRICE": "2.99"},
            {"TAPE_ID": "1001", "TAPE_TITLE": "Big Easy, The", "TAPE_DESC":
             "A suspense set in New Orleans.", "SUBJECT": "Action/Adventure",
             "RUNTIME": "104", "RATING": "R", "AVAILABLE": "0",
             "RENTPRICE": "2.99"},
        ):
            database.append(values)

        indexing.save_index(database, indexing.IndexDefinition(
            "AVMOVSUB", "SUBJECT", "Alphabetically by Movie Subject",
            levels=[("SUBJECT", "A")]))
        database.set_primary_index("AVMOVSUB")
        index_session = IndexSession(database, "AVMSUBTI")
        index_session.levels = [("SUBJECT", "A"), ("TAPE_TITLE", "A")]
        index_session.row = 1
        index_session.column = 0
        index_session._load_cell()
        range_session = RangeSession(
            database,
            settings=indexing.RangeSettings(primary="AVMOVSUB"))
        range_session.row = 3
        range_session.edit_text = "Children's"
        search_session = SearchSession(database, letter="A")
        search_session.rows = [
            SearchRow("SUBJECT", "=", "Children's", "AND"),
            SearchRow("RATING", "=", "G", "AND"),
        ]
        search_session.sort_rows = [("TAPE_TITLE", "A")]
        search_session.description = "Children's movies rated G"
        search_session.stage = "search"
        search_session._load_cell()
        view_shot = RecordSession(database, "view").view()
        browse_shot = RecordSession(database, "browse").view()
        indexing.run_search(
            database,
            search_rows=[SearchRow("SUBJECT", "=", "Children's")],
            sort_rows=[("TAPE_TITLE", "A")], description="Children")
        indexing.run_search(
            database,
            search_rows=[SearchRow("RATING", "=", "G")],
            description="Rated G")
        lookup_table = LookupTable(
            columns=["RATING"],
            rows=[["Children's", "G"], ["Action/Adventure", "PG"],
                  ["Drama", "G"], ["Comedy", "PG"]])
        database.save_field_rule(FieldRule(
            "SUBJECT", lookup=True, lookup_validation="Exists",
            auto_popup="Yes", table=lookup_table,
            prompt="Press F3 for the subject list"))
        database.save_field_rule(FieldRule(
            "TAPE_TITLE", case="Word",
            prompt="Enter the movie title"))
        database.save_field_rule(FieldRule("RUNTIME", required="Yes"))
        rules_session = RulesSession(database)
        rules_session.field_index = 1
        rules_session.window = "rules"
        rules_session.page = 1
        rules_session.row = 1
        rules_session._clamp_row()
        lookup_editor = LookupTableEditor(lookup_table, database=database,
                                          field_name="SUBJECT")
        posting_editor = PostingEditor([
            PostingRule("STOCK", "QOH", "Subtract", "", "",
                        linking_index="STOCKCOD", common="TAPE_ID")],
            database=database)

        header = workspace.create_database("AVHEADER", [
            Field("INV_NO", "C", 6), Field("CUST_ID", "C", 6),
            Field("INV_DATE", "D", 8)])
        patrons = workspace.create_database("AVPATRON", [
            Field("CUST_ID", "C", 6), Field("NAME", "C", 20),
            Field("CITY", "C", 15)])
        items = workspace.create_database("AVITEMS", [
            Field("INV_NO", "C", 6), Field("TAPE_ID", "C", 6),
            Field("QUANTITY", "N", 3, 0)])
        indexing.save_index(patrons, indexing.IndexDefinition(
            "AVPATID", "CUST_ID"))
        indexing.save_index(items, indexing.IndexDefinition(
            "AVINVNO", "INV_NO"))
        indexing.save_index(database, indexing.IndexDefinition(
            "AVMOVTAP", "TAPE_ID"))
        patrons.append({"CUST_ID": "1001", "NAME": "Ada", "CITY": "Rome"})
        header.append({"INV_NO": "A015", "CUST_ID": "1001",
                       "INV_DATE": "19930505"})
        items.append({"INV_NO": "A015", "TAPE_ID": "1006", "QUANTITY": "1"})
        items.append({"INV_NO": "A015", "TAPE_ID": "1007", "QUANTITY": "2"})
        set_definition = SetDefinition(
            workspace, "AVIDEO", "Alpha Video Invoicing", "AVHEADER")
        set_definition.links = [
            Link("AVHEADER", "AVPATRON", "AVPATID", "CUST_ID", "First"),
            Link("AVHEADER", "AVITEMS", "AVINVNO", "INV_NO", "All",
                 referential=True, cascading_updates=True,
                 cascading_deletes=True),
            Link("AVITEMS", "AVMOVIES", "AVMOVTAP", "TAPE_ID", "First",
                 edit_child="No", add_child="No"),
        ]
        set_definition.save()
        set_designer = SetDesigner(
            workspace, header, definition=set_definition)
        set_designer.stage = "editor"
        set_designer.window = "bottom"
        set_designer.selected = 2
        set_designer.row = 3
        set_designer._load_row()
        set_view = SetSession(set_definition, "view")
        set_browse = SetSession(set_definition, "browse")
        lookup_record = RecordSession(database, "enter")
        lookup_record.field_index = 3
        lookup_record._load_field()
        lookup_record._open_lookup()

        history = indexing.search_history(database)
        state.database = database
        history_view = screens.search_history_overlay(
            screens.main_menu(state, selected=0), history, 0,
            database=database)
        state.database = None

        shots = {
            "01-main-menu": menu,
            "02-directory": directory,
            "03-help": help_view,
            "04-structure": structure,
            "05-status": status,
            "07-view-records": view_shot,
            "08-browse-records": browse_shot,
            "09-designer": DesignerSession(workspace, database.name, database).view(),
            "10-index-table": index_session.view(),
            "11-range-settings": range_session.view(),
            "12-search-table": search_session.view(),
            "13-search-history": history_view,
            "14-field-rules": rules_session.view(),
            "15-lookup-table": lookup_editor.view(),
            "16-lookup-choices": lookup_record.view(),
            "17-posting-rules": posting_editor.view(),
            "18-set-editor": set_designer.view(),
            "19-set-view": set_view.view(),
            "20-set-browse": set_browse.view(),
        }
        for name, view in shots.items():
            image = renderer.to_image(view.buffer)
            path = out / f"{name}.png"
            image.save(str(path))
            print(f"{path.relative_to(ROOT)} {image.width()}x{image.height()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
