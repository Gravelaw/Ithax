# MCP: protocol version, Python library and how assistants connect (spec 4, M7)

## Question

Spec 4 "Research before building", M7: "MCP. Current protocol version, the official Python
server library, and how desktop assistants connect to local servers." Done before any MCP
server code (guide rule 3, AKS-115). For the server that `python -m lcsim.mcp` will run:

- which revision of the Model Context Protocol is current, and which revisions a server
  must still answer, since assistants in use today may speak an older one;
- which Python library to build on, its current release, its licence and every package it
  pulls in that lcsim does not already depend on, and whether it installs on Python 3.11
  and 3.13 (CI runs both) and on Windows (spec 3 "Architecture": Phase 1 native on
  Windows, proposed default, AKS-77 open);
- which transport, stdio or Streamable HTTP, and how a desktop assistant (Claude Desktop,
  Claude Code, others) is told to start a local server;
- how the protocol separates an error the model should read from a protocol failure,
  since spec 4 "Behaviour an assistant can rely on" says "Errors are data".

## Finding

### The protocol revision

The specification's versioning page (read 2026-11-08) says: "The current protocol version
is 2026-07-28." Revisions are dated strings, "the last date backwards incompatible changes
were made". The 2026-07-28 revision drops the connection handshake: "Every request declares
the protocol version it is using via the `io.modelcontextprotocol/protocolVersion` key in
its `_meta` field, and the server accepts or rejects each request independently", and a
client may first call `server/discover`. Revisions up to 2025-11-25 open each connection
with the `initialize` handshake instead.

The SDK's own registry (`mcp_types/version.py` in mcp-types 2.3.0) lists the known
revisions `2024-11-05`, `2025-03-26`, `2025-06-18`, `2025-11-25` (handshake era) and
`2026-07-28` (modern era), with `LATEST_PROTOCOL_VERSION` = `2026-07-28` and
`OLDEST_SUPPORTED_VERSION` = `2024-11-05`. Its "Protocol versions" page says `MCPServer`
"answers `server/discover` on every transport — Streamable HTTP, stdio, and the in-process
connection", and the low-level `Server.run` docstring says it serves "the legacy handshake
era and the modern per-request-envelope era (the client's first request decides which)".
So one server answers an assistant of either era without configuration.

### The Python library

The official SDK is the `mcp` package (repository `modelcontextprotocol/python-sdk`,
maintained by the protocol's maintainers). Version 2.3.0 was uploaded to PyPI on
2026-10-02 (`https://pypi.org/pypi/mcp/2.3.0/json`, read 2026-11-08); `pip install mcp`
installs it. Version 2 renamed v1's `FastMCP` to `MCPServer` ("What's new in v2") and
rebuilt the low-level `Server`: handlers are passed to the constructor as
`on_list_tools=` and `on_call_tool=`, each `async (ctx, params) -> result`, the result is
built in full (`ListToolsResult`, `CallToolResult`), and "the schema is advertised but
never applied: nothing checks the arguments before your handler runs".

The two server styles differ in what lcsim needs:

| | `MCPServer` (decorators) | low-level `Server` |
| --- | --- | --- |
| Input schema | from the function's type hints | written by hand, exactly as advertised |
| Argument check | the SDK validates against the hints; a failure is the SDK's message | none; the server checks and words the problem itself |
| Error result | `raise ToolError(msg)` gives `is_error` with the text "Error executing tool <name>: <msg>" and no structured content | the server returns `CallToolResult(is_error=True, ...)` with whatever content it chooses |
| Unexpected exception | `is_error` with "Error executing tool <name>", the text hidden | a sanitised protocol error `-32603` |

Licences and the packages `mcp` 2.3.0 pulls in that lcsim did not already depend on, read
from each installed distribution's metadata (`importlib.metadata`) and the head of its
licence file, and from PyPI's JSON for upload dates and Windows wheels:

| Package | Version (uploaded) | Licence (file read) | Windows |
| --- | --- | --- | --- |
| mcp | 2.3.0 (2026-10-02) | MIT (`mcp-2.3.0.dist-info/licenses/LICENSE`, "Copyright (c) 2024 Anthropic, PBC") | pure Python |
| mcp-types | 2.3.0 (2026-10-02) | MIT (`mcp_types-2.3.0.dist-info/licenses/LICENSE`, same notice) | pure Python |
| PyJWT | 2.15.1 (2026-09-28) | MIT (`pyjwt-2.15.1.dist-info/licenses/LICENSE`, "Copyright (c) 2015-2022 José Padilla") | pure Python |
| cryptography | 50.0.2 (2026-09-30) | Apache-2.0 OR BSD-3-Clause (`LICENSE`, `LICENSE.APACHE`, `LICENSE.BSD`) | `win_amd64` wheels (cp311 abi3) |
| cffi | 2.1.1 (2026-08-03) | MIT-0 ("MIT No Attribution", `cffi-2.1.1.dist-info/licenses/LICENSE`) | `win32`, `win_amd64`, `win_arm64` wheels for 3.11 to 3.13 |
| pycparser | 3.12 (2026-10-22) | BSD-3-Clause (`pycparser-3.12.dist-info/licenses/LICENSE`, "Copyright (c) 2008-2027, Eli Bendersky") | pure Python |
| sse-starlette | 3.7.0 (2026-11-07) | BSD-3-Clause (`sse_starlette-3.7.0.dist-info/licenses/LICENSE`) | pure Python |
| pywin32 | 311 (2025-07-14), Windows only (`sys_platform == 'win32'`) | PSF (PyPI metadata; not installed on Linux, so no file read) | Windows wheels only |

`mcp` also requires anyio, httpx2, jsonschema, opentelemetry-api, pydantic,
python-multipart, starlette, typing-extensions, typing-inspection and uvicorn, which lcsim
already has (the M6 entries of `docs/DECISIONS.md`; httpx2 was a development dependency
and now arrives at run time through `mcp`). PyJWT, cryptography and sse-starlette serve the
SDK's HTTP transports and OAuth, which a stdio server does not use, but they are
unconditional requirements. Every licence is permissive and compatible with AGPL-3.0 for a
combined work; the engine licence rule itself is deferred by the owner (AKS-83).

### Transport

The specification (revision 2025-11-25, "Transports") defines two standard transports,
stdio and Streamable HTTP, and says "Clients SHOULD support stdio whenever possible". In
stdio "the client launches the MCP server as a subprocess", messages are newline-delimited
JSON-RPC on stdin and stdout, and "The server MUST NOT write anything to its `stdout` that
is not a valid MCP message"; stderr may carry logs. Streamable HTTP is "an independent
process that can handle multiple client connections" and requires the server to validate
`Origin`, bind to localhost and "SHOULD implement proper authentication".

The SDK's "Connect to a real host" page: "Inside it, an MCP client launches your server as
a child process and speaks to it over that process's stdin and stdout. Which means
connecting to a host is one act: you tell it the command that starts your server." Its
`stdio_server` protects the protocol stream: in the prototype below a `print` inside a tool
did not reach the client's stream.

### How desktop assistants connect

- **Claude Desktop:** an entry under `mcpServers` in `claude_desktop_config.json` with
  `command` and `args` (macOS `~/Library/Application Support/Claude/`, Windows
  `%APPDATA%\Claude\`); the app must be fully quit and reopened; it "starts your server in
  its own process, so your shell's environment variables are not there" (SDK "Connect to a
  real host").
- **Claude Code:** `claude mcp add <name> -- <command> <args...>`, or a JSON entry in
  `.mcp.json` or `~/.claude.json`; "Claude Code reads an entry with no `type` as a stdio
  server", and it sets `CLAUDE_PROJECT_DIR` in the spawned server's environment
  (Claude Code documentation, "Connect Claude Code to tools via MCP").
- **Cursor** (`.cursor/mcp.json`, the same `mcpServers` layout) and **VS Code**
  (`.vscode/mcp.json`, key `servers`, each entry with `"type": "stdio"`) take the same
  command (SDK "Connect to a real host").

Every one of them takes a command line, not a URL, for a local server; a host may start
the server with a near-empty environment and any working directory.

### Errors the model reads

The specification's "Tools" page (2025-11-25), "Error Handling": protocol errors are for
"Unknown tools", "Malformed requests (requests that fail to satisfy CallToolRequest
schema)" and "Server errors"; tool execution errors are "Reported in tool results with
`isError: true`" and cover "API failures", "Input validation errors" and "Business logic
errors". "Tool Execution Errors contain actionable feedback that language models can use
to self-correct and retry with adjusted parameters ... Clients SHOULD provide tool
execution errors to language models to enable self-correction." A result may carry
`structuredContent`, a JSON object, and "a tool that returns structured content SHOULD
also return the serialized JSON in a TextContent block". A tool without parameters should
declare `{"type": "object", "additionalProperties": false}`. Tool names should use only
ASCII letters, digits, `_`, `-` and `.`; spec 4's eleven names do.

The SDK's "Handling errors" page draws the same line: a result with `is_error` is "a turn
in the conversation" the model can react to, a raised `MCPError` "hands it nothing".

## Sources

- Model Context Protocol, "Versioning", https://modelcontextprotocol.io/specification/versioning (read 2026-11-08).
- Model Context Protocol, specification 2025-11-25, "Transports", https://modelcontextprotocol.io/specification/2025-11-25/basic/transports (read 2026-11-08).
- Model Context Protocol, specification 2025-11-25, "Tools", https://modelcontextprotocol.io/specification/2025-11-25/server/tools (read 2026-11-08).
- MCP Python SDK documentation, "What's new in v2", https://py.sdk.modelcontextprotocol.io/whats-new/ ; "Protocol versions", https://py.sdk.modelcontextprotocol.io/protocol-versions/ ; "Handling errors", https://py.sdk.modelcontextprotocol.io/servers/handling-errors/ ; "Testing", https://py.sdk.modelcontextprotocol.io/get-started/testing/ ; "Connect to a real host", https://py.sdk.modelcontextprotocol.io/get-started/real-host/ ; "Serving legacy clients", https://py.sdk.modelcontextprotocol.io/run/legacy-clients/ (all read 2026-11-08).
- Claude Code documentation, "Connect Claude Code to tools via MCP", https://code.claude.com/docs/en/mcp (read 2026-11-08).
- PyPI JSON API, `https://pypi.org/pypi/<name>/<version>/json` for mcp 2.3.0, mcp-types 2.3.0, pyjwt 2.15.1, cryptography 50.0.2, cffi 2.1.1, pycparser 3.12, sse-starlette 3.7.0 and pywin32 311 (read 2026-11-08).
- The installed packages' metadata and licence files, and `mcp_types/version.py`, `mcp/server/lowlevel/server.py` and `mcp/server/stdio.py` of mcp 2.3.0.

## Decision

- **Library:** `mcp>=2.3.0`, the official SDK, with its low-level `Server`. Spec 4 needs
  inputs exactly as it names them, a worked example in each description, problems in its
  own words with spec 1 codes, and failures returned as data; the low-level server
  advertises a hand-written schema unchanged and returns the `CallToolResult` lcsim
  builds, where `MCPServer` would word argument problems and tool errors itself. The tool
  registry, the argument check and the result shape live in `lcsim.mcp.tools`, one place
  that AKS-134's five tools join.
- **Protocol:** whatever the client speaks; the SDK serves 2024-11-05 to 2025-11-25 by the
  handshake and 2026-07-28 by `server/discover`. Tests cover both eras.
- **Transport:** stdio only. `python -m lcsim.mcp` is the command every assistant above
  takes. Streamable HTTP would be a second listening process with its own port, `Origin`
  check and authentication beside the engine service, for no Phase 1 need.
- **Connecting:** the assistant starts `python -m lcsim.mcp` with the Python that has
  lcsim installed (an absolute path, since a host's `PATH` may be near empty); optional
  `--config-dir` and `--data-dir` are passed to the service when the MCP server starts
  it. Example for Claude Desktop:
  `{"mcpServers": {"lcsim": {"command": "/path/to/python", "args": ["-m", "lcsim.mcp"]}}}`;
  for Claude Code: `claude mcp add lcsim -- /path/to/python -m lcsim.mcp`.
- **Errors:** a service refusal, a service that cannot be reached or started, and an input
  problem are tool results with `isError` true; the only protocol error is an unknown tool
  name, as the specification lists it. A result's text is the JSON of the service's body,
  and the same object is its `structuredContent` when the body is a JSON object (the list
  endpoints return arrays, which `structuredContent` cannot hold).
- **Spec 4 is not contradicted**: its tool list, "Errors are data" and "Model files only"
  fit the protocol as it stands. Two summary sentences are corrected while building
  (AKS-115): the MCP server, not the service, exposes the tools, and the summary table
  gains `list_projects` and `get_model`, which the detailed table already has.

## Tested

On 2026-11-08, at `main` `a4c4551`, from scripts in a scratch directory outside the
repository; no product code was written or changed.

- `pip install "mcp==2.3.0"` into fresh venvs on Python 3.11.18 (`/usr/bin/python3.11`)
  and 3.13.18 (the repository's `.venv`): both resolved the same tree (the table above
  plus the packages already used), mcp 2.3.0 with mcp-types 2.3.0, PyJWT 2.15.1,
  cryptography 50.0.2, cffi 2.1.1, pycparser 3.12 and sse-starlette 3.7.0.
- A one-tool low-level `Server` (an `echo` tool with
  `{"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"],
  "additionalProperties": false}`, returning `CallToolResult(is_error=True,
  structured_content=...)` and printing a line to stdout inside the tool) was driven on
  both Pythons by `mcp.Client`: in memory (`Client(server)`), over stdio
  (`Client(StdioServerParameters(command=sys.executable, args=["srv.py"]))`) and over stdio
  with `mode="legacy"`. Results: protocol versions `2026-07-28`, `2026-07-28` and
  `2025-11-25`; every call returned `is_error` True with the structured content intact;
  the stray `print` did not break the stdio stream; an unknown tool name raised
  `MCPError` at the client, as the specification lists unknown tools as protocol errors.
