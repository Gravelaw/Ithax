"""The ``run_id`` (spec 1 "Run folder and results"): ``<UTC time YYYYMMDDTHHMMSS>-<6
random base32 characters>``.

The six characters are RFC 4648 base32 (``A`` to ``Z``, ``2`` to ``7``) from the operating
system's generator (``secrets``). They only make the identifier unique; they are not
simulation randomness, so the spec 1 stream scheme does not apply (docs/DECISIONS.md,
AKS-103). Never the global ``random`` or ``numpy.random`` generator.
"""

from __future__ import annotations

import base64
import re
import secrets
from datetime import UTC, datetime

__all__ = ["RUN_ID_PATTERN", "new_run_id"]

RUN_ID_PATTERN = re.compile(r"[0-9]{8}T[0-9]{6}-[A-Z2-7]{6}")


def new_run_id(moment: datetime) -> str:
    """A new ``run_id`` for a run created at ``moment``, which must carry a time zone."""
    if moment.tzinfo is None:
        raise ValueError("a run_id needs a time with a time zone, to write it in UTC")
    stamp = moment.astimezone(UTC).strftime("%Y%m%dT%H%M%S")
    # 4 random bytes give 7 base32 characters; the first 6 carry 30 random bits.
    characters = base64.b32encode(secrets.token_bytes(4)).decode("ascii")[:6]
    return f"{stamp}-{characters}"
