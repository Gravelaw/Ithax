"""Format versions and migrations (spec 1 "Versioning"; AKS-92).

The spec 1 acceptance row for M1: "A test-only migration rewrites a 0.1 file to a test
version and back; the first real format change replaces it with the real migration and a
0.1 fixture that must still open". The test-only migration lives in this file and is
registered from here, never shipped in ``src/``: format 0 has no other major to migrate to.
"""

import copy
import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ithax.model import migration as migration_module
from ithax.model.issues import Issue
from ithax.model.loading import load_document, load_text
from ithax.model.migration import (
    FORMAT_VERSION,
    MIGRATIONS,
    MigrationRegistry,
    MigrationResult,
    can_open,
    migrate,
    parse_version,
    version_issue,
)
from ithax.model.schema import FORMAT_VERSION as SCHEMA_FORMAT_VERSION
from ithax.model.schema import schema_pass

ROOT = Path(__file__).resolve().parents[2]
COFFEE_SHOP_FILE = ROOT / "examples" / "coffee_shop.json"

# The test-only format version. Its major is far from any real one, so that the first real
# format change (major 1) cannot collide with it.
TEST_VERSION = "99.0"
TEST_MAJOR = 99

# The keys the test-only format renames, in both directions.
RENAMES = {"components": "blocks", "connections": "links"}


def coffee() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(COFFEE_SHOP_FILE.read_text(encoding="utf-8"))
    return loaded


def renamed(document: dict[str, Any], names: dict[str, str], version: str) -> dict[str, Any]:
    """``document`` with its top-level keys renamed, in place, and a new version."""
    rewritten = {names.get(key, key): value for key, value in document.items()}
    rewritten["format_version"] = version
    return rewritten


def to_test_format(document: dict[str, Any]) -> dict[str, Any]:
    """The test-only migration up: 0.x to 99.0, renaming two top-level keys."""
    return renamed(document, RENAMES, TEST_VERSION)


def from_test_format(document: dict[str, Any]) -> dict[str, Any]:
    """The test-only migration down: 99.0 to 0.1, renaming them back. It writes 0.1, a
    minor of the reader's major no higher than the reader's 0.3 (#77), so a 0.1 file
    comes back as it was."""
    return renamed(document, {new: old for old, new in RENAMES.items()}, "0.1")


def serialized(document: object) -> bytes:
    """One fixed serializer: equal bytes mean equal keys, key order, values and types."""
    return json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")


def only(issues: tuple[Issue, ...] | list[Issue]) -> Issue:
    assert len(issues) == 1, [issue.as_dict() for issue in issues]
    return issues[0]


@pytest.fixture
def test_migrations() -> Iterator[None]:
    """The test-only migration, registered in the program's registry for one test."""
    MIGRATIONS.register(0, TEST_MAJOR, to_test_format)
    MIGRATIONS.register(TEST_MAJOR, 0, from_test_format)
    try:
        yield
    finally:
        MIGRATIONS.unregister(0, TEST_MAJOR)
        MIGRATIONS.unregister(TEST_MAJOR, 0)


# --- the acceptance test (spec 1 acceptance table, M1) -------------------------------------


def test_a_test_only_migration_rewrites_a_0_1_file_to_a_test_version_and_back(
    test_migrations: None,
) -> None:
    file_bytes = COFFEE_SHOP_FILE.read_bytes()
    original = coffee()
    assert original["format_version"] == "0.1"

    up = migrate(original, TEST_VERSION)
    assert up.issues == ()
    assert up.migrated
    assert up.document is not None
    assert up.document["format_version"] == TEST_VERSION
    assert "blocks" in up.document and "components" not in up.document
    assert list(up.document) == [RENAMES.get(key, key) for key in original]

    # This reader does not open the test version as it is, but says it can convert it.
    issue = only(load_document(up.document).issues)
    assert (issue.code, issue.path) == ("E101", "/format_version")
    assert "can convert" in issue.hint
    assert can_open(TEST_VERSION)

    down = migrate(up.document, FORMAT_VERSION)
    assert down.issues == ()
    assert down.migrated
    assert down.document == original
    assert serialized(down.document) == serialized(original)
    # The migrated-back file opens with zero issues.
    assert load_document(down.document).issues == ()

    # Nothing was written: the file and the dict passed in are unchanged.
    assert COFFEE_SHOP_FILE.read_bytes() == file_bytes
    assert serialized(original) == serialized(coffee())


def test_the_round_trip_keeps_every_value_type_and_key_order(test_migrations: None) -> None:
    # 1 and 1.0, key order in nested objects, and text outside ASCII all survive.
    original = coffee()
    original["meta"] = {"name": "Café ☕", "z": 1, "a": 1.0, "nested": {"b": [1, 2.5, None]}}
    up = migrate(original, TEST_VERSION).document
    assert up is not None
    down = migrate(up, FORMAT_VERSION).document
    assert down is not None
    assert serialized(down) == serialized(original)
    assert type(down["meta"]["z"]) is int
    assert type(down["meta"]["a"]) is float


def test_the_program_ships_no_migration_in_format_0() -> None:
    # The first real format change replaces the test-only migration with a real one.
    assert MIGRATIONS.pairs() == ()
    assert not can_open(TEST_VERSION)


def test_a_fresh_program_has_no_migration_registered() -> None:
    # The test-only migration is registered from this file only: a new interpreter that
    # imports the whole model layer finds the registry empty.
    code = (
        "import ithax.model.loading, ithax.model.migration as m; "
        "print(m.MIGRATIONS.pairs(), m.can_open('99.0'))"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=ROOT
    )
    assert done.stdout.strip() == "() False"


# --- versions ------------------------------------------------------------------------------


def test_format_version_is_shared_with_the_schema_pass() -> None:
    assert FORMAT_VERSION == "0.3"
    assert SCHEMA_FORMAT_VERSION is FORMAT_VERSION


@pytest.mark.parametrize(
    ("version", "parts"),
    [("0.1", ("0", "1")), ("0.0", ("0", "0")), ("12.340", ("12", "340")), ("99.0", ("99", "0"))],
)
def test_parse_version(version: str, parts: tuple[str, str]) -> None:
    assert parse_version(version) == parts


@pytest.mark.parametrize(
    "version", ["0", "0.1.0", "v0.1", "0.01", "00.1", " 0.1", "0.1 ", "", "\u0660.\u0661", "-1.0"]
)
def test_parse_version_refuses_other_strings(version: str) -> None:
    assert parse_version(version) is None


def test_parse_version_keeps_very_long_numbers_as_text() -> None:
    assert parse_version("1" * 5000 + ".0") == ("1" * 5000, "0")


# --- the registry ----------------------------------------------------------------------------


def identity(document: dict[str, Any]) -> dict[str, Any]:
    return document


def test_register_and_unregister() -> None:
    registry = MigrationRegistry()
    registry.register(2, 10, identity)
    registry.register(0, 2, identity)
    registry.register("10", "3", identity)
    # Pairs in numeric order, not text order.
    assert registry.pairs() == (("0", "2"), ("2", "10"), ("10", "3"))
    registry.unregister(2, 10)
    assert registry.pairs() == (("0", "2"), ("10", "3"))


def test_register_refuses_a_second_migration_for_the_same_pair() -> None:
    registry = MigrationRegistry()
    registry.register(0, 1, identity)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("0", "1", identity)


def test_register_refuses_a_migration_within_one_major() -> None:
    # Spec 1: a minor increase is additive and needs no migration.
    with pytest.raises(ValueError, match="same major"):
        MigrationRegistry().register(1, 1, identity)


@pytest.mark.parametrize("major", [-1, "01", "1.0", "", "x", "\u0661"])
def test_register_refuses_a_major_that_is_not_a_whole_number(major: int | str) -> None:
    with pytest.raises(ValueError, match="not a major version"):
        MigrationRegistry().register(major, 5, identity)
    with pytest.raises(ValueError, match="not a major version"):
        MigrationRegistry().register(5, major, identity)


@pytest.mark.parametrize("major", [True, 1.0, None])
def test_register_refuses_a_major_of_another_type(major: object) -> None:
    with pytest.raises(TypeError, match="major version"):
        MigrationRegistry().register(major, 5, identity)  # type: ignore[arg-type]


def test_unregister_an_unknown_pair() -> None:
    with pytest.raises(KeyError):
        MigrationRegistry().unregister(0, 1)


def test_route_takes_the_fewest_steps() -> None:
    def step(name: str) -> Any:
        def migration(document: dict[str, Any]) -> dict[str, Any]:
            return document

        migration.__name__ = name
        return migration

    registry = MigrationRegistry()
    zero_one, one_two, zero_two, two_three = step("01"), step("12"), step("02"), step("23")
    registry.register(0, 1, zero_one)
    registry.register(1, 2, one_two)
    registry.register(2, 3, two_three)
    assert registry.route(0, 3) == (zero_one, one_two, two_three)
    registry.register(0, 2, zero_two)
    assert registry.route(0, 3) == (zero_two, two_three)
    assert registry.route("0", "2") == (zero_two,)
    assert registry.route(1, 1) == ()
    assert registry.route(3, 0) is None
    assert registry.route(5, 0) is None


def test_route_of_a_very_long_major_never_converts_it_to_a_number() -> None:
    registry = MigrationRegistry()
    assert registry.route("1" * 5000, "0") is None
    assert registry.route("1" * 5000, "1" * 5000) == ()


# --- can_open and version_issue (the reader, version 0.1) ------------------------------------


@pytest.mark.parametrize("version", ["0.0", "0.1", "0.2", "0.3"])
def test_the_reader_opens_its_own_major_up_to_its_minor(version: str) -> None:
    assert can_open(version)
    assert version_issue(version) is None


@pytest.mark.parametrize("version", ["0.4", "1.0", "0.1.0", "v0.1", "", "1" * 5000 + ".0"])
def test_the_reader_cannot_open_other_versions_without_a_migration(version: str) -> None:
    assert not can_open(version)
    issue = version_issue(version)
    assert issue is not None
    assert (issue.code, issue.path, issue.component) == ("E101", "/format_version", None)


def test_a_major_with_a_migration_can_be_opened_after_converting() -> None:
    registry = MigrationRegistry()
    registry.register(2, 1, identity)
    registry.register(1, 0, identity)
    assert can_open("2.7", registry=registry)
    assert not can_open("3.0", registry=registry)
    # A minor above the reader's is never migrated within one major.
    assert not can_open("0.4", registry=registry)
    issue = version_issue("2.7", registry=registry)
    assert issue is not None
    assert issue.code == "E101"
    assert issue.message == (
        "'format_version' is '2.7', but this program reads format versions 0.0 to 0.3."
    )
    assert issue.hint == (
        "This program can convert the file to format version 0.3. Convert it when the "
        "program offers to; the file is rewritten only after you agree."
    )


def test_the_schema_pass_says_when_a_file_can_be_converted(test_migrations: None) -> None:
    document = coffee()
    document["format_version"] = TEST_VERSION
    issue = only(schema_pass(document))
    assert issue.code == "E101"
    assert "can convert the file to format version 0.3" in issue.hint


def test_loading_never_migrates(test_migrations: None) -> None:
    # The model layer only reports: the caller asks the user and calls migrate.
    text = COFFEE_SHOP_FILE.read_text(encoding="utf-8").replace('"0.1"', f'"{TEST_VERSION}"', 1)
    result = load_text(text)
    assert result.model is None
    assert only(result.issues).code == "E101"


# --- migrate ----------------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["0.0", "0.1", "0.2", "0.3"])
def test_migrate_within_the_readers_major_returns_an_unchanged_copy(version: str) -> None:
    document = coffee()
    document["format_version"] = version
    result = migrate(document)
    assert result == MigrationResult(document, (), migrated=False)
    assert result.document is not document
    assert result.document is not None
    assert result.document["components"] is not document["components"]


def test_migrate_is_to_the_readers_version_by_default(test_migrations: None) -> None:
    document = to_test_format(coffee())
    result = migrate(document)
    assert result.document == coffee()


def test_migrate_never_changes_the_document_it_is_given() -> None:
    def destructive(document: dict[str, Any]) -> dict[str, Any]:
        document["meta"]["name"] = "changed"
        document["format_version"] = "0.1"
        del document["components"]
        return document

    registry = MigrationRegistry()
    registry.register(1, 0, destructive)
    document = coffee()
    document["format_version"] = "1.0"
    before = copy.deepcopy(document)
    result = migrate(document, registry=registry)
    assert result.migrated
    assert result.document is not None
    assert result.document["meta"]["name"] == "changed"
    assert document == before


def test_migrate_follows_a_route_of_several_steps() -> None:
    def two_to_one(document: dict[str, Any]) -> dict[str, Any]:
        document["format_version"] = "1.4"
        document["steps"] = ["2 to 1"]
        return document

    def one_to_zero(document: dict[str, Any]) -> dict[str, Any]:
        assert document["format_version"] == "1.4"
        document["format_version"] = "0.1"
        document["steps"].append("1 to 0")
        return document

    registry = MigrationRegistry()
    registry.register(2, 1, two_to_one)
    registry.register(1, 0, one_to_zero)
    result = migrate({"format_version": "2.3"}, registry=registry)
    assert result == MigrationResult(
        {"format_version": "0.1", "steps": ["2 to 1", "1 to 0"]}, (), migrated=True
    )


def test_migrate_reports_a_missing_version_as_e100() -> None:
    issue = only(migrate({"meta": {"name": "x"}}).issues)
    assert (issue.code, issue.path) == ("E100", "/format_version")
    assert issue.message == "The model file is missing the required key 'format_version'."


@pytest.mark.parametrize("version", [1, 0.1, None, True, ["0.1"], {"v": "0.1"}])
def test_migrate_reports_a_version_that_is_not_text_as_e100(version: object) -> None:
    result = migrate({"format_version": version})
    assert result.document is None
    issue = only(result.issues)
    assert (issue.code, issue.path) == ("E100", "/format_version")
    assert issue.message == "'format_version' is not text, so the file's format version is unknown."


@pytest.mark.parametrize(
    ("version", "hint_part"),
    [
        ("v0.1", "two whole numbers"),
        ("0.4", "newer version of the program"),
        ("1.0", "cannot read or convert"),
    ],
)
def test_migrate_to_the_reader_reports_what_the_schema_pass_reports(
    version: str, hint_part: str
) -> None:
    document = coffee()
    document["format_version"] = version
    result = migrate(document)
    assert result.document is None
    assert not result.migrated
    issue = only(result.issues)
    assert issue == only(schema_pass(document))
    assert hint_part in issue.hint


@pytest.mark.parametrize(
    ("version", "message_end"),
    [
        ("v0.1", "which is not of the form MAJOR.MINOR, such as '0.3'."),
        ("0.4", "which this program cannot convert to format version 99.0."),
        ("1.0", "which this program cannot convert to format version 99.0."),
        ("99.1", "which this program cannot convert to format version 99.0."),
    ],
)
def test_migrate_to_another_version_reports_e101(
    version: str, message_end: str, test_migrations: None
) -> None:
    result = migrate({"format_version": version}, TEST_VERSION)
    assert result.document is None
    issue = only(result.issues)
    assert (issue.code, issue.path) == ("E101", "/format_version")
    assert issue.message == f"'format_version' is '{version}', {message_end}"


def test_migrate_refuses_a_target_that_is_not_a_version() -> None:
    with pytest.raises(ValueError, match="not a format version"):
        migrate(coffee(), "1")


def test_migrate_refuses_a_migration_that_writes_the_wrong_major() -> None:
    def wrong(document: dict[str, Any]) -> dict[str, Any]:
        document["format_version"] = "5.0"
        return document

    registry = MigrationRegistry()
    registry.register(1, 0, wrong)
    with pytest.raises(ValueError, match=r"wrote format_version '5\.0'"):
        migrate({"format_version": "1.0"}, registry=registry)


@pytest.mark.parametrize("written", [None, 0.1, "0.01"])
def test_migrate_refuses_a_migration_that_writes_no_version(written: object) -> None:
    def wrong(document: dict[str, Any]) -> dict[str, Any]:
        document["format_version"] = written
        return document

    registry = MigrationRegistry()
    registry.register(1, 0, wrong)
    with pytest.raises(ValueError, match="wrote format_version"):
        migrate({"format_version": "1.0"}, registry=registry)


def test_migrate_refuses_a_migration_that_writes_a_minor_above_the_target() -> None:
    def too_new(document: dict[str, Any]) -> dict[str, Any]:
        document["format_version"] = "0.4"
        return document

    registry = MigrationRegistry()
    registry.register(1, 0, too_new)
    with pytest.raises(ValueError, match=r"wrote format_version '0\.4'"):
        migrate({"format_version": "1.0"}, registry=registry)


def test_migrate_copies_deeply_nested_files_without_recursion() -> None:
    # The loader opens a `ui` nested 20,000 levels deep; migrate must copy it too.
    deep: Any = {}
    for _ in range(20_000):
        deep = {"ui": deep}
    document = coffee()
    document["components"][0]["ui"] = deep
    result = migrate(document)
    assert result.document is not None
    inner = result.document["components"][0]["ui"]
    for _ in range(20_000):
        assert inner is not deep
        inner, deep = inner["ui"], deep["ui"]
    assert inner == {}


def test_module_lists_its_public_names() -> None:
    assert set(migration_module.__all__) == {
        "FORMAT_VERSION",
        "MIGRATIONS",
        "Migration",
        "MigrationRegistry",
        "MigrationResult",
        "can_open",
        "migrate",
        "parse_version",
        "version_issue",
    }


# --- the 0.2 and 0.3 minors (AKS-123, #77) ---------------------------------------------------

OLDER_MINOR_FILES = sorted(
    [*(ROOT / "examples").glob("*.json"), *(ROOT / "benchmarks").glob("*/model.json")]
)


def test_the_reader_is_0_3_and_its_minor_changes_need_no_migration() -> None:
    """Spec 1 "Versioning": a minor increase is additive, so format 0.2 (the indexed
    optimization keys) and 0.3 (rate units, #77) register no migration."""
    assert FORMAT_VERSION == "0.3"
    assert MIGRATIONS.pairs() == ()


@pytest.mark.parametrize(
    "path", OLDER_MINOR_FILES, ids=[f"{path.parent.name}/{path.name}" for path in OLDER_MINOR_FILES]
)
def test_the_0_1_examples_and_benchmarks_still_open_under_the_0_3_reader(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    if path.parent.name == "transport":
        assert document["format_version"] == "0.2"
    else:
        assert document["format_version"] == "0.1"
    result = load_document(document)
    assert result.model is not None, [issue.as_dict() for issue in result.issues]
    assert result.model.format_version == document["format_version"]
