"""The token and the per-user folders (spec 3 "Token" and "Discovery"; AKS-110)."""

import base64
import os
import re
import sys
from pathlib import Path

import pytest

from ithax.service.config import (
    APP_FOLDER,
    LEGACY_APP_FOLDER,
    TOKEN_BYTES,
    ServiceConfig,
    default_config_dir,
    default_data_dir,
    new_token,
)

HOME = Path("/home/someone")


def test_the_token_is_32_random_bytes_base64url() -> None:
    token = new_token()
    assert len(token) == 43
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    assert len(base64.urlsafe_b64decode(token + "=")) == TOKEN_BYTES == 32


def test_each_token_is_new() -> None:
    assert len({new_token() for _ in range(50)}) == 50


def test_linux_folders_follow_xdg() -> None:
    env = {"XDG_CONFIG_HOME": "/xdg/config", "XDG_DATA_HOME": "/xdg/data"}
    assert default_config_dir(env, "linux", HOME) == Path("/xdg/config/ithax")
    assert default_data_dir(env, "linux", HOME) == Path("/xdg/data/ithax")


def test_linux_folders_default_under_home() -> None:
    assert default_config_dir({}, "linux", HOME) == HOME / ".config" / "ithax"
    assert default_data_dir({}, "linux", HOME) == HOME / ".local" / "share" / "ithax"


def test_a_relative_xdg_folder_is_ignored() -> None:
    env = {"XDG_CONFIG_HOME": "relative", "XDG_DATA_HOME": ""}
    assert default_config_dir(env, "linux", HOME) == HOME / ".config" / "ithax"
    assert default_data_dir(env, "linux", HOME) == HOME / ".local" / "share" / "ithax"


def test_windows_folders() -> None:
    env = {"APPDATA": "C:/Users/s/AppData/Roaming", "LOCALAPPDATA": "C:/Users/s/AppData/Local"}
    assert default_config_dir(env, "win32", HOME) == Path("C:/Users/s/AppData/Roaming/ithax")
    assert default_data_dir(env, "win32", HOME) == Path("C:/Users/s/AppData/Local/ithax")
    assert default_config_dir({}, "win32", HOME) == HOME / "AppData" / "Roaming" / "ithax"
    assert default_data_dir({}, "win32", HOME) == HOME / "AppData" / "Local" / "ithax"


def test_macos_folders() -> None:
    support = HOME / "Library" / "Application Support" / "ithax"
    assert default_config_dir({}, "darwin", HOME) == support
    assert default_data_dir({}, "darwin", HOME) == support


def test_the_defaults_read_this_process() -> None:
    assert default_config_dir() == default_config_dir(os.environ, sys.platform, Path.home())
    assert default_data_dir() == default_data_dir(os.environ, sys.platform, Path.home())


@pytest.mark.parametrize("platform", ["linux", "win32", "darwin"])
def test_a_folder_from_before_the_rename_is_used_while_no_ithax_folder_exists(
    tmp_path: Path, platform: str
) -> None:
    """#70: projects and settings made under the ``lcsim`` name are still found."""
    env = {
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "APPDATA": str(tmp_path / "config"),
        "LOCALAPPDATA": str(tmp_path / "data"),
    }
    new = default_config_dir(env, platform, tmp_path), default_data_dir(env, platform, tmp_path)
    assert {path.name for path in new} == {APP_FOLDER}
    for path in new:
        (path.parent / LEGACY_APP_FOLDER).mkdir(parents=True, exist_ok=True)
    legacy = default_config_dir(env, platform, tmp_path), default_data_dir(env, platform, tmp_path)
    assert legacy == tuple(path.parent / LEGACY_APP_FOLDER for path in new)
    for path in new:
        path.mkdir(parents=True, exist_ok=True)
    assert (
        default_config_dir(env, platform, tmp_path),
        default_data_dir(env, platform, tmp_path),
    ) == new


def test_a_legacy_name_that_is_a_file_is_not_a_folder(tmp_path: Path) -> None:
    env = {"XDG_CONFIG_HOME": str(tmp_path)}
    (tmp_path / LEGACY_APP_FOLDER).write_text("not a folder", encoding="utf-8")
    assert default_config_dir(env, "linux", tmp_path) == tmp_path / APP_FOLDER


@pytest.mark.parametrize(("port", "token"), [(0, "t"), (65536, "t"), (80, "")])
def test_a_config_needs_a_port_and_token(tmp_path: Path, port: int, token: str) -> None:
    with pytest.raises(ValueError, match=r"port|token"):
        ServiceConfig(config_dir=tmp_path, data_dir=tmp_path, port=port, token=token)
