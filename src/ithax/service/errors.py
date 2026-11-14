"""Error bodies and the service's issue codes (spec 3 "Status codes and errors").

Every error a client sees is ``{"error": {"code", "message"}, "issues": [...]}``, where
``code`` is a spec 1 code and ``issues`` are spec 1 issue objects. Messages are written
here, never copied from an exception (guide "Conventions", Errors). A route raises
``ServiceError``; FastAPI's request-validation errors, Starlette's 404 and 405 and any
unexpected exception are turned into the same body by ``install_error_handlers``.

The service codes (spec 1 "Validation issues", AKS-110, owner to confirm):

- E182: token missing or wrong (401);
- E183: refused by the hardening rules, ``Host`` or WebSocket ``Origin`` (403);
- E184: request malformed (400);
- E185: not found (404), or a method a path does not take (405);
- E186: a project folder that cannot be used (400);
- E187: the service failed while answering (500);
- E188: an action the run's current state does not allow (409; AKS-112).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from ithax.model.issues import Issue, pointer
from ithax.strict_json import json_text

__all__ = [
    "INTERNAL",
    "MALFORMED",
    "NOT_ALLOWED",
    "NOT_FOUND",
    "PROJECT_FOLDER",
    "REFUSED",
    "TOKEN",
    "AsciiJSONResponse",
    "ServiceError",
    "error_body",
    "error_response",
    "install_error_handlers",
    "malformed",
    "request_issues",
]

TOKEN = "E182"
REFUSED = "E183"
MALFORMED = "E184"
NOT_FOUND = "E185"
PROJECT_FOLDER = "E186"
INTERNAL = "E187"
NOT_ALLOWED = "E188"

_log = logging.getLogger(__name__)


class AsciiJSONResponse(JSONResponse):
    """A JSON response written with every character outside ASCII escaped, so no text a
    client sent (such as a lone surrogate, which strict UTF-8 cannot encode) can stop a
    body from being sent; JSON readers decode the escapes back."""

    def render(self, content: object) -> bytes:
        return json_text(content, ascii_only=True, compact=True).encode("ascii")


class ServiceError(Exception):
    """A request the service refuses: an HTTP ``status``, a spec 1 ``code``, a plain
    ``message``, any ``issues`` and any ``extra`` keys of the body. Raised by routes and
    turned into spec 3's body."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        issues: Sequence[Issue] = (),
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.issues = tuple(issues)
        # Keys added to the body beside "error" and "issues", such as the current "model"
        # and "revision" of a 409 with E181 (spec 3 "Revision").
        self.extra = dict(extra or {})


def error_body(code: str, message: str, issues: Iterable[Issue] = ()) -> dict[str, Any]:
    """Spec 3's error body."""
    return {
        "error": {"code": code, "message": message},
        "issues": [issue.as_dict() for issue in issues],
    }


def error_response(
    status: int,
    code: str,
    message: str,
    issues: Iterable[Issue] = (),
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """A JSON response holding spec 3's error body."""
    return AsciiJSONResponse(error_body(code, message, issues), status_code=status, headers=headers)


def _field(parts: Sequence[str | int]) -> str:
    """The name of the field ``parts`` lead to: its last key."""
    keys = [part for part in parts if isinstance(part, str)]
    return keys[-1] if keys else "body"


def _request_issue(error: Mapping[str, Any]) -> Issue:
    """One request-validation error as an E184 issue, its path into the request body."""
    location = list(error.get("loc", ()))
    if location and location[0] == "body":
        location = location[1:]
    kind = str(error.get("type", ""))
    if kind == "json_invalid":
        return Issue(
            code=MALFORMED,
            component=None,
            path="",
            message="The request body is not valid JSON.",
            hint="Send the request's fields as one JSON object.",
        )
    if not location:
        message = (
            "The request has no body."
            if kind == "missing"
            else "The request body is not a JSON object."
        )
        return Issue(
            code=MALFORMED,
            component=None,
            path="",
            message=message,
            hint="Send the request's fields as one JSON object.",
        )
    name = _field(location)
    path = pointer(*location)
    messages = {
        "missing": (
            f"The request field '{name}' is missing.",
            'Add it; spec 3 "Endpoints" lists the fields of each request.',
        ),
        "extra_forbidden": (
            f"The request field '{name}' is not one this request takes.",
            'Remove it; spec 3 "Endpoints" lists the fields of each request.',
        ),
        "string_too_short": (
            f"The request field '{name}' is empty.",
            "Give it at least one character.",
        ),
        "string_type": (
            f"The request field '{name}' must be text.",
            "Write it as a JSON string.",
        ),
        "literal_error": (
            f"The request field '{name}' must be one of "
            f"{error.get('ctx', {}).get('expected', 'the listed words')}.",
            "Use one of those words.",
        ),
    }
    message, hint = messages.get(
        kind,
        (
            f"The request field '{name}' has a value of the wrong kind.",
            'Spec 3 "Endpoints" says what each field takes.',
        ),
    )
    return Issue(code=MALFORMED, component=None, path=path, message=message, hint=hint)


def request_issues(errors: Iterable[Mapping[str, Any]]) -> list[Issue]:
    """FastAPI's request-validation errors as E184 issues, one per error, without
    repeats, in the order given."""
    issues: dict[Issue, None] = {}
    for error in errors:
        issues[_request_issue(error)] = None
    return list(issues)


def malformed(issues: Sequence[Issue]) -> ServiceError:
    """A 400 E184 error for ``issues``."""
    message = (
        issues[0].message
        if len(issues) == 1
        else f"The request has {len(issues)} problems; each is listed in 'issues'."
    )
    return ServiceError(400, MALFORMED, message, issues)


async def _service_error(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ServiceError)
    body = {**error_body(error.code, error.message, error.issues), **error.extra}
    return AsciiJSONResponse(body, status_code=error.status)


async def _validation_error(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    refused = malformed(request_issues(error.errors()))
    return error_response(refused.status, refused.code, refused.message, refused.issues)


async def _http_error(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, HTTPException)
    path = request.url.path
    if error.status_code == 404:
        message = f"The service has no '{path}'."
        code = NOT_FOUND
    elif error.status_code == 405:
        message = f"'{path}' does not take {request.method}."
        code = NOT_FOUND
    else:
        message = f"The request to '{path}' cannot be answered (HTTP {error.status_code})."
        code = MALFORMED if error.status_code < 500 else INTERNAL
    return error_response(error.status_code, code, message, headers=error.headers)


async def _unexpected_error(request: Request, error: Exception) -> JSONResponse:
    _log.error(
        "The service failed while answering %s %s.",
        request.method,
        request.url.path,
        exc_info=error,
    )
    return error_response(
        500,
        INTERNAL,
        "The service failed while answering; the details are in its log.",
    )


def install_error_handlers(app: FastAPI) -> None:
    """Make every error ``app`` returns spec 3's error body."""
    app.add_exception_handler(ServiceError, _service_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)
