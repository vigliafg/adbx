from pathlib import Path

from support import make_tutorial_set, write_dbf

from adbx.shell.files import PARENT_LABEL, scan, strip_wildcard


def test_scan_lists_parent_directories_and_files(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    (data / "SUB").mkdir()
    (data / "NOTES.TXT").write_text("ignore me", encoding="ascii")
    listing = scan(data)
    kinds = [entry.kind for entry in listing.entries]
    assert kinds[0] == "parent"
    assert "dir" in kinds
    files = [entry.name for entry in listing.entries if entry.kind == "file"]
    assert files == ["ALPHAVID", "AVMOVIES", "AVPATRON", "AVSALES", "AVSALES2"]


def test_parent_entry_points_up(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    listing = scan(data)
    parent = listing.entries[0]
    assert parent.name == PARENT_LABEL
    assert parent.path == data.parent
    assert parent.selectable_text.endswith("*")


def test_records_and_fields_from_dbf_header(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    listing = scan(data)
    movies = next(entry for entry in listing.entries if entry.name == "AVMOVIES")
    assert movies.ext == "DBF"
    assert movies.records == 50
    assert movies.fields == 11
    assert movies.date == "06/01/1993"


def test_pattern_filters_files(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    listing = scan(data, "AVS*")
    names = [entry.name for entry in listing.entries if entry.is_file]
    assert names == ["AVSALES", "AVSALES2"]


def test_extension_filter(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    listing = scan(data, "*.SET")
    names = [entry.name for entry in listing.entries if entry.is_file]
    assert names == ["ALPHAVID"]


def test_unreadable_dbf_still_listed(tmp_path):
    data = tmp_path / "DATA"
    data.mkdir()
    (data / "BROKEN.DBF").write_bytes(b"broken")
    listing = scan(data)
    broken = next(entry for entry in listing.entries if entry.name == "BROKEN")
    assert broken.records is None
    write_dbf(tmp_path / "OTHER.DBF")


def test_strip_wildcard():
    assert strip_wildcard("/tmp/data/*.DBF") == ("/tmp/data", "*.DBF")
    assert strip_wildcard("*") == ("", "*")
    assert strip_wildcard("/tmp/data") == ("/tmp/data", None)


def test_path_text_uses_wildcard(tmp_path):
    listing = scan(tmp_path, "AV*")
    assert listing.path_text == str(tmp_path / "AV*")


def test_index_of(tmp_path):
    data = make_tutorial_set(tmp_path / "TUTOR")
    listing = scan(data)
    index = listing.index_of(data / "AVSALES.DBF")
    assert listing.entries[index].name == "AVSALES"
    assert listing.index_of(Path("/nonexistent")) == -1
