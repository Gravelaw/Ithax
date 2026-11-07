"""Canonical project and folder paths, and what counts as the same project folder
(spec 3 "Endpoints" notes on projects; review of PR #34: relative paths, Windows paths
without a drive, and aliases such as symbolic links and junctions)."""

import os
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

import pytest

from lcsim.service.paths import canonical, fully_qualified, same_folder


def link(target: Path, alias: Path) -> Path:
    """``alias`` as a symbolic link to the folder ``target``; the test is skipped where the
    operating system, or the account, cannot make one (Windows without the privilege)."""
    try:
        os.symlink(target, alias, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - depends on the platform
        pytest.skip("this system cannot create symbolic links")
    return alias


@pytest.mark.parametrize(
    ("flavour", "path", "qualified"),
    [
        (PureWindowsPath, r"C:\projects\demo", True),
        (PureWindowsPath, r"\\server\share\demo", True),
        (PureWindowsPath, r"\projects\demo", False),
        (PureWindowsPath, r"C:projects\demo", False),
        (PureWindowsPath, r"projects\demo", False),
        (PurePosixPath, "/projects/demo", True),
        (PurePosixPath, "projects/demo", False),
    ],
)
def test_a_path_is_fully_qualified_only_with_its_drive_or_share(
    flavour: type[PurePath], path: str, qualified: bool
) -> None:
    assert fully_qualified(path, flavour) is qualified


def test_canonical_is_absolute_normalised_and_resolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = link(real, tmp_path / "alias")
    assert canonical(alias) == real
    assert canonical(alias / "missing" / ".." / "x") == real / "x"
    monkeypatch.chdir(tmp_path)
    assert canonical(Path("real")) == real
    assert canonical("alias") == real


def test_the_same_folder_by_any_name(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    alias = link(real, tmp_path / "alias")
    assert same_folder(alias, real)
    assert same_folder(real / ".", real)
    assert not same_folder(other, real)
    # Folders that do not exist are compared by their canonical paths.
    assert same_folder(tmp_path / "gone", tmp_path / "x" / ".." / "gone")
    assert not same_folder(tmp_path / "gone", real)


def test_samefile_decides_for_two_names_resolving_leaves_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Such as ``C:\\Work`` and ``C:\\work`` on Windows, whose file system ignores case."""
    first, second = tmp_path / "Work", tmp_path / "work2"
    first.mkdir()
    second.mkdir()
    monkeypatch.setattr(os.path, "samefile", lambda a, b: True)
    assert same_folder(first, second)
