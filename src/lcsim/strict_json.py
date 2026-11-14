"""The product's JSON files: one encoder for what it writes and one strict reader for what it
reads back from disk (review of PR #36).

``encode_json`` gives the exact bytes the product writes: JSON indented by two spaces and
ending in a newline, in strict UTF-8, with no NaN or infinity. ``read_json`` admits a
document only when ``encode_json`` could write it back: a file changed outside the product
may hold ``NaN``, ``Infinity``, a number such as ``1e999`` (which Python reads as an
infinity) or a lone surrogate escape (``"\\ud800"``), which the standard reader takes but
which no file the product writes, and no response it sends, may hold. Such a document, like
one that is not JSON in UTF-8, raises ``UnreadableJSON``; each caller turns that into its own
coded issue for that file (an unreadable project, a run that is not a run, default
settings), never a 500.

A number read from such a file and then used in arithmetic or a comparison is taken through
``whole_in`` or ``real_in``, which declare its kind and range and give ``None`` for anything
else, a ``bool`` included; they never raise, so a whole number too large for a float (such
as ``10**400`` written out) is refused, not converted (review of PR #36). Each caller says
what ``None`` means for its field: a default for a setting, an unreadable file otherwise.

The model file has its own admission (``lcsim.service.model_store.admit``), built on
``encode_json``, since its issue names the place of the value.

``json_text`` is the one place JSON text is made for anything but a file: a message that
quotes a value, a line of a progress stream, a response body, an MCP request or result. It
too refuses NaN and infinity. Ruff's ``banned-api`` sends every other use of the ``json``
module here (docs/retrospective/proposed-agent-setup.md, P5; #99).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, TypeGuard

__all__ = [
    "MAX_WHOLE",
    "UnreadableJSON",
    "encode_json",
    "is_finite_real",
    "is_number",
    "is_whole",
    "json_text",
    "read_json",
    "read_json_file",
    "read_json_object_file",
    "real_in",
    "whole_in",
]

#: The largest whole number a stored count, revision or size may hold: a signed 64-bit
#: integer, which every reader of the files (and SQLite) can hold.
MAX_WHOLE = 2**63 - 1


class UnreadableJSON(ValueError):
    """A JSON file the product cannot read, or could not write back."""


def encode_json(value: object) -> bytes:
    """The exact bytes the service writes for ``value``: JSON indented by two spaces and
    ending in a newline, encoded as strict UTF-8. ``ValueError`` when that is impossible:
    a NaN or an infinity, or text that is not valid Unicode (a lone surrogate such as
    ``"\\ud800"``, which a JSON escape can carry); ``UnicodeEncodeError`` is one."""
    try:
        text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    except (TypeError, RecursionError) as error:
        raise ValueError("the value cannot be written as JSON") from error
    return text.encode("utf-8")


def json_text(value: object, *, ascii_only: bool = False, compact: bool = False) -> str:
    """``value`` as one line of JSON text: every character outside ASCII escaped when
    ``ascii_only``, and no spaces after the separators when ``compact``. ``ValueError`` for
    a NaN or an infinity, ``TypeError`` for a value JSON cannot hold."""
    separators = (",", ":") if compact else None
    return json.dumps(value, ensure_ascii=ascii_only, allow_nan=False, separators=separators)


def read_json(raw: bytes) -> object:
    """``raw`` (UTF-8, an optional byte order mark) as a JSON document that ``encode_json``
    can write back; ``UnreadableJSON`` otherwise."""
    try:
        document = json.loads(raw.decode("utf-8-sig"))
        encode_json(document)
    except (ValueError, RecursionError):
        raise UnreadableJSON("not a JSON document the product can write back") from None
    return document


def read_json_file(path: Path) -> object:
    """``read_json`` of the file at ``path``; ``OSError`` when it cannot be read."""
    return read_json(path.read_bytes())


def is_whole(value: object) -> TypeGuard[int]:
    """Whether ``value`` is a JSON integer: an ``int`` that is not a ``bool`` (``True`` is an
    ``int`` in Python, but not a JSON number)."""
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value: object) -> TypeGuard[int | float]:
    """Whether ``value`` is a JSON number: an ``int`` or a ``float``, not a ``bool``."""
    return isinstance(value, int | float) and not isinstance(value, bool)


def is_finite_real(value: object) -> TypeGuard[int | float]:
    """Whether ``value`` is a finite JSON number. An ``int`` is always finite and is never
    converted to a float, so a whole number above about 1.8e308 (``10**309``) is admitted
    rather than overflowing."""
    return is_whole(value) or (isinstance(value, float) and math.isfinite(value))


def whole_in(value: object, minimum: int, maximum: int) -> int | None:
    """``value`` when it is a whole number (a JSON integer, not a ``bool`` or a float) from
    ``minimum`` to ``maximum``; otherwise ``None``."""
    if not is_whole(value):
        return None
    return value if minimum <= value <= maximum else None


def real_in(
    value: object, minimum: float, maximum: float, *, above_minimum: bool = False
) -> float | None:
    """``value`` as a float when it is a finite number (a JSON integer or float, not a
    ``bool``) from ``minimum`` (excluded when ``above_minimum``) to ``maximum``; otherwise
    ``None``. The range is checked before any conversion, so a whole number too large for a
    float is refused rather than raising."""
    if not is_number(value):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    low_ok = value > minimum if above_minimum else value >= minimum
    if not (low_ok and value <= maximum):
        return None
    return float(value)


def read_json_object_file(path: Path) -> dict[str, Any]:
    """``read_json_file`` of a file that must hold a JSON object; ``UnreadableJSON`` when
    it holds anything else, ``OSError`` when it cannot be read."""
    document = read_json_file(path)
    if not isinstance(document, dict):
        raise UnreadableJSON("not a JSON object")
    return document
