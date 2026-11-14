"""Where the service finds the interface and the templates by default (spec 3, the
``GET /v1/ui/{path}`` and Templates notes; "Packaging", AKS-127): the source checkout's
folders, or else those the Linux package installs under ``sys.prefix``."""

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from ithax.service.config import (
    default_templates_dir,
    default_ui_dir,
    installed_share_dir,
)

CHECKOUT = Path(__file__).resolve().parents[2]

Finder = Callable[..., Path]


def test_the_installed_share_folder_is_share_lcsim_under_the_python_prefix() -> None:
    assert installed_share_dir() == Path(sys.prefix) / "share" / "lcsim"
    assert installed_share_dir("/opt/x/python") == Path("/opt/x/python/share/lcsim")


@pytest.mark.parametrize(
    ("finder", "checkout_part", "installed_part"),
    [
        (default_ui_dir, Path("ui", "dist"), Path("ui")),
        (default_templates_dir, Path("templates"), Path("templates")),
    ],
)
class TestDefaultFolders:
    def test_the_checkout_folder_wins_when_it_exists(
        self, finder: Finder, checkout_part: Path, installed_part: Path, tmp_path: Path
    ) -> None:
        checkout, prefix = tmp_path / "checkout", tmp_path / "python"
        (checkout / checkout_part).mkdir(parents=True)
        (prefix / "share" / "lcsim" / installed_part).mkdir(parents=True)
        assert finder(checkout, str(prefix)) == checkout / checkout_part

    def test_the_installed_folder_is_used_when_the_checkout_has_none(
        self, finder: Finder, checkout_part: Path, installed_part: Path, tmp_path: Path
    ) -> None:
        checkout, prefix = tmp_path / "checkout", tmp_path / "python"
        checkout.mkdir()
        (prefix / "share" / "lcsim" / installed_part).mkdir(parents=True)
        assert finder(checkout, str(prefix)) == prefix / "share" / "lcsim" / installed_part

    def test_a_file_is_not_a_folder(
        self, finder: Finder, checkout_part: Path, installed_part: Path, tmp_path: Path
    ) -> None:
        checkout, prefix = tmp_path / "checkout", tmp_path / "python"
        (checkout / checkout_part).parent.mkdir(parents=True, exist_ok=True)
        (checkout / checkout_part).write_text("not a folder")
        (prefix / "share" / "lcsim" / installed_part).mkdir(parents=True)
        assert finder(checkout, str(prefix)) == prefix / "share" / "lcsim" / installed_part

    def test_with_neither_the_checkout_folder_is_named(
        self, finder: Finder, checkout_part: Path, installed_part: Path, tmp_path: Path
    ) -> None:
        # The service then answers 404 (E185) for the interface and serves no template.
        assert finder(tmp_path / "checkout", str(tmp_path / "python")) == (
            tmp_path / "checkout" / checkout_part
        )

    def test_by_default_the_checkout_is_this_one_and_the_prefix_this_python(
        self, finder: Finder, checkout_part: Path, installed_part: Path
    ) -> None:
        expected = CHECKOUT / checkout_part
        if not expected.is_dir() and (installed_share_dir() / installed_part).is_dir():
            expected = installed_share_dir() / installed_part
        assert finder() == expected
