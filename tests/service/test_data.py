"""The data endpoints (spec 3 "Endpoints", the data rows and notes, "Project folder";
AKS-113): ``POST``/``GET /v1/projects/{pid}/data``, ``DELETE .../data/{file}`` and
``POST .../data/{file}/fit``, the column index, and a run that uses ``empirical`` ``data``.
"""

import hashlib
import io
import json
import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from lcsim.model import data_files
from lcsim.model.data import INDEX_FILE
from lcsim.runs.manifest import read_manifest
from lcsim.service import data as data_routes
from lcsim.service.app import create_app
from lcsim.service.config import ServiceConfig
from lcsim.service.projects_store import PROJECT_FILE
from lcsim.service.state import ServiceState
from service.service_support import AUTH, BASE_URL, assert_error

Json = dict[str, Any]
ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_S = 120.0

GAPS = "time,gap_min\n08:00:12,1.8\n08:02:40,2.5\n08:03:05,0.4\n08:06:51,3.8\n08:07:30,0.7\n"


@pytest.fixture
def client(config: ServiceConfig) -> Iterator[TestClient]:
    with TestClient(create_app(config), base_url=BASE_URL, headers=AUTH) as test_client:
        yield test_client


def state_of(client: TestClient) -> ServiceState:
    app = client.app
    assert isinstance(app, FastAPI)
    state = app.state.service
    assert isinstance(state, ServiceState)
    return state


def project(client: TestClient) -> str:
    response = client.post("/v1/projects", json={"name": "Shop"})
    assert response.status_code == 200, response.text
    pid: str = response.json()["id"]
    return pid


def folder_of(client: TestClient, pid: str) -> Path:
    return state_of(client).projects.folder(pid)


def upload(
    client: TestClient,
    pid: str,
    name: str = "arrivals.csv",
    raw: bytes = GAPS.encode(),
    units: object = None,
    *,
    content_type: str = "text/csv",
) -> Any:
    form = (
        {} if units is None else {"units": units if isinstance(units, str) else json.dumps(units)}
    )
    return client.post(
        f"/v1/projects/{pid}/data", files={"file": (name, raw, content_type)}, data=form
    )


def xlsx(*rows: tuple[object, ...]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Log"
    for row in rows:
        sheet.append(list(row))
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


def refusal(response: Any, status: int, code: str, path: str | None = None) -> Json:
    assert response.status_code == status, response.text
    body: Json = response.json()
    assert_error(body, code)
    if path is not None:
        assert [issue["path"] for issue in body["issues"]] == [path], body
        assert all(issue["code"] == code for issue in body["issues"])
    assert "Traceback" not in response.text and "Error:" not in response.text
    return body


def data_listing(folder: Path) -> list[str]:
    return sorted(path.name for path in (folder / "data").iterdir())


# --- POST .../data ---------------------------------------------------------------------


def test_an_uploaded_csv_gives_columns_types_units_and_a_preview(client: TestClient) -> None:
    pid = project(client)
    response = upload(client, pid, units={"gap_min": "min"})
    assert response.status_code == 200, response.text
    body = response.json()
    raw = GAPS.encode()
    assert body["name"] == "arrivals.csv"
    assert body["format"] == "csv" and body["sheet"] is None
    assert body["size"] == len(raw)
    assert body["sha256"] == hashlib.sha256(raw).hexdigest()
    assert body["imported"].endswith("Z")
    assert body["rows"] == 5
    assert body["columns"] == [
        {"name": "time", "type": "text", "unit": None, "largest": None},
        {"name": "gap_min", "type": "number", "unit": "min", "largest": 3.8},
    ]
    assert body["preview"][:2] == [["08:00:12", 1.8], ["08:02:40", 2.5]]
    folder = folder_of(client, pid)
    # Imported unchanged, plus the column index.
    assert (folder / "data" / "arrivals.csv").read_bytes() == raw
    index = json.loads((folder / "data" / INDEX_FILE).read_text(encoding="utf-8"))
    entry = {key: value for key, value in body.items() if key != "preview"}
    assert index == {"index_version": 1, "files": [entry]}
    assert data_listing(folder) == ["arrivals.csv", INDEX_FILE]


def test_an_uploaded_excel_file_gives_a_column_index_with_units(client: TestClient) -> None:
    pid = project(client)
    raw = xlsx(("machine", "repair_h"), ("A", 1.5), ("B", 2), ("C", 0.5))
    response = upload(
        client, pid, "repairs.xlsx", raw, {"repair_h": "h"}, content_type="application/octet-stream"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["format"] == "xlsx" and body["sheet"] == "Log"
    assert body["columns"] == [
        {"name": "machine", "type": "text", "unit": None, "largest": None},
        {"name": "repair_h", "type": "number", "unit": "h", "largest": 2.0},
    ]
    assert body["preview"] == [["A", 1.5], ["B", 2.0], ["C", 0.5]]
    assert client.get(f"/v1/projects/{pid}/data").json()[0]["columns"][1]["unit"] == "h"


def test_a_unit_may_be_null_and_columns_left_out_have_none(client: TestClient) -> None:
    pid = project(client)
    response = upload(client, pid, units={"gap_min": None})
    assert response.status_code == 200, response.text
    assert [column["unit"] for column in response.json()["columns"]] == [None, None]


def test_importing_a_name_again_replaces_it_in_place(client: TestClient) -> None:
    pid = project(client)
    upload(client, pid, "a.csv", b"x\n1\n")
    upload(client, pid, "b.csv", b"y\n2\n")
    again = upload(client, pid, "a.csv", b"x\n1\n5\n", {"x": "s"})
    assert again.status_code == 200, again.text
    listed = client.get(f"/v1/projects/{pid}/data").json()
    assert [entry["name"] for entry in listed] == ["a.csv", "b.csv"]
    assert listed[0]["rows"] == 2 and listed[0]["columns"][0]["unit"] == "s"
    assert (folder_of(client, pid) / "data" / "a.csv").read_bytes() == b"x\n1\n5\n"


def test_a_windows_path_sent_as_the_file_name_is_reduced_to_its_last_part(
    client: TestClient,
) -> None:
    """python-multipart keeps only the last part of a name such as ``C:\\data\\a.csv`` or
    ``\\\\server\\a.csv``, as old browsers sent the whole path (spec 3 data notes)."""
    pid = project(client)
    response = upload(client, pid, "C:\\data\\a.csv", b"x\n1\n")
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "a.csv"
    assert data_listing(folder_of(client, pid)) == ["a.csv", INDEX_FILE]


def test_a_name_that_differs_only_in_case_is_refused(client: TestClient) -> None:
    pid = project(client)
    upload(client, pid, "a.csv", b"x\n1\n")
    refusal(upload(client, pid, "A.CSV", b"x\n2\n"), 400, "E184", "/file")
    assert data_listing(folder_of(client, pid)) == ["a.csv", INDEX_FILE]


@pytest.mark.parametrize(
    "name",
    ["../escape.csv", "sub/a.csv", "sub\\a.csv", "con.csv", "a.txt", "", ".a.csv", "\u00e4.csv"],
)
def test_a_file_name_the_naming_rule_refuses_is_e184_and_saves_nothing(
    client: TestClient, name: str
) -> None:
    pid = project(client)
    response = upload(client, pid, name, b"x\n1\n")
    if name == "":
        # Without a file name the part is a field, not a file.
        refusal(response, 400, "E184")
    else:
        refusal(response, 400, "E184", "/file")
    folder = folder_of(client, pid)
    assert data_listing(folder) == []
    assert not (folder.parent / "escape.csv").exists()


@pytest.mark.parametrize(
    "raw",
    [b"", "gap\n1\n".encode("utf-16"), b"a,a\n1,2\n", b"a,b\n1,2,3\n", b"1,2\n3,4\n"],
)
def test_a_file_that_cannot_be_imported_is_e189_and_keeps_the_previous_files(
    client: TestClient, raw: bytes
) -> None:
    pid = project(client)
    upload(client, pid, "keep.csv", b"x\n1\n")
    before = client.get(f"/v1/projects/{pid}/data").json()
    refusal(upload(client, pid, "new.csv", raw), 400, "E189", "/file")
    refusal(upload(client, pid, "keep.csv", raw), 400, "E189", "/file")
    assert client.get(f"/v1/projects/{pid}/data").json() == before
    assert (folder_of(client, pid) / "data" / "keep.csv").read_bytes() == b"x\n1\n"


@pytest.mark.parametrize("raw", [b"not a zip", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(600)])
def test_a_workbook_that_cannot_be_read_is_e189(client: TestClient, raw: bytes) -> None:
    pid = project(client)
    body = refusal(upload(client, pid, "a.xlsx", raw), 400, "E189", "/file")
    assert "Excel" in body["error"]["message"]


def test_a_file_above_the_size_limit_is_e189(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = project(client)
    monkeypatch.setattr(data_files, "MAX_FILE_BYTES", 10)
    refusal(upload(client, pid, "a.csv", b"x\n1\n2\n3\n4\n5\n"), 400, "E189", "/file")
    assert data_listing(folder_of(client, pid)) == []


def test_a_request_above_the_size_limit_is_refused_while_it_is_read(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = project(client)
    monkeypatch.setattr(data_routes, "MAX_REQUEST_BYTES", 300)
    body = b"x\n" + b"1\n" * 400

    def chunks() -> Iterator[bytes]:  # no Content-Length: the limit applies while reading
        head = (
            b'--b\r\nContent-Disposition: form-data; name="file"; filename="a.csv"\r\n'
            b"Content-Type: text/csv\r\n\r\n"
        )
        yield head
        yield body
        yield b"\r\n--b--\r\n"

    response = client.post(
        f"/v1/projects/{pid}/data",
        content=chunks(),
        headers={"Content-Type": "multipart/form-data; boundary=b"},
    )
    refusal(response, 400, "E189", "/file")
    big = client.post(
        f"/v1/projects/{pid}/data",
        files={"file": ("a.csv", body, "text/csv")},
    )
    refusal(big, 400, "E189", "/file")
    assert data_listing(folder_of(client, pid)) == []


@pytest.mark.parametrize(
    ("request_kwargs", "path"),
    [
        ({"json": {"file": "a.csv"}}, ""),
        ({"content": b"x", "headers": {"Content-Type": "multipart/form-data"}}, ""),
        (
            {"content": b"garbage", "headers": {"Content-Type": "multipart/form-data; boundary=b"}},
            None,
        ),
        ({"files": {"data": ("a.csv", b"x\n1\n", "text/csv")}}, "/data"),
        ({"data": {"file": "a.csv"}}, ""),
        ({"files": {"file": (None, b"a.csv")}}, "/file"),
        ({"files": {"units": (None, b"{}")}}, "/file"),
        (
            {
                "files": [
                    ("file", ("a.csv", b"x\n1\n", "text/csv")),
                    ("file", ("b.csv", b"x\n1\n", "text/csv")),
                ]
            },
            "",
        ),
        ({"files": {"file": ("a.csv", b"x\n1\n", "text/csv")}, "data": {"other": "1"}}, "/other"),
    ],
)
def test_a_malformed_form_is_e184(
    client: TestClient, request_kwargs: dict[str, Any], path: str | None
) -> None:
    pid = project(client)
    response = client.post(f"/v1/projects/{pid}/data", **request_kwargs)
    refusal(response, 400, "E184", path)
    assert data_listing(folder_of(client, pid)) == []


@pytest.mark.parametrize(
    ("units", "path"),
    [
        ("not json", "/units"),
        ("[1]", "/units"),
        ('{"gap_min": NaN}', "/units"),
        ({"gap_min": "ms"}, "/units/gap_min"),
        ({"gap_min": 5}, "/units/gap_min"),
        ({"nope": "min"}, "/units/nope"),
        ({"time": "min"}, "/units/time"),
    ],
)
def test_units_that_cannot_be_used_are_e184(client: TestClient, units: object, path: str) -> None:
    pid = project(client)
    refusal(upload(client, pid, units=units), 400, "E184", path)
    assert data_listing(folder_of(client, pid)) == []


def test_an_unknown_project_is_404_and_an_unreadable_one_e186(client: TestClient) -> None:
    unknown = "00000000-0000-4000-8000-000000000000"
    refusal(upload(client, unknown), 404, "E185")
    refusal(client.get(f"/v1/projects/{unknown}/data"), 404, "E185")
    refusal(client.delete(f"/v1/projects/{unknown}/data/a.csv"), 404, "E185")
    refusal(
        client.post(f"/v1/projects/{unknown}/data/a.csv/fit", json={"column": "x"}), 404, "E185"
    )
    pid = project(client)
    (folder_of(client, pid) / PROJECT_FILE).write_text("{", encoding="utf-8")
    refusal(upload(client, pid), 400, "E186")
    refusal(client.get(f"/v1/projects/{pid}/data"), 400, "E186")


def test_a_failed_commit_puts_the_previous_file_back(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = project(client)
    upload(client, pid, "a.csv", b"x\n1\n")
    folder = folder_of(client, pid)
    before = {name: (folder / "data" / name).read_bytes() for name in data_listing(folder)}
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        if Path(target).name == INDEX_FILE:
            raise PermissionError("denied")
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    response = upload(client, pid, "a.csv", b"x\n9\n")
    monkeypatch.undo()
    body = refusal(response, 400, "E186")
    assert "denied" not in json.dumps(body)
    after = {name: (folder / "data" / name).read_bytes() for name in data_listing(folder)}
    assert after == before


def test_an_import_is_saved_while_the_project_s_writes_are_held(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """So no model write or run creation sees half an import."""
    pid = project(client)
    lock = state_of(client).models._lock_for(pid)
    held: list[bool] = []
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        outcome: list[bool] = []
        probe = threading.Thread(target=lambda: outcome.append(lock.acquire(blocking=False)))
        probe.start()
        probe.join()
        if outcome[0]:
            lock.release()
        held.append(not outcome[0])
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    assert upload(client, pid).status_code == 200
    monkeypatch.undo()
    assert held == [True, True]


def test_a_data_folder_that_is_missing_is_made_again(client: TestClient) -> None:
    pid = project(client)
    (folder_of(client, pid) / "data").rmdir()
    assert client.get(f"/v1/projects/{pid}/data").json() == []
    assert upload(client, pid).status_code == 200


# --- GET .../data ----------------------------------------------------------------------


def test_the_list_holds_the_files_in_the_order_first_imported(client: TestClient) -> None:
    pid = project(client)
    assert client.get(f"/v1/projects/{pid}/data").json() == []
    first = upload(client, pid, "z.csv", b"x\n1\n").json()
    second = upload(client, pid, "a.csv", b"y\n2\n").json()
    listed = client.get(f"/v1/projects/{pid}/data").json()
    assert listed == [
        {key: value for key, value in entry.items() if key != "preview"}
        for entry in (first, second)
    ]


def test_an_index_that_cannot_be_read_lists_nothing_and_is_replaced(client: TestClient) -> None:
    pid = project(client)
    upload(client, pid, "a.csv", b"x\n1\n")
    index = folder_of(client, pid) / "data" / INDEX_FILE
    index.write_text('{"index_version": 1, "files": [NaN]}', encoding="utf-8")
    assert client.get(f"/v1/projects/{pid}/data").json() == []
    upload(client, pid, "b.csv", b"y\n1\n")
    assert [entry["name"] for entry in client.get(f"/v1/projects/{pid}/data").json()] == ["b.csv"]


# --- DELETE .../data/{file} -------------------------------------------------------------


def test_delete_removes_the_file_and_its_entry(client: TestClient) -> None:
    pid = project(client)
    upload(client, pid, "a.csv", b"x\n1\n")
    kept = upload(client, pid, "b.csv", b"y\n2\n").json()
    response = client.delete(f"/v1/projects/{pid}/data/a.csv")
    assert response.status_code == 200, response.text
    expected = [{key: value for key, value in kept.items() if key != "preview"}]
    assert response.json() == expected
    assert client.get(f"/v1/projects/{pid}/data").json() == expected
    assert data_listing(folder_of(client, pid)) == ["b.csv", INDEX_FILE]


@pytest.mark.parametrize("name", ["missing.csv", "A.csv", "index.json", "..", "%2E%2E"])
def test_delete_of_a_name_not_in_the_index_is_404(client: TestClient, name: str) -> None:
    pid = project(client)
    upload(client, pid, "a.csv", b"x\n1\n")
    refusal(client.delete(f"/v1/projects/{pid}/data/{name}"), 404, "E185")
    assert data_listing(folder_of(client, pid)) == ["a.csv", INDEX_FILE]


def test_a_file_whose_removal_fails_after_the_commit_is_logged(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    pid = project(client)
    upload(client, pid, "a.csv", b"x\n1\n")
    real = Path.unlink

    def unlink(self: Path, missing_ok: bool = False) -> None:
        if self.name == "a.csv":
            raise PermissionError("denied")
        real(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    response = client.delete(f"/v1/projects/{pid}/data/a.csv")
    monkeypatch.undo()
    assert response.status_code == 200 and response.json() == []
    assert "could not be removed" in caplog.text


def test_a_delete_whose_commit_fails_changes_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = project(client)
    upload(client, pid, "a.csv", b"x\n1\n")
    before = client.get(f"/v1/projects/{pid}/data").json()

    def replace(source: Any, target: Any) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(os, "replace", replace)
    response = client.delete(f"/v1/projects/{pid}/data/a.csv")
    monkeypatch.undo()
    refusal(response, 400, "E186")
    assert client.get(f"/v1/projects/{pid}/data").json() == before
    assert data_listing(folder_of(client, pid)) == ["a.csv", INDEX_FILE]


# --- POST .../data/{file}/fit ----------------------------------------------------------


def exponential_column(count: int = 300) -> bytes:
    from lcsim.model.distributions import sampler_from_numbers
    from lcsim.model.streams import generator_for

    sampler = sampler_from_numbers("exponential", {"mean": 2.0})
    rng = generator_for(1, 0, "column")
    values = [round(sampler(rng), 4) for _ in range(count)]
    return ("gap\n" + "".join(f"{value}\n" for value in values)).encode()


def test_the_fit_returns_spec_1_candidates_best_first(client: TestClient) -> None:
    pid = project(client)
    upload(client, pid, "gaps.csv", exponential_column(), {"gap": "min"})
    response = client.post(f"/v1/projects/{pid}/data/gaps.csv/fit", json={"column": "gap"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["file"] == "gaps.csv" and body["column"] == "gap" and body["unit"] == "min"
    assert body["values"] == 300 and body["score"] == "ks"
    names = [candidate["distribution"]["dist"] for candidate in body["candidates"]]
    assert set(names) == {"exponential", "uniform", "triangular", "normal", "lognormal", "weibull"}
    scores = [candidate["score"] for candidate in body["candidates"]]
    assert scores == sorted(scores)
    best = body["candidates"][0]["distribution"]
    assert best["dist"] in ("exponential", "weibull")
    # A candidate is a distribution set_setting takes as it is.
    model = json.loads((ROOT / "examples" / "coffee_shop.json").read_text())
    assert client.put(f"/v1/projects/{pid}/model", content=json.dumps(model)).status_code == 200
    for candidate in body["candidates"]:
        edit = {
            "edit": "set_setting",
            "id": "arrivals",
            "path": "/interarrival",
            "value": candidate["distribution"],
        }
        saved = client.post(f"/v1/projects/{pid}/model/edits", json={"edits": [edit]})
        assert saved.status_code == 200, saved.text
        errors = [issue for issue in saved.json()["issues"] if issue["severity"] == "error"]
        assert errors == [], candidate


def test_a_constant_column_gives_constant(client: TestClient) -> None:
    pid = project(client)
    upload(client, pid, "c.csv", b"t\n2\n2\n2\n", {"t": "h"})
    body = client.post(f"/v1/projects/{pid}/data/c.csv/fit", json={"column": "t"}).json()
    assert body["candidates"] == [
        {"distribution": {"dist": "constant", "value": "2.0 h"}, "score": 0.0}
    ]


def test_the_fit_of_an_excel_column(client: TestClient) -> None:
    pid = project(client)
    upload(client, pid, "r.xlsx", xlsx(("r",), (1.0,), (2.0,), (4.0,)), {"r": "h"})
    body = client.post(f"/v1/projects/{pid}/data/r.xlsx/fit", json={"column": "r"}).json()
    assert body["values"] == 3 and body["candidates"]


def test_fit_refusals(client: TestClient) -> None:
    pid = project(client)
    upload(client, pid, units={"gap_min": "min"})
    fit = f"/v1/projects/{pid}/data/arrivals.csv/fit"
    refusal(
        client.post(f"/v1/projects/{pid}/data/other.csv/fit", json={"column": "x"}), 404, "E185"
    )
    refusal(client.post(fit, json={"column": "nope"}), 400, "E184", "/column")
    refusal(client.post(fit, json={"column": "time"}), 400, "E189", "/column")
    refusal(client.post(fit, json={"column": "gap_min", "extra": 1}), 400, "E184", "/extra")
    refusal(client.post(fit, json={"column": 3}), 400, "E184", "/column")
    refusal(client.post(fit, json={}), 400, "E184", "/column")
    refusal(client.post(fit, content=b"not json"), 400, "E184")
    lone = client.post(
        fit, content=b'{"column": "\\ud800"}', headers={"Content-Type": "application/json"}
    )
    refusal(lone, 400, "E184", "/column")
    data = folder_of(client, pid) / "data" / "arrivals.csv"
    data.write_bytes(GAPS.encode() + b"08:09:00,1.0\n")
    refusal(client.post(fit, json={"column": "gap_min"}), 400, "E189", "/file")
    data.unlink()
    refusal(client.post(fit, json={"column": "gap_min"}), 400, "E189", "/file")


def test_an_empty_column_cannot_be_fitted(client: TestClient) -> None:
    pid = project(client)
    upload(client, pid, "e.csv", b"a,b\n1,\n")
    body = refusal(
        client.post(f"/v1/projects/{pid}/data/e.csv/fit", json={"column": "b"}),
        400,
        "E189",
        "/column",
    )
    assert "no values" in body["error"]["message"]


# --- a run that uses data --------------------------------------------------------------


def wait_until_final(client: TestClient, rid: str) -> Json:
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        run: Json = client.get(f"/v1/runs/{rid}").json()
        if run["state"] in ("done", "failed", "cancelled"):
            return run
        time.sleep(0.05)
    raise AssertionError(f"the run {rid} did not finish")


def breakdown() -> Json:
    model: Json = json.loads((ROOT / "benchmarks" / "failure" / "model.json").read_text())
    model["experiments"][0].update(length="4 h", warmup="0 s", replications=2)
    params = model["components"][2]["params"]
    params["time_to_failure"] = {"dist": "empirical", "data": {"file": "log.csv", "column": "up_h"}}
    params["time_to_repair"] = {
        "dist": "empirical",
        "data": {"file": "log.csv", "column": "down_min"},
    }
    return model


def test_a_run_with_two_data_distributions_on_one_component(client: TestClient) -> None:
    pid = project(client)
    log = b"up_h,down_min\n1.5,20\n2,35\n0.75,10\n"
    upload(client, pid, "log.csv", log, {"up_h": "h", "down_min": "min"})
    put = client.put(f"/v1/projects/{pid}/model", content=json.dumps(breakdown()))
    assert put.status_code == 200 and put.json()["issues"] == [], put.text
    assert client.post(f"/v1/projects/{pid}/validate").json()["issues"] == []
    started = client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "benchmark"})
    assert started.status_code == 202, started.text
    rid = started.json()["run_id"]
    assert wait_until_final(client, rid)["state"] == "done"
    folder = folder_of(client, pid) / "runs" / rid
    assert sorted(path.name for path in (folder / "data").iterdir()) == [
        "breakdown.time_to_failure.parquet",
        "breakdown.time_to_repair.parquet",
    ]
    digest = hashlib.sha256(log).hexdigest()
    assert read_manifest(folder)["data_files"] == [
        {
            "component": "breakdown",
            "setting": name,
            "file": "log.csv",
            "column": column,
            "sha256": digest,
        }
        for name, column in (("time_to_failure", "up_h"), ("time_to_repair", "down_min"))
    ]
    # Changing the file afterwards: validation reports E162, and a new run is refused.
    (folder_of(client, pid) / "data" / "log.csv").write_bytes(log + b"1,5\n")
    issues = client.post(f"/v1/projects/{pid}/validate").json()["issues"]
    assert [issue["code"] for issue in issues] == ["E162", "E162"]
    refused = client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "benchmark"})
    refusal(refused, 422, "E162")
    # The run already made keeps its snapshots.
    assert len(list((folder / "data").iterdir())) == 2
    # Its summary and findings do not depend on the project's data either (AKS-135): the
    # rules read the run folder's model without checking its data references again.
    summary = client.get(f"/v1/runs/{rid}/summary")
    assert summary.status_code == 200, summary.text
    assert isinstance(summary.json()["findings"], list)
    assert client.delete(f"/v1/projects/{pid}/data/log.csv").status_code == 200
    assert client.get(f"/v1/runs/{rid}/summary").json() == summary.json()


def test_removing_a_file_the_model_names_is_allowed_and_validation_reports_it(
    client: TestClient,
) -> None:
    pid = project(client)
    upload(client, pid, "log.csv", b"up_h,down_min\n1.5,20\n", {"up_h": "h", "down_min": "min"})
    client.put(f"/v1/projects/{pid}/model", content=json.dumps(breakdown()))
    assert client.delete(f"/v1/projects/{pid}/data/log.csv").status_code == 200
    issues = client.post(f"/v1/projects/{pid}/validate").json()["issues"]
    assert [(issue["code"], issue["path"]) for issue in issues] == [
        ("E162", "/components/2/params/time_to_failure/data/file"),
        ("E162", "/components/2/params/time_to_repair/data/file"),
    ]


def test_a_run_reads_the_data_while_the_project_s_writes_are_held(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """So an import cannot replace a file between the run's check and its copy."""
    pid = project(client)
    upload(client, pid, "log.csv", b"up_h,down_min\n1.5,20\n", {"up_h": "h", "down_min": "min"})
    client.put(f"/v1/projects/{pid}/model", content=json.dumps(breakdown()))
    state = state_of(client)
    lock = state.models._lock_for(pid)
    held: list[bool] = []
    from lcsim.runs import snapshots, targets

    real = snapshots.read_columns

    def read_columns(*args: Any, **kwargs: Any) -> Any:
        outcome: list[bool] = []
        probe = threading.Thread(target=lambda: outcome.append(lock.acquire(blocking=False)))
        probe.start()
        probe.join()
        if outcome[0]:
            lock.release()
        held.append(not outcome[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(targets, "read_columns", read_columns)
    started = client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "benchmark"})
    assert started.status_code == 202, started.text
    assert held == [True]
    wait_until_final(client, started.json()["run_id"])


def test_a_data_folder_that_cannot_be_made_is_e186(client: TestClient) -> None:
    pid = project(client)
    folder = folder_of(client, pid)
    (folder / "data").rmdir()
    (folder / "data").write_bytes(b"not a folder")
    refusal(client.get(f"/v1/projects/{pid}/data"), 400, "E186")
    refusal(upload(client, pid), 400, "E186")


def test_an_index_that_is_a_folder_cannot_be_written_and_is_e186(client: TestClient) -> None:
    pid = project(client)
    (folder_of(client, pid) / "data" / INDEX_FILE).mkdir()
    assert client.get(f"/v1/projects/{pid}/data").json() == []
    refusal(upload(client, pid), 400, "E186")
    assert data_listing(folder_of(client, pid)) == [INDEX_FILE]


def test_importing_again_a_file_missing_from_the_folder(client: TestClient) -> None:
    pid = project(client)
    upload(client, pid, "a.csv", b"x\n1\n")
    (folder_of(client, pid) / "data" / "a.csv").unlink()
    again = upload(client, pid, "a.csv", b"x\n2\n")
    assert again.status_code == 200, again.text
    assert (folder_of(client, pid) / "data" / "a.csv").read_bytes() == b"x\n2\n"


def test_a_fit_whose_file_no_longer_reads_is_e189(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bytes hashed as imported read as imported; were the reader to change, the fit
    is refused rather than fitting something else."""
    from lcsim.model.data_files import UnreadableData
    from lcsim.service import data_store

    pid = project(client)
    upload(client, pid, "a.csv", b"x\n1\n2\n", {"x": "s"})

    def unreadable(raw: bytes, form: str) -> Any:
        raise UnreadableData("unreadable", "hint")

    monkeypatch.setattr(data_store, "read_table", unreadable)
    response = client.post(f"/v1/projects/{pid}/data/a.csv/fit", json={"column": "x"})
    refusal(response, 400, "E189", "/file")


def test_validation_hashes_the_data_files_while_the_project_s_writes_are_held(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An import renames its file before its index; a validation between the two would see
    a changed file (E162) that is not."""
    from lcsim.model.data import DataIndex

    pid = project(client)
    upload(client, pid, "log.csv", b"up_h,down_min\n1.5,20\n", {"up_h": "h", "down_min": "min"})
    client.put(f"/v1/projects/{pid}/model", content=json.dumps(breakdown()))
    lock = state_of(client).models._lock_for(pid)
    held: list[bool] = []
    real = DataIndex.current_sha256

    def current_sha256(self: DataIndex, name: str) -> str | None:
        outcome: list[bool] = []
        probe = threading.Thread(target=lambda: outcome.append(lock.acquire(blocking=False)))
        probe.start()
        probe.join()
        if outcome[0]:
            lock.release()
        held.append(not outcome[0])
        return real(self, name)

    monkeypatch.setattr(DataIndex, "current_sha256", current_sha256)
    assert client.post(f"/v1/projects/{pid}/validate").json()["issues"] == []
    put = client.put(f"/v1/projects/{pid}/model", content=json.dumps(breakdown()))
    assert put.json()["issues"] == []
    assert held and all(held)


def test_a_column_that_overflows_in_seconds_is_refused_by_validate_and_by_runs(
    client: TestClient,
) -> None:
    """1e308 min is finite in the file but not in seconds; it is E162 before any run
    exists, as an inline "1e308 min" is E141 (Codex on PR #37)."""
    pid = project(client)
    upload(client, pid, "log.csv", b"up_h,down_min\n1.5,1e308\n", {"up_h": "h", "down_min": "min"})
    put = client.put(f"/v1/projects/{pid}/model", content=json.dumps(breakdown()))
    assert put.status_code == 200
    expected = [("E162", "/components/2/params/time_to_repair/data/column")]
    assert [(issue["code"], issue["path"]) for issue in put.json()["issues"]] == expected
    issues = client.post(f"/v1/projects/{pid}/validate").json()["issues"]
    assert [(issue["code"], issue["path"]) for issue in issues] == expected
    refused = client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "benchmark"})
    body = refusal(refused, 422, "E162")
    assert [(issue["code"], issue["path"]) for issue in body["issues"]] == expected
    runs = folder_of(client, pid) / "runs"
    assert not runs.exists() or list(runs.iterdir()) == []
