/**
 * The Canvas dialogs: the delete confirmation (`docs/design/canvas-interactions.md`
 * "Deleting"; focus starts on Cancel, "Don't ask me again" turns off Settings' "Ask before
 * deleting") and Connect, the keyboard way to connect (C on a selected block).
 */
import { TrashIcon } from "@phosphor-icons/react";
import { useRef, useState } from "react";
import { Dialog } from "../components/Dialog";

export interface DeletePlan {
  blocks: string[];
  /** Every connection the delete removes: the blocks' own and the selected ones. */
  connections: number;
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

export function deleteSentence(plan: DeletePlan): string {
  const names = plan.blocks.join(", ");
  return `This removes ${names} and ${plural(plan.connections, "connection")}. You can undo it with Ctrl+Z.`;
}

export function DeleteDialog({
  plan,
  onCancel,
  onDelete,
}: {
  plan: DeletePlan;
  onCancel: () => void;
  onDelete: (dontAskAgain: boolean) => void;
}) {
  const cancel = useRef<HTMLButtonElement>(null);
  const [dontAsk, setDontAsk] = useState(false);
  return (
    <Dialog
      labelledBy="delete-title"
      describedBy="delete-sentence"
      onEscape={onCancel}
      initialFocus={cancel}
    >
      <h2 className="subheading" id="delete-title">
        Delete {plural(plan.blocks.length, "block")}?
      </h2>
      <p id="delete-sentence">{deleteSentence(plan)}</p>
      <label className="tick">
        <input
          type="checkbox"
          checked={dontAsk}
          onChange={(event) => setDontAsk(event.target.checked)}
        />
        Don't ask me again
      </label>
      <div className="dialog-actions">
        <button ref={cancel} type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="danger" onClick={() => onDelete(dontAsk)}>
          <TrashIcon aria-hidden="true" size={16} />
          Delete
        </button>
      </div>
    </Dialog>
  );
}

export function ConnectDialog({
  block,
  outputs,
  inputs,
  current,
  onCancel,
  onConnect,
}: {
  block: string;
  outputs: string[];
  inputs: string[];
  current: (port: string) => string | undefined;
  onCancel: () => void;
  onConnect: (from: string, to: string) => void;
}) {
  const [port, setPort] = useState(outputs[0] ?? "");
  const [to, setTo] = useState(current(outputs[0] ?? "") ?? inputs[0] ?? "");
  return (
    <Dialog labelledBy="connect-title" onEscape={onCancel}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (port !== "" && to !== "") onConnect(`${block}.${port}`, to);
        }}
      >
        <h2 className="subheading" id="connect-title">
          Connect <span className="mono">{block}</span>
        </h2>
        {outputs.length === 0 ? <p>This block has no output ports.</p> : null}
        <div className="panel-field">
          <label htmlFor="connect-from" className="field-label">
            Output port
          </label>
          <select
            id="connect-from"
            className="mono"
            value={port}
            onChange={(event) => {
              setPort(event.target.value);
              setTo(current(event.target.value) ?? to);
            }}
          >
            {outputs.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
        <div className="panel-field">
          <label htmlFor="connect-to" className="field-label">
            Goes to
          </label>
          <select
            id="connect-to"
            className="mono"
            value={to}
            onChange={(event) => setTo(event.target.value)}
          >
            {inputs.map((end) => (
              <option key={end} value={end}>
                {end}
              </option>
            ))}
          </select>
        </div>
        <div className="dialog-actions">
          <button type="button" className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={outputs.length === 0 || to === ""}>
            Connect
          </button>
        </div>
      </form>
    </Dialog>
  );
}
