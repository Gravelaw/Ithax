/**
 * App's one queue of project actions (`projectActions.ts`): `run` and whether an action is
 * queued or running.
 */
import { useCallback, useMemo, useRef, useState } from "react";
import type { ApiClient } from "../api/client";
import { oneAtATime } from "../components/oneAtATime";
import { type ProjectApi, projectApi, type RunProjects } from "./projectActions";

export function useProjectQueue(client: ApiClient): { run: RunProjects; busy: boolean } {
  const api = useMemo<ProjectApi>(() => projectApi(client), [client]);
  const queue = useRef(oneAtATime());
  const [waiting, setWaiting] = useState(0);
  const run = useCallback<RunProjects>(
    async (action) => {
      setWaiting((count) => count + 1);
      try {
        return await queue.current(() => action(api));
      } finally {
        setWaiting((count) => count - 1);
      }
    },
    [api],
  );
  return { run, busy: waiting > 0 };
}
