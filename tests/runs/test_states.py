"""Job states and their allowed moves (spec 1 "Run folder and results"; AKS-103)."""

import itertools

import pytest

from ithax.runs.states import (
    ALLOWED_MOVES,
    FINAL_STATES,
    JOB_STATES,
    StateError,
    check_move,
)


def test_the_five_states_and_the_final_ones() -> None:
    assert JOB_STATES == ("queued", "running", "done", "failed", "cancelled")
    assert FINAL_STATES == ("done", "failed", "cancelled")


def test_the_allowed_moves_are_exactly_those_of_spec_1() -> None:
    # Spec 1, with queued -> failed for E191 only (AKS-103, owner to confirm).
    assert ALLOWED_MOVES == frozenset(
        {
            ("queued", "running"),
            ("running", "done"),
            ("running", "failed"),
            ("running", "cancelled"),
            ("queued", "cancelled"),
            ("queued", "failed"),
        }
    )


@pytest.mark.parametrize("move", sorted(ALLOWED_MOVES))
def test_an_allowed_move_passes(move: tuple[str, str]) -> None:
    check_move(*move)


@pytest.mark.parametrize(
    "move",
    [move for move in itertools.product(JOB_STATES, repeat=2) if move not in ALLOWED_MOVES],
)
def test_every_other_move_is_refused(move: tuple[str, str]) -> None:
    with pytest.raises(StateError, match=f"from {move[0]!r} to {move[1]!r}"):
        check_move(*move)


def test_an_unknown_state_is_refused() -> None:
    with pytest.raises(StateError, match="'paused'"):
        check_move("running", "paused")
