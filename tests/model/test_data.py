"""The data index of a project's ``data/`` folder (AKS-90).

Spec 1 "Distributions", ``empirical`` with ``data``: values are read per the column
index's declared unit, and a missing or changed file is E162 (the SHA-256 recorded at
import against the file now). Spec 3 "Project folder": ``data/`` holds the imported files
plus a column index. The meaning pass's use of the index is tested in
``test_validation_b.py``.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import pytest

from lcsim.model.data import (
    EMPTY_DATA_INDEX,
    INDEX_FILE,
    DataColumn,
    DataFile,
    DataIndex,
    file_sha256,
    index_bytes,
    read_data_index,
)

CONTENT = b"minutes\n1.5\n2.0\n"
DIGEST = hashlib.sha256(CONTENT).hexdigest()


def entry(name: str = "times.csv", sha256: str = DIGEST) -> DataFile:
    return DataFile(name, (DataColumn("minutes", "min"), DataColumn("count")), sha256)


def test_file_sha256_is_the_lower_case_hex_digest(tmp_path: Path) -> None:
    path = tmp_path / "times.csv"
    path.write_bytes(CONTENT)
    assert file_sha256(path) == DIGEST


def test_file_sha256_reads_a_file_larger_than_one_chunk(tmp_path: Path) -> None:
    content = bytes(range(256)) * 9000  # about 2.3 MB, more than one 1 MiB read
    path = tmp_path / "big.bin"
    path.write_bytes(content)
    assert file_sha256(path) == hashlib.sha256(content).hexdigest()


def test_file_sha256_of_a_missing_file_raises_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        file_sha256(tmp_path / "missing.csv")


def test_a_column_has_a_name_and_a_declared_unit() -> None:
    assert DataColumn("minutes", "min").unit == "min"
    # No unit: plain numbers.
    assert DataColumn("count").unit is None


def test_a_file_finds_its_columns_by_name() -> None:
    data_file = entry()
    assert data_file.column("minutes") == DataColumn("minutes", "min")
    assert data_file.column("count") == DataColumn("count")
    assert data_file.column("Minutes") is None


@pytest.mark.parametrize("name", ["", ".", "..", "a/b.csv", "../b.csv", "a\\b.csv", "a\x00b"])
def test_a_file_name_must_be_a_name_in_the_folder(name: str) -> None:
    with pytest.raises(ValueError, match="not the name of a file in data/"):
        entry(name)


@pytest.mark.parametrize("sha256", ["", DIGEST.upper(), DIGEST[:-1], DIGEST + "0", "g" * 64])
def test_a_file_hash_must_be_64_lower_case_hex_digits(sha256: str) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        entry(sha256=sha256)


def test_the_empty_index_has_no_files() -> None:
    assert EMPTY_DATA_INDEX.folder is None
    assert dict(EMPTY_DATA_INDEX.files) == {}
    assert EMPTY_DATA_INDEX.file("times.csv") is None
    assert EMPTY_DATA_INDEX.current_sha256("times.csv") is None


def test_an_index_finds_its_files_by_name(tmp_path: Path) -> None:
    index = DataIndex(tmp_path, {"times.csv": entry()})
    assert index.file("times.csv") == entry()
    assert index.file("other.csv") is None


def test_an_index_with_files_needs_its_folder() -> None:
    with pytest.raises(ValueError, match="needs the data/ folder"):
        DataIndex(None, {"times.csv": entry()})


def test_an_index_entry_must_be_filed_under_its_own_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"is for 'times\.csv'"):
        DataIndex(tmp_path, {"other.csv": entry()})


def test_an_index_is_read_only_and_keeps_no_link_to_the_mapping_given(tmp_path: Path) -> None:
    files = {"times.csv": entry()}
    index = DataIndex(tmp_path, files)
    files.clear()
    assert index.file("times.csv") == entry()
    with pytest.raises(TypeError):
        index.files["x.csv"] = entry("x.csv")  # type: ignore[index]


def test_current_sha256_hashes_the_file_as_it_is_now(tmp_path: Path) -> None:
    path = tmp_path / "times.csv"
    path.write_bytes(CONTENT)
    index = DataIndex(tmp_path, {"times.csv": entry()})
    assert index.current_sha256("times.csv") == DIGEST
    path.write_bytes(CONTENT + b"3.0\n")
    assert index.current_sha256("times.csv") == hashlib.sha256(CONTENT + b"3.0\n").hexdigest()


def test_current_sha256_of_a_missing_or_unreadable_file_is_none(tmp_path: Path) -> None:
    index = DataIndex(tmp_path, {"times.csv": entry(), "folder.csv": entry("folder.csv")})
    assert index.current_sha256("times.csv") is None  # not in the folder
    (tmp_path / "folder.csv").mkdir()
    assert index.current_sha256("folder.csv") is None  # a folder, not a file


def test_current_sha256_of_a_file_not_in_the_index_is_none(tmp_path: Path) -> None:
    # A file in the folder that was never imported is not hashed: only the index counts.
    (tmp_path / "loose.csv").write_bytes(CONTENT)
    index = DataIndex(tmp_path, {"times.csv": entry()})
    assert index.current_sha256("loose.csv") is None


# --- the column index file, data/index.json (spec 3 "Project folder"; AKS-113) ------------------


def imported(name: str = "times.csv", sha256: str = DIGEST) -> DataFile:
    return DataFile(
        name,
        (
            DataColumn("minutes", "min"),
            DataColumn("note", None, "text"),
            DataColumn("e", None, "empty"),
        ),
        sha256,
        format="csv",
        sheet=None,
        size=len(CONTENT),
        rows=2,
        imported="2026-11-07T10:00:00.000Z",
    )


def test_a_file_entry_as_the_api_lists_it() -> None:
    assert imported().as_dict() == {
        "name": "times.csv",
        "format": "csv",
        "sheet": None,
        "size": len(CONTENT),
        "sha256": DIGEST,
        "imported": "2026-11-07T10:00:00.000Z",
        "rows": 2,
        "columns": [
            {"name": "minutes", "type": "number", "unit": "min"},
            {"name": "note", "type": "text", "unit": None},
            {"name": "e", "type": "empty", "unit": None},
        ],
    }


def test_the_index_is_written_and_read_back_in_order(tmp_path: Path) -> None:
    files = [imported("b.csv"), imported("a.xlsx")]
    (tmp_path / INDEX_FILE).write_bytes(index_bytes(files))
    document = json.loads((tmp_path / INDEX_FILE).read_text(encoding="utf-8"))
    assert document["index_version"] == 1
    assert [entry["name"] for entry in document["files"]] == ["b.csv", "a.xlsx"]
    index = read_data_index(tmp_path)
    assert index.folder == tmp_path
    assert list(index.files) == ["b.csv", "a.xlsx"]
    assert index.entries() == tuple(files)


def test_a_missing_index_is_an_empty_index_of_the_folder(tmp_path: Path) -> None:
    index = read_data_index(tmp_path)
    assert index.folder == tmp_path and dict(index.files) == {}


def good_document() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(index_bytes([imported()]))
    return document


def spoil(document: dict[str, Any], change: str) -> object:
    entry = document["files"][0]
    column = entry["columns"][0]
    changes: dict[str, Any] = {
        "version": lambda: document.update(index_version=2),
        "files not a list": lambda: document.update(files={}),
        "entry not an object": lambda: document.update(files=[1]),
        "unknown key": lambda: entry.update(extra=1),
        "missing key": lambda: entry.pop("rows"),
        "bad name": lambda: entry.update(name="../x.csv"),
        "reserved name": lambda: entry.update(name="con.csv"),
        "bad format": lambda: entry.update(format="ods"),
        "bad sheet": lambda: entry.update(sheet=3),
        "csv with a sheet": lambda: entry.update(sheet="A"),
        "size is a bool": lambda: entry.update(size=True),
        "size negative": lambda: entry.update(size=-1),
        "size too large": lambda: entry.update(size=2**63),
        "rows a float": lambda: entry.update(rows=2.0),
        "bad sha": lambda: entry.update(sha256="X" * 64),
        "imported not text": lambda: entry.update(imported=None),
        "columns not a list": lambda: entry.update(columns={}),
        "column not an object": lambda: entry.update(columns=["minutes"]),
        "column name not text": lambda: column.update(name=1),
        "column name empty": lambda: column.update(name=""),
        "two columns one name": lambda: entry["columns"].append(dict(column)),
        "bad type": lambda: column.update(type="date"),
        "bad unit": lambda: column.update(unit="ms"),
        "unit on text": lambda: entry["columns"][1].update(unit="min"),
        "column extra key": lambda: column.update(x=1),
        "two entries one name": lambda: document["files"].append(dict(entry)),
        "two names one file on windows": lambda: document["files"].append(
            {**entry, "name": "TIMES.csv"}
        ),
    }
    if change == "not an object":
        return [document]
    changes[change]()
    return document


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "not an object",
        "files not a list",
        "entry not an object",
        "unknown key",
        "missing key",
        "bad name",
        "reserved name",
        "bad format",
        "bad sheet",
        "csv with a sheet",
        "size is a bool",
        "size negative",
        "size too large",
        "rows a float",
        "bad sha",
        "imported not text",
        "columns not a list",
        "column not an object",
        "column name not text",
        "column name empty",
        "two columns one name",
        "bad type",
        "bad unit",
        "unit on text",
        "column extra key",
        "two entries one name",
        "two names one file on windows",
    ],
)
def test_an_index_that_cannot_be_read_is_taken_as_empty(
    tmp_path: Path, change: str, caplog: pytest.LogCaptureFixture
) -> None:
    document = good_document()
    assert read_data_index_of(tmp_path, document).file("times.csv") == imported()
    spoilt = spoil(good_document(), change)
    with caplog.at_level(logging.WARNING):
        index = read_data_index_of(tmp_path, spoilt)
    assert dict(index.files) == {}
    assert index.folder == tmp_path
    assert "cannot be read" in caplog.text


def read_data_index_of(folder: Path, document: object) -> DataIndex:
    (folder / INDEX_FILE).write_text(json.dumps(document), encoding="utf-8")
    return read_data_index(folder)


@pytest.mark.parametrize(
    "raw", [b"not json", b'{"index_version": 1, "files": [NaN]}', b"\xff\xfe", b'"\\ud800"']
)
def test_an_index_the_strict_reader_refuses_is_taken_as_empty(tmp_path: Path, raw: bytes) -> None:
    (tmp_path / INDEX_FILE).write_bytes(raw)
    assert dict(read_data_index(tmp_path).files) == {}


def test_an_xlsx_entry_names_its_sheet(tmp_path: Path) -> None:
    entry = DataFile(
        "a.xlsx",
        (DataColumn("x"),),
        DIGEST,
        format="xlsx",
        sheet="Arrivals",
        size=1,
        rows=1,
        imported="2026-11-07T10:00:00.000Z",
    )
    (tmp_path / INDEX_FILE).write_bytes(index_bytes([entry]))
    assert read_data_index(tmp_path).entries() == (entry,)


def test_an_index_folder_that_cannot_be_read_is_taken_as_empty(tmp_path: Path) -> None:
    (tmp_path / INDEX_FILE).mkdir()
    assert dict(read_data_index(tmp_path).files) == {}
