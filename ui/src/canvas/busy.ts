/**
 * Whether the canvas is waiting for a write's answer (`CanvasSession` `busy`). While it is,
 * every control that changes the model is unavailable but keeps the focus: `aria-disabled`
 * rather than `disabled`, and the session takes no change; a text box keeps its draft and
 * commits it once the answer has come.
 */
import { createContext, useContext } from "react";

export const BusyContext = createContext(false);

export function useBusy(): boolean {
  return useContext(BusyContext);
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
