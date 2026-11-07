"""Reading, writing, editing and validating a project's model (spec 3 "Revision",
"Endpoints", "Model edits"; AKS-111).

``ModelStore`` is what the model routes call. Every write (a whole model, or a batch of
edits) of one project is made under that project's lock, so two writes that state the
same ``base_revision`` cannot both pass the check. A write saves ``project.json`` with the
new ``model_revision`` first and ``model.json`` second, each through a temporary file and
a rename; a failure between the two leaves a revision that has moved over an unchanged
model, which a client sees as a 409 and reloads, never a changed model under an old
revision. After a write the store tells the project's listeners
(``ProjectEvents.model_written``).

A refused write changes nothing: 400 with E184 (malformed), E180 (an edit that cannot be
applied), E100 or E101 (a ``PUT`` body that fails the schema pass) or E186 (a project
folder or ``model.json`` that cannot be used), or 409 with E181 (a stale
``base_revision``). The store never puts exception text in a message (guide
"Conventions", Errors).
"""

from __future__ import annotations

import json
import logging
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
from lcsim.model.edits import apply_edits, check_edits, first_non_finite
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
    json_text,
    read_project,
    write_text,
)

__all__ = [
    "CONFLICT",
    "EDIT_REJECTED",
    "ModelStore",
    "Written",
    "base_revision",
    "no_data",
    "non_finite_issue",
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


def non_finite_issue(document: object) -> Issue | None:
    """An E100 issue at the first number in ``document`` that JSON cannot hold (``NaN``,
    ``Infinity``, or a number such as ``1e400`` that reads as an infinity), or ``None``.
    Such a file cannot be read unambiguously, so spec 1 makes it a schema-pass issue, and
    it could not be written back or sent."""
    place = first_non_finite(document)
    if place is None:
        return None
    return Issue(
        code="E100",
        component=None,
        path=place,
        message=f"The number at '{place}' is too large to be stored, or is not a number.",
        hint="Write a number a 64-bit float can hold, below about 1.8e308.",
    )


def _folder_error(message: str, issues: Sequence[Issue] = ()) -> ServiceError:
    return ServiceError(400, PROJECT_FOLDER, message, issues)


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

    @classmethod
    def _model(cls, folder: Path) -> object:
        raw = cls._raw(folder)
        try:
            document = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise _folder_error(
                f"The {MODEL_FILE} in '{folder}' is not a JSON model file; write a whole "
                "model to replace it.",
                load_text(raw).issues,
            ) from None
        issue = non_finite_issue(document)
        if issue is not None:
            raise _folder_error(
                f"The {MODEL_FILE} in '{folder}' holds a number JSON cannot hold; write a "
                "whole model to replace it.",
                [issue],
            )
        return document

    def read(self, pid: str) -> dict[str, Any]:
        """``{model, revision}`` of project ``pid``."""
        with self._locked(pid):
            folder, record = self._record(pid)
            return {"model": self._model(folder), "revision": record.model_revision}

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
        """``{revision, issues}`` of the saved model: the schema pass, the meaning pass,
        then the adapter's ``validate`` when the first two find no error."""
        with self._locked(pid):
            folder, record = self._record(pid)
            raw = self._raw(folder)
        result = self._load(folder, raw)
        issues = list(result.issues)
        if not issues:
            # Loading reads `1e400` as an infinity, which a setting may not check (a
            # component's `ui`): such a file cannot be served or written back.
            unstorable = non_finite_issue(json.loads(raw.decode("utf-8-sig")))
            if unstorable is not None:
                return {"revision": record.model_revision, "issues": [unstorable.as_dict()]}
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
            extra={"model": self._model(folder), "revision": record.model_revision},
        )

    def _save(
        self, pid: str, folder: Path, record: ProjectRecord, model: object, client: str
    ) -> int:
        revision = record.model_revision + 1
        # Both files are made into text before either is written, so a value JSON cannot
        # hold (refused on every way in) could never move the revision without the model.
        project_text = json_text(asdict(replace(record, model_revision=revision)))
        model_text = json_text(model)
        try:
            write_text(folder / PROJECT_FILE, project_text)
            write_text(folder / MODEL_FILE, model_text)
        except OSError:
            _log.warning("Writing the model of %s failed.", folder, exc_info=True)
            raise _folder_error(
                f"The project folder '{folder}' cannot be written, so the model was not saved."
            ) from None
        self.events.model_written(pid, revision, client)
        return revision

    def put(self, pid: str, body: bytes, base_revision: int | None, client: str) -> Written:
        """Save the model file ``body`` when it passes the schema pass."""
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
        model = json.loads(body.decode("utf-8-sig"))
        unstorable = non_finite_issue(model)
        if unstorable is not None:
            raise ServiceError(
                400,
                "E100",
                "The model file does not pass the schema pass, so it was not saved.",
                [unstorable],
            )
        with self._locked(pid):
            folder, record = self._record(pid)
            self._check_revision(folder, record, base_revision)
            revision = self._save(pid, folder, record, model, client)
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
            current = self._model(folder)
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
            revision = self._save(pid, folder, record, outcome.model, client)
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
