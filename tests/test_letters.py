"""O8 — modello, comandi e stampa delle lettere."""

import datetime

import pytest

from adbx.data.fields import Field
from adbx.data.letters import (
    LetterDefinition,
    LetterError,
    render_letters,
)
from adbx.data.workspace import Workspace


def make_patrons(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVPATRON", [
        Field("SALUTATION", "C", 4), Field("FIRSTNAME", "C", 10),
        Field("LASTNAME", "C", 12), Field("ADDRESS1", "C", 20),
        Field("ADDRESS2", "C", 20), Field("CITY", "C", 12),
        Field("STATE", "C", 2), Field("ZIP", "C", 5), Field("ACTIVE", "L", 1),
    ])
    database.append({
        "SALUTATION": "Ms.", "FIRSTNAME": "Jane", "LASTNAME": "Higgins",
        "ADDRESS1": "100 Main Street", "ADDRESS2": "",
        "CITY": "Burlington", "STATE": "MA", "ZIP": "01803", "ACTIVE": "1",
    })
    database.append({
        "SALUTATION": "Mr.", "FIRSTNAME": "Joe", "LASTNAME": "Smith",
        "ADDRESS1": "1 Main Street", "ADDRESS2": "Apt 2",
        "CITY": "Boston", "STATE": "MA", "ZIP": "02139", "ACTIVE": "0",
    })
    return workspace, database


def popcorn_letter(workspace):
    return LetterDefinition(workspace, "AVPATRON", "POPORNOT", "Popcorn", [
        "[SYSTEM->DATE]",
        "",
        "[SALUTATION] [FIRSTNAME] [LASTNAME]",
        "[ADDRESS1]",
        "[ADDRESS2.D]",
        "[CITY], [STATE]  [ZIP]",
        "",
        "Dear [FIRSTNAME],",
        "",
        "[.WIDTH 40]",
        "[.IF ACTIVE = .T.]",
        "We at Alpha Video appreciate your business, [FIRSTNAME].",
        "Our records tell us that you have rented or bought a movie",
        "from our collection this past month.",
        "",
        "As a small token of thanks, [FIRSTNAME], we have enclosed",
        "a coupon good for a FREE box of popcorn.",
        "[.ELSE]",
        "Hey, [FIRSTNAME], we miss you! Our records tell us that you",
        "have not rented or bought a movie from us in over a month.",
        "[.ENDIF]",
        "",
        "Sincerely,",
        "",
        "The Gang at Alpha Video",
    ])


def test_letter_save_validation_and_delete(tmp_path):
    workspace, _database = make_patrons(tmp_path)
    letter = popcorn_letter(workspace)
    letter.save()
    restored = workspace.get_letter("AVPATRON", "POPORNOT")
    assert restored is not None
    assert restored.name == "POPORNOT"
    assert "Dear [FIRSTNAME]," in restored.text
    assert workspace.letter_names("AVPATRON")[0].startswith("POPORNOT")
    assert workspace.delete_letter("AVPATRON", "POPORNOT")
    assert workspace.get_letter("AVPATRON", "POPORNOT") is None

    with pytest.raises(LetterError, match="names"):
        LetterDefinition(workspace, "AVPATRON", "TOO-LONG-NAME", "", [""])
    missing = LetterDefinition(workspace, "MISSING", "TEST", "", [""])
    with pytest.raises(LetterError, match="Owner"):
        missing.save()


def test_lesson_18_active_and_inactive_letters(tmp_path):
    workspace, _database = make_patrons(tmp_path)
    letter = popcorn_letter(workspace)
    output = render_letters(letter, workspace,
                            today=datetime.date(1991, 11, 15))
    assert len(output.pages) == 2
    active = output.pages[0].text
    inactive = output.pages[1].text
    assert "11/15/1991" in active
    assert "Ms. Jane Higgins" in active
    assert "100 Main Street" in active
    assert "Burlington, MA 01803" in active
    assert "Dear Jane," in active
    assert "We at Alpha Video appreciate your business, Jane." in (
        " ".join(active.split()))
    assert "we miss you" not in active
    assert "Mr. Joe Smith" in inactive
    assert "Apt 2" in inactive
    assert "Boston, MA 02139" in inactive
    assert "Hey, Joe, we miss you!" in inactive
    assert "appreciate your business" not in inactive


def test_letter_elseif_chain_and_prompt(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("T", [
        Field("NAME", "C", 10), Field("STATE", "C", 2)])
    database.append({"NAME": "Ann", "STATE": "MA"})
    database.append({"NAME": "Bob", "STATE": "NY"})
    database.append({"NAME": "Cal", "STATE": "CA"})
    letter = LetterDefinition(workspace, "T", "STATES", "", [
        "Dear [NAME],",
        "[.IF STATE = \"MA\"]",
        "Boston office",
        "[.ELSEIF STATE = \"NY\"]",
        "New York office",
        "[.ELSE]",
        "National headquarters",
        "[.ENDIF]",
        "Title: [?Enter title]",
    ])
    output = render_letters(letter, workspace,
                            prompts={"Enter title": "Dr."})
    assert "Boston office" in output.pages[0].text
    assert "New York office" in output.pages[1].text
    assert "National headquarters" in output.pages[2].text
    assert "Title: Dr." in output.pages[0].text


def test_letter_include_width_fill_and_eject(tmp_path):
    workspace, _database = make_patrons(tmp_path)
    (tmp_path / "BOILER.TXT").write_text(
        "This is an included paragraph that is long enough to wrap around "
        "the configured line width for the letter.", encoding="utf-8")
    letter = LetterDefinition(workspace, "AVPATRON", "TEST", "", [
        "[.WIDTH 30]",
        "Dear [FIRSTNAME],",
        "",
        "[.INCLUDE BOILER.TXT]",
        "[.EJECT]",
        "Second page for [FIRSTNAME].",
    ])
    output = render_letters(letter, workspace)
    active = output.pages[0].text
    assert "Dear Jane," in active
    assert "This is an included" in active
    assert max(len(line) for line in active.splitlines()) <= 30
    assert "Second page for Jane." in output.pages[1].text


def test_letter_commands_and_codes_are_not_printed(tmp_path):
    workspace, _database = make_patrons(tmp_path)
    letter = LetterDefinition(workspace, "AVPATRON", "CMDS", "", [
        "[.LEFT 5]",
        "[.TOP 1]",
        "[.FILL-]",
        "Line one   [FIRSTNAME]",
        "[@27 100]Bold?",
        "[.FILL+]",
        "Wrapped paragraph with [FIRSTNAME] and several words.",
    ])
    output = render_letters(letter, workspace)
    text = output.pages[0].text
    assert "[.LEFT" not in text
    assert "[@27" not in text
    assert "Line one   Jane" in text
    assert "Bold?" in text
    assert text.splitlines()[0] == ""
    assert text.splitlines()[1].startswith("     Line one")


def test_letter_numbers_and_calculated_fields(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("T", [
        Field("PRICE", "N", 8, 2), Field("QTY", "N", 4, 0)])
    database.append({"PRICE": "12.50", "QTY": "3"})
    letter = LetterDefinition(workspace, "T", "CALC", "", [
        "[{PRICE*QTY}.X$]",
        "[{PRICE*QTY}.L:12.2] Dollars",
        "[{SUBSTR(\"Alpha\",1,1)}].",
    ])
    output = render_letters(letter, workspace)
    text = output.pages[0].text
    assert "Thirty seven and 50/100 Dollars" in text
    assert "37.50 Dollars" in text
    assert "A." in text
