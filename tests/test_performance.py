"""O13 — prestazioni minime, con soglie larghe per la CI."""

from __future__ import annotations

import time

from adbx.data import indexing
from adbx.data.fields import Field
from adbx.data.report_engine import render_report
from adbx.data.reports import ReportDefinition, ReportField
from adbx.data.workspace import Workspace


def timed(callable_):
    started = time.perf_counter()
    result = callable_()
    return result, time.perf_counter() - started


def make_large(tmp_path, count=3000):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("BENCH", [
        Field("ID", "C", 8), Field("NAME", "C", 30),
        Field("AMOUNT", "N", 10, 2)])
    for index in range(count):
        database.append({"ID": f"{index:08d}", "NAME": f"Person {index}",
                         "AMOUNT": f"{index % 1000}.50"})
    workspace.save_database(database)
    return workspace, database


def test_append_and_read_3000_records(tmp_path):
    def work():
        workspace = Workspace(tmp_path)
        database = workspace.create_database("BENCH", [
            Field("ID", "C", 8), Field("NAME", "C", 30),
            Field("AMOUNT", "N", 10, 2)])
        for index in range(3000):
            database.append({"ID": f"{index:08d}",
                             "NAME": f"Person {index}",
                             "AMOUNT": f"{index % 1000}.50"})
        return database.count()

    count, elapsed = timed(work)
    assert count == 3000
    assert elapsed < 20.0, elapsed


def test_index_and_order_3000_records(tmp_path):
    _workspace, database = make_large(tmp_path)

    def build():
        indexing.save_index(database, indexing.IndexDefinition("BENCHID", "ID"))
        database.set_primary_index("BENCHID")
        return indexing.ordered_sequences(database, database.current_range)

    seqs, elapsed = timed(build)
    assert len(seqs) == 3000
    assert elapsed < 10.0, elapsed
    assert database.read(seqs[0])["ID"] == "00000000"


def test_search_and_report_3000_records(tmp_path):
    _workspace, database = make_large(tmp_path)
    indexing.save_index(database, indexing.IndexDefinition("BENCHID", "ID"))

    def search():
        search = indexing.SavedSearch(
            "A", "First fifty", search_expression="ID < '00000050'",
            sort_expression="ID")
        indexing.save_saved_search(database, search)
        return indexing.run_saved_search(database, "A")

    result, elapsed = timed(search)
    assert len(result.seqs) == 50
    assert elapsed < 10.0, elapsed

    database.set_primary_index("BENCHID")
    report = ReportDefinition(database.workspace, "BENCH", "A", "Bench", 80)
    report.sections = ["detail"]
    report.fields = [ReportField("detail", 1, 1, "BENCH.ID", length=8),
                     ReportField("detail", 1, 10, "BENCH.NAME", length=20)]
    output, elapsed = timed(lambda: render_report(report, database.workspace))
    assert output.rows == 3000
    assert elapsed < 20.0, elapsed


def test_update_1000_records(tmp_path):
    _workspace, database = make_large(tmp_path, count=1000)
    from adbx.data.utilities import UpdateExpression, update_fields

    result, elapsed = timed(lambda: update_fields(
        database, [UpdateExpression("AMOUNT", "AMOUNT * 2")]))
    assert result.updated == 1000
    assert elapsed < 10.0, elapsed
