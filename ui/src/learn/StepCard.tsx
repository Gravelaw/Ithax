/**
 * The lesson's step card (spec 4 "Learn and Build modes"; `docs/design/canvas-interactions.md`
 * "Learn mode on the canvas"; `docs/design/wireframes/01b-canvas-learn.svg`; AKS-124).
 *
 * "Step k of n", the step's heading and text, Back and Next, and "Exit lesson". The last
 * step is the exercise: its Change text, each of the exercise's edits with the value the
 * model shown holds and the value it sets, "Make the change" (the edits as one batch, one
 * undo step, under the Save rule), the choices under "What do you think will happen?",
 * and Run, available once the change is made, a choice is picked and the Canvas's Run
 * rule allows a run. Run starts the template's experiment (none for an `optimization`
 * model) and opens the Run monitor. The right choice is not shown here.
 */
import { ArrowLeftIcon, ArrowRightIcon, CheckCircleIcon, PlayIcon } from "@phosphor-icons/react";
import { useCallback, useId, useState } from "react";
import type { Model } from "../api/types";
import type { Route } from "../app/router";
import { editsWrite } from "../canvas/plans";
import type { CanvasSession, SessionState } from "../canvas/session";
import { runBlocked, WAIT } from "../canvas/Toolbar";
import { useMounted } from "../components/useMounted";
import { type Learning, useLearning } from "./LearnContext";
import { changeMade, changeRows, type Inline, paragraphs, valueText } from "./lesson";

/** Why the step card's Run waits, before the Canvas's own reasons. */
export const MAKE_THE_CHANGE = "Make the change to run.";
export const CHOOSE_FIRST = "Choose what you think will happen to run.";

function Text({ text }: { text: string }) {
  return (
    <>
      {paragraphs(text).map((parts: Inline[], index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: paragraphs have no other identity
        <p key={index}>
          {parts.map((part, at) =>
            part.code ? (
              // biome-ignore lint/suspicious/noArrayIndexKey: parts have no other identity
              <code key={at}>{part.text}</code>
            ) : (
              part.text
            ),
          )}
        </p>
      ))}
    </>
  );
}

/** Whether the model shown holds the exercise's change. */
export function exerciseMade(learning: Learning, model: Model): boolean {
  const edits = learning.template.exercise?.edits ?? [];
  return changeMade(model, edits) ?? learning.sent;
}

export function StepCard({
  learning,
  model,
  state,
  session,
  present,
  what,
  onGo,
}: {
  learning: Learning;
  model: Model;
  state: SessionState;
  session: CanvasSession;
  /** Whether the model has what the step names. */
  present: boolean;
  /** What the step names, in words: "block" on the Canvas, "part of the plan" for a plan. */
  what: string;
  onGo: (route: Route) => void;
}) {
  const { update, exit } = useLearning();
  const mounted = useMounted();
  const [notice, setNotice] = useState<string | null>(null);
  const name = useId();
  const { lesson, step, template } = learning;
  const count = lesson.steps.length + 1;
  const exercise = step >= lesson.steps.length;
  const shown = exercise ? lesson.exercise : lesson.steps[step];
  const edits = template.exercise?.edits ?? [];
  const made = exerciseMade(learning, model);
  const blocked = runBlocked(state);
  const reason = !made
    ? MAKE_THE_CHANGE
    : learning.prediction === null
      ? CHOOSE_FIRST
      : (blocked?.reason ?? null);

  const go = (to: number) => {
    setNotice(null);
    update({ step: Math.max(0, Math.min(count - 1, to)) });
  };

  const makeChange = useCallback(() => {
    if (!session.canWrite()) {
      if (session.getState().busy) setNotice(WAIT);
      return;
    }
    setNotice(null);
    void session.write(editsWrite(`exercise: ${lesson.exercise.heading}`, edits)).then((result) => {
      if (result?.kind === "ok" && mounted.current) update({ sent: true });
    });
  }, [session, edits, lesson.exercise.heading, update, mounted]);

  const run = useCallback(() => {
    if (reason !== null || runBlocked(session.getState()) !== null) return;
    const experiment = model.domain === "optimization" ? null : (template.experiment ?? null);
    void session.startRun(experiment).then((result) => {
      if (result?.kind !== "ok" || !mounted.current) return;
      update({ runId: result.data.run_id, predicted: learning.prediction });
      onGo({ screen: "monitor", projectId: learning.projectId, runId: result.data.run_id });
    });
  }, [reason, session, model.domain, template.experiment, update, onGo, learning, mounted]);

  if (shown === undefined) return null;
  return (
    <section
      className="step-card"
      aria-labelledby="step-heading"
      data-region="lesson"
      tabIndex={-1}
    >
      <p className="step-label small">
        {template.title} · Step {step + 1} of {count}
        {exercise ? " · Try it" : ""}
      </p>
      <h2 id="step-heading" className="subheading">
        {shown.heading}
      </h2>
      {!present ? (
        <p className="notice" role="status">
          This step's {what}, <code>{shown.component}</code>, is no longer in the model.
        </p>
      ) : null}
      {exercise ? (
        <>
          <h3 className="step-part">Change</h3>
          <Text text={lesson.exercise.change} />
          <ul className="change-list" aria-label="The change">
            {changeRows(model, edits).map((row, index) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: two edits may name one place
              <li key={`${index}:${row.where}`}>
                <code>{row.where}</code>: {valueText(row.now)} → {valueText(row.to)}
              </li>
            ))}
          </ul>
          {made ? (
            <p className="change-made" role="status">
              <CheckCircleIcon aria-hidden="true" size={16} weight="fill" />
              The change is made.
            </p>
          ) : (
            <button
              type="button"
              className="secondary"
              aria-disabled={state.busy || state.failing || undefined}
              onClick={makeChange}
            >
              Make the change
            </button>
          )}
          {notice !== null ? <p className="notice">{notice}</p> : null}
          <fieldset className="choices prediction">
            <legend className="step-part">What do you think will happen?</legend>
            {lesson.exercise.choices.map((choice, index) => (
              <label key={choice.text} className="choice">
                <input
                  type="radio"
                  name={name}
                  checked={learning.prediction === index}
                  onChange={() => update({ prediction: index })}
                />
                <span>{choice.text}</span>
              </label>
            ))}
          </fieldset>
        </>
      ) : (
        <Text text={shown.text} />
      )}
      <div className="button-row">
        <button
          type="button"
          className="secondary"
          disabled={step === 0}
          onClick={() => go(step - 1)}
        >
          <ArrowLeftIcon aria-hidden="true" size={16} />
          Back
        </button>
        {exercise ? (
          <button
            type="button"
            className="primary"
            aria-disabled={reason !== null || undefined}
            aria-describedby={reason !== null ? "lesson-run-reason" : undefined}
            onClick={run}
          >
            <PlayIcon aria-hidden="true" size={16} weight="fill" />
            Run the exercise
          </button>
        ) : (
          <button type="button" className="primary" onClick={() => go(step + 1)}>
            Next
            <ArrowRightIcon aria-hidden="true" size={16} />
          </button>
        )}
      </div>
      {exercise && reason !== null ? (
        <p id="lesson-run-reason" className="small muted">
          {reason}
        </p>
      ) : null}
      <button type="button" className="link" onClick={exit}>
        Exit lesson
      </button>
    </section>
  );
}
