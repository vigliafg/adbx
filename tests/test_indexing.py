"""Indici, range e search/sort list (O3)."""

import pytest

from adbx.data import indexing
from adbx.data.expressions import SearchRow
from adbx.data.fields import Field
from adbx.data.workspace import Workspace


def make_movies(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVMOVIES", [
        Field("TAPE_ID", "C", 4), Field("TITLE", "C", 30),
        Field("SUBJECT", "C", 20), Field("RUNTIME", "N", 3, 0),
        Field("RATING", "C", 5), Field("AVAILABLE", "L", 1),
    ])
    rows = [
        ("1006", "Dumbo", "Children", "64", "NR", "1"),
        ("1007", "For Your Eyes Only", "Action", "127", "PG", "1"),
        ("1001", "Big Easy, The", "Action", "104", "R", "1"),
        ("1013", "Gone With The Wind", "Drama", "222", "G", "1"),
        ("1015", "Benji", "Children", "85", "G", "0"),
    ]
    for tape_id, title, subject, runtime, rating, available in rows:
        database.append({"TAPE_ID": tape_id, "TITLE": title,
                         "SUBJECT": subject, "RUNTIME": runtime,
                         "RATING": rating, "AVAILABLE": available})
    return workspace, database


def test_single_and_multi_level_index_order(tmp_path):
    _workspace, database = make_movies(tmp_path)
    title = indexing.IndexDefinition("AVMOVTLE", "TITLE",
                                     "Alphabetically by Title")
    indexing.save_index(database, title)
    ordered = indexing.ordered_sequences(
        database, indexing.RangeSettings(primary="AVMOVTLE"))
    titles = [database.read(seq)["TITLE"] for seq in ordered]
    assert titles == sorted(titles, key=str.upper)

    multi = indexing.IndexDefinition(
        "AVMSUBTI", "SUBJECT+TITLE", "Ordered by Subject, Title",
        levels=[("SUBJECT", "A"), ("TITLE", "A")])
    indexing.save_index(database, multi)
    ordered = indexing.ordered_sequences(
        database, indexing.RangeSettings(primary="AVMSUBTI"))
    pairs = [(database.read(seq)["SUBJECT"], database.read(seq)["TITLE"])
             for seq in ordered]
    assert pairs == sorted(pairs, key=lambda pair: (pair[0].upper(),
                                                    pair[1].upper()))

    descending = indexing.ordered_sequences(
        database, indexing.RangeSettings(primary="AVMOVTLE",
                                         order=indexing.ORDER_DESCENDING))
    assert descending == list(reversed(indexing.ordered_sequences(
        database, indexing.RangeSettings(primary="AVMOVTLE"))))


def test_index_filter_and_key_values(tmp_path):
    _workspace, database = make_movies(tmp_path)
    rated = indexing.IndexDefinition("AVRATING", "RATING", "Ordered by Rating",
                                     filter='RATING = "G"')
    indexing.save_index(database, rated)
    ordered = indexing.ordered_sequences(
        database, indexing.RangeSettings(primary="AVRATING"))
    assert len(ordered) == 2
    assert {database.read(seq)["RATING"] for seq in ordered} == {"G"}
    assert [key.strip() for key in indexing.key_values(database, rated)] == ["G"]


def test_range_show_deleted_unique_and_bounds(tmp_path):
    _workspace, database = make_movies(tmp_path)
    database.delete(5)
    subject = indexing.IndexDefinition("AVSUBJ", "SUBJECT")
    indexing.save_index(database, subject)

    visible = indexing.ordered_sequences(
        database, indexing.RangeSettings(primary="AVSUBJ"))
    assert 5 not in visible
    deleted = indexing.ordered_sequences(
        database, indexing.RangeSettings(primary="AVSUBJ",
                                         show=indexing.SHOW_DELETED))
    assert deleted == [5]
    all_records = indexing.ordered_sequences(
        database, indexing.RangeSettings(primary="AVSUBJ",
                                         show=indexing.SHOW_ALL))
    assert 5 in all_records

    unique = indexing.ordered_sequences(
        database, indexing.RangeSettings(primary="AVSUBJ", unique_keys=True))
    subjects = [database.read(seq)["SUBJECT"] for seq in unique]
    assert len(subjects) == len(set(subjects))

    bounded = indexing.ordered_sequences(
        database, indexing.RangeSettings(primary="AVSUBJ",
                                         first_key="Action",
                                         last_key="Action"))
    assert {database.read(seq)["SUBJECT"] for seq in bounded} == {"Action"}


def test_range_filter_is_active_only_when_enabled(tmp_path):
    _workspace, database = make_movies(tmp_path)
    settings = indexing.RangeSettings(filter='RUNTIME > 100')
    assert len(indexing.ordered_sequences(database, settings)) == 5
    settings.filter_active = True
    ordered = indexing.ordered_sequences(database, settings)
    assert all(int(database.read(seq)["RUNTIME"]) > 100 for seq in ordered)
    assert len(ordered) == 3


def test_saved_range_roundtrip(tmp_path):
    workspace, database = make_movies(tmp_path)
    settings = indexing.RangeSettings(primary="AVMOVTLE",
                                      order=indexing.ORDER_DESCENDING)
    indexing.save_range(database, "A", "Movies backwards", settings)
    saved = indexing.saved_ranges(database)
    assert len(saved) == 1
    letter, description, restored = saved[0]
    assert letter == "A" and description == "Movies backwards"
    assert restored.order == indexing.ORDER_DESCENDING
    database.save_current_range(settings)
    assert database.current_range.order == indexing.ORDER_DESCENDING
    assert indexing.get_range(database, "A")[1].primary == "AVMOVTLE"


def test_search_rows_sort_and_out_of_date(tmp_path):
    _workspace, database = make_movies(tmp_path)
    result = indexing.run_search(
        database,
        search_rows=[SearchRow("RATING", "=", "G")],
        sort_rows=[("TITLE", "A")],
        description="Rated G by title")
    assert len(result.seqs) == 2
    assert [database.read(seq)["TITLE"] for seq in result.seqs] == [
        "Benji", "Gone With The Wind"]
    assert database.primary_index == f"{indexing.SEARCH_PREFIX}{result.id}"
    assert not result.out_of_date(database)
    assert "Search/Sort" in indexing.primary_label(database)
    assert "\u2666" not in indexing.primary_label(database)

    assert len(indexing.get_search_list(database, result.id).seqs) == 2
    database.update(5, {**database.read(5), "RATING": "PG"})
    refreshed = indexing.get_search_list(database, result.id)
    assert refreshed.out_of_date(database)
    assert "\u2666" in indexing.primary_label(database)

    rebuilt = indexing.refresh_search_list(database, result.id)
    assert [database.read(seq)["TITLE"] for seq in rebuilt.seqs] == [
        "Gone With The Wind"]
    assert not rebuilt.out_of_date(database)


def test_search_history_and_refining_active_list(tmp_path):
    _workspace, database = make_movies(tmp_path)
    first = indexing.run_search(
        database, search_rows=[SearchRow("SUBJECT", "=", "Children")],
        description="Children")
    assert len(first.seqs) == 2

    # La ricerca successiva parte dalla lista attiva.
    second = indexing.run_search(
        database, search_rows=[SearchRow("RATING", "=", "G")],
        description="Children rated G",
        range_settings=indexing.RangeSettings(
            primary=f"{indexing.SEARCH_PREFIX}{first.id}"))
    assert [database.read(seq)["TITLE"] for seq in second.seqs] == ["Benji"]

    history = indexing.search_history(database)
    ids = [item.id for item in history]
    assert ids[0] == second.id and first.id in ids
    assert len(history) == 2


def test_saved_search_criteria_and_version(tmp_path):
    _workspace, database = make_movies(tmp_path)
    saved = indexing.SavedSearch(
        "A", "G movies", mode="table",
        search_rows=[SearchRow("RATING", "=", "G")])
    indexing.save_saved_search(database, saved)
    result = indexing.run_saved_search(database, "A")
    assert len(result.seqs) == 2
    assert result.letter == "A"
    assert not result.out_of_date(database)
    assert indexing.saved_search(database, "A").description == "G movies"

    saved.description = "Only G"
    indexing.save_saved_search(database, saved)
    assert indexing.get_search_list(database, result.id).out_of_date(database)


def test_attached_limit_and_delete_index(tmp_path):
    _workspace, database = make_movies(tmp_path)
    for index in range(indexing.MAX_INDEXES_ATTACHED):
        definition = indexing.IndexDefinition(f"I{index}", "TAPE_ID")
        indexing.save_index(database, definition)
    with pytest.raises(indexing.IndexError_):
        indexing.save_index(database, indexing.IndexDefinition("OVER", "TITLE"))
    indexing.set_index_attached(database, "I0", False)
    indexing.save_index(database, indexing.IndexDefinition("OVER", "TITLE"))
    assert indexing.find_index(database, "OVER") is not None
    database.set_primary_index("OVER")
    assert indexing.delete_index(database, "OVER")
    assert database.primary_index == indexing.RECORD_NUMBER


def test_record_revision_moves_with_writes(tmp_path):
    _workspace, database = make_movies(tmp_path)
    before = database.revision()
    database.append({"TAPE_ID": "2000"})
    assert database.revision() == before + 1
    database.update(1, {**database.read(1), "TITLE": "Dumbo 2"})
    assert database.revision() == before + 2
    database.set_deleted(1, True)
    assert database.revision() == before + 3


def test_unique_index_blocks_or_warns(tmp_path):
    from adbx.screen.keys import Key
    from adbx.shell.records import RecordSession

    workspace = Workspace(tmp_path)
    database = workspace.create_database("DEMO", [Field("TITLE", "C", 20)])
    database.append({"TITLE": "Dumbo"})
    indexing.save_index(database, indexing.IndexDefinition(
        "DEMOTIT", "TITLE", allow=indexing.ALLOW_UNIQUE))

    session = RecordSession(database, "enter")
    for char in "Dumbo":
        session.handle(Key(char, shift=char.isupper()))
    assert not session.save()
    assert "Duplicate key" in session.status
    assert database.count() == 1

    indexing.save_index(database, indexing.IndexDefinition(
        "DEMOTIT", "TITLE", allow=indexing.ALLOW_EXCEPTIONS), replace=True)
    session = RecordSession(database, "enter")
    for char in "Dumbo":
        session.handle(Key(char, shift=char.isupper()))
    assert session.save()
    assert "Duplicate key allowed" in session.status
    assert database.count() == 2


def test_case_sensitive_unique_keys(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("DEMO", [Field("NAME", "C", 20)])
    database.append({"NAME": "smith"})
    indexing.save_index(database, indexing.IndexDefinition(
        "DEMONAME", "NAME", allow=indexing.ALLOW_UNIQUE,
        case_sensitive=True))
    from adbx.screen.keys import Key
    from adbx.shell.records import RecordSession

    session = RecordSession(database, "enter")
    for char in "SMITH":
        session.handle(Key(char, shift=True))
    assert session.save()
    assert database.count() == 2
