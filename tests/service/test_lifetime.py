"""The service's lifetime (spec 3 "Lifetime", proposed default; AKS-78 open; AKS-110)."""

import asyncio
import dataclasses
import threading

import pytest
from starlette.testclient import TestClient

from ithax.service.app import create_app
from ithax.service.config import DEFAULT_IDLE_TIMEOUT_S, ServiceConfig
from ithax.service.lifetime import Lifetime, watch
from service.service_support import AUTH, BASE_URL


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_default_limit_is_30_minutes() -> None:
    assert DEFAULT_IDLE_TIMEOUT_S == 1800.0


def test_idle_time_counts_from_the_last_activity() -> None:
    clock = Clock()
    lifetime = Lifetime(1800, clock)
    clock.now += 1799
    assert lifetime.idle_for() == 1799
    assert not lifetime.expired()
    clock.now += 1
    assert lifetime.expired()
    lifetime.touch()
    assert lifetime.idle_for() == 0
    assert not lifetime.expired()


def test_a_hold_keeps_the_service_up_and_restarts_the_count() -> None:
    clock = Clock()
    lifetime = Lifetime(10, clock)
    with lifetime.hold():
        with lifetime.hold():
            assert lifetime.holds == 2
            clock.now += 100
            assert lifetime.idle_for() == 0
            assert not lifetime.expired()
        assert lifetime.holds == 1
        assert not lifetime.expired()
    assert lifetime.holds == 0
    assert lifetime.idle_for() == 0
    clock.now += 10
    assert lifetime.expired()


def test_a_hold_ends_even_when_its_block_fails() -> None:
    lifetime = Lifetime(10, Clock())
    with pytest.raises(RuntimeError), lifetime.hold():
        raise RuntimeError("the run failed")
    assert lifetime.holds == 0


def test_the_limit_must_be_above_zero() -> None:
    with pytest.raises(ValueError, match="above 0"):
        Lifetime(0)


def test_watch_calls_on_idle_once_when_expired() -> None:
    clock = Clock()
    lifetime = Lifetime(5, clock)
    calls: list[float] = []

    async def scenario() -> None:
        task = asyncio.create_task(watch(lifetime, 0.001, lambda: calls.append(clock.now)))
        await asyncio.sleep(0.01)
        assert calls == []
        clock.now += 5
        await asyncio.wait_for(task, 1)

    asyncio.run(scenario())
    assert calls == [1005.0]


def test_requests_hold_and_touch_the_lifetime(config: ServiceConfig) -> None:
    clock = Clock()
    app = create_app(dataclasses.replace(config, clock=clock))
    lifetime = app.state.service.lifetime
    clock.now += 600
    assert lifetime.idle_for() == 600
    with TestClient(app, base_url=BASE_URL, headers=AUTH) as client:
        client.get("/v1/system")
    assert lifetime.idle_for() == 0
    assert lifetime.holds == 0


def test_a_request_without_the_token_does_not_keep_the_service_up(
    config: ServiceConfig,
) -> None:
    clock = Clock()
    app = create_app(dataclasses.replace(config, clock=clock))
    with TestClient(app, base_url=BASE_URL) as client:
        clock.now += 600
        assert client.get("/v1/system").status_code == 401
    assert app.state.service.lifetime.idle_for() == 600


def test_the_app_calls_on_idle_after_its_idle_limit(config: ServiceConfig) -> None:
    idle = threading.Event()
    quick = dataclasses.replace(config, idle_timeout_s=0.05, idle_check_s=0.01, on_idle=idle.set)
    with TestClient(create_app(quick), base_url=BASE_URL, headers=AUTH):
        assert idle.wait(5)


def test_without_on_idle_nothing_is_watched(config: ServiceConfig) -> None:
    quick = dataclasses.replace(config, idle_timeout_s=0.01, idle_check_s=0.001)
    with TestClient(create_app(quick), base_url=BASE_URL, headers=AUTH) as client:
        assert client.get("/v1/system").status_code == 200


def test_the_idle_count_starts_when_the_service_starts_serving(config: ServiceConfig) -> None:
    """A slow start (here longer than the limit, between building the app and serving)
    is not idleness: the count starts when serving starts, so the service never exits at
    its first check, just after publishing service.json (CI failure on PR #35: a 1.2 s
    limit, a slow runner and a refused connection)."""
    clock = Clock()
    idle = threading.Event()
    app = create_app(
        dataclasses.replace(
            config, clock=clock, idle_timeout_s=10, idle_check_s=0.01, on_idle=idle.set
        )
    )
    clock.now += 60
    with TestClient(app, base_url=BASE_URL, headers=AUTH):
        assert not idle.wait(0.2)
        assert app.state.service.lifetime.idle_for() == 0
        clock.now += 10
        assert idle.wait(5)
