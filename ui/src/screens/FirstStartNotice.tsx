/**
 * The first-start notice (spec 3 "Service rules", First start; `docs/design/flows.md`
 * "Shared start" step 2; `docs/design/wireframes/08-first-start-notice.svg`): what the tool
 * does, that results are estimates to support judgement, and where the licence is. One
 * button, Continue, which is where focus starts. It is shown until `first_start_seen` is
 * stored in `settings.json`.
 */
import { useRef } from "react";
import { Dialog } from "../components/Dialog";

export const NOTICE_TEXT = {
  heading: "Welcome",
  does: "Build a model of a process, run it many times, and see where the waits and bottlenecks are. No code needed.",
  estimates:
    "Results are estimates from a simulation. Use them to support your judgement, not to replace it.",
  licence:
    "This is free software under the GNU AGPL version 3. Read the licence any time in Settings, About.",
} as const;

export function FirstStartNotice({ onContinue }: { onContinue: () => void }) {
  const button = useRef<HTMLButtonElement>(null);
  return (
    <Dialog labelledBy="first-start-heading" initialFocus={button}>
      <h1 id="first-start-heading" className="title">
        {NOTICE_TEXT.heading}
      </h1>
      <h2 className="subheading">What it does</h2>
      <p>{NOTICE_TEXT.does}</p>
      <h2 className="subheading">Results are estimates</h2>
      <p>{NOTICE_TEXT.estimates}</p>
      <h2 className="subheading">Licence</h2>
      <p>{NOTICE_TEXT.licence}</p>
      <div className="dialog-actions">
        <button ref={button} type="button" className="primary" onClick={onContinue}>
          Continue
        </button>
      </div>
    </Dialog>
  );
}
