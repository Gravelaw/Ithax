/**
 * The queued-write mechanism as a whole (review of PR #45). Scripted runs of user actions
 * (edit a setting, label, rename, move, connect, delete, add, undo, redo), each built as
 * the Canvas builds it and naming blocks by the ids drawn when it is asked, are played
 * twice: one action after another with every answer awaited, and against a slow service
 * whose writes are held and let through in an order the seed chooses. The saved models
 * must be equal: no action may be lost, applied to the wrong block, or built from a model
 * that changed before it was sent.
 */
import { describe, expect, it } from "vitest";
import type { Component, Edit, Model } from "../api/types";
import { emptyModel, ModelService, PID } from "../test/fakeModel";
import { FakeService } from "../test/fakes";
import { nextId } from "./model";
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
  | { kind: "redo" };

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
    } else if (roll < 0.9) actions.push({ kind: "undo" });
    else actions.push({ kind: "redo" });
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
    case "nudge":
      return session.nudge([id], action.dx, 0);
    case "delete":
      return send(`delete ${id}`, [{ edit: "remove_component", id } satisfies Edit]);
  }
}

async function idle(session: CanvasSession): Promise<void> {
  for (let tries = 0; tries < 500 && session.getState().saving; tries += 1) {
    await new Promise((resolve) => setTimeout(resolve, 2));
  }
  expect(session.getState().saving).toBe(false);
}

async function play(actions: Action[], seed: number | null): Promise<Model> {
  const fake = new FakeService();
  const service = new ModelService(fake, { model: start(), revision: 1 });
  const session = new CanvasSession(fake.client(), PID, { undoLimit: 100, now: () => 0 });
  session.start();
  while (session.getState().status !== "ready") await new Promise((r) => setTimeout(r, 1));
  if (seed === null) {
    for (const action of actions) await perform(session, action);
  } else {
    const next = random(seed * 7919);
    const open = fake.holdWrites();
    const pending: Promise<unknown>[] = [];
    for (const action of actions) {
      // Before each action, let through as many held writes as the seed says (often none).
      const release = Math.floor(next() * 3);
      for (let count = 0; count < release && fake.held > 0; count += 1) {
        await fake.releaseOne();
        await new Promise((r) => setTimeout(r, 1));
      }
      pending.push(perform(session, action));
      await new Promise((r) => setTimeout(r, 0));
    }
    open();
    await Promise.all(pending);
  }
  await idle(session);
  session.stop();
  return service.model;
}

describe("actions queued behind a slow service end as if made one at a time", () => {
  for (const seed of [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]) {
    it(`seed ${seed}`, async () => {
      const actions = script(seed, 30);
      const oneByOne = await play(actions, null);
      const queued = await play(actions, seed);
      expect(queued).toEqual(oneByOne);
    });
  }

  it("the scripts exercise every kind of action", () => {
    const kinds = new Set(
      [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].flatMap((seed) =>
        script(seed, 30).map((a) => a.kind),
      ),
    );
    expect([...kinds].sort()).toEqual(
      ["add", "connect", "delete", "label", "nudge", "redo", "rename", "setting", "undo"].sort(),
    );
  });
});
