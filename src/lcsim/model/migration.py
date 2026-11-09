"""Format versions and migrations between major versions (spec 1 "Versioning").

``format_version`` is ``MAJOR.MINOR``: two ASCII decimal integers without leading zeros,
joined by a dot. This reader is ``FORMAT_VERSION``. It opens a file of its own major whose
minor is no higher than its own; the loader fills the defaults of a lower minor in memory
(a minor increase is additive and needs no migration). A file of another major opens only
through a migration, a function that rewrites a parsed model file of one major version into
one of another major version.

The registry maps a pair of major versions (from, to) to such a function; ``migrate``
follows the shortest chain of registered steps. The model layer never migrates on its own
and never writes a file: loading a file of another major reports E101 (with a hint that
says whether it can be converted), and the caller (the service at M6, the interface at M9)
asks the user, calls ``migrate``, and saves the result only after the user agrees.

Format 0 ships no migration, so ``MIGRATIONS`` is empty. The M1 acceptance test registers a
test-only migration from the test itself; the first real format change registers the real
one here and adds a 0.1 fixture that must still open.

Versions are compared as digit strings, never converted with ``int()``: Python refuses to
convert a string of more than 4,300 digits. Without leading zeros, a longer digit string is
the larger number.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from lcsim.model.issues import Issue

__all__ = [
    "FORMAT_VERSION",
    "MIGRATIONS",
    "Migration",
    "MigrationRegistry",
    "MigrationResult",
    "can_open",
    "migrate",
    "parse_version",
    "version_issue",
]

# The format version this reader writes and reads (spec 1 "Versioning"; 0.2 since AKS-123,
# which added the indexed optimization keys): it opens any file
# with the same major version and a minor version no higher than this one.
FORMAT_VERSION = "0.2"

# A migration takes a parsed model file of its "from" major (a dict it may change) and
# returns the file rewritten in its "to" major, with ``format_version`` set to a version of
# that major. It must not raise on a file it cannot fully read: it rewrites what it knows
# and leaves the rest for the schema pass, which runs when the result is loaded.
Migration = Callable[[dict[str, Any]], dict[str, Any]]

_NUMBER = "(0|[1-9][0-9]*)"
_VERSION = re.compile(rf"{_NUMBER}\.{_NUMBER}")
_MAJOR = re.compile(_NUMBER)
_PATH = "/format_version"


def parse_version(version: str) -> tuple[str, str] | None:
    """The major and minor parts of ``version`` as digit strings, or ``None`` when it is
    not ``MAJOR.MINOR`` (two ASCII decimal integers without leading zeros, and a dot)."""
    match = _VERSION.fullmatch(version)
    if match is None:
        return None
    return match.group(1), match.group(2)


def _number_key(digits: str) -> tuple[int, str]:
    """Sort key for a digit string without leading zeros: numeric order, no ``int()``."""
    return len(digits), digits


def _major(value: int | str) -> str:
    """A major version as its digit string, from a whole number or such a string."""
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise TypeError(f"a major version is a whole number, not {value!r}")
    text = str(value) if isinstance(value, int) else value
    if _MAJOR.fullmatch(text) is None:
        raise ValueError(f"{value!r} is not a major version (a whole number from 0)")
    return text


class MigrationRegistry:
    """Migrations between major versions, keyed by (from major, to major).

    Majors are given as whole numbers or digit strings without leading zeros; ``pairs``
    and ``route`` treat ``1`` and ``"1"`` as the same major.
    """

    def __init__(self) -> None:
        self._steps: dict[tuple[str, str], Migration] = {}

    def register(self, from_major: int | str, to_major: int | str, migration: Migration) -> None:
        """Add the migration from ``from_major`` to ``to_major``.

        Raises ``ValueError`` for a pair that already has one, or for two equal majors
        (a minor increase needs no migration).
        """
        pair = (_major(from_major), _major(to_major))
        if pair[0] == pair[1]:
            raise ValueError(f"a migration from major {pair[0]} to the same major is not needed")
        if pair in self._steps:
            raise ValueError(f"a migration from major {pair[0]} to {pair[1]} is already registered")
        self._steps[pair] = migration

    def unregister(self, from_major: int | str, to_major: int | str) -> None:
        """Remove the migration from ``from_major`` to ``to_major``; ``KeyError`` if none."""
        del self._steps[(_major(from_major), _major(to_major))]

    def pairs(self) -> tuple[tuple[str, str], ...]:
        """The registered (from major, to major) pairs, in numeric order."""
        return tuple(
            sorted(self._steps, key=lambda pair: (_number_key(pair[0]), _number_key(pair[1])))
        )

    def route(self, from_major: int | str, to_major: int | str) -> tuple[Migration, ...] | None:
        """The migrations that lead from ``from_major`` to ``to_major`` in the fewest steps.

        ``()`` for the same major; ``None`` when no chain of registered steps leads there.
        Of several shortest chains, the breadth-first search, trying steps in numeric order
        of majors, picks one deterministically.
        """
        path = self._path(_major(from_major), _major(to_major))
        return None if path is None else tuple(self._steps[pair] for pair in path)

    def _path(self, start: str, goal: str) -> list[tuple[str, str]] | None:
        """The (from, to) pairs of the shortest chain from ``start`` to ``goal``: a
        breadth-first search, with steps tried in numeric order."""
        came_from: dict[str, tuple[str, str] | None] = {start: None}
        queue = deque([start])
        while queue and goal not in came_from:
            current = queue.popleft()
            for pair in self.pairs():
                if pair[0] == current and pair[1] not in came_from:
                    came_from[pair[1]] = pair
                    queue.append(pair[1])
        if goal not in came_from:
            return None
        path: list[tuple[str, str]] = []
        link = came_from[goal]
        while link is not None:
            path.append(link)
            link = came_from[link[0]]
        return path[::-1]

    def _step(self, pair: tuple[str, str]) -> Migration:
        return self._steps[pair]


# The program's migrations. Format 0 has none; each new major version registers here the
# migration that upgrades the files of the major before it (spec 1 "Versioning").
MIGRATIONS = MigrationRegistry()


@dataclass(frozen=True)
class MigrationResult:
    """The outcome of ``migrate``.

    ``document`` is the file in the version asked for, or ``None`` when ``issues`` (E100
    or E101) say why it cannot be. ``migrated`` is true when it was rewritten into another
    major version: the caller asks the user before saving it over the file.
    """

    document: dict[str, Any] | None
    issues: tuple[Issue, ...]
    migrated: bool


def can_open(version: str, *, registry: MigrationRegistry = MIGRATIONS) -> bool:
    """Whether this reader opens a file of ``version``, as it is or after migrating it."""
    return _problem(version, FORMAT_VERSION, registry) is None


def version_issue(version: str, *, registry: MigrationRegistry = MIGRATIONS) -> Issue | None:
    """E101 when this reader cannot open a file of ``version`` as it is; ``None`` otherwise.

    A version of another major that ``registry`` can migrate is still E101, since the file
    is not read as it is; its hint says that the program can convert it.
    """
    parts = parse_version(version)
    if parts is not None and _readable(parts, FORMAT_VERSION):
        return None
    issue = _problem(version, FORMAT_VERSION, registry)
    if issue is not None:
        return issue
    return _e101(
        f"'format_version' is '{version}', but this program reads format versions "
        f"{_reader_range()}.",
        f"This program can convert the file to format version {FORMAT_VERSION}. Convert it "
        "when the program offers to; the file is rewritten only after you agree.",
    )


def migrate(
    document: Mapping[str, Any],
    to_version: str = FORMAT_VERSION,
    *,
    registry: MigrationRegistry = MIGRATIONS,
) -> MigrationResult:
    """``document`` rewritten into ``to_version``, by the migrations of ``registry``.

    ``document`` is a parsed model file; it is never changed, and the result is a copy. A
    file of the same major as ``to_version`` and a minor no higher is returned as it is,
    not migrated (the loader fills the defaults of a lower minor). A file of another major
    is passed through the shortest chain of registered migrations. A ``format_version``
    that is missing or not text is E100; one that cannot be brought to ``to_version`` is
    E101, the same issue the schema pass reports when ``to_version`` is this reader's.

    Raises ``ValueError`` when ``to_version`` is not ``MAJOR.MINOR``, or when a migration
    writes a ``format_version`` other than a version of its target major (for the last
    step, one no higher than ``to_version``): both are faults of the program, not the file.
    """
    target = parse_version(to_version)
    if target is None:
        raise ValueError(f"{to_version!r} is not a format version of the form MAJOR.MINOR")
    if "format_version" not in document:
        return _refused(
            "E100",
            "The model file is missing the required key 'format_version'.",
            "Add 'format_version' to the model file.",
        )
    version = document["format_version"]
    if not isinstance(version, str):
        return _refused(
            "E100",
            "'format_version' is not text, so the file's format version is unknown.",
            f"Write the format version as text, as in '{FORMAT_VERSION}'.",
        )
    issue = _problem(version, to_version, registry)
    if issue is not None:
        return MigrationResult(None, (issue,), migrated=False)
    parts = parse_version(version)
    assert parts is not None  # _problem reports a version of another form
    copied = _copy_json(dict(document))
    if parts[0] == target[0]:
        return MigrationResult(copied, (), migrated=False)
    path = registry._path(parts[0], target[0])
    assert path is not None  # _problem reports a major with no route
    for pair in path:
        step = registry._step(pair)
        copied = step(copied)
        last = pair == path[-1]
        written = copied.get("format_version")
        written_parts = parse_version(written) if isinstance(written, str) else None
        if (
            written_parts is None
            or written_parts[0] != pair[1]
            or (last and _number_key(written_parts[1]) > _number_key(target[1]))
        ):
            name = getattr(step, "__name__", repr(step))
            raise ValueError(
                f"the migration {name} from major {pair[0]} to {pair[1]} wrote "
                f"format_version {written!r}"
            )
    return MigrationResult(copied, (), migrated=True)


def _readable(parts: tuple[str, str], reader: str) -> bool:
    """Whether a version of ``parts`` is read as it is by a reader of version ``reader``."""
    reader_major, reader_minor = reader.split(".")
    return parts[0] == reader_major and _number_key(parts[1]) <= _number_key(reader_minor)


def _reader_range() -> str:
    major = FORMAT_VERSION.split(".")[0]
    return f"{major}.0 to {FORMAT_VERSION}"


def _problem(version: str, to_version: str, registry: MigrationRegistry) -> Issue | None:
    """E101 when a file of ``version`` cannot be brought to ``to_version``; else ``None``.

    A file of this reader's major and a minor above its own is newer than the program,
    whatever the target; it is never passed to a migration.
    """
    for_reader = to_version == FORMAT_VERSION
    parts = parse_version(version)
    if parts is None:
        return _e101(
            f"'format_version' is '{version}', which is not of the form MAJOR.MINOR, "
            f"such as '{FORMAT_VERSION}'.",
            f"Write the format version as two whole numbers with a dot, as in '{FORMAT_VERSION}'.",
        )
    target = parse_version(to_version)
    assert target is not None  # callers pass FORMAT_VERSION or a checked version
    reader_major = FORMAT_VERSION.split(".")[0]
    newer = parts[0] == reader_major and not _readable(parts, FORMAT_VERSION)
    if not newer:
        if parts[0] == target[0]:
            if _number_key(parts[1]) <= _number_key(target[1]):
                return None
        elif registry.route(parts[0], target[0]) is not None:
            return None
    if not for_reader:
        return _e101(
            f"'format_version' is '{version}', which this program cannot convert to "
            f"format version {to_version}.",
            "Open the file with a version of the program that reads it.",
        )
    message = (
        f"'format_version' is '{version}', but this program reads format versions "
        f"{_reader_range()}."
    )
    if parts[0] == reader_major:
        hint = (
            "The file was written by a newer version of the program; update the program to open it."
        )
    else:
        hint = (
            "The file uses another major version of the format, which this program "
            "cannot read or convert. Open it with a version of the program that reads it."
        )
    return _e101(message, hint)


def _e101(message: str, hint: str) -> Issue:
    return Issue(code="E101", component=None, path=_PATH, message=message, hint=hint)


def _refused(code: str, message: str, hint: str) -> MigrationResult:
    issue = Issue(code=code, component=None, path=_PATH, message=message, hint=hint)
    return MigrationResult(None, (issue,), migrated=False)


def _copy_json(value: dict[str, Any]) -> dict[str, Any]:
    """A deep copy of parsed JSON (dicts, lists, scalars), keeping key order.

    The walk uses an explicit stack, so a deeply nested file (the loader opens a ``ui``
    nested 20,000 levels deep) cannot exhaust Python's recursion limit.
    """
    holder: list[object] = [value]
    work: list[tuple[dict[Any, object] | list[object], Any]] = [(holder, 0)]
    while work:
        container, key = work.pop()
        item = container[key]
        if isinstance(item, dict):
            copied_dict = dict(item)
            container[key] = copied_dict
            work.extend((copied_dict, name) for name in copied_dict)
        elif isinstance(item, list):
            copied_list = list(item)
            container[key] = copied_list
            work.extend((copied_list, index) for index in range(len(copied_list)))
    copied = holder[0]
    assert isinstance(copied, dict)
    return copied
