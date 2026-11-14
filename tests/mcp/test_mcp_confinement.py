"""No MCP tool reads or writes outside the project folder (spec 4 "Limits" and acceptance
table, M7; AKS-134).

``python -m ithax.mcp``'s ``main`` runs as its own process, as an assistant starts it, with
an audit hook (``sys.addaudithook``, PEP 578) installed before ``ithax.mcp`` is imported.
The hook writes one line for every file the process opens, every folder it lists, and every
file or folder it creates, renames, removes or changes, and for every program it starts, to
a log opened before the hook (writing to an open file raises no audit event). A scripted
client then calls each of the eleven tools, refusals included, against a service running in
this test's process, so everything the service does to the project folder happens here and
nothing of it is in the log.

The child runs with ``-I`` (so neither the working folder nor any ``PYTHON*`` variable
reaches ``sys.path``) and ``-B`` (so importing writes no ``.pyc`` file). What the log may
hold: the interpreter reading its own modules (read-only, under an entry of the child's
``sys.path`` or the folder holding the ``ithax`` package); the null device opened
read-only, which the SDK's stdio transport points standard input at while it serves the
protocol on a private copy of it (``mcp.server.stdio``), no file in any folder; and the read
of ``service.json`` in the configuration folder, which is discovery (spec 3), not a tool's
read. Anything else, a read inside a project folder included, would be listed; there is
none, so no tool reads or writes a file at all, and the spec 4 rule ("only inside project
folders") holds a fortiori.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import anyio
import httpx2
import pytest
from mcp import Client, StdioServerParameters
from mcp.types import CallToolResult, TextContent
from mcp_support import in_process_service

#: The child: open the log, install the hook, then run the MCP server's ``main``.
CHILD = r"""
import importlib.util, json, os, sys

log = open(sys.argv[1], "w", encoding="utf-8", buffering=1)
package = importlib.util.find_spec("ithax").submodule_search_locations[0]
roots = sys.path + [os.path.dirname(package)]
log.write(json.dumps({"roots": roots}) + "\n")
PATHS = {
    "os.listdir", "os.scandir", "os.mkdir", "os.rmdir", "os.remove", "os.rename",
    "os.truncate", "os.chmod", "os.chown", "os.lchown", "os.chflags", "os.utime",
    "os.link", "os.symlink", "os.mkfifo", "os.mknod", "os.chdir", "os.setxattr",
    "os.removexattr", "os.listxattr", "os.getxattr", "shutil.copyfile",
    "shutil.copymode", "shutil.copystat", "shutil.copytree", "shutil.rmtree",
    "shutil.move", "shutil.make_archive", "shutil.unpack_archive", "tempfile.mkstemp",
    "tempfile.mkdtemp", "sqlite3.connect", "glob.glob", "glob.glob/2",
    "pathlib.Path.glob", "pathlib.Path.rglob",
}
PROGRAMS = {"subprocess.Popen", "os.exec", "os.posix_spawn", "os.spawn", "os.system",
            "os.startfile", "os.fork", "os.forkpty"}

def text(value):
    if isinstance(value, (str, bytes, os.PathLike)):
        return os.fsdecode(value)
    return None

def hook(event, args):
    if event == "open":
        path = text(args[0])
        if path is not None:
            log.write(json.dumps({"event": event, "path": path, "mode": args[1],
                                  "flags": args[2]}) + "\n")
    elif event in PATHS:
        path = text(args[0]) if args else None
        log.write(json.dumps({"event": event, "path": path}) + "\n")
    elif event in PROGRAMS:
        log.write(json.dumps({"event": event, "path": repr(args[:1])}) + "\n")

sys.addaudithook(hook)
from ithax.mcp.server import main
raise SystemExit(main(sys.argv[2:]))
"""

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
FINAL = ("done", "failed", "cancelled")


def writes(record: dict[str, Any]) -> bool:
    """Whether an ``open`` may write: a mode with ``w``, ``a``, ``x`` or ``+``, or flags
    asking to write, create, truncate or append."""
    mode = record.get("mode") or ""
    return any(letter in mode for letter in "wax+") or bool((record["flags"] or 0) & _WRITE_FLAGS)


def under(path: str, roots: list[str]) -> bool:
    real = os.path.realpath(path)
    return any(
        real == root or real.startswith(root.rstrip(os.sep) + os.sep)
        for root in (os.path.realpath(r) for r in roots)
    )


def payload(result: CallToolResult) -> Any:
    [block] = result.content
    assert isinstance(block, TextContent)
    return json.loads(block.text)


COFFEE_SHOP_EDITS: list[dict[str, Any]] = [
    {
        "edit": "add_component",
        "id": "arrivals",
        "type": "source",
        "params": {"interarrival": {"dist": "exponential", "mean": "2 min"}},
    },
    {
        "edit": "add_component",
        "id": "till",
        "type": "server",
        "params": {"capacity": 1, "service": {"dist": "exponential", "mean": "1.5 min"}},
    },
    {"edit": "add_component", "id": "exit", "type": "sink", "params": {}},
    {"edit": "connect", "from": "arrivals.out", "to": "till.in"},
    {"edit": "connect", "from": "till.out", "to": "exit.in"},
    {
        "edit": "set_experiment",
        "id": "base",
        "length": "10 h",
        "warmup": "1 h",
        "replications": 2,
        "seed": 12345,
    },
]


async def use_every_tool(mcp_client: Client) -> dict[str, Any]:
    """Call each of the eleven tools, with refusals; return what the checks need."""
    called: set[str] = set()

    async def call(name: str, arguments: dict[str, Any]) -> tuple[bool, Any]:
        called.add(name)
        result = await mcp_client.call_tool(name, arguments)
        return bool(result.is_error), payload(result)

    listed = await mcp_client.list_tools()
    for name in ("list_templates", "list_engines", "list_projects", "get_schema"):
        assert not (await call(name, {}))[0], name
    assert not (await call("get_schema", {"component_type": "server"}))[0]
    error, project = await call("create_model", {"name": "Coffee shop"})
    assert not error, project
    pid = project["id"]
    assert not (await call("get_model", {"project_id": pid}))[0]
    error, edited = await call(
        "edit_model", {"project_id": pid, "edits": COFFEE_SHOP_EDITS, "base_revision": 0}
    )
    assert not error and edited["issues"] == [], edited
    assert not (await call("validate_model", {"project_id": pid}))[0]
    error, started = await call("run_model", {"project_id": pid, "experiment_id": "base"})
    assert not error, started
    rid = started["run_id"]
    with anyio.fail_after(120):
        while True:
            error, status = await call("get_run_status", {"run_id": rid})
            assert not error
            if status["state"] in FINAL:
                break
            await anyio.sleep(0.1)
    assert status["state"] == "done", status
    error, results = await call(
        "get_results", {"run_id": rid, "tables": ["replications", "timeseries"]}
    )
    assert not error and set(results["tables"]) == {"replications", "timeseries"}
    # Refusals, among them inputs that name places outside the project folder.
    refusals = [
        ("create_model", {"name": "x", "path": str(Path.home())}, "E184"),
        ("create_model", {"name": "x", "template_id": "../../etc"}, "E185"),
        ("get_model", {"project_id": "../../.."}, "E185"),
        ("get_schema", {"component_type": "../../schema"}, "E185"),
        ("edit_model", {"project_id": pid, "edits": COFFEE_SHOP_EDITS, "base_revision": 0}, "E181"),
        ("get_results", {"run_id": rid, "tables": ["../manifest"]}, "E185"),
        ("get_run_status", {"run_id": "../../projects"}, "E185"),
        ("run_model", {"project_id": pid}, "E184"),
    ]
    for name, arguments, code in refusals:
        error, body = await call(name, arguments)
        assert error and body["error"]["code"] == code, (name, body)
    return {
        "listed": {tool.name for tool in listed.tools},
        "called": called,
        "project_path": project["path"],
    }


def test_no_mcp_tool_reads_or_writes_outside_the_project_folder(tmp_path: Path) -> None:
    config_dir, data_dir = tmp_path / "config", tmp_path / "data"
    log_file = tmp_path / "audit.jsonl"
    workdir = tmp_path / "work"
    workdir.mkdir()
    with in_process_service(config_dir, data_dir) as info:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[
                "-I",
                "-B",
                "-c",
                CHILD,
                str(log_file),
                "--config-dir",
                str(config_dir),
                "--data-dir",
                str(data_dir),
            ],
            cwd=str(workdir),
        )

        async def session() -> dict[str, Any]:
            async with Client(parameters) as mcp_client:
                return await use_every_tool(mcp_client)

        seen = anyio.run(session)
        with httpx2.Client(
            base_url=f"http://127.0.0.1:{info.port}",
            headers={"Authorization": f"Bearer {info.token}"},
            trust_env=False,
        ) as http:
            project_paths = [item["path"] for item in http.get("/v1/projects").json()]

    assert seen["called"] == seen["listed"] and len(seen["called"]) == 11
    assert project_paths == [seen["project_path"]]
    lines = log_file.read_text(encoding="utf-8").splitlines()
    roots: list[str] = json.loads(lines[0])["roots"]
    records = [json.loads(line) for line in lines[1:]]

    def code(record: dict[str, Any]) -> bool:
        reads = record["event"] != "open" or not writes(record)
        listing = record["event"] in ("open", "os.listdir", "os.scandir")
        return listing and reads and record["path"] is not None and under(record["path"], roots)

    def transport(record: dict[str, Any]) -> bool:
        return record["path"] == os.devnull and not writes(record)

    assert "" not in roots and all(os.path.isabs(root) for root in roots)
    # The hook saw the process work: its own modules, among them the tools.
    tools = os.path.join("ithax", "mcp", "")
    assert any(code(r) and tools in r["path"] for r in records)
    service_file = os.path.realpath(config_dir / "service.json")
    others = [r for r in records if not code(r) and not transport(r)]
    # No program started, nothing written anywhere.
    assert [r for r in others if r["event"] not in ("open", "os.listdir", "os.scandir")] == []
    assert [r for r in others if writes(r)] == []
    # The one read outside the interpreter's modules is discovery's read of service.json.
    assert {os.path.realpath(r["path"]) for r in others} == {service_file}
    # So nothing outside the project folders, which is what spec 4 asks.
    outside = [
        r
        for r in others
        if os.path.realpath(r["path"]) != service_file and not under(r["path"], project_paths)
    ]
    assert outside == []


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"event": "open", "mode": "r", "flags": os.O_RDONLY}, False),
        ({"event": "open", "mode": "rb", "flags": 0}, False),
        ({"event": "open", "mode": "w", "flags": 0}, True),
        ({"event": "open", "mode": "r+", "flags": 0}, True),
        ({"event": "open", "mode": None, "flags": os.O_WRONLY | os.O_CREAT}, True),
        ({"event": "open", "mode": None, "flags": os.O_RDONLY}, False),
    ],
)
def test_the_write_check_reads_modes_and_flags(record: dict[str, Any], expected: bool) -> None:
    assert writes(record) is expected
