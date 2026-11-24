import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from adbx.cell.buffer import audit_clipping  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "allow_clipping: il test produce di proposito scritture fuori griglia")


def pytest_collection_modifyitems(config, items):
    """O13: la suite di conformità non ammette test saltati."""
    skipped = [item.nodeid for item in items
               if item.get_closest_marker("skip")
               or item.get_closest_marker("skipif")]
    if skipped:
        raise pytest.UsageError(
            "Skipped tests are not allowed in the 1.0 conformance suite: "
            + ", ".join(skipped))


@pytest.fixture(autouse=True)
def no_silent_clipping(request):
    """Rete di sicurezza: nessuna vista scrive fuori dalla griglia 80x25.

    Il video originale taglia in silenzio, quindi un layout che sborda non
    fallisce mai: qui ogni test viene eseguito con l'audit attivo e le
    scritture fuori bordo fanno fallire il test, con l'indicazione del punto
    di codice. I test che verificano il clipping di proposito usano il marker
    `allow_clipping`.
    """
    if request.node.get_closest_marker("allow_clipping") is not None:
        yield
        return
    with audit_clipping() as events:
        yield
    if events:
        detail = "\n".join(
            f"  {event.kind} riga {event.row} colonna {event.col}: "
            f"{event.detail!r} <- {event.where}"
            for event in events[:12])
        raise AssertionError(
            f"{len(events)} scritture fuori dalla griglia:\n{detail}")
