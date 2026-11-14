"""A template's ``lesson.md`` (spec 4 "Template package"; AKS-122).

The lesson is Markdown: a first line ``# <title>``, then one ``## <heading>`` section per
step, at least two. A step's first non-empty line is ``Component: `<id>` ``, and its text
(every line after that one) holds at most ``MAX_STEP_WORDS`` words. The last step's heading
starts with ``Exercise`` and its text is three ``### `` parts in order: ``Change``,
``Prediction`` (two to four choices ``- [ ] <text>`` or ``- [x] <text>``, exactly one
``[x]``) and ``Explanation``.

``parse_lesson`` returns the lesson, or the problems that stop it, each with a JSON
Pointer into the lesson (``/steps/2``, ``/steps/3/prediction/1``); the package loader
turns them into E195 issues under ``/lesson.md``. Whether a step's component exists is the
loader's to check, since it needs the model.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "EXERCISE_PARTS",
    "MAX_CHOICES",
    "MAX_CHOICE_WORDS",
    "MAX_STEP_WORDS",
    "MIN_CHOICES",
    "Choice",
    "Exercise",
    "Lesson",
    "LessonProblem",
    "Step",
    "count_words",
    "parse_lesson",
]

#: Spec 4: each lesson step gives up to 80 words of explanation.
MAX_STEP_WORDS = 80
#: The exercise's choices: two to four, each at most 30 words (AKS-122).
MIN_CHOICES = 2
MAX_CHOICES = 4
MAX_CHOICE_WORDS = 30
#: The exercise's three parts, in order.
EXERCISE_PARTS = ("Change", "Prediction", "Explanation")

_COMPONENT = re.compile(r"Component: `([^`]+)`")
_CHOICE = re.compile(r"- \[( |x)\] (\S.*)")


@dataclass(frozen=True)
class Step:
    """One step: its heading, the component (or variable, constraint or ``objective``)
    it highlights, and its text."""

    heading: str
    component: str
    text: str


@dataclass(frozen=True)
class Choice:
    """One prediction to choose from; ``right`` for the one marked ``[x]``."""

    text: str
    right: bool


@dataclass(frozen=True)
class Exercise:
    """The last step: the change to make, the predictions and the explanation."""

    heading: str
    component: str
    change: str
    choices: tuple[Choice, ...]
    explanation: str


@dataclass(frozen=True)
class Lesson:
    """A lesson that keeps every rule: its title, its steps before the exercise, and the
    exercise."""

    title: str
    steps: tuple[Step, ...]
    exercise: Exercise

    @property
    def components(self) -> tuple[str, ...]:
        """What each step highlights, in order, the exercise's last."""
        return (*(step.component for step in self.steps), self.exercise.component)


@dataclass(frozen=True)
class LessonProblem:
    """A rule the lesson breaks: ``path`` is a JSON Pointer into the lesson (``""`` for
    the whole file)."""

    path: str
    message: str
    hint: str


def count_words(text: str) -> int:
    """The words of ``text``: runs of characters between spaces or line ends that hold
    a letter or a digit (so a sign such as ``-`` or ``=`` alone is not a word)."""
    return sum(1 for token in text.split() if any(char.isalnum() for char in token))


@dataclass
class _Section:
    heading: str
    lines: list[str]


def _sections(lines: Sequence[str], marker: str) -> tuple[list[str], list[_Section]]:
    """The lines before the first heading starting with ``marker``, and each section."""
    before: list[str] = []
    sections: list[_Section] = []
    for line in lines:
        if line.startswith(marker):
            sections.append(_Section(line[len(marker) :].strip(), []))
        elif sections:
            sections[-1].lines.append(line)
        else:
            before.append(line)
    return before, sections


def _text(lines: Sequence[str]) -> str:
    return "\n".join(lines).strip()


class _Parser:
    def __init__(self) -> None:
        self.problems: list[LessonProblem] = []

    def problem(self, path: str, message: str, hint: str) -> None:
        self.problems.append(LessonProblem(path, message, hint))

    def words(self, path: str, what: str, text: str, limit: int) -> None:
        words = count_words(text)
        if words == 0:
            self.problem(path, f"{what} is empty.", f"Write {what.lower()}.")
        elif words > limit:
            self.problem(
                path,
                f"{what} has {words} words; at most {limit} are allowed.",
                f"Shorten it to {limit} words or fewer.",
            )

    def component(self, index: int, section: _Section) -> tuple[str | None, list[str]]:
        """The step's component and the lines after its ``Component:`` line."""
        lines = section.lines
        first = next((at for at, line in enumerate(lines) if line.strip()), None)
        match = None if first is None else _COMPONENT.fullmatch(lines[first].strip())
        if first is None or match is None:
            self.problem(
                f"/steps/{index}",
                f"Step {index + 1}, '{section.heading}', does not start with a "
                "'Component: `<id>`' line.",
                "Make the step's first line 'Component: `<id>`', naming what it highlights.",
            )
            return None, lines if first is None else lines[first:]
        return match.group(1), lines[first + 1 :]

    def step(self, index: int, section: _Section) -> Step | None:
        component, rest = self.component(index, section)
        path = f"/steps/{index}"
        if any(line.startswith("### ") for line in rest):
            self.problem(
                path,
                f"Step {index + 1}, '{section.heading}', has a '###' part; only the "
                "exercise, the last step, has parts.",
                "Remove the '###' heading, or make this step the exercise.",
            )
        text = _text(rest)
        self.words(path, f"Step {index + 1}'s text", text, MAX_STEP_WORDS)
        return None if component is None else Step(section.heading, component, text)

    def choices(self, path: str, lines: Sequence[str]) -> tuple[Choice, ...]:
        choices: list[Choice] = []
        for line in (line.strip() for line in lines):
            if not line:
                continue
            match = _CHOICE.fullmatch(line)
            if match is None:
                self.problem(
                    path,
                    f"The prediction line '{line}' is not a choice.",
                    "Write each choice as '- [ ] <text>', and the right one as '- [x] <text>'.",
                )
                continue
            at = f"{path}/{len(choices)}"
            self.words(at, f"Choice {len(choices) + 1}", match.group(2), MAX_CHOICE_WORDS)
            choices.append(Choice(match.group(2).strip(), match.group(1) == "x"))
        if not MIN_CHOICES <= len(choices) <= MAX_CHOICES:
            self.problem(
                path,
                f"The prediction has {len(choices)} choices; it needs {MIN_CHOICES} to "
                f"{MAX_CHOICES}.",
                f"Give {MIN_CHOICES} to {MAX_CHOICES} choices.",
            )
        right = sum(choice.right for choice in choices)
        if right != 1:
            self.problem(
                path,
                f"The prediction marks {right} choices right; exactly one is marked '[x]'.",
                "Mark the one right choice '- [x]' and the others '- [ ]'.",
            )
        return tuple(choices)

    def exercise(self, index: int, section: _Section) -> Exercise | None:
        path = f"/steps/{index}"
        if not section.heading.startswith("Exercise"):
            self.problem(
                path,
                f"The last step, '{section.heading}', is not an exercise: its heading "
                "does not start with 'Exercise'.",
                "End the lesson with a step headed 'Exercise: ...'.",
            )
        component, rest = self.component(index, section)
        before, parts = _sections(rest, "### ")
        names = tuple(part.heading for part in parts)
        if names != EXERCISE_PARTS or _text(before):
            self.problem(
                path,
                f"The exercise's parts are {list(names)}; it needs exactly "
                f"{list(EXERCISE_PARTS)}, in that order, and no text before them.",
                "Write '### Change', '### Prediction' and '### Explanation' after the "
                "Component line.",
            )
            return None
        change, explanation = _text(parts[0].lines), _text(parts[2].lines)
        self.words(f"{path}/change", "The exercise's change", change, MAX_STEP_WORDS)
        choices = self.choices(f"{path}/prediction", parts[1].lines)
        self.words(f"{path}/explanation", "The exercise's explanation", explanation, MAX_STEP_WORDS)
        if component is None:
            return None
        return Exercise(section.heading, component, change, choices, explanation)


def parse_lesson(text: str) -> tuple[Lesson | None, tuple[LessonProblem, ...]]:
    """The lesson in ``text``, or ``None`` with every problem found."""
    parser = _Parser()
    lines = text.splitlines()
    title = lines[0][2:].strip() if lines and lines[0].startswith("# ") else None
    if not title:
        parser.problem(
            "", "The lesson does not start with a '# <title>' line.", "Start with '# <title>'."
        )
    before, sections = _sections(lines[1:], "## ")
    if _text(before):
        parser.problem(
            "",
            "The lesson has text between its title and its first step.",
            "Put every text inside a '## ' step.",
        )
    if len(sections) < 2:
        parser.problem(
            "",
            f"The lesson has {len(sections)} steps; it needs at least one step and the exercise.",
            "Add '## ' steps, the last one the exercise.",
        )
        return None, tuple(parser.problems)
    steps = [parser.step(index, section) for index, section in enumerate(sections[:-1])]
    exercise = parser.exercise(len(sections) - 1, sections[-1])
    if parser.problems or title is None or exercise is None:
        return None, tuple(parser.problems)
    return Lesson(title, tuple(step for step in steps if step is not None), exercise), ()
