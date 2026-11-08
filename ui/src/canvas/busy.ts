/**
 * Whether the canvas is waiting for a write's answer (`CanvasSession` `busy`), and the
 * revision of the model shown. While it is busy, every control that changes the model is
 * unavailable but keeps the focus (`aria-disabled` rather than `disabled`), and the session
 * takes no change. A text box's draft never outlives a change of the model shown: when the
 * revision changes it shows the saved value again (review of PR #45).
 */
import { createContext, useCallback, useContext, useState } from "react";

export const BusyContext = createContext(false);
export const RevisionContext = createContext(0);

export function useBusy(): boolean {
  return useContext(BusyContext);
}

export function useRevision(): number {
  return useContext(RevisionContext);
}

/** `disabled` while read-only; `aria-disabled` while busy, so the focus stays. */
export function lock(
  readOnly: boolean,
  busy: boolean,
): {
  disabled: boolean;
  "aria-disabled"?: true;
} {
  return busy ? { disabled: readOnly, "aria-disabled": true } : { disabled: readOnly };
}

/**
 * A draft that never outlives a change to the model shown: it is `initial` again whenever
 * the revision changes (an answer, a reload, another client's write).
 */
export function useDraft<T>(initial: T): [T, (value: T) => void] {
  const revision = useRevision();
  const [draft, setDraft] = useState({ revision, value: initial });
  const value = draft.revision === revision ? draft.value : initial;
  const set = useCallback((next: T) => setDraft({ revision, value: next }), [revision]);
  return [value, set];
}
