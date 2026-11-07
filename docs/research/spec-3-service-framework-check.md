# Service framework check (spec 3, M6)

## Question

Spec 3 "Research before building", M6 (service) and M9 (interface): "Framework check.
Current state, licences and Linux support of Tauri, Electron, Qt and React Flow." The
interface half was done on 2026-11-06 (`docs/research/spec-3-framework-check.md`). This
note is the service half, done before any service code (guide rule 3, AKS-110): is
FastAPI, which spec 3 "Architecture" proposes for the engine service, confirmed or
replaced, and which ASGI server, WebSocket library and test client go with it? For each:

- the current release and its date, and its licence, read from the installed
  distribution's licence file, with every runtime dependency's;
- whether it runs natively on Windows as well as Linux, since Phase 1 runs both parts
  natively on Windows (spec 3 "Architecture", proposed default, owner decision AKS-77
  open): no package without a Windows build, no fork-only or Linux-only code;
- WebSocket support, which spec 3 needs for `.../events` (token as the first message,
  close code 1008, the `Origin` check);
- that the lower bounds install and work on Python 3.11 and 3.13 (CI runs both);
- that nothing in the stack reaches the network on its own (spec 3 acceptance "The app
  works with outbound network blocked", M6).

The multipart parser that `POST .../data` (AKS-113) needs is checked here too, so that
ticket starts from a known licence; it is not added now.

## Finding

### Versions, dates and licences, read on 2026-11-07

Method: `https://pypi.org/pypi/<name>/<version>/json` read with `curl` for the upload time
and the files offered; the packages installed with `pip` into a fresh venv on
`/usr/bin/python3.11` (3.11.18) and one on Python 3.13.18, in a scratch folder outside the
repository; a script walked `importlib.metadata` requirements from the roots (`fastapi`,
`uvicorn`, `websockets`, `httpx2`), evaluating markers with no extras, and printed each
distribution's licence metadata; the head of every licence file was then read. Both
Pythons gave the same tree and versions.

| Package | Version (uploaded) | Role | Licence (file read) | Windows |
| --- | --- | --- | --- | --- |
| fastapi | 0.162.1 (2026-11-07) | the web framework | MIT (`fastapi-0.162.1.dist-info/licenses/LICENSE`, "Copyright (c) 2018 Sebastián Ramírez") | pure Python |
| starlette | 1.10.0 (2026-10-24) | FastAPI's base: routing, WebSocket, test client | BSD-3-Clause (`licenses/LICENSE.md`, "Copyright © 2018, Encode OSS Ltd") | pure Python |
| pydantic | 2.14.3 (2026-11-05) | request bodies | MIT (`licenses/LICENSE`) | pure Python |
| pydantic-core | 2.50.4 (2026-11-05) | pydantic's compiled core | MIT (`licenses/LICENSE`, "Copyright (c) 2022 Samuel Colvin") | wheels `cp311` and `cp313` for `win_amd64`, `win32`, `win_arm64` |
| annotated-types | 0.8.0 | pydantic | MIT | pure Python |
| typing-inspection | 0.4.5 | fastapi, pydantic | MIT | pure Python |
| typing_extensions | 4.16.0 | fastapi, pydantic, anyio | PSF-2.0 (already present through optuna, AKS-109) | pure Python |
| annotated-doc | 0.0.5 | fastapi | MIT ("Copyright (c) 2025 Sebastián Ramírez") | pure Python |
| opentelemetry-api | 1.45.2 (2026-10-29) | fastapi (its built-in telemetry) | Apache-2.0 (`licenses/LICENSE`, Apache License 2.0 text) | pure Python |
| anyio | 4.16.0 | starlette | MIT ("Copyright (c) 2018 Alex Grönholm") | pure Python |
| idna | 3.20 | anyio | BSD-3-Clause | pure Python |
| uvicorn | 0.54.0 (2026-09-25) | the ASGI server | BSD-3-Clause (`licenses/LICENSE.md`, "Copyright © 2017-present, Encode OSS Ltd") | pure Python; classifier "OS Independent" |
| click | 8.5.1 | uvicorn | BSD-3-Clause ("Copyright 2014 Pallets") | pure Python |
| h11 | 0.16.0 | uvicorn | MIT | pure Python |
| websockets | 17.4 (2026-10-30) | uvicorn's WebSocket protocol | BSD-3-Clause (`licenses/LICENSE`, "Copyright (c) Aymeric Augustin and contributors") | wheels `cp311` and `cp313` for `win_amd64`, `win32`, `win_arm64`, and a `py3-none-any` wheel |
| httpx2 | 2.16.0 (2026-10-21) | test client (development only) | BSD-3-Clause (`licenses/LICENSE.md`) | pure Python |
| httpcore2 | 2.16.0 | httpx2 | BSD-3-Clause | pure Python |
| truststore | 0.10.5 | httpx2 | MIT | pure Python |
| httpx | 0.28.1 (2024-12-06) | the older test client | BSD-3-Clause | pure Python (not chosen, below) |
| python-multipart | 0.0.33 (2026-10-31) | multipart parser for uploads (AKS-113) | Apache-2.0 (`licenses/LICENSE.txt`) | pure Python (not added now) |
| wsproto | 1.3.2 (2025-11-20) | alternative WebSocket protocol | MIT | pure Python (not chosen) |
| uvloop | 0.23.0 (2026-10-01) | faster event loop in `uvicorn[standard]` | PyPI: `License: MIT License`, classifiers MIT and Apache (not installed) | **no Windows wheel** (61 files, none for Windows) |

Every licence above is permissive (MIT, BSD-3-Clause, Apache-2.0, PSF-2.0) and compatible
with AGPL-3.0 for a combined work under the spec 1 engine licence rule (owner decision
AKS-83 deferred; not legal advice).

### FastAPI is confirmed, with three settings

- **Routes.** FastAPI adds `/docs`, `/redoc` and `/openapi.json` unless told not to; spec
  3's route table test (AKS-114) asserts that the application's routes equal the spec
  table both ways, so the app is created with `docs_url=None`, `redoc_url=None` and
  `openapi_url=None`. Checked: with these, `app.routes` holds only the routes the code
  declares.
- **Telemetry.** FastAPI 0.162 depends on `opentelemetry-api` and records spans,
  metrics and logs through it (`fastapi/telemetry/`). With the API alone and no SDK the
  calls are no-ops, and OTLP exporters are added only when `FASTAPI_OTEL_AUTO_CONFIGURE`
  is `true` and an `OTEL_EXPORTER_OTLP_*` endpoint is set (read in
  `fastapi/telemetry/_runtime.py` and `applications.py`). So that no environment variable
  can make the service send anything (spec 3 acceptance, outbound network blocked), the
  app is created with `telemetry` set to turn tracing, metrics, logs, operation spans and
  auto-configuration off.
- **Errors.** FastAPI answers a request it cannot parse with 422 and pydantic's own
  messages; spec 3 wants 400 "Request malformed" and an error body with a spec 1 code and
  lcsim's own words. Its `RequestValidationError` and Starlette's `HTTPException` are given
  handlers that write spec 3's error body.

Starlette alone (anyio only) was the alternative: it has the routing, the WebSocket and
the test client, and fewer dependencies (no pydantic, no OpenTelemetry). FastAPI is kept
because spec 3 names it, its typed request models give the field checks that
"Request malformed" needs without hand-written parsing, and the MCP server (M7) is likely
to bring pydantic anyway.

### The ASGI server: uvicorn, plain, with websockets; not `uvicorn[standard]`

- `uvicorn` alone depends only on `click` and `h11` and has no WebSocket protocol: a
  WebSocket upgrade needs `websockets` or `wsproto` installed.
- `uvicorn[standard]` adds `httptools`, `python-dotenv`, `pyyaml`, `watchfiles`,
  `websockets` and `uvloop`, the last with the marker `sys_platform != 'win32'`, so it
  installs on Windows but runs differently there; uvloop has no Windows build at all.
  The service needs none of the extras but `websockets`, so it declares `uvicorn` and
  `websockets` and never `uvicorn[standard]`; the event loop is asyncio on every
  platform.
- uvicorn 0.50.0 (2026-07-04) deprecated its `websockets` protocol (built on the legacy
  `websockets` API) in favour of `websockets-sansio` or `wsproto`; the installed 0.54.0
  warns `UvicornDeprecationWarning` when `ws="websockets"` is chosen, and its `ws="auto"`
  picks `websockets-sansio` when `websockets` is installed (read in
  `uvicorn/protocols/websockets/auto.py` and `websockets_impl.py`). The service names
  `ws="websockets-sansio"` explicitly, so the choice does not depend on what else is
  installed.
- uvicorn's `Server.run(sockets=[...])` serves on a socket the caller has bound, so the
  service binds `127.0.0.1` port 0, reads the port the operating system chose, and writes
  `service.json` before serving (spec 3 "Discovery"). Signal handlers are installed only
  in the main thread, so `main()` can also be run in a thread by a test.

### The test client: Starlette's `TestClient` on httpx2

Starlette 1.10's `TestClient` warns `StarletteDeprecationWarning: Using httpx with
starlette.testclient is deprecated; install httpx2 instead` when only `httpx` is installed,
and imports without warning when `httpx2` is (checked with `python -W error`). Its
`TestClient` drives the app in-process, HTTP and WebSocket alike, which httpx's
`ASGITransport` does not (it has no WebSocket support). `httpx2` 2.16.0 (pydantic's
successor to httpx, `py.typed`) is therefore the development dependency, not `httpx`; the
tests that start a real server use `httpx2.Client(trust_env=False)`, so that the
session's proxy variables do not send `127.0.0.1` requests through a proxy. The service's
own probe of `GET /v1/system` (spec 3 "One service per user") needs no client library:
it uses `urllib.request` with an empty `ProxyHandler`, for the same reason.

### Platform notes for the service code

- `service.json` mode 0600 is `os.open(..., 0o600)` on a temporary file in the same
  folder, then `os.replace`; on Windows `os.chmod` changes only the read-only flag, and
  the per-user configuration folder (`%APPDATA%`) is what keeps the file private.
- Hardware: the cores the process may use (`os.process_cpu_count` on 3.13,
  `os.sched_getaffinity` on Linux, else `os.cpu_count`); physical memory from
  `os.sysconf` on Linux and macOS (as `lcsim.runs.limits.system_memory` already does) and
  from `GlobalMemoryStatusEx` through `ctypes` on Windows; graphics vendors from
  `/sys/class/drm/card*/device/vendor` on Linux only, unknown elsewhere. No new
  dependency (psutil, BSD-3-Clause, would cover all three platforms but is one more
  compiled package for two numbers).

## Sources

All read on 2026-11-07.

- PyPI JSON: <https://pypi.org/pypi/fastapi/0.162.1/json>,
  <https://pypi.org/pypi/starlette/1.10.0/json>, <https://pypi.org/pypi/uvicorn/0.54.0/json>
  (`requires_dist`, the uvloop marker, "OS Independent"),
  <https://pypi.org/pypi/websockets/17.4/json> (Windows wheels),
  <https://pypi.org/pypi/pydantic-core/2.50.4/json> (Windows wheels),
  <https://pypi.org/pypi/uvloop/0.23.0/json> (no Windows wheel),
  <https://pypi.org/pypi/httpx2/json>, <https://pypi.org/pypi/httpx/0.28.1/json>,
  <https://pypi.org/pypi/python-multipart/0.0.33/json>,
  <https://pypi.org/pypi/opentelemetry-api/1.45.2/json>, <https://pypi.org/pypi/wsproto/1.3.2/json>.
- uvicorn documentation, WebSockets: <https://uvicorn.dev/concepts/websockets/> (the
  `websockets-sansio` protocol and why it replaced the old one).
- uvicorn release notes, 0.50.0 to 0.52.x (deprecation of the legacy `websockets`
  protocol, `auto` picking `websockets-sansio`, `websockets>=13.0`):
  <https://releasebot.io/updates/kludex/uvicorn>.
- The installed sources: `fastapi/applications.py` and `fastapi/telemetry/` (telemetry
  defaults), `starlette/testclient.py` (the httpx2 warning),
  `uvicorn/protocols/websockets/auto.py` and `websockets_impl.py`, `uvicorn/server.py`.
- The licence file of every distribution listed, inside the installed wheels.
- `docs/research/spec-3-framework-check.md` (the interface half).

## Decision

1. **FastAPI confirmed** for the engine service: `fastapi>=0.162.1`, created with
   `docs_url`, `redoc_url` and `openapi_url` set to `None` and all telemetry off. Spec 3
   "Architecture" keeps "Python with FastAPI" and names the server.
2. **uvicorn with websockets**: `uvicorn>=0.54.0` and `websockets>=17.4`, never
   `uvicorn[standard]` (uvloop has no Windows build); `ws="websockets-sansio"`; asyncio
   on every platform.
3. **Test client**: Starlette's `TestClient` with `httpx2>=2.16.0` as a development
   dependency (not `httpx`, which Starlette 1.10 deprecates for its test client).
4. **Multipart**: `python-multipart` 0.0.33 (Apache-2.0) is the parser FastAPI needs for
   `UploadFile`; AKS-113 adds it.
5. **No psutil**: hardware is read with the standard library and `ctypes` (above).
6. Lower bounds are the newest releases, as for the M5 dependencies (AKS-132 decision
   5), all of which install on Python 3.11 and 3.13.

## Tested

On 2026-11-07, in the scratch venvs (Python 3.11.18 and 3.13.18) with fastapi 0.162.1,
uvicorn 0.54.0, websockets 17.4 and httpx 0.28.1, with `warnings.simplefilter("error")`,
a script bound `127.0.0.1` port 0 itself, served a FastAPI app with
`docs_url=redoc_url=openapi_url=None` through `uvicorn.Server(...).run(sockets=[sock])`
with `ws="websockets-sansio"` in a thread, and on both Pythons:

- `GET /v1/system` answered over real HTTP, and `app.routes` held only `/v1/system` and
  `/ws`;
- a WebSocket that sent a first text message was answered;
- a WebSocket that sent nothing was closed by the server with code 1008 and reason
  `E182` after its timeout;
- an upgrade with an `Origin` header that the endpoint closed before accepting was
  refused with HTTP 403;
- `server.should_exit = True` stopped the server and the thread ended.

`python -W error -c "import starlette.testclient"` passed with httpx2 2.16.0 installed
and warned without it. The product's own service tests (`tests/service/`) then exercise
the same paths with the built code, on both Pythons in CI.
