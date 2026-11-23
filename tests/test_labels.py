"""O8 — modello, giustificazioni e stampa delle etichette."""

import pytest

from adbx.data.fields import Field
from adbx.data.labels import (
    LabelDefinition,
    LabelError,
    LabelField,
    LabelText,
)
from adbx.data.labels_engine import LabelEngine, LabelRow, render_labels
from adbx.data.workspace import Workspace


def make_patrons(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVPATRON", [
        Field("SALUTATION", "C", 4), Field("FIRSTNAME", "C", 10),
        Field("LASTNAME", "C", 12), Field("ADDRESS", "C", 20),
        Field("ADDRESS2", "C", 20), Field("CITY", "C", 15),
        Field("STATE", "C", 2), Field("ZIP", "C", 5),
        Field("COPIES", "N", 2, 0),
    ])
    database.append({
        "SALUTATION": "Ms.", "FIRSTNAME": "Grace", "LASTNAME": "Jones",
        "ADDRESS": "11 Willow Street", "ADDRESS2": "",
        "CITY": "Rushton", "STATE": "NY", "ZIP": "11211", "COPIES": "1",
    })
    database.append({
        "SALUTATION": "Mr.", "FIRSTNAME": "Joe", "LASTNAME": "Franklin",
        "ADDRESS": "1 Main Street", "ADDRESS2": "Apt 29",
        "CITY": "Boston", "STATE": "MA", "ZIP": "02139", "COPIES": "2",
    })
    return workspace, database


def lesson_label(workspace):
    label = LabelDefinition(workspace, "AVPATRON", "A",
                            "Mail Labels with Message Line", 40, 8, 2, 2, 1)
    label.fields = [
        LabelField(2, 1, "AVPATRON.SALUTATION", length=4,
                   justification="Suppress"),
        LabelField(2, 6, "AVPATRON.FIRSTNAME", length=10,
                   justification="Suppress"),
        LabelField(2, 17, "AVPATRON.LASTNAME", length=12,
                   justification="Suppress"),
        LabelField(3, 1, "AVPATRON.ADDRESS", length=20,
                   justification="Suppress"),
        LabelField(4, 1, "AVPATRON.ADDRESS2", length=20,
                   justification="Suppress", delete_line_if_empty=True),
        LabelField(5, 1, "AVPATRON.CITY", length=15,
                   justification="Suppress"),
        LabelField(5, 18, "AVPATRON.STATE", length=2,
                   justification="Suppress"),
        LabelField(5, 21, "AVPATRON.ZIP", length=5,
                   justification="Suppress"),
    ]
    label.texts = [
        LabelText(1, 1, chr(127)),
        LabelText(5, 16, ","),
        LabelText(6, 1, chr(127)),
        LabelText(7, 1, "FREE Popcorn from Alpha Video!"),
        LabelText(8, 1, chr(127)),
    ]
    return label


def test_label_save_validation_and_delete(tmp_path):
    workspace, _database = make_patrons(tmp_path)
    label = lesson_label(workspace)
    label.save()
    restored = workspace.get_label("AVPATRON", "A")
    assert restored is not None
    assert restored.width == 40
    assert restored.across == 2
    assert len(restored.fields) == 8
    assert workspace.label_names("AVPATRON")[0].startswith("A - Mail Labels")
    assert workspace.delete_label("AVPATRON", "A")
    assert workspace.get_label("AVPATRON", "A") is None

    bad = LabelDefinition(workspace, "AVPATRON", "B", "", 20, 4)
    bad.fields = [LabelField(1, 1, "AVPATRON.ADDRESS", length=30)]
    with pytest.raises(LabelError, match="fit"):
        bad.save()

    workspace.create_database("MEMOS", [Field("NOTE", "M", 10)])
    bad_memo = LabelDefinition(workspace, "MEMOS", "A", "", 20, 4)
    bad_memo.fields = [LabelField(1, 1, "MEMOS.NOTE", length=10)]
    with pytest.raises(LabelError, match="Memo"):
        bad_memo.save()

    outside = LabelDefinition(workspace, "AVPATRON", "C", "", 20, 4)
    outside.fields = [LabelField(1, 1, "OTHER.NAME", length=10)]
    with pytest.raises(LabelError, match="outside"):
        outside.save()


def test_lesson_17_label_output(tmp_path):
    workspace, _database = make_patrons(tmp_path)
    label = lesson_label(workspace)
    label.save()
    output = render_labels(label, workspace)
    lines = output.pages[0].lines
    assert lines[1].startswith("Ms. Grace Jones")
    assert "11 Willow Street" in lines[2]
    assert "Rushton, NY 11211" in lines[3]
    assert lines[5].startswith("FREE Popcorn from Alpha Video!")
    assert "FREE Popcorn from Alpha Video!" in lines[6]
    assert "Apt 29" in lines[3][40:]
    assert lines[0] == ""  # riga non sopprimibile in cima
    assert lines[7] == ""
    assert "Mr. Joe Franklin" in lines[1][40:]


def test_label_copies_from_field(tmp_path):
    workspace, _database = make_patrons(tmp_path)
    label = lesson_label(workspace)
    label.copies = "COPIES"
    label.save()
    output = render_labels(label, workspace)
    text = "\n".join(output.pages[0].lines)
    assert text.count("Ms. Grace Jones") == 1
    assert text.count("Mr. Joe Franklin") == 2


def test_advanced_justifications(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create_database("T", [
        Field("A", "C", 8), Field("B", "C", 8)])
    label = LabelDefinition(workspace, "T", "A", "", 30, 2)
    row = LabelRow(1, {"T": {"A": "Mr", "B": "Smith"}}, "T")

    def run(justification):
        label.fields = [
            LabelField(1, 1, "T.A", length=8, justification="Suppress"),
            LabelField(1, 10, "T.B", length=8,
                       justification=justification),
        ]
        label.texts = [LabelText(1, 9, "."), LabelText(1, 18, "!!!")]
        return LabelEngine(label, workspace).render_label(row)[0]

    suppress = run("Suppress")
    assert "Mr.Smith" in suppress
    assert suppress.index("Smith") == 3
    float_line = run("Float")
    assert float_line.index("Smith") == 3
    assert float_line.index("!!!") == 17
    trim_line = run("Trim")
    assert trim_line.index("Smith") == 9
    assert trim_line.index("!!!") == 14
    join_line = run("Join")
    assert join_line.index("Smith") == 3


def test_before_after_and_delete_line(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create_database("T", [Field("A", "C", 8)])
    label = LabelDefinition(workspace, "T", "A", "", 20, 2)
    empty = LabelRow(1, {"T": {"A": ""}}, "T")
    filled = LabelRow(1, {"T": {"A": "Mr"}}, "T")

    label.fields = [LabelField(1, 5, "T.A", length=4,
                               justification="Before")]
    label.texts = [LabelText(1, 1, "Mr. "), LabelText(1, 10, "X")]
    engine = LabelEngine(label, workspace)
    assert engine.render_label(empty)[0].strip() == "X"
    line = engine.render_label(filled)[0]
    assert "Mr." in line and "X" in line

    label.fields = [LabelField(1, 5, "T.A", length=4,
                               justification="After")]
    label.texts = [LabelText(1, 10, "!!!")]
    engine = LabelEngine(label, workspace)
    assert engine.render_label(empty) == []
    assert "!!!" in engine.render_label(filled)[0]

    label.fields = [LabelField(1, 1, "T.A", length=4,
                               delete_line_if_empty=True)]
    label.texts = [LabelText(1, 6, "tail")]
    engine = LabelEngine(label, workspace)
    assert engine.render_label(empty) == []


def test_label_pages_rows_per_page(tmp_path):
    workspace, _database = make_patrons(tmp_path)
    label = lesson_label(workspace)
    label.continuous_feed = False
    label.across = 1
    label.rows_per_page = 1
    label.save()
    output = render_labels(label, workspace)
    assert len(output.pages) == 2
    assert all(page.number == index + 1
               for index, page in enumerate(output.pages))
