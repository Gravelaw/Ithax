"""The data endpoints (spec 3 "Endpoints", the data rows and notes; AKS-113):

- ``POST /v1/projects/{pid}/data``: ``multipart/form-data`` with the part ``file`` (the
  file; its file name is its name in ``data/``) and optionally ``units`` (a JSON object of
  column names and Phase 1 time units or ``null``); the file as listed, with ``preview``;
- ``GET /v1/projects/{pid}/data``: the imported files and their columns;
- ``DELETE /v1/projects/{pid}/data/{file}``: removes the file and its index entry; the
  files that remain;
- ``POST /v1/projects/{pid}/data/{file}/fit``: ``{column}``; the candidate distributions.

The work is ``ithax.service.data_store``'s; this module is the HTTP side, including the
upload's limits: the request may be at most ``MAX_REQUEST_BYTES``, refused from its
``Content-Length`` or as soon as more is read (E189), before Starlette's multipart parser
(``python-multipart``) spools it, and the form may hold only the two parts (E184).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from ithax.model import data_files
from ithax.model.issues import Issue, pointer
from ithax.service.data_store import UNUSABLE, parse_units
from ithax.service.errors import MALFORMED, ServiceError, malformed
from ithax.service.state import ServiceState, service_state

__all__ = ["MAX_FORM_BYTES", "MAX_REQUEST_BYTES", "FitRequest", "router"]

router = APIRouter(prefix="/v1/projects")

State = Annotated[ServiceState, Depends(service_state)]

#: What the form may add to the file: its boundaries, headers and the ``units`` part.
MAX_FORM_BYTES = 64 * 2**10
#: The largest upload request (spec 3: 64 MiB plus 64 KiB for the form).
MAX_REQUEST_BYTES = data_files.MAX_FILE_BYTES + MAX_FORM_BYTES

_PARTS = ("file", "units")


def _bad(path: str, message: str, hint: str) -> ServiceError:
    return malformed([Issue(code=MALFORMED, component=None, path=path, message=message, hint=hint)])


def _too_large() -> ServiceError:
    message = "The upload is larger than 64 MiB, the most a data file may be."
    hint = "Import a smaller file, such as only the rows and columns the model needs."
    issue = Issue(code=UNUSABLE, component=None, path="/file", message=message, hint=hint)
    return ServiceError(400, UNUSABLE, message, [issue])


def _not_a_form() -> ServiceError:
    return _bad(
        "",
        "The request is not a multipart form holding one file.",
        "Send multipart/form-data with the file in the part 'file', and optionally 'units'.",
    )


async def _capped(request: Request) -> AsyncGenerator[bytes, None]:
    """The request body, refused as soon as it is larger than ``MAX_REQUEST_BYTES``."""
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > MAX_REQUEST_BYTES:
            raise _too_large()
        yield chunk


@router.post("/{pid}/data")
async def import_data(pid: str, request: Request, state: State) -> dict[str, Any]:
    """Import an uploaded CSV or Excel file."""
    await run_in_threadpool(state.data.check_project, pid)
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("multipart/form-data"):
        raise _not_a_form()
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_REQUEST_BYTES:
        raise _too_large()
    parser = MultiPartParser(
        request.headers, _capped(request), max_files=1, max_fields=1, max_part_size=MAX_FORM_BYTES
    )
    try:
        form = await parser.parse()
    except MultiPartException:
        raise _not_a_form() from None
    try:
        upload: UploadFile | None = None
        units: str | None = None
        for key, value in form.multi_items():
            if key == "file" and isinstance(value, UploadFile):
                upload = value
            elif key == "units" and isinstance(value, str):
                units = value
            elif key in _PARTS:
                raise _bad(
                    pointer(key),
                    f"The part '{key}' is not " + ("a file." if key == "file" else "text."),
                    "Send the file in the part 'file' and the units as text in 'units'.",
                )
            else:
                raise _bad(
                    pointer(key),
                    f"The form part '{key}' is not one this request takes.",
                    "Send only the parts 'file' and 'units'.",
                )
        if upload is None:
            raise _bad(
                "/file",
                "The form has no part 'file' holding the file.",
                "Send the file in the part 'file'.",
            )
        raw = await upload.read()
        declared = parse_units(units)
        name = upload.filename or ""
        return await run_in_threadpool(state.data.upload, pid, name, raw, declared)
    finally:
        await form.close()


@router.get("/{pid}/data")
def list_data(pid: str, state: State) -> list[dict[str, Any]]:
    """The imported files and their columns."""
    return state.data.files(pid)


@router.delete("/{pid}/data/{file}")
def delete_data(pid: str, file: str, state: State) -> list[dict[str, Any]]:
    """Remove an imported file and its index entry."""
    return state.data.delete(pid, file)


def _unicode(value: str) -> str:
    """``value`` when it is valid Unicode; a lone surrogate is refused (E184)."""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("not valid Unicode") from None
    return value


class FitRequest(BaseModel):
    """The body of ``POST .../data/{file}/fit``."""

    model_config = ConfigDict(extra="forbid", strict=True)

    column: str

    _writable = field_validator("column")(lambda value: _unicode(value))


@router.post("/{pid}/data/{file}/fit")
def fit_data(pid: str, file: str, body: FitRequest, state: State) -> dict[str, Any]:
    """Fit the spec 1 distributions to a column."""
    return state.data.fit(pid, file, body.column)
