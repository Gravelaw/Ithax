"""The milestone the build has reached, for the benchmark harness (AKS-100).

Spec 2 "Benchmark definitions": cases whose milestone is later than the current one are
skipped. Bump ``CURRENT_MILESTONE`` when the next milestone starts (M9 since AKS-119).
"""

import pytest

CURRENT_MILESTONE = "M9"


@pytest.fixture
def current_milestone() -> str:
    """The current milestone, ``CURRENT_MILESTONE``."""
    return CURRENT_MILESTONE
