"""O9 — copy, append, summarize, crosstab, post e comandi relazionali."""

from decimal import Decimal

import pytest

from adbx.data import indexing, utilities
from adbx.data.fields import Field
from adbx.data.rules import FieldRule
from adbx.data.workspace import Workspace


def make_sales(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVSALES", [
        Field("CUST_ID", "C", 4), Field("NAME", "C", 12),
        Field("AMT", "N", 7, 2), Field("INV", "C", 4),
    ])
    for row in (("1001", "Richardson", "3.24", "A001"),
                ("1001", "Richardson", "4.00", "A002"),
                ("1021", "Barber", "5.00", "A111")):
        database.append(dict(zip(
            [field.name for field in database.fields], row)))
    indexing.save_index(
        database, indexing.IndexDefinition("CUST", "CUST_ID",
                                           description="By customer"))
    database.set_primary_index("CUST")
    workspace.save_database(database)
    return workspace, database


def rows(database):
    return [database.read(seq) for seq in database.sequences()]


def test_copy_selected_fields_and_order(tmp_path):
    workspace, database = make_sales(tmp_path)
    database.save_field_rule(FieldRule("NAME", required="Yes"))
    result = utilities.copy_database(database, utilities.CopyOptions(
        "COPY1", description="Working copy", inherit_support=True,
        fields=[utilities.CopyField("AVSALES", "CUST_ID"),
                utilities.CopyField("AVSALES", "AMT")]))
    assert result.written == 3
    copied = workspace.get("COPY1")
    assert [field.name for field in copied.fields] == ["CUST_ID", "AMT"]
    assert [row["AMT"] for row in rows(copied)] == ["3.24", "4.00", "5.00"]
    assert copied.description == "Working copy"
    assert copied.field_rule("NAME") is not None
    # Il .DBF è già stato riscritto.
    assert copied.source.exists()


def test_append_four_modes(tmp_path):
    workspace, target = make_sales(tmp_path)
    external = workspace.create_database("EXT", [
        Field("CUST_ID", "C", 4), Field("NAME", "C", 12),
        Field("AMT", "N", 7, 2), Field("INV", "C", 4),
    ])
    external.append({"CUST_ID": "1001", "NAME": "Richardson",
                     "AMT": "9.99", "INV": "B001"})
    external.append({"CUST_ID": "9999", "NAME": "New", "AMT": "7.77",
                     "INV": "B002"})
    workspace.save_database(external)

    result = utilities.append_database(target, external,
                                       utilities.AppendOptions("Unique"))
    assert result.written == 1
    assert [row["INV"] for row in rows(target)] == [
        "A001", "A002", "A111", "B002"]

    result = utilities.append_database(
        target, external,
        utilities.AppendOptions("Replace existing, add unique"))
    assert result.replaced == 3
    replaced = [row for row in rows(target) if row["CUST_ID"] == "1001"]
    assert {row["AMT"] for row in replaced} == {"9.99"}
    assert target.count() == 4

    # Mark unique: il record esterno già aggiunto viene marcato cancellato.
    external.append({"CUST_ID": "8888", "NAME": "Another", "AMT": "1.00",
                     "INV": "B003"})
    workspace.save_database(external)
    result = utilities.append_database(
        target, external,
        utilities.AppendOptions("Replace existing, mark unique"))
    assert result.marked == 1
    marked = [seq for seq in external.sequences(include_deleted=True)
              if external.is_deleted(seq)]
    assert len(marked) == 1

    result = utilities.append_database(target, external,
                                       utilities.AppendOptions("All"))
    assert result.written == 2


def test_append_filter_and_mapping(tmp_path):
    workspace, target = make_sales(tmp_path)
    external = workspace.create_database("EXT", [
        Field("CUST", "C", 4), Field("TOTAL", "N", 7, 2)])
    external.append({"CUST": "1001", "TOTAL": "1.00"})
    external.append({"CUST": "1021", "TOTAL": "2.00"})
    mapping = [utilities.AppendMapping("CUST_ID", "CUST"),
               utilities.AppendMapping("AMT", "TOTAL")]
    result = utilities.append_database(
        target, external,
        utilities.AppendOptions("All", filter='CUST="1021"',
                                mappings=mapping))
    assert result.written == 1
    assert rows(target)[-1]["AMT"] == "2.00"


def test_summarize_operations(tmp_path):
    workspace, database = make_sales(tmp_path)
    result = utilities.summarize(database, utilities.SummarizeOptions(
        "SUM1", [utilities.SummaryField("CUST_ID", "Group"),
                 utilities.SummaryField("AMT", "Total"),
                 utilities.SummaryField("AMT", "Average"),
                 utilities.SummaryField("AMT", "Count"),
                 utilities.SummaryField("AMT", "Biggest"),
                 utilities.SummaryField("AMT", "Smallest"),
                 utilities.SummaryField("AMT", "First"),
                 utilities.SummaryField("AMT", "Last"),
                 utilities.SummaryField("NAME", "Null")]))
    assert result.written == 2
    summary = workspace.get("SUM1")
    first, second = rows(summary)
    assert first["CUST_ID"] == "1001"
    assert first["AMT"] == "7.24"
    assert first["AMT2"] == "3.62"
    assert first["AMT3"] == "2"
    assert first["AMT4"] == "4.00"
    assert first["AMT5"] == "3.24"
    assert first["AMT6"] == "3.24"
    assert first["AMT7"] == "4.00"
    assert first["NAME"] == ""
    assert second["CUST_ID"] == "1021"


def test_summarize_needs_index(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("PLAIN", [Field("A", "C", 4)])
    database.append({"A": "x"})
    with pytest.raises(utilities.UtilityError):
        utilities.summarize(database, utilities.SummarizeOptions(
            "SUM1", [utilities.SummaryField("A", "Group")]))


def test_crosstab_totals_names_and_expressions(tmp_path):
    workspace, database = make_sales(tmp_path)
    result = utilities.crosstab(database, utilities.CrosstabOptions(
        "XT1", "CUST_ID", "NAME", "AMT", "Total",
        create_names=True, names_name="XTNAME"))
    assert result.written == 2
    table = workspace.get("XT1")
    first = rows(table)[0]
    assert first["CUST_ID"] == "1001"
    assert "RICHARDSON" in first and first["RICHARDSON"] == "7.24"
    names = workspace.get("XTNAME")
    assert {"SHORT": "RICHARDSON", "FULL": "Richardson"} in rows(names)

    utilities.crosstab(database, utilities.CrosstabOptions(
        "XT2", "CUST_ID", "NAME", "AMT", "Count",
        columns=[utilities.CrosstabColumn("BAR", 'NAME="Barber"')]))
    counts = workspace.get("XT2")
    assert [row["BAR"] for row in rows(counts)] == ["0", "1"]


def test_post_add_subtract_replace_and_status(tmp_path):
    workspace, master = make_sales(tmp_path)
    transaction = workspace.create_database("TRAN", [
        Field("CUST_ID", "C", 4), Field("AMT", "N", 7, 2),
        Field("NAME", "C", 12), Field("POSTED", "L", 1)])
    transaction.append({"CUST_ID": "1001", "AMT": "1.00",
                        "NAME": "Updated", "POSTED": "0"})
    transaction.append({"CUST_ID": "4040", "AMT": "2.00",
                        "NAME": "Nobody", "POSTED": "0"})
    workspace.save_database(transaction)
    result = utilities.post(master, transaction, utilities.PostOptions(
        status_field="POSTED", mark_unmatched=True,
        fields=[utilities.PostField("AMT", "AMT", "Add"),
                utilities.PostField("NAME", "NAME", "Replace")]))
    assert result.written == 1
    assert result.updated == 2
    assert result.unmatched == 1
    target_rows = [row for row in rows(master) if row["CUST_ID"] == "1001"]
    assert {row["AMT"] for row in target_rows} == {"4.24", "5.00"}
    assert {row["NAME"] for row in target_rows} == {"Updated"}
    posted = [row for row in rows(transaction)]
    assert posted[0]["POSTED"] == "1"
    assert transaction.is_deleted(2)


def test_relational_join_intersect_subtract(tmp_path):
    workspace, purchase = make_sales(tmp_path)
    company = workspace.create_database("COMPANY", [
        Field("CUST", "C", 4), Field("CITY", "C", 10)])
    company.append({"CUST": "1001", "CITY": "Boston"})
    company.append({"CUST": "1021", "CITY": "Chicago"})
    indexing.save_index(company, indexing.IndexDefinition("CUSTC", "CUST"))
    other = workspace.create_database("OTHER", [Field("CUST", "C", 4)])
    indexing.save_index(other, indexing.IndexDefinition("CUSTO", "CUST"))

    result = utilities.relational(purchase, company,
                                  utilities.RelationalOptions(
                                      "Join", "JOIN1", "CUSTC",
                                      common_expression="CUST_ID",
                                      secondary_fields=[
                                          utilities.JoinField("COMPANY", "CITY")]))
    assert result.written == 3
    joined = workspace.get("JOIN1")
    assert [row["CITY"] for row in rows(joined)] == [
        "Boston", "Boston", "Chicago"]

    result = utilities.relational(purchase, company,
                                  utilities.RelationalOptions(
                                      "Intersect", "INT1", "CUSTC",
                                      common_expression="CUST_ID"))
    assert result.written == 3
    result = utilities.relational(purchase, company,
                                  utilities.RelationalOptions(
                                      "Subtract", "SUB1", "CUSTC",
                                      common_expression="CUST_ID"))
    assert result.written == 0


def test_relational_collision_and_outer_join(tmp_path):
    workspace, primary = make_sales(tmp_path)
    secondary = workspace.create_database("SEC", [
        Field("CUST_ID", "C", 4), Field("NOTE", "C", 8)])
    secondary.append({"CUST_ID": "1001", "NOTE": "one"})
    secondary.append({"CUST_ID": "1001", "NOTE": "two"})
    indexing.save_index(secondary, indexing.IndexDefinition("SECI", "CUST_ID"))
    result = utilities.relational(primary, secondary,
                                  utilities.RelationalOptions(
                                      "Join", "J2", "SECI",
                                      common_expression="CUST_ID"))
    joined = workspace.get("J2")
    names = [field.name for field in joined.fields]
    assert names[:4] == ["CUST_ID", "NAME", "AMT", "INV"]
    assert "CUST_ID2" in names
    assert result.written == 5  # due match per 1001, poi 1021 senza match
    assert [row["NOTE"] for row in rows(joined)].count("") == 1


def test_global_update_case_and_mark_range(tmp_path):
    workspace, database = make_sales(tmp_path)
    result = utilities.update_fields(database, [
        utilities.UpdateExpression("AMT", "AMT * 2")])
    assert result.updated == 3
    assert [row["AMT"] for row in rows(database)] == [
        "6.48", "8.00", "10.00"]
    result = utilities.change_case(database, ["NAME"], "Upper case")
    assert [row["NAME"] for row in rows(database)] == [
        "RICHARDSON", "RICHARDSON", "BARBER"]
    settings = indexing.RangeSettings(primary="CUST",
                                      show=indexing.SHOW_ALL,
                                      first_key="1021", last_key="1021")
    result = utilities.mark_range(database, True, settings)
    assert result.updated == 1
    assert database.is_deleted(3)
    utilities.mark_range(database, False, settings)
    assert not database.is_deleted(3)


def test_summary_total_too_large_shows_zero(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("T", [
        Field("K", "C", 2), Field("N", "N", 2, 0)])
    for _index in range(1000):
        database.append({"K": "A", "N": "99"})
    indexing.save_index(database, indexing.IndexDefinition("KI", "K"))
    database.set_primary_index("KI")
    utilities.summarize(database, utilities.SummarizeOptions(
        "S", [utilities.SummaryField("K", "Group"),
              utilities.SummaryField("N", "Total")]))
    total = rows(workspace.get("S"))[0]["N"]
    assert Decimal(total) == Decimal(0)
