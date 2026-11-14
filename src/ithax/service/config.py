"""The service's configuration, its folders and its token (spec 3 "Service rules").

``ServiceConfig`` holds everything a service instance needs, so that tests make one with
temporary folders and a fixed port and token. ``new_token`` draws the bearer token;
``default_config_dir`` and ``default_data_dir`` name the per-user folders on each
platform (spec 3 "Discovery", AKS-110, owner to confirm).
"""

from __future__ import annotations

import base64
import os
import secrets
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from ithax.engines.adapter import EngineAdapter
from ithax.service.hardware import Hardware
from ithax.service.idle_settings import DEFAULT_IDLE_MINUTES
from ithax.service.paths import canonical

__all__ = [
    "APP_FOLDER",
    "DEFAULT_IDLE_TIMEOUT_S",
    "LEGACY_APP_FOLDER",
    "TOKEN_BYTES",
    "WEBSOCKET_AUTH_TIMEOUT_S",
    "ServiceConfig",
    "default_config_dir",
    "default_data_dir",
    "default_templates_dir",
    "default_ui_dir",
    "installed_share_dir",
    "new_token",
]

#: The folder name under the platform's configuration and data folders (owner decision C8).
APP_FOLDER = "ithax"
#: The folder name before the product was named (#70). A folder of that name is used, for
#: one release, when the ``ithax`` folder does not exist, so projects and settings made
#: before the rename are still found; the ``ithax`` folder wins once it exists.
LEGACY_APP_FOLDER = "lcsim"

#: Spec 3 "Lifetime": exit after 30 idle minutes unless ``idle_timeout_minutes`` in
#: ``settings.json`` or ``--idle-minutes`` says otherwise (owner decision B5, AKS-141).
DEFAULT_IDLE_TIMEOUT_S = DEFAULT_IDLE_MINUTES * 60.0

#: Spec 3 "Token": the first WebSocket message must arrive within 5 seconds.
WEBSOCKET_AUTH_TIMEOUT_S = 5.0

#: Spec 3 "Token": 32 random bytes.
TOKEN_BYTES = 32


def new_token() -> str:
    """A new bearer token: 32 bytes from the operating system's generator, base64url
    without padding (43 characters).

    A secret, not simulation randomness, so the spec 1 stream scheme does not apply.
    """
    return base64.urlsafe_b64encode(secrets.token_bytes(TOKEN_BYTES)).rstrip(b"=").decode("ascii")


def _platform_folder(
    env: Mapping[str, str],
    platform: str,
    home: Path,
    *,
    windows_variable: str,
    windows_default: str,
    xdg_variable: str,
    xdg_default: str,
) -> Path:
    if platform == "win32":
        base = env.get(windows_variable)
        root = Path(base) if base else home / windows_default
    elif platform == "darwin":
        root = home / "Library" / "Application Support"
    else:
        base = env.get(xdg_variable)
        # The XDG specification ignores a relative path.
        root = Path(base) if base and Path(base).is_absolute() else home / xdg_default
    folder, legacy = root / APP_FOLDER, root / LEGACY_APP_FOLDER
    return legacy if not folder.exists() and legacy.is_dir() else folder


def default_config_dir(
    env: Mapping[str, str] | None = None,
    platform: str | None = None,
    home: Path | None = None,
) -> Path:
    """The per-user configuration folder: ``%APPDATA%\\ithax`` on Windows,
    ``~/Library/Application Support/ithax`` on macOS, ``$XDG_CONFIG_HOME/ithax``
    (default ``~/.config/ithax``) elsewhere.

    The arguments default to the running process's environment, platform and home folder.
    """
    return _platform_folder(
        os.environ if env is None else env,
        sys.platform if platform is None else platform,
        Path.home() if home is None else home,
        windows_variable="APPDATA",
        windows_default="AppData/Roaming",
        xdg_variable="XDG_CONFIG_HOME",
        xdg_default=".config",
    )


def default_data_dir(
    env: Mapping[str, str] | None = None,
    platform: str | None = None,
    home: Path | None = None,
) -> Path:
    """The per-user data folder, which holds ``projects/``: ``%LOCALAPPDATA%\\ithax`` on
    Windows, ``~/Library/Application Support/ithax`` on macOS, ``$XDG_DATA_HOME/ithax``
    (default ``~/.local/share/ithax``) elsewhere."""
    return _platform_folder(
        os.environ if env is None else env,
        sys.platform if platform is None else platform,
        Path.home() if home is None else home,
        windows_variable="LOCALAPPDATA",
        windows_default="AppData/Local",
        xdg_variable="XDG_DATA_HOME",
        xdg_default=".local/share",
    )


#: The source checkout holding ``src/ithax``: the folder three levels above this file.
_CHECKOUT = Path(__file__).resolve().parents[3]


def installed_share_dir(prefix: str | None = None) -> Path:
    """Where the Linux package puts the interface and the templates: ``share/ithax`` under
    the Python installation's prefix, ``sys.prefix`` by default (spec 3 "Packaging", M11,
    AKS-127, owner to confirm)."""
    return Path(sys.prefix if prefix is None else prefix) / "share" / APP_FOLDER


def _first_folder(*candidates: Path) -> Path:
    """The first of ``candidates`` that is a folder, else the first one."""
    return next((candidate for candidate in candidates if candidate.is_dir()), candidates[0])


def default_ui_dir(checkout: Path | None = None, prefix: str | None = None) -> Path:
    """The built interface the service serves by default: ``ui/dist`` of the source
    checkout, which a checkout has once the interface is built (``npm run build`` in
    ``ui/``), or else ``share/ithax/ui`` under the Python prefix, where the Linux package
    puts it (``installed_share_dir``). When neither exists, the checkout's folder is named
    and ``/v1/ui/`` is 404 (AKS-119, AKS-127, owner to confirm).

    ``checkout`` and ``prefix`` default to this checkout and ``sys.prefix``."""
    root = _CHECKOUT if checkout is None else checkout
    return _first_folder(root / "ui" / "dist", installed_share_dir(prefix) / "ui")


def default_templates_dir(checkout: Path | None = None, prefix: str | None = None) -> Path:
    """The template packages the service serves by default: ``templates`` of the source
    checkout, or else ``share/ithax/templates`` under the Python prefix, where the Linux
    package puts them; when neither exists, the checkout's folder is named and no template
    is served (AKS-122, AKS-127, owner to confirm). The arguments are as for
    ``default_ui_dir``."""
    root = _CHECKOUT if checkout is None else checkout
    return _first_folder(root / "templates", installed_share_dir(prefix) / "templates")


@dataclass(frozen=True)
class ServiceConfig:
    """What one service instance needs; ``config_dir`` and ``data_dir`` are made
    canonical (``ithax.service.paths``).

    ``port`` is the port the service listens on, for the ``Host`` check; ``token`` the
    bearer token. ``ui_dir`` is the built interface served at ``/v1/ui/`` (``None``: none).
    ``templates_dir`` holds the template packages served at ``/v1/templates`` (``None``:
    none; AKS-122).
    ``allowed_origins`` are WebSocket ``Origin`` values let through besides the
    interface's own, ``http://127.0.0.1:<port>`` and ``http://localhost:<port>`` (AKS-119;
    the desktop shell's is added at M11). ``idle_timeout_s`` is the lifetime's
    idle limit and ``idle_check_s`` how often it is checked; ``on_idle`` is called once
    when it is reached (``None``: never checked). ``hardware`` is detected when ``None``;
    ``adapters`` are the installed adapters when ``None``. ``clock`` measures idle time.
    """

    config_dir: Path
    data_dir: Path
    port: int
    token: str
    ui_dir: Path | None = None
    templates_dir: Path | None = None
    allowed_origins: frozenset[str] = frozenset()
    idle_timeout_s: float = DEFAULT_IDLE_TIMEOUT_S
    idle_check_s: float = 10.0
    on_idle: Callable[[], None] | None = None
    websocket_auth_timeout_s: float = WEBSOCKET_AUTH_TIMEOUT_S
    hardware: Hardware | None = None
    adapters: Mapping[str, EngineAdapter] | None = None
    clock: Callable[[], float] = field(default=time.monotonic)

    def __post_init__(self) -> None:
        # Absolute, so that paths stored in projects.json do not depend on the working
        # directory (review of PR #34).
        object.__setattr__(self, "config_dir", canonical(self.config_dir))
        object.__setattr__(self, "data_dir", canonical(self.data_dir))
        if self.ui_dir is not None:
            object.__setattr__(self, "ui_dir", canonical(self.ui_dir))
        if self.templates_dir is not None:
            object.__setattr__(self, "templates_dir", canonical(self.templates_dir))
        if not 0 < self.port < 65536:
            raise ValueError(f"port {self.port!r} is not from 1 to 65535")
        if not self.token:
            raise ValueError("the service needs a token")
