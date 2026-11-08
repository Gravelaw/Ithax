/**
 * The settings form of a block, built from its type's description (`GET
 * /v1/schema/components/{type}`; `docs/design/design-system.md` "Controls"). Each kind of
 * setting has its field: numbers, time quantities (a number and a unit), distributions (a
 * type and the fields it needs, spec 1 "Distributions"), choices, references to other
 * blocks, lists, and objects keyed by another setting or listed in rows. A number or time
 * can instead use a parameter (`{"$param": id}`, spec 1 "Parameters").
 *
 * A field changes the model only when it is committed (Enter, or leaving the field), with
 * one `set_setting`; text that is not a number is sent as typed, so the service, not the
 * interface, says what is wrong with it. A field shows the service's issues whose `path`
 * names it.
 */
import { WarningCircleIcon } from "@phosphor-icons/react";
import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import type { Component, Edit, Issue, Model, SettingDescription } from "../api/types";
import {
  components,
  DISTRIBUTIONS,
  isRequired,
  paramOf,
  pointer,
  readNumber,
  settingEdit,
  shown,
  splitQuantity,
  TIME_UNITS,
  valueAt,
  withoutSetting,
  words,
} from "./model";

/**
 * Edits, or a plan that builds them from the model as it is when the write is sent (after
 * every write queued before it has answered); `null` or `[]` sends nothing.
 */
export type EditPlan = Edit[] | ((model: Model) => Edit[] | null);

/** What a field does to the model: one batch of edits, or a whole model (clearing). */
export interface FieldActions {
  edit(label: string, edits: EditPlan): void;
  /** A whole model, built when the write is sent; `null` sends nothing. */
  replace(label: string, build: (model: Model) => Model | null): void;
}

/** The component of that id in `model`, or undefined. */
export function componentIn(model: Model, id: string): Component | undefined {
  return components(model).find((item) => item.id === id);
}

export interface FieldContext {
  model: Model;
  component: Component;
  /** The block's issues whose `path` lies inside its `params`, by that path. */
  issues: Map<string, Issue[]>;
  readOnly: boolean;
  actions: FieldActions;
}

type Segments = readonly (string | number)[];

export function FieldIssues({ issues }: { issues: Issue[] | undefined }) {
  if (!issues || issues.length === 0) return null;
  return (
    <ul className="field-issues">
      {issues.map((issue) => (
        <li key={`${issue.code} ${issue.message}`} className={`field-issue ${issue.severity}`}>
          <WarningCircleIcon aria-hidden="true" size={14} weight="fill" />
          <span>
            <span className="mono">{issue.code}</span> {issue.message}
            {issue.hint ? <span className="hint"> {issue.hint}</span> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** A text box that commits on Enter or on leaving it, and reverts on Escape. */
export function CommitInput({
  id,
  value,
  onCommit,
  readOnly,
  mono,
  describedBy,
  invalid,
}: {
  id: string;
  value: string;
  onCommit: (text: string) => void;
  readOnly: boolean;
  mono?: boolean;
  describedBy?: string;
  invalid?: boolean;
}) {
  const [text, setText] = useState(value);
  const editing = useRef(false);
  // The text last committed from this box, or last shown from the model: a commit is sent
  // when the text differs from it, not from what the model held when drawn (a value typed
  // and then cleared before the first answer is cleared; review of PR #45).
  const committed = useRef(value);
  useEffect(() => {
    if (!editing.current) {
      setText(value);
      committed.current = value;
    }
  }, [value]);
  const commit = () => {
    editing.current = false;
    if (text !== committed.current) {
      committed.current = text;
      onCommit(text);
    }
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    } else if (event.key === "Escape") {
      editing.current = false;
      setText(committed.current);
    }
  };
  return (
    <input
      id={id}
      type="text"
      className={mono ? "mono" : undefined}
      value={text}
      readOnly={readOnly}
      aria-describedby={describedBy}
      aria-invalid={invalid ? true : undefined}
      onChange={(event) => {
        editing.current = true;
        setText(event.target.value);
      }}
      onBlur={commit}
      onKeyDown={onKeyDown}
    />
  );
}

function Field({
  label,
  htmlFor,
  hint,
  hintId,
  issues,
  children,
}: {
  label: ReactNode;
  htmlFor?: string;
  hint?: string;
  hintId?: string;
  issues?: Issue[] | undefined;
  children: ReactNode;
}) {
  return (
    <div className="panel-field">
      {htmlFor ? (
        <label htmlFor={htmlFor} className="field-label">
          {label}
        </label>
      ) : (
        <span className="field-label">{label}</span>
      )}
      {children}
      {hint ? (
        <p className="hint" id={hintId}>
          {hint}
        </p>
      ) : null}
      <FieldIssues issues={issues} />
    </div>
  );
}

function labelOf(setting: SettingDescription, required: boolean): string {
  return required ? words(setting.name) : `${words(setting.name)} (optional)`;
}

function hintOf(setting: SettingDescription): string | undefined {
  return setting.default === undefined ? undefined : `Default: ${shown(setting.default)}`;
}

/**
 * Sets the value at `segments`. The edit is built when it is sent, from the component as
 * the earlier queued writes left it (a `set_setting` path depends on what already exists).
 * A function value is given the value there at that moment, and `undefined` sends nothing.
 */
function write(
  ctx: FieldContext,
  segments: Segments,
  value: unknown | ((current: unknown) => unknown),
): void {
  const id = ctx.component.id;
  ctx.actions.edit(`set ${id}${pointer(segments)}`, (model) => {
    const component = componentIn(model, id);
    if (component === undefined) return null;
    const next =
      typeof value === "function"
        ? (value as (current: unknown) => unknown)(valueAt(component.params, segments))
        : value;
    return next === undefined ? null : [settingEdit(component, segments, next)];
  });
}

/** Clears the value at `segments`, if the model holds one when the write is sent. */
function clear(ctx: FieldContext, segments: Segments): void {
  const id = ctx.component.id;
  ctx.actions.replace(`clear ${id}${pointer(segments)}`, (model) => {
    const component = componentIn(model, id);
    if (component === undefined || valueAt(component.params, segments) === undefined) return null;
    return withoutSetting(model, id, segments);
  });
}

/** "Use parameter": a tick box and a picker of the model's parameters. */
function ParameterLink({
  ctx,
  segments,
  value,
  fieldId,
  onUnlink,
}: {
  ctx: FieldContext;
  segments: Segments;
  value: unknown;
  fieldId: string;
  onUnlink: () => void;
}) {
  const bound = paramOf(value);
  // The user's own choice until the model answers with a new value: whether the box is
  // ticked, and the parameter chosen (review of PR #45).
  const [draft, setDraft] = useState<{ on: boolean; id: string | null } | null>(null);
  const boundText = JSON.stringify(value);
  useEffect(() => {
    if (boundText !== undefined) setDraft(null);
  }, [boundText]);
  const on = draft?.on ?? bound !== null;
  const chosen = draft === null ? bound : draft.id;
  const ids = Object.keys(ctx.model.parameters ?? {});
  const name = words(String(segments.at(-1)));
  return (
    <div className="param-link">
      <label className="tick">
        <input
          type="checkbox"
          aria-label={`Use parameter for ${name}`}
          checked={on}
          disabled={ctx.readOnly}
          onChange={(event) => {
            if (event.target.checked) setDraft({ on: true, id: null });
            else {
              setDraft({ on: false, id: null });
              onUnlink();
            }
          }}
        />
        Use parameter
      </label>
      {on ? (
        <select
          id={`${fieldId}-param`}
          aria-label={`Parameter for ${name}`}
          value={chosen ?? ""}
          disabled={ctx.readOnly}
          onChange={(event) => {
            if (event.target.value !== "") {
              setDraft({ on: true, id: event.target.value });
              write(ctx, segments, { $param: event.target.value });
            }
          }}
        >
          <option value="" disabled>
            Choose a parameter
          </option>
          {bound !== null && !ids.includes(bound) ? <option value={bound}>{bound}</option> : null}
          {ids.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      ) : null}
    </div>
  );
}

/** A number or a time quantity, or a parameter in its place. */
function ValueField({
  ctx,
  setting,
  segments,
  required,
  label,
}: {
  ctx: FieldContext;
  setting: SettingDescription;
  segments: Segments;
  required: boolean;
  label?: string;
}) {
  const id = `field-${ctx.component.id}${pointer(segments)}`;
  const hintId = `${id}-hint`;
  const value = valueAt(ctx.component.params, segments);
  const bound = paramOf(value);
  const time = setting.kind === "quantity" && setting.dimension === "time";
  const split = splitQuantity(value);
  const [unit, setUnit] = useState(split?.unit ?? "s");
  const savedUnit = split?.unit;
  useEffect(() => {
    if (savedUnit !== undefined) setUnit(savedUnit);
  }, [savedUnit]);
  const issues = ctx.issues.get(pointer(segments));
  const hint = hintOf(setting);
  const commitText = (text: string) => {
    if (text.trim() === "") {
      if (!required) clear(ctx, segments);
      return;
    }
    if (time && (split !== null || value === undefined))
      write(ctx, segments, `${text.trim()} ${unit}`);
    else if (setting.kind === "number") write(ctx, segments, readNumber(text));
    else write(ctx, segments, text);
  };
  const unlink = () => {
    const id = ctx.component.id;
    ctx.actions.edit(`set ${id}${pointer(segments)}`, (model) => {
      const component = componentIn(model, id);
      const current = component ? paramOf(valueAt(component.params, segments)) : null;
      const parameter = current === null ? undefined : model.parameters?.[current];
      return component && parameter !== undefined
        ? [settingEdit(component, segments, parameter.value)]
        : null;
    });
  };
  const title = label ?? labelOf(setting, required);
  return (
    <Field
      label={title}
      htmlFor={bound === null ? id : `${id}-param`}
      hint={hint}
      hintId={hintId}
      issues={issues}
    >
      <div className="value-row">
        {bound !== null ? (
          <span className="bound mono">= {bound}</span>
        ) : time && (split !== null || value === undefined) ? (
          <span className="quantity">
            <CommitInput
              id={id}
              value={split?.number ?? ""}
              onCommit={commitText}
              readOnly={ctx.readOnly}
              describedBy={hint ? hintId : undefined}
              invalid={issues !== undefined}
            />
            <select
              aria-label={`Unit of ${title}`}
              value={unit}
              disabled={ctx.readOnly}
              onChange={(event) => {
                setUnit(event.target.value);
                // The number as saved when this write is sent: one typed just before
                // (committed on leaving its box) is kept, never the number last shown.
                const chosen = event.target.value;
                // An unset value is written with this unit when its number is committed.
                write(ctx, segments, (current: unknown) => {
                  const saved = splitQuantity(current);
                  return saved ? `${saved.number} ${chosen}` : undefined;
                });
              }}
            >
              {TIME_UNITS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </span>
        ) : (
          <CommitInput
            id={id}
            value={shown(value)}
            onCommit={commitText}
            readOnly={ctx.readOnly}
            describedBy={hint ? hintId : undefined}
            invalid={issues !== undefined}
          />
        )}
      </div>
      <ParameterLink ctx={ctx} segments={segments} value={value} fieldId={id} onUnlink={unlink} />
    </Field>
  );
}

const TIME: SettingDescription = { name: "", kind: "quantity", required: true, dimension: "time" };
const PLAIN: SettingDescription = { name: "", kind: "number", required: true };

/** A distribution: its type, then the fields that type needs (spec 1 "Distributions"). */
function DistributionField({
  ctx,
  setting,
  segments,
  required,
}: {
  ctx: FieldContext;
  setting: SettingDescription;
  segments: Segments;
  required: boolean;
}) {
  const id = `field-${ctx.component.id}${pointer(segments)}`;
  const value = valueAt(ctx.component.params, segments);
  const object =
    typeof value === "object" && value !== null && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : null;
  const dist = typeof object?.dist === "string" ? object.dist : "";
  const fields = DISTRIBUTIONS[dist] ?? [];
  const choose = (next: string) => {
    if (next === "") {
      if (!required) clear(ctx, segments);
      return;
    }
    // Fields both types share are kept, as they are when the write is sent.
    write(ctx, segments, (current: unknown) => {
      const saved =
        typeof current === "object" && current !== null && !Array.isArray(current)
          ? (current as Record<string, unknown>)
          : {};
      const kept: Record<string, unknown> = { dist: next };
      for (const field of DISTRIBUTIONS[next] ?? []) {
        if (saved[field.name] !== undefined) kept[field.name] = saved[field.name];
      }
      return kept;
    });
  };
  return (
    <fieldset className="distribution">
      <legend className="field-label">{labelOf(setting, required)}</legend>
      <Field label="Distribution" htmlFor={id} issues={ctx.issues.get(pointer(segments))}>
        <select
          id={id}
          value={dist}
          disabled={ctx.readOnly}
          onChange={(event) => choose(event.target.value)}
        >
          <option value="" disabled={required}>
            {required ? "Choose a distribution" : "Not set"}
          </option>
          {dist !== "" && DISTRIBUTIONS[dist] === undefined ? (
            <option value={dist}>{dist}</option>
          ) : null}
          {Object.keys(DISTRIBUTIONS).map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </Field>
      {fields.map((field) => (
        <ValueField
          key={field.name}
          ctx={ctx}
          setting={field.time ? TIME : PLAIN}
          segments={[...segments, field.name]}
          required
          label={words(field.name)}
        />
      ))}
      {dist === "empirical" ? (
        object?.data !== undefined ? (
          <Field label="Data column">
            <span className="mono">{shown(object.data)}</span>
          </Field>
        ) : (
          <ListField ctx={ctx} segments={[...segments, "values"]} label="Values" required numbers />
        )
      ) : null}
    </fieldset>
  );
}

function ChoiceField({
  ctx,
  setting,
  segments,
  required,
  options,
}: {
  ctx: FieldContext;
  setting: SettingDescription;
  segments: Segments;
  required: boolean;
  options: string[];
}) {
  const id = `field-${ctx.component.id}${pointer(segments)}`;
  const value = valueAt(ctx.component.params, segments);
  const current = typeof value === "string" ? value : "";
  const empty =
    setting.default !== undefined
      ? `Default (${shown(setting.default)})`
      : required
        ? "Choose"
        : "None";
  return (
    <Field
      label={labelOf(setting, required)}
      htmlFor={id}
      issues={ctx.issues.get(pointer(segments))}
    >
      <select
        id={id}
        value={current}
        disabled={ctx.readOnly}
        onChange={(event) => {
          if (event.target.value === "") clear(ctx, segments);
          else write(ctx, segments, event.target.value);
        }}
      >
        <option value="" disabled={required && setting.default === undefined}>
          {empty}
        </option>
        {current !== "" && !options.includes(current) ? (
          <option value={current}>{current}</option>
        ) : null}
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </Field>
  );
}

/** A list of identifiers or values, typed with commas between them. */
function ListField({
  ctx,
  segments,
  label,
  required,
  numbers,
}: {
  ctx: FieldContext;
  segments: Segments;
  label: string;
  required: boolean;
  numbers?: boolean;
}) {
  const id = `field-${ctx.component.id}${pointer(segments)}`;
  const hintId = `${id}-hint`;
  const value = valueAt(ctx.component.params, segments);
  const text = Array.isArray(value) ? value.map(shown).join(", ") : shown(value);
  return (
    <Field
      label={required ? label : `${label} (optional)`}
      htmlFor={id}
      hint="Separate the entries with commas."
      hintId={hintId}
      issues={ctx.issues.get(pointer(segments))}
    >
      <CommitInput
        id={id}
        value={text}
        mono={!numbers}
        readOnly={ctx.readOnly}
        describedBy={hintId}
        onCommit={(typed) => {
          const items = typed
            .split(",")
            .map((item) => item.trim())
            .filter((item) => item !== "");
          if (items.length === 0 && !required) {
            clear(ctx, segments);
            return;
          }
          write(ctx, segments, numbers ? items.map(readNumber) : items);
        }}
      />
    </Field>
  );
}

/** An object keyed by the entries of another setting, such as a branch's `weights`. */
function KeyedField({
  ctx,
  setting,
  segments,
  required,
}: {
  ctx: FieldContext;
  setting: SettingDescription;
  segments: Segments;
  required: boolean;
}) {
  const keys = valueAt(ctx.component.params, [setting.keyed_by ?? ""]);
  const listed = Array.isArray(keys)
    ? keys.filter((key): key is string => typeof key === "string")
    : [];
  const values = setting.values ?? PLAIN;
  return (
    <fieldset className="group">
      <legend className="field-label">{labelOf(setting, required)}</legend>
      <FieldIssues issues={ctx.issues.get(pointer(segments))} />
      {listed.length === 0 ? (
        <p className="hint">One entry for each of {words(setting.keyed_by ?? "")}; none yet.</p>
      ) : (
        listed.map((key) => (
          <ValueField
            key={key}
            ctx={ctx}
            setting={values}
            segments={[...segments, key]}
            required
            label={key}
          />
        ))
      )}
    </fieldset>
  );
}

/** A list of objects with fixed fields, such as a schedule's `shifts`. */
function RowsField({
  ctx,
  setting,
  segments,
  required,
}: {
  ctx: FieldContext;
  setting: SettingDescription;
  segments: Segments;
  required: boolean;
}) {
  const value = valueAt(ctx.component.params, segments);
  const rows = Array.isArray(value) ? value : [];
  const name = words(setting.name);
  const add = () => {
    const id = ctx.component.id;
    ctx.actions.edit(`add to ${id}${pointer(segments)}`, (model) => {
      const component = componentIn(model, id);
      if (component === undefined) return null;
      return Array.isArray(valueAt(component.params, segments))
        ? [{ edit: "set_setting", id, path: `${pointer(segments)}/-`, value: {} }]
        : [settingEdit(component, segments, [{}])];
    });
  };
  return (
    <fieldset className="group">
      <legend className="field-label">{labelOf(setting, required)}</legend>
      <FieldIssues issues={ctx.issues.get(pointer(segments))} />
      {rows.map((_, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: rows are addressed by index in the model
        <fieldset key={index} className="row-group">
          <legend className="small">
            {name} {index + 1}
          </legend>
          {(setting.fields ?? []).map((field) => (
            <SettingField
              key={field.name}
              ctx={ctx}
              setting={field}
              segments={[...segments, index, field.name]}
            />
          ))}
          <button
            type="button"
            className="secondary small-button"
            disabled={ctx.readOnly}
            onClick={() =>
              write(ctx, segments, (current: unknown) =>
                Array.isArray(current) ? current.filter((__, other) => other !== index) : undefined,
              )
            }
          >
            Remove {name.toLowerCase()} {index + 1}
          </button>
        </fieldset>
      ))}
      <button
        type="button"
        className="secondary small-button"
        disabled={ctx.readOnly}
        onClick={add}
      >
        Add to {name.toLowerCase()}
      </button>
    </fieldset>
  );
}

/** One setting, by its kind. */
export function SettingField({
  ctx,
  setting,
  segments,
}: {
  ctx: FieldContext;
  setting: SettingDescription;
  segments: Segments;
}) {
  const required =
    segments.length > 1 ? setting.required : isRequired(setting, ctx.component.params);
  if (setting.kind === "distribution") {
    return (
      <DistributionField ctx={ctx} setting={setting} segments={segments} required={required} />
    );
  }
  if (setting.kind === "number" || setting.kind === "quantity") {
    return <ValueField ctx={ctx} setting={setting} segments={segments} required={required} />;
  }
  if (setting.kind === "identifier") {
    if (setting.many) {
      return (
        <ListField ctx={ctx} segments={segments} label={words(setting.name)} required={required} />
      );
    }
    if (setting.choices) {
      return (
        <ChoiceField
          ctx={ctx}
          setting={setting}
          segments={segments}
          required={required}
          options={setting.choices}
        />
      );
    }
    if (setting.refers_to) {
      const kinds = setting.refers_to;
      const options = components(ctx.model)
        .filter((item) => kinds.includes(item.type) && item.id !== ctx.component.id)
        .map((item) => item.id);
      return (
        <ChoiceField
          ctx={ctx}
          setting={setting}
          segments={segments}
          required={required}
          options={options}
        />
      );
    }
  }
  if (setting.kind === "object") {
    if (setting.keyed_by) {
      return <KeyedField ctx={ctx} setting={setting} segments={segments} required={required} />;
    }
    if (setting.many && setting.fields) {
      return <RowsField ctx={ctx} setting={setting} segments={segments} required={required} />;
    }
  }
  return <TextSetting ctx={ctx} setting={setting} segments={segments} required={required} />;
}

/** Any other setting: its value as text (an identifier, or JSON the form has no field for). */
function TextSetting({
  ctx,
  setting,
  segments,
  required,
}: {
  ctx: FieldContext;
  setting: SettingDescription;
  segments: Segments;
  required: boolean;
}) {
  const id = useId();
  const value = valueAt(ctx.component.params, segments);
  return (
    <Field
      label={labelOf(setting, required)}
      htmlFor={id}
      issues={ctx.issues.get(pointer(segments))}
    >
      <CommitInput
        id={id}
        value={shown(value)}
        mono
        readOnly={ctx.readOnly}
        onCommit={(text) => {
          if (text.trim() === "") {
            if (!required) clear(ctx, segments);
            return;
          }
          write(ctx, segments, text.trim());
        }}
      />
    </Field>
  );
}
