/**
 * Writes the interface makes for the user without a form to show their answer (the place
 * reached in a lesson, the time a project was opened): one that is refused or not answered
 * is never taken as saved (review of pull request 201). It is kept by what it saves and
 * shown in the top bar with "Try again", which sends it again; a later write of the same
 * thing that succeeds clears it.
 */
import { useCallback, useState } from "react";
import type { ApiResult } from "../api/client";
import { ServiceProblem } from "../components/ServiceProblem";

export interface Unsaved {
  /** What was not saved, in words. */
  what: string;
  result: ApiResult<unknown>;
  retry: () => void;
}

/** Notes a write's answer under `key`: an answer that is not `ok` is kept with its retry. */
export type KeepWrite = (
  key: string,
  what: string,
  result: ApiResult<unknown>,
  retry: () => void,
) => void;

export function useUnsaved(): [Record<string, Unsaved>, KeepWrite] {
  const [unsaved, setUnsaved] = useState<Record<string, Unsaved>>({});
  const keep = useCallback<KeepWrite>((key, what, result, retry) => {
    setUnsaved((current) => {
      const { [key]: _done, ...others } = current;
      return result.kind === "ok" ? others : { ...others, [key]: { what, result, retry } };
    });
  }, []);
  return [unsaved, keep];
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
