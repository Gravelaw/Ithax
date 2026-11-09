/**
 * The interface's only way to the engine service (spec 3 "API": no private channel).
 *
 * Every request goes to a documented `/v1` path on the service that served the page, with
 * `Authorization: Bearer <token>` and `X-Client: ui` (spec 3 "Service rules"); every
 * WebSocket sends `{"token": ...}` as its first message. Nothing else in the interface
 * calls `fetch` or `WebSocket`.
 *
 * Results are data, never exceptions: a request gives an `ApiResult`, which is
 * - `ok`: the response body, typed;
 * - `refused`: the service's error body, its spec 1 issue objects shown as they are (the
 *   interface never writes its own text for a model problem);
 * - `failed`: no usable answer (the service is unreachable, or answered something that is
 *   not its JSON), which the interface reports as lost contact.
 */
import type {
  ComponentType,
  CreateProject,
  DataFile,
  Edit,
  Engine,
  ErrorBody,
  FitBody,
  ImportedFile,
  Issue,
  Model,
  ModelBody,
  ModelWriteBody,
  Project,
  ProjectEvent,
  Run,
  RunEvent,
  SchemaBody,
  SettingsBody,
  SettingsChange,
  StartedRun,
  SummaryBody,
  SystemInfo,
  TableRow,
  Template,
  TemplateBody,
  ValidateBody,
} from "./types";

export type ApiResult<T> =
  | { kind: "ok"; status: number; data: T }
  | { kind: "refused"; status: number; error: ErrorBody["error"]; issues: Issue[] }
  | { kind: "failed"; status: number; reason: "unreachable" | "not-json" };

export type Method = "GET" | "POST" | "PUT" | "DELETE";

/** A file the service sent (a table as CSV, the project zip), with its media type. */
export interface Download {
  blob: Blob;
  type: string;
}

/** One request the client sent, for a request log (the M9 end-to-end test, AKS-121). */
export interface SentRequest {
  method: Method;
  path: string;
}

export interface WebSocketLike {
  readonly readyState: number;
  onopen: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent) => void) | null;
  onclose: ((event: CloseEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}

export type WebSocketFactory = (url: string) => WebSocketLike;

export interface ClientOptions {
  /** The service's origin, such as `http://127.0.0.1:8765`: the page's own. */
  origin: string;
  token: string;
  fetch?: typeof fetch;
  webSocket?: WebSocketFactory;
  /** Called for every request before it is sent. */
  onRequest?: (request: SentRequest) => void;
}

export interface SocketHandlers<E> {
  onEvent: (event: E) => void;
  /** The socket closed: `code` and `reason` as the service sent them (1008 with `E185`). */
  onClose?: (code: number, reason: string) => void;
}

export interface EventSocket {
  close(): void;
}

function isErrorBody(body: unknown): body is ErrorBody {
  if (typeof body !== "object" || body === null) return false;
  const candidate = body as Partial<ErrorBody>;
  return (
    typeof candidate.error === "object" &&
    candidate.error !== null &&
    typeof candidate.error.code === "string" &&
    typeof candidate.error.message === "string" &&
    Array.isArray(candidate.issues)
  );
}

export class ApiClient {
  readonly origin: string;
  private readonly token: string;
  private readonly fetcher: typeof fetch;
  private readonly openSocket: WebSocketFactory;
  private readonly onRequest: ((request: SentRequest) => void) | undefined;

  constructor(options: ClientOptions) {
    this.origin = options.origin.replace(/\/$/, "");
    this.token = options.token;
    this.fetcher = options.fetch ?? ((input, init) => globalThis.fetch(input, init));
    this.openSocket = options.webSocket ?? ((url) => new WebSocket(url));
    this.onRequest = options.onRequest;
  }

  /**
   * A request to a documented `/v1` path; `body` is sent as JSON when given, or as it is
   * when it is a form (`multipart/form-data`, the browser writes its boundary).
   */
  async request<T>(method: Method, path: string, body?: unknown): Promise<ApiResult<T>> {
    if (!path.startsWith("/v1/")) {
      throw new Error(`'${path}' is not a /v1 path of the service`);
    }
    this.onRequest?.({ method, path });
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.token}`,
      "X-Client": "ui",
      Accept: "application/json",
    };
    const init: RequestInit = { method, headers, cache: "no-store" };
    if (body instanceof FormData) {
      init.body = body;
    } else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
    let response: Response;
    try {
      response = await this.fetcher(this.origin + path, init);
    } catch {
      return { kind: "failed", status: 0, reason: "unreachable" };
    }
    let parsed: unknown;
    try {
      parsed = await response.json();
    } catch {
      return { kind: "failed", status: response.status, reason: "not-json" };
    }
    if (response.ok) {
      return { kind: "ok", status: response.status, data: parsed as T };
    }
    if (isErrorBody(parsed)) {
      return {
        kind: "refused",
        status: response.status,
        error: parsed.error,
        issues: parsed.issues,
      };
    }
    return { kind: "failed", status: response.status, reason: "not-json" };
  }

  /**
   * A `GET` of a documented `/v1` path that answers with a file rather than JSON (a CSV
   * table, the project zip): `ok` with its bytes; a refusal is the service's JSON error
   * body, as for `request`.
   */
  async download(path: string): Promise<ApiResult<Download>> {
    if (!path.startsWith("/v1/")) {
      throw new Error(`'${path}' is not a /v1 path of the service`);
    }
    this.onRequest?.({ method: "GET", path });
    const headers = { Authorization: `Bearer ${this.token}`, "X-Client": "ui" };
    let response: Response;
    try {
      response = await this.fetcher(this.origin + path, {
        method: "GET",
        headers,
        cache: "no-store",
      });
    } catch {
      return { kind: "failed", status: 0, reason: "unreachable" };
    }
    if (response.ok) {
      try {
        const blob = await response.blob();
        return {
          kind: "ok",
          status: response.status,
          data: { blob, type: response.headers.get("Content-Type") ?? "" },
        };
      } catch {
        return { kind: "failed", status: response.status, reason: "unreachable" };
      }
    }
    let parsed: unknown;
    try {
      parsed = await response.json();
    } catch {
      return { kind: "failed", status: response.status, reason: "not-json" };
    }
    if (isErrorBody(parsed)) {
      return {
        kind: "refused",
        status: response.status,
        error: parsed.error,
        issues: parsed.issues,
      };
    }
    return { kind: "failed", status: response.status, reason: "not-json" };
  }

  /** A WebSocket on a documented `/v1` path: the token message first, then each event. */
  socket<E>(path: string, handlers: SocketHandlers<E>): EventSocket {
    if (!path.startsWith("/v1/")) {
      throw new Error(`'${path}' is not a /v1 path of the service`);
    }
    this.onRequest?.({ method: "GET", path });
    const socket = this.openSocket(`${this.origin.replace(/^http/, "ws")}${path}`);
    socket.onopen = () => socket.send(JSON.stringify({ token: this.token }));
    socket.onmessage = (message) => {
      if (typeof message.data !== "string") return;
      let event: unknown;
      try {
        event = JSON.parse(message.data);
      } catch {
        return;
      }
      handlers.onEvent(event as E);
    };
    socket.onclose = (closed) => handlers.onClose?.(closed.code, closed.reason);
    return { close: () => socket.close(1000) };
  }

  getSystem(): Promise<ApiResult<SystemInfo>> {
    return this.request("GET", "/v1/system");
  }

  getSettings(): Promise<ApiResult<SettingsBody>> {
    return this.request("GET", "/v1/settings");
  }

  putSettings(change: SettingsChange): Promise<ApiResult<SettingsBody>> {
    return this.request("PUT", "/v1/settings", change);
  }

  listProjects(): Promise<ApiResult<Project[]>> {
    return this.request("GET", "/v1/projects");
  }

  createProject(project: CreateProject): Promise<ApiResult<Project>> {
    return this.request("POST", "/v1/projects", project);
  }

  openProject(path: string): Promise<ApiResult<Project>> {
    return this.request("POST", "/v1/projects/open", { path });
  }

  listTemplates(): Promise<ApiResult<Template[]>> {
    return this.request("GET", "/v1/templates");
  }

  /** `GET /v1/templates/{tid}`: one template, its lesson's text and its expected values. */
  getTemplate(tid: string): Promise<ApiResult<TemplateBody>> {
    return this.request("GET", `/v1/templates/${encodeURIComponent(tid)}`);
  }

  getModel(pid: string): Promise<ApiResult<ModelBody>> {
    return this.request("GET", `/v1/projects/${encodeURIComponent(pid)}/model`);
  }

  getSchema(): Promise<ApiResult<SchemaBody>> {
    return this.request("GET", "/v1/schema");
  }

  getComponentType(type: string): Promise<ApiResult<ComponentType>> {
    return this.request("GET", `/v1/schema/components/${encodeURIComponent(type)}`);
  }

  /** A whole model with `?base_revision=N` (spec 3: undo and redo write stored models). */
  putModel(pid: string, model: Model, baseRevision: number): Promise<ApiResult<ModelWriteBody>> {
    return this.request(
      "PUT",
      `/v1/projects/${encodeURIComponent(pid)}/model?base_revision=${baseRevision}`,
      model,
    );
  }

  editModel(pid: string, edits: Edit[], baseRevision: number): Promise<ApiResult<ModelWriteBody>> {
    return this.request("POST", `/v1/projects/${encodeURIComponent(pid)}/model/edits`, {
      edits,
      base_revision: baseRevision,
    });
  }

  validate(pid: string): Promise<ApiResult<ValidateBody>> {
    return this.request("POST", `/v1/projects/${encodeURIComponent(pid)}/validate`);
  }

  /** `GET .../data`: the imported files, in the order first imported. */
  listData(pid: string): Promise<ApiResult<DataFile[]>> {
    return this.request("GET", `/v1/projects/${encodeURIComponent(pid)}/data`);
  }

  /**
   * `POST .../data`: imports a CSV or Excel file under `name`, with the time unit of any
   * number column in `units` (`null` for plain numbers).
   */
  importData(
    pid: string,
    file: Blob,
    name: string,
    units?: Readonly<Record<string, string | null>>,
  ): Promise<ApiResult<ImportedFile>> {
    const form = new FormData();
    form.append("file", file, name);
    if (units !== undefined && Object.keys(units).length > 0) {
      form.append("units", JSON.stringify(units));
    }
    return this.request("POST", `/v1/projects/${encodeURIComponent(pid)}/data`, form);
  }

  /** `DELETE .../data/{file}`: the files that remain. */
  deleteData(pid: string, name: string): Promise<ApiResult<DataFile[]>> {
    return this.request(
      "DELETE",
      `/v1/projects/${encodeURIComponent(pid)}/data/${encodeURIComponent(name)}`,
    );
  }

  /** `POST .../data/{file}/fit`: the candidates, best first, and the column's histogram. */
  fitData(pid: string, name: string, column: string): Promise<ApiResult<FitBody>> {
    return this.request(
      "POST",
      `/v1/projects/${encodeURIComponent(pid)}/data/${encodeURIComponent(name)}/fit`,
      { column },
    );
  }

  projectEvents(pid: string, handlers: SocketHandlers<ProjectEvent>): EventSocket {
    return this.socket(`/v1/projects/${encodeURIComponent(pid)}/events`, handlers);
  }

  getEngines(): Promise<ApiResult<Engine[]>> {
    return this.request("GET", "/v1/engines");
  }

  /**
   * `POST .../runs`: a `process` model's run of `experimentId`; an `optimization` model's
   * with `null`, which sends no `experiment_id` (spec 3).
   */
  startRun(pid: string, experimentId: string | null): Promise<ApiResult<StartedRun>> {
    return this.request(
      "POST",
      `/v1/projects/${encodeURIComponent(pid)}/runs`,
      experimentId === null ? {} : { experiment_id: experimentId },
    );
  }

  /** `GET .../runs`: the project's runs in the order accepted. */
  listRuns(pid: string): Promise<ApiResult<Run[]>> {
    return this.request("GET", `/v1/projects/${encodeURIComponent(pid)}/runs`);
  }

  getRun(rid: string): Promise<ApiResult<Run>> {
    return this.request("GET", `/v1/runs/${encodeURIComponent(rid)}`);
  }

  cancelRun(rid: string): Promise<ApiResult<Run>> {
    return this.request("POST", `/v1/runs/${encodeURIComponent(rid)}/cancel`);
  }

  /** `GET /v1/runs/{rid}/events`: the state and the latest progress first, then each change. */
  runEvents(rid: string, handlers: SocketHandlers<RunEvent>): EventSocket {
    return this.socket(`/v1/runs/${encodeURIComponent(rid)}/events`, handlers);
  }

  getSummary(rid: string): Promise<ApiResult<SummaryBody>> {
    return this.request("GET", `/v1/runs/${encodeURIComponent(rid)}/summary`);
  }

  /** `GET .../tables/{name}?format=json`: one object per row. */
  getTable(rid: string, name: string): Promise<ApiResult<TableRow[]>> {
    return this.request(
      "GET",
      `/v1/runs/${encodeURIComponent(rid)}/tables/${encodeURIComponent(name)}?format=json`,
    );
  }

  /** `GET .../tables/{name}?format=csv`. */
  tableCsv(rid: string, name: string): Promise<ApiResult<Download>> {
    return this.download(
      `/v1/runs/${encodeURIComponent(rid)}/tables/${encodeURIComponent(name)}?format=csv`,
    );
  }

  /** `GET .../export`: the project folder as a zip (AKS-138). */
  exportProject(pid: string): Promise<ApiResult<Download>> {
    return this.download(`/v1/projects/${encodeURIComponent(pid)}/export`);
  }
}
