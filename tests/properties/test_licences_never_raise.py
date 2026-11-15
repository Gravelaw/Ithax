"""Property: whatever the package's licence list holds, ``GET /v1/licences`` lists every
installed package with text for each field and never raises (P6; review of PR #203, where
an empty distribution name raised ``ValueError``)."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from ithax.service.licences import licence_record, listing
from properties.strategies import HOSTILE_STRINGS, JSON_VALUES

#: Lists shaped like the real one, with hostile names and values in every place.
RECORDS = st.fixed_dictionaries(
    {},
    optional={
        "distributions": st.one_of(
            JSON_VALUES, st.dictionaries(HOSTILE_STRINGS, JSON_VALUES, max_size=5)
        ),
        "python": JSON_VALUES,
        "crates": JSON_VALUES,
    },
)
#: The state ``listing`` reads: no adapters.
STATE: Any = SimpleNamespace(adapters={})


def _texts(rows: list[dict[str, Any]]) -> bool:
    return all(isinstance(value, str) for row in rows for value in row.values())


@settings(max_examples=60, deadline=None)
@given(RECORDS)
def test_any_licence_list_gives_a_listing(record: dict[str, Any]) -> None:
    body = listing(STATE, record)
    assert {row["name"] for row in body["packages"]} >= {"numpy", "simpy"}
    assert _texts(body["packages"]) and _texts(body["crates"]) and _texts(body["python"]["bundled"])


@settings(max_examples=60, deadline=None)
@given(st.one_of(st.binary(max_size=200), JSON_VALUES.map(lambda v: json.dumps(v).encode())))
def test_any_licence_file_reads_as_an_object(raw: bytes) -> None:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "licences.json"
        path.write_bytes(raw)
        assert isinstance(licence_record(path), dict)
