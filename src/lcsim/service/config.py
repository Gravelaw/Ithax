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

from lcsim.engines.adapter import EngineAdapter
from lcsim.service.hardware import Hardware
from lcsim.service.idle_settings import DEFAULT_IDLE_MINUTES
from lcsim.service.paths import canonical

__all__ = [
    "APP_FOLDER",
    "DEFAULT_IDLE_TIMEOUT_S",
    "TOKEN_BYTES",
    "WEBSOCKET_AUTH_TIMEOUT_S",
    "ServiceConfig",
    "default_config_dir",
    "default_data_dir",
    "default_templates_dir",
    "default_ui_dir",
    "new_token",
]

#: The folder name under the platform's configuration and data folders; renamed with the
#: placeholder package.
APP_FOLDER = "lcsim"

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
    return root / APP_FOLDER


def default_config_dir(
    env: Mapping[str, str] | None = None,
    platform: str | None = None,
    home: Path | None = None,
) -> Path:
    """The per-user configuration folder: ``%APPDATA%\\lcsim`` on Windows,
    ``~/Library/Application Support/lcsim`` on macOS, ``$XDG_CONFIG_HOME/lcsim``
    (default ``~/.config/lcsim``) elsewhere.

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
    """The per-user data folder, which holds ``projects/``: ``%LOCALAPPDATA%\\lcsim`` on
    Windows, ``~/Library/Application Support/lcsim`` on macOS, ``$XDG_DATA_HOME/lcsim``
    (default ``~/.local/share/lcsim``) elsewhere."""
    return _platform_folder(
        os.environ if env is None else env,
        sys.platform if platform is None else platform,
        Path.home() if home is None else home,
        windows_variable="LOCALAPPDATA",
        windows_default="AppData/Local",
        xdg_variable="XDG_DATA_HOME",
        xdg_default=".local/share",
    )


def default_ui_dir() -> Path:
    """The built interface the service serves by default: ``ui/dist`` beside the package's
    source folder, which a source checkout has once the interface is built (``npm run
    build`` in ``ui/``). An installed package has no such folder, so its ``/v1/ui/`` is 404
    until packaging (M11) names the installed one (AKS-119, owner to confirm)."""
    return Path(__file__).resolve().parents[3] / "ui" / "dist"


def default_templates_dir() -> Path:
    """The template packages the service serves by default: ``templates`` beside the
    package's source folder, which a source checkout has. An installed package has no such
    folder, so it serves no template until packaging (M11) names the installed one, as for
    ``default_ui_dir`` (AKS-122, owner to confirm)."""
    return Path(__file__).resolve().parents[3] / "templates"


@dataclass(frozen=True)
class ServiceConfig:
    """What one service instance needs; ``config_dir`` and ``data_dir`` are made
    canonical (``lcsim.service.paths``).

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
