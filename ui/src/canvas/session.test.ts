import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Edit, Model } from "../api/types";
import { coffeeShop, ModelService, PID } from "../test/fakeModel";
import { FakeService } from "../test/fakes";
import { CanvasSession, MOVE_BURST_MS, RETRY_MS, VALIDATE_MS } from "./session";

const MODEL = `/v1/projects/${PID}/model`;
const EDITS = `/v1/projects/${PID}/model/edits`;
const VALIDATE = `/v1/projects/${PID}/validate`;

function setup(limit = 100) {
  const fake = new FakeService();
  const service = new ModelService(fake, { model: coffeeShop(), revision: 3 });
  const session = new CanvasSession(fake.client(), PID, { undoLimit: limit });
  return { fake, service, session };
}

const label = (id: string, text: string): Edit => ({ edit: "set_label", id, label: text });

function write(session: CanvasSession, edits: Edit[], name = "change") {
  return session.write(() => ({ kind: "edits", label: name, edits }));
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("the canvas's session with the service", () => {
  it("loads the model, opens the project's events and validates at once", async () => {
    const { fake, service, session } = setup();
    service.validateIssues = () => [
      {
        code: "W201",
        severity: "warning",
        component: "till",
        path: "/components/1",
        message: "x",
        hint: null,
      },
    ];
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(session.getState()).toMatchObject({ status: "ready", revision: 3, checking: false });
    expect(session.getState().model?.components).toHaveLength(3);
    expect(fake.sockets[0]?.url).toBe(`ws://127.0.0.1:8765/v1/projects/${PID}/events`);
    expect(fake.requested("POST", VALIDATE)).toHaveLength(1);
    expect(session.getState().issues.map((issue) => issue.code)).toEqual(["W201"]);
    session.stop();
    await vi.advanceTimersByTimeAsync(0);
    expect(fake.sockets[0]?.closedWith).toBe(1000);
  });

  it("says why the model cannot be loaded, as the service said it", async () => {
    const fake = new FakeService();
    const session = new CanvasSession(fake.client(), "gone", { undoLimit: 100 });
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    const state = session.getState();
    expect(state.status).toBe("unavailable");
    expect(state.loadProblem).toMatchObject({ kind: "refused", error: { code: "E185" } });
    expect(fake.sockets).toHaveLength(0);
  });

  it("sends each action as one batch with the current base_revision, and shows the answer", async () => {
    const { fake, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    const first = write(session, [label("till", "Till")]);
    const second = write(session, [label("exit", "Door")]);
    expect(session.getState().saving).toBe(true);
    await first;
    await second;
    const sent = fake.requested("POST", EDITS).map((request) => request.body);
    expect(sent).toEqual([
      { edits: [label("till", "Till")], base_revision: 3 },
      { edits: [label("exit", "Door")], base_revision: 4 },
    ]);
    const state = session.getState();
    expect(state.revision).toBe(5);
    expect(state.saving).toBe(false);
    expect(state.model?.components?.map((item) => item.label)).toEqual([undefined, "Till", "Door"]);
  });

  it("builds a write from the model as it is when the write is sent", async () => {
    const { fake, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    const seen: number[] = [];
    void write(session, [label("till", "A")]);
    await session.write((model: Model) => {
      seen.push(model.components?.filter((item) => item.label === "A").length ?? 0);
      return null;
    });
    expect(seen).toEqual([1]);
    expect(fake.requested("POST", EDITS)).toHaveLength(1);
  });

  it("validates half a second after the last write and drops older answers", async () => {
    const { fake, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(fake.requested("POST", VALIDATE)).toHaveLength(1);
    await write(session, [label("till", "A")]);
    await vi.advanceTimersByTimeAsync(VALIDATE_MS - 100);
    await write(session, [label("till", "B")]);
    expect(session.getState().checking).toBe(true);
    await vi.advanceTimersByTimeAsync(VALIDATE_MS - 1);
    expect(fake.requested("POST", VALIDATE)).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(fake.requested("POST", VALIDATE)).toHaveLength(2);
    expect(session.getState().checking).toBe(false);
  });

  it("asks again when the answer is for another revision, or when there was none", async () => {
    const { fake, service, session } = setup();
    let calls = 0;
    fake.on(`POST ${VALIDATE}`, () => {
      calls += 1;
      if (calls === 1) return { status: 200, body: { revision: 2, issues: [] } };
      if (calls === 2) return "unreachable";
      return { status: 200, body: { revision: service.revision, issues: [] } };
    });
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(session.getState().checking).toBe(true);
    await vi.advanceTimersByTimeAsync(VALIDATE_MS);
    expect(calls).toBe(2);
    expect(session.getState().checking).toBe(true);
    await vi.advanceTimersByTimeAsync(RETRY_MS);
    expect(calls).toBe(3);
    expect(session.getState().checking).toBe(false);
  });

  it("shows a validation refusal's issues", async () => {
    const { fake, session } = setup();
    fake.answer(
      `POST ${VALIDATE}`,
      {
        error: { code: "E186", message: "No." },
        issues: [
          {
            code: "E100",
            severity: "error",
            component: null,
            path: "/x",
            message: "m",
            hint: null,
          },
        ],
      },
      400,
    );
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(session.getState().issues.map((issue) => issue.code)).toEqual(["E100"]);
  });

  it("undoes and redoes by writing whole models with base_revision", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    const before = structuredClone(service.model);
    await write(session, [label("till", "Till")], "label till");
    const after = structuredClone(service.model);
    expect(session.getState().undoLabel).toBe("label till");
    await session.undo();
    const undo = fake.requested("PUT", MODEL)[0];
    expect(undo?.search).toBe("?base_revision=4");
    expect(undo?.body).toEqual(before);
    expect(session.getState()).toMatchObject({
      undoLabel: null,
      redoLabel: "label till",
      revision: 5,
    });
    await session.redo();
    const redo = fake.requested("PUT", MODEL)[1];
    expect(redo?.search).toBe("?base_revision=5");
    expect(redo?.body).toEqual(after);
    expect(session.getState()).toMatchObject({ undoLabel: "label till", redoLabel: null });
    // A new action clears the redo steps.
    await session.undo();
    await write(session, [label("exit", "Door")], "label exit");
    expect(session.getState()).toMatchObject({ undoLabel: "label exit", redoLabel: null });
    expect(await session.redo()).toBeNull();
  });

  it("keeps as many steps as Settings says", async () => {
    const { session } = setup(2);
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    for (const text of ["a", "b", "c"]) await write(session, [label("till", text)], text);
    await session.undo();
    await session.undo();
    expect(session.getState().undoLabel).toBeNull();
    expect(await session.undo()).toBeNull();
    // A smaller limit keeps the nearest steps.
    session.setUndoLimit(1);
    expect(session.getState().redoLabel).toBe("b");
    await session.redo();
    expect(await session.redo()).toBeNull();
  });

  it("keeps the model and its steps when the service refuses an edit", async () => {
    const { session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    const result = await write(session, [{ edit: "rename_component", id: "till", new_id: "exit" }]);
    expect(result).toMatchObject({ kind: "refused", error: { code: "E180" } });
    const state = session.getState();
    expect(state.refusal).toBe(result);
    expect(state.revision).toBe(3);
    expect(state.undoLabel).toBeNull();
    await write(session, [label("till", "T")]);
    expect(session.getState().refusal).toBeNull();
  });

  it("is read-only while a write gets no answer, and sends it again every 2 seconds", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    service.unreachable = true;
    const pending = write(session, [label("till", "T")]);
    await vi.advanceTimersByTimeAsync(0);
    expect(session.getState().failing).toBe(true);
    expect(await write(session, [label("exit", "E")])).toBeNull();
    expect(await session.undo()).toBeNull();
    await vi.advanceTimersByTimeAsync(RETRY_MS);
    expect(fake.requested("POST", EDITS)).toHaveLength(2);
    service.unreachable = false;
    await vi.advanceTimersByTimeAsync(RETRY_MS);
    expect((await pending)?.kind).toBe("ok");
    const sent = fake.requested("POST", EDITS).map((request) => request.body);
    expect(sent).toEqual([
      { edits: [label("till", "T")], base_revision: 3 },
      { edits: [label("till", "T")], base_revision: 3 },
      { edits: [label("till", "T")], base_revision: 3 },
    ]);
    expect(session.getState()).toMatchObject({ failing: false, revision: 4 });
  });

  it("reloads and clears undo on a revision it did not write, and ignores its own", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    const socket = fake.sockets[0];
    socket?.emit({ type: "model", revision: 3, client: null });
    // An event for the canvas's own write, even one arriving before the answer.
    const own = write(session, [label("till", "T")]);
    socket?.emit({ type: "model", revision: 4, client: "ui" });
    socket?.emit({ type: "run", run_id: "r", state: "queued" });
    await own;
    await vi.advanceTimersByTimeAsync(0);
    expect(fake.requested("GET", MODEL)).toHaveLength(1);
    expect(session.getState()).toMatchObject({ reloads: 0, undoLabel: "change" });

    service.outsideWrite((model) => {
      model.components?.pop();
    });
    socket?.emit({ type: "model", revision: 5, client: "mcp" });
    await vi.advanceTimersByTimeAsync(0);
    expect(fake.requested("GET", MODEL)).toHaveLength(2);
    expect(session.getState()).toMatchObject({ reloads: 1, revision: 5, undoLabel: null });
    expect(session.getState().model?.components).toHaveLength(2);
  });

  it("reloads and clears undo when its write raced another (409 E181)", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    await write(session, [label("till", "T")]);
    service.outsideWrite(() => undefined);
    const result = await write(session, [label("exit", "E")]);
    expect(result).toMatchObject({ kind: "refused", error: { code: "E181" } });
    expect(fake.requested("GET", MODEL)).toHaveLength(2);
    expect(session.getState()).toMatchObject({ revision: 5, undoLabel: null, refusal: result });
  });

  it("sends a burst of moves as one write, half a second after the last", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    session.move(new Map([["exit", { x: 488, y: 0 }]]));
    expect(session.getState().saving).toBe(true);
    await vi.advanceTimersByTimeAsync(MOVE_BURST_MS - 100);
    session.move(new Map([["exit", { x: 496, y: 0 }]]));
    await vi.advanceTimersByTimeAsync(MOVE_BURST_MS - 1);
    expect(fake.requested("POST", EDITS)).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(1);
    expect(fake.requested("POST", EDITS).map((request) => request.body)).toEqual([
      { edits: [{ edit: "set_ui", id: "exit", ui: { x: 496, y: 0 } }], base_revision: 3 },
    ]);
    expect(service.component("exit")?.ui).toEqual({ x: 496, y: 0 });
    expect(session.getState()).toMatchObject({ saving: false, undoLabel: "move exit" });
  });

  it("sends a waiting move before a write, so the write follows it", async () => {
    const { fake, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    session.move(new Map([["exit", { x: 8, y: 8 }]]));
    await write(session, [label("till", "T")], "label till");
    expect(fake.requested("POST", EDITS).map((request) => request.body)).toEqual([
      { edits: [{ edit: "set_ui", id: "exit", ui: { x: 8, y: 8 } }], base_revision: 3 },
      { edits: [label("till", "T")], base_revision: 4 },
    ]);
    await vi.advanceTimersByTimeAsync(MOVE_BURST_MS);
    expect(fake.requested("POST", EDITS)).toHaveLength(2);
  });

  it("undo during a burst undoes the move, not the step before it", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    await write(session, [label("till", "T")], "label till");
    session.move(new Map([["exit", { x: 8, y: 8 }]]));
    await session.undo();
    expect(fake.requested("POST", EDITS)).toHaveLength(2);
    expect(service.component("exit")?.ui).toEqual({ x: 480, y: 0 });
    expect(service.component("till")?.label).toBe("T");
    expect(session.getState()).toMatchObject({ undoLabel: "label till", redoLabel: "move exit" });
    await vi.advanceTimersByTimeAsync(MOVE_BURST_MS * 2);
    expect(fake.requested("POST", EDITS)).toHaveLength(2);
    expect(session.getState().redoLabel).toBe("move exit");
  });

  it("redo during a burst sends the move, which is a new action and clears redo", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    await write(session, [label("till", "T")], "label till");
    await session.undo();
    session.move(new Map([["exit", { x: 8, y: 8 }]]));
    expect(await session.redo()).toBeNull();
    expect(service.component("exit")?.ui).toEqual({ x: 8, y: 8 });
    expect(service.component("till")?.label).toBeUndefined();
    expect(fake.requested("PUT", MODEL)).toHaveLength(1);
    expect(session.getState()).toMatchObject({ undoLabel: "move exit", redoLabel: null });
  });

  it("sends a waiting move before reloading for another client's revision", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    session.move(new Map([["exit", { x: 8, y: 8 }]]));
    service.outsideWrite(() => undefined);
    fake.sockets[0]?.emit({ type: "model", revision: 4, client: "mcp" });
    await vi.advanceTimersByTimeAsync(0);
    // Its base revision is stale now, so the service refuses it and the canvas reloads.
    expect(fake.requested("POST", EDITS)).toHaveLength(1);
    expect(fake.requested("GET", MODEL).length).toBeGreaterThanOrEqual(2);
    expect(session.getState()).toMatchObject({ revision: 4, undoLabel: null });
  });

  it("sends a waiting move and the writes queued when it stops, then closes", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    void write(session, [label("till", "T")]);
    session.move(new Map([["exit", { x: 8, y: 8 }]]));
    session.stop();
    session.stop();
    expect(await write(session, [label("arrivals", "A")])).toBeNull();
    session.move(new Map([["till", { x: 0, y: 0 }]]));
    await vi.advanceTimersByTimeAsync(MOVE_BURST_MS);
    expect(fake.requested("POST", EDITS).map((request) => request.body)).toEqual([
      { edits: [label("till", "T")], base_revision: 3 },
      { edits: [{ edit: "set_ui", id: "exit", ui: { x: 8, y: 8 } }], base_revision: 4 },
    ]);
    expect(service.revision).toBe(5);
    expect(fake.sockets[0]?.closedWith).toBe(1000);
  });

  it("does not retry a write with no answer once stopped", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    service.unreachable = true;
    void write(session, [label("till", "T")]);
    session.stop();
    await vi.advanceTimersByTimeAsync(RETRY_MS * 3);
    expect(fake.requested("POST", EDITS)).toHaveLength(1);
    fake.sockets[0]?.emit({ type: "model", revision: 9, client: "mcp" });
    await vi.advanceTimersByTimeAsync(0);
    expect(fake.requested("GET", MODEL)).toHaveLength(1);
  });

  it("says when the project's events stop", async () => {
    const { fake, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    fake.sockets[0]?.serverClose(1011, "gone");
    expect(session.getState().eventsClosed).toBe("gone");
  });
});
