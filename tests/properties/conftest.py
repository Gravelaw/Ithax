"""Hypothesis profiles for the property tests (docs/retrospective/proposed-agent-setup.md,
P6; #99).

- ``ci``, used when ``CI`` is set (GitHub Actions sets it): derandomized, so a failure is
  reproducible from the log, and with no deadline, so a slow runner does not fail a test.
- ``thorough``: 2,000 examples per test, for a long run by hand or on a schedule
  (``HYPOTHESIS_PROFILE=thorough``).
- otherwise Hypothesis's default: 100 random examples per test.
"""

import os

from hypothesis import settings

settings.register_profile("ci", derandomize=True, deadline=None)
settings.register_profile("thorough", max_examples=2000, deadline=None)
settings.load_profile(
    os.environ.get("HYPOTHESIS_PROFILE") or ("ci" if os.environ.get("CI") else "default")
)
