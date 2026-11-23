"""O4 — motore delle regole di campo (capitolo 10)."""

import datetime

from adbx.data import indexing, rules
from adbx.data.fields import Field
from adbx.data.rules import (
    CascadingEntry,
    ConditionalDatabase,
    ConditionalGroup,
    FieldRule,
    LookupTable,
    MappingRow,
    PostingRule,
)
from adbx.data.workspace import Workspace


def make_database(tmp_path, name="AVSALES", fields=None):
    workspace = Workspace(tmp_path)
    database = workspace.create_database(name, fields or [
        Field("INV_NUMBER", "N", 6, 0),
        Field("INV_TYPE", "C", 8),
        Field("INV_DATE", "D", 8),
        Field("CODE", "C", 6),
        Field("QTY", "N", 4, 0),
        Field("ITEMPRICE", "N", 8, 2),
        Field("QUANTITY", "N", 4, 0),
        Field("SUBTOTAL", "N", 10, 2),
        Field("TAXRATE", "N", 5, 2),
        Field("INVTOTAL", "N", 10, 2),
        Field("SALUTATION", "C", 5),
        Field("FIRSTNAME", "C", 20),
        Field("ZIP", "C", 5),
        Field("HOMEPHONE", "C", 14),
        Field("NOTES", "M", 10),
    ])
    return workspace, database


def test_case_conversion_modes():
    assert rules.apply_case("alpha software", "Caps") == "ALPHA SOFTWARE"
    assert rules.apply_case("ALPHA SOFTWARE", "Lower") == "alpha software"
    assert rules.apply_case("alpha software", "First") == "Alpha software"
    assert rules.apply_case("alpha software", "Word") == "Alpha Software"
    assert rules.apply_case("ALPHA SOFTWARE", "X") == "Alpha software"
    assert rules.apply_case("alpha software", "None") == "alpha software"


def test_template_and_mask():
    template = "(   )   -    "
    assert rules.editable_positions(template) == [1, 2, 3, 5, 6, 7,
                                                 9, 10, 11, 12]
    display = rules.template_display(template, "6175552647")
    assert display == "(617)555-2647"
    assert rules.template_data(template, display) == "6175552647"
    assert rules.template_is_blank(template, template)
    assert not rules.template_is_blank(template, display)

    mask = "999-99-9999"
    assert rules.mask_error("", mask, "123-45-6789") == ""
    assert "digits" in rules.mask_error("", mask, "12A-45-6789")
    assert "uppercase" in rules.mask_error("", "AA", "aB")
    assert "letters" in rules.mask_error("", "aa", "a1")


def test_template_with_fixed_pipe_and_mask_on_editable_slots():
    template = "(|||)|||-||||".replace("|", " ")
    assert rules.mask_slots(template, "9999999999")[1] == "9"


def test_default_value_and_expression(tmp_path):
    _workspace, database = make_database(tmp_path)
    value_rule = FieldRule("TAXRATE", default_mode="Value", default="8.25")
    values = {"ITEMPRICE": "2.49", "QUANTITY": "1"}
    assert rules.default_value(value_rule, database, values) == "8.25"

    date_rule = FieldRule("INV_DATE", default_mode="Expression",
                          default="DATE()")
    assert rules.default_value(date_rule, database, values) == \
        datetime.date.today().strftime("%Y%m%d")

    expression_rule = FieldRule(
        "TAXRATE", default_mode="Expression",
        default='IF(QUANTITY>10,7.5,8.25)')
    assert rules.default_value(expression_rule, database,
                               {"QUANTITY": "12"}) == "7.50"
    assert rules.default_value(expression_rule, database,
                               {"QUANTITY": "2"}) == "8.25"


def test_increment_numeric_character_and_date(tmp_path):
    _workspace, database = make_database(tmp_path)
    number = database.field("INV_NUMBER")
    assert rules.increment_value(number, "11001") == "11002"
    assert rules.increment_value(database.field("ITEMPRICE"), "2.49") == "3.49"
    assert rules.increment_value(database.field("INV_DATE"), "19931231") == \
        "19940101"

    text = Field("CODE", "C", 8)
    assert rules.increment_value(text, "12") == "13"
    assert rules.increment_value(text, "A9") == "B0"
    assert rules.increment_value(text, "13Z") == "14A"
    assert rules.increment_value(text, "ZZ") == "AAA"

    template = "INV   "
    assert rules.increment_value(text, "INV001", template) == "INV002"


def test_next_increment_uses_last_physical_record(tmp_path):
    _workspace, database = make_database(tmp_path)
    database.append({"INV_NUMBER": "1001", "INV_TYPE": "Sale"})
    database.append({"INV_NUMBER": "1002", "INV_TYPE": "Rental"})
    rule = FieldRule("INV_NUMBER", increment="Records")
    assert rules.next_increment(rule, database,
                                database.field("INV_NUMBER")) == "1003"


def test_required_validation_and_double_entry(tmp_path):
    _workspace, database = make_database(tmp_path)
    required = FieldRule("INV_TYPE", required="Yes")
    assert rules.is_required(required, database, {"INV_TYPE": ""})
    assert rules.missing_required(required, database, {"INV_TYPE": ""})
    assert not rules.missing_required(required, database, {"INV_TYPE": "Sale"})

    conditional = FieldRule("INV_TYPE", required="Expression",
                            required_expression="QUANTITY>0")
    assert rules.is_required(conditional, database, {"QUANTITY": "2"})
    assert not rules.is_required(conditional, database, {"QUANTITY": "0"})

    validation = FieldRule(
        "ITEMPRICE", validation="ITEMPRICE>0",
        validation_message="Price must be positive.")
    assert rules.validation_error(
        validation, database, {"ITEMPRICE": "0"}) == "Price must be positive."
    assert rules.validation_error(validation, database,
                                  {"ITEMPRICE": "2.49"}) == ""

    double = FieldRule("INV_TYPE", double_entry="Expression",
                       double_entry_expression='INV_TYPE="Credit"')
    assert rules.double_entry_required(double, database, {"INV_TYPE": "Credit"})
    assert not rules.double_entry_required(double, database,
                                           {"INV_TYPE": "Sale"})


def test_skip_expression(tmp_path):
    _workspace, database = make_database(tmp_path)
    rule = FieldRule("SALUTATION", skip_expression='LOWER(FIRSTNAME)="john"')
    assert rules.should_skip(rule, database, {"FIRSTNAME": "John"})
    assert not rules.should_skip(rule, database, {"FIRSTNAME": "Jane"})


def test_calculated_fields_chain(tmp_path):
    _workspace, database = make_database(tmp_path)
    rule_map = {
        "SUBTOTAL": FieldRule("SUBTOTAL", value="Calculated",
                              expression="ITEMPRICE*QUANTITY"),
        "INVTOTAL": FieldRule("INVTOTAL", value="Calculated",
                              expression="SUBTOTAL*(1+(TAXRATE/100))"),
    }
    values = {"ITEMPRICE": "2.49", "QUANTITY": "3", "TAXRATE": "8.25"}
    rules.recalculate(rule_map, database, values)
    assert values["SUBTOTAL"] == "7.47"
    assert values["INVTOTAL"] == "8.09"


def test_lookup_table_choices_and_fill(tmp_path):
    _workspace, database = make_database(tmp_path)
    table = LookupTable(
        columns=["INV_DATE"],
        rows=[["Sale", "19930101"], ["Rental", "19930202"],
              ["Credit", "19930303"]])
    rule = FieldRule("INV_TYPE", lookup=True, lookup_source="Table",
                     table=table)
    values = {"INV_TYPE": ""}
    choices = rules.lookup_choices(rule, database, values)
    assert choices.headers == ["INV_TYPE", "INV_DATE"]
    assert choices.values == ["Sale", "Rental", "Credit"]
    filled = rules.lookup_fill(rule, database, values, "Rental")
    assert filled["INV_TYPE"] == "Rental"
    assert filled["INV_DATE"] == "19930202"


def test_lookup_validation_exists_and_doesnt_exist(tmp_path):
    _workspace, database = make_database(tmp_path)
    table = LookupTable(rows=[["Sale"], ["Rental"]])
    exists = FieldRule("INV_TYPE", lookup=True,
                       lookup_validation="Exists", table=table)
    assert rules.lookup_validation_error(
        exists, database, {"INV_TYPE": "Donate"})
    assert rules.lookup_validation_error(
        exists, database, {"INV_TYPE": "Sale"}) == ""

    disallowed = FieldRule("INV_TYPE", lookup=True,
                           lookup_validation="Doesn't Exist", table=table)
    assert rules.lookup_validation_error(
        disallowed, database, {"INV_TYPE": "Sale"})
    assert rules.lookup_validation_error(
        disallowed, database, {"INV_TYPE": "Donate"}) == ""


def test_lookup_database_mapping_and_order(tmp_path):
    workspace, database = make_database(tmp_path)
    patrons = workspace.create_database("AVPATRON", [
        Field("CUST_ID", "C", 6), Field("NAME", "C", 20),
        Field("CITY", "C", 15)])
    patrons.append({"CUST_ID": "1002", "NAME": "Bob", "CITY": "Placid"})
    patrons.append({"CUST_ID": "1001", "NAME": "Ada", "CITY": "Rome"})
    indexing.save_index(patrons, indexing.IndexDefinition(
        "AVPATID", "CUST_ID"))
    indexing.save_index(patrons, indexing.IndexDefinition(
        "AVPATNAM", "NAME"))
    patrons.set_primary_index("AVPATNAM")
    rule = FieldRule(
        "INV_TYPE", lookup=True, lookup_source="Database",
        lookup_database="AVPATRON", linking_index="AVPATID",
        display_index="AVPATNAM",
        mapping=[MappingRow("CUST_ID", "INV_TYPE"),
                 MappingRow("NAME", "SALUTATION", display=True),
                 MappingRow("CITY", "FIRSTNAME", display=False)])
    choices = rules.lookup_choices(rule, database, {"INV_TYPE": "1001"})
    assert choices.values[0] == "Ada" or choices.values[0] == "1001"
    assert [value for value in choices.values] == ["1001", "1002"]
    filled = rules.lookup_fill(rule, database, {"INV_TYPE": "1002"}, "1002")
    assert filled["INV_TYPE"] == "1002"
    assert filled["SALUTATION"] == "Bob"
    assert filled["FIRSTNAME"] == "Placid"


def test_cascading_table(tmp_path):
    _workspace, database = make_database(tmp_path)
    rule = FieldRule(
        "INV_TYPE", lookup=True, lookup_source="Advanced",
        advanced="Cascading table",
        cascading=[CascadingEntry(0, "Tape"),
                   CascadingEntry(1, "VHS"),
                   CascadingEntry(1, "Beta"),
                   CascadingEntry(0, "Disc"),
                   CascadingEntry(1, "DVD~Digital Video Disc"),
                   CascadingEntry(1, "CD^")])
    labels, endpoints = rules.cascading_choices(rule, ())
    assert labels == ["Tape", "Disc"]
    assert endpoints == [False, False]
    labels, endpoints = rules.cascading_choices(rule, ("Disc",))
    assert labels == ["DVD", "CD"]
    assert endpoints == [True, True]
    value, endpoint = rules.cascading_value(rule, ("Disc",), "DVD")
    assert (value, endpoint) == ("Digital Video Disc", True)
    value, endpoint = rules.cascading_value(rule, ("Disc",), "CD")
    assert (value, endpoint) == ("Disc. CD", True)


def test_conditional_table_and_filter(tmp_path):
    _workspace, database = make_database(tmp_path)
    table_air = LookupTable(rows=[["Federal Express"], ["Airborne"]])
    table_ground = LookupTable(rows=[["US Mail"], ["UPS"]])
    fallback = LookupTable(rows=[["Other"]])
    rule = FieldRule(
        "INV_TYPE", lookup=True, lookup_source="Advanced",
        advanced="Conditional table", table=fallback,
        conditional_tables=[
            ConditionalGroup('SALUTATION="Air"', table=table_air),
            ConditionalGroup('SALUTATION="Ground"', table=table_ground)])
    assert rules.lookup_choices(
        rule, database, {"SALUTATION": "Air"}).values == [
            "Federal Express", "Airborne"]
    assert rules.lookup_choices(
        rule, database, {"SALUTATION": "Ground"}).values == ["US Mail", "UPS"]
    assert rules.lookup_choices(
        rule, database, {"SALUTATION": "Sea"}).values == ["Other"]


def test_conditional_database(tmp_path):
    workspace, database = make_database(tmp_path)
    small = workspace.create_database("SMALL", [
        Field("PRICE", "N", 8, 2)])
    small.append({"PRICE": "10.00"})
    large = workspace.create_database("LARGE", [
        Field("PRICE", "N", 8, 2)])
    large.append({"PRICE": "20.00"})
    rule = FieldRule(
        "ITEMPRICE", lookup=True, lookup_source="Advanced",
        advanced="Conditional database", lookup_database="SMALL",
        mapping=[MappingRow("PRICE", "ITEMPRICE")],
        conditional_databases=[
            ConditionalDatabase('SALUTATION="Large"', "LARGE")])
    choices = rules.lookup_choices(rule, database, {"SALUTATION": "Large"})
    assert choices.values == ["20.00"]
    assert rules.lookup_choices(
        rule, database, {"SALUTATION": "Small"}).values == ["10.00"]


def test_post_data_add_subtract_replace_and_difference(tmp_path):
    workspace, database = make_database(tmp_path)
    stock = workspace.create_database("STOCK", [
        Field("CODE", "C", 6), Field("QOH", "N", 8, 0)])
    stock.append({"CODE": "A1", "QOH": "100"})
    indexing.save_index(stock, indexing.IndexDefinition("STOCKCOD", "CODE"))
    posting = PostingRule("STOCK", "QOH", "Subtract", "", "",
                          linking_index="STOCKCOD", common="CODE")
    rule = FieldRule("QTY", post_data=True, postings=[posting])
    warnings = rules.post_values(
        rule, database, {}, {"CODE": "A1", "QTY": "5"}, rule)
    assert warnings == []
    assert stock.read(1)["QOH"] == "95"

    # In modifica si posta la differenza fra vecchio e nuovo valore.
    rules.post_values(rule, database, {"CODE": "A1", "QTY": "5"},
                      {"CODE": "A1", "QTY": "8"}, rule)
    assert stock.read(1)["QOH"] == "92"

    posting.mode = "Add"
    rules.post_values(rule, database, {"CODE": "A1"},
                      {"CODE": "A1", "QTY": "2"}, rule)
    assert stock.read(1)["QOH"] == "94"

    posting.mode = "Replace"
    rules.post_values(rule, database, {"CODE": "A1"},
                      {"CODE": "A1", "QTY": "7"}, rule)
    assert stock.read(1)["QOH"] == "7"


def test_set_level_rule_replaces_database_rule_entirely():
    database_rule = FieldRule("INV_TYPE", case="Caps", required="Yes",
                              prompt="Database prompt")
    set_rule = FieldRule("INV_TYPE", default_mode="Value", default="Sale")
    effective = rules.resolve_rule(database_rule, set_rule)
    assert effective is set_rule
    assert effective.case == "None" and effective.required == "No"

    empty_set_rule = FieldRule("INV_TYPE")
    assert rules.resolve_rule(database_rule, empty_set_rule) is database_rule

    resolved = rules.resolve_rules({"INV_TYPE": database_rule},
                                   {"INV_TYPE": set_rule})
    assert resolved["INV_TYPE"] is set_rule


def test_rules_persist_and_survive_field_rename(tmp_path):
    workspace, database = make_database(tmp_path)
    database.save_field_rule(FieldRule("INV_TYPE", case="Caps",
                                       lookup=True,
                                       table=LookupTable(rows=[["Sale"]])))
    assert database.field_rule("INV_TYPE").case == "Caps"
    assert database.field_rule("INV_TYPE").table.choices() == ["Sale"]

    updated = workspace.alter_database(
        database.name, [(field.name, field) for field in database.fields])
    assert updated.field_rule("INV_TYPE") is not None

    fields = [("INV_TYPE", Field("KIND", "C", 8))]
    fields += [(field.name, field) for field in database.fields
               if field.name != "INV_TYPE"]
    updated = workspace.alter_database(database.name, fields)
    assert updated.field_rule("INV_TYPE") is None
    assert updated.field_rule("KIND").case == "Caps"


def test_re_evaluate_applies_case_and_calculation(tmp_path):
    _workspace, database = make_database(tmp_path)
    database.append({"INV_TYPE": "sale", "ITEMPRICE": "2.00",
                     "QUANTITY": "3", "TAXRATE": "0"})
    rule_map = {
        "INV_TYPE": FieldRule("INV_TYPE", case="Caps"),
        "SUBTOTAL": FieldRule("SUBTOTAL", value="Calculated",
                              expression="ITEMPRICE*QUANTITY"),
    }
    for rule in rule_map.values():
        database.save_field_rule(rule)
    changed, problems = rules.re_evaluate(database, database.field_rules())
    assert changed == 1 and problems == []
    record = database.read(database.sequences()[0])
    assert record["INV_TYPE"] == "SALE"
    assert record["SUBTOTAL"] == "6.00"


def test_cascading_lookup_validation_uses_endpoints(tmp_path):
    _workspace, database = make_database(tmp_path)
    rule = FieldRule(
        "INV_TYPE", lookup=True, lookup_source="Advanced",
        advanced="Cascading table", lookup_validation="Exists",
        cascading=[CascadingEntry(0, "Tape"),
                   CascadingEntry(1, "VHS"),
                   CascadingEntry(1, "Beta~BETACAM")])
    assert rules.lookup_validation_error(
        rule, database, {"INV_TYPE": "VHS"}) == ""
    assert rules.lookup_validation_error(
        rule, database, {"INV_TYPE": "BETACAM"}) == ""
    assert rules.lookup_validation_error(
        rule, database, {"INV_TYPE": "Tape"})


def test_conditional_table_fills_related_fields(tmp_path):
    _workspace, database = make_database(tmp_path)
    group = ConditionalGroup('SALUTATION="Air"', table=LookupTable(
        columns=["INV_DATE"], rows=[["Federal Express", "19930101"]]))
    rule = FieldRule(
        "INV_TYPE", lookup=True, lookup_source="Advanced",
        advanced="Conditional table", conditional_tables=[group])
    filled = rules.lookup_fill(rule, database, {"SALUTATION": "Air"},
                               "Federal Express")
    assert filled["INV_TYPE"] == "Federal Express"
    assert filled["INV_DATE"] == "19930101"
