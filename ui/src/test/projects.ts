/**
 * App's project queue for screen tests: `runIn(client)` runs actions one at a time on the
 * client's project requests, and `testActions` gives Home App's rename and remove, with
 * open and lesson reported to the test as it gives them (without the `api`).
 */
import type { ApiClient } from "../api/client";
import type { Project, Template } from "../api/types";
import { type ProjectActions, projectApi, type RunProjects } from "../app/projectActions";
import { oneAtATime } from "../components/oneAtATime";
import type { Lesson } from "../learn/lesson";

export function runIn(client: ApiClient): RunProjects {
  const api = projectApi(client);
  const queue = oneAtATime();
  return (action) => queue(() => action(api));
}

export interface Given {
  open?: (project: Project) => void;
  lesson?: (project: Project, template: Template, lesson: Lesson, step: number) => void;
}

export function testActions(client: ApiClient, given: Given = {}): ProjectActions {
  return {
    run: runIn(client),
    busy: false,
    open: async (_api, project) => given.open?.(project),
    lesson: async (_api, project, template, lesson, step) =>
      given.lesson?.(project, template, lesson, step),
    rename: (api, target, name) => api.change(target.id, { name }),
    remove: (api, target) => api.remove(target.id),
  };
}
