import { describe, expect, it, vi } from "vitest";
import { errorBody, FakeService, issue, ORIGIN, TOKEN } from "../test/fakes";
import { ApiClient } from "./client";

describe("ApiClient requests", () => {
  it("sends the token and X-Client: ui to the service's own origin", async () => {
    const service = new FakeService().answer("GET /v1/system", { tier: "mid" });
    const result = await service.client().getSystem();
    expect(result).toEqual({ kind: "ok", status: 200, data: { tier: "mid" } });
    const [request] = service.requests;
    expect(request?.headers.authorization).toBe(`Bearer ${TOKEN}`);
    expect(request?.headers["x-client"]).toBe("ui");
    expect(request?.body).toBeUndefined();
  });

  it("sends a body as JSON", async () => {
    const service = new FakeService().answer("POST /v1/projects", { id: "p" });
    await service.client().createProject({ name: "Shop", domain: "optimization" });
    const [request] = service.requests;
    expect(request?.headers["content-type"]).toBe("application/json");
    expect(request?.body).toEqual({ name: "Shop", domain: "optimization" });
  });

  it("gives a refusal's issue objects as data", async () => {
    const issues = [issue("E184", "The request field 'name' is empty.", "/name")];
    const service = new FakeService().answer(
      "POST /v1/projects",
      errorBody("E184", "The request field 'name' is empty.", issues),
      400,
    );
    const result = await service.client().createProject({ name: "" });
    expect(result).toEqual({
      kind: "refused",
      status: 400,
      error: { code: "E184", message: "The request field 'name' is empty." },
      issues,
    });
  });

  it("reports an unreachable service as failed", async () => {
    const service = new FakeService().on("GET /v1/projects", () => "unreachable");
    expect(await service.client().listProjects()).toEqual({
      kind: "failed",
      status: 0,
      reason: "unreachable",
    });
  });

  it("reports an answer that is not the service's JSON as failed", async () => {
    const html = vi.fn(async () => new Response("<html>", { status: 200 }));
    const client = new ApiClient({ origin: ORIGIN, token: TOKEN, fetch: html });
    expect(await client.getSettings()).toMatchObject({ kind: "failed", reason: "not-json" });
    const service = new FakeService().answer("GET /v1/settings", { detail: "no" }, 500);
    expect(await service.client().getSettings()).toEqual({
      kind: "failed",
      status: 500,
      reason: "not-json",
    });
  });

  it("refuses a path outside /v1", async () => {
    const client = new FakeService().client();
    await expect(client.request("GET", "/private")).rejects.toThrow("/v1");
    expect(() => client.socket("/events", { onEvent: () => {} })).toThrow("/v1");
  });

  it("logs every request before it is sent", async () => {
    const log: string[] = [];
    const service = new FakeService().answer("GET /v1/templates", []);
    const client = service.client((request) => log.push(`${request.method} ${request.path}`));
    await client.listTemplates();
    client.projectEvents("p 1", { onEvent: () => {} });
    expect(log).toEqual(["GET /v1/templates", "GET /v1/projects/p%201/events"]);
  });

  it.each([
    ["getSystem", [], "GET", "/v1/system"],
    ["getSettings", [], "GET", "/v1/settings"],
    ["putSettings", [{ tier: "low" }], "PUT", "/v1/settings"],
    ["listProjects", [], "GET", "/v1/projects"],
    ["createProject", [{ name: "a" }], "POST", "/v1/projects"],
    ["openProject", ["/home/a"], "POST", "/v1/projects/open"],
    ["listTemplates", [], "GET", "/v1/templates"],
    ["getModel", ["abc"], "GET", "/v1/projects/abc/model"],
  ] as const)("%s calls %s %s", async (method, args, verb, path) => {
    const service = new FakeService();
    const client = service.client() as unknown as Record<string, (...a: unknown[]) => unknown>;
    await client[method]?.(...args);
    expect(service.requests.map((request) => `${request.method} ${request.path}`)).toEqual([
      `${verb} ${path}`,
    ]);
  });

  it("sends the open path as its body", async () => {
    const service = new FakeService();
    await service.client().openProject("/home/me/shop");
    expect(service.requests[0]?.body).toEqual({ path: "/home/me/shop" });
  });

  it("uses the page's fetch when none is given", async () => {
    const page = vi.fn(async () => new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", page);
    const client = new ApiClient({ origin: `${ORIGIN}/`, token: TOKEN });
    expect(await client.listTemplates()).toEqual({ kind: "ok", status: 200, data: [] });
    expect(page).toHaveBeenCalledWith(`${ORIGIN}/v1/templates`, expect.anything());
    vi.unstubAllGlobals();
  });
});

describe("ApiClient sockets", () => {
  it("opens the ws address and sends the token message first", () => {
    const service = new FakeService();
    service.client().projectEvents("abc", { onEvent: () => {} });
    const [socket] = service.sockets;
    expect(socket?.url).toBe("ws://127.0.0.1:8765/v1/projects/abc/events");
    expect(socket?.sent).toEqual([]);
    socket?.open();
    expect(socket?.sent).toEqual([JSON.stringify({ token: TOKEN })]);
  });

  it("passes each JSON event on and skips what is not JSON text", () => {
    const service = new FakeService();
    const events: unknown[] = [];
    service.client().projectEvents("abc", { onEvent: (event) => events.push(event) });
    const socket = service.sockets[0];
    socket?.emit({ type: "model", revision: 3, client: null });
    socket?.emit("not json");
    socket?.emitRaw(new ArrayBuffer(2));
    expect(events).toEqual([{ type: "model", revision: 3, client: null }]);
  });

  it("reports how the service closed the socket, and closes it normally", () => {
    const service = new FakeService();
    const closes: [number, string][] = [];
    const events = service.client().projectEvents("abc", {
      onEvent: () => {},
      onClose: (code, reason) => closes.push([code, reason]),
    });
    service.sockets[0]?.serverClose(1008, "E185");
    expect(closes).toEqual([[1008, "E185"]]);
    events.close();
    expect(service.sockets[0]?.closedWith).toBe(1000);
  });

  it("closes quietly without an onClose handler", () => {
    const service = new FakeService();
    service.client().projectEvents("abc", { onEvent: () => {} });
    expect(() => service.sockets[0]?.serverClose(1000, "")).not.toThrow();
  });

  it("uses the page's WebSocket when none is given", () => {
    const made: string[] = [];
    class PageSocket {
      constructor(url: string) {
        made.push(url);
      }
    }
    vi.stubGlobal("WebSocket", PageSocket);
    new ApiClient({ origin: ORIGIN, token: TOKEN }).socket("/v1/runs/r/events", {
      onEvent: () => {},
    });
    expect(made).toEqual(["ws://127.0.0.1:8765/v1/runs/r/events"]);
    vi.unstubAllGlobals();
  });
});

describe("ApiClient data routes (AKS-120)", () => {
  it("imports a file as a multipart form, with the units as JSON text", async () => {
    const service = new FakeService().answer("POST /v1/projects/p%201/data", { name: "a.csv" });
    const file = new Blob(["gap\n1\n"], { type: "text/csv" });
    await service.client().importData("p 1", file, "a.csv", { gap: "min" });
    const [request] = service.requests;
    expect(request?.path).toBe("/v1/projects/p%201/data");
    // The browser writes the multipart boundary itself: no JSON content type is set.
    expect(request?.headers["content-type"]).toBeUndefined();
    const form = request?.body as FormData;
    expect((form.get("file") as File).name).toBe("a.csv");
    expect(await (form.get("file") as File).text()).toBe("gap\n1\n");
    expect(form.get("units")).toBe('{"gap":"min"}');
  });

  it("sends no units part when none are given", async () => {
    const service = new FakeService().answer("POST /v1/projects/p/data", { name: "a.csv" });
    await service.client().importData("p", new Blob(["x\n1\n"]), "a.csv");
    await service.client().importData("p", new Blob(["x\n1\n"]), "a.csv", {});
    for (const request of service.requests) {
      expect((request.body as FormData).has("units")).toBe(false);
    }
  });

  it("lists, removes and fits files at their documented paths", async () => {
    const service = new FakeService()
      .answer("GET /v1/projects/p/data", [])
      .answer("DELETE /v1/projects/p/data/a%20b.csv", [])
      .answer("POST /v1/projects/p/data/a%20b.csv/fit", { candidates: [] });
    const client = service.client();
    await client.listData("p");
    await client.deleteData("p", "a b.csv");
    await client.fitData("p", "a b.csv", "gap");
    expect(service.requests.map((item) => `${item.method} ${item.path}`)).toEqual([
      "GET /v1/projects/p/data",
      "DELETE /v1/projects/p/data/a%20b.csv",
      "POST /v1/projects/p/data/a%20b.csv/fit",
    ]);
    expect(service.requests[2]?.body).toEqual({ column: "gap" });
  });
});
