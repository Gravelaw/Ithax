"""The perf checks must load where ``resource`` does not exist (Windows), since pytest
imports every test module before it deselects the ``perf`` marker (review of PR #25).

Not marked ``perf``: this runs in ``bash scripts/check.sh``.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]

WITHOUT_RESOURCE = """
import sys
sys.modules["resource"] = None  # import resource now raises ImportError, as on Windows
import perf.test_three_machine_line as module
print(module.max_rss_bytes("self"), module.max_rss_bytes("children"))
"""


def test_the_perf_module_loads_without_resource() -> None:
    finished = subprocess.run(
        [sys.executable, "-c", WITHOUT_RESOURCE],
        cwd=TESTS,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    assert finished.stdout.split() == ["None", "None"]


def test_peak_rss_is_read_where_resource_exists_and_none_elsewhere() -> None:
    """Holds on every platform, with nothing skipped: a reading where ``resource`` exists
    (Linux, macOS), ``None`` where it does not (Windows; second review of PR #25)."""
    from perf.test_three_machine_line import max_rss_bytes

    self_rss, children = max_rss_bytes("self"), max_rss_bytes("children")
    if importlib.util.find_spec("resource") is None:
        assert (self_rss, children) == (None, None)
    else:
        assert self_rss is not None and self_rss > 2**20  # this process holds over 1 MiB
        assert children is not None and children >= 0


def test_peak_rss_is_none_without_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    from perf.test_three_machine_line import max_rss_bytes

    monkeypatch.setitem(sys.modules, "resource", None)  # as on Windows
    assert (max_rss_bytes("self"), max_rss_bytes("children")) == (None, None)


#: Runs this folder's tests, except this one, in a fresh interpreter without ``resource``.
SUITE_WITHOUT_RESOURCE = """
import sys
sys.modules["resource"] = None
import pytest
sys.exit(pytest.main(["-q", "-p", "no:cacheprovider", "-k", "not without_resource_pass",
                      sys.argv[1]]))
"""


def test_the_folder_tests_without_resource_pass() -> None:
    """The tests that ``check.sh`` runs here also pass where ``resource`` is missing
    (second review of PR #25)."""
    finished = subprocess.run(
        [sys.executable, "-c", SUITE_WITHOUT_RESOURCE, str(TESTS / "perf")],
        cwd=TESTS.parent,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert finished.returncode == 0, finished.stdout + finished.stderr
