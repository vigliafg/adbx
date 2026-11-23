"""Benchmark riproducibile di adbx (O13).

Uso: python tools/benchmark.py [--records 5000]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from adbx.data import indexing  # noqa: E402
from adbx.data.fields import Field  # noqa: E402
from adbx.data.report_engine import render_report  # noqa: E402
from adbx.data.reports import ReportDefinition, ReportField  # noqa: E402
from adbx.data.utilities import (  # noqa: E402
    UpdateExpression,
    update_fields,
)
from adbx.data.workspace import Workspace  # noqa: E402


def measure(label, function):
    started = time.perf_counter()
    value = function()
    elapsed = time.perf_counter() - started
    print(f"{label:<28} {elapsed:7.3f} s")
    return value, elapsed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, default=5000)
    args = parser.parse_args(argv)
    count = max(1, args.records)
    with tempfile.TemporaryDirectory(prefix="adbx-bench-") as temporary:
        workspace = Workspace(temporary)
        database = workspace.create_database("BENCH", [
            Field("ID", "C", 8), Field("NAME", "C", 30),
            Field("AMOUNT", "N", 10, 2)])

        def append_all():
            for index in range(count):
                database.append({"ID": f"{index:08d}",
                                 "NAME": f"Person {index}",
                                 "AMOUNT": f"{index % 1000}.50"})
            workspace.save_database(database)

        measure(f"append {count}", append_all)
        measure("index",
                lambda: indexing.save_index(
                    database, indexing.IndexDefinition("BENCHID", "ID")))
        database.set_primary_index("BENCHID")
        measure("ordered scan",
                lambda: indexing.ordered_sequences(
                    database, database.current_range))

        def search():
            definition = indexing.SavedSearch(
                "A", "Prefix", search_expression="ID < '00000100'",
                sort_expression="ID")
            indexing.save_saved_search(database, definition)
            return indexing.run_saved_search(database, "A")

        measure("search 100", search)
        database.set_primary_index("BENCHID")
        report = ReportDefinition(workspace, "BENCH", "A", "Bench", 80)
        report.sections = ["detail"]
        report.fields = [ReportField("detail", 1, 1, "BENCH.ID", length=8),
                         ReportField("detail", 1, 10, "BENCH.NAME",
                                     length=20)]
        measure("report", lambda: render_report(report, workspace))
        measure("update",
                lambda: update_fields(
                    database,
                    [UpdateExpression("AMOUNT", "AMOUNT * 1.10")]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
