"""``GET /v1/projects/{pid}/export``: the project folder as a zip file (spec 3 "Endpoints",
the export note, and "Project folder"; AKS-138).

The zip holds every regular file of the project folder at its path relative to the folder,
names joined by ``/``, except:

- the run index (``index.sqlite``) and the files kept beside it (its SQLite journal, a
  rebuild in progress, ``.index.sqlite.<pid>.partial``): a cache, rebuilt from ``runs/``
  when the project is opened;
- under ``runs/``, everything but the folders of runs that have ended: a run's folder is
  included when the project's run index lists it and the run endpoints show it ``done``,
  ``failed`` or ``cancelled``, so no file a run is still writing is read;
- a link (symbolic link, Windows junction), which is never followed, anything whose real
  path lies outside the folder, and a name that is not valid Unicode (zip names are
  UTF-8).

The zip is written to a temporary file while the project's write lock is held
(``ModelStore.locked``), so no model write or data import meets half an export, and is then
sent from that file in parts of ``CHUNK`` bytes, never held whole in memory. The project's
folder is found as every project route finds it: 404 with E185 for an unknown project, 400
with E186 for one whose ``project.json`` cannot be read.
"""

from __future__ import annotations

import logging
import os
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from lcsim.runs.index import INDEX_FILE, RUNS_FOLDER
from lcsim.runs.states import FINAL_STATES
from lcsim.service.paths import canonical
from lcsim.service.state import ServiceState, service_state

__all__ = ["CHUNK", "archive_project", "parts", "router"]

router = APIRouter(prefix="/v1/projects")

State = Annotated[ServiceState, Depends(service_state)]

#: The size of each part of the zip sent.
CHUNK = 1 << 16

_log = logging.getLogger(__name__)


def _is_link(path: Path) -> bool:
    """Whether ``path`` is a symbolic link or a Windows junction (never followed)."""
    is_junction = getattr(os.path, "isjunction", None)  # Python 3.12 and later
    return path.is_symlink() or (is_junction is not None and bool(is_junction(path)))


def _named(relative: Path) -> str | None:
    """The zip name of ``relative``: its parts joined by ``/``, or ``None`` when a part is
    not valid Unicode (a name read from the disk as ``surrogateescape``)."""
    name = "/".join(relative.parts)
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return name


def _index_file(name: str) -> bool:
    """Whether a top-level file belongs to the run index: ``index.sqlite``, its journal,
    or a rebuild in progress."""
    return name.removeprefix(".").startswith(INDEX_FILE)


def _files(folder: Path, root: Path, ended: set[str]) -> Iterator[tuple[Path, str]]:
    """The files of ``folder`` (inside ``root``, the project folder) to put in the zip,
    with their zip names, in a stable order."""
    for entry in sorted(folder.iterdir(), key=lambda path: path.name):
        relative = entry.relative_to(root)
        name = _named(relative)
        if name is None:
            _log.warning("Left out of the export: a name that is not valid Unicode.")
            continue
        if _is_link(entry) or not canonical(entry).is_relative_to(canonical(root)):
            continue
        top = len(relative.parts) == 1
        if entry.is_dir():
            if relative.parts[0] == RUNS_FOLDER and len(relative.parts) == 2:
                if entry.name not in ended:
                    continue
            yield from _files(entry, root, ended)
        elif entry.is_file():
            if top and _index_file(entry.name):
                continue
            if relative.parts[0] == RUNS_FOLDER and len(relative.parts) == 2:
                continue  # a file directly in runs/ is not a run
            yield entry, name


def archive_project(state: ServiceState, pid: str) -> IO[bytes]:
    """The zip of project ``pid``'s folder, in a temporary file positioned at its start;
    the caller closes it."""
    with state.models.locked(pid):
        root = state.models.project_folder(pid)
        ended = {run["run_id"] for run in state.runs.runs(pid) if run["state"] in FINAL_STATES}
        archive = tempfile.TemporaryFile()
        try:
            with zipfile.ZipFile(
                archive, "w", compression=zipfile.ZIP_DEFLATED, strict_timestamps=False
            ) as zipped:
                for path, name in _files(root, root, ended):
                    zipped.write(path, name)
        except BaseException:
            archive.close()
            raise
    archive.seek(0)
    return archive


def parts(archive: IO[bytes]) -> Iterator[bytes]:
    """``archive`` in parts of ``CHUNK`` bytes; closes it at the end."""
    with archive:
        while chunk := archive.read(CHUNK):
            yield chunk


@router.get("/{pid}/export", response_model=None)
def export_project(pid: str, state: State) -> StreamingResponse:
    """The project folder as a zip file."""
    archive = archive_project(state, pid)
    return StreamingResponse(
        parts(archive),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{pid}.zip"'},
    )
