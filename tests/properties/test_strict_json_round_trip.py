"""Property: ``read_json`` admits exactly what ``encode_json`` can write back, and what it
admits round-trips (P6; #99). NaN, infinity and lone surrogates are refused."""

import json
import math

from hypothesis import given
from hypothesis import strategies as st

from lcsim.strict_json import UnreadableJSON, encode_json, read_json
from properties.strategies import JSON_VALUES


def _writable(value: object) -> bool:
    try:
        encode_json(value)
    except ValueError:
        return False
    return True


@given(JSON_VALUES)
def test_what_read_json_admits_round_trips(value: object) -> None:
    raw = json.dumps(value, ensure_ascii=True).encode("ascii")  # any value, NaN included
    if _writable(value):
        assert encode_json(read_json(raw)) == encode_json(value)
    else:
        try:
            read_json(raw)
        except UnreadableJSON:
            return
        raise AssertionError(f"read_json admitted a value it cannot write back: {raw!r}")


@given(st.sampled_from([math.nan, math.inf, -math.inf, "\ud800"]))
def test_read_json_refuses_what_the_product_never_writes(bad: object) -> None:
    raw = json.dumps({"a": bad}, ensure_ascii=True).encode("ascii")
    try:
        read_json(raw)
    except UnreadableJSON:
        return
    raise AssertionError(f"read_json admitted {raw!r}")


@given(st.binary(max_size=200))
def test_any_bytes_are_read_or_refused(raw: bytes) -> None:
    try:
        read_json(raw)
    except UnreadableJSON:
        pass
