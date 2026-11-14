"""PostToolUse hook: format and lint-fix the Python file that was just edited.

docs/retrospective/proposed-agent-setup.md, P2 (#99), run by `.claude/settings.json` after
each Edit or Write. It never fails the edit: what ruff cannot fix is left for the Stop hook
(`scripts/fast.sh --lint`) and `scripts/check.sh` to report.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def edited_path(event: str) -> str:
    """The edited file named by a hook event, or "" when the event names none."""
    try:
        payload = json.loads(event)
    except json.JSONDecodeError:
        return ""
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    return path if isinstance(path, str) else ""


def interpreter(root: Path = ROOT) -> str:
    """The repository's ``.venv`` Python when there is one, else the hook's own."""
    venv = root / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def main() -> None:
    path = edited_path(sys.stdin.read())
    if path.endswith(".py"):
        python = interpreter()
        # Fix first, then format, so that what a fix leaves behind is formatted too.
        subprocess.run([python, "-m", "ruff", "check", "--fix", "--quiet", path], check=False)
        subprocess.run([python, "-m", "ruff", "format", "--quiet", path], check=False)


if __name__ == "__main__":
    main()
