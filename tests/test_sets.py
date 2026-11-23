"""O5 — modello dei set, link, closest, integrità e cascading."""

import pytest

from adbx.data import indexing
from adbx.data.fields import Field
from adbx.data.sets import Link, SetDefinition, SetError
from adbx.data.workspace import Workspace


def make_invoice_set(tmp_path):
    workspace = Workspace(tmp_path)
    header = workspace.create_database("AVHEADER", [
        Field("INV_NO", "C", 6), Field("CUST_ID", "C", 6),
        Field("INV_DATE", "D", 8)])
    items = workspace.create_database("AVITEMS", [
        Field("INV_NO", "C", 6), Field("TAPE_ID", "C", 6),
        Field("QUANTITY", "N", 3, 0)])
    patrons = workspace.create_database("AVPATRON", [
        Field("CUST_ID", "C", 6), Field("NAME", "C", 20),
        Field("CITY", "C", 15)])
    movies = workspace.create_database("AVMOVIES", [
        Field("TAPE_ID", "C", 6), Field("TITLE", "C", 30)])
    indexing.save_index(items, indexing.IndexDefinition("AVINVNO", "INV_NO"))
    indexing.save_index(patrons, indexing.IndexDefinition(
        "AVPATID", "CUST_ID"))
    indexing.save_index(movies, indexing.IndexDefinition(
        "AVMOVID", "TAPE_ID"))

    patrons.append({"CUST_ID": "1002", "NAME": "Bob", "CITY": "Placid"})
    patrons.append({"CUST_ID": "1001", "NAME": "Ada", "CITY": "Rome"})
    movies.append({"TAPE_ID": "1018", "TITLE": "Dumbo"})
    movies.append({"TAPE_ID": "1025", "TITLE": "Benji"})
    header.append({"INV_NO": "A015", "CUST_ID": "1001",
                   "INV_DATE": "19930505"})
    header.append({"INV_NO": "A016", "CUST_ID": "1002",
                   "INV_DATE": "19930506"})
    items.append({"INV_NO": "A015", "TAPE_ID": "1018", "QUANTITY": "1"})
    items.append({"INV_NO": "A015", "TAPE_ID": "1025", "QUANTITY": "2"})
    items.append({"INV_NO": "A016", "TAPE_ID": "1018", "QUANTITY": "1"})

    definition = SetDefinition(workspace, "AVIDEO", "Alpha Video Invoicing",
                               "AVHEADER")
    definition.links = [
        Link("AVHEADER", "AVPATRON", "AVPATID", "CUST_ID", "First"),
        Link("AVHEADER", "AVITEMS", "AVINVNO", "INV_NO", "All",
             referential=True, cascading_updates=True,
             cascading_deletes=True),
        Link("AVITEMS", "AVMOVIES", "AVMOVID", "TAPE_ID", "First",
             edit_child="No", add_child="No"),
    ]
    definition.save()
    return workspace, definition, header, items, patrons, movies


def test_set_persists_and_has_tree(tmp_path):
    workspace, definition, _header, _items, _patrons, _movies = \
        make_invoice_set(tmp_path)
    restored = workspace.get_set("AVIDEO")
    assert restored is not None
    assert restored.description == "Alpha Video Invoicing"
    assert restored.primary == "AVHEADER"
    assert restored.database_names() == ["AVHEADER", "AVPATRON", "AVITEMS",
                                         "AVMOVIES"]
    assert workspace.set_names() == ["AVIDEO"]
    assert restored.children_of("AVHEADER")[0].child == "AVPATRON"
    assert restored.link_for("AVITEMS").one_to_many


def test_linked_rows_first_last_all_closest(tmp_path):
    _workspace, definition, header, _items, _patrons, _movies = \
        make_invoice_set(tmp_path)
    values = header.read(header.sequences()[0])
    patron_link = definition.link_for("AVPATRON")
    related = definition.linked_rows(patron_link, values)
    assert [row[1]["NAME"] for row in related] == ["Ada"]

    items_link = definition.link_for("AVITEMS")
    related = definition.linked_rows(items_link, values)
    assert [row[1]["TAPE_ID"] for row in related] == ["1018", "1025"]
    all_children = definition.child_rows_all(values)
    assert len(all_children) == 1
    assert len(all_children[0][1]) == 2

    # Closest: se manca il match prende il primo figlio successivo.
    closest = Link("AVHEADER", "AVPATRON", "AVPATID", "CUST_ID", "Closest")
    definition.links[-1] = closest
    values["CUST_ID"] = "1000"
    related = definition.linked_rows(closest, values)
    assert related[0][1]["CUST_ID"] == "1001"


def test_closest_picks_next_key_in_index_order(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create_database("P", [Field("KEY", "C", 6),
                                     Field("NAME", "C", 10)])
    child = workspace.create_database("C", [Field("KEY", "C", 6),
                                            Field("VALUE", "C", 10)])
    indexing.save_index(child, indexing.IndexDefinition("CKEY", "KEY"))
    for key in ("1002", "1001", "1004"):
        child.append({"KEY": key, "VALUE": key + "-v"})
    definition = SetDefinition(workspace, "S", "", "P")
    definition.links = [Link("P", "C", "CKEY", "KEY", "Closest")]
    definition.save()
    rows = definition.linked_rows(definition.links[0], {"KEY": "1003"})
    assert rows and rows[0][1]["KEY"] == "1004"


def test_flat_fields_and_values(tmp_path):
    _workspace, definition, header, _items, _patrons, _movies = \
        make_invoice_set(tmp_path)
    fields = definition.flat_fields()
    labels = [label for _database, _field, label in fields]
    assert "INV_NO" in labels
    assert "AVPATRON.NAME" in labels
    assert not any(label.startswith("AVITEMS.") for label in labels)
    values = definition.flat_values(header.read(header.sequences()[0]))
    assert values[("AVHEADER", "INV_NO")] == "A015"
    assert values[("AVPATRON", "NAME")] == "Ada"


def test_integrity_mapping_default_and_custom(tmp_path):
    _workspace, definition, _header, _items, _patrons, _movies = \
        make_invoice_set(tmp_path)
    item_link = definition.link_for("AVITEMS")
    matrix = definition.integrity_rows(item_link)
    assert ("INV_NO", "INV_NO") in matrix
    item_link.integrity = [("INV_NO", "INV_NO"),
                           ("CUST_ID", "TAPE_ID")]
    assert definition.integrity_rows(item_link) == [
        ("INV_NO", "INV_NO"), ("CUST_ID", "TAPE_ID")]


def test_cascading_update_and_delete(tmp_path):
    _workspace, definition, header, items, _patrons, _movies = \
        make_invoice_set(tmp_path)
    seq = header.sequences()[0]
    old = header.read(seq)
    new = dict(old, INV_NO="A020")
    definition.update_parent(seq, new)
    assert {items.read(row)["INV_NO"] for row in items.sequences()} == {
        "A020", "A016"}

    definition.delete_parent(seq)
    assert header.is_deleted(seq)
    item_seqs = [row for row in items.sequences(include_deleted=True)
                 if items.read(row)["INV_NO"] == "A020"]
    assert item_seqs and all(items.is_deleted(row) for row in item_seqs)

    definition.undelete_parent(seq)
    assert not header.is_deleted(seq)
    assert all(not items.is_deleted(row) for row in item_seqs)


def test_include_parent_if_and_set_filter(tmp_path):
    _workspace, definition, header, _items, _patrons, _movies = \
        make_invoice_set(tmp_path)
    patron_link = definition.link_for("AVPATRON")
    patron_link.include_parent = "Has Related Child"
    header.append({"INV_NO": "A099", "CUST_ID": "9999",
                   "INV_DATE": "19930507"})
    visible = definition.visible_parent_sequences()
    assert header.sequences()[-1] not in visible

    definition.filter_active = True
    definition.filter = 'CUST_ID="1002"'
    assert definition.parent_sequences() == [2]


def test_limits_and_cycles(tmp_path):
    workspace = Workspace(tmp_path)
    fields = [Field("KEY", "C", 4)]
    primary = workspace.create_database("P", fields)
    for index in range(10):
        workspace.create_database(f"C{index}", fields)
    definition = SetDefinition(workspace, "BIG", "", "P")
    definition.links = [Link("P", f"C{index}", "", "KEY")
                        for index in range(10)]
    with pytest.raises(SetError, match="at most"):
        definition.validate()

    definition.links = [Link("P", "C0", "", "KEY"),
                        Link("P", "C1", "", "KEY")]
    s = SetDefinition(workspace, "S", "", "P")
    s.links = [Link("P", "C0", "", "KEY"),
               Link("P", "C1", "", "KEY")]
    s.save()
    # Due link All dallo stesso genitore sono rifiutati.
    s.links[0].link_to = "All"
    s.links[1].link_to = "All"
    with pytest.raises(SetError, match="one-to-many"):
        s.validate()
    assert not primary.count() and primary.name == "P"


def test_duplicate_databases(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create_database("P", [Field("KEY", "C", 4)])
    workspace.create_database("C", [Field("KEY", "C", 4)])
    definition = SetDefinition(workspace, "S", "", "P")
    definition.links = [Link("P", "C", "", "KEY"),
                        Link("P", "C", "", "KEY")]
    with pytest.raises(SetError, match="only once"):
        definition.validate()


def test_link_filter_and_show_mode(tmp_path):
    _workspace, definition, header, items, _patrons, _movies = \
        make_invoice_set(tmp_path)
    items.delete(1)
    link = definition.link_for("AVITEMS")
    link.show_mode = "all"
    assert len(definition.linked_rows(link,
                                      header.read(header.sequences()[0]))) == 2
    link.show_mode = "deleted"
    assert [row[0] for row in definition.linked_rows(
        link, header.read(header.sequences()[0]))] == [1]


def test_add_child_and_integrity(tmp_path):
    _workspace, definition, header, items, _patrons, _movies = \
        make_invoice_set(tmp_path)
    link = definition.link_for("AVITEMS")
    link.add_child = "Yes"
    parent = header.read(header.sequences()[0])
    seq = definition.add_child(link, parent)
    record = items.read(seq)
    assert record["INV_NO"] == "A015"
    assert record["TAPE_ID"] == ""


def test_missing_database_error(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create_database("P", [Field("KEY", "C", 4)])
    definition = SetDefinition(workspace, "S", "", "P")
    definition.links = [Link("P", "MISSING", "", "KEY")]
    with pytest.raises(SetError, match="does not exist"):
        definition.validate()
