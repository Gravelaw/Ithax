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
  CreateProject,
  ErrorBody,
  Issue,
  ModelBody,
  Project,
  ProjectEvent,
  SettingsBody,
  SettingsChange,
  SystemInfo,
  Template,
} from "./types";

export type ApiResult<T> =
  | { kind: "ok"; status: number; data: T }
  | { kind: "refused"; status: number; error: ErrorBody["error"]; issues: Issue[] }
  | { kind: "failed"; status: number; reason: "unreachable" | "not-json" };

export type Method = "GET" | "POST" | "PUT" | "DELETE";

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

  /** A request to a documented `/v1` path; `body` is sent as JSON when given. */
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
    if (body !== undefined) {
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

  getModel(pid: string): Promise<ApiResult<ModelBody>> {
    return this.request("GET", `/v1/projects/${encodeURIComponent(pid)}/model`);
  }

  projectEvents(pid: string, handlers: SocketHandlers<ProjectEvent>): EventSocket {
    return this.socket(`/v1/projects/${encodeURIComponent(pid)}/events`, handlers);
  }
}
