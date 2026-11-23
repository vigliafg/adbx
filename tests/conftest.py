import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_collection_modifyitems(config, items):
    """O13: la suite di conformità non ammette test saltati."""
    skipped = [item.nodeid for item in items
               if item.get_closest_marker("skip")
               or item.get_closest_marker("skipif")]
    if skipped:
        import pytest
        raise pytest.UsageError(
            "Skipped tests are not allowed in the 1.0 conformance suite: "
            + ", ".join(skipped))
