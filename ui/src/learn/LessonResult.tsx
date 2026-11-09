/**
 * What Results show above the headline card for the run of a lesson's exercise (spec 4
 * "Learn and Build modes", After the run; `docs/design/flows.md` step L9; AKS-124): the
 * choice picked, whether it is the right one or which one is, the explanation, and the way
 * on: another lesson (Home, ending this one) or back to the canvas.
 */
import { CheckCircleIcon, InfoIcon } from "@phosphor-icons/react";
import type { Route } from "../app/router";
import type { Learning } from "./LearnContext";

export function LessonResult({
  learning,
  onGo,
  onExit,
}: {
  learning: Learning;
  onGo: (route: Route) => void;
  onExit: () => void;
}) {
  const { exercise } = learning.lesson;
  const picked = learning.predicted === null ? undefined : exercise.choices[learning.predicted];
  const right = exercise.choices.find((choice) => choice.right);
  return (
    <section className="lesson-result" aria-labelledby="lesson-result-heading">
      <p className="step-label small">{learning.template.title} · The exercise's answer</p>
      <h2 id="lesson-result-heading" className="subheading">
        {exercise.heading}
      </h2>
      {picked ? <p>You predicted: {picked.text}</p> : null}
      {picked?.right ? (
        <p className="lesson-verdict">
          <CheckCircleIcon aria-hidden="true" size={16} weight="fill" />
          That is right.
        </p>
      ) : right ? (
        <p className="lesson-verdict">
          <InfoIcon aria-hidden="true" size={16} weight="fill" />
          The right answer: {right.text}
        </p>
      ) : null}
      <p>{exercise.explanation}</p>
      <div className="button-row">
        <button
          type="button"
          className="primary"
          onClick={() => {
            onExit();
            onGo({ screen: "home", projectId: null });
          }}
        >
          Try another lesson
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => onGo({ screen: "canvas", projectId: learning.projectId })}
        >
          Back to the canvas
        </button>
      </div>
    </section>
  );
}
