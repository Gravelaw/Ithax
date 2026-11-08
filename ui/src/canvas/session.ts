/**
 * The open model of one project, as the Canvas edits it (spec 3 "Canvas behaviour";
 * `docs/design/canvas-interactions.md`).
 *
 * - **Single source.** The model shown is the last one the service returned; every change
 *   is a write to the service (`POST .../model/edits`, or `PUT .../model` for undo and redo),
 *   and the response is the truth.
 * - **One write at a time,** in order, each with `base_revision`. A write that gets no
 *   usable answer is retried every 2 seconds, and the canvas is read-only meanwhile.
 * - **Undo and redo** keep the whole model before and after each write; undo writes the
 *   earlier model with `PUT .../model?base_revision=N`, redo the later one. The number of
 *   steps kept is set by the caller (Settings, `undo_steps`).
 * - **Validation** runs half a second after the last write; a result for an older write
 *   is dropped.
 * - **Moves** (arrow keys, a drag's end) are writes like any other, sent at once and so
 *   retried like any other. A move of the same blocks within half a second of the previous
 *   one joins that move's undo step, so a burst of arrow presses is one undo step; until a
 *   move's answer arrives, `predicted` holds where it puts each block, so the drawing never
 *   jumps back while moves are queued (review of PR #45).
 * - **Other clients.** A `model` event whose revision is newer than the canvas's own, once
 *   its writes have answered, reloads the model and clears undo and redo (the review of an
 *   outside change is AKS-137). A 409 with E181 does the same.
 */
import type { ApiClient, ApiResult, EventSocket } from "../api/client";
import type { Edit, Issue, Model, ModelWriteBody, ProjectEvent } from "../api/types";
import { movesIn, type Point } from "./model";

export const RETRY_MS = 2000;
export const VALIDATE_MS = 500;
/** Moves of the same blocks less than this apart are one undo step (a burst of arrows). */
export const MOVE_BURST_MS = 500;

/** One undo step: the model before and after one write. */
export interface Step {
  label: string;
  before: Model;
  after: Model;
  /** For a move: the blocks it moved, so a following move of them can join it. */
  moved?: string;
}

/** What one user action writes: edits, or a whole model. */
export type Write =
  | { kind: "edits"; label: string; edits: Edit[] }
  | { kind: "model"; label: string; model: Model };

/** Builds the write from the model as it is when the write is sent; `null` sends nothing. */
export type Plan = (model: Model) => Write | null;

export interface SessionState {
  status: "loading" | "ready" | "unavailable";
  /** Why the model could not be loaded, as the service said it. */
  loadProblem: ApiResult<unknown> | null;
  model: Model | null;
  revision: number;
  /** The issues of the last validation of the current revision. */
  issues: Issue[];
  /** A validation is waiting for its half second or for its answer. */
  checking: boolean;
  /** A write is waiting to be sent or for its answer. */
  saving: boolean;
  /** A write got no usable answer: the canvas is read-only and the write is retried. */
  failing: boolean;
  /** The service refused the last write (400 E180, 409 E181, ...); cleared by the next. */
  refusal: ApiResult<unknown> | null;
  undoLabel: string | null;
  redoLabel: string | null;
  /** How many times another client's change reloaded the model. */
  reloads: number;
  /** The events socket closed with this reason (lost contact). */
  eventsClosed: string | null;
  /** Where queued moves put blocks, by id, until each move's answer arrives. */
  predicted: Readonly<Record<string, Point>>;
}

export interface SessionOptions {
  undoLimit: number;
  setTimer?: (callback: () => void, ms: number) => unknown;
  clearTimer?: (handle: unknown) => void;
  now?: () => number;
}

const INITIAL: SessionState = {
  status: "loading",
  loadProblem: null,
  model: null,
  revision: 0,
  issues: [],
  checking: true,
  saving: false,
  failing: false,
  refusal: null,
  undoLabel: null,
  redoLabel: null,
  reloads: 0,
  eventsClosed: null,
  predicted: {},
};

/** `merge` is a move that joins the previous move's undo step. */
type History = "do" | "merge" | "undo" | "redo";

export class CanvasSession {
  private state: SessionState = INITIAL;
  private readonly listeners = new Set<() => void>();
  private undoStack: Step[] = [];
  private redoStack: Step[] = [];
  private chain: Promise<unknown> = Promise.resolve();
  private writes = 0;
  private validation = 0;
  private validateTimer: unknown = null;
  private socket: EventSocket | null = null;
  private stopped = false;
  /** Predicted positions, each with the move that set it. */
  private readonly predicted = new Map<string, { at: Point; move: number }>();
  private moves = 0;
  /** The last move action: which blocks, and when it was asked for. */
  private lastMove: { moved: string; at: number } | null = null;
  private readonly now: () => number;
  private undoLimit: number;
  private readonly setTimer: (callback: () => void, ms: number) => unknown;
  private readonly clearTimer: (handle: unknown) => void;

  constructor(
    private readonly client: ApiClient,
    private readonly pid: string,
    options: SessionOptions,
  ) {
    this.undoLimit = options.undoLimit;
    this.setTimer = options.setTimer ?? ((callback, ms) => setTimeout(callback, ms));
    this.clearTimer =
      options.clearTimer ?? ((handle) => clearTimeout(handle as ReturnType<typeof setTimeout>));
    this.now = options.now ?? (() => Date.now());
  }

  readonly subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  readonly getState = (): SessionState => this.state;

  /** Updates the state; after `stop`, writes still queued keep it current, unannounced. */
  private set(change: Partial<SessionState>): void {
    this.state = {
      ...this.state,
      ...change,
      undoLabel: this.undoStack.at(-1)?.label ?? null,
      redoLabel: this.redoStack.at(-1)?.label ?? null,
    };
    if (this.stopped) return;
    for (const listener of this.listeners) listener();
  }

  /** Loads the model, opens the project's events and validates. */
  start(): void {
    this.chain = this.chain.then(async () => {
      const loaded = await this.client.getModel(this.pid);
      if (this.stopped) return;
      if (loaded.kind !== "ok") {
        this.set({ status: "unavailable", loadProblem: loaded, checking: false });
        return;
      }
      this.set({ status: "ready", model: loaded.data.model, revision: loaded.data.revision });
      this.socket = this.client.projectEvents(this.pid, {
        onEvent: (event) => this.onEvent(event),
        onClose: (code, reason) => {
          if (code !== 1000) this.set({ eventsClosed: reason });
        },
      });
      this.scheduleValidate(0);
    });
  }

  /**
   * Moves blocks to `positions`, sent at once as one write of `set_ui` (built when it is
   * sent). With `burst`, a move of the same blocks less than `MOVE_BURST_MS` after the
   * previous one joins that move's undo step.
   */
  move(
    positions: ReadonlyMap<string, Point>,
    burst = true,
  ): Promise<ApiResult<ModelWriteBody> | null> {
    if (this.state.status !== "ready" || this.state.failing || this.stopped) {
      return Promise.resolve(null);
    }
    const ids = [...positions.keys()];
    const moved = [...ids].sort().join(" ");
    const now = this.now();
    const joins = burst && this.lastMove?.moved === moved && now - this.lastMove.at < MOVE_BURST_MS;
    this.lastMove = burst ? { moved, at: now } : null;
    const move = ++this.moves;
    for (const [id, at] of positions) this.predicted.set(id, { at, move });
    this.set({ predicted: this.predictions() });
    const label = ids.length === 1 ? `move ${ids[0]}` : `move ${ids.length} blocks`;
    const plan: Plan = (model) => {
      const edits = movesIn(model, positions);
      return edits.length === 0 ? null : { kind: "edits", label, edits };
    };
    return this.queue(joins ? "merge" : "do", plan, moved).finally(() => {
      for (const id of ids) {
        if (this.predicted.get(id)?.move === move) this.predicted.delete(id);
      }
      this.set({ predicted: this.predictions() });
    });
  }

  private predictions(): Record<string, Point> {
    return Object.fromEntries([...this.predicted].map(([id, entry]) => [id, entry.at]));
  }

  /**
   * Stops: writes already queued are still sent once
   * (without retries when they get no answer), then the events socket closes.
   */
  stop(): void {
    if (this.stopped) return;
    this.stopped = true;
    if (this.validateTimer !== null) this.clearTimer(this.validateTimer);
    void this.chain.finally(() => this.socket?.close());
  }

  setUndoLimit(limit: number): void {
    this.undoLimit = limit;
    this.trim();
    this.set({});
  }

  /** Sends one user action. `null` when the canvas is read-only or not loaded. */
  write(plan: Plan): Promise<ApiResult<ModelWriteBody> | null> {
    this.lastMove = null;
    return this.queue("do", plan);
  }

  undo(): Promise<ApiResult<ModelWriteBody> | null> {
    this.lastMove = null;
    return this.queue("undo", () => {
      const step = this.undoStack.at(-1);
      return step ? { kind: "model", label: step.label, model: step.before } : null;
    });
  }

  redo(): Promise<ApiResult<ModelWriteBody> | null> {
    this.lastMove = null;
    return this.queue("redo", () => {
      const step = this.redoStack.at(-1);
      return step ? { kind: "model", label: step.label, model: step.after } : null;
    });
  }

  private queue(
    history: History,
    plan: Plan,
    moved?: string,
  ): Promise<ApiResult<ModelWriteBody> | null> {
    if (this.state.status !== "ready" || this.state.failing || this.stopped) {
      return Promise.resolve(null);
    }
    this.writes += 1;
    this.invalidateValidation();
    this.set({ saving: true });
    const job = this.chain.then(() => this.send(history, plan, moved));
    this.chain = job.catch(() => undefined);
    return job.finally(() => {
      this.writes -= 1;
      this.set({ saving: this.writes > 0 });
    });
  }

  private async send(
    history: History,
    plan: Plan,
    moved?: string,
  ): Promise<ApiResult<ModelWriteBody> | null> {
    const before = this.state.model;
    if (before === null) return null;
    const base = this.state.revision;
    const write = plan(before);
    if (write === null) {
      this.scheduleValidate();
      return null;
    }
    const request = () =>
      write.kind === "edits"
        ? this.client.editModel(this.pid, write.edits, base)
        : this.client.putModel(this.pid, write.model, base);
    let result = await request();
    while (result.kind === "failed" && !this.stopped) {
      this.set({ failing: true });
      await this.sleep(RETRY_MS);
      if (this.stopped) return result;
      result = await request();
    }
    if (result.kind === "ok") {
      this.record(history, write.label, before, result.data.model, moved);
      this.set({
        failing: false,
        refusal: null,
        model: result.data.model,
        revision: result.data.revision,
      });
    } else if (result.kind === "refused" && result.error.code === "E181") {
      this.set({ failing: false, refusal: result });
      await this.reload();
    } else {
      this.set({ failing: false, refusal: result });
    }
    this.scheduleValidate();
    return result;
  }

  private record(
    history: History,
    label: string,
    before: Model,
    after: Model,
    moved?: string,
  ): void {
    const top = this.undoStack.at(-1);
    if (history === "merge" && top !== undefined && top.moved === moved) {
      // The burst's step keeps the model from before its first move.
      top.after = after;
      this.redoStack = [];
    } else if (history === "do" || history === "merge") {
      const step: Step = { label, before, after };
      if (moved !== undefined) step.moved = moved;
      this.undoStack.push(step);
      this.redoStack = [];
      this.trim();
    } else if (history === "undo") {
      const step = this.undoStack.pop();
      if (step) this.redoStack.push(step);
    } else {
      const step = this.redoStack.pop();
      if (step) this.undoStack.push(step);
    }
  }

  private trim(): void {
    while (this.undoStack.length > this.undoLimit) this.undoStack.shift();
    while (this.redoStack.length > this.undoLimit) this.redoStack.shift();
  }

  private onEvent(event: ProjectEvent): void {
    if (event.type !== "model" || this.stopped) return;
    // Held until the canvas's own writes have answered, so its own revisions are known.
    this.chain = this.chain.then(async () => {
      if (this.state.status === "ready" && event.revision > this.state.revision) {
        await this.reload();
        this.set({ reloads: this.state.reloads + 1 });
      }
    });
  }

  /** Reads the model again and clears undo and redo (another client changed it). */
  private async reload(): Promise<void> {
    let loaded = await this.client.getModel(this.pid);
    while (loaded.kind === "failed" && !this.stopped) {
      this.set({ failing: true });
      await this.sleep(RETRY_MS);
      loaded = await this.client.getModel(this.pid);
    }
    this.undoStack = [];
    this.redoStack = [];
    if (loaded.kind === "ok") {
      this.set({ failing: false, model: loaded.data.model, revision: loaded.data.revision });
    } else {
      this.set({ failing: false, refusal: loaded });
    }
    this.scheduleValidate();
  }

  private invalidateValidation(): void {
    this.validation += 1;
    if (this.validateTimer !== null) this.clearTimer(this.validateTimer);
    this.validateTimer = null;
    this.set({ checking: true });
  }

  private scheduleValidate(delay = VALIDATE_MS): void {
    this.invalidateValidation();
    const ticket = this.validation;
    this.validateTimer = this.setTimer(() => {
      this.validateTimer = null;
      void this.runValidate(ticket);
    }, delay);
  }

  private async runValidate(ticket: number): Promise<void> {
    if (ticket !== this.validation || this.stopped) return;
    const result = await this.client.validate(this.pid);
    if (ticket !== this.validation || this.stopped) return;
    if (result.kind === "ok") {
      if (result.data.revision !== this.state.revision) {
        // Another write landed between; its own validation follows.
        this.scheduleValidate();
        return;
      }
      this.set({ issues: result.data.issues, checking: false });
    } else if (result.kind === "refused") {
      this.set({ issues: result.issues, checking: false });
    } else {
      this.scheduleValidate(RETRY_MS);
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => {
      this.setTimer(resolve, ms);
    });
  }
}
