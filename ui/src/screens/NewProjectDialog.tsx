/**
 * "New empty project" asks a name and Process or Plan (owner design review, "API additions
 * and the open gap"; spec 3 `POST /v1/projects` with `domain`). The service checks the
 * name; its issues are shown as they come.
 */
import { type FormEvent, useRef, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { Domain, Project } from "../api/types";
import { Dialog } from "../components/Dialog";
import { ServiceProblem } from "../components/ServiceProblem";

export const DOMAINS: readonly { value: Domain; label: string; hint: string }[] = [
  { value: "process", label: "Process (flows and queues)", hint: "Items move through steps." },
  {
    value: "optimization",
    label: "Plan (decisions and limits)",
    hint: "Choose the best values within limits.",
  },
];

export function NewProjectDialog({
  client,
  onCreated,
  onCancel,
}: {
  client: ApiClient;
  onCreated: (project: Project) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState<Domain>("process");
  const [busy, setBusy] = useState(false);
  // A second press while the request is pending would create a second project, since each
  // POST /v1/projects makes a new one; the ref sees it before React re-renders.
  const pending = useRef(false);
  const [refused, setRefused] = useState<ApiResult<Project> | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    const result = await client.createProject({ name, domain });
    pending.current = false;
    setBusy(false);
    if (result.kind === "ok") onCreated(result.data);
    else setRefused(result);
  };

  return (
    <Dialog labelledBy="new-project-heading" onEscape={onCancel}>
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
          <button type="button" className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={busy}>
            Create
          </button>
        </div>
      </form>
    </Dialog>
  );
}
