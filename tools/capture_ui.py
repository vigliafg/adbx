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
from adbx.data.forms import (  # noqa: E402
    FormBox,
    FormDefinition,
    FormField,
    FormLabel,
    FormRegion,
)
from adbx.data.labels import LabelDefinition, LabelField, LabelText  # noqa: E402
from adbx.data.labels_engine import render_labels  # noqa: E402
from adbx.data.letters import LetterDefinition, render_letters  # noqa: E402
from adbx.data.report_engine import render_report  # noqa: E402
from adbx.data.reports import (  # noqa: E402
    ReportCalc,
    ReportDefinition,
    ReportField,
    ReportGroup,
    ReportSummary,
    ReportText,
)
from adbx.data.rules import FieldRule, LookupTable, PostingRule  # noqa: E402
from adbx.data.sets import Link, SetDefinition  # noqa: E402
from adbx.data.workspace import Workspace  # noqa: E402
from adbx.render.qt_renderer import CellRenderer  # noqa: E402
from adbx.shell import screens  # noqa: E402
from adbx.shell.designer import DesignerSession  # noqa: E402
from adbx.shell.forms import FormDesigner  # noqa: E402
from adbx.shell.global_update import GlobalSession  # noqa: E402
from adbx.shell.indexes import IndexSession, RangeSession  # noqa: E402
from adbx.shell.labels import LabelDesigner  # noqa: E402
from adbx.shell.letters import LetterEditor  # noqa: E402
from adbx.shell.records import RecordSession  # noqa: E402
from adbx.shell.relational import RelationalSession  # noqa: E402
from adbx.shell.reports import ReportDesigner, ReportPreview  # noqa: E402
from adbx.shell.rules import (  # noqa: E402
    LookupTableEditor,
    PostingEditor,
    RulesSession,
)
from adbx.shell.searching import SearchSession  # noqa: E402
from adbx.shell.sets import SetDesigner, SetSession  # noqa: E402
from adbx.shell.state import demo_state  # noqa: E402
from adbx.shell.transfer import TransferSession  # noqa: E402
from adbx.shell.utilities import UtilitySession  # noqa: E402


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
        movie_form = FormDefinition(workspace, "AVMOVIES", "A",
                                    "Alpha Video Movie")
        movie_form.labels = [
            FormLabel(0, 1, 2, "Alpha Video Movies"),
            FormLabel(0, 3, 2, "Id:"),
            FormLabel(0, 4, 2, "Title:"),
            FormLabel(0, 5, 2, "Subject:"),
            FormLabel(0, 6, 2, "Rating:"),
            FormLabel(0, 9, 2, "Description:"),
        ]
        movie_form.boxes = [FormBox(0, 2, 1, 7, 92, True)]
        movie_form.fields = [
            FormField("AVMOVIES", "TAPE_ID", 0, 3, 10, 4, 4),
            FormField("AVMOVIES", "TAPE_TITLE", 0, 4, 10, 40, 40),
            FormField("AVMOVIES", "SUBJECT", 0, 5, 10, 20, 20),
            FormField("AVMOVIES", "RATING", 0, 6, 10, 5, 5),
            FormField("AVMOVIES", "TAPE_DESC", 0, 10, 2, 300, 50,
                      format="!X"),
        ]
        movie_form.save()
        database.set_primary_index("AVMOVSUB")
        movie_view = RecordSession(database, "view", form=movie_form)

        set_form = FormDefinition(workspace, "AVIDEO", "A",
                                  "Alpha Video Invoice")
        set_form.labels = [
            FormLabel(0, 1, 2, "Invoice:"),
            FormLabel(0, 2, 2, "Customer:"),
            FormLabel(0, 3, 2, "City:"),
            FormLabel(0, 9, 2, "Line items"),
        ]
        set_form.boxes = [FormBox(0, 1, 1, 8, 100, True),
                          FormBox(0, 11, 1, 12, 80, True)]
        set_form.fields = [
            FormField("AVHEADER", "INV_NO", 0, 1, 14, 6, 6),
            FormField("AVPATRON", "NAME", 0, 2, 14, 20, 20),
            FormField("AVPATRON", "CITY", 0, 3, 14, 15, 15),
            FormField("CALC", "TOTAL", 0, 3, 60, 12, 12, "Items total", True,
                      "R", kind="summary", summary="Total",
                      summary_field="QUANTITY", summary_database="AVITEMS"),
        ]
        set_form.regions = [FormRegion("AVITEMS", 0, 12, 2, 10, 72,
                                       "Line items")]
        set_form.printable = False
        set_form.save()
        set_form_view = SetSession(set_definition, "view", form=set_form)
        form_designer = FormDesigner(workspace, header, owner="AVIDEO",
                                     form=set_form)
        form_designer.stage = "layout"
        form_designer.row = 12
        form_designer.col = 2
        form_designer.page = 0
        form_designer_format = FormDesigner(workspace, header, owner="AVIDEO",
                                            form=set_form)
        form_designer_format.stage = "formatting"
        form_designer_format.format_row = 1
        form_designer_format.format_col = 2
        set_view = SetSession(set_definition, "view")
        set_browse = SetSession(set_definition, "browse")

        movie_report = ReportDefinition(workspace, "AVMOVIES", "A",
                                        "Movies by subject", 100)
        movie_report.set_group_count(1)
        movie_report.groups = [ReportGroup(1, "AVMOVIES.SUBJECT")]
        movie_report.sections = ["page_header", "titles", "group1_header",
                                 "detail", "group1_footer", "summary"]
        movie_report.texts = [
            ReportText("page_header", 1, 1, "Alpha Video Movies"),
            ReportText("page_header", 1, 76, "Page"),
            ReportText("titles", 1, 1, "Id    Title"),
            ReportText("titles", 1, 50, "Subject"),
            ReportText("titles", 1, 72, "Runtime"),
            ReportText("group1_header", 1, 1, "Subject:"),
            ReportText("group1_footer", 1, 1,
                       "Movies in this subject:"),
        ]
        movie_report.fields = [
            ReportField("page_header", 1, 84, "SYSTEM.PAGENUMBER",
                        length=4),
            ReportField("group1_header", 1, 10, "AVMOVIES.SUBJECT",
                        length=25),
            ReportField("detail", 1, 1, "AVMOVIES.TAPE_ID", length=6,
                        data="Unique"),
            ReportField("detail", 1, 7, "AVMOVIES.TAPE_TITLE", length=40,
                        window=30, format="X"),
            ReportField("detail", 1, 50, "AVMOVIES.SUBJECT", length=20,
                        data="Unique"),
            ReportField("detail", 1, 72, "AVMOVIES.RUNTIME", length=6,
                        justification="R"),
            ReportField("group1_footer", 1, 26, "SUMMARY.COUNT1",
                        length=6, justification="R"),
            ReportField("summary", 1, 1, "SUMMARY.TOTAL1", length=6,
                        justification="R"),
        ]
        movie_report.summaries = [
            ReportSummary("COUNT1", "AVMOVIES.TAPE_ID", "Count", "Group 1",
                          "None", "Pre-processed"),
            ReportSummary("TOTAL1", "AVMOVIES.RUNTIME", "Total", "Grand"),
        ]
        movie_report.calcs = [ReportCalc("PRICE2", "RENTPRICE * 2")]
        movie_report.save()
        report_designer = ReportDesigner(
            workspace, database, owner="AVMOVIES", report=movie_report,
            stage="layout")
        report_designer.section = "detail"
        report_designer.row = 1
        report_designer.col = 7
        report_grouping = ReportDesigner(
            workspace, database, owner="AVMOVIES", report=movie_report,
            stage="grouping")
        report_output = render_report(movie_report, workspace)
        report_preview = ReportPreview(
            report_output, movie_report.label,
            pdf_path=workspace.directory / "AVMOVIES-A.pdf")

        movie_label = LabelDefinition(workspace, "AVMOVIES", "A",
                                      "Movie shelf labels", 40, 6, 2, 2, 1)
        movie_label.fields = [
            LabelField(1, 1, "AVMOVIES.TAPE_ID", length=5),
            LabelField(1, 7, "AVMOVIES.TAPE_TITLE", length=32),
            LabelField(2, 1, "AVMOVIES.SUBJECT", length=20),
            LabelField(2, 22, "AVMOVIES.RUNTIME", length=6,
                       justification="Right"),
            LabelField(4, 1, "AVMOVIES.RENTPRICE", length=8, format="$",
                       justification="Right"),
        ]
        movie_label.texts = [
            LabelText(1, 5, " "),
            LabelText(3, 1, chr(127)),
            LabelText(5, 1, "Alpha Video"),
        ]
        movie_label.save()
        label_designer = LabelDesigner(
            workspace, database, owner="AVMOVIES", label=movie_label,
            stage="layout")
        label_designer.row = 2
        label_designer.col = 1
        label_preview = ReportPreview(
            render_labels(movie_label, workspace), movie_label.label,
            pdf_path=workspace.directory / "AVMOVIES-A-label.pdf")

        movie_letter = LetterDefinition(
            workspace, "AVMOVIES", "MOVNOTE", "Movie note", [
                "[SYSTEM->DATE]",
                "",
                "Dear movie fan,",
                "",
                "You are holding [TAPE_TITLE].",
                "Subject: [SUBJECT]  Runtime: [RUNTIME] minutes.",
                "",
                "[.IF AVAILABLE = .T.]",
                "This title is available for rental at [RENTPRICE.$].",
                "[.ELSE]",
                "This title is currently rented out.",
                "[.ENDIF]",
                "",
                "Enjoy the show!",
                "",
                "The Gang at Alpha Video",
            ])
        movie_letter.save()
        letter_editor = LetterEditor(
            workspace, database, owner="AVMOVIES", letter=movie_letter)
        letter_editor.row = 4
        letter_editor.col = 14
        letter_preview = ReportPreview(
            render_letters(movie_letter, workspace), movie_letter.label,
            pdf_path=workspace.directory / "AVMOVIES-MOVNOTE.pdf")
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

        indexing.save_index(items, indexing.IndexDefinition(
            "AVITMTAP", "TAPE_ID"))
        copy_session = UtilitySession(
            workspace, database, None, "copy")
        copy_session.stage = "options"
        copy_session.name = "AVCOPY"
        copy_session.description = "Working copy of the movie catalog"
        copy_session._load_row()
        crosstab_session = UtilitySession(
            workspace, database, None, "crosstab")
        crosstab_session.stage = "options"
        crosstab_session.name = "AVXTAB"
        crosstab_session.row_field = "SUBJECT"
        crosstab_session.column_field = "RATING"
        crosstab_session.tab_field = "RUNTIME"
        crosstab_session.operation = "Average"
        crosstab_session.create_names = True
        crosstab_session.names_name = "AVXTABN"
        crosstab_session._load_row()
        join_session = RelationalSession(
            workspace, database, "join")
        join_session.picker = None
        join_session.secondary = items
        join_session.secondary_name = "AVITEMS"
        join_session.index_name = "AVITMTAP"
        join_session.common_expression = "TAPE_ID"
        join_session._prepare_index_fields()
        join_session.stage = "common"
        join_session._load_row()
        import_session = TransferSession(
            workspace, database, "import")
        import_session.picker = None
        import_session.format_key = "delimited"
        import_session.path_text = "C:\\ALPHA4\\PATRONS.ASC"
        import_session.stage = "options"
        import_session._load_row()
        export_session = TransferSession(
            workspace, database, "export")
        export_session.picker = None
        export_session.format_key = "csv"
        export_session.path_text = "C:\\ALPHA4\\MOVIES.CSV"
        export_session.chosen = [field.name for field in database.fields]
        export_session.stage = "fields"
        export_session._load_row()
        update_session = GlobalSession(
            database, "update-field")
        update_session.expressions = [
            ("TAPETITLE", "UPPER(TAPETITLE)"),
            ("RENTPRICE", "RENTPRICE * 1.10"),
        ]
        update_session.stage = "expressions"
        update_session._load_row()
        delete_session = GlobalSession(
            database, "delete-range")
        delete_session.stage = "confirm"
        delete_session._load_row()

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
            "21-form-designer": form_designer.view(),
            "22-custom-form": movie_view.view(),
            "23-set-form": set_form_view.view(),
            "24-formatting": form_designer_format.view(),
            "25-report-designer": report_designer.view(),
            "26-report-preview": report_preview.view(),
            "27-report-grouping": report_grouping.view(),
            "28-label-designer": label_designer.view(),
            "29-label-preview": label_preview.view(),
            "30-letter-editor": letter_editor.view(),
            "31-letter-preview": letter_preview.view(),
            "32-copy-database": copy_session.view(),
            "33-crosstab": crosstab_session.view(),
            "34-relational-join": join_session.view(),
            "35-import-options": import_session.view(),
            "36-export-fields": export_session.view(),
            "37-global-update": update_session.view(),
            "38-delete-range": delete_session.view(),
        }
        for name, view in shots.items():
            image = renderer.to_image(view.buffer)
            path = out / f"{name}.png"
            image.save(str(path))
            print(f"{path.relative_to(ROOT)} {image.width()}x{image.height()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
