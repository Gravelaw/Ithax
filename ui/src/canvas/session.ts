/**
 * The open model of one project, as the Canvas edits it (spec 3 "Canvas behaviour";
 * `docs/design/canvas-interactions.md`).
 *
 * - **Single source.** The model shown is the last one the service returned; every change
 *   is a write to the service (`POST .../model/edits`, or `PUT .../model` for undo, redo and
 *   clearing), and the response is the truth.
 * - **One write at a time, and nothing else meanwhile.** While a write, or a reload, awaits
 *   its answer the session is `busy` and refuses every other change (`null`), so every
 *   action is computed from the model actually shown, which holds every accepted write.
 *   On a local service the wait is a few milliseconds (review of PR #45: actions computed
 *   against a model that queued writes would still change gave seven findings in three
 *   rounds; the queue was removed). A write that gets no usable answer is retried every 2
 *   seconds, and the canvas is read-only meanwhile.
 * - **Undo and redo** keep the whole model before and after each write; undo writes the
 *   earlier model with `PUT .../model?base_revision=N`, redo the later one. The number of
 *   steps kept is set by the caller (Settings, `undo_steps`). A move of the same blocks
 *   less than half a second after the previous move joins that move's step, so a burst of
 *   arrow presses is one step.
 * - **Validation** runs half a second after the last write; a result for an older write
 *   is dropped.
 * - **Other clients.** A `model` event whose revision is newer than the canvas's own, once
 *   its write has answered, reloads the model and clears undo and redo (the review of an
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

/** Builds the write from the model shown; `null` sends nothing. */
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
  /** A write is waiting for its answer. */
  saving: boolean;
  /** A write or a reload is waiting for its answer: no other change is taken. */
  busy: boolean;
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
  /**
   * The renames the last accepted write made, old id to new, given with its model so the
   * selection and the side panel follow a renamed block in the same drawing.
   */
  renamed: Readonly<Record<string, string>>;
}

export interface SessionOptions {
  undoLimit: number;
  setTimer?: (callback: () => void, ms: number) => unknown;
  clearTimer?: (handle: unknown) => void;
  now?: () => number;
}

export const INITIAL_STATE: SessionState = {
  status: "loading",
  loadProblem: null,
  model: null,
  revision: 0,
  issues: [],
  checking: true,
  saving: false,
  busy: false,
  failing: false,
  refusal: null,
  undoLabel: null,
  redoLabel: null,
  reloads: 0,
  eventsClosed: null,
  renamed: {},
};

/** `merge` is a move that joins the previous move's undo step. */
type History = "do" | "merge" | "undo" | "redo";

export class CanvasSession {
  private state: SessionState = INITIAL_STATE;
  private readonly listeners = new Set<() => void>();
  private undoStack: Step[] = [];
  private redoStack: Step[] = [];
  /** The write or reload in flight, if any. */
  private current: Promise<unknown> = Promise.resolve();
  private validation = 0;
  private validateTimer: unknown = null;
  private socket: EventSocket | null = null;
  private stopped = false;
  /** The last move: which blocks, and when it was asked for. */
  private lastMove: { moved: string; at: number } | null = null;
  /** The newest revision another client announced while the session was busy. */
  private announced = 0;
  private undoLimit: number;
  private readonly setTimer: (callback: () => void, ms: number) => unknown;
  private readonly clearTimer: (handle: unknown) => void;
  private readonly now: () => number;

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

  /** Updates the state; after `stop`, the write in flight keeps it current, unannounced. */
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
    this.current = (async () => {
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
    })();
  }

  /** Stops: the write in flight is still answered once (no retries), then the socket closes. */
  stop(): void {
    if (this.stopped) return;
    this.stopped = true;
    if (this.validateTimer !== null) this.clearTimer(this.validateTimer);
    void this.current.finally(() => this.socket?.close());
  }

  setUndoLimit(limit: number): void {
    this.undoLimit = limit;
    this.trim();
    this.set({});
  }

  /** Whether a change would be taken now. */
  canWrite(): boolean {
    return (
      this.state.status === "ready" && !this.state.busy && !this.state.failing && !this.stopped
    );
  }

  /** Sends one user action; `null` when it is not taken (busy, read-only, not loaded). */
  write(plan: Plan): Promise<ApiResult<ModelWriteBody> | null> {
    if (!this.canWrite()) return Promise.resolve(null);
    this.lastMove = null;
    return this.send("do", plan);
  }

  /**
   * Moves blocks to `positions`. With `burst` (arrow keys), a move of the same blocks less
   * than `MOVE_BURST_MS` after the previous one joins that move's undo step.
   */
  move(
    positions: ReadonlyMap<string, Point>,
    burst = false,
  ): Promise<ApiResult<ModelWriteBody> | null> {
    if (!this.canWrite() || positions.size === 0) return Promise.resolve(null);
    const ids = [...positions.keys()];
    const moved = [...ids].sort().join(" ");
    const now = this.now();
    const joins = burst && this.lastMove?.moved === moved && now - this.lastMove.at < MOVE_BURST_MS;
    this.lastMove = burst ? { moved, at: now } : null;
    const label = ids.length === 1 ? `move ${ids[0]}` : `move ${ids.length} blocks`;
    return this.send(
      joins ? "merge" : "do",
      (model) => {
        const edits = movesIn(model, positions);
        return edits.length === 0 ? null : { kind: "edits", label, edits };
      },
      moved,
    );
  }

  undo(): Promise<ApiResult<ModelWriteBody> | null> {
    if (!this.canWrite()) return Promise.resolve(null);
    this.lastMove = null;
    return this.send("undo", () => {
      const step = this.undoStack.at(-1);
      return step ? { kind: "model", label: step.label, model: step.before } : null;
    });
  }

  redo(): Promise<ApiResult<ModelWriteBody> | null> {
    if (!this.canWrite()) return Promise.resolve(null);
    this.lastMove = null;
    return this.send("redo", () => {
      const step = this.redoStack.at(-1);
      return step ? { kind: "model", label: step.label, model: step.after } : null;
    });
  }

  private send(
    history: History,
    plan: Plan,
    moved?: string,
  ): Promise<ApiResult<ModelWriteBody> | null> {
    const before = this.state.model;
    const write = before === null ? null : plan(before);
    if (before === null || write === null) return Promise.resolve(null);
    this.invalidateValidation();
    this.set({ saving: true, busy: true });
    const job = this.answer(history, before, write, moved);
    this.current = job.catch(() => undefined);
    return job;
  }

  private async answer(
    history: History,
    before: Model,
    write: Write,
    moved?: string,
  ): Promise<ApiResult<ModelWriteBody> | null> {
    const base = this.state.revision;
    const request = () =>
      write.kind === "edits"
        ? this.client.editModel(this.pid, write.edits, base)
        : this.client.putModel(this.pid, write.model, base);
    let result = await request();
    while (result.kind === "failed" && !this.stopped) {
      this.set({ failing: true });
      await this.sleep(RETRY_MS);
      if (this.stopped) break;
      result = await request();
    }
    const done = { saving: false, busy: false, failing: false };
    if (result.kind === "ok") {
      this.record(history, write.label, before, result.data.model, moved);
      const renamed: Record<string, string> = {};
      if (write.kind === "edits") {
        for (const edit of write.edits) {
          if (edit.edit === "rename_component") renamed[edit.id] = edit.new_id;
        }
      }
      // The model and the end of the wait in one change, so the screen never draws the
      // new model while still refusing changes, nor the reverse.
      this.set({
        ...done,
        refusal: null,
        renamed,
        model: result.data.model,
        revision: result.data.revision,
      });
    } else if (result.kind === "refused" && result.error.code === "E181") {
      this.set({ failing: false, refusal: result });
      await this.reload();
      this.set(done);
    } else {
      this.set({ ...done, refusal: result });
    }
    this.afterBusy();
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

  /**
   * A `model` event: one for a revision newer than the canvas's reloads the model; one
   * that arrives while a write is waiting is judged once it has answered, since it may be
   * that write's own.
   */
  private onEvent(event: ProjectEvent): void {
    if (event.type !== "model" || this.stopped) return;
    this.announced = Math.max(this.announced, event.revision);
    if (!this.state.busy) this.afterBusy();
  }

  private afterBusy(): void {
    if (this.stopped || this.state.status !== "ready") return;
    if (this.announced > this.state.revision) {
      this.set({ busy: true });
      this.current = this.reload().then(() => {
        this.set({ busy: false, reloads: this.state.reloads + 1 });
        this.afterBusy();
      });
    }
  }

  /** Reads the model again and clears undo and redo (another client changed it). */
  private async reload(): Promise<void> {
    const before = this.announced;
    let loaded = await this.client.getModel(this.pid);
    while (loaded.kind === "failed" && !this.stopped) {
      this.set({ failing: true });
      await this.sleep(RETRY_MS);
      loaded = await this.client.getModel(this.pid);
    }
    this.undoStack = [];
    this.redoStack = [];
    this.lastMove = null;
    if (loaded.kind === "ok") {
      // A revision announced while the reload was under way, newer than the one read, is
      // read next; otherwise the service's revision is the truth (an announcement it does
      // not bear out is not chased again).
      this.announced =
        this.announced > before
          ? Math.max(this.announced, loaded.data.revision)
          : loaded.data.revision;
      this.set({
        failing: false,
        renamed: {},
        model: loaded.data.model,
        revision: loaded.data.revision,
      });
    } else {
      this.announced = this.state.revision;
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
