/**
 * The problems list under the canvas (`docs/design/canvas-interactions.md` "Validation and
 * error display"): the issues of the last validation, errors first, then warnings, each in
 * the service's order, shown as the service wrote them (severity, code, component, message,
 * hint). Choosing an entry selects its block; an entry about a parameter opens the
 * parameters, and one about an experiment the Experiment screen. The counts are announced
 * in a polite live region.
 */
import { CaretDownIcon, CaretUpIcon, WarningCircleIcon, WarningIcon } from "@phosphor-icons/react";
import { forwardRef, useState } from "react";
import type { Issue, Model } from "../api/types";
import { countsText, issueComponent } from "./model";

export const ProblemsList = forwardRef<
  HTMLElement,
  {
    model: Model;
    issues: Issue[];
    checking: boolean;
    onChoose: (issue: Issue, component: string | null) => void;
  }
>(function ProblemsList({ model, issues, checking, onChoose }, ref) {
  const [open, setOpen] = useState(true);
  const ordered = [
    ...issues.filter((issue) => issue.severity === "error"),
    ...issues.filter((issue) => issue.severity !== "error"),
  ];
  return (
    <section
      ref={ref}
      className={`problems${open ? "" : " problems-closed"}`}
      data-region="problems"
      aria-labelledby="problems-heading"
      tabIndex={-1}
    >
      <div className="problems-head">
        <h2 className="subheading" id="problems-heading">
          Problems
        </h2>
        <p className="muted" role="status" aria-live="polite">
          {countsText(issues)}
          {checking ? " · Checking…" : ""}
        </p>
        <button
          type="button"
          className="icon-button"
          aria-expanded={open}
          aria-controls="problems-rows"
          onClick={() => setOpen(!open)}
        >
          {open ? (
            <CaretDownIcon aria-hidden="true" size={16} />
          ) : (
            <CaretUpIcon aria-hidden="true" size={16} />
          )}
          <span className="visually-hidden">{open ? "Collapse" : "Expand"} the problems list</span>
        </button>
      </div>
      {open ? (
        <ul className="problem-rows" id="problems-rows">
          {ordered.map((issue) => {
            const component = issueComponent(issue, model);
            return (
              <li key={`${issue.code} ${issue.path} ${issue.message}`}>
                <button
                  type="button"
                  className={`problem-row ${issue.severity}`}
                  onClick={() => onChoose(issue, component)}
                >
                  {issue.severity === "error" ? (
                    <WarningCircleIcon aria-hidden="true" size={18} weight="fill" />
                  ) : (
                    <WarningIcon aria-hidden="true" size={18} weight="fill" />
                  )}
                  <span className="problem-text">
                    <span className="problem-title">
                      {issue.severity === "error" ? "Error" : "Warning"}{" "}
                      <span className="mono">{issue.code}</span>
                      {component ? <span className="mono"> {component}</span> : null}
                    </span>
                    <span>{issue.message}</span>
                    {issue.hint ? <span className="hint">{issue.hint}</span> : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
});
