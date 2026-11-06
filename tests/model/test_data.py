"""The data index of a project's ``data/`` folder (AKS-90).

Spec 1 "Distributions", ``empirical`` with ``data``: values are read per the column
index's declared unit, and a missing or changed file is E162 (the SHA-256 recorded at
import against the file now). Spec 3 "Project folder": ``data/`` holds the imported files
plus a column index. The meaning pass's use of the index is tested in
``test_validation_b.py``.
"""

import hashlib
from pathlib import Path

import pytest

from lcsim.model.data import EMPTY_DATA_INDEX, DataColumn, DataFile, DataIndex, file_sha256

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
