/**
 * Writes the interface makes for the user without a form to show their answer (the place
 * reached in a lesson, the time a project was opened): one that is refused or not answered
 * is never taken as saved (review of pull request 201). It is kept by what it saves and
 * shown in the top bar with "Try again", which sends it again; a later write of the same
 * thing that succeeds clears it. A retry sends the value wanted when it runs, never the
 * one captured when the write failed, so it cannot undo a newer write queued meanwhile.
 */
import { useCallback, useState } from "react";
import type { ApiResult } from "../api/client";
import { ServiceProblem } from "../components/ServiceProblem";

export interface Unsaved {
  /** The project the write was for. */
  project: string;
  /** What was not saved, in words. */
  what: string;
  result: ApiResult<unknown>;
  retry: () => void;
}

/**
 * Notes the answer of the write of `kind` ("step", "opened") for `project`: an answer that
 * is not `ok` is kept with its retry, an `ok` one clears it.
 */
export type KeepWrite = (
  project: string,
  kind: string,
  what: string,
  result: ApiResult<unknown>,
  retry: () => void,
) => void;

/** Drops every write kept for `project`, as when it is removed (review of pull request 201). */
export type ForgetProject = (project: string) => void;

export function useUnsaved(): [Record<string, Unsaved>, KeepWrite, ForgetProject] {
  const [unsaved, setUnsaved] = useState<Record<string, Unsaved>>({});
  const keep = useCallback<KeepWrite>((project, kind, what, result, retry) => {
    const key = `${kind} ${project}`;
    setUnsaved((current) => {
      const { [key]: _done, ...others } = current;
      return result.kind === "ok" ? others : { ...others, [key]: { project, what, result, retry } };
    });
  }, []);
  const forget = useCallback<ForgetProject>((project) => {
    setUnsaved((current) =>
      Object.fromEntries(Object.entries(current).filter(([, item]) => item.project !== project)),
    );
  }, []);
  return [unsaved, keep, forget];
}

export function UnsavedWrites({ unsaved }: { unsaved: Record<string, Unsaved> }) {
  return (
    <>
      {Object.entries(unsaved).map(([key, item]) => (
        <div key={key} className="unsaved">
          <p role="alert">{item.what}</p>
          <ServiceProblem result={item.result} />
          <button type="button" className="secondary" onClick={item.retry}>
            Try again
          </button>
        </div>
      ))}
    </>
  );
}
