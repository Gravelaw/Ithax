"""Reading, writing, editing and validating a project's model (spec 3 "Revision",
"Endpoints", "Model edits"; AKS-111, redesigned after the review of PR #35).

``ModelStore`` is what the model routes call. Two mechanisms hold every path:

- **Admission.** A model document is admitted only when it becomes the exact bytes the
  service writes (``encode_json``: JSON without NaN or infinities, in strict UTF-8).
  ``admit`` is the one gate, run on every path and whatever else loading reports: a
  ``model.json`` read from disk (``GET``, edits, the 409 body, an opened folder; E186), a
  ``PUT`` body (E100), the result of an edit batch (E180) and ``validate`` (its E100 is
  the only issue reported). An edit's own fields are checked as the request's shape first
  (E184, ``lcsim.model.edits.check_edits``).
- **Saving.** ``_commit`` makes both files' final bytes first, writes each to a temporary
  file in the project folder, then renames ``model.json`` into place and ``project.json``
  (the new revision) last: that last rename is the commit. A failure before it removes the
  temporary files, and a failure at it also puts the previous model back, so the revision,
  the model and the events are unchanged; the project's listeners are told only after the
  commit. Every write of one project holds that project's lock, so two writes that state
  the same ``base_revision`` cannot both pass the check.

A refused write changes nothing: 400 with E184 (malformed), E180 (an edit that cannot be
applied), E100 or E101 (a ``PUT`` body that fails the schema pass) or E186 (a project
folder or ``model.json`` that cannot be used), or 409 with E181 (a stale
``base_revision``). The store never puts exception text in a message (guide
"Conventions", Errors).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from lcsim.engines.adapter import EngineAdapter
from lcsim.engines.registry import installed_engines, select_adapter
from lcsim.model.catalogue import BlockType
from lcsim.model.data import EMPTY_DATA_INDEX, DataIndex
from lcsim.model.edits import apply_edits, check_edits, first_unstorable
from lcsim.model.issues import Issue
from lcsim.model.loading import LoadResult, load_document, load_text
from lcsim.model.schema import schema_pass
from lcsim.service.errors import MALFORMED, PROJECT_FOLDER, ServiceError, malformed
from lcsim.service.events import ProjectEvents
from lcsim.service.projects_store import (
    MODEL_FILE,
    PROJECT_FILE,
    ProjectRecord,
    ProjectRegistry,
    encode_json,
    read_project,
)
from lcsim.strict_json import MAX_WHOLE

__all__ = [
    "CONFLICT",
    "EDIT_REJECTED",
    "ModelStore",
    "Written",
    "admit",
    "base_revision",
    "no_data",
]

_log = logging.getLogger(__name__)

#: Spec 1: an edit that cannot be applied (400), and a model changed since the stated
#: revision (409).
EDIT_REJECTED = "E180"
CONFLICT = "E181"

_SCHEMA_CODES = ("E100", "E101")

# A revision as the query parameter writes it (at most 18 digits, so it fits 64 bits).
_WHOLE = re.compile(r"-?[0-9]{1,18}")


def no_data(_folder: Path) -> DataIndex:
    """The column index of a project with nothing imported; the import endpoint
    (AKS-113) gives the store the index of the project's ``data/`` folder instead."""
    return EMPTY_DATA_INDEX


def _no_seed() -> int:
    # Loading for issues only: a seed the file leaves out is never used, so none is drawn.
    return 0


@dataclass(frozen=True)
class Written:
    """A saved model, its new revision and the issues of loading it."""

    model: object
    revision: int
    issues: tuple[Issue, ...]

    def body(self) -> dict[str, Any]:
        """The response body ``{model, revision, issues}``."""
        return {
            "model": self.model,
            "revision": self.revision,
            "issues": [issue.as_dict() for issue in self.issues],
        }


def admit(document: object) -> bytes | Issue:
    """The admission gate: the bytes ``model.json`` would hold for ``document``, or an
    E100 issue at the first value that stops it from being written (a number JSON cannot
    hold, or text that is not valid Unicode). Such a file cannot be read unambiguously,
    so spec 1 makes it a schema-pass issue; the issue never quotes the value."""
    try:
        return encode_json(document)
    except ValueError:
        place = first_unstorable(document) or ""
        where = f"at '{place}'" if place else "in the model"
        return Issue(
            code="E100",
            component=None,
            path=place,
            message=f"The model cannot be stored: the value {where} is a number too large "
            "to store, or text that is not valid Unicode.",
            hint="Write numbers a 64-bit float can hold (below about 1.8e308) and text "
            "that is valid Unicode.",
        )


def _folder_error(message: str, issues: Sequence[Issue] = ()) -> ServiceError:
    return ServiceError(400, PROJECT_FOLDER, message, issues)


@dataclass(frozen=True)
class _Stored:
    """A ``model.json`` as read and admitted: its document and its bytes."""

    document: object
    data: bytes


class ModelStore:
    """The models of the registered projects.

    ``adapters`` are the installed adapters, for engine selection, the component types of
    ``add_component`` and the adapter's ``validate``; ``events`` are told of every write;
    ``data_index`` gives the column index of a project's ``data/`` folder.
    """

    def __init__(
        self,
        projects: ProjectRegistry,
        adapters: Mapping[str, EngineAdapter],
        events: ProjectEvents,
        data_index: Callable[[Path], DataIndex] = no_data,
    ) -> None:
        self.projects = projects
        self.adapters = adapters
        self.events = events
        self.data_index = data_index
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    # --- reading ---------------------------------------------------------------------

    @contextmanager
    def _locked(self, pid: str) -> Iterator[None]:
        with self._guard:
            lock = self._locks.setdefault(pid, threading.Lock())
        with lock:
            yield

    def _record(self, pid: str) -> tuple[Path, ProjectRecord]:
        folder = self.projects.folder(pid)
        record = read_project(folder)
        if record is None or record.id != pid:
            raise _folder_error(
                f"The project '{pid}' cannot be used: the {PROJECT_FILE} in '{folder}' is "
                "missing or cannot be read."
            )
        return folder, record

    @staticmethod
    def _raw(folder: Path) -> bytes:
        try:
            return (folder / MODEL_FILE).read_bytes()
        except OSError:
            raise _folder_error(
                f"The {MODEL_FILE} in '{folder}' is missing or cannot be read."
            ) from None

    @staticmethod
    def _parse(raw: bytes) -> object:
        """``raw`` as JSON; ``ValueError`` when it is not."""
        try:
            return json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ValueError("not JSON") from None

    @classmethod
    def _stored(cls, folder: Path) -> _Stored:
        """The admitted ``model.json`` of ``folder``; E186 when it cannot be used."""
        raw = cls._raw(folder)
        try:
            document = cls._parse(raw)
        except ValueError:
            raise _folder_error(
                f"The {MODEL_FILE} in '{folder}' is not a JSON model file; write a whole "
                "model to replace it.",
                load_text(raw).issues,
            ) from None
        admitted = admit(document)
        if isinstance(admitted, Issue):
            raise _folder_error(
                f"The {MODEL_FILE} in '{folder}' cannot be stored as it is; write a whole "
                "model to replace it.",
                [admitted],
            )
        return _Stored(document, raw)

    def read(self, pid: str) -> dict[str, Any]:
        """``{model, revision}`` of project ``pid``."""
        with self._locked(pid):
            folder, record = self._record(pid)
            return {"model": self._stored(folder).document, "revision": record.model_revision}

    def revision(self, pid: str) -> int:
        """The current revision of project ``pid``."""
        with self._locked(pid):
            return self._record(pid)[1].model_revision

    # --- validating ------------------------------------------------------------------

    def _load(self, folder: Path, text: bytes | None, document: object = None) -> LoadResult:
        engines = installed_engines(self.adapters)
        data = self.data_index(folder / "data")
        if text is not None:
            return load_text(text, seed_source=_no_seed, data=data, engines=engines)
        return load_document(document, seed_source=_no_seed, data=data, engines=engines)

    def validate(self, pid: str) -> dict[str, Any]:
        """``{revision, issues}`` of the saved model: when it is JSON, the admission gate
        first (its E100 alone when it fails), then the schema pass, the meaning pass and
        the adapter's ``validate`` when the first two find no error."""
        with self._locked(pid):
            folder, record = self._record(pid)
            raw = self._raw(folder)
        with contextlib.suppress(ValueError):
            admitted = admit(self._parse(raw))
            if isinstance(admitted, Issue):
                return {"revision": record.model_revision, "issues": [admitted.as_dict()]}
        result = self._load(folder, raw)
        issues = list(result.issues)
        if result.model is not None:
            selection = select_adapter(result.model.domain, result.model.run.engine, self.adapters)
            # A model that loads has passed engine selection (E102).
            assert selection.adapter is not None
            issues.extend(selection.adapter.validate(result.model))
        return {"revision": record.model_revision, "issues": [issue.as_dict() for issue in issues]}

    # --- writing ---------------------------------------------------------------------

    def _check_revision(self, folder: Path, record: ProjectRecord, base: int | None) -> None:
        if base is None or base == record.model_revision:
            return
        raise ServiceError(
            409,
            CONFLICT,
            f"The model has changed since revision {base}: it is now at revision "
            f"{record.model_revision}, so nothing was applied.",
            extra={"model": self._stored(folder).document, "revision": record.model_revision},
        )

    def _commit(
        self,
        pid: str,
        folder: Path,
        record: ProjectRecord,
        data: bytes,
        previous: bytes | None,
        client: str,
    ) -> int:
        """Save the admitted model bytes ``data`` as the next revision; ``previous`` is the
        ``model.json`` it replaces (``None`` when there was none), put back when the
        commit fails."""
        revision = record.model_revision + 1
        if revision > MAX_WHOLE:
            raise _folder_error(
                f"The project in '{folder}' is at the largest revision the {PROJECT_FILE} may "
                "hold, so the model was not saved."
            )
        # The record was read by the strict reader, so it can be written back (PR #36).
        project_data = encode_json(asdict(replace(record, model_revision=revision)))
        suffix = f".{os.getpid()}.{threading.get_ident()}.tmp"
        model_path, project_path = folder / MODEL_FILE, folder / PROJECT_FILE
        model_temp = folder / f".{MODEL_FILE}{suffix}"
        project_temp = folder / f".{PROJECT_FILE}{suffix}"
        unsaved = _folder_error(
            f"The project folder '{folder}' cannot be written, so the model was not saved."
        )
        try:
            try:
                model_temp.write_bytes(data)
                project_temp.write_bytes(project_data)
                os.replace(model_temp, model_path)
            except OSError:
                _log.warning("Writing the model of %s failed.", folder, exc_info=True)
                raise unsaved from None
            try:
                os.replace(project_temp, project_path)  # the commit
            except OSError:
                _log.warning("Committing the model of %s failed.", folder, exc_info=True)
                self._put_back(model_path, model_temp, previous)
                raise unsaved from None
        finally:
            for temporary in (model_temp, project_temp):
                with contextlib.suppress(OSError):
                    temporary.unlink()
        self.events.model_written(pid, revision, client)
        return revision

    @staticmethod
    def _put_back(model_path: Path, temporary: Path, previous: bytes | None) -> None:
        """Put the model a failed commit replaced back in place."""
        try:
            if previous is None:
                model_path.unlink()
                return
            temporary.write_bytes(previous)
            os.replace(temporary, model_path)
        except OSError:
            _log.error("The previous model of %s could not be put back.", model_path, exc_info=True)

    def put(self, pid: str, body: bytes, base_revision: int | None, client: str) -> Written:
        """Save the model file ``body`` when it passes the schema pass and is admitted."""
        folder = self.projects.folder(pid)
        loaded = self._load(folder, body)
        schema = [issue for issue in loaded.issues if issue.code in _SCHEMA_CODES]
        if schema:
            raise ServiceError(
                400,
                schema[0].code,
                "The model file does not pass the schema pass, so it was not saved.",
                schema,
            )
        model = self._parse(body)
        admitted = admit(model)
        if isinstance(admitted, Issue):
            raise ServiceError(
                400,
                admitted.code,
                "The model file does not pass the schema pass, so it was not saved.",
                [admitted],
            )
        with self._locked(pid):
            folder, record = self._record(pid)
            self._check_revision(folder, record, base_revision)
            try:
                previous: bytes | None = (folder / MODEL_FILE).read_bytes()
            except OSError:
                previous = None
            revision = self._commit(pid, folder, record, admitted, previous, client)
        return Written(model, revision, loaded.issues)

    def _component_types(self, domain: object) -> dict[str, BlockType]:
        """The component types the installed adapters offer for ``domain``; where two
        adapters declare one type, the first by name."""
        types: dict[str, BlockType] = {}
        for name in sorted(self.adapters):
            capabilities = self.adapters[name].capabilities()
            if domain in capabilities.domains:
                for type_name, block in capabilities.component_types.items():
                    types.setdefault(type_name, block)
        return types

    def edit(self, pid: str, edits: object, base_revision: int | None, client: str) -> Written:
        """Apply the batch ``edits`` and save the result."""
        shape = check_edits(edits)
        if shape:
            raise malformed([*shape])
        assert isinstance(edits, list)
        with self._locked(pid):
            folder, record = self._record(pid)
            self._check_revision(folder, record, base_revision)
            stored = self._stored(folder)
            current = stored.document
            schema = schema_pass(current)
            if schema:
                raise _folder_error(
                    f"The {MODEL_FILE} in '{folder}' does not pass the schema pass, so edits "
                    "cannot be applied to it; write a whole model to replace it.",
                    schema,
                )
            assert isinstance(current, dict)  # the schema requires an object
            outcome = apply_edits(current, edits, self._component_types(current["domain"]))
            if outcome.model is None:
                raise ServiceError(400, EDIT_REJECTED, outcome.issues[0].message, outcome.issues)
            admitted = admit(outcome.model)
            if isinstance(admitted, Issue):
                issue = Issue(
                    code=EDIT_REJECTED,
                    component=None,
                    path="/edits",
                    message="The edits would leave a model that cannot be stored: "
                    + admitted.message[0].lower()
                    + admitted.message[1:],
                    hint=admitted.hint,
                )
                raise ServiceError(400, EDIT_REJECTED, issue.message, [issue])
            revision = self._commit(pid, folder, record, admitted, stored.data, client)
        return Written(outcome.model, revision, self._load(folder, None, outcome.model).issues)


def base_revision(text: str | None) -> int | None:
    """The ``base_revision`` query parameter of ``PUT .../model``: a whole number, or
    ``None`` when absent; anything else is 400 with E184."""
    if text is None:
        return None
    if _WHOLE.fullmatch(text) is None:
        raise malformed(
            [
                Issue(
                    code=MALFORMED,
                    component=None,
                    path="",
                    message=f"The query parameter 'base_revision' is '{text}', which is not "
                    "a whole number.",
                    hint="Send the revision the model was read at, such as ?base_revision=3.",
                )
            ]
        )
    return int(text)
