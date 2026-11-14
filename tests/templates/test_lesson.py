"""``lesson.md``'s rules (spec 4 "Template package"; AKS-122)."""

import pytest

from ithax.templates.lesson import Choice, count_words, parse_lesson

VALID = """# Coffee shop queue

## Customers arrive

Component: `arrivals`

Customers arrive at random.

## One till

Component: `till`

The till serves them.

## Exercise: a second till

Component: `till`

### Change

Set `tills` to 2.

### Prediction

- [ ] The wait halves.
- [x] The wait falls far more.

### Explanation

Waiting grows steeply near full load.
"""


def paths(text: str) -> list[str]:
    lesson, problems = parse_lesson(text)
    assert lesson is None
    return [problem.path for problem in problems]


def test_a_valid_lesson_is_read() -> None:
    lesson, problems = parse_lesson(VALID)
    assert problems == ()
    assert lesson is not None
    assert lesson.title == "Coffee shop queue"
    assert [step.heading for step in lesson.steps] == ["Customers arrive", "One till"]
    assert lesson.steps[0].text == "Customers arrive at random."
    assert lesson.components == ("arrivals", "till", "till")
    exercise = lesson.exercise
    assert exercise.heading == "Exercise: a second till"
    assert exercise.change == "Set `tills` to 2."
    assert exercise.choices == (
        Choice("The wait halves.", False),
        Choice("The wait falls far more.", True),
    )
    assert exercise.explanation == "Waiting grows steeply near full load."


def test_words_hold_a_letter_or_a_digit() -> None:
    # A multiplication sign and a division sign alone are not words either.
    assert count_words("0.5 a minute \u00d7 6 minutes = 3 \u00f7 - x") == 7
    assert count_words("") == 0


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (("# Coffee shop queue\n", ""), [""]),
        (("# Coffee shop queue\n", "# Coffee shop queue\nIntro text.\n"), [""]),
        (
            ("Component: `arrivals`\n\nCustomers arrive at random.", "Customers arrive."),
            ["/steps/0"],
        ),
        (("Customers arrive at random.", "word " * 81), ["/steps/0"]),
        (("Customers arrive at random.", ""), ["/steps/0"]),
        (("The till serves them.", "### Part\nText."), ["/steps/1"]),
        (("## Exercise: a second till", "## A second till"), ["/steps/2"]),
        (("### Change\n", "### Changes\n"), ["/steps/2"]),
        (
            ("Component: `till`\n\n### Change", "Component: `till`\n\nIntro.\n\n### Change"),
            ["/steps/2"],
        ),
        (("Set `tills` to 2.", ""), ["/steps/2/change"]),
        (("Waiting grows steeply near full load.", "word " * 81), ["/steps/2/explanation"]),
        (("- [ ] The wait halves.", "* The wait halves."), ["/steps/2/prediction"] * 2),
        (("- [ ] The wait halves.", "- [x] The wait halves."), ["/steps/2/prediction"]),
        (
            ("- [x] The wait falls far more.", "- [ ] The wait falls far more."),
            ["/steps/2/prediction"],
        ),
        (("- [ ] The wait halves.", "- [ ] " + "word " * 31), ["/steps/2/prediction/0"]),
        (
            ("- [ ] The wait halves.\n", "- [ ] a\n- [ ] b\n- [ ] c\n- [ ] d\n"),
            ["/steps/2/prediction"],
        ),
    ],
)
def test_each_rule_is_a_problem_at_its_place(change: tuple[str, str], expected: list[str]) -> None:
    assert change[0] in VALID
    assert paths(VALID.replace(change[0], change[1], 1)) == expected


def test_the_exercise_needs_its_component_line() -> None:
    text = VALID.replace("## Exercise: a second till\n\nComponent: `till`\n", "## Exercise\n")
    assert paths(text) == ["/steps/2"]


def test_a_lesson_needs_a_step_and_the_exercise() -> None:
    text = VALID.split("## One till")[0]
    assert paths(text) == [""]
    assert paths("") == ["", ""]


def test_problems_say_what_to_do() -> None:
    _, problems = parse_lesson(VALID.replace("Customers arrive at random.", "word " * 81))
    assert "81 words" in problems[0].message
    assert "80" in problems[0].hint
