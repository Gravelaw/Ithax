"""Compute WCAG 2.2 contrast ratios for the colour pairs in docs/design/tokens.json.

Usage:
    python scripts/contrast.py            print the Markdown table
    python scripts/contrast.py --check    also exit 1 if any pair is below its threshold

Formulas: WCAG 2.2, section 6 (Glossary), "relative luminance" and "contrast ratio"
(https://www.w3.org/TR/WCAG22/). Thresholds: 1.4.3 Contrast (Minimum), 4.5:1 for text and
3:1 for large text; 1.4.11 Non-text Contrast, 3:1.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "docs" / "design" / "tokens.json"
THRESHOLDS = {"text": 4.5, "large-text": 3.0, "non-text": 3.0}
CRITERION = {"text": "1.4.3", "large-text": "1.4.3", "non-text": "1.4.11"}


def channel(value: int) -> float:
    """Linearise one 8-bit sRGB channel."""
    c = value / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    """Relative luminance of a #RRGGBB colour."""
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def ratio(fg: str, bg: str) -> float:
    """Contrast ratio (L1 + 0.05) / (L2 + 0.05), L1 the lighter colour."""
    a, b = luminance(fg), luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def rows() -> list[tuple[str, str, str, str, float, float, bool]]:
    """(theme, fg, bg, use, ratio, threshold, passes) for every theme and pair."""
    data = json.loads(TOKENS.read_text(encoding="utf-8"))
    out = []
    for theme, colours in data["themes"].items():
        for pair in data["pairs"]:
            r = round(ratio(colours[pair["fg"]], colours[pair["bg"]]), 2)
            need = THRESHOLDS[pair["kind"]]
            out.append((theme, pair["fg"], pair["bg"], pair["use"], r, need, r >= need))
    return out


def table() -> str:
    """The Markdown table embedded in docs/design/design-system.md."""
    data = json.loads(TOKENS.read_text(encoding="utf-8"))
    kinds = {(p["fg"], p["bg"], p["use"]): p["kind"] for p in data["pairs"]}
    lines = [
        "| Theme | Foreground | Background | Used for | Ratio | Needed | Criterion | Result |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for theme, fg, bg, use, r, need, ok in rows():
        crit = CRITERION[kinds[(fg, bg, use)]]
        verdict = "pass" if ok else "FAIL"
        lines.append(
            f"| {theme} | `{fg}` | `{bg}` | {use} | {r:.2f}:1 | {need:.1f}:1 | {crit} | {verdict} |"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    print(table())
    if "--check" in argv:
        failures = [row for row in rows() if not row[6]]
        for theme, fg, bg, _use, r, need, _ok in failures:
            print(f"FAIL {theme}: {fg} on {bg} is {r:.2f}:1, needs {need:.1f}:1", file=sys.stderr)
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
