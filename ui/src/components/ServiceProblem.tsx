/**
 * What the service said when it refused a request: its spec 1 issue objects, shown as the
 * service wrote them (code, message, hint, path). The interface writes no text of its own
 * for a model or request problem; only lost contact, where the service said nothing, has
 * the interface's words (`docs/design/flows.md` "Error and edge paths").
 */
import { WarningCircleIcon } from "@phosphor-icons/react";
import type { ApiResult } from "../api/client";
import type { Issue } from "../api/types";

export const LOST_CONTACT = "Lost contact with the engine service.";

export function IssueList({ issues }: { issues: Issue[] }) {
  return (
    <ul className="issues">
      {issues.map((issue) => (
        <li
          key={`${issue.code} ${issue.path} ${issue.message}`}
          className={`issue ${issue.severity}`}
        >
          <WarningCircleIcon aria-hidden="true" size={18} weight="fill" />
          <div>
            <p>
              <span className="mono">{issue.code}</span> {issue.message}
            </p>
            {issue.hint ? <p className="hint">{issue.hint}</p> : null}
            {issue.path ? <p className="mono hint">at {issue.path}</p> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

/** The problem of a result that is not `ok`; nothing for an `ok` one. */
export function ServiceProblem({ result }: { result: ApiResult<unknown> | null }) {
  if (result === null || result.kind === "ok") return null;
  if (result.kind === "failed") {
    return (
      <div className="problem" role="alert">
        <p>{LOST_CONTACT}</p>
      </div>
    );
  }
  return (
    <div className="problem" role="alert">
      {result.issues.length > 0 ? (
        <IssueList issues={result.issues} />
      ) : (
        <p>
          <span className="mono">{result.error.code}</span> {result.error.message}
        </p>
      )}
    </div>
  );
}
