import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Edit, Model } from "../api/types";
import { coffeeShop, ModelService, PID } from "../test/fakeModel";
import { FakeService } from "../test/fakes";
import { CanvasSession, clientsOf, MOVE_BURST_MS, RETRY_MS, VALIDATE_MS } from "./session";

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

  it("takes one write at a time: a change asked while one awaits its answer is refused", async () => {
    const { fake, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(session.canWrite()).toBe(true);
    const first = write(session, [label("till", "Till")]);
    expect(session.getState()).toMatchObject({ saving: true, busy: true });
    expect(session.canWrite()).toBe(false);
    expect(await write(session, [label("exit", "Door")])).toBeNull();
    expect(await session.undo()).toBeNull();
    expect(await session.redo()).toBeNull();
    expect(await session.move(new Map([["exit", { x: 0, y: 0 }]]))).toBeNull();
    await first;
    expect(session.getState()).toMatchObject({ saving: false, busy: false, revision: 4 });
    await write(session, [label("exit", "Door")]);
    expect(fake.requested("POST", EDITS).map((request) => request.body)).toEqual([
      { edits: [label("till", "Till")], base_revision: 3 },
      { edits: [label("exit", "Door")], base_revision: 4 },
    ]);
    expect(session.getState().model?.components?.map((item) => item.label)).toEqual([
      undefined,
      "Till",
      "Door",
    ]);
  });

  it("builds a write from the model shown, and sends nothing for a plan of nothing", async () => {
    const { fake, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    await write(session, [label("till", "A")]);
    const seen: (string | undefined)[] = [];
    expect(
      await session.write((model: Model) => {
        seen.push(model.components?.[1]?.label);
        return null;
      }),
    ).toBeNull();
    expect(seen).toEqual(["A"]);
    expect(session.getState().busy).toBe(false);
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

  it("judges another client's revision, announced during a write, once the write answers", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    const own = write(session, [label("till", "T")]);
    service.outsideWrite(() => undefined);
    fake.sockets[0]?.emit({ type: "model", revision: 5, client: "mcp" });
    expect(fake.requested("GET", MODEL)).toHaveLength(1);
    await own;
    await vi.advanceTimersByTimeAsync(0);
    expect(fake.requested("GET", MODEL)).toHaveLength(2);
    expect(session.getState()).toMatchObject({ reloads: 1, busy: false, undoLabel: null });
  });

  it("reloads once for a revision the service does not have, then trusts the service", async () => {
    const { fake, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    fake.sockets[0]?.emit({ type: "model", revision: 99, client: "mcp" });
    await vi.advanceTimersByTimeAsync(RETRY_MS);
    expect(fake.requested("GET", MODEL)).toHaveLength(2);
    expect(session.getState()).toMatchObject({ busy: false, revision: 3, reloads: 1 });
  });

  it("reads again when a newer revision is announced while a reload is under way", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    let reads = 0;
    fake.on(`GET ${MODEL}`, () => {
      reads += 1;
      const answer = { model: structuredClone(service.model), revision: service.revision };
      if (reads === 1) {
        // Another write lands, and is announced, after this read was answered.
        service.outsideWrite((model) => {
          model.components?.pop();
        });
        fake.sockets[0]?.emit({ type: "model", revision: service.revision, client: "mcp" });
      }
      return { status: 200, body: answer };
    });
    service.outsideWrite(() => undefined);
    fake.sockets[0]?.emit({ type: "model", revision: service.revision, client: "mcp" });
    await vi.advanceTimersByTimeAsync(0);
    expect(reads).toBe(2);
    expect(session.getState()).toMatchObject({ revision: 5, busy: false, reloads: 2 });
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

  it("sends each move at once; moves of the same blocks close together are one undo step", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    const before = structuredClone(service.model);
    await session.move(new Map([["exit", { x: 488, y: 0 }]]), true);
    await vi.advanceTimersByTimeAsync(MOVE_BURST_MS - 100);
    await session.move(new Map([["exit", { x: 496, y: 0 }]]), true);
    expect(fake.requested("POST", EDITS).map((request) => request.body)).toEqual([
      { edits: [{ edit: "set_ui", id: "exit", ui: { x: 488, y: 0 } }], base_revision: 3 },
      { edits: [{ edit: "set_ui", id: "exit", ui: { x: 496, y: 0 } }], base_revision: 4 },
    ]);
    expect(session.getState().undoLabel).toBe("move exit");
    await session.undo();
    expect(fake.requested("PUT", MODEL)[0]?.body).toEqual(before);
    expect(session.getState()).toMatchObject({ undoLabel: null, redoLabel: "move exit" });
  });

  it("makes separate steps of moves apart in time, of other blocks, or with a write between", async () => {
    const { session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    await session.move(new Map([["exit", { x: 1, y: 0 }]]), true);
    await vi.advanceTimersByTimeAsync(MOVE_BURST_MS);
    await session.move(new Map([["exit", { x: 2, y: 0 }]]), true);
    await session.move(new Map([["till", { x: 3, y: 0 }]]), true);
    await write(session, [label("till", "T")]);
    await session.move(new Map([["till", { x: 4, y: 0 }]]), true);
    await session.move(new Map([["till", { x: 5, y: 0 }]]));
    let undone = 0;
    while (session.getState().undoLabel !== null && undone < 10) {
      await session.undo();
      undone += 1;
    }
    // exit 1; exit 2 (apart in time); till 3 (another block); the write; till 4 (after a
    // write); till 5 (a drag's end, never part of a burst).
    expect(undone).toBe(6);
    expect(await session.move(new Map())).toBeNull();
  });

  it("retries a move while the service does not answer, as any write", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    service.unreachable = true;
    const move = session.move(new Map([["exit", { x: 8, y: 8 }]]), true);
    await vi.advanceTimersByTimeAsync(0);
    expect(session.getState()).toMatchObject({ failing: true, busy: true });
    expect(await session.move(new Map([["exit", { x: 16, y: 8 }]]), true)).toBeNull();
    await vi.advanceTimersByTimeAsync(RETRY_MS);
    service.unreachable = false;
    await vi.advanceTimersByTimeAsync(RETRY_MS);
    expect((await move)?.kind).toBe("ok");
    expect(service.component("exit")?.ui).toEqual({ x: 8, y: 8 });
    expect(fake.requested("POST", EDITS)).toHaveLength(3);
    expect(session.getState()).toMatchObject({
      failing: false,
      busy: false,
      undoLabel: "move exit",
    });
  });

  it("answers the write in flight when it stops, then closes", async () => {
    const { fake, service, session } = setup();
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    void write(session, [label("till", "T")]);
    session.stop();
    session.stop();
    expect(await write(session, [label("arrivals", "A")])).toBeNull();
    await vi.advanceTimersByTimeAsync(0);
    expect(fake.requested("POST", EDITS)).toHaveLength(1);
    expect(service.revision).toBe(4);
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

describe("the review of an outside change (AKS-137)", () => {
  async function opened() {
    const parts = setup();
    parts.session.start();
    await vi.advanceTimersByTimeAsync(0);
    return parts;
  }

  function outside(
    fake: FakeService,
    service: ModelService,
    change: (model: Model) => void,
    client: string | null = "mcp",
  ) {
    service.outsideWrite(change);
    fake.sockets[0]?.emit({ type: "model", revision: service.revision, client });
  }

  const capacity = (model: Model) => {
    const till = model.components?.find((item) => item.id === "till");
    if (till) till.params.capacity = 2;
  };

  it("marks what another client changed and names the client, keeping its own writes out", async () => {
    const { fake, service, session } = await opened();
    const own = write(session, [label("till", "T")]);
    fake.sockets[0]?.emit({ type: "model", revision: 4, client: "ui" });
    await own;
    outside(fake, service, capacity, "script");
    await vi.advanceTimersByTimeAsync(0);
    const state = session.getState();
    expect(state.outside).toMatchObject({ from: 4, to: 5, conflict: false });
    expect(clientsOf(state)).toEqual(["script"]);
    expect(state.review.map((item) => item.ref)).toEqual([
      { kind: "list", key: "components", id: "till" },
    ]);
    expect(session.marks()).toHaveLength(1);
    expect(state.undoLabel).toBeNull();
  });

  it("takes a 409 E181 as an outside change, with the client of the event", async () => {
    const { fake, service, session } = await opened();
    service.outsideWrite(capacity);
    await write(session, [label("till", "T")]);
    await vi.advanceTimersByTimeAsync(0);
    expect(session.getState().outside).toMatchObject({ from: 3, to: 4, conflict: true });
    expect(clientsOf(session.getState())).toEqual([]);
    fake.sockets[0]?.emit({ type: "model", revision: 4, client: "mcp" });
    expect(clientsOf(session.getState())).toEqual(["mcp"]);
    expect(session.marks()).toHaveLength(1);
  });

  it("accepts without writing, and refuses while a write awaits its answer", async () => {
    const { fake, service, session } = await opened();
    outside(fake, service, (model) => {
      capacity(model);
      model.meta = { name: "Cafe" };
    });
    await vi.advanceTimersByTimeAsync(0);
    const [first, second] = session.marks();
    const release = fake.holdWrites();
    const pending = write(session, [label("exit", "E")]);
    expect(session.accept(first?.id ?? 0)).toBe(false);
    expect(session.marks()).toHaveLength(2);
    release();
    await pending;
    const writes = fake.requests.length;
    expect(session.accept(first?.id ?? 0)).toBe(true);
    expect(session.marks().map((item) => item.id)).toEqual([second?.id]);
    expect(session.acceptAll()).toBe(true);
    expect(session.marks()).toEqual([]);
    expect(fake.requests.length).toBe(writes);
  });

  it("rejects with a whole-model write and base_revision, one undo step that brings the mark back", async () => {
    const { fake, service, session } = await opened();
    outside(fake, service, (model) => {
      capacity(model);
      model.components?.push({ id: "queue_1", type: "queue", params: {} });
    });
    await vi.advanceTimersByTimeAsync(0);
    const [changed] = session.marks();
    await session.reject(changed?.id ?? 0);
    const put = fake.requested("PUT", MODEL).at(-1);
    expect(put?.search).toBe("?base_revision=4");
    expect(service.component("till")?.params.capacity).toEqual({ $param: "tills" });
    expect(service.component("queue_1")).toBeDefined();
    expect(session.marks().map((item) => item.ref)).toEqual([
      { kind: "list", key: "components", id: "queue_1" },
    ]);
    expect(session.getState().undoLabel).toBe("reject the change to block till");
    await session.undo();
    expect(session.marks()).toHaveLength(2);
    await session.rejectAll();
    expect(service.model).toEqual(coffeeShop());
    expect(session.marks()).toEqual([]);
  });

  it("ends a mark when the user changes the item, and keeps the others", async () => {
    const { fake, service, session } = await opened();
    outside(fake, service, (model) => {
      capacity(model);
      model.meta = { name: "Cafe" };
    });
    await vi.advanceTimersByTimeAsync(0);
    await write(session, [label("till", "Mine")]);
    expect(session.marks().map((item) => item.ref)).toEqual([{ kind: "top", key: "meta" }]);
  });

  it("adds a later outside change to the marks, keeping an item's first before", async () => {
    const { fake, service, session } = await opened();
    outside(fake, service, capacity);
    await vi.advanceTimersByTimeAsync(0);
    outside(
      fake,
      service,
      (model) => {
        const till = model.components?.find((item) => item.id === "till");
        if (till) till.params.capacity = 3;
        model.meta = { name: "Cafe" };
      },
      "ui",
    );
    await vi.advanceTimersByTimeAsync(0);
    expect(session.getState().outside).toMatchObject({ from: 4, to: 5 });
    expect(clientsOf(session.getState())).toEqual(["ui"]);
    expect(session.marks()).toHaveLength(2);
    const till = session.marks().find((item) => item.ref.kind === "list");
    await session.reject(till?.id ?? 0);
    expect(service.component("till")?.params.capacity).toEqual({ $param: "tills" });
  });

  it("refuses Reject while a write awaits its answer, and for a mark no longer shown", async () => {
    const { fake, service, session } = await opened();
    outside(fake, service, capacity);
    await vi.advanceTimersByTimeAsync(0);
    const [mark] = session.marks();
    const release = fake.holdWrites();
    const pending = write(session, [label("exit", "E")]);
    expect(await session.reject(mark?.id ?? 0)).toBeNull();
    expect(await session.rejectAll()).toBeNull();
    release();
    await pending;
    expect(await session.reject(999)).toBeNull();
    expect(fake.requested("PUT", MODEL)).toHaveLength(0);
  });
});
