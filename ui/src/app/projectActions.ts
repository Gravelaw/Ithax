/**
 * Every read and write of project state goes through one queue in App, as whole actions
 * (reviews of pull request 201: each reply acted on, or each list shown, while another
 * request was in flight brought a new interleaving: a removed project reopened, an older
 * name or list shown, a lesson resumed a step back). An action runs to completion before the
 * next begins, and reads the state as it is when it starts; while one is pending, Home
 * disables the actions that conflict with it.
 *
 * `projectApi` is the only code that calls the client's project requests
 * (`projectActions.test.ts` fails on any other): an action receives it from `run`, so a
 * request outside an action cannot be written.
 */
import type { ApiClient, ApiResult } from "../api/client";
import type { ChangeProject, CreateProject, Project, Template, TemplateBody } from "../api/types";
import type { Lesson } from "../learn/lesson";

/** The project requests, for use inside an action only. */
export interface ProjectApi {
  list(): Promise<ApiResult<Project[]>>;
  template(tid: string): Promise<ApiResult<TemplateBody>>;
  create(project: CreateProject): Promise<ApiResult<Project>>;
  openFolder(path: string): Promise<ApiResult<Project>>;
  change(pid: string, change: ChangeProject): Promise<ApiResult<Project>>;
  remove(pid: string): Promise<ApiResult<{ id: string; path: string }>>;
}

export function projectApi(client: ApiClient): ProjectApi {
  return {
    list: () => client.listProjects(),
    template: (tid) => client.getTemplate(tid),
    create: (project) => client.createProject(project),
    openFolder: (path) => client.openProject(path),
    change: (pid, change) => client.changeProject(pid, change),
    remove: (pid) => client.removeProject(pid),
  };
}

/** Runs `action` once every earlier action has finished; its answer. */
export type RunProjects = <T>(action: (api: ProjectApi) => Promise<T>) => Promise<T>;

/** App's handling of a project, each called inside an action with its `api`. */
export interface ProjectActions {
  /** Runs an action in App's queue. */
  run: RunProjects;
  /** Whether an action is queued or running. */
  busy: boolean;
  /** Opens `project` on the Canvas, without a lesson, and notes the time. */
  open(api: ProjectApi, project: Project): Promise<void>;
  /** Opens `project`, made from `template`, with its lesson at `step` (0 for a new one). */
  lesson(
    api: ProjectApi,
    project: Project,
    template: Template,
    lesson: Lesson,
    step: number,
  ): Promise<void>;
  /** Renames `project`; the open project takes the new name. */
  rename(api: ProjectApi, project: Project, name: string): Promise<ApiResult<Project>>;
  /** Takes `project` off the list; when it is open, it and its lesson are closed. */
  remove(api: ProjectApi, project: Project): Promise<ApiResult<unknown>>;
}
