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

The model file has its own admission (``lcsim.service.model_store.admit``), built on
``encode_json``, since its issue names the place of the value.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["UnreadableJSON", "encode_json", "read_json", "read_json_file"]


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
