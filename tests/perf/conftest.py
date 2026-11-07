"""Performance checks (guide "Performance measurement protocol"; marker ``perf``).

They are excluded from ``bash scripts/check.sh`` by ``addopts`` in ``pyproject.toml`` and
run with ``taskset -c 0-3 pytest -m perf``. Each check records its measurements through the
``perf_record`` fixture; they are printed at the end of the session, so the protocol's
command shows them without ``-s``, for ``docs/research/perf-M<n>.md``.
"""

import json
from collections.abc import Callable
from typing import Any

import pytest

#: The measurements recorded in this session, one dict per check.
RECORDS: list[dict[str, Any]] = []


@pytest.fixture
def perf_record() -> Callable[[dict[str, Any]], None]:
    """Records one check's measurements for the end-of-session report."""
    return RECORDS.append


def pytest_terminal_summary(terminalreporter: Any) -> None:
    """Prints each recorded measurement as one JSON line."""
    if not RECORDS:
        return
    terminalreporter.section("performance measurements")
    for record in RECORDS:
        terminalreporter.write_line(json.dumps(record, sort_keys=False))
