"""The perf checks must load where ``resource`` does not exist (Windows), since pytest
imports every test module before it deselects the ``perf`` marker (review of PR #25).

Not marked ``perf``: this runs in ``bash scripts/check.sh``.
"""

import subprocess
import sys
from pathlib import Path

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


def test_peak_rss_is_read_where_resource_exists() -> None:
    from perf.test_three_machine_line import max_rss_bytes

    self_rss = max_rss_bytes("self")
    assert self_rss is not None and self_rss > 2**20  # this process holds more than 1 MiB
    children = max_rss_bytes("children")
    assert children is not None and children >= 0
