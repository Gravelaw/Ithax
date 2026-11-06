"""Issue objects and the issue-code fixtures (spec 1 "Validation issues"; AKS-87).

The fixture test is the spec 1 acceptance row (M1): one deliberately broken file per issue
code with Pass ``schema`` or ``meaning``, in ``fixtures/issues/<code>_<slug>.json``, yields
that code as its only issue of that severity, with ``path`` filled and ``component`` filled
where the code concerns a component; every ``message`` names the component id or key
concerned and contains no exception text. Later M1 tickets add fixtures and passes here.
"""

import json
import re
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from lcsim.model.issues import CodedProblem, Issue, pointer
from lcsim.model.loading import load_document
from lcsim.model.units import Dimension, QuantityError, parse_quantity, read_number

FIXTURES = Path(__file__).parent / "fixtures" / "issues"
FIXTURE_FILES = sorted(FIXTURES.glob("*.json"))

# Text that only an exception or a validator's own message would contain.
EXCEPTION_TEXT = re.compile(
    r"Traceback|Exception|Error\b|is not of type|is a required property|"
    r"Additional properties|should not be valid|does not match|is not valid under"
)


def issues_for(document: Any) -> list[Issue]:
    """Every issue of ``document``: the schema pass, then loading (AKS-88).

    The meaning pass joins here (AKS-89 to AKS-91)."""
    return list(load_document(document).issues)


def segments(path: str) -> list[str]:
    return [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")[1:]]


# --- the issue-code fixtures -----------------------------------------------------------


def test_fixture_folder_holds_only_issue_fixtures() -> None:
    names = [path.name for path in FIXTURES.iterdir()]
    assert names, "no fixtures"
    for name in names:
        assert re.fullmatch(r"[EW][0-9]{3}_[a-z0-9_]+\.json", name), name


@pytest.mark.parametrize("fixture", FIXTURE_FILES, ids=[path.stem for path in FIXTURE_FILES])
def test_fixture_yields_its_code_as_the_only_issue_of_its_severity(fixture: Path) -> None:
    code = fixture.name.split("_", 1)[0]
    severity = "error" if code.startswith("E") else "warning"
    document = json.loads(fixture.read_text(encoding="utf-8"))

    issues = issues_for(document)
    same_severity = [issue for issue in issues if issue.severity == severity]

    assert same_severity, f"{fixture.name} yields no {severity}"
    assert {issue.code for issue in same_severity} == {code}, [i.as_dict() for i in issues]
    for issue in same_severity:
        assert issue.path, issue
        parts = segments(issue.path)
        keys = [part for part in parts if not part.isdigit()]
        assert f"'{keys[-1]}'" in issue.message, issue
        if parts[0] == "components" and len(parts) > 1:
            component = document["components"][int(parts[1])]
            assert issue.component == component["id"], issue
            assert f"'{component['id']}'" in issue.message, issue
        assert not EXCEPTION_TEXT.search(issue.message), issue
        assert not EXCEPTION_TEXT.search(issue.hint), issue
        assert issue.hint


# --- the issue object ------------------------------------------------------------------


def test_issue_as_dict_has_the_spec_1_keys_in_order() -> None:
    issue = Issue(
        code="E131",
        component="till",
        path="/components/1",
        message="The 'out' port of 'till' is not connected to anything.",
        hint="Connect it to another block or to a sink.",
    )
    assert issue.as_dict() == {
        "code": "E131",
        "severity": "error",
        "component": "till",
        "path": "/components/1",
        "message": "The 'out' port of 'till' is not connected to anything.",
        "hint": "Connect it to another block or to a sink.",
    }
    assert list(issue.as_dict()) == ["code", "severity", "component", "path", "message", "hint"]
    # The dict is JSON as spec 1 shows it.
    assert json.loads(json.dumps(issue.as_dict())) == issue.as_dict()


@pytest.mark.parametrize(("code", "severity"), [("E100", "error"), ("W201", "warning")])
def test_severity_follows_the_code(code: str, severity: str) -> None:
    issue = Issue(code=code, component=None, path="/x", message="m", hint="h")
    assert issue.severity == severity


def test_component_may_be_null() -> None:
    issue = Issue(code="E100", component=None, path="/notes", message="m", hint="h")
    assert issue.as_dict()["component"] is None


@pytest.mark.parametrize("code", ["E10", "X100", "e100", "E1000", "W20a", ""])
def test_code_must_be_a_spec_1_code(code: str) -> None:
    with pytest.raises(ValueError, match="code"):
        Issue(code=code, component=None, path="/x", message="m", hint="h")


@pytest.mark.parametrize("path", ["x", "components/1"])
def test_path_must_be_a_json_pointer(path: str) -> None:
    with pytest.raises(ValueError, match="path"):
        Issue(code="E100", component=None, path=path, message="m", hint="h")


def test_root_path_is_the_empty_pointer() -> None:
    assert Issue(code="E100", component=None, path="", message="m", hint="h").path == ""


@pytest.mark.parametrize(("message", "hint"), [("", "h"), ("m", "")])
def test_message_and_hint_must_not_be_empty(message: str, hint: str) -> None:
    with pytest.raises(ValueError, match="message and hint"):
        Issue(code="E100", component=None, path="/x", message=message, hint=hint)


def test_issue_is_frozen() -> None:
    issue = Issue(code="E100", component=None, path="/x", message="m", hint="h")
    with pytest.raises(FrozenInstanceError):
        issue.code = "E101"  # type: ignore[misc]


def test_issues_compare_by_value() -> None:
    first = Issue(code="E100", component="a", path="/x", message="m", hint="h")
    second = Issue(code="E100", component="a", path="/x", message="m", hint="h")
    assert first == second
    assert hash(first) == hash(second)


# --- the hand-off from the units layer (AKS-86) ------------------------------------------


def quantity_error(value: object, expected: Dimension) -> QuantityError:
    with pytest.raises(QuantityError) as caught:
        if expected is Dimension.DIMENSIONLESS:
            read_number(value)
        else:
            assert isinstance(value, str)
            parse_quantity(value, expected)
    return caught.value


@pytest.mark.parametrize(
    ("value", "expected", "code"),
    [
        ("5 m", Dimension.TIME, "E140"),
        ("2min", Dimension.TIME, "E141"),
        ("2 min", Dimension.DIMENSIONLESS, "E123"),
    ],
)
def test_a_units_error_becomes_an_issue(value: object, expected: Dimension, code: str) -> None:
    error = quantity_error(value, expected)
    problem: CodedProblem = error
    issue = Issue.from_problem(
        problem,
        where="the 'mean' setting of 'till'",
        path="/components/1/params/service/mean",
        component="till",
    )
    assert issue.code == code
    assert issue.severity == "error"
    assert issue.component == "till"
    assert issue.path == "/components/1/params/service/mean"
    assert issue.message == f"In the 'mean' setting of 'till', {error.message}"
    assert issue.hint == error.hint
    assert f"'{value}'" in issue.message


# --- JSON Pointers ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        ((), ""),
        (("components", 1), "/components/1"),
        (("parameters", "a/b"), "/parameters/a~1b"),
        (("parameters", "a~b"), "/parameters/a~0b"),
        (("parameters", "~/"), "/parameters/~0~1"),
        (("",), "/"),
    ],
)
def test_pointer_escapes_per_rfc_6901(parts: tuple[str | int, ...], expected: str) -> None:
    assert pointer(*parts) == expected
    assert segments(expected) == [str(part) for part in parts]
