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


# --- Typed, bounded fields (review of PR #36, third finding on numbers read from disk) ---

from lcsim.strict_json import MAX_WHOLE, real_in, whole_in  # noqa: E402

HUGE = 10**400
BAD_KINDS: list[object] = [True, False, None, "3", [3], {"a": 3}]


def test_whole_in_takes_only_whole_numbers_in_range() -> None:
    assert whole_in(3, 1, 64) == 3
    assert whole_in(1, 1, 64) == 1
    assert whole_in(64, 1, 64) == 64
    assert whole_in(MAX_WHOLE, 0, MAX_WHOLE) == MAX_WHOLE
    for value in [0, -1, 65, HUGE, -HUGE, 3.0, 2.5, float("inf"), float("nan"), *BAD_KINDS]:
        assert whole_in(value, 1, 64) is None, value


def test_real_in_takes_finite_numbers_in_range_without_raising() -> None:
    assert real_in(1.5, 0.0, 10.0) == 1.5
    assert real_in(2, 0.0, 10.0) == 2.0
    assert isinstance(real_in(2, 0.0, 10.0), float)
    assert real_in(0, 0.0, 1.0) == 0.0
    assert real_in(0, 0.0, 1.0, above_minimum=True) is None
    assert real_in(1.0, 0.0, 1.0) == 1.0
    for value in [HUGE, -HUGE, 10.5, -0.1, float("inf"), float("-inf"), float("nan"), *BAD_KINDS]:
        assert real_in(value, 0.0, 10.0) is None, value
