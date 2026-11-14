"""``GET /v1/ui/{path}``: the interface's own files (spec 3 "Endpoints" and "Service rules";
AKS-119, owner to confirm).

The service serves the built interface (``npm run build`` in ``ui/``) from the folder its
configuration names (``ServiceConfig.ui_dir``, ``python -m ithax.service --ui-dir``), so the
page's origin is the service's own and its requests and WebSockets need no CORS. These
files hold no data and need no token (``ithax.service.auth``); the ``Host`` check applies.

``/v1/ui/`` and a path ending in ``/`` give that folder's ``index.html``. A path is taken as
``/``-separated names: an empty name, ``.``, ``..``, a ``\\``, a ``:`` or a control
character, or a file that resolves outside the folder (through a link), is refused as not
found, as is a missing folder or file (404, E185).

Every response carries a ``Content-Security-Policy`` that lets the page load scripts,
styles, fonts and images only from the service and connect only to it, so nothing is
fetched from the network at run time (spec 0 principle 6), with ``Cache-Control:
no-cache``, ``X-Content-Type-Options: nosniff`` and ``Referrer-Policy: no-referrer``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from starlette.responses import FileResponse

from ithax.service.errors import NOT_FOUND, ServiceError
from ithax.service.state import ServiceState, service_state

__all__ = ["INDEX", "content_security_policy", "interface_path", "media_type", "router"]

router = APIRouter(prefix="/v1/ui")

#: The file a folder path gives.
INDEX = "index.html"

# A name holding one of these could name a place outside the folder on some platform: a
# Windows separator, a drive (``c:``) or an alternate stream (``a:b``), a control character.
_REFUSED = re.compile(r"[\\:\x00-\x1f\x7f]")

#: Media types by suffix, fixed here rather than read from the platform's tables (which on
#: Windows come from the registry and may name JavaScript ``text/plain``).
_MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".map": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
}


def media_type(path: Path) -> str:
    """The media type of an interface file, by its suffix in any letter case."""
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def content_security_policy(port: int) -> str:
    """The policy of every interface file: the page reaches only the service at ``port``."""
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            # React sets style attributes, and the theme is one inline style element.
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "font-src 'self'",
            f"connect-src 'self' ws://127.0.0.1:{port} ws://localhost:{port}",
            "object-src 'none'",
            "base-uri 'none'",
            "form-action 'none'",
            "frame-ancestors 'none'",
        ]
    )


def interface_path(ui_dir: Path, path: str) -> Path | None:
    """The file ``path`` names inside ``ui_dir``, resolved, or ``None`` when it names
    nothing there: a refused name, a missing file, or one that resolves outside."""
    names = path.split("/")
    if names[-1] == "":
        names[-1] = INDEX
    if any(name in ("", ".", "..") or _REFUSED.search(name) for name in names):
        return None
    try:
        root = ui_dir.resolve(strict=True)
        resolved = ui_dir.joinpath(*names).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not resolved.is_relative_to(root) or not resolved.is_file():
        return None
    return resolved


# HEAD is listed: FastAPI, unlike Starlette, does not add it to a GET route.
@router.api_route("/{path:path}", methods=["GET", "HEAD"])
def get_interface_file(
    path: str, state: Annotated[ServiceState, Depends(service_state)]
) -> FileResponse:
    """A file of the built interface."""
    ui_dir = state.config.ui_dir
    if ui_dir is None:
        raise ServiceError(404, NOT_FOUND, "This service was started without the interface.")
    found = interface_path(ui_dir, path)
    if found is None:
        raise ServiceError(404, NOT_FOUND, f"The interface has no file '{path}'.")
    return FileResponse(
        found,
        media_type=media_type(found),
        headers={
            "Content-Security-Policy": content_security_policy(state.config.port),
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )
