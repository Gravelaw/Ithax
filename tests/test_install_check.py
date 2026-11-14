"""``python -m ithax.install_check``, the check the Linux package's ``install.sh`` runs
(spec 3 "Packaging"; AKS-127)."""

import io
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import ithax
from ithax.engines.registry import load_adapters
from ithax.install_check import PHASE_1_ENGINES, check, main

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


@pytest.fixture
def ui_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "ui"
    folder.mkdir()
    (folder / "index.html").write_text("<!doctype html>", encoding="utf-8")
    return folder


def test_phase_1_engines_are_highs_and_simpy() -> None:
    assert PHASE_1_ENGINES == ("highs", "simpy")


def test_a_complete_installation_has_no_problem(ui_dir: Path) -> None:
    report = check(ui_dir, TEMPLATES)
    assert report.problems == []
    assert report.engines == ["highs", "simpy"]
    assert report.templates == 10


def test_a_missing_engine_is_a_problem(ui_dir: Path) -> None:
    adapters = {name: adapter for name, adapter in load_adapters().items() if name != "highs"}
    report = check(ui_dir, TEMPLATES, adapters)
    assert report.problems == ["The engine 'highs' is not installed or does not load."]


def test_a_missing_interface_is_a_problem(tmp_path: Path) -> None:
    report = check(tmp_path / "nowhere", TEMPLATES)
    assert report.problems == [f"The interface is missing: {tmp_path / 'nowhere' / 'index.html'}."]


def test_no_templates_is_a_problem(ui_dir: Path, tmp_path: Path) -> None:
    report = check(ui_dir, tmp_path / "none")
    assert report.problems == [f"No template package was found in {tmp_path / 'none'}."]


def test_a_template_that_cannot_be_served_is_a_problem(ui_dir: Path, tmp_path: Path) -> None:
    templates = tmp_path / "templates"
    shutil.copytree(TEMPLATES / "coffee_shop", templates / "coffee_shop")
    (templates / "broken").mkdir()
    report = check(ui_dir, templates)
    assert report.templates == 1
    assert len(report.problems) == 1
    assert report.problems[0].startswith("The template 'broken' cannot be served: E195")


def test_main_reports_a_complete_installation(ui_dir: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    status = main(["--ui-dir", str(ui_dir), "--templates-dir", str(TEMPLATES)], out=out, err=err)
    assert status == 0
    assert err.getvalue() == ""
    python = ".".join(str(part) for part in sys.version_info[:3])
    assert out.getvalue() == (
        f"lcsim {ithax.__version__} on Python {python}: engines highs, simpy; "
        f"the interface in {ui_dir}; 10 templates in {TEMPLATES}.\n"
    )


def test_main_lists_each_problem_and_fails(tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    status = main(
        ["--ui-dir", str(tmp_path / "ui"), "--templates-dir", str(tmp_path / "t")], out=out, err=err
    )
    assert status == 1
    assert out.getvalue() == ""
    assert err.getvalue() == (
        f"The interface is missing: {tmp_path / 'ui' / 'index.html'}.\n"
        f"No template package was found in {tmp_path / 't'}.\n"
    )


def test_main_uses_the_service_defaults(monkeypatch: pytest.MonkeyPatch, ui_dir: Path) -> None:
    import ithax.install_check as module

    monkeypatch.setattr(module, "default_ui_dir", lambda: ui_dir)
    monkeypatch.setattr(module, "default_templates_dir", lambda: TEMPLATES)
    out = io.StringIO()
    assert main([], out=out, err=io.StringIO()) == 0
    assert f"the interface in {ui_dir}" in out.getvalue()


def test_python_dash_m_runs_it(ui_dir: Path) -> None:
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "ithax.install_check",
            "--ui-dir",
            str(ui_dir),
            "--templates-dir",
            str(TEMPLATES),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "10 templates" in done.stdout
