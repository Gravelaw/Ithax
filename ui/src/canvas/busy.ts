/**
 * Whether the canvas is waiting for a write's answer (`CanvasSession` `busy`), and the
 * revision of the model shown. While it is busy, every control that changes the model is
 * unavailable but keeps the focus (`aria-disabled` rather than `disabled`), and the session
 * takes no change. A text box's draft never outlives a change of the model shown: when the
 * revision changes it shows the saved value again (review of PR #45).
 */
import { createContext, useContext } from "react";

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
