"""The token and the per-user folders (spec 3 "Token" and "Discovery"; AKS-110)."""

import base64
import re
from pathlib import Path

import pytest

from lcsim.service.config import (
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
    assert default_config_dir(env, "linux", HOME) == Path("/xdg/config/lcsim")
    assert default_data_dir(env, "linux", HOME) == Path("/xdg/data/lcsim")


def test_linux_folders_default_under_home() -> None:
    assert default_config_dir({}, "linux", HOME) == HOME / ".config" / "lcsim"
    assert default_data_dir({}, "linux", HOME) == HOME / ".local" / "share" / "lcsim"


def test_a_relative_xdg_folder_is_ignored() -> None:
    env = {"XDG_CONFIG_HOME": "relative", "XDG_DATA_HOME": ""}
    assert default_config_dir(env, "linux", HOME) == HOME / ".config" / "lcsim"
    assert default_data_dir(env, "linux", HOME) == HOME / ".local" / "share" / "lcsim"


def test_windows_folders() -> None:
    env = {"APPDATA": "C:/Users/s/AppData/Roaming", "LOCALAPPDATA": "C:/Users/s/AppData/Local"}
    assert default_config_dir(env, "win32", HOME) == Path("C:/Users/s/AppData/Roaming/lcsim")
    assert default_data_dir(env, "win32", HOME) == Path("C:/Users/s/AppData/Local/lcsim")
    assert default_config_dir({}, "win32", HOME) == HOME / "AppData" / "Roaming" / "lcsim"
    assert default_data_dir({}, "win32", HOME) == HOME / "AppData" / "Local" / "lcsim"


def test_macos_folders() -> None:
    support = HOME / "Library" / "Application Support" / "lcsim"
    assert default_config_dir({}, "darwin", HOME) == support
    assert default_data_dir({}, "darwin", HOME) == support


def test_the_defaults_read_this_process() -> None:
    assert default_config_dir().name == "lcsim"
    assert default_data_dir().name == "lcsim"


@pytest.mark.parametrize(("port", "token"), [(0, "t"), (65536, "t"), (80, "")])
def test_a_config_needs_a_port_and_token(tmp_path: Path, port: int, token: str) -> None:
    with pytest.raises(ValueError, match=r"port|token"):
        ServiceConfig(config_dir=tmp_path, data_dir=tmp_path, port=port, token=token)
