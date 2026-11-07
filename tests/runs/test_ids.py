"""``run_id`` (spec 1 "Run folder and results"; AKS-103)."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from lcsim.runs.ids import RUN_ID_PATTERN, new_run_id


def test_a_run_id_is_the_utc_time_and_six_base32_characters() -> None:
    moment = datetime(2026, 11, 6, 18, 5, 9, 999999, tzinfo=UTC)
    run_id = new_run_id(moment)
    assert run_id.startswith("20261106T180509-")
    assert RUN_ID_PATTERN.fullmatch(run_id)
    assert len(run_id) == 22


def test_a_time_in_another_zone_is_written_in_utc() -> None:
    moment = datetime(2026, 11, 6, 20, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    assert new_run_id(moment).startswith("20261106T180000-")


def test_a_naive_time_is_refused() -> None:
    with pytest.raises(ValueError, match="UTC"):
        new_run_id(datetime(2026, 11, 6))


def test_the_characters_come_from_the_operating_system_generator() -> None:
    moment = datetime(2026, 11, 6, tzinfo=UTC)
    seen = {new_run_id(moment)[-6:] for _ in range(200)}
    # 30 random bits: 200 draws all differ unless the generator is broken.
    assert len(seen) == 200
    assert all(set(text) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567") for text in seen)
