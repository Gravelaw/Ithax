"""Validation issue objects (spec 1 "Validation issues").

Every problem the model layer reports to a user is one ``Issue``: a spec 1 code, its
severity, the component concerned (or ``None``), a JSON Pointer ``path``, and a
plain-language ``message`` and ``hint`` written by lcsim, never copied from an exception
(guide "Conventions", Errors).

The units layer raises errors that already carry ``code``, ``message`` and ``hint``
(``lcsim.model.units.QuantityError``). The pass that calls it knows where the value sits,
and turns such an error into an issue with ``Issue.from_problem``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

__all__ = ["CodedProblem", "Issue", "Severity", "pointer"]

Severity = Literal["error", "warning"]

# Spec 1: E codes are errors and W codes warnings, three digits each (E100 to E399,
# W200 to W210 in this version).
_CODE = re.compile(r"[EW][0-9]{3}")


class CodedProblem(Protocol):
    """A problem that knows its spec 1 code and how to say it, such as a ``QuantityError``."""

    @property
    def code(self) -> str: ...

    @property
    def message(self) -> str: ...

    @property
    def hint(self) -> str: ...


@dataclass(frozen=True)
class Issue:
    """One validation issue, as spec 1 "Validation issues" shows it.

    ``severity`` follows from ``code``: ``error`` for an E code, ``warning`` for a W code.
    ``path`` is a JSON Pointer (RFC 6901) into the model file; ``""`` is the whole file.
    """

    code: str
    component: str | None
    path: str
    message: str
    hint: str
    severity: Severity = field(init=False)

    def __post_init__(self) -> None:
        if _CODE.fullmatch(self.code) is None:
            raise ValueError(f"issue code {self.code!r} is not a spec 1 code such as E100")
        if self.path and not self.path.startswith("/"):
            raise ValueError(f"issue path {self.path!r} is not a JSON Pointer")
        if not self.message or not self.hint:
            raise ValueError("an issue needs a message and hint")
        severity: Severity = "error" if self.code.startswith("E") else "warning"
        object.__setattr__(self, "severity", severity)

    @classmethod
    def from_problem(
        cls, problem: CodedProblem, *, where: str, path: str, component: str | None
    ) -> Issue:
        """Turn a coded problem into an issue placed in the model file.

        ``where`` names the setting in plain language, such as
        ``"the 'mean' setting of 'till'"``; the message becomes
        ``"In <where>, <problem message>"`` and the hint is the problem's own.
        """
        return cls(
            code=problem.code,
            component=component,
            path=path,
            message=f"In {where}, {problem.message}",
            hint=problem.hint,
        )

    def as_dict(self) -> dict[str, str | None]:
        """The issue as the JSON object of spec 1, keys in spec order."""
        return {
            "code": self.code,
            "severity": self.severity,
            "component": self.component,
            "path": self.path,
            "message": self.message,
            "hint": self.hint,
        }


def pointer(*segments: str | int) -> str:
    """A JSON Pointer (RFC 6901) from object keys and array indexes.

    ``pointer("components", 1)`` is ``"/components/1"``; no segments give ``""``, the
    whole document. ``~`` and ``/`` in a key are escaped as ``~0`` and ``~1``.
    """
    return "".join("/" + str(segment).replace("~", "~0").replace("/", "~1") for segment in segments)
