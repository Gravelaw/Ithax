/**
 * The write rule as a whole (review of PR #45): one write at a time, and no change taken
 * while one awaits its answer. Seeded scripts of user actions (edit a setting, label,
 * rename, move, connect, delete, add, undo, redo), each built as the Canvas builds it from
 * the model shown, are played against a slow service whose answers come after a number of
 * further actions the seed chooses. An action asked while a write awaits its answer must
 * be refused (and the session says it is busy); the saved model must equal the accepted
 * actions played again one after another. Each script starts after another client's
 * write, so the review's Accept and Reject (AKS-137) are among the actions, under the
 * same rule.
 */
import { describe, expect, it } from "vitest";
import type { Component, Edit, Model } from "../api/types";
import { emptyModel, ModelService, PID } from "../test/fakeModel";
import { FakeService } from "../test/fakes";
import { nextId, positionOf } from "./model";
import { editsWrite, settingPlan } from "./plans";
import { CanvasSession } from "./session";

/** A small seeded generator (mulberry32), so every run of a seed is the same. */
function random(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

type Action =
  | { kind: "label"; block: string; text: string }
  | { kind: "setting"; block: string; capacity: number }
  | { kind: "rename"; block: string; to: string }
  | { kind: "nudge"; block: string; dx: number }
  | { kind: "connect"; from: string; to: string }
  | { kind: "delete"; block: string }
  | { kind: "add" }
  | { kind: "undo" }
  | { kind: "redo" }
  | { kind: "accept"; pick: number }
  | { kind: "reject"; pick: number };

const BLOCKS = ["b1", "b2", "b3", "b4"];

function script(seed: number, length: number): Action[] {
  const next = random(seed);
  const pick = <T>(items: readonly T[]): T => items[Math.floor(next() * items.length)] as T;
  const alive = new Set(BLOCKS);
  const actions: Action[] = [];
  let names = 0;
  for (let step = 0; step < length; step += 1) {
    const live = [...alive];
    const roll = next();
    if (live.length === 0 || roll < 0.08) actions.push({ kind: "add" });
    else if (roll < 0.2) actions.push({ kind: "label", block: pick(live), text: `L${step}` });
    else if (roll < 0.32)
      actions.push({ kind: "setting", block: pick(live), capacity: 1 + Math.floor(next() * 5) });
    else if (roll < 0.47) actions.push({ kind: "rename", block: pick(live), to: `n${names++}` });
    else if (roll < 0.62) actions.push({ kind: "nudge", block: pick(live), dx: 8 });
    else if (roll < 0.72) actions.push({ kind: "connect", from: pick(live), to: pick(live) });
    else if (roll < 0.78) {
      const block = pick(live);
      alive.delete(block);
      actions.push({ kind: "delete", block });
    } else if (roll < 0.86) actions.push({ kind: "undo" });
    else if (roll < 0.9) actions.push({ kind: "redo" });
    else if (roll < 0.94) actions.push({ kind: "accept", pick: Math.floor(next() * 4) });
    else actions.push({ kind: "reject", pick: Math.floor(next() * 4) });
  }
  return actions;
}

function start(): Model {
  return {
    ...emptyModel(),
    components: BLOCKS.map(
      (key, index): Component => ({
        id: `server_${index + 1}`,
        type: "server",
        params: {},
        ui: { x: index * 240, y: 0, k: key },
      }),
    ),
  };
}

/** The id the drawn model gives a block now (the user names what they see). */
function drawnId(session: CanvasSession, key: string): string | null {
  const found = session.getState().model?.components?.find((item) => item.ui?.k === key);
  return found?.id ?? null;
}

function perform(session: CanvasSession, action: Action): Promise<unknown> {
  const send = (label: string, edits: Parameters<typeof editsWrite>[1]) =>
    session.write(editsWrite(label, edits));
  if (action.kind === "accept" || action.kind === "reject") {
    const marks = session.marks();
    const mark = marks[action.pick % Math.max(marks.length, 1)];
    if (mark === undefined) return Promise.resolve(session.canWrite() ? "none" : null);
    if (action.kind === "reject") return session.reject(mark.key);
    return Promise.resolve(session.accept(mark.key) ? "accepted" : null);
  }
  if (action.kind === "undo") return session.undo();
  if (action.kind === "redo") return session.redo();
  if (action.kind === "add") {
    return session.write((model) => {
      const id = nextId(model, "queue");
      return {
        kind: "edits",
        label: `add ${id}`,
        edits: [{ edit: "add_component", id, type: "queue", params: {}, ui: { x: 0, y: 200 } }],
      };
    });
  }
  if (action.kind === "connect") {
    const from = drawnId(session, action.from);
    const to = drawnId(session, action.to);
    if (from === null || to === null) return Promise.resolve(null);
    return send(`connect`, [{ edit: "connect", from: `${from}.out`, to: `${to}.in` }]);
  }
  const id = drawnId(session, action.block);
  if (id === null) return Promise.resolve(null);
  switch (action.kind) {
    case "label":
      return send(`label ${id}`, [{ edit: "set_label", id, label: action.text }]);
    case "setting":
      return send(`set ${id}`, settingPlan(id, ["capacity"], action.capacity));
    case "rename":
      return send(`rename ${id}`, [{ edit: "rename_component", id, new_id: action.to }]);
    case "nudge": {
      const all = session.getState().model?.components ?? [];
      const index = all.findIndex((item) => item.id === id);
      const from = positionOf(all[index] as Component, index);
      return session.move(new Map([[id, { x: from.x + action.dx, y: from.y }]]), true);
    }
    case "delete":
      return send(`delete ${id}`, [{ edit: "remove_component", id } satisfies Edit]);
  }
}

async function idle(session: CanvasSession): Promise<void> {
  for (let tries = 0; tries < 500 && session.getState().busy; tries += 1) {
    await new Promise((resolve) => setTimeout(resolve, 2));
  }
  expect(session.getState().busy).toBe(false);
}

async function open(): Promise<{
  fake: FakeService;
  service: ModelService;
  session: CanvasSession;
}> {
  const fake = new FakeService();
  const service = new ModelService(fake, { model: start(), revision: 1 });
  const session = new CanvasSession(fake.client(), PID, { undoLimit: 100, now: () => 0 });
  session.start();
  while (session.getState().status !== "ready") await new Promise((r) => setTimeout(r, 1));
  // Another client's write: a changed block, a new one, a removed one and a renamed one.
  service.outsideWrite((model) => {
    const [first, second, third] = model.components ?? [];
    if (first) first.params.capacity = 3;
    if (third) third.id = "outside_renamed";
    model.components = (model.components ?? []).filter((item) => item !== second);
    model.components.push({ id: "outside_1", type: "queue", params: {}, ui: { x: 0, y: 400 } });
    model.meta = { name: "Changed outside" };
  });
  fake.sockets[0]?.emit({ type: "model", revision: service.revision, client: "script" });
  while (session.marks().length === 0) await new Promise((r) => setTimeout(r, 1));
  await idle(session);
  return { fake, service, session };
}

/** Plays the script against a slow service; gives the accepted actions and the model. */
async function slow(
  actions: Action[],
  seed: number,
): Promise<{ accepted: Action[]; model: Model; marks: unknown[] }> {
  const { fake, service, session } = await open();
  const next = random(seed * 7919);
  const release = fake.holdWrites();
  const accepted: Action[] = [];
  for (const action of actions) {
    // Sometimes the answer to the write in flight comes before the next action.
    if (fake.held > 0 && next() < 0.4) {
      await fake.releaseOne();
      await idle(session);
    }
    if (session.getState().busy) {
      expect(session.canWrite()).toBe(false);
      expect(await perform(session, action)).toBeNull();
      continue;
    }
    const answer = perform(session, action);
    await new Promise((r) => setTimeout(r, 0));
    accepted.push(action);
    void answer;
  }
  release();
  await idle(session);
  const marks = session.marks().map((item) => item.key);
  session.stop();
  return { accepted, model: service.model, marks };
}

async function oneByOne(actions: Action[]): Promise<{ model: Model; marks: unknown[] }> {
  const { service, session } = await open();
  for (const action of actions) await perform(session, action);
  await idle(session);
  const marks = session.marks().map((item) => item.key);
  session.stop();
  return { model: service.model, marks };
}

describe("against a slow service, actions asked while a write awaits its answer are refused", () => {
  for (const seed of [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]) {
    it(`seed ${seed}: the model equals the accepted actions made one at a time`, async () => {
      const { accepted, model, marks } = await slow(script(seed, 30), seed);
      expect(accepted.length).toBeGreaterThan(0);
      expect(accepted.length).toBeLessThan(30);
      expect({ model, marks }).toEqual(await oneByOne(accepted));
    });
  }

  it("the scripts exercise every kind of action", () => {
    const kinds = new Set(
      [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].flatMap((seed) =>
        script(seed, 30).map((a) => a.kind),
      ),
    );
    expect([...kinds].sort()).toEqual(
      [
        "accept",
        "add",
        "connect",
        "delete",
        "label",
        "nudge",
        "redo",
        "reject",
        "rename",
        "setting",
        "undo",
      ].sort(),
    );
  });
});
