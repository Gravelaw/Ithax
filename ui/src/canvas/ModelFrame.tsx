/**
 * The frame of a screen other than the Canvas that changes the model (the Data and
 * Experiment screens, AKS-120): the same `CanvasSession` class and the same rules as the
 * Canvas (spec 3 "Canvas behaviour", Save and External edits; the AKS-136 and AKS-137
 * readings).
 *
 * 1. One write at a time: while a write or a reload awaits its answer, every control that
 *    changes the model is unavailable (`BusyContext`), and a change tried anyway is not
 *    made and a notice says so.
 * 2. Every action is a plan the session builds from the model shown.
 * 3. No draft outlives a change to the model shown (`RevisionContext`, `useDraft`).
 * 4. Names the model holds are read through `own.ts`.
 * 5. Nothing is queued or kept to be sent later.
 * 6. Another client's write reloads the model, names the client and lists the changes to
 *    review with Accept and Reject, as the Canvas does.
 *
 * The top bar holds the save state, "N changes to review", Undo and Redo.
 */
import { ArrowUUpLeftIcon, ArrowUUpRightIcon, XIcon } from "@phosphor-icons/react";
import { type ReactNode, useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import type { ApiClient, ApiResult } from "../api/client";
import type { Model, ModelWriteBody, Project, SchemaBody } from "../api/types";
import { LOST_CONTACT, ServiceProblem } from "../components/ServiceProblem";
import { useSettings } from "../settings/SettingsContext";
import { BusyContext, RevisionContext } from "./busy";

export { useDraft } from "./busy";

import { type EditPlan, editsWrite, modelWrite } from "./plans";
import {
  OutsideNotice,
  type ReviewActions,
  ReviewContext,
  ReviewCount,
  ReviewList,
} from "./ReviewParts";
import { type CanvasSession, clientsOf, marksOf, type SessionState } from "./session";
import "./screens.css";
import { NOTICE_MS, SaveState } from "./Toolbar";
import { undoSteps, useSession } from "./useSession";

/** Said when a change is tried while a write awaits its answer: it is not made. */
export const WAIT_MODEL = "Not saved: the model was saving. Make the change again.";

/** What a screen inside the frame uses to change the model. */
export interface ModelWrites {
  /** Whether a change is taken now; when not, the wait notice is shown. */
  free(): boolean;
  /** One batch of edits built from the model shown; `null` when nothing was sent. */
  edit(label: string, edits: EditPlan): Promise<ApiResult<ModelWriteBody> | null>;
  /** A whole model built from the model shown (clearing a field no edit removes). */
  replace(
    label: string,
    build: (model: Model) => Model | null,
  ): Promise<ApiResult<ModelWriteBody> | null>;
  /** A one-line notice that goes after 8 seconds. */
  say(text: string): void;
}

/** `GET /v1/schema`, once per screen. */
export function useSchema(client: ApiClient): ApiResult<SchemaBody> | null {
  const [schema, setSchema] = useState<ApiResult<SchemaBody> | null>(null);
  useEffect(() => {
    let live = true;
    void client.getSchema().then((result) => {
      if (live) setSchema(result);
    });
    return () => {
      live = false;
    };
  }, [client]);
  return schema;
}

export interface ModelScreenProps {
  client: ApiClient;
  project: Project | null;
  /** The top bar's slot for the save state, the review count, Undo and Redo. */
  toolbar: HTMLElement | null;
}

/**
 * Loads the project's model in a session of its own and gives it to `children` once it is
 * shown; until then, says what it waits for or what the service said.
 */
export function ModelScreen({
  client,
  project,
  toolbar,
  heading,
  children,
}: ModelScreenProps & {
  heading: string;
  children: (props: {
    state: SessionState;
    model: Model;
    session: CanvasSession;
    writes: ModelWrites;
  }) => ReactNode;
}) {
  if (project === null) {
    return (
      <p className="screen-message" role="status">
        Opening the project…
      </p>
    );
  }
  return (
    <SessionFrame
      key={project.id}
      client={client}
      project={project}
      toolbar={toolbar}
      heading={heading}
    >
      {children}
    </SessionFrame>
  );
}

function SessionFrame({
  client,
  project,
  toolbar,
  heading,
  children,
}: Omit<Parameters<typeof ModelScreen>[0], "project"> & { project: Project }) {
  const { settings } = useSettings();
  const [state, session] = useSession(client, project.id, undoSteps(settings));
  const [notice, setNotice] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(0);
  const [openReview, setOpenReview] = useState(0);

  useEffect(() => {
    if (notice === null) return;
    const timer = setTimeout(() => setNotice(null), NOTICE_MS);
    return () => clearTimeout(timer);
  }, [notice]);

  // "N changes to review" moves the focus to the list.
  useLayoutEffect(() => {
    if (openReview > 0) document.getElementById("review-heading")?.focus();
  }, [openReview]);

  const free = useCallback(() => {
    if (session === null) return false;
    if (session.getState().busy) setNotice(WAIT_MODEL);
    return session.canWrite();
  }, [session]);

  const writes: ModelWrites = useMemo(
    () => ({
      free,
      edit: (label, edits) =>
        free() && session !== null
          ? session.write(editsWrite(label, edits))
          : Promise.resolve(null),
      replace: (label, build) =>
        free() && session !== null
          ? session.write(modelWrite(label, build))
          : Promise.resolve(null),
      say: setNotice,
    }),
    [free, session],
  );

  const review: ReviewActions = useMemo(
    () => ({
      accept: (key) => {
        if (free()) session?.accept(key);
      },
      reject: (key) => {
        if (free()) void session?.reject(key);
      },
      acceptAll: () => {
        if (free()) session?.acceptAll();
      },
      rejectAll: () => {
        if (free()) void session?.rejectAll();
      },
      readOnly: state.failing,
    }),
    [free, session, state.failing],
  );

  const marks = useMemo(
    () => marksOf({ baseline: state.baseline, model: state.model }),
    [state.baseline, state.model],
  );

  if (state.status === "unavailable") {
    return (
      <div className="screen-message">
        <ServiceProblem result={state.loadProblem} />
      </div>
    );
  }
  if (state.model === null || session === null) {
    return (
      <p className="screen-message" role="status">
        Loading the model…
      </p>
    );
  }
  const model = state.model;
  const busy = state.busy;
  const locked = state.failing;

  const tools = (
    <div className="canvas-tools">
      <SaveState state={state} />
      <ReviewCount count={marks.length} onOpen={() => setOpenReview((count) => count + 1)} />
      <button
        type="button"
        className="secondary tool"
        aria-label={state.undoLabel ? `Undo: ${state.undoLabel}` : "Undo"}
        title={state.undoLabel ? `Undo: ${state.undoLabel}` : "Nothing to undo"}
        disabled={state.undoLabel === null || locked}
        aria-disabled={busy || undefined}
        onClick={() => {
          if (free()) void session.undo();
        }}
      >
        <ArrowUUpLeftIcon aria-hidden="true" size={16} />
        Undo
      </button>
      <button
        type="button"
        className="secondary tool"
        aria-label={state.redoLabel ? `Redo: ${state.redoLabel}` : "Redo"}
        title={state.redoLabel ? `Redo: ${state.redoLabel}` : "Nothing to redo"}
        disabled={state.redoLabel === null || locked}
        aria-disabled={busy || undefined}
        onClick={() => {
          if (free()) void session.redo();
        }}
      >
        <ArrowUUpRightIcon aria-hidden="true" size={16} />
        Redo
      </button>
    </div>
  );

  return (
    <BusyContext.Provider value={busy}>
      <RevisionContext.Provider value={state.revision}>
        <ReviewContext.Provider value={review}>
          <div className="model-screen" aria-busy={busy}>
            {toolbar ? createPortal(tools, toolbar) : tools}
            <h1 className="visually-hidden">{heading}</h1>
            <div className="screen-notices" aria-live="polite">
              {state.failing ? (
                <p className="notice notice-error">
                  Not saved: the service is not answering. Retrying.
                </p>
              ) : null}
              {state.eventsClosed !== null ? (
                <p className="notice notice-error">{LOST_CONTACT}</p>
              ) : null}
              {state.outside !== null && state.outside.seq !== dismissed ? (
                <OutsideNotice
                  outside={state.outside}
                  clients={clientsOf(state)}
                  reloaded="The model has been reloaded; undo history was cleared."
                  onDismiss={() => setDismissed(state.outside?.seq ?? 0)}
                />
              ) : null}
              <ServiceProblem result={state.refusal} />
              {notice !== null ? (
                <p className="notice">
                  <span>{notice}</span>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="Dismiss"
                    onClick={() => setNotice(null)}
                  >
                    <XIcon aria-hidden="true" size={14} />
                  </button>
                </p>
              ) : null}
            </div>
            {marks.length > 0 ? (
              <div className="screen-review">
                <ReviewList marks={marks} model={model} />
              </div>
            ) : null}
            {children({ state, model, session, writes })}
          </div>
        </ReviewContext.Provider>
      </RevisionContext.Provider>
    </BusyContext.Provider>
  );
}
