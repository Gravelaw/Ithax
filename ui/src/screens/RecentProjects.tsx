/**
 * Home's recent projects (#97, Reviewer B finding 10): newest opened first (a project never
 * opened after the ones that were, newest registered first among them), each with when it
 * was last opened or made, a rename in place, and "Remove from the list", which keeps the
 * project's folder (`POST /v1/projects/{pid}/remove`; "Open a project folder" lists it
 * again). Opening one notes the time (`PATCH /v1/projects/{pid}` `{opened: true}`).
 */
import { PencilSimpleIcon, XIcon } from "@phosphor-icons/react";
import { useState } from "react";
import type { ApiResult } from "../api/client";
import type { Project } from "../api/types";
import type { ProjectActions } from "../app/projectActions";
import { ServiceProblem } from "../components/ServiceProblem";
import { dateText, whenText } from "../results/display";

export const REMOVED_KEEPS_FILES =
  "Taken off the list. Its folder and files are kept: open the folder to list it again.";

/** Newest opened first, then those never opened, newest registered first. */
export function recentOrder(projects: readonly Project[]): Project[] {
  const registered = [...projects].reverse();
  return registered
    .map((project, index) => ({ project, index }))
    .sort((a, b) => {
      const left = a.project.opened ?? "";
      const right = b.project.opened ?? "";
      if (left !== right) return left < right ? 1 : -1;
      return a.index - b.index;
    })
    .map(({ project }) => project);
}

function when(project: Project): string {
  if (!project.available) return "Not available";
  if (project.opened) return `Last opened ${whenText(project.opened)}`;
  if (project.created === null) return "";
  const date = dateText(project.created);
  return date === project.created ? "" : `Created ${date}`;
}

export function RecentProjects({
  projects,
  actions,
  onChanged,
}: {
  projects: readonly Project[];
  /** The application's, which also updates the open project (review of pull request 201). */
  actions: ProjectActions;
  /** Reads the list again after a rename or a removal. */
  onChanged: () => void;
}) {
  const [renaming, setRenaming] = useState<string | null>(null);
  const [problem, setProblem] = useState<ApiResult<unknown> | null>(null);
  const [removed, setRemoved] = useState(false);

  const rename = async (project: Project, name: string) => {
    setRenaming(null);
    if (name.trim() === "" || name.trim() === project.name) return;
    const answer = await actions.rename(project, name.trim());
    setProblem(answer.kind === "ok" ? null : answer);
    onChanged();
  };

  const remove = async (project: Project) => {
    const answer = await actions.remove(project);
    setProblem(answer.kind === "ok" ? null : answer);
    setRemoved(answer.kind === "ok");
    onChanged();
  };

  return (
    <>
      <ul className="projects">
        {recentOrder(projects).map((project) => {
          const name = project.name ?? project.path;
          return (
            <li key={project.id} className="project-row">
              {renaming === project.id ? (
                <input
                  className="project-rename"
                  aria-label={`New name for ${name}`}
                  defaultValue={project.name ?? ""}
                  // biome-ignore lint/a11y/noAutofocus: the field the Rename button opens
                  autoFocus
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void rename(project, event.currentTarget.value);
                    if (event.key === "Escape") setRenaming(null);
                  }}
                  onBlur={(event) => void rename(project, event.target.value)}
                />
              ) : (
                <button
                  type="button"
                  className="project"
                  aria-disabled={project.available ? undefined : "true"}
                  onClick={() => {
                    if (project.available) actions.open(project);
                  }}
                >
                  <span className="subheading">{name}</span>
                  <span className="muted small">{when(project)}</span>
                  <span className="mono small muted">{project.path}</span>
                </button>
              )}
              <span className="project-actions">
                {project.available ? (
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Rename ${name}`}
                    title="Rename"
                    onClick={() => setRenaming(project.id)}
                  >
                    <PencilSimpleIcon aria-hidden="true" size={16} />
                  </button>
                ) : null}
                <button
                  type="button"
                  className="icon-button"
                  aria-label={`Remove ${name} from the list`}
                  title="Remove from the list (the files are kept)"
                  onClick={() => void remove(project)}
                >
                  <XIcon aria-hidden="true" size={16} />
                </button>
              </span>
            </li>
          );
        })}
      </ul>
      {removed ? (
        <p className="muted small" role="status">
          {REMOVED_KEEPS_FILES}
        </p>
      ) : null}
      <ServiceProblem result={problem} />
    </>
  );
}
