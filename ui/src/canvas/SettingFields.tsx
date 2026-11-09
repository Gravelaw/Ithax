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
import {
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import type { ApiResult } from "../api/client";
import type { Component, Issue, Model, SettingDescription } from "../api/types";
import { lock, useBusy, useDraft, useRevision } from "./busy";
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
  words,
} from "./model";
import { hasOwn, own } from "./own";
import { clearPlan, componentIn, type EditPlan, settingLabel, settingPlan } from "./plans";
import { type ParameterKind, tryChangeEdits } from "./tryChange";

export type { EditPlan } from "./plans";

/** What "Try a change" needs: the experiment chosen in the top bar, a write and a notice. */
export interface TryChangeActions {
  /** The experiment the option is added to; `null` when the model has none. */
  experiment: string | null;
  send(label: string, edits: EditPlan): Promise<ApiResult<unknown> | null>;
  say(text: string): void;
}

/** What a field does to the model: one batch of edits, or a whole model (clearing). */
export interface FieldActions {
  edit(label: string, edits: EditPlan): void;
  /** A whole model built from the model shown; `null` sends nothing. */
  replace(label: string, build: (model: Model) => Model | null): void;
  /** "Try a change" beside a number or time; absent where it is not offered. */
  tryChange?: TryChangeActions;
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
  label,
  placeholder,
}: {
  id: string;
  value: string;
  /** Takes the text; `false` means nothing is sent for it, and the box shows the saved value. */
  onCommit: (text: string) => unknown;
  readOnly: boolean;
  mono?: boolean;
  describedBy?: string;
  invalid?: boolean;
  /** Its accessible name, where no `<label>` names it (a table cell). */
  label?: string;
  /** Shown while the box is empty, such as the value used when it is left empty. */
  placeholder?: string;
}) {
  const busy = useBusy();
  const revision = useRevision();
  const [text, setText] = useState(value);
  // A draft never outlives a change of the model shown: whenever the model changes (an
  // answer, a reload, another client's revision) the box shows the saved value again
  // (review of PR #45).
  // The text this box has just sent, so leaving the box while its write is answered is not
  // a second commit; forgotten when the answer comes.
  const sent = useRef<string | null>(null);
  // Compared while rendering, not in an effect: an effect run late (after the first
  // keystroke) would throw that keystroke away.
  const [shownFor, setShownFor] = useState({ value, revision });
  if (shownFor.value !== value || shownFor.revision !== revision) {
    setShownFor({ value, revision });
    setText(value);
  }
  useEffect(() => {
    if (!busy) sent.current = null;
  }, [busy]);
  const commit = () => {
    if (text === value || text === sent.current) return;
    // While a write awaits its answer the change is refused (the canvas says so) and the
    // box shows the saved value; nothing is kept to be sent later.
    if (busy) setText(value);
    else sent.current = text;
    if (onCommit(text) === false) {
      sent.current = null;
      setText(value);
    }
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    } else if (event.key === "Escape") {
      setText(value);
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
      aria-label={label}
      placeholder={placeholder}
      aria-invalid={invalid ? true : undefined}
      onChange={(event) => setText(event.target.value)}
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
 * Sets the value at `segments` (a `set_setting` whose path depends on what exists). A
 * function value is given the value there now, and `undefined` sends nothing.
 */
function write(
  ctx: FieldContext,
  segments: Segments,
  value: unknown | ((current: unknown) => unknown),
): void {
  ctx.actions.edit(
    settingLabel(ctx.component.id, segments),
    settingPlan(ctx.component.id, segments, value),
  );
}

/** Clears the value at `segments`, if the model holds one. */
function clear(ctx: FieldContext, segments: Segments): void {
  const id = ctx.component.id;
  ctx.actions.replace(`clear ${id}${pointer(segments)}`, clearPlan(id, segments));
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
  const busy = useBusy();
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
          {...lock(ctx.readOnly, busy)}
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
          {...lock(ctx.readOnly, busy)}
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
  const busy = useBusy();
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
      if (component === undefined) return null;
      const current = paramOf(valueAt(component.params, segments));
      const parameter =
        current === null ? undefined : own<{ value: unknown }>(model.parameters, current);
      return parameter !== undefined ? [settingEdit(component, segments, parameter.value)] : null;
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
              {...lock(ctx.readOnly, busy)}
              onChange={(event) => {
                const chosen = event.target.value;
                // While a write awaits its answer the change is refused (the write says
                // so), and the unit shown stays the saved one.
                if (!busy) setUnit(chosen);
                // A unit for an unset value is used when its number is committed.
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
      <TryChange
        ctx={ctx}
        segments={segments}
        value={value}
        name={title}
        kind={time ? "quantity" : setting.integer ? "integer" : "number"}
      />
    </Field>
  );
}

/**
 * "Try a change" (`canvas-interactions.md` "Trying a change"): a small form asking the value
 * to try and a name for the option; adding it makes the field a parameter and adds a
 * scenario on the experiment chosen in the top bar, in one batch (`tryChange.ts`). The form
 * is a draft: it closes whenever the model shown changes.
 */
function TryChange({
  ctx,
  segments,
  value,
  name,
  kind,
}: {
  ctx: FieldContext;
  segments: Segments;
  value: unknown;
  name: string;
  kind: ParameterKind;
}) {
  const busy = useBusy();
  const base = useId();
  const actions = ctx.actions.tryChange;
  const bound = paramOf(value);
  const current =
    bound === null ? value : own<{ value?: unknown }>(ctx.model.parameters, bound)?.value;
  const [open, setOpen] = useDraft(false);
  const [tried, setTried] = useDraft<string | null>(null);
  const [option, setOption] = useDraft("");
  if (actions === undefined || value === undefined) return null;
  if (!open) {
    return (
      <button
        type="button"
        className="link try-change"
        aria-label={`Try a change to ${name}`}
        disabled={ctx.readOnly}
        onClick={() => setOpen(true)}
      >
        Try a change
      </button>
    );
  }
  const experiment = actions.experiment;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (experiment === null) {
      actions.say(
        "Add an experiment on the Experiment screen first: the option is one of its scenarios.",
      );
      return;
    }
    const plan = {
      component: ctx.component.id,
      segments,
      kind,
      experiment,
      option: option.trim() === "" ? "option" : option,
      tried: tried ?? shown(current),
    };
    void actions
      .send(`try a change to ${ctx.component.id}${pointer(segments)}`, (model) =>
        tryChangeEdits(model, plan),
      )
      .then((result) => {
        if (result?.kind === "ok") {
          actions.say(
            `Added an option to experiment ${experiment}. Compare it on the Experiment screen.`,
          );
        }
      });
  };
  return (
    <form className="try-form" aria-labelledby={`${base}-title`} onSubmit={submit}>
      <p className="subheading" id={`${base}-title`}>
        Try a change to {name}
      </p>
      <label htmlFor={`${base}-value`} className="field-label">
        What value do you want to try?
      </label>
      <input
        id={`${base}-value`}
        value={tried ?? shown(current)}
        readOnly={ctx.readOnly}
        onChange={(event) => setTried(event.target.value)}
      />
      <label htmlFor={`${base}-name`} className="field-label">
        Name for the option
      </label>
      <input
        id={`${base}-name`}
        value={option}
        placeholder="Faster coffee machine"
        readOnly={ctx.readOnly}
        onChange={(event) => setOption(event.target.value)}
      />
      <p className="hint">
        {experiment === null
          ? "The model has no experiment to add the option to."
          : `Added as a scenario of experiment ${experiment}, beside the current model.`}
      </p>
      <div className="try-actions">
        <button type="submit" className="secondary small-button" {...lock(ctx.readOnly, busy)}>
          Add the option
        </button>
        <button type="button" className="link" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
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
  const busy = useBusy();
  const id = `field-${ctx.component.id}${pointer(segments)}`;
  const value = valueAt(ctx.component.params, segments);
  const object =
    typeof value === "object" && value !== null && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : null;
  const dist = typeof object?.dist === "string" ? object.dist : "";
  const fields = own<(typeof DISTRIBUTIONS)[string]>(DISTRIBUTIONS, dist) ?? [];
  const choose = (next: string) => {
    if (next === "") {
      if (!required) clear(ctx, segments);
      return;
    }
    // Fields both types share are kept.
    write(ctx, segments, (current: unknown) => {
      const saved =
        typeof current === "object" && current !== null && !Array.isArray(current)
          ? (current as Record<string, unknown>)
          : {};
      const kept: Record<string, unknown> = { dist: next };
      for (const field of own<(typeof DISTRIBUTIONS)[string]>(DISTRIBUTIONS, next) ?? []) {
        const was = own(saved, field.name);
        if (was !== undefined) kept[field.name] = was;
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
          {...lock(ctx.readOnly, busy)}
          onChange={(event) => choose(event.target.value)}
        >
          <option value="" disabled={required}>
            {required ? "Choose a distribution" : "Not set"}
          </option>
          {dist !== "" && !hasOwn(DISTRIBUTIONS, dist) ? (
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
  const busy = useBusy();
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
        {...lock(ctx.readOnly, busy)}
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
  const busy = useBusy();
  const value = valueAt(ctx.component.params, segments);
  const rows = Array.isArray(value) ? value : [];
  const name = words(setting.name);
  const add = () => {
    const id = ctx.component.id;
    ctx.actions.edit(`add to ${id}${pointer(segments)}`, (model) => {
      const component = componentIn(model, id);
      if (component === undefined) return null;
      return Array.isArray(valueAt(component.params, segments))
        ? [{ edit: "set_setting", id: component.id, path: `${pointer(segments)}/-`, value: {} }]
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
            {...lock(ctx.readOnly, busy)}
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
        {...lock(ctx.readOnly, busy)}
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
