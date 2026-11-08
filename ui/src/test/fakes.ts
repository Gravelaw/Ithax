/**
 * A fake engine service for component tests: `fetch` answers from handlers keyed by
 * `"METHOD /path"` and records every request; `FakeSocket` stands in for a WebSocket.
 */
import { ApiClient, type WebSocketLike } from "../api/client";
import type { Issue, Settings } from "../api/types";
import { DEFAULT_PREFERENCES } from "../settings/preferences";

export const ORIGIN = "http://127.0.0.1:8765";
export const TOKEN = "test-token";

export interface Recorded {
  method: string;
  path: string;
  /** The query, such as `?base_revision=3`, or `""`. */
  search: string;
  headers: Record<string, string>;
  body: unknown;
}

export type Handler = (
  body: unknown,
  url: URL,
) => { status: number; body: unknown } | "unreachable";

export function errorBody(code: string, message: string, issues: unknown[] = []) {
  return { error: { code, message }, issues };
}

export function issue(code: string, message: string, path = "", hint: string | null = null): Issue {
  return { code, severity: "error", component: null, path, message, hint };
}

export const SETTINGS: Settings = {
  tier: "mid",
  max_concurrent_runs: 1,
  run_time_limit_s: 600,
  run_memory_limit_bytes: 8 * 1024 ** 3,
  finding_thresholds: {
    bottleneck_utilization: 0.85,
    idle_utilization: 0.3,
    relative_half_width: 0.1,
    min_time_s: 60,
    min_rate_per_s: 1 / 3600,
  },
  interface: { ...DEFAULT_PREFERENCES },
};

export class FakeService {
  readonly requests: Recorded[] = [];
  readonly sockets: FakeSocket[] = [];
  private readonly handlers = new Map<string, Handler>();
  /** While holding, each write (`POST` or `PUT`, except validation) waits its turn. */
  private holding = false;
  private readonly waiting: (() => void)[] = [];

  /** Holds every write until the returned function is called. */
  holdWrites(): () => void {
    this.holding = true;
    return () => {
      this.holding = false;
      for (const go of this.waiting.splice(0)) go();
    };
  }

  /** How many writes are waiting to be let through. */
  get held(): number {
    return this.waiting.length;
  }

  /** Lets the first held write through; resolves once one was waiting. */
  async releaseOne(): Promise<void> {
    while (this.waiting.length === 0) await new Promise((resolve) => setTimeout(resolve, 5));
    this.waiting.shift()?.();
  }

  on(route: string, handler: Handler): this {
    this.handlers.set(route, handler);
    return this;
  }

  /** Answers `route` with `body` and `status` (200 by default). */
  answer(route: string, body: unknown, status = 200): this {
    return this.on(route, () => ({ status, body }));
  }

  readonly fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = new URL(String(input));
    const method = init?.method ?? "GET";
    const headers = Object.fromEntries(new Headers(init?.headers).entries());
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    this.requests.push({ method, path: url.pathname, search: url.search, headers, body });
    // A slow service: writes wait here until the test opens the gate.
    if (this.holding && (method === "POST" || method === "PUT")) {
      if (!url.pathname.endsWith("/validate")) {
        await new Promise<void>((resolve) => this.waiting.push(resolve));
      }
    }
    const handler = this.handlers.get(`${method} ${url.pathname}`);
    const answer = handler
      ? handler(body, url)
      : { status: 404, body: errorBody("E185", `The service has no '${url.pathname}'.`) };
    if (answer === "unreachable") throw new TypeError("Failed to fetch");
    return new Response(JSON.stringify(answer.body), {
      status: answer.status,
      headers: { "Content-Type": "application/json" },
    });
  };

  readonly webSocket = (url: string): WebSocketLike => {
    const socket = new FakeSocket(url);
    this.sockets.push(socket);
    return socket;
  };

  client(onRequest?: ApiClientOptions["onRequest"]): ApiClient {
    return new ApiClient({
      origin: ORIGIN,
      token: TOKEN,
      fetch: this.fetch,
      webSocket: this.webSocket,
      ...(onRequest ? { onRequest } : {}),
    });
  }

  requested(method: string, path: string): Recorded[] {
    return this.requests.filter((request) => request.method === method && request.path === path);
  }
}

type ApiClientOptions = ConstructorParameters<typeof ApiClient>[0];

export class FakeSocket implements WebSocketLike {
  readyState = 0;
  readonly sent: string[] = [];
  closedWith: number | undefined;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(readonly url: string) {}

  send(data: string): void {
    this.sent.push(data);
  }

  close(code?: number): void {
    this.closedWith = code;
  }

  open(): void {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }

  emit(data: unknown): void {
    const text = typeof data === "string" ? data : JSON.stringify(data);
    this.onmessage?.(new MessageEvent("message", { data: text }));
  }

  emitRaw(data: unknown): void {
    this.onmessage?.(new MessageEvent("message", { data }));
  }

  serverClose(code: number, reason: string): void {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close", { code, reason }));
  }
}

/** A fake service that answers what the app asks for at start. */
export function startedService(settings: Settings = SETTINGS): FakeService {
  return new FakeService()
    .answer("GET /v1/settings", { settings, issues: [] })
    .answer("GET /v1/projects", [])
    .answer("GET /v1/templates", []);
}
