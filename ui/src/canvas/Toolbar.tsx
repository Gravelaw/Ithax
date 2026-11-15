/**
 * What the Canvas screen puts in the top bar for any model (spec 3 "Canvas behaviour",
 * Save and Run; owner review choice 9): the save state, and why Run waits.
 */
import { CheckCircleIcon, WarningCircleIcon } from "@phosphor-icons/react";
import { issueCounts } from "./model";
import type { SessionState } from "./session";

export const NOTICE_MS = 8000;
/** Said when a change is tried while a write awaits its answer: it is not made. */
export const WAIT = "Not saved: the canvas was saving. Make the change again.";

/** Said while `POST .../runs` awaits its answer (AKS-138). */
export const STARTING = "Starting the run…";

/** Said when the model has no blocks (W204; #95, owner decision #188, option A). */
export const EMPTY_MODEL = "Add a block to run the model.";

/**
 * Why Run is not available, and which pointer it shows (owner review choice 9). An empty
 * process model is told by the service's W204 in the last validation, so the rule is the
 * service's (#95; owner decision #188, option A).
 */
export function runBlocked(
  state: SessionState,
): { reason: string; pointer: "errors" | "busy" | "empty" } | null {
  if (state.failing) {
    return { reason: "Not saved: the service is not answering. Retrying.", pointer: "busy" };
  }
  if (state.starting) return { reason: STARTING, pointer: "busy" };
  if (state.saving) return { reason: "Saving…", pointer: "busy" };
  if (state.checking) return { reason: "Checking…", pointer: "busy" };
  const { errors } = issueCounts(state.issues);
  if (errors > 0) {
    return {
      reason: `${errors} error${errors === 1 ? "" : "s"}. Fix ${errors === 1 ? "it" : "them"} to run.`,
      pointer: "errors",
    };
  }
  if (state.issues.some((issue) => issue.code === "W204")) {
    return { reason: EMPTY_MODEL, pointer: "empty" };
  }
  return null;
}

export function SaveState({ state }: { state: SessionState }) {
  if (state.failing) {
    return (
      <span className="save-state save-failing" role="status">
        <WarningCircleIcon aria-hidden="true" size={16} weight="fill" />
        Not saved: the service is not answering. Retrying.
      </span>
    );
  }
  if (state.saving) {
    return (
      <span className="save-state" role="status">
        Saving…
      </span>
    );
  }
  return (
    <span className="save-state save-saved" role="status" title={`Revision ${state.revision}`}>
      <CheckCircleIcon aria-hidden="true" size={16} weight="fill" />
      Saved
    </span>
  );
}
