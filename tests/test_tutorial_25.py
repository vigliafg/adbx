"""O13 — conformità: una prova per ciascuna delle 25 lezioni del Tutorial."""

from __future__ import annotations

from pathlib import Path

from adbx.app.model import AppItem, Application, AppMenu
from adbx.app.runtime import ApplicationRuntime
from adbx.app.store import ApplicationStore
from adbx.data import indexing
from adbx.data import rules as field_rules
from adbx.data.fields import Field
from adbx.data.forms import FormDefinition, FormField
from adbx.data.indexing import RangeSettings
from adbx.data.labels import LabelDefinition, LabelField
from adbx.data.labels_engine import render_labels
from adbx.data.letters import LetterDefinition, render_letters
from adbx.data.report_engine import render_report
from adbx.data.reports import ReportDefinition, ReportField
from adbx.data.rules import FieldRule, LookupTable, PostingRule
from adbx.data.sets import Link, SetDefinition
from adbx.data.utilities import UpdateExpression, change_case, update_fields
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.script import Script, ScriptEngine, ScriptHost, ScriptStore
from adbx.shell.controller import ShellController
from adbx.shell.records import RecordSession


def type_text(target, text):
    for char in text:
        target.handle(Key("SPACE" if char == " " else char,
                          shift=char.isupper()))


def make_library(tmp_path):
    workspace = Workspace(tmp_path)
    patrons = workspace.create_database("AVPATRON", [
        Field("CUST_ID", "C", 4), Field("NAME", "C", 20),
        Field("CITY", "C", 15), Field("STATE", "C", 2),
        Field("ACTIVE", "L", 1), Field("FEE", "N", 6, 2),
        Field("CATEGORY", "C", 10), Field("SINCE", "D", 8)])
    for row in (
            ("1001", "Ada", "Placid", "NY", "1", "2.50", "GOLD", "19900131"),
            ("1002", "Bob", "Placid", "CA", "0", "0.00", "BASIC", "19910101"),
            ("1003", "Cara", "Snowville", "NY", "1", "5.00", "GOLD",
             "19920202")):
        patrons.append(dict(zip(
            ["CUST_ID", "NAME", "CITY", "STATE", "ACTIVE", "FEE",
             "CATEGORY", "SINCE"], row)))
    movies = workspace.create_database("AVMOVIES", [
        Field("TAPE_ID", "C", 4), Field("TITLE", "C", 30),
        Field("SUBJECT", "C", 15), Field("COPIES", "N", 4, 0)])
    for row in (("1006", "Dumbo", "Children", "3"),
                ("1007", "For Your Eyes Only", "Action", "1"),
                ("1013", "Gone With The Wind", "Drama", "2")):
        movies.append(dict(zip(
            ["TAPE_ID", "TITLE", "SUBJECT", "COPIES"], row)))
    sales = workspace.create_database("AVSALES", [
        Field("INV_NO", "C", 4), Field("CUST_ID", "C", 4),
        Field("AMOUNT", "N", 8, 2), Field("TAPE_ID", "C", 4)])
    sales.append({"INV_NO": "A001", "CUST_ID": "1001",
                  "AMOUNT": "3.50", "TAPE_ID": "1006"})
    sales.append({"INV_NO": "A002", "CUST_ID": "1003",
                  "AMOUNT": "4.25", "TAPE_ID": "1007"})
    indexing.save_index(patrons, indexing.IndexDefinition("AVPATID", "CUST_ID"))
    indexing.save_index(movies, indexing.IndexDefinition("AVTAPE", "TAPE_ID"))
    indexing.save_index(sales, indexing.IndexDefinition("AVINV", "INV_NO"))
    for database in (patrons, movies, sales):
        workspace.save_database(database)
    return workspace, patrons, movies, sales


# 1 — Getting started
def test_lesson_01_getting_started(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    controller = ShellController(tmp_path)
    assert "D A T A B A S E   D I R E C T O R Y" in \
        "\n".join(controller.view().buffer.to_lines())
    controller.input_text = str(patrons.source)
    controller.input_cursor = len(controller.input_text)
    controller.handle(Key("ENTER"))
    assert controller.base == "menu"
    controller.handle(Key("F1"))
    assert controller.overlay.kind == "help"
    controller.handle(Key("ESC"))
    controller.handle(Key("Q"))
    assert controller.quit


# 2 — Creating a new database
def test_lesson_02_create_database(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("NEWDB", [
        Field("NAME", "C", 20), Field("BORN", "D", 8),
        Field("DUES", "N", 8, 2), Field("ACTIVE", "L", 1)])
    assert workspace.get("NEWDB") is not None
    assert [field.name for field in database.fields] == [
        "NAME", "BORN", "DUES", "ACTIVE"]
    assert database.field("DUES").decimals == 2


# 3 — Choosing the current database
def test_lesson_03_choose_database(tmp_path):
    _workspace, patrons, movies, _sales = make_library(tmp_path)
    controller = ShellController(tmp_path, open_path=patrons.source)
    assert controller.database.name == "AVPATRON"
    controller._adopt_database(movies)
    assert controller.database.name == "AVMOVIES"
    controller.handle(Key("F3"))
    assert "AVMOVIES" in "\n".join(controller.view().buffer.to_lines())
    controller.handle(Key("F10"))
    assert controller.base == "menu"


# 4 — Entering records
def test_lesson_04_enter_records(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    session = RecordSession(patrons, "enter")
    session.field_index = 1
    session._load_field()
    session.edit_text = "Dan"
    session.handle(Key("ENTER"))
    session.draft["CITY"] = "Rome"
    assert session.save()
    assert patrons.count() == 4
    assert patrons.read(4)["NAME"] == "Dan"


# 5 — Viewing, browsing and changing
def test_lesson_05_view_browse_change(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    view = RecordSession(patrons, "view")
    assert view.values_for(view.current_seq)["NAME"] == "Ada"
    browse = RecordSession(patrons, "browse")
    assert "NAME" in "\n".join(browse.view().buffer.to_lines())
    change = RecordSession(patrons, "change")
    change.field_index = 1
    change._load_field()
    change.edit_text = "Ada B."
    change.handle(Key("ENTER"))
    assert change.save()
    assert patrons.read(1)["NAME"] == "Ada B."


# 6 — Deleting and undeleting
def test_lesson_06_delete_and_undelete(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    session = RecordSession(patrons, "view")
    seq = session.current_seq
    assert seq is not None
    session.handle(Key("D", alt=True))
    assert patrons.is_deleted(seq)
    session.handle(Key("F7"))
    session.index = session._seqs.index(seq)
    session.handle(Key("U", alt=True))
    assert not patrons.is_deleted(seq)


# 7 — Indexes
def test_lesson_07_indexes_order_records(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    indexing.save_index(
        patrons, indexing.IndexDefinition("AVPATNAME", "NAME"))
    patrons.set_primary_index("AVPATNAME")
    seqs = indexing.ordered_sequences(patrons, patrons.current_range)
    names = [patrons.read(seq)["NAME"] for seq in seqs]
    assert names == sorted(names)


# 8 — Finding records
def test_lesson_08_find_record(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    session = RecordSession(patrons, "view")
    session.range_settings.primary_index = "AVPATID"
    session.apply_range()
    session.find("1003")
    assert session.values_for(session.current_seq)["CUST_ID"] == "1003"


# 9 — Ranges
def test_lesson_09_ranges(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    settings = RangeSettings(primary="AVPATID", first_key="1002",
                              last_key="1003")
    seqs = indexing.ordered_sequences(patrons, settings)
    assert [patrons.read(seq)["CUST_ID"] for seq in seqs] == ["1002", "1003"]


# 10 — Forms
def test_lesson_10_forms(tmp_path):
    workspace, patrons, _movies, _sales = make_library(tmp_path)
    form = FormDefinition(workspace, "AVPATRON", "A", "Patron form")
    form.fields = [FormField("AVPATRON", "NAME", row=2, col=2, length=20),
                   FormField("AVPATRON", "CITY", row=3, col=2, length=15)]
    workspace.save_form(form)
    session = RecordSession(patrons, "view", form=workspace.active_form("AVPATRON"))
    text = "\n".join(session.view().buffer.to_lines())
    assert "Ada" in text


# 11 — Field rules
def test_lesson_11_field_rules(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    patrons.save_field_rule(FieldRule("NAME", required="Yes"))
    session = RecordSession(patrons, "enter")
    assert not session.save()
    assert "NAME is required" in session.status
    patrons.save_field_rule(FieldRule(
        "FEE", default_mode="Constant", default="1.00"))
    assert patrons.field_rule("FEE").default == "1.00"


# 12 — Lookup tables
def test_lesson_12_lookup_table(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    rule = FieldRule("CATEGORY", lookup=True, lookup_source="Table",
                     table=LookupTable(rows=[["GOLD"], ["BASIC"]]))
    values = {"CATEGORY": ""}
    choices = field_rules.lookup_choices(rule, patrons, values)
    assert choices.values == ["GOLD", "BASIC"]
    assert field_rules.lookup_fill(
        rule, patrons, values, "GOLD")["CATEGORY"] == "GOLD"


# 13 — Lookup databases
def test_lesson_13_lookup_database(tmp_path):
    _workspace, patrons, movies, _sales = make_library(tmp_path)
    rule = FieldRule("TAPE_ID", lookup=True, lookup_source="Database",
                     lookup_database="AVMOVIES", linking_index="AVTAPE",
                     display_index="AVTAPE",
                     mapping=[])
    choices = field_rules.lookup_choices(rule, patrons, {"TAPE_ID": ""})
    assert "1006" in choices.values
    filled = field_rules.lookup_fill(rule, patrons, {"TAPE_ID": ""}, "1006")
    assert filled["TAPE_ID"] == "1006"


# 14 — Customizing a browse table
def test_lesson_14_browse_table(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    session = RecordSession(patrons, "browse")
    view = session.view()
    text = "\n".join(view.buffer.to_lines())
    assert "B R O W S E   R E C O R D S" in text
    assert "CUST_ID" in text and "NAME" in text
    session.browse_field = 2
    assert session.browse_field == 2


# 15 — Search/sort lists
def test_lesson_15_search_sort(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    definition = indexing.SavedSearch(
        "A", "NY patrons", search_expression='STATE = "NY"',
        sort_expression="NAME")
    indexing.save_saved_search(patrons, definition)
    result = indexing.run_saved_search(patrons, "A")
    assert len(result.seqs) == 2
    names = [patrons.read(seq)["NAME"] for seq in result.seqs]
    assert names == ["Ada", "Cara"]


# 16 — Global updating
def test_lesson_16_global_update(tmp_path):
    _workspace, patrons, _movies, _sales = make_library(tmp_path)
    result = update_fields(patrons, [UpdateExpression("CATEGORY", "UPPER(CATEGORY)")])
    assert result.updated == 3
    result = change_case(patrons, ["NAME"], "Lower case")
    assert patrons.read(1)["NAME"] == "ada"


# 17 — Mailing labels
def test_lesson_17_mailing_labels(tmp_path):
    workspace, patrons, _movies, _sales = make_library(tmp_path)
    label = LabelDefinition(workspace, "AVPATRON", "A", "Patron labels",
                            width=40, height=4, across=1)
    label.fields = [
        LabelField(1, 1, "AVPATRON.NAME", length=20,
                   justification="Suppress"),
        LabelField(2, 1, "AVPATRON.CITY", length=15,
                   justification="Suppress")]
    output = render_labels(label, workspace)
    assert "Ada" in output.to_text()


# 18 — Form letters
def test_lesson_18_form_letters(tmp_path):
    workspace, _patrons, _movies, _sales = make_library(tmp_path)
    letter = LetterDefinition(workspace, "AVPATRON", "HELLO", "Hello",
                              ["Dear [NAME],", "", "Welcome to [CITY]."])
    output = render_letters(letter, workspace)
    assert "Dear Ada," in output.to_text()


# 19 — Reports
def test_lesson_19_reports(tmp_path):
    workspace, _patrons, _movies, sales = make_library(tmp_path)
    report = ReportDefinition(workspace, "AVSALES", "A", "Invoices", 80)
    report.sections = ["detail"]
    report.fields = [
        ReportField("detail", 1, 1, "AVSALES.INV_NO", length=6),
        ReportField("detail", 1, 10, "AVSALES.AMOUNT", length=10)]
    output = render_report(report, workspace)
    text = output.to_text()
    assert "A001" in text and "3.50" in text


# 20 — Sets
def test_lesson_20_sets(tmp_path):
    workspace, patrons, _movies, sales = make_library(tmp_path)
    definition = SetDefinition(workspace, "AVSYS", "Sales set", "AVSALES")
    definition.links = [Link("AVSALES", "AVPATRON", "AVPATID", "CUST_ID",
                             "First")]
    definition.save()
    restored = workspace.get_set("AVSYS")
    assert restored.database_names() == ["AVSALES", "AVPATRON"]
    assert restored.link_for("AVPATRON").link_to == "First"


# 21 — Applications
def test_lesson_21_applications(tmp_path):
    store = ApplicationStore(tmp_path / "apps")
    app = Application("AVSYSTEM", menu=AppMenu(title="ALPHA VIDEO", items=[
        AppItem("Customers", action="Macro", macro="{BEEP}")]))
    store.save(app)
    runtime = ApplicationRuntime(store.get("AVSYSTEM"), store)
    assert runtime.menu.title == "ALPHA VIDEO"
    assert runtime.activate() == "macro"


# 22 — Advanced sets: one-to-many
def test_lesson_22_one_to_many(tmp_path):
    workspace, _patrons, _movies, sales = make_library(tmp_path)
    definition = SetDefinition(workspace, "AVINV", "Invoices", "AVSALES")
    definition.links = [Link("AVSALES", "AVPATRON", "AVPATID", "CUST_ID",
                             "First")]
    definition.save()
    assert definition.link_for("AVPATRON").one_to_many is False
    indexing.save_index(
        sales, indexing.IndexDefinition("AVSALCUST", "CUST_ID"))
    definition.links = [Link("AVPATRON", "AVSALES", "AVSALCUST", "CUST_ID",
                             "All")]
    definition.primary = "AVPATRON"
    definition.save()
    assert definition.link_for("AVSALES").one_to_many


# 23 — Advanced field rules: post data
def test_lesson_23_post_data(tmp_path):
    workspace, _patrons, movies, sales = make_library(tmp_path)
    posting = PostingRule("AVMOVIES", "COPIES", "Subtract", "", "",
                          linking_index="AVTAPE", common="TAPE_ID")
    rule = FieldRule("COPIES", post_data=True, postings=[posting])
    field_rules.post_values(rule, sales, {},
                            {"TAPE_ID": "1006", "COPIES": "1"}, rule)
    assert movies.read(1)["COPIES"] == "2"


# 24 — Scripts
def test_lesson_24_scripts(tmp_path):
    controller = ShellController(tmp_path)
    store = ScriptStore(tmp_path / "objects" / "scripts")
    store.save(Script("OPENDBS", source='{WRITE 1,1,"opened"}'))
    controller._play_script("OPENDBS")
    assert (1, 1, "opened") in controller.script_writes
    controller._open_script("OPENDBS")
    assert controller.base == "scripteditor"
    controller.handle(Key("ESC"))


# 25 — More on scripts: trigger and dialog
def test_lesson_25_advanced_scripts(tmp_path):
    store = ScriptStore(tmp_path / "scripts")
    host = ScriptHost()
    engine = ScriptEngine(store, host)
    store.save(Script("SHOW", source='{WRITE 2,2,"advanced"}'))
    assert engine.run(store.get("SHOW"))
    assert engine.variables.get("%SYS_TRIG_REC_SAVE") == ""
    engine.set_variable("%SYS_TRIG_REC_SAVE", "SHOW")
    assert engine.triggers.get("REC_SAVE") == "SHOW"
    engine.set_variable("%SYS_TRIG_REC_SAVE", "")
    assert not engine.fire("REC_SAVE")


def test_all_25_lessons_are_present():
    import ast

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    named = {node.name for node in tree.body
             if isinstance(node, ast.FunctionDef)
             and node.name.startswith("test_lesson_")}
    assert len(named) == 25
