/**
 * "Open a project folder" (`docs/design/flows.md` "Shared start" step 4; spec 3
 * `POST /v1/projects/open`). The folder is typed as a full path: the desktop shell's folder
 * picker comes with the shell (M11). The service checks the path; its issues are shown.
 * While Open is pending the dialog sends nothing more and cannot be dismissed, and once it
 * is gone it reports nothing (review of PR #44).
 */
import { type FormEvent, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { Project } from "../api/types";
import { Dialog } from "../components/Dialog";
import { ServiceProblem } from "../components/ServiceProblem";
import { usePendingRequest } from "../components/usePendingRequest";

export function OpenProjectDialog({
  client,
  onOpened,
  onCancel,
}: {
  client: ApiClient;
  onOpened: (project: Project) => void;
  onCancel: () => void;
}) {
  const [path, setPath] = useState("");
  const { busy, run } = usePendingRequest();
  const [refused, setRefused] = useState<ApiResult<Project> | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void run(
      () => client.openProject(path),
      (result) => {
        if (result.kind === "ok") onOpened(result.data);
        else setRefused(result);
      },
    );
  };

  return (
    <Dialog labelledBy="open-project-heading" onEscape={busy ? undefined : onCancel}>
      <form onSubmit={submit}>
        <h1 id="open-project-heading" className="heading">
          Open a project folder
        </h1>
        <label className="field">
          <span>Folder</span>
          <input
            className="mono"
            value={path}
            onChange={(event) => setPath(event.target.value)}
            aria-describedby="open-project-hint"
          />
        </label>
        <p id="open-project-hint" className="hint">
          The full path of a folder that holds a project.json.
        </p>
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
            Open
          </button>
        </div>
      </form>
    </Dialog>
  );
}
