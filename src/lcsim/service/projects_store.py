"""Project folders and the project registry (spec 3 "Project folder" and "Endpoints").

A project folder holds ``project.json`` ``{id, name, created, layout_version,
model_revision}``, ``model.json``, ``data/`` and ``runs/`` (``index.sqlite`` is made with
the first run, AKS-112). The service keeps ``projects.json`` in its configuration folder,
an object mapping each project id to its folder's absolute path, in the order the
projects were registered.

``ProjectRegistry`` creates, opens, lists and finds projects; it refuses with
``ServiceError`` (E184, E185, E186) and never with exception text. It is safe to call from
several threads (FastAPI runs plain routes in a thread pool).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from lcsim.model.migration import FORMAT_VERSION
from lcsim.service.errors import NOT_FOUND, PROJECT_FOLDER, ServiceError

__all__ = [
    "LAYOUT_VERSION",
    "MODEL_FILE",
    "PROJECTS_FILE",
    "PROJECT_FILE",
    "Domain",
    "ProjectRecord",
    "ProjectRegistry",
    "default_model",
    "encode_json",
    "read_project",
    "utc_now",
    "write_json",
]

_log = logging.getLogger(__name__)

Domain = Literal["process", "optimization"]

PROJECT_FILE = "project.json"
MODEL_FILE = "model.json"
PROJECTS_FILE = "projects.json"

#: The version of the project folder layout of spec 3 "Project folder".
LAYOUT_VERSION = 1

_FIELDS = ("id", "name", "created", "layout_version", "model_revision")


def utc_now() -> str:
    """The time now, ISO 8601 UTC to the millisecond, ending in ``Z``."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def default_model(name: str, domain: Domain) -> dict[str, Any]:
    """The model of a project created without a template (spec 3 "Endpoints" notes)."""
    model: dict[str, Any] = {"format_version": FORMAT_VERSION, "meta": {"name": name}}
    if domain == "process":
        model.update(
            {
                "domain": "process",
                "parameters": {},
                "components": [],
                "connections": [],
                "experiments": [
                    {"id": "base", "length": "8 h", "warmup": "0 s", "replications": 30}
                ],
            }
        )
    else:
        model.update(
            {
                "domain": "optimization",
                "variables": [],
                "objective": {"sense": "maximize", "linear": {}},
                "constraints": [],
            }
        )
    model["run"] = {"target": "local", "fidelity": "standard"}
    return model


@dataclass(frozen=True)
class ProjectRecord:
    """The content of ``project.json``."""

    id: str
    name: str
    created: str
    layout_version: int
    model_revision: int


def _is_uuid4(text: str) -> bool:
    try:
        parsed = uuid.UUID(text)
    except ValueError:
        return False
    return parsed.version == 4 and str(parsed) == text


def read_project(folder: Path) -> ProjectRecord | None:
    """The ``project.json`` of ``folder``, or ``None`` when it is missing, unreadable or
    does not hold the five fields with the right kinds (``id`` a UUID4 string)."""
    try:
        loaded = json.loads((folder / PROJECT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(loaded, dict) or not all(key in loaded for key in _FIELDS):
        return None
    texts = all(isinstance(loaded[key], str) for key in ("id", "name", "created"))
    whole = all(
        isinstance(loaded[key], int) and not isinstance(loaded[key], bool)
        for key in ("layout_version", "model_revision")
    )
    if not (texts and whole and _is_uuid4(loaded["id"])):
        return None
    return ProjectRecord(**{key: loaded[key] for key in _FIELDS})


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


def write_json(path: Path, value: object) -> None:
    """Write ``value`` as ``encode_json`` gives it, through a temporary file and a rename,
    so a reader never sees half a file. Nothing is written when ``value`` cannot be
    encoded (``ValueError``). The temporary file is named for the process and thread, and
    removed when the write fails; the ``OSError`` is raised."""
    data = encode_json(value)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    except OSError:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise


def _folder_error(message: str) -> ServiceError:
    return ServiceError(400, PROJECT_FOLDER, message)


class ProjectRegistry:
    """The projects the service knows, kept in ``projects.json`` in ``config_dir``;
    projects without a ``path`` are created under ``<data_dir>/projects/<id>/``."""

    def __init__(
        self,
        config_dir: Path,
        data_dir: Path,
        new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        # Absolute, so that the paths in projects.json do not depend on the working
        # directory (review of PR #34).
        self.config_dir = config_dir.absolute()
        self.data_dir = data_dir.absolute()
        self._new_id = new_id
        self._lock = threading.Lock()

    # --- projects.json --------------------------------------------------------------

    @property
    def _file(self) -> Path:
        return self.config_dir / PROJECTS_FILE

    def _load(self) -> dict[str, str]:
        try:
            loaded = json.loads(self._file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            loaded = None
        if isinstance(loaded, dict) and all(
            isinstance(key, str) and isinstance(value, str) for key, value in loaded.items()
        ):
            return loaded
        # Kept aside, not overwritten: the registrations may be recovered by hand.
        aside = self._file.with_name(PROJECTS_FILE + ".unreadable")
        with contextlib.suppress(OSError):
            os.replace(self._file, aside)
        _log.warning("%s cannot be read; it is kept as %s.", self._file, aside)
        return {}

    def _save(self, projects: dict[str, str]) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        write_json(self._file, projects)

    # --- reading --------------------------------------------------------------------

    @staticmethod
    def view(pid: str, folder: Path, record: ProjectRecord | None) -> dict[str, Any]:
        """A project as the API shows it; ``record`` ``None`` for one that cannot be
        read, which is ``available`` ``false``."""
        if record is None or record.id != pid:
            empty: dict[str, Any] = dict.fromkeys(_FIELDS)
            return {**empty, "id": pid, "path": str(folder), "available": False}
        return {**asdict(record), "path": str(folder), "available": True}

    def entries(self) -> list[dict[str, Any]]:
        """Every registered project, in the order registered."""
        with self._lock:
            projects = self._load()
        return [
            self.view(pid, Path(path), read_project(Path(path))) for pid, path in projects.items()
        ]

    def folder(self, pid: str) -> Path:
        """The folder of project ``pid``; 404 with E185 when no project has that id."""
        with self._lock:
            path = self._load().get(pid)
        if path is None:
            raise ServiceError(404, NOT_FOUND, f"There is no project '{pid}'.")
        return Path(path)

    # --- creating and opening ------------------------------------------------------

    def create(self, name: str, domain: Domain, path: Path | None) -> dict[str, Any]:
        """Create a project named ``name`` with the default model of ``domain`` in
        ``path`` (absolute; missing or empty) or under the data folder, and register it."""
        pid = self._new_id()
        folder = self.data_dir / "projects" / pid if path is None else path
        if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
            raise _folder_error(
                f"'{folder}' is not an empty folder, so a project cannot be created there."
            )
        record = ProjectRecord(pid, name, utc_now(), LAYOUT_VERSION, 0)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "data").mkdir()
            (folder / "runs").mkdir()
            write_json(folder / MODEL_FILE, default_model(name, domain))
            write_json(folder / PROJECT_FILE, asdict(record))
        except OSError:
            _log.warning("Creating the project folder %s failed.", folder, exc_info=True)
            raise _folder_error(f"The project folder '{folder}' cannot be written.") from None
        with self._lock:
            projects = self._load()
            projects[pid] = str(folder)
            self._save(projects)
        return self.view(pid, folder, record)

    def open(self, path: Path) -> dict[str, Any]:
        """Register the existing project folder ``path`` (absolute) and return it."""
        if not path.is_dir():
            raise ServiceError(404, NOT_FOUND, f"There is no folder '{path}'.")
        record = read_project(path)
        if record is None:
            raise _folder_error(
                f"'{path}' is not a project folder: its {PROJECT_FILE} is missing or "
                "does not hold id, name, created, layout_version and model_revision."
            )
        with self._lock:
            projects = self._load()
            known = projects.get(record.id)
            if known is not None and Path(known) != path:
                other = read_project(Path(known))
                if other is not None and other.id == record.id:
                    raise _folder_error(
                        f"The project in '{path}' has the same id as the one open in "
                        f"'{known}', so it is a copy; open it from one folder only."
                    )
            if known is None or Path(known) != path:
                projects[record.id] = str(path)
                self._save(projects)
        return self.view(record.id, path, record)
