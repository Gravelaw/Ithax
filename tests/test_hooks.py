"""The agent hooks and the fast gate (#99; docs/retrospective/proposed-agent-setup.md, P2)."""

import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts" / "hooks" / "format_edited.py"
FAST = ROOT / "scripts" / "fast.sh"
SETTINGS = ROOT / ".claude" / "settings.json"

sys.path.insert(0, str(HOOK.parent))
import format_edited  # noqa: E402


def excluded_markers(expression: str) -> set[str]:
    return set(re.findall(r"not ([a-z_]+)", expression))


def test_fast_sh_keeps_every_exclusion_of_addopts() -> None:
    """fast.sh's -m replaces the one in addopts, so it must repeat each exclusion."""
    with (ROOT / "pyproject.toml").open("rb") as handle:
        addopts = tomllib.load(handle)["tool"]["pytest"]["ini_options"]["addopts"]
    configured = excluded_markers(addopts.split("-m", 1)[1])
    fast = excluded_markers(FAST.read_text(encoding="utf-8").split(" -m ", 1)[1])
    assert configured <= fast, f"fast.sh would run: {sorted(configured - fast)}"
    assert {"benchmark", "template"} <= fast


def test_the_settings_run_the_hook_and_the_fast_lint() -> None:
    hooks = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]
    (post,) = hooks["PostToolUse"]
    assert post["matcher"] == "Edit|Write"
    assert "scripts/hooks/format_edited.py" in post["hooks"][0]["command"]
    (stop,) = hooks["Stop"]
    assert "bash scripts/fast.sh --lint" in stop["hooks"][0]["command"]
    assert stop["hooks"][0]["command"].endswith("|| exit 2")


def test_the_hook_reads_the_edited_path() -> None:
    event = json.dumps({"tool_input": {"file_path": "/x/y.py"}})
    assert format_edited.edited_path(event) == "/x/y.py"
    assert format_edited.edited_path("not json") == ""
    assert format_edited.edited_path("[]") == ""
    assert format_edited.edited_path(json.dumps({"tool_input": {"file_path": 3}})) == ""
    assert format_edited.edited_path(json.dumps({})) == ""


def test_the_hook_prefers_the_repository_venv(tmp_path: Path) -> None:
    assert format_edited.interpreter(tmp_path) == sys.executable
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text("", encoding="utf-8")
    assert format_edited.interpreter(tmp_path) == str(venv / "python")


def run_hook(event: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)], input=event, text=True, capture_output=True, check=False
    )


def test_the_hook_formats_and_fixes_an_edited_python_file(tmp_path: Path) -> None:
    edited = tmp_path / "edited.py"
    edited.write_text("import sys\nimport os\nx=[1,2 ,3]\n", encoding="utf-8")
    finished = run_hook(json.dumps({"tool_input": {"file_path": str(edited)}}))
    assert finished.returncode == 0, finished.stderr
    # Formatted, and the unused imports removed by ruff check --fix (F401).
    assert edited.read_text(encoding="utf-8") == "x = [1, 2, 3]\n"


def test_the_hook_leaves_other_files_and_bad_events_alone(tmp_path: Path) -> None:
    other = tmp_path / "notes.md"
    other.write_text("x=[1,2 ,3]\n", encoding="utf-8")
    assert run_hook(json.dumps({"tool_input": {"file_path": str(other)}})).returncode == 0
    assert other.read_text(encoding="utf-8") == "x=[1,2 ,3]\n"
    assert run_hook("not json").returncode == 0


def test_fast_sh_lint_mode_passes_on_the_repository() -> None:
    bash = shutil.which("bash")
    assert bash is not None
    finished = subprocess.run(
        [bash, str(FAST), "--lint"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert finished.returncode == 0, finished.stdout[-2000:] + finished.stderr[-2000:]
