"""The warm-up check and W210 (spec 2 "Statistic definitions", warm-up check; AKS-129 and
AKS-102): ``ithax.runs.warmup``.

The unit tests use synthetic ``timeseries`` tables and a hand computation with
``scipy.stats.t.ppf``. One case runs the process adapter on the research note's "slow
fill" model (``docs/research/spec-2-output-analysis.md``, "Tested"), shortened to keep
the gate fast; the coffee shop's silence is checked on its full run in
``tests/engines/process/test_example_models.py``.
"""

import math
import re
import statistics
import threading
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from scipy.stats import t

from ithax.engines.process.adapter import ProcessAdapter
from ithax.model.loading import load_document
from ithax.runs.warmup import Drift, warmup_check, warmup_warning

HOUR = 3600.0


def series(rows: list[tuple[str, int, str, float, float]]) -> pa.Table:
    """A ``timeseries`` table (spec 1 "Tables for the process domain") from rows of
    scenario, replication, metric, time and value."""
    names = ["scenario", "replication", "metric", "time_s", "value"]
    columns: dict[str, list[Any]] = {name: [row[i] for row in rows] for i, name in enumerate(names)}
    columns["unit"] = ["1"] * len(rows)
    return pa.table(columns)


def rows_of(
    scenario: str, metric: str, values: dict[int, list[float]], start: float = 0.0
) -> list[tuple[str, int, str, float, float]]:
    """Rows of one metric, one sample a second from ``start``, per replication."""
    return [
        (scenario, rep, metric, start + k, value)
        for rep, samples in values.items()
        for k, value in enumerate(samples)
    ]


# Three replications, J = 5 observed samples (the middle one, index 2, is in neither half).
RISING = {
    0: [1.0, 2.0, 50.0, 4.0, 5.0],
    1: [2.0, 2.0, -50.0, 6.0, 6.0],
    2: [0.0, 1.0, 0.0, 5.0, 4.0],
}


def test_the_statistic_equals_a_hand_computation() -> None:
    found = warmup_check(series(rows_of("default", "x.queue_length", RISING)), 0.0, ["default"])
    assert len(found) == 1
    drift = found[0]
    # d_r: (4 + 5)/2 - (1 + 2)/2 = 3; (6 + 6)/2 - (2 + 2)/2 = 4; (5 + 4)/2 - (0 + 1)/2 = 4.
    d = [3.0, 4.0, 4.0]
    # m_r: means of all five samples, the middle one included.
    m = [statistics.fmean(samples) for samples in RISING.values()]
    assert drift.samples == 5 and drift.replications == 3
    assert drift.change == pytest.approx(statistics.fmean(d), rel=1e-15)
    assert drift.mean == pytest.approx(statistics.fmean(m), rel=1e-15)
    expected = t.ppf(0.995, 2) * statistics.stdev(d) / math.sqrt(3)
    assert drift.half_width == pytest.approx(expected, rel=1e-13)
    # d-bar 3.667 against a half-width of 9.925 x 0.577 / 1.732 = 3.31: changed.
    assert drift.changed
    assert drift.percent == round(100 * abs(drift.change) / abs(drift.mean))


def test_only_samples_at_or_after_warmup_are_observed() -> None:
    # Samples at 0 to 6 s; warm-up 2 s leaves the five samples at 2 to 6 s.
    values = {rep: [99.0, 99.0, *samples] for rep, samples in RISING.items()}
    found = warmup_check(series(rows_of("default", "x.wip", values)), 2.0, ["default"])
    direct = warmup_check(series(rows_of("default", "x.wip", RISING)), 0.0, ["default"])
    assert found[0].samples == 5
    assert (found[0].change, found[0].mean, found[0].half_width) == (
        direct[0].change,
        direct[0].mean,
        direct[0].half_width,
    )


def test_samples_are_taken_in_time_order() -> None:
    rows = rows_of("default", "x.wip", RISING)
    found = warmup_check(series(list(reversed(rows))), 0.0, ["default"])
    assert found == warmup_check(series(rows), 0.0, ["default"])


def test_noise_within_the_half_width_has_not_changed() -> None:
    values = {0: [1.0, 3.0, 1.0, 3.0], 1: [3.0, 1.0, 3.0, 1.0], 2: [2.0, 2.0, 2.0, 2.0]}
    drift = warmup_check(series(rows_of("default", "x.wip", values)), 0.0, ["default"])[0]
    # d_r: 0, 0, 0 for J = 4 (halves [1, 3] and [1, 3] and so on): d-bar 0.
    assert drift.change == 0.0 and drift.half_width == 0.0
    assert not drift.changed


def test_a_change_below_five_percent_has_not_changed() -> None:
    # Every replication rises by 0.04 on a mean of about 1.02: no spread, so the half-width
    # is 0, but 0.04 is below 5% of the mean.
    values = {rep: [1.0, 1.0, 1.04, 1.04] for rep in range(3)}
    drift = warmup_check(series(rows_of("default", "x.wip", values)), 0.0, ["default"])[0]
    assert drift.half_width == 0.0
    assert drift.change == pytest.approx(0.04)
    assert not drift.changed
    values = {rep: [1.0, 1.0, 1.2, 1.2] for rep in range(3)}
    assert warmup_check(series(rows_of("default", "x.wip", values)), 0.0, ["default"])[0].changed


def test_a_constant_series_never_changes() -> None:
    values = {rep: [0.0] * 6 for rep in range(3)}
    drift = warmup_check(series(rows_of("default", "x.wip", values)), 0.0, ["default"])[0]
    assert (drift.change, drift.half_width, drift.mean, drift.changed) == (0.0, 0.0, 0.0, False)


def test_a_zero_mean_is_not_reported_as_changed() -> None:
    """Spec 2 (AKS-102): the change as a percentage of a zero mean is undefined."""
    values = {rep: [-1.0, -1.0, 1.0, 1.0] for rep in range(3)}
    drift = warmup_check(series(rows_of("default", "x.wip", values)), 0.0, ["default"])[0]
    assert drift.mean == 0.0 and drift.change == 2.0 and drift.half_width == 0.0
    assert not drift.changed
    assert drift.percent is None


def test_fewer_than_two_observed_samples_are_skipped() -> None:
    values = {rep: [1.0, 2.0, 3.0] for rep in range(3)}
    assert warmup_check(series(rows_of("default", "x.wip", values)), 2.0, ["default"]) == []
    assert warmup_check(series(rows_of("default", "x.wip", values)), 1.0, ["default"])[0].samples


def test_one_replication_is_skipped() -> None:
    values = {0: [1.0, 2.0, 3.0, 4.0]}
    assert warmup_check(series(rows_of("default", "x.wip", values)), 0.0, ["default"]) == []


def test_unequal_sample_counts_are_refused() -> None:
    values = {0: [1.0, 2.0, 3.0, 4.0], 1: [1.0, 2.0, 3.0]}
    with pytest.raises(ValueError, match="same number of observed samples"):
        warmup_check(series(rows_of("default", "x.wip", values)), 0.0, ["default"])


def test_drifts_follow_scenario_then_row_order() -> None:
    rows = [
        *rows_of("b", "y.utilization", RISING),
        *rows_of("b", "model.wip", RISING),
        *rows_of("a", "model.wip", RISING),
        *rows_of("ignored", "model.wip", RISING),
    ]
    found = warmup_check(series(rows), 0.0, ["a", "b"])
    assert [(drift.scenario, drift.metric) for drift in found] == [
        ("a", "model.wip"),
        ("b", "y.utilization"),
        ("b", "model.wip"),
    ]


# ---------------------------------------------------------------------------------------
# W210


def drift(metric: str, scenario: str, change: float, mean: float, changed: bool) -> Drift:
    return Drift(scenario, metric, 30, 190, change, 0.1, mean, changed)


def test_no_change_gives_no_warning() -> None:
    assert warmup_warning([drift("x.wip", "default", 0.01, 3.0, False)], 0) is None
    assert warmup_warning([], 0) is None


def test_one_w210_lists_every_changed_metric() -> None:
    drifts = [
        drift("till.queue_length", "base", 0.5, 2.0, True),
        drift("till.utilization", "base", 0.001, 0.7, False),
        drift("model.wip", "two", -60.644, 268.81, True),
    ]
    issue = warmup_warning(drifts, 2)
    assert issue is not None
    assert issue.as_dict() == {
        "code": "W210",
        "severity": "warning",
        "component": None,
        "path": "/experiments/2/warmup",
        "message": (
            "Results were still changing after warm-up: till.queue_length in scenario base "
            "changed by 25% of its mean between the first and second halves of the observed "
            "period; model.wip in scenario two changed by 23% of its mean between the first "
            "and second halves of the observed period."
        ),
        "hint": "Lengthen 'warmup' and run again.",
    }


@pytest.mark.parametrize(
    ("change", "percent"), [(0.125, 13), (0.135, 14), (0.0251, 3), (-2.5, 250)]
)
def test_the_percentage_rounds_a_half_up(change: float, percent: int) -> None:
    assert drift("x", "s", change, 1.0, True).percent == percent


# ---------------------------------------------------------------------------------------
# A real run: the research note's slow fill with no warm-up fires; with 50 h it does not


def slow_fill(warmup: str) -> dict[str, Any]:
    return {
        "format_version": "0.1",
        "meta": {"name": "Slow fill"},
        "domain": "process",
        "components": [
            {
                "id": "arrivals",
                "type": "source",
                "params": {"interarrival": {"dist": "exponential", "mean": "2 min"}},
            },
            {
                "id": "travel",
                "type": "delay",
                "params": {"time": {"dist": "exponential", "mean": "10 h"}},
            },
            {"id": "exit", "type": "sink", "params": {}},
        ],
        "connections": [
            {"from": "arrivals.out", "to": "travel.in"},
            {"from": "travel.out", "to": "exit.in"},
        ],
        "experiments": [
            {
                "id": "base",
                "length": "100 h",
                "warmup": warmup,
                "replications": 5,
                "seed": 12345,
                "record_interval": "2 h",
            }
        ],
    }


def run_slow_fill(warmup: str, workdir: Path) -> list[Drift]:
    result = load_document(slow_fill(warmup))
    assert result.issues == ()
    model = result.model
    assert model is not None
    adapter = ProcessAdapter()
    adapter.translate(model, "base", workdir)
    adapter.run(workdir, lambda progress: None, threading.Event(), 1)
    timeseries = adapter.collect(workdir).tables["timeseries"]
    return warmup_check(timeseries, model.experiments[0].warmup.magnitude, ["default"])


def test_the_slow_fill_with_no_warmup_fires(tmp_path: Path) -> None:
    drifts = run_slow_fill("0 s", tmp_path)
    assert [item.metric for item in drifts] == ["model.wip"]
    wip = drifts[0]
    assert wip.samples == 50 and wip.replications == 5
    # Work in progress rises from 0 toward 300 with a 10 h time constant.
    assert wip.change > 0 and wip.changed
    issue = warmup_warning(drifts, 0)
    assert issue is not None and issue.path == "/experiments/0/warmup"
    assert re.fullmatch(
        r"Results were still changing after warm-up: model\.wip in scenario default changed "
        r"by \d+% of its mean between the first and second halves of the observed period\.",
        issue.message,
    )


def test_the_slow_fill_with_a_50_hour_warmup_is_silent(tmp_path: Path) -> None:
    drifts = run_slow_fill("50 h", tmp_path)
    assert drifts[0].samples == 25
    assert warmup_warning(drifts, 0) is None
