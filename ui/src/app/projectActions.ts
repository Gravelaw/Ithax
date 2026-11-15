/**
 * Every change Home makes to a project goes through the application, which holds the open
 * project and its lesson (review of pull request 201, a third finding of one class: the
 * lesson step, the time a project was opened, then removing the open project, each made on
 * Home while App kept its own copy). App implements these; no screen calls
 * `changeProject` or `removeProject` itself (`projectActions.test.ts` checks it).
 */
import type { ApiResult } from "../api/client";
import type { Project, Template } from "../api/types";
import type { Lesson } from "../learn/lesson";

export interface ProjectActions {
  /** Opens `project` on the Canvas, without a lesson, and notes the time. */
  open(project: Project): void;
  /** Opens `project`, made from `template`, with its lesson at `step` (0 for a new one). */
  lesson(project: Project, template: Template, lesson: Lesson, step: number): void;
  /** Renames `project`; the open project takes the new name. */
  rename(project: Project, name: string): Promise<ApiResult<Project>>;
  /** Takes `project` off the list; when it is open, it and its lesson are closed. */
  remove(project: Project): Promise<ApiResult<unknown>>;
}
