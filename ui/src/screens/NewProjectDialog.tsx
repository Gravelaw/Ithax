/**
 * "New empty project" asks a name and Process or Plan (owner design review, "API additions
 * and the open gap"; spec 3 `POST /v1/projects` with `domain`). The service checks the
 * name; its issues are shown as they come. While Create is pending the dialog sends nothing
 * more and cannot be dismissed, and once it is gone it reports nothing (review of PR #44).
 */
import { type FormEvent, useState } from "react";
import type { ApiResult } from "../api/client";
import type { Domain, Project } from "../api/types";
import type { ProjectApi, RunProjects } from "../app/projectActions";
import { Dialog } from "../components/Dialog";
import { ServiceProblem } from "../components/ServiceProblem";
import { useMounted } from "../components/useMounted";
import { usePendingRequest } from "../components/usePendingRequest";

export const DOMAINS: readonly { value: Domain; label: string; hint: string }[] = [
  { value: "process", label: "Process (flows and queues)", hint: "Items move through steps." },
  {
    value: "optimization",
    label: "Plan (decisions and limits)",
    hint: "Choose the best values within limits.",
  },
];

export function NewProjectDialog({
  projects,
  onCreated,
  onCancel,
}: {
  /** App's queue of project actions (review of pull request 201). */
  projects: RunProjects;
  /** Opens the project, inside the same action. */
  onCreated: (api: ProjectApi, project: Project) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState<Domain>("process");
  const { busy, run } = usePendingRequest();
  const mounted = useMounted();
  const [refused, setRefused] = useState<ApiResult<Project> | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void run(
      () =>
        projects(async (api) => {
          const result = await api.create({ name, domain });
          // A dialog closed meanwhile opens nothing.
          if (result.kind === "ok" && mounted.current) await onCreated(api, result.data);
          return result;
        }),
      (result) => {
        if (result.kind !== "ok") setRefused(result);
      },
    );
  };

  return (
    <Dialog labelledBy="new-project-heading" onEscape={busy ? undefined : onCancel}>
      <form onSubmit={submit}>
        <h1 id="new-project-heading" className="heading">
          New empty project
        </h1>
        <label className="field">
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <fieldset className="choices">
          <legend>What will you model?</legend>
          {DOMAINS.map((choice) => (
            <label key={choice.value} className="choice">
              <input
                type="radio"
                name="domain"
                value={choice.value}
                checked={domain === choice.value}
                onChange={() => setDomain(choice.value)}
              />
              <span>
                <strong>{choice.label}</strong>
                <span className="hint">{choice.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>
        <ServiceProblem result={refused} />
        <div className="dialog-actions">
          <button
            type="button"
            className="secondary"
            onClick={busy ? undefined : onCancel}
            aria-disabled={busy ? "true" : undefined}
          >
            Cancel
          </button>
          <button type="submit" className="primary" aria-disabled={busy ? "true" : undefined}>
            Create
          </button>
        </div>
      </form>
    </Dialog>
  );
}
