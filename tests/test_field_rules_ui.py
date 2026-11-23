"""O4 — lezioni 11-13: regole di campo e lookup dall'interfaccia."""

from adbx.data import indexing
from adbx.data.fields import Field
from adbx.data.rules import FieldRule
from adbx.data.workspace import Workspace
from adbx.screen.keys import Key
from adbx.shell.controller import ShellController


def type_text(target, text):
    for char in text:
        target.handle(Key("SPACE" if char == " " else char,
                          shift=char.isupper()))


def make_controller(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVSALES", [
        Field("INV_NUMBER", "N", 6, 0), Field("INV_TYPE", "C", 8),
        Field("INV_DATE", "D", 8), Field("ITEMPRICE", "N", 8, 2),
        Field("QUANTITY", "N", 4, 0), Field("SUBTOTAL", "N", 10, 2),
        Field("INVTOTAL", "N", 10, 2), Field("TAXRATE", "N", 5, 2),
        Field("SALUTATION", "C", 5), Field("FIRSTNAME", "C", 20),
        Field("LASTNAME", "C", 20), Field("ZIP", "C", 5),
        Field("HOMEPHONE", "C", 14),
    ])
    return ShellController(tmp_path, open_path=database.source)


def open_field_rules(controller):
    controller.handle(Key("D"))
    assert controller.overlay.target == "design"
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.overlay.target == "field-rules"
    controller.handle(Key("ENTER"))
    assert controller.base == "rules"


def goto_field(session, name):
    session.field_index = [field.name for field in session.fields].index(name)


def set_rule(session, name, *keys):
    goto_field(session, name)
    session.window = "fields"
    session.handle(Key("F9"))
    for key in keys:
        session.handle(key)


def test_lesson_11_field_rules_from_menu(tmp_path):
    controller = make_controller(tmp_path)
    open_field_rules(controller)
    session = controller.rules_session
    assert session is not None

    # Auto-increment + required su INV_NUMBER.
    set_rule(session, "INV_NUMBER", Key("DOWN"), Key("DOWN"), Key("RIGHT"),
             Key("PGDN"), Key("ENTER"))
    assert session.rules["INV_NUMBER"].increment == "Records"
    assert session.rules["INV_NUMBER"].required == "Yes"

    # Case Convert su SALUTATION e FIRSTNAME.
    set_rule(session, "SALUTATION", Key("DOWN"), Key("RIGHT"), Key("F9"))
    set_rule(session, "FIRSTNAME", Key("DOWN"), Key("RIGHT"), Key("RIGHT"),
             Key("RIGHT"), Key("F9"))
    assert session.rules["SALUTATION"].case == "Caps"
    assert session.rules["FIRSTNAME"].case == "First"

    # Prompt personalizzato su INV_TYPE (page 1, ultima riga).
    set_rule(session, "INV_TYPE", Key("DOWN"), Key("DOWN"), Key("DOWN"),
             Key("DOWN"), Key("DOWN"), Key("DOWN"), Key("DOWN"),
             Key("ENTER"))
    type_text(session, "Enter SALE or RENTAL")
    session.handle(Key("ENTER"))
    session.handle(Key("F9"))
    assert session.rules["INV_TYPE"].prompt == "Enter SALE or RENTAL"

    # Mask + exceptions su ZIP.
    set_rule(session, "ZIP", Key("DOWN"), Key("DOWN"), Key("DOWN"),
             Key("ENTER"))
    type_text(session, "99999")
    session.handle(Key("ENTER"))
    session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    session.handle(Key("F9"))
    assert session.rules["ZIP"].mask == "99999"
    assert session.rules["ZIP"].allow_exceptions

    # Template e mask su HOMEPHONE.
    set_rule(session, "HOMEPHONE", Key("DOWN"), Key("DOWN"), Key("ENTER"))
    type_text(session, "(   )   -    ")
    session.handle(Key("ENTER"))
    session.handle(Key("DOWN"))
    session.handle(Key("ENTER"))
    type_text(session, "9999999999")
    session.handle(Key("ENTER"))
    session.handle(Key("F9"))
    assert session.rules["HOMEPHONE"].template == "(   )   -    "
    assert session.rules["HOMEPHONE"].mask == "9999999999"

    # Default expression DATE() e default costante 8.25.
    set_rule(session, "INV_DATE", Key("DOWN"), Key("ENTER"), Key("ENTER"),
             Key("DOWN"), Key("ENTER"))
    type_text(session, "DATE()")
    session.handle(Key("ENTER"))
    session.handle(Key("F9"))
    set_rule(session, "TAXRATE", Key("DOWN"), Key("ENTER"), Key("DOWN"),
             Key("ENTER"))
    type_text(session, "8.25")
    session.handle(Key("ENTER"))
    session.handle(Key("F9"))
    assert session.rules["INV_DATE"].default_mode == "Expression"
    assert session.rules["TAXRATE"].default_mode == "Value"

    # Campi calcolati.
    set_rule(session, "SUBTOTAL", Key("RIGHT"), Key("DOWN"), Key("ENTER"))
    type_text(session, "ITEMPRICE*QUANTITY")
    session.handle(Key("ENTER"))
    session.handle(Key("F9"))
    set_rule(session, "INVTOTAL", Key("RIGHT"), Key("DOWN"), Key("ENTER"))
    type_text(session, "SUBTOTAL*(1+(TAXRATE/100))")
    session.handle(Key("ENTER"))

    controller.handle(Key("F10"))
    assert controller.base == "menu"
    assert controller.overlay.kind == "message"
    rules = controller.database.field_rules()
    assert rules["SUBTOTAL"].expression == "ITEMPRICE*QUANTITY"
    assert rules["INVTOTAL"].value == "Calculated"
    assert rules["ZIP"].mask == "99999"


def test_lesson_12_lookup_table_and_choices(tmp_path):
    controller = make_controller(tmp_path)
    open_field_rules(controller)
    session = controller.rules_session
    set_rule(session, "INV_TYPE", Key("PGDN"), Key("PGDN"), Key("ENTER"))
    assert session.current_rule().lookup
    session.handle(Key("F7"))
    assert session.editor is not None
    type_text(session, "Sale")
    session.handle(Key("F6"))
    type_text(session, "Rental")
    session.handle(Key("F6"))
    type_text(session, "Credit")
    session.handle(Key("F10"))
    assert session.editor is None
    assert session.current_rule().table.choices() == ["Sale", "Rental",
                                                      "Credit"]
    # Exists, no exceptions.
    session.handle(Key("DOWN"))
    session.handle(Key("RIGHT"))
    assert session.current_rule().lookup_validation == "Exists"
    session.handle(Key("DOWN"))
    session.handle(Key("RIGHT"))
    assert session.current_rule().lookup_allow_exceptions
    controller.handle(Key("F10"))
    assert controller.base == "menu"

    database = controller.database
    rule = database.field_rule("INV_TYPE")
    assert rule is not None and rule.lookup_validation == "Exists"

    # In immissione F3 apre la tabella e la scelta riempie il campo.
    controller.handle(Key("ENTER"))  # chiude il messaggio
    controller.handle(Key("V"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.records.mode == "enter"
    controller.records.field_index = 1
    controller.records._load_field()
    controller.handle(Key("F3"))
    assert controller.records.lookup is not None
    assert controller.records.lookup.choices.values == ["Sale", "Rental",
                                                        "Credit"]
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.records.draft["INV_TYPE"] == "Rental"

    # Un valore fuori tabella viene rifiutato dal commit.
    controller.records.field_index = 1
    controller.records.edit_text = "Donate"
    controller.records.edit_cursor = 6
    controller.handle(Key("ENTER"))
    assert "not in the lookup" in controller.records.status


def test_lookup_database_mapping_editor(tmp_path):
    controller = make_controller(tmp_path)
    workspace = controller.database.workspace
    patrons = workspace.create_database("AVPATRON", [
        Field("CUST_ID", "C", 6), Field("NAME", "C", 20),
        Field("CITY", "C", 15)])
    patrons.append({"CUST_ID": "1001", "NAME": "Ada", "CITY": "Rome"})
    patrons.append({"CUST_ID": "1002", "NAME": "Bob", "CITY": "Placid"})
    indexing.save_index(patrons, indexing.IndexDefinition(
        "AVPATID", "CUST_ID"))

    open_field_rules(controller)
    session = controller.rules_session
    set_rule(session, "INV_TYPE", Key("PGDN"), Key("PGDN"), Key("ENTER"),
             Key("DOWN"), Key("DOWN"), Key("DOWN"), Key("DOWN"),
             Key("DOWN"))
    assert session.rows()[session.row].key == "lookup_source"
    session.handle(Key("ENTER"))  # Table -> Database
    session.handle(Key("F9"))
    # Compila i campi della lookup database.
    session.window = "rules"
    goto_field(session, "INV_TYPE")
    for _key in (Key("DOWN"),):
        session.row = [row.key for row in session.rows()].index(
            "lookup_database")
    session.handle(Key("ENTER"))
    type_text(session, "AVPATRON")
    session.handle(Key("ENTER"))
    session.row = [row.key for row in session.rows()].index("linking_index")
    session.handle(Key("ENTER"))
    type_text(session, "AVPATID")
    session.handle(Key("ENTER"))
    assert session.current_rule().lookup_database == "AVPATRON"
    assert session.current_rule().linking_index == "AVPATID"

    session.handle(Key("F7"))
    editor = session.editor
    assert editor is not None
    # Prima riga: CUST_ID -> INV_TYPE.
    editor.set_cell(0, 0, "CUST_ID")
    editor.set_cell(0, 1, "INV_TYPE")
    editor._load_cell()
    editor.handle(Key("F6"))
    editor.row = 1
    editor._load_cell()
    editor.set_cell(1, 0, "NAME")
    editor.set_cell(1, 1, "SALUTATION")
    editor.set_cell(1, 4, "Yes")
    editor._load_cell()
    session.handle(Key("F10"))
    assert session.editor is None
    assert len(session.current_rule().mapping) == 2
    controller.handle(Key("F10"))
    assert controller.base == "menu"

    # La lookup mostra i clienti e riempie i campi mappati.
    saved_rule = controller.database.field_rule("INV_TYPE")
    assert saved_rule.lookup_source == "Database"
    assert len(saved_rule.mapping) == 2
    from adbx.data import rules as field_rules
    filled = field_rules.lookup_fill(saved_rule, controller.database,
                                     {"INV_TYPE": "1002"}, "1002")
    assert filled.get("SALUTATION") == "Bob", filled
    controller.handle(Key("ENTER"))
    controller.handle(Key("V"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    controller.records.field_index = 1
    controller.records._load_field()
    controller.handle(Key("F3"))
    assert len(controller.records.rule_map["INV_TYPE"].mapping) == 2
    lookup = controller.records.lookup
    assert lookup is not None
    assert lookup.choices.values == ["1001", "1002"]
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    assert controller.records.draft["INV_TYPE"] == "1002"
    assert controller.records.draft["SALUTATION"] == "Bob"


def test_re_evaluate_and_erase_from_menu(tmp_path):
    controller = make_controller(tmp_path)
    database = controller.database
    database.append({"INV_TYPE": "sale", "ITEMPRICE": "2.00",
                     "QUANTITY": "3", "TAXRATE": "0"})
    database.save_field_rule(FieldRule("INV_TYPE", case="Caps"))
    database.save_field_rule(FieldRule("SUBTOTAL", value="Calculated",
                                       expression="ITEMPRICE*QUANTITY"))

    controller.handle(Key("D"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Re-evaluate
    assert controller.overlay.kind == "message"
    assert "1 record(s)" in controller.overlay.text
    record = database.read(database.sequences()[0])
    assert record["INV_TYPE"] == "SALE"
    assert record["SUBTOTAL"] == "6.00"

    controller.handle(Key("ENTER"))
    controller.handle(Key("D"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("DOWN"))
    controller.handle(Key("ENTER"))  # Erase
    assert controller.overlay.kind == "confirm"
    controller.handle(Key("ENTER"))
    assert controller.database.field_rules() == {}
