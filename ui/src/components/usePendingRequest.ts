/**
 * One request at a time from a form, such as a dialog's Create or Open (review of PR #44).
 *
 * `run(request, done)` starts `request` unless one is already pending; a second press is
 * ignored even before React re-renders, since the guard is a ref (each `POST /v1/projects`
 * makes a new project). `busy` is true while it is pending, for disabling the submit and
 * the dismiss controls. `done` receives the result only while the component is still
 * mounted, so a dialog that is gone never navigates or sets state.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export interface PendingRequest {
  busy: boolean;
  run<T>(request: () => Promise<T>, done: (result: T) => void): Promise<void>;
}

export function usePendingRequest(): PendingRequest {
  const pending = useRef(false);
  const mounted = useRef(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(
    async <T>(request: () => Promise<T>, done: (result: T) => void): Promise<void> => {
      if (pending.current) return;
      pending.current = true;
      setBusy(true);
      try {
        const result = await request();
        if (mounted.current) done(result);
      } finally {
        pending.current = false;
        if (mounted.current) setBusy(false);
      }
    },
    [],
  );

  return { busy, run };
}
