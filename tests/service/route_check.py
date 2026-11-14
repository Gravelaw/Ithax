"""The controller's half of the route check under pytest-xdist (#99, P1), called by the plugin
``tests/xdist_routes.py`` once every worker has finished."""

from pathlib import Path

from ithax.service.app import create_app, route_table
from ithax.service.config import ServiceConfig
from ithax.service.hardware import Hardware
from service import route_recorder
from service.endpoint_table import route_problems, spec_table


def controller_route_problems(folder: Path, workers: int) -> list[str]:
    """What the workers' records in ``folder`` fail to show; empty when no worker's coverage
    test handed the check over, or when every row was reached."""
    written, recorded, deferred = route_recorder.read_worker_records(folder)
    if not deferred:
        return []
    if written < workers:
        return [f"only {written} of {workers} pytest-xdist workers wrote a route record"]
    config = ServiceConfig(
        config_dir=folder / "config",
        data_dir=folder / "data",
        port=1,
        token="route-check",
        hardware=Hardware(cores=1, memory=1024**3, graphics=()),
    )
    return route_problems(recorded, spec_table(), route_table(create_app(config)))
