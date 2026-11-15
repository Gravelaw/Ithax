"""``GET /v1/licences``: every package and engine the service runs on, with its licence and
authors, for the Help screen's "Open source licences" (#89; owner decisions B4, C7 and F4,
2026-11-13).

The list is generated, so it cannot drift from what is installed:

- **Packages** are the installed distributions that the package's licence list
  (``packaging/linux/licences.json``, which the Linux package build checks against what it
  installs; spec 3 "Packaging") records, and every run-time requirement of the installed
  ``ithax`` distribution, followed through its requirements. Each has its installed version,
  the licence the list records (or else its metadata's ``License-Expression``) and its
  authors from its metadata.
- **Engines** are the installed adapters, with the licence and the distribution that
  their ``Capabilities`` name (spec 1 "Engine adapter interface").
- **Python** is the running interpreter with the licence and the bundled libraries the list
  records for the package's Python.

The licence list is read from the source checkout, or else from ``share/ithax`` under the
Python prefix, where the Linux package puts it with the desktop shell's crates
(``ithax.service.config.default_licences_file``). A list that cannot be read leaves each
licence to the package's metadata and lists no bundled library and no crate.
"""

from __future__ import annotations

import platform
import re
from collections.abc import Iterator, Mapping
from email.utils import getaddresses
from importlib import metadata
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from packaging.requirements import InvalidRequirement, Requirement

from ithax import __version__
from ithax.service.config import default_licences_file
from ithax.service.state import ServiceState, service_state
from ithax.strict_json import UnreadableJSON, read_json_object_file

__all__ = ["authors", "licence_record", "listing", "router", "runtime_distributions"]

router = APIRouter(prefix="/v1")

#: The product itself (``LICENSE``; owner decisions B4 and C7).
PRODUCT = {
    "name": "Ithax",
    "licence": "AGPL-3.0-only",
    "source": "https://github.com/Gravelaw/Ithax",
}

#: Shown for a licence or authors that neither the list nor the metadata gives.
NOT_GIVEN = "not given"


def normalise(name: str) -> str:
    """A distribution name as PEP 503 compares it."""
    return re.sub(r"[-_.]+", "-", name).lower()


def licence_record(path: Path) -> dict[str, Any]:
    """The licence list at ``path``, or an empty one when it cannot be read."""
    try:
        return read_json_object_file(path)
    except (OSError, UnreadableJSON):
        return {}


def _requirements(
    distribution: metadata.Distribution, extras: frozenset[str]
) -> Iterator[tuple[str, frozenset[str]]]:
    """``distribution``'s requirements that apply here with the ``extras`` asked of it, each
    with the extras it asks of its own distribution (review of PR #203: mcp asks for
    ``pyjwt[crypto]``, and only that extra brings in cryptography)."""
    for line in distribution.requires or []:
        try:
            requirement = Requirement(line)
        except InvalidRequirement:
            continue
        marker = requirement.marker
        if marker is None or any(marker.evaluate({"extra": extra}) for extra in {"", *extras}):
            yield requirement.name, frozenset(requirement.extras)


def _installed(name: str) -> metadata.Distribution | None:
    """The installed distribution ``name``, or ``None``; a name the list or an adapter gives
    that names nothing, empty included, is ``None`` too (review of PR #203)."""
    try:
        return metadata.distribution(name)
    except (metadata.PackageNotFoundError, ValueError):
        return None


def runtime_distributions(names: list[str]) -> dict[str, metadata.Distribution]:
    """The installed distributions of ``names`` and of every run-time requirement of the
    ``ithax`` distribution, followed through theirs with the extras each asks for; by
    normalised name, ``ithax`` left out."""
    found: dict[str, metadata.Distribution] = {}
    # The extras already followed for each distribution: one asked again with a new extra
    # is followed again for it.
    followed: dict[str, frozenset[str]] = {}
    stack: list[tuple[str, frozenset[str]]] = [(name, frozenset()) for name in ["ithax", *names]]
    while stack:
        name, extras = stack.pop()
        key = normalise(name)
        if key in followed and extras <= followed[key]:
            continue
        distribution = found.get(key) or _installed(name)
        if distribution is None:
            continue
        found[key] = distribution
        followed[key] = followed.get(key, frozenset()) | extras
        stack.extend(_requirements(distribution, followed[key]))
    found.pop("ithax", None)
    return found


def _names(*fields: str | None) -> list[str]:
    """The people named in metadata fields of addresses (``Name <mail>``), without the
    addresses; an address with no name is left out."""
    named = getaddresses([field for field in fields if field])
    return [name for name, _ in named if name]


#: A copyright line: "Copyright", then "(c)" or "©", a year or both, then the holder; a
#: line of a licence's own text ("copyright license to reproduce") has neither.
_COPYRIGHT = re.compile(r"^\s*Copyright\s+(\([cC]\)\s*|©\s*)?(\d[\d\s,\u2013-]*\s)?(.+)$")
_LICENCE_FILE = re.compile(r"^(licen[cs]e|copying|notice)", re.IGNORECASE)


def copyright_holder(text: str) -> str | None:
    """The holder in the first copyright line of a licence text, skipping a template line
    with brackets (the Apache-2.0 appendix); ``None`` when there is none. The interface's
    build reads its packages' licences the same way (``ui/plugins/notices.ts``)."""
    for line in text.splitlines():
        match = _COPYRIGHT.match(line)
        if match and (match[1] or match[2]) and "[" not in line:
            return match[3].strip().lstrip(", ")
    return None


def _licence_holder(distribution: metadata.Distribution) -> str | None:
    """The copyright holder that the distribution's licence files name: its own licence
    (``LICENSE``, ``LICENCE.rst``) before the licences of code it includes
    (``LICENCE.python``)."""
    files = sorted(
        distribution.files or [],
        key=lambda file: (file.suffix not in ("", ".txt", ".rst", ".md"), str(file)),
    )
    for file in files:
        if not (_LICENCE_FILE.match(file.name) and ".dist-info" in str(file)):
            continue
        try:
            text = Path(str(file.locate())).read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        holder = copyright_holder(text)
        if holder is not None:
            return holder
    return None


def _field(distribution: metadata.Distribution, name: str) -> str | None:
    """A metadata field's first value, or ``None`` when it is absent or empty."""
    values = distribution.metadata.get_all(name) or []
    return (str(values[0]).strip() or None) if values else None


def _named_authors(distribution: metadata.Distribution) -> str | None:
    for plain, addresses in (("Author", "Author-email"), ("Maintainer", "Maintainer-email")):
        named = _field(distribution, plain)
        if named:
            return named
        names = _names(_field(distribution, addresses))
        if names:
            return ", ".join(names)
    return None


def authors(distribution: metadata.Distribution) -> str:
    """The authors a distribution's metadata names, without e-mail addresses: ``Author``,
    else the names in ``Author-email``, else ``Maintainer``, else the names in
    ``Maintainer-email``. When that is none, or only points to a file ("See AUTHORS.txt"),
    the copyright holder its licence files name; else ``NOT_GIVEN``."""
    named = _named_authors(distribution)
    if named is not None and not named.lower().startswith("see "):
        return named
    return _licence_holder(distribution) or named or NOT_GIVEN


def _licence(distribution: metadata.Distribution, recorded: Mapping[str, Any]) -> str:
    entry = recorded.get(normalise(distribution.name))
    if isinstance(entry, Mapping) and isinstance(entry.get("licence"), str):
        return str(entry["licence"])
    return _field(distribution, "License-Expression") or NOT_GIVEN


def _packages(record: Mapping[str, Any]) -> list[dict[str, str]]:
    listed = record.get("distributions")
    recorded = (
        {normalise(str(name)): entry for name, entry in listed.items()}
        if isinstance(listed, Mapping)
        else {}
    )
    found = runtime_distributions([str(name) for name in recorded])
    rows = [
        {
            "name": distribution.name,
            "version": distribution.version,
            "licence": _licence(distribution, recorded),
            "authors": authors(distribution),
        }
        for distribution in found.values()
    ]
    return sorted(rows, key=lambda row: row["name"].lower())


def _engines(state: ServiceState) -> list[dict[str, str]]:
    rows = []
    for name in sorted(state.adapters):
        adapter = state.adapters[name]
        capabilities = adapter.capabilities()
        installed = _installed(capabilities.distribution) if capabilities.distribution else None
        rows.append(
            {
                "name": name,
                "version": adapter.version,
                "licence": capabilities.licence,
                "distribution": capabilities.distribution,
                "authors": NOT_GIVEN if installed is None else authors(installed),
            }
        )
    return rows


def _records(value: object) -> list[dict[str, str]]:
    """The entries of a list of ``{name, version?, licence}`` objects, as text."""
    if not isinstance(value, list):
        return []
    return [
        {key: str(item[key]) for key in ("name", "version", "licence") if key in item}
        for item in value
        if isinstance(item, Mapping) and "name" in item and "licence" in item
    ]


def listing(state: ServiceState, record: Mapping[str, Any]) -> dict[str, Any]:
    """The response of ``GET /v1/licences`` for the licence list ``record``."""
    python = record.get("python")
    python = python if isinstance(python, Mapping) else {}
    version = platform.python_version()
    return {
        "product": {**PRODUCT, "version": __version__},
        "engines": _engines(state),
        "python": {
            "name": platform.python_implementation(),
            "version": version,
            "licence": str(python.get("licence", "PSF-2.0")),
            # What the package's Python bundles, when this is that Python.
            "bundled": _records(python.get("bundled")) if python.get("version") == version else [],
        },
        "packages": _packages(record),
        "crates": _records(record.get("crates")),
    }


@router.get("/licences")
def get_licences(state: Annotated[ServiceState, Depends(service_state)]) -> dict[str, Any]:
    """Every package and engine with its licence and authors."""
    path = state.config.licences_file or default_licences_file()
    return listing(state, licence_record(path))
