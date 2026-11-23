"""O6 — modello dei form, pagine, calcolati, summary e regioni."""

import pytest

from adbx.data import indexing
from adbx.data.fields import Field
from adbx.data.forms import (
    FormBox,
    FormDefinition,
    FormError,
    FormField,
    FormLabel,
    FormRegion,
)
from adbx.data.sets import Link, SetDefinition
from adbx.data.workspace import Workspace


def make_database(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVMOVIES", [
        Field("TAPE_ID", "C", 4), Field("TAPE_TITLE", "C", 30),
        Field("TAPE_DESC", "M", 10), Field("RUNTIME", "N", 3, 0),
    ])
    database.append({"TAPE_ID": "1006", "TAPE_TITLE": "Dumbo",
                     "TAPE_DESC": "A Disney cartoon favorite.",
                     "RUNTIME": "64"})
    return workspace, database


def test_form_save_active_and_delete(tmp_path):
    workspace, database = make_database(tmp_path)
    form = FormDefinition(workspace, "AVMOVIES", "A", "Movie form")
    form.fields = [FormField("AVMOVIES", "TAPE_TITLE", 0, 2, 2, 30, 30,
                             "Title", True)]
    form.labels = [FormLabel(0, 1, 2, "Movie card")]
    form.boxes = [FormBox(0, 1, 1, 4, 40)]
    form.save()
    restored = workspace.get_form("AVMOVIES", "A")
    assert restored is not None
    assert restored.description == "Movie form"
    assert restored.label == "A - Movie form"
    assert restored.fields[0].field == "TAPE_TITLE"
    assert workspace.active_form("AVMOVIES").letter == "A"
    assert len(workspace.forms("AVMOVIES")) == 1
    assert workspace.set_active_form("AVMOVIES", "A")
    assert workspace.delete_form("AVMOVIES", "A")
    assert workspace.active_form("AVMOVIES") is None


def test_form_pages_and_validation(tmp_path):
    workspace, _database = make_database(tmp_path)
    form = FormDefinition(workspace, "AVMOVIES", "B")
    form.fields = [FormField("AVMOVIES", "TAPE_ID", 2, 1, 1, 4, 4)]
    form.save()
    restored = workspace.get_form("AVMOVIES", "B")
    assert restored.pages == 3
    assert len(restored.page_fields(2)) == 1

    broken = FormDefinition(workspace, "AVMOVIES", "C")
    broken.fields = [FormField("AVMOVIES", "MISSING", 0, 1, 1, 10, 10)]
    with pytest.raises(FormError, match="not found"):
        broken.save()

    outside = FormDefinition(workspace, "AVMOVIES", "D")
    outside.fields = [FormField("OTHER", "TAPE_ID", 0, 1, 1, 4, 4)]
    with pytest.raises(FormError, match="outside"):
        outside.save()


def test_form_calculated_and_summary_values(tmp_path):
    workspace, database = make_database(tmp_path)
    form = FormDefinition(workspace, "AVMOVIES", "A")
    calculated = FormField("AVMOVIES", "CALC", 0, 1, 1, 10, 10,
                           kind="calculated", expression="RUNTIME*2")
    assert form.value_for(calculated, {"RUNTIME": "64"},
                          database) == "128"
    summary = FormField("AVMOVIES", "SUM", kind="summary",
                        summary="Total", summary_field="RUNTIME")
    assert form.summary_value(summary, [{"RUNTIME": "64"},
                                       {"RUNTIME": "36"}]) == "100"
    assert form.summary_value(FormField(summary="Count"),
                              [{}, {}]) == "2"


def test_set_form_with_region_and_summary(tmp_path):
    workspace = Workspace(tmp_path)
    header = workspace.create_database("AVHEADER", [
        Field("INV_NO", "C", 6), Field("CUST_ID", "C", 6)])
    items = workspace.create_database("AVITEMS", [
        Field("INV_NO", "C", 6), Field("QTY", "N", 4, 0)])
    indexing.save_index(items, indexing.IndexDefinition("AVINVNO", "INV_NO"))
    header.append({"INV_NO": "A015", "CUST_ID": "1001"})
    items.append({"INV_NO": "A015", "QTY": "2"})
    items.append({"INV_NO": "A015", "QTY": "3"})
    definition = SetDefinition(workspace, "AVIDEO", "", "AVHEADER")
    definition.links = [Link("AVHEADER", "AVITEMS", "AVINVNO", "INV_NO",
                             "All")]
    definition.save()
    form = FormDefinition(workspace, "AVIDEO", "A", "Invoice set")
    form.fields = [
        FormField("AVHEADER", "INV_NO", 0, 1, 1, 6, 6),
        FormField("CALC", "TOTAL", 0, 2, 1, 10, 10, kind="summary",
                  summary="Total", summary_field="QTY",
                  summary_database="AVITEMS"),
    ]
    form.regions = [FormRegion("AVITEMS", 0, 5, 1, 8, 60, "Line items")]
    form.printable = False
    form.save()
    restored = workspace.get_form("AVIDEO", "A")
    assert not restored.printable
    assert restored.page_regions(0)[0].database == "AVITEMS"
    assert set(restored.owner_databases()) == {"AVHEADER", "AVITEMS"}
