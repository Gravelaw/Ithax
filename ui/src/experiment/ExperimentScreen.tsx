/**
 * The Experiment screen (spec 3 "Screens" 4; `docs/design/flows.md` B9;
 * `docs/design/wireframes/04-experiment.svg`): an experiment's run length, settling-in time,
 * repeat runs, seed, how sure the likely range is and record interval (`set_experiment`),
 * its scenarios (`set_scenario`, `remove_scenario`), the model's objectives and constraints
 * (`set_path`, `remove_path` on `/objectives` and `/constraints`) and the experiment's
 * search (`set_path`, `remove_path` on `/experiments/<n>/search`). Model edits only, through
 * the same session and rules as the Canvas (`ModelFrame.tsx`). An `optimization` model has
 * no experiments, so the screen says so and points to the Canvas.
 *
 * Words are plain (`design-system.md` "Type"): each field's technical term is under it and
 * in its label's hover text. A value is written as typed, a time as spec 1's quantity
 * (`"200 h"`); the service's issues say what is wrong with one.
 */
import { MinusCircleIcon, PlusIcon } from "@phosphor-icons/react";
import { type FormEvent, useId, useState } from "react";
import type { ApiClient } from "../api/client";
import type { ComponentType, Experiment, Issue, Model, Project } from "../api/types";
import type { Route } from "../app/router";
import { lock, useBusy } from "../canvas/busy";
import { ModelScreen, type ModelWrites, useDraft, useSchema } from "../canvas/ModelFrame";
import { shown, splitQuantity, TIME_UNITS } from "../canvas/model";
import { own } from "../canvas/own";
import { CommitInput, FieldIssues } from "../canvas/SettingFields";
import {
  addScenarioPlan,
  appendPlan,
  clearFieldPlan,
  type ExperimentField,
  experimentPointer,
  experimentsOf,
  FIELDS,
  idsOf,
  listOf,
  type MetricConstraint,
  type MetricObjective,
  metricNames,
  nextName,
  parameterKind,
  renameObjectivePlan,
  type Scenario,
  scenarioColumns,
  scenariosOf,
  scenarioValuePlan,
  searchable,
  searchPlan,
  setFieldPlan,
  typedValue,
} from "./experiment";

/** The issues at `path` or inside it. */
export function issuesAt(issues: readonly Issue[], path: string): Issue[] {
  return issues.filter((issue) => issue.path === path || issue.path.startsWith(`${path}/`));
}

export function ExperimentScreen({
  client,
  project,
  toolbar,
  onGo,
}: {
  client: ApiClient;
  project: Project | null;
  toolbar: HTMLElement | null;
  onGo: (route: Route) => void;
}) {
  const schema = useSchema(client);
  const types = schema?.kind === "ok" ? (schema.data["x-component-types"] ?? {}) : {};
  return (
    <ModelScreen client={client} project={project} toolbar={toolbar} heading="Experiment">
      {({ state, model, writes }) =>
        model.domain === "optimization" ? (
          <section className="screen-body plan-experiment" aria-labelledby="experiment-heading">
            <h2 className="title" id="experiment-heading">
              Experiment
            </h2>
            <p>
              A plan has no experiments: it is solved once, so it has no run length, repeat runs or
              scenarios. Its goal and limits are set on the Canvas.
            </p>
            <button
              type="button"
              className="secondary"
              onClick={() => project && onGo({ screen: "canvas", projectId: project.id })}
            >
              Go to the canvas
            </button>
          </section>
        ) : (
          <Experiments
            model={model}
            issues={state.issues}
            readOnly={state.failing}
            writes={writes}
            types={types}
          />
        )
      }
    </ModelScreen>
  );
}

interface Parts {
  model: Model;
  issues: Issue[];
  readOnly: boolean;
  writes: ModelWrites;
}

function Experiments({ types, ...parts }: Parts & { types: Record<string, ComponentType> }) {
  const { model, writes, readOnly } = parts;
  const busy = useBusy();
  const experiments = experimentsOf(model);
  const [chosen, setChosen] = useState<string | null>(null);
  const experiment =
    experiments.find((item) => item.id === chosen) ??
    experiments.find((item) => item.id === "base") ??
    experiments[0];

  return (
    <div className="screen-body experiment-screen">
      <nav className="experiment-list" aria-labelledby="experiments-heading" data-region="list">
        <h2 className="heading" id="experiments-heading">
          Experiments
        </h2>
        <ul>
          {experiments.map((item, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: two experiments may share an id until the service reports it
            <li key={`${item.id}-${index}`}>
              <button
                type="button"
                className="list-item mono"
                aria-current={item === experiment ? "true" : undefined}
                onClick={() => setChosen(item.id)}
              >
                {item.id}
              </button>
            </li>
          ))}
        </ul>
        <AddForm
          label="New experiment id"
          button="Add experiment"
          readOnly={readOnly}
          onAdd={(id) => {
            void writes
              .edit(`add experiment ${id}`, (current) =>
                experimentsOf(current).some((item) => item.id === id)
                  ? null
                  : [{ edit: "set_experiment", id }],
              )
              .then((result) => {
                if (result?.kind === "ok") setChosen(id);
              });
          }}
        />
        {experiment !== undefined ? (
          <button
            type="button"
            className="secondary small-button"
            {...lock(readOnly, busy)}
            onClick={() =>
              void writes.edit(`remove experiment ${experiment.id}`, [
                { edit: "remove_experiment", id: experiment.id },
              ])
            }
          >
            <MinusCircleIcon aria-hidden="true" size={14} />
            Remove experiment {experiment.id}
          </button>
        ) : null}
      </nav>
      {experiment === undefined ? (
        <section className="experiment-main">
          <p className="muted">No experiments yet. Add one to set how the model is run.</p>
        </section>
      ) : (
        <ExperimentForm {...parts} experiment={experiment} />
      )}
      <Optimization {...parts} experiment={experiment} types={types} />
    </div>
  );
}

/** A box and a button that adds something by the typed id; the draft goes with the model. */
function AddForm({
  label,
  button,
  readOnly,
  onAdd,
}: {
  label: string;
  button: string;
  readOnly: boolean;
  onAdd: (id: string) => void;
}) {
  const busy = useBusy();
  const id = useId();
  const [text, setText] = useDraft("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const typed = text.trim();
    setText("");
    if (typed !== "") onAdd(typed);
  };
  return (
    <form className="add-form" onSubmit={submit}>
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      <div className="add-row">
        <input
          id={id}
          className="mono"
          value={text}
          readOnly={readOnly}
          onChange={(event) => setText(event.target.value)}
        />
        <button type="submit" className="secondary" {...lock(readOnly, busy)}>
          <PlusIcon aria-hidden="true" size={14} />
          {button}
        </button>
      </div>
    </form>
  );
}

function ExperimentForm({
  model,
  issues,
  readOnly,
  writes,
  experiment,
}: Parts & {
  experiment: Experiment;
}) {
  const at = experimentPointer(model, experiment.id) ?? "";
  const scenarios = scenariosOf(experiment);
  const shownHere = [
    ...FIELDS.map((field) => `${at}/${field.key}`),
    `${at}/scenarios`,
    `${at}/search`,
  ];
  const other = issuesAt(issues, at).filter(
    (issue) => !shownHere.some((path) => issue.path === path || issue.path.startsWith(`${path}/`)),
  );
  return (
    <section className="experiment-main" aria-labelledby="experiment-id-heading">
      <h2 className="title mono" id="experiment-id-heading">
        {experiment.id}
      </h2>
      <FieldIssues issues={other} />
      <h3 className="heading">Run</h3>
      <div className="experiment-fields">
        {FIELDS.map((field) => (
          <ExperimentFieldInput
            key={field.key}
            field={field}
            experiment={experiment}
            issues={issuesAt(issues, `${at}/${field.key}`)}
            readOnly={readOnly}
            writes={writes}
          />
        ))}
      </div>
      <Scenarios
        model={model}
        issues={issuesAt(issues, `${at}/scenarios`)}
        readOnly={readOnly}
        writes={writes}
        experiment={experiment}
        scenarios={scenarios}
      />
    </section>
  );
}

function ExperimentFieldInput({
  field,
  experiment,
  issues,
  readOnly,
  writes,
}: {
  field: ExperimentField;
  experiment: Experiment;
  issues: Issue[];
  readOnly: boolean;
  writes: ModelWrites;
}) {
  const id = `experiment-${field.key}`;
  const hintId = `${id}-hint`;
  const value = own(experiment, field.key);
  const label = `set ${field.key} of experiment ${experiment.id}`;
  const set = (typed: unknown) =>
    void writes.edit(label, setFieldPlan(experiment.id, field.key, typed));
  const clear = () => {
    if (!field.required) {
      void writes.replace(
        `clear ${field.key} of experiment ${experiment.id}`,
        clearFieldPlan(experiment.id, field.key),
      );
    }
  };
  return (
    <div className="panel-field">
      <label htmlFor={id} className="field-label" title={field.term}>
        {field.label}
      </label>
      {field.kind === "quantity" ? (
        <QuantityInput
          id={id}
          label={field.label}
          value={value}
          describedBy={hintId}
          invalid={issues.length > 0}
          readOnly={readOnly}
          onSet={set}
          onClear={clear}
        />
      ) : (
        <CommitInput
          id={id}
          value={shown(value)}
          readOnly={readOnly}
          describedBy={hintId}
          invalid={issues.length > 0}
          onCommit={(text) => (text.trim() === "" ? clear() : set(typedValue(field.kind, text)))}
        />
      )}
      <p className="hint" id={hintId}>
        {field.term}
        {field.empty ? `. ${field.empty}` : ""}
      </p>
      <FieldIssues issues={issues} />
    </div>
  );
}

/**
 * A time: the number and a unit picker, written together as spec 1's quantity (`"200 h"`).
 * Choosing a unit rewrites a saved value in it; for an empty field the unit is kept until
 * the number is committed or the model changes. A saved value of another form is shown and
 * written as text.
 */
function QuantityInput({
  id,
  label,
  value,
  describedBy,
  invalid,
  readOnly,
  onSet,
  onClear,
}: {
  id: string;
  label: string;
  value: unknown;
  describedBy: string;
  invalid: boolean;
  readOnly: boolean;
  onSet: (value: string) => void;
  onClear: () => void;
}) {
  const busy = useBusy();
  const split = splitQuantity(value);
  const [draftUnit, setDraftUnit] = useDraft("s");
  const unit = split?.unit ?? draftUnit;
  if (value !== undefined && split === null) {
    return (
      <CommitInput
        id={id}
        value={shown(value)}
        readOnly={readOnly}
        describedBy={describedBy}
        invalid={invalid}
        onCommit={(text) => (text.trim() === "" ? onClear() : onSet(text.trim()))}
      />
    );
  }
  return (
    <span className="quantity">
      <CommitInput
        id={id}
        value={split?.number ?? ""}
        readOnly={readOnly}
        describedBy={describedBy}
        invalid={invalid}
        onCommit={(text) => (text.trim() === "" ? onClear() : onSet(`${text.trim()} ${unit}`))}
      />
      <select
        aria-label={`Unit of ${label}`}
        value={unit}
        {...lock(readOnly, busy)}
        onChange={(event) => {
          const chosen = event.target.value;
          if (split !== null) onSet(`${split.number} ${chosen}`);
          else setDraftUnit(chosen);
        }}
      >
        {TIME_UNITS.includes(unit as (typeof TIME_UNITS)[number]) ? null : (
          <option value={unit}>{unit}</option>
        )}
        {TIME_UNITS.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
    </span>
  );
}

function Scenarios({
  model,
  issues,
  readOnly,
  writes,
  experiment,
  scenarios,
}: Parts & { experiment: Experiment; scenarios: Scenario[] }) {
  const busy = useBusy();
  const columns = scenarioColumns(model, scenarios);
  return (
    <section className="experiment-section" aria-labelledby="scenarios-heading">
      <h3 className="heading" id="scenarios-heading">
        Scenarios
      </h3>
      {scenarios.length === 0 ? (
        <p className="muted">
          No scenarios: the experiment runs the model as written (the scenario{" "}
          <span className="mono">default</span>).
        </p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Scenario</th>
                {columns.map((name) => (
                  <th key={name} scope="col" className="mono">
                    {name}
                  </th>
                ))}
                <th scope="col">
                  <span className="visually-hidden">Remove</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {scenarios.map((scenario, index) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: two scenarios may share an id until the service reports it
                <tr key={`${scenario.id}-${index}`}>
                  <th scope="row" className="mono">
                    {scenario.id}
                  </th>
                  {columns.map((name) => (
                    <td key={name}>
                      <CommitInput
                        id={`scenario-${index}-${name}`}
                        label={`${name} in ${scenario.id}`}
                        value={shown(own(scenario.set, name))}
                        placeholder={shown(own<{ value?: unknown }>(model.parameters, name)?.value)}
                        readOnly={readOnly}
                        onCommit={(text) =>
                          void writes.edit(
                            `set ${name} in scenario ${scenario.id}`,
                            scenarioValuePlan(
                              experiment.id,
                              scenario.id,
                              name,
                              text.trim() === ""
                                ? undefined
                                : typedValue(parameterKind(model, name), text),
                            ),
                          )
                        }
                      />
                    </td>
                  ))}
                  <td>
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={`Remove scenario ${scenario.id}`}
                      title={`Remove scenario ${scenario.id}`}
                      {...lock(readOnly, busy)}
                      onClick={() =>
                        void writes.edit(`remove scenario ${scenario.id}`, [
                          {
                            edit: "remove_scenario",
                            experiment_id: experiment.id,
                            id: scenario.id,
                          },
                        ])
                      }
                    >
                      <MinusCircleIcon aria-hidden="true" size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint">One column per parameter; an empty cell uses its value.</p>
        </div>
      )}
      <FieldIssues issues={issues} />
      <AddForm
        label="New scenario id"
        button="Add scenario"
        readOnly={readOnly}
        onAdd={(id) => {
          if (scenarios.some((item) => item.id === id)) {
            writes.say(`The experiment already has a scenario ${id}.`);
            return;
          }
          void writes.edit(`add scenario ${id}`, addScenarioPlan(experiment.id, id));
        }}
      />
    </section>
  );
}

const SENSES = [
  ["minimize", "Make it smaller (minimize)"],
  ["maximize", "Make it larger (maximize)"],
] as const;

const OPS = [
  ["<=", "at most (≤)"],
  [">=", "at least (≥)"],
] as const;

/** A picker whose saved value it does not list still shows that value. */
function Choice({
  label,
  value,
  options,
  readOnly,
  onChoose,
  mono,
}: {
  label: string;
  value: unknown;
  options: readonly (readonly [string, string])[];
  readOnly: boolean;
  onChoose: (value: string) => void;
  mono?: boolean;
}) {
  const busy = useBusy();
  const current = typeof value === "string" ? value : shown(value);
  return (
    <select
      aria-label={label}
      className={mono ? "mono" : undefined}
      value={current}
      {...lock(readOnly, busy)}
      onChange={(event) => onChoose(event.target.value)}
    >
      {options.some(([option]) => option === current) ? null : (
        <option value={current}>{current === "" ? "Choose" : current}</option>
      )}
      {options.map(([option, words]) => (
        <option key={option} value={option}>
          {words}
        </option>
      ))}
    </select>
  );
}

function Optimization({
  model,
  issues,
  readOnly,
  writes,
  experiment,
  types,
}: Parts & { experiment: Experiment | undefined; types: Record<string, ComponentType> }) {
  const busy = useBusy();
  const metrics = metricNames(model, types).map((name) => [name, name] as const);
  const objectives = listOf<MetricObjective>(model, "objectives");
  const constraints = listOf<MetricConstraint>(model, "constraints");
  const path = (key: string, index: number, field: string) => `/${key}/${index}/${field}`;
  const setAt = (label: string, at: string, value: unknown) =>
    void writes.edit(label, [{ edit: "set_path", path: at, value }]);
  return (
    <section className="experiment-optimization" aria-labelledby="optimization-heading">
      <h2 className="heading" id="optimization-heading">
        Optimization
      </h2>
      <h3 className="subheading" id="objectives-heading">
        Objectives
      </h3>
      <FieldIssues issues={issues.filter((issue) => issue.path === "/objectives")} />
      {objectives.length === 0 ? <p className="muted">No objectives.</p> : null}
      <ul className="rows" aria-labelledby="objectives-heading">
        {objectives.map((item, index) => {
          const name = shown(item?.id);
          return (
            // biome-ignore lint/suspicious/noArrayIndexKey: rows are addressed by index in the model
            <li key={index} className="row">
              <CommitInput
                id={`objective-${index}-id`}
                label={`Name of objective ${index + 1}`}
                value={name}
                mono
                readOnly={readOnly}
                onCommit={(text) =>
                  void writes.edit(
                    `rename objective ${name}`,
                    renameObjectivePlan(index, text.trim()),
                  )
                }
              />
              <Choice
                label={`Metric of objective ${name}`}
                value={item?.metric}
                options={metrics}
                mono
                readOnly={readOnly}
                onChoose={(value) =>
                  setAt(`set metric of ${name}`, path("objectives", index, "metric"), value)
                }
              />
              <Choice
                label={`Goal of objective ${name}`}
                value={item?.sense}
                options={SENSES}
                readOnly={readOnly}
                onChoose={(value) =>
                  setAt(`set goal of ${name}`, path("objectives", index, "sense"), value)
                }
              />
              <button
                type="button"
                className="icon-button"
                aria-label={`Remove objective ${name}`}
                title={`Remove objective ${name}`}
                {...lock(readOnly, busy)}
                onClick={() =>
                  void writes.edit(`remove objective ${name}`, [
                    { edit: "remove_path", path: `/objectives/${index}` },
                  ])
                }
              >
                <MinusCircleIcon aria-hidden="true" size={16} />
              </button>
              <FieldIssues issues={issuesAt(issues, `/objectives/${index}`)} />
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        className="secondary small-button"
        {...lock(readOnly, busy)}
        onClick={() =>
          void writes.edit("add an objective", (current) =>
            appendPlan("objectives", {
              id: nextName(idsOf(current, "objectives"), "objective"),
              metric: metrics[0]?.[0] ?? "",
              sense: "minimize",
            })(current),
          )
        }
      >
        <PlusIcon aria-hidden="true" size={14} />
        Add objective
      </button>

      <h3 className="subheading" id="constraints-heading">
        Constraints
      </h3>
      <FieldIssues issues={issues.filter((issue) => issue.path === "/constraints")} />
      {constraints.length === 0 ? <p className="muted">No constraints.</p> : null}
      <ul className="rows" aria-labelledby="constraints-heading">
        {constraints.map((item, index) => {
          const name = shown(item?.id);
          return (
            // biome-ignore lint/suspicious/noArrayIndexKey: rows are addressed by index in the model
            <li key={index} className="row">
              <CommitInput
                id={`constraint-${index}-id`}
                label={`Name of constraint ${index + 1}`}
                value={name}
                mono
                readOnly={readOnly}
                onCommit={(text) =>
                  setAt(`rename constraint ${name}`, path("constraints", index, "id"), text.trim())
                }
              />
              <Choice
                label={`Metric of constraint ${name}`}
                value={item?.metric}
                options={metrics}
                mono
                readOnly={readOnly}
                onChoose={(value) =>
                  setAt(`set metric of ${name}`, path("constraints", index, "metric"), value)
                }
              />
              <Choice
                label={`Must be, for constraint ${name}`}
                value={item?.op}
                options={OPS}
                readOnly={readOnly}
                onChoose={(value) =>
                  setAt(`set the limit of ${name}`, path("constraints", index, "op"), value)
                }
              />
              <CommitInput
                id={`constraint-${index}-value`}
                label={`Value of constraint ${name}`}
                value={shown(item?.value)}
                readOnly={readOnly}
                onCommit={(text) =>
                  setAt(
                    `set the value of ${name}`,
                    path("constraints", index, "value"),
                    /^\S+ (s|min|h|d)$/.test(text.trim())
                      ? text.trim()
                      : typedValue("number", text),
                  )
                }
              />
              <button
                type="button"
                className="icon-button"
                aria-label={`Remove constraint ${name}`}
                title={`Remove constraint ${name}`}
                {...lock(readOnly, busy)}
                onClick={() =>
                  void writes.edit(`remove constraint ${name}`, [
                    { edit: "remove_path", path: `/constraints/${index}` },
                  ])
                }
              >
                <MinusCircleIcon aria-hidden="true" size={16} />
              </button>
              <FieldIssues issues={issuesAt(issues, `/constraints/${index}`)} />
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        className="secondary small-button"
        {...lock(readOnly, busy)}
        onClick={() =>
          void writes.edit("add a constraint", (current) =>
            appendPlan("constraints", {
              id: nextName(idsOf(current, "constraints"), "constraint"),
              metric: metrics[0]?.[0] ?? "",
              op: "<=",
              value: 0,
            })(current),
          )
        }
      >
        <PlusIcon aria-hidden="true" size={14} />
        Add constraint
      </button>
      <p className="hint">Metrics are those spec 2 defines for each block (E174 otherwise).</p>
      {experiment !== undefined ? (
        <Search
          model={model}
          issues={issues}
          readOnly={readOnly}
          writes={writes}
          experiment={experiment}
        />
      ) : null}
    </section>
  );
}

function Search({
  model,
  issues,
  readOnly,
  writes,
  experiment,
}: Parts & {
  experiment: Experiment;
}) {
  const busy = useBusy();
  const at = experimentPointer(model, experiment.id) ?? "";
  const search = own<Record<string, unknown>>(experiment, "search");
  const on = search !== undefined;
  const objectives = idsOf(model, "objectives");
  const variables = Array.isArray(search?.variables)
    ? (search.variables as unknown[]).filter((item): item is string => typeof item === "string")
    : [];
  const candidates = [...searchable(model)];
  for (const name of variables) if (!candidates.includes(name)) candidates.push(name);
  const set = (label: string, rest: string[], value: unknown) =>
    void writes.edit(label, searchPlan(experiment.id, rest, value));
  const number = (key: "budget" | "replications", label: string, term: string) => {
    const id = `search-${key}`;
    return (
      <div className="panel-field">
        <label htmlFor={id} className="field-label" title={term}>
          {label}
        </label>
        <CommitInput
          id={id}
          value={shown(search?.[key])}
          readOnly={readOnly}
          describedBy={`${id}-hint`}
          onCommit={(text) =>
            set(
              `set the search's ${key}`,
              [key],
              text.trim() === "" ? undefined : typedValue("integer", text),
            )
          }
        />
        <p className="hint" id={`${id}-hint`}>
          {term}
        </p>
        <FieldIssues issues={issuesAt(issues, `${at}/search/${key}`)} />
      </div>
    );
  };
  return (
    <section className="experiment-section" aria-labelledby="search-heading">
      <h3 className="subheading" id="search-heading">
        Search (simulation-based optimization)
      </h3>
      <label className="tick">
        <input
          type="checkbox"
          checked={on}
          {...lock(readOnly, busy)}
          onChange={(event) =>
            set(
              event.target.checked ? "turn the search on" : "turn the search off",
              [],
              event.target.checked ? { objective: objectives[0] ?? "" } : undefined,
            )
          }
        />
        Search for the best parameter values
      </label>
      {on ? (
        <>
          <FieldIssues
            issues={issues.filter(
              (issue) =>
                issue.path === `${at}/search` ||
                issue.path === `${at}/search/objective` ||
                issue.path.startsWith(`${at}/search/variables`),
            )}
          />
          <div className="experiment-fields">
            <div className="panel-field">
              <span className="field-label">Objective</span>
              <Choice
                label="Objective of the search"
                value={search?.objective}
                options={objectives.map((id) => [id, id] as const)}
                mono
                readOnly={readOnly}
                onChoose={(value) => set("set the search's objective", ["objective"], value)}
              />
            </div>
            {number("budget", "Budget", "Candidates tried. Empty: 50")}
            {number("replications", "Repeat runs each", "Replications per candidate. Empty: 10")}
          </div>
          <fieldset className="group">
            <legend className="field-label">Parameters searched</legend>
            {candidates.length === 0 ? (
              <p className="hint">No parameter has both a min and a max.</p>
            ) : null}
            {candidates.map((name) => {
              const parameter = own<{ min?: unknown; max?: unknown }>(model.parameters, name);
              return (
                <label key={name} className="tick">
                  <input
                    type="checkbox"
                    checked={variables.includes(name)}
                    {...lock(readOnly, busy)}
                    onChange={(event) => {
                      const ticked = event.target.checked;
                      void writes.edit(`choose the parameters searched`, (current) => {
                        const now = own<{ variables?: unknown }>(
                          current.experiments?.find((item) => item.id === experiment.id),
                          "search",
                        )?.variables;
                        const listed = Array.isArray(now)
                          ? now.filter((item): item is string => typeof item === "string")
                          : [];
                        const next = ticked
                          ? [...listed.filter((item) => item !== name), name]
                          : listed.filter((item) => item !== name);
                        return searchPlan(
                          experiment.id,
                          ["variables"],
                          next.length === 0 ? undefined : next,
                        )(current);
                      });
                    }}
                  />
                  <span className="mono">{name}</span>
                  {parameter
                    ? ` from ${shown(parameter.min)} to ${shown(parameter.max)}`
                    : " (not a parameter with a min and a max)"}
                </label>
              );
            })}
            <p className="hint">None ticked: every parameter with both a min and a max.</p>
          </fieldset>
          <p className="hint">
            The best candidates are run again with the experiment's{" "}
            {shown(experiment.replications ?? 30)} repeat runs before the result is reported.
          </p>
        </>
      ) : null}
    </section>
  );
}
