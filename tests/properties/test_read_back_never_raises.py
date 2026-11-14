"""Property: a file the product reads back gives defaults, issues or ``None``, never an
exception, whatever it holds (P6; #99). Covers ``settings.json`` (read by the service for
``GET /v1/settings``) and a run's ``manifest.json``."""

import json
import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from ithax.runs.manifest import MANIFEST_FILE, read_run_manifest
from ithax.service.hardware import SETTINGS_FILE, Hardware
from ithax.service.settings_store import SettingsStore
from properties.strategies import JSON_VALUES

HARDWARE = Hardware(cores=4, memory=8 * 1024**3, graphics=())


def _contents() -> st.SearchStrategy[bytes]:
    """Any bytes, any JSON value (NaN included), or an object with hostile values."""
    as_json = JSON_VALUES.map(lambda value: json.dumps(value).encode("utf-8"))
    objects = st.dictionaries(st.text(max_size=12), JSON_VALUES, max_size=6).map(
        lambda value: json.dumps(value).encode("utf-8")
    )
    return st.one_of(st.binary(max_size=200), as_json, objects)


@given(_contents())
def test_any_settings_file_reads_as_settings(raw: bytes) -> None:
    with tempfile.TemporaryDirectory() as folder:
        config_dir = Path(folder)
        (config_dir / SETTINGS_FILE).write_bytes(raw)
        body = SettingsStore(config_dir, HARDWARE).read()
    assert set(body) == {"settings", "issues"}


@given(_contents())
def test_any_manifest_reads_as_a_run_or_none(raw: bytes) -> None:
    with tempfile.TemporaryDirectory() as folder:
        run = Path(folder) / "r-1"
        run.mkdir()
        (run / MANIFEST_FILE).write_bytes(raw)
        read = read_run_manifest(run)
    assert read is None or read["run_id"] == "r-1"
