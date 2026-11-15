"""The two AppImage build tools (#88; ``docs/research/m16-appimage.md``): each is downloaded
by its exact release URL and checked against its pinned SHA-256, and against the digest its
release publishes; a tool with no pin yet is never used by a build (fail closed)."""

import hashlib
from pathlib import Path
from typing import Any

import pytest

from linux_package.build_script import build


def tool(tmp_path: Path, data: bytes, sha256: str | None) -> Any:
    source = tmp_path / "upstream" / "appimagetool-x86_64.AppImage"
    source.parent.mkdir(exist_ok=True)
    source.write_bytes(data)
    return build.Tool(
        name="appimagetool-1.9.1-x86_64.AppImage",
        url=source.as_uri(),
        release="https://api.github.com/repos/AppImage/appimagetool/releases/tags/1.9.1",
        sha256=sha256,
    )


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def no_published(_tool: Any) -> str | None:
    return None


def test_the_tools_are_the_researched_releases_by_exact_url() -> None:
    urls = [item.url for item in build.APPIMAGE_TOOLS]
    assert urls == [
        "https://github.com/AppImage/appimagetool/releases/download/1.9.1/"
        "appimagetool-x86_64.AppImage",
        "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64",
    ]
    for item in build.APPIMAGE_TOOLS:
        assert item.sha256 is None or len(item.sha256) == 64


def test_a_pinned_tool_is_downloaded_once_and_checked(tmp_path: Path) -> None:
    item = tool(tmp_path, b"tool", digest(b"tool"))
    cache = tmp_path / "cache"
    path = build.fetch_tool(cache, item)
    assert path == cache / item.name
    assert path.read_bytes() == b"tool"
    assert not list(cache.glob("*.part"))
    # A second build takes the cached file, and still checks it.
    (tmp_path / "upstream" / "appimagetool-x86_64.AppImage").unlink()
    assert build.fetch_tool(cache, item) == path


def test_a_tool_whose_bytes_differ_from_its_pin_is_refused(tmp_path: Path) -> None:
    item = tool(tmp_path, b"changed", digest(b"tool"))
    with pytest.raises(build.BuildError, match="does not have the pinned SHA-256"):
        build.fetch_tool(tmp_path / "cache", item)


def test_a_build_refuses_a_tool_with_no_pin(tmp_path: Path) -> None:
    item = tool(tmp_path, b"tool", None)
    with pytest.raises(build.BuildError, match="has no pinned SHA-256"):
        build.fetch_tool(tmp_path / "cache", item)


def test_the_check_prints_the_hash_of_a_tool_not_pinned_yet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    item = tool(tmp_path, b"tool", None)
    assert build.check_tools(tmp_path / "cache", [item], no_published) == 0
    out = capsys.readouterr().out
    assert f"{item.name} sha256 {digest(b'tool')}" in out
    assert "not pinned yet" in out


def test_the_check_passes_a_pinned_tool_matching_its_release(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    item = tool(tmp_path, b"tool", digest(b"tool"))
    assert build.check_tools(tmp_path / "cache", [item], lambda _t: digest(b"tool")) == 0
    out = capsys.readouterr().out
    assert "matches the pin" in out
    assert "matches the release's published digest" in out


def test_the_check_fails_a_tool_that_differs_from_its_pin(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    item = tool(tmp_path, b"changed", digest(b"tool"))
    assert build.check_tools(tmp_path / "cache", [item], no_published) == 1
    assert "does not match the pin" in capsys.readouterr().err


def test_the_check_fails_a_tool_that_differs_from_its_published_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    item = tool(tmp_path, b"tool", None)
    assert build.check_tools(tmp_path / "cache", [item], lambda _t: "b" * 64) == 1
    assert "does not match the release's published digest" in capsys.readouterr().err


def test_the_published_digest_is_read_from_the_release_asset() -> None:
    release = {
        "assets": [
            {"name": "other", "digest": "sha256:" + "c" * 64},
            {"name": "appimagetool-x86_64.AppImage", "digest": "sha256:" + "d" * 64},
        ]
    }
    url = build.APPIMAGE_TOOLS[0].url
    assert build.asset_digest(release, url) == "d" * 64
    # A release older than GitHub's asset digests lists none.
    assert build.asset_digest({"assets": [{"name": "appimagetool-x86_64.AppImage"}]}, url) is None
    assert build.asset_digest({"assets": []}, url) is None


def test_the_command_checks_the_tools_and_builds_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = tool(tmp_path, b"tool", None)
    monkeypatch.setattr(build, "APPIMAGE_TOOLS", (item,))
    monkeypatch.setattr(build, "published_digest", lambda _t: digest(b"tool"))
    out = tmp_path / "dist"
    assert build.main(["--check-appimage-tools", "--out", str(out)]) == 0
    assert (out / "cache" / "check" / item.name).read_bytes() == b"tool"
    assert sorted(path.name for path in out.iterdir()) == ["cache"]
