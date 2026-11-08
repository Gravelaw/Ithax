/**
 * The model's parameters (spec 1 "Parameters"), shown in the side panel when nothing is
 * selected (`docs/design/canvas-interactions.md` "Selecting"). Each is created and changed
 * with `set_parameter` and removed with `remove_parameter` (spec 3 "Model edits"); clearing
 * `min` or `max` writes the whole model, since no edit removes a field. No scenario is made
 * here: the Experiment screen does that (AKS-120).
 */
import { useId, useState } from "react";
import type { Issue, Model, Parameter } from "../api/types";
import { readNumber, shown, withoutParameterField } from "./model";
import { CommitInput, type FieldActions, FieldIssues } from "./SettingFields";

const TYPES = ["integer", "number", "quantity"] as const;

/** A typed value as the parameter's `type` writes it: a number, or a time as text. */
function typed(type: unknown, text: string): unknown {
  return type === "quantity" ? text.trim() : readNumber(text);
}

function ParameterRow({
  id,
  parameter,
  issues,
  readOnly,
  actions,
}: {
  id: string;
  parameter: Parameter;
  issues: Issue[];
  readOnly: boolean;
  actions: FieldActions;
}) {
  const base = useId();
  const set = (field: "value" | "min" | "max", text: string) => {
    if (text.trim() === "") {
      // Cleared if the parameter holds it when the write is sent.
      if (field !== "value") {
        actions.replace(`clear ${field} of parameter ${id}`, (model) =>
          model.parameters?.[id]?.[field] === undefined
            ? null
            : withoutParameterField(model, id, field),
        );
      }
      return;
    }
    // Read by the parameter's type as it is when the write is sent.
    actions.edit(`set ${field} of parameter ${id}`, (model) => [
      { edit: "set_parameter", id, [field]: typed(model.parameters?.[id]?.type, text) },
    ]);
  };
  return (
    <fieldset className="parameter">
      <legend className="mono">{id}</legend>
      <FieldIssues issues={issues} />
      <div className="parameter-grid">
        <label htmlFor={`${base}-type`} className="field-label">
          Type
        </label>
        <select
          id={`${base}-type`}
          value={String(parameter.type)}
          disabled={readOnly}
          onChange={(event) =>
            actions.edit(`set type of parameter ${id}`, [
              { edit: "set_parameter", id, type: event.target.value },
            ])
          }
        >
          {!TYPES.includes(parameter.type as (typeof TYPES)[number]) ? (
            <option value={String(parameter.type)}>{String(parameter.type)}</option>
          ) : null}
          {TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        {(["value", "min", "max"] as const).map((field) => (
          <ParameterField
            key={field}
            id={`${base}-${field}`}
            label={
              field === "value" ? "Value" : field === "min" ? "Min (optional)" : "Max (optional)"
            }
            value={shown(parameter[field])}
            readOnly={readOnly}
            onCommit={(text) => set(field, text)}
          />
        ))}
      </div>
      <button
        type="button"
        className="secondary small-button"
        disabled={readOnly}
        onClick={() => actions.edit(`remove parameter ${id}`, [{ edit: "remove_parameter", id }])}
      >
        Remove {id}
      </button>
    </fieldset>
  );
}

function ParameterField({
  id,
  label,
  value,
  readOnly,
  onCommit,
}: {
  id: string;
  label: string;
  value: string;
  readOnly: boolean;
  onCommit: (text: string) => void;
}) {
  return (
    <>
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      <CommitInput id={id} value={value} readOnly={readOnly} onCommit={onCommit} />
    </>
  );
}

function AddParameter({ readOnly, actions }: { readOnly: boolean; actions: FieldActions }) {
  const base = useId();
  const [id, setId] = useState("");
  const [type, setType] = useState<string>("integer");
  const [value, setValue] = useState("");
  const [min, setMin] = useState("");
  const [max, setMax] = useState("");
  const add = () => {
    const edit: { edit: "set_parameter"; id: string; [field: string]: unknown } = {
      edit: "set_parameter",
      id: id.trim(),
      type,
      value: typed(type, value),
    };
    if (min.trim() !== "") edit.min = typed(type, min);
    if (max.trim() !== "") edit.max = typed(type, max);
    actions.edit(`add parameter ${id.trim()}`, [edit as { edit: "set_parameter"; id: string }]);
    setId("");
    setValue("");
    setMin("");
    setMax("");
  };
  return (
    <form
      className="add-parameter"
      aria-labelledby={`${base}-title`}
      onSubmit={(event) => {
        event.preventDefault();
        add();
      }}
    >
      <h3 className="subheading" id={`${base}-title`}>
        Add parameter
      </h3>
      <div className="parameter-grid">
        <label htmlFor={`${base}-id`} className="field-label">
          Id
        </label>
        <input
          id={`${base}-id`}
          className="mono"
          value={id}
          disabled={readOnly}
          onChange={(event) => setId(event.target.value)}
        />
        <label htmlFor={`${base}-type`} className="field-label">
          Type
        </label>
        <select
          id={`${base}-type`}
          value={type}
          disabled={readOnly}
          onChange={(event) => setType(event.target.value)}
        >
          {TYPES.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <label htmlFor={`${base}-value`} className="field-label">
          Value
        </label>
        <input
          id={`${base}-value`}
          value={value}
          disabled={readOnly}
          onChange={(event) => setValue(event.target.value)}
        />
        <label htmlFor={`${base}-min`} className="field-label">
          Min (optional)
        </label>
        <input
          id={`${base}-min`}
          value={min}
          disabled={readOnly}
          onChange={(event) => setMin(event.target.value)}
        />
        <label htmlFor={`${base}-max`} className="field-label">
          Max (optional)
        </label>
        <input
          id={`${base}-max`}
          value={max}
          disabled={readOnly}
          onChange={(event) => setMax(event.target.value)}
        />
      </div>
      <button type="submit" className="secondary" disabled={readOnly}>
        Add parameter
      </button>
    </form>
  );
}

export function Parameters({
  model,
  issues,
  readOnly,
  actions,
}: {
  model: Model;
  issues: Issue[];
  readOnly: boolean;
  actions: FieldActions;
}) {
  const parameters = Object.entries(model.parameters ?? {});
  return (
    <section className="panel-section" aria-labelledby="parameters-heading">
      <h2 className="heading" id="parameters-heading">
        Parameters
      </h2>
      {parameters.length === 0 ? <p className="muted">No parameters yet.</p> : null}
      {parameters.map(([id, parameter]) => (
        <ParameterRow
          key={id}
          id={id}
          parameter={parameter}
          issues={issues.filter(
            (issue) =>
              issue.path === `/parameters/${id}` || issue.path.startsWith(`/parameters/${id}/`),
          )}
          readOnly={readOnly}
          actions={actions}
        />
      ))}
      <AddParameter readOnly={readOnly} actions={actions} />
    </section>
  );
}
