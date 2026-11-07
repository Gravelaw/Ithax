"""The worker (spec 1 "Run targets"; AKS-103): the spawned worker's entry function and
``python -m lcsim.runs.worker <workdir>``, in process and as a real subprocess."""

import io
import json
import multiprocessing
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from dummy_adapters import DummyAdapter, FailingAdapter

from lcsim.engines.process.adapter import REPLICATIONS_FILE, TIMESERIES_FILE, ProcessAdapter
from lcsim.model.loading import load_text
from lcsim.runs import worker
from lcsim.runs.targets import LocalTarget
from lcsim.runs.worker import (
    CANCEL_FILE,
    EXIT_CANCELLED,
    EXIT_DONE,
    EXIT_ERROR,
    EXIT_USAGE,
    FileCancelToken,
    WatchedToken,
    child_main,
    main,
    parent_alive,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def coffee_shop(length: str = "5 h", replications: int = 2) -> bytes:
    document: dict[str, Any] = json.loads(
        (EXAMPLES / "coffee_shop.json").read_text(encoding="utf-8")
    )
    document["experiments"][0].update(
        {"length": length, "warmup": "30 min", "replications": replications}
    )
    return json.dumps(document).encode("utf-8")


def prepared_engine_folder(tmp_path: Path, model_file: bytes) -> Path:
    """A run folder made by the local target, with the process adapter's input translated
    into its ``engine/``, as the remote target will sync it to a host."""
    run = LocalTarget(tmp_path / "runs").create(model_file, "base")
    loaded = load_text(model_file)
    assert loaded.model is not None
    ProcessAdapter().translate(loaded.model, "base", run.engine_folder)
    run.cancel()  # the queued run is not executed here; this releases its lock
    return run.engine_folder


# --- tokens --------------------------------------------------------------------------------


def test_the_file_token_is_set_once_cancel_exists(tmp_path: Path) -> None:
    token = FileCancelToken(tmp_path / CANCEL_FILE, interval=0.0)
    assert not token.is_set()
    (tmp_path / CANCEL_FILE).touch()
    assert token.is_set()
    (tmp_path / CANCEL_FILE).unlink()
    assert token.is_set()  # once set, it stays set


def test_the_file_token_looks_at_the_file_at_most_every_interval(tmp_path: Path) -> None:
    clock = [10.0]
    token = FileCancelToken(tmp_path / CANCEL_FILE, interval=0.5, clock=lambda: clock[0])
    assert not token.is_set()  # looked at once at once
    (tmp_path / CANCEL_FILE).touch()
    clock[0] += 0.25
    assert not token.is_set()  # not looked at again yet
    clock[0] += 0.25
    assert token.is_set()


def test_the_watched_token_is_set_when_the_parent_has_gone() -> None:
    event = threading.Event()
    alive = [True]
    token = WatchedToken(event, lambda: alive[0])
    assert not token.is_set()
    event.set()
    assert token.is_set()
    event.clear()
    alive[0] = False
    assert token.is_set()


def test_the_main_process_has_no_parent_to_lose() -> None:
    assert multiprocessing.parent_process() is None
    assert parent_alive() is True


# --- the spawned worker's function, run in this process --------------------------------


def received(connection: Any) -> list[tuple[Any, ...]]:
    messages = []
    while connection.poll():
        try:
            messages.append(connection.recv())
        except EOFError:  # child_main closed its end
            break
    return messages


def test_child_main_runs_the_adapter_and_reports(tmp_path: Path) -> None:
    (tmp_path / "dummy_input.json").write_text('{"experiment": "base"}', encoding="utf-8")
    receive, send = multiprocessing.Pipe(duplex=False)
    child_main(DummyAdapter, str(tmp_path), threading.Event(), 3, send)
    assert received(receive) == [
        ("progress", 0.5, "Replication 1 of 2"),
        ("progress", 1.0, "Replication 2 of 2"),
        ("finished",),
    ]
    assert json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))["workers"] == 3


def test_child_main_reports_the_traceback_of_an_error(tmp_path: Path) -> None:
    (tmp_path / "dummy_input.json").write_text("{}", encoding="utf-8")
    receive, send = multiprocessing.Pipe(duplex=False)
    child_main(FailingAdapter, str(tmp_path), threading.Event(), 1, send)
    [(kind, details)] = received(receive)
    assert kind == "error"
    assert "Traceback" in details and "secret engine detail 4711" in details


# --- python -m lcsim.runs.worker, in this process ----------------------------------------


def test_main_runs_the_installed_adapter_named_in_the_manifest(tmp_path: Path) -> None:
    engine = prepared_engine_folder(tmp_path, coffee_shop())
    out, err = io.StringIO(), io.StringIO()
    assert main([str(engine), "--workers", "1"], stdout=out, stderr=err) == EXIT_DONE
    assert err.getvalue() == ""
    lines = [json.loads(line) for line in out.getvalue().splitlines()]
    assert lines == [
        {"type": "progress", "fraction": 0.5, "message": "Scenario 1 of 1, replication 1 of 2"},
        {"type": "progress", "fraction": 1.0, "message": "Scenario 1 of 1, replication 2 of 2"},
    ]
    assert (engine / REPLICATIONS_FILE).is_file() and (engine / TIMESERIES_FILE).is_file()


def test_main_returns_cancelled_when_cancel_exists(tmp_path: Path) -> None:
    engine = prepared_engine_folder(tmp_path, coffee_shop())
    (engine / CANCEL_FILE).touch()
    out = io.StringIO()
    assert main([str(engine)], stdout=out, stderr=io.StringIO()) == EXIT_CANCELLED
    assert out.getvalue() == ""
    assert not (engine / REPLICATIONS_FILE).exists()


def test_main_reports_an_adapter_error_on_stderr(tmp_path: Path) -> None:
    engine = prepared_engine_folder(tmp_path, coffee_shop())
    (engine / "dummy_input.json").write_text("{}", encoding="utf-8")
    manifest = engine.parent / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["engine"]["name"] = "dummy"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    err = io.StringIO()
    code = main(
        [str(engine)], stdout=io.StringIO(), stderr=err, adapters={"dummy": FailingAdapter()}
    )
    assert code == EXIT_ERROR
    assert "Traceback" in err.getvalue() and "secret engine detail 4711" in err.getvalue()


def test_main_refuses_what_it_cannot_use(tmp_path: Path) -> None:
    err = io.StringIO()
    assert main([str(tmp_path / "engine")], stdout=io.StringIO(), stderr=err) == EXIT_USAGE
    assert "manifest.json" in err.getvalue()

    engine = prepared_engine_folder(tmp_path, coffee_shop())
    err = io.StringIO()
    assert main([str(engine), "--workers", "0"], stdout=io.StringIO(), stderr=err) == EXIT_USAGE
    assert "--workers" in err.getvalue()

    err = io.StringIO()
    assert main([str(engine)], stdout=io.StringIO(), stderr=err, adapters={}) == EXIT_USAGE
    assert "'simpy' is not installed" in err.getvalue()

    for broken in ('{"engine": 3}', '{"engine": {"name": 3}}', "not json"):
        (engine.parent / "manifest.json").write_text(broken, encoding="utf-8")
        err = io.StringIO()
        assert main([str(engine)], stdout=io.StringIO(), stderr=err) == EXIT_USAGE
        assert "cannot read the engine name" in err.getvalue()


def test_main_writes_to_the_process_streams_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(tmp_path / "engine")]) == EXIT_USAGE
    assert "manifest.json" in capsys.readouterr().err


# --- python -m lcsim.runs.worker, as a real subprocess ---------------------------------


def test_the_module_runs_as_a_subprocess(tmp_path: Path) -> None:
    engine = prepared_engine_folder(tmp_path, coffee_shop())
    before = sorted(path.name for path in engine.parent.iterdir())
    finished = subprocess.run(
        [sys.executable, "-m", "lcsim.runs.worker", str(engine), "--workers", "2"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert finished.returncode == EXIT_DONE, finished.stderr
    lines = [json.loads(line) for line in finished.stdout.splitlines()]
    assert [line["fraction"] for line in lines] == [0.5, 1.0]
    assert (engine / REPLICATIONS_FILE).is_file()
    # The worker wrote nothing in the run folder outside engine/.
    assert sorted(path.name for path in engine.parent.iterdir()) == before


def test_the_subprocess_stops_soon_after_cancel_appears(tmp_path: Path) -> None:
    engine = prepared_engine_folder(tmp_path, coffee_shop(length="2000 h", replications=30))
    process = subprocess.Popen(
        [sys.executable, "-m", "lcsim.runs.worker", str(engine)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        first = json.loads(process.stdout.readline())  # running: one replication is done
        assert first["type"] == "progress" and first["fraction"] < 1
        cancelled_at = time.monotonic()
        (engine / CANCEL_FILE).touch()
        assert process.wait(timeout=30) == EXIT_CANCELLED
        assert time.monotonic() - cancelled_at < 2.0
    finally:
        process.kill()
        process.communicate()
    assert not (engine / REPLICATIONS_FILE).exists()


def test_the_module_guards_its_entry_point() -> None:
    source = Path(worker.__file__).read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":\n    raise SystemExit(main())\n' in source
