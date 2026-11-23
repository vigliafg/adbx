"""O4 — regole di campo durante l'immissione e il salvataggio."""

from adbx.data import indexing
from adbx.data.fields import Field
from adbx.data.rules import (
    FieldRule,
    LookupTable,
    PostingRule,
)
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.shell.records import RecordSession


def type_text(session, text):
    for char in text:
        session.handle(Key("SPACE" if char == " " else char,
                           shift=char.isupper()))


def make(tmp_path, fields, name="DEMO"):
    workspace = Workspace(tmp_path)
    return workspace, workspace.create_database(name, fields)


def test_required_blocks_move_and_save(tmp_path):
    _workspace, database = make(tmp_path, [
        Field("NAME", "C", 20), Field("CITY", "C", 15)])
    database.save_field_rule(FieldRule("NAME", required="Yes"))
    session = RecordSession(database, "enter")
    session.handle(Key("ENTER"))
    assert session.field_index == 0
    assert session.status == "NAME is required."
    assert not session.save()
    assert "NAME is required" in session.status

    # Completandolo il movimento riesce.
    type_text(session, "Ada")
    session.handle(Key("ENTER"))
    assert session.field_index == 1


def test_validation_message_blocks_commit(tmp_path):
    _workspace, database = make(tmp_path, [
        Field("PRICE", "N", 8, 2), Field("CITY", "C", 15)])
    database.save_field_rule(FieldRule(
        "PRICE", validation="PRICE>0",
        validation_message="Price must be positive."))
    session = RecordSession(database, "enter")
    type_text(session, "0")
    session.handle(Key("ENTER"))
    assert session.field_index == 0
    assert session.status == "Price must be positive."
    session.edit_text = "2.50"
    session.edit_cursor = 4
    session.handle(Key("ENTER"))
    assert session.field_index == 1
    assert session.draft["PRICE"] == "2.50"


def test_double_entry_mismatch_and_match(tmp_path):
    _workspace, database = make(tmp_path, [
        Field("CODE", "C", 8), Field("CITY", "C", 15)])
    database.save_field_rule(FieldRule("CODE", double_entry="Yes"))
    session = RecordSession(database, "enter")
    type_text(session, "abc")
    session.handle(Key("ENTER"))
    assert session.field_index == 0
    assert "again to confirm" in session.status
    assert session.edit_text == ""

    type_text(session, "abd")
    session.handle(Key("ENTER"))
    assert session.field_index == 0
    assert "do not match" in session.status

    type_text(session, "abc")
    session.handle(Key("ENTER"))
    assert session.field_index == 0
    type_text(session, "abc")
    session.handle(Key("ENTER"))
    assert session.field_index == 1
    assert session.draft["CODE"] == "abc"


def test_skip_expression_and_auto_advance(tmp_path):
    _workspace, database = make(tmp_path, [
        Field("A", "C", 3), Field("B", "C", 3), Field("C", "C", 3)])
    database.save_field_rule(FieldRule("A", auto_advance=True))
    database.save_field_rule(FieldRule("B", skip_expression='A="xxx"'))
    session = RecordSession(database, "enter")
    type_text(session, "xxx")
    assert session.field_index == 2
    assert session.draft["A"] == "xxx"


def test_calculated_fields_are_skipped_and_recomputed(tmp_path):
    _workspace, database = make(tmp_path, [
        Field("PRICE", "N", 8, 2), Field("QTY", "N", 4, 0),
        Field("TOTAL", "N", 10, 2)])
    database.save_field_rule(FieldRule(
        "TOTAL", value="Calculated", expression="PRICE*QTY"))
    session = RecordSession(database, "enter")
    assert session.draft["TOTAL"] == "0.00"
    session.field_index = 0
    session._load_field()
    type_text(session, "2.50")
    session.handle(Key("ENTER"))
    assert session.field_index == 1  # TOTAL viene saltato
    type_text(session, "4")
    session.handle(Key("ENTER"))
    assert session.draft["TOTAL"] == "10.00"
    assert session.save()
    record = database.read(database.sequences()[0])
    assert record["TOTAL"] == "10.00"


def test_default_value_and_expression_on_new_record(tmp_path):
    _workspace, database = make(tmp_path, [
        Field("TYPE", "C", 8), Field("TAX", "N", 5, 2),
        Field("DATE", "D", 8)])
    database.save_field_rule(FieldRule(
        "TYPE", default_mode="Value", default="Sale"))
    database.save_field_rule(FieldRule(
        "TAX", default_mode="Expression", default="7.5+0.75"))
    database.save_field_rule(FieldRule(
        "DATE", default_mode="Expression", default="DATE()"))
    session = RecordSession(database, "enter")
    assert session.draft["TYPE"] == "Sale"
    assert session.draft["TAX"] == "8.25"
    assert len(session.draft["DATE"]) == 8


def test_lookup_table_fills_related_fields(tmp_path):
    _workspace, database = make(tmp_path, [
        Field("TYPE", "C", 8), Field("PRICE", "N", 8, 2),
        Field("CITY", "C", 15)])
    table = LookupTable(columns=["PRICE"],
                        rows=[["Sale", "2.50"], ["Rental", "1.00"]])
    database.save_field_rule(FieldRule(
        "TYPE", lookup=True, table=table, lookup_validation="Exists",
        auto_popup="Yes"))
    session = RecordSession(database, "enter")
    session.field_index = 0
    session._load_field()
    session.handle(Key("F3"))
    assert session.lookup is not None
    session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    assert session.draft["TYPE"] == "Rental"
    assert session.draft["PRICE"] == "1.00"


def test_auto_popup_when_new_record_reaches_field(tmp_path):
    _workspace, database = make(tmp_path, [
        Field("CODE", "C", 4), Field("TYPE", "C", 8)])
    database.save_field_rule(FieldRule(
        "TYPE", lookup=True, table=LookupTable(rows=[["Sale"], ["Rental"]]),
        auto_popup="Yes"))
    session = RecordSession(database, "enter")
    session.field_index = 0
    session._load_field()
    type_text(session, "A1")
    session.handle(Key("ENTER"))
    assert session.field_index == 1
    assert session.lookup is not None


def test_template_and_mask_typing(tmp_path):
    _workspace, database = make(tmp_path, [
        Field("PHONE", "C", 14), Field("ZIP", "C", 5),
        Field("NAME", "C", 10)])
    database.save_field_rule(FieldRule(
        "PHONE", template="(   )   -    ", mask="9999999999"))
    database.save_field_rule(FieldRule(
        "ZIP", mask="99999", allow_exceptions=True))
    session = RecordSession(database, "enter")
    session.field_index = 0
    session._load_field()
    assert session.edit_text == "(   )   -    "
    type_text(session, "3155556767")
    session.handle(Key("ENTER"))
    assert session.draft["PHONE"] == "(315)555-6767"

    session.field_index = 1
    session._load_field()
    type_text(session, "E3223")
    session.handle(Key("ENTER"))
    assert session.draft["ZIP"] == "E3223"
    assert "exception" in session.status.lower()


def test_post_data_on_save(tmp_path):
    workspace, database = make(tmp_path, [
        Field("CODE", "C", 6), Field("QTY", "N", 4, 0)], name="ITEMS")
    stock = workspace.create_database("STOCK", [
        Field("CODE", "C", 6), Field("QOH", "N", 8, 0)])
    stock.append({"CODE": "A1", "QOH": "100"})
    indexing.save_index(stock, indexing.IndexDefinition("STOCKCOD", "CODE"))
    database.save_field_rule(FieldRule("QTY", post_data=True, postings=[
        PostingRule("STOCK", "QOH", "Subtract", "", "",
                    linking_index="STOCKCOD", common="CODE")]))
    session = RecordSession(database, "enter")
    session.field_index = 0
    session._load_field()
    type_text(session, "A1")
    session.handle(Key("ENTER"))
    session.field_index = 1
    session._load_field()
    type_text(session, "5")
    assert session.save()
    assert stock.read(1)["QOH"] == "95"


def test_template_backspace_skips_fixed_characters(tmp_path):
    _workspace, database = make(tmp_path, [Field("PHONE", "C", 14)])
    database.save_field_rule(FieldRule(
        "PHONE", template="(   )   -    ", mask="9999999999"))
    session = RecordSession(database, "enter")
    type_text(session, "315")
    assert session.edit_text == "(315)   -    "
    session.handle(Key("BACKSPACE"))
    assert session.edit_text == "(31 )   -    "
    session.handle(Key("BACKSPACE"))
    assert session.edit_text == "(3  )   -    "
    assert session.edit_text[0] == "(" and session.edit_text[4] == ")"
