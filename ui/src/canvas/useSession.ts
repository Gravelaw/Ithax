/**
 * The React side of `CanvasSession`: one session per open project, its state read with
 * `useSyncExternalStore`, and its undo depth from Settings (`undo_steps`; `null` takes the
 * tier's recommendation: 200 on low, 500 on mid, 1,000 on high; spec 3 `GET /v1/settings`).
 */
import { useEffect, useState, useSyncExternalStore } from "react";
import type { ApiClient } from "../api/client";
import type { Settings } from "../api/types";
import { CanvasSession, type SessionState } from "./session";

export const RECOMMENDED_UNDO_STEPS = { low: 200, mid: 500, high: 1000 } as const;

export function undoSteps(settings: Settings): number {
  return settings.interface.undo_steps ?? RECOMMENDED_UNDO_STEPS[settings.tier];
}

const NONE: SessionState = {
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

const nothing = () => () => undefined;
const none = () => NONE;

export function useSession(
  client: ApiClient,
  pid: string,
  undoLimit: number,
): [SessionState, CanvasSession | null] {
  const [session, setSession] = useState<CanvasSession | null>(null);
  // The limit when the session starts; later changes go through setUndoLimit.
  const [startLimit] = useState(undoLimit);

  useEffect(() => {
    const opened = new CanvasSession(client, pid, { undoLimit: startLimit });
    setSession(opened);
    opened.start();
    return () => opened.stop();
  }, [client, pid, startLimit]);

  useEffect(() => {
    session?.setUndoLimit(undoLimit);
  }, [session, undoLimit]);

  const state = useSyncExternalStore(
    session?.subscribe ?? nothing,
    session?.getState ?? none,
    session?.getState ?? none,
  );
  return [state, session];
}
