/**
 * The lesson being played (spec 4 "Learn and Build modes"; AKS-124): which project it is
 * for, the template and its lesson, the step reached, the prediction chosen, whether
 * "Make the change" was accepted, and the exercise's run. It is held by the interface only
 * while it is open: the project folder holds only what spec 3 lists, so a reload ends it.
 */
import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";
import type { Template } from "../api/types";
import type { Lesson } from "./lesson";

export interface Learning {
  projectId: string;
  template: Template;
  lesson: Lesson;
  /** The step shown: 0 to `lesson.steps.length`, the last being the exercise. */
  step: number;
  /** The index of the choice picked, or `null`. */
  prediction: number | null;
  /** Whether "Make the change" was accepted (counts for edits `changeMade` cannot read). */
  sent: boolean;
  /** The exercise's run, once started, and the choice picked when it was started. */
  runId: string | null;
  predicted: number | null;
}

export interface LearnControls {
  learning: Learning | null;
  start(learning: Learning): void;
  update(change: Partial<Omit<Learning, "projectId" | "template" | "lesson">>): void;
  exit(): void;
}

const NONE: LearnControls = {
  learning: null,
  start: () => undefined,
  update: () => undefined,
  exit: () => undefined,
};

export const LearnContext = createContext<LearnControls>(NONE);

export function useLearning(): LearnControls {
  return useContext(LearnContext);
}

/** The lesson for one project, or `null` when none is played on it. */
export function useLessonFor(projectId: string): LearnControls & { learning: Learning | null } {
  const controls = useLearning();
  return controls.learning?.projectId === projectId ? controls : { ...controls, learning: null };
}

export function LearnProvider({
  children,
  initial = null,
}: {
  children: ReactNode;
  initial?: Learning | null;
}) {
  const [learning, setLearning] = useState<Learning | null>(initial);
  const start = useCallback((next: Learning) => setLearning(next), []);
  const update = useCallback<LearnControls["update"]>(
    (change) => setLearning((current) => (current === null ? null : { ...current, ...change })),
    [],
  );
  const exit = useCallback(() => setLearning(null), []);
  const value = useMemo(() => ({ learning, start, update, exit }), [learning, start, update, exit]);
  return <LearnContext.Provider value={value}>{children}</LearnContext.Provider>;
}

/** A new lesson on `projectId`, at its first step. */
export function newLearning(projectId: string, template: Template, lesson: Lesson): Learning {
  return {
    projectId,
    template,
    lesson,
    step: 0,
    prediction: null,
    sent: false,
    runId: null,
    predicted: null,
  };
}
