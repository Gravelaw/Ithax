"""``lcsim.strict_json``: the one strict reader for the JSON files the product reads from
disk, and the encoder of the files it writes (review of PR #36). A document is read only
when it would be written back exactly: no ``NaN`` or infinity (also ``1e999``, which
Python reads as an infinity) and no text that is not valid Unicode."""

import json
from pathlib import Path

import pytest

from lcsim.strict_json import UnreadableJSON, encode_json, read_json, read_json_file

#: Texts that ``json.loads`` accepts but the product cannot write back or send.
POISONED = [
    '{"a": 1e999}',
    '{"a": -1e999}',
    '{"a": NaN}',
    '{"a": Infinity}',
    '{"a": -Infinity}',
    '{"a": "\\ud800"}',
    '{"\\udfff": 1}',
    '[1, [2, {"b": 1e400}]]',
]


@pytest.mark.parametrize("text", POISONED)
def test_a_document_that_cannot_be_written_back_is_unreadable(text: str) -> None:
    assert json.loads(text) is not None  # the standard reader takes it
    with pytest.raises(UnreadableJSON):
        read_json(text.encode())


@pytest.mark.parametrize("raw", [b"{", b"", b"\xff\xfe", b"[" * 100_000])
def test_bytes_that_are_not_json_in_utf8_are_unreadable(raw: bytes) -> None:
    with pytest.raises(UnreadableJSON):
        read_json(raw)


def test_a_good_document_is_read_as_json_reads_it() -> None:
    raw = '{"a": [1, 2.5, "café", null, true], "b": {}}'.encode()
    assert read_json(raw) == json.loads(raw)
    assert read_json(b'\xef\xbb\xbf{"bom": 1}') == {"bom": 1}
    assert isinstance(UnreadableJSON("x"), ValueError)


def test_read_json_file_reads_or_raises(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    path.write_text('{"a": 1}')
    assert read_json_file(path) == {"a": 1}
    path.write_text('{"a": 1e999}')
    with pytest.raises(UnreadableJSON):
        read_json_file(path)
    with pytest.raises(OSError):
        read_json_file(tmp_path / "missing.json")


def test_encode_json_round_trips_what_read_json_reads() -> None:
    value = {"a": [1, 2.5, "café"]}
    assert read_json(encode_json(value)) == value
