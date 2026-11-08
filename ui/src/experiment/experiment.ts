/**
 * Reading a `process` model's experiments, scenarios, objectives and constraints, and
 * building the edits of the Experiment screen (spec 1 "Experiments", "Metric names"; spec 3
 * "Model edits": `set_experiment`, `set_scenario`, `remove_scenario`, `set_path` and
 * `remove_path` on `/experiments/<n>/search`, `/objectives` and `/constraints`).
 *
 * Every plan is built from the model the session shows when it sends the write, so an
 * index into a list is the index in that model. Nothing here judges a value: text that is
 * not a number is sent as typed, and the service's issues say what is wrong with it.
 */
import type { ComponentType, Edit, Experiment, Model } from "../api/types";
import { identifier } from "../canvas/identifiers";
import { components, pointer, readNumber } from "../canvas/model";
import { hasOwn, own, record, setOwn } from "../canvas/own";
/** A plan built from the model shown: the edits, or `null` to send nothing. */
export type ModelPlan = (model: Model) => Edit[] | null;

/** The experiment fields the screen edits, and what each holds (spec 1 "Experiments"). */
export type FieldKind = "quantity" | "integer" | "number";

export interface ExperimentField {
  key: "length" | "warmup" | "replications" | "seed" | "confidence" | "record_interval";
  kind: FieldKind;
  /** The plain words of the label (`design-system.md` "Type", Plain words). */
  label: string;
  /** The technical term, shown under the field and on hover. */
  term: string;
  required: boolean;
  /** What an empty field means. */
  empty?: string;
}

export const FIELDS: readonly ExperimentField[] = [
  {
    key: "length",
    kind: "quantity",
    label: "Run length",
    term: "Length: the time each run simulates",
    required: true,
  },
  {
    key: "warmup",
    kind: "quantity",
    label: "Settling-in time",
    term: "Warm-up; less than the run length",
    required: false,
    empty: "Empty: 0 s",
  },
  {
    key: "replications",
    kind: "integer",
    label: "Repeat runs",
    term: "Replications; at least 2",
    required: false,
    empty: "Empty: 30",
  },
  {
    key: "seed",
    kind: "integer",
    label: "Seed",
    term: "Starting point of the random numbers",
    required: false,
    empty: "Empty: chosen at random",
  },
  {
    key: "confidence",
    kind: "number",
    label: "Sure of the likely range",
    term: "Confidence level, between 0 and 1",
    required: false,
    empty: "Empty: 0.95",
  },
  {
    key: "record_interval",
    kind: "quantity",
    label: "Record interval",
    term: "Time between recorded values",
    required: false,
    empty: "Empty: run length / 200",
  },
];

export function experimentsOf(model: Model): Experiment[] {
  return Array.isArray(model.experiments) ? model.experiments : [];
}

export function experimentIn(model: Model, id: string): Experiment | undefined {
  return experimentsOf(model).find((item) => item.id === id);
}

/** `/experiments/<n>`, the first experiment with that id (spec 3 "Model edits", Order). */
export function experimentPointer(model: Model, id: string): string | null {
  const index = experimentsOf(model).findIndex((item) => item.id === id);
  return index < 0 ? null : `/experiments/${index}`;
}

/**
 * A typed value as the field's kind writes it: a time as typed text (`"200 h"`), a number
 * as a JSON number when it follows spec 1's number grammar. A whole number too large for
 * the interface to hold exactly (beyond 2⁵³ − 1) is sent as typed, so it is never rounded.
 */
export function typedValue(kind: FieldKind | "quantity-parameter", text: string): unknown {
  const trimmed = text.trim();
  if (kind === "quantity" || kind === "quantity-parameter") return trimmed;
  if (/^-?[0-9]+$/.test(trimmed) && !Number.isSafeInteger(Number(trimmed))) return trimmed;
  return readNumber(trimmed);
}

/** `set_experiment` of one field, when the experiment is in the model shown. */
export function setFieldPlan(id: string, key: string, value: unknown): ModelPlan {
  return (model) => {
    if (experimentIn(model, id) === undefined) return null;
    const edit = { edit: "set_experiment", id } as Edit & Record<string, unknown>;
    setOwn(edit, key, value);
    return [edit];
  };
}

/**
 * The model without one field of an experiment: `set_experiment` sets fields and never
 * removes one (spec 3 "Model edits"), so clearing writes the whole model, as the Canvas's
 * Clearing rule does.
 */
export function clearFieldPlan(id: string, key: string): (model: Model) => Model | null {
  return (model) => {
    const found = experimentIn(model, id);
    if (found === undefined || !hasOwn(found, key)) return null;
    const copy = structuredClone(model);
    const target = experimentIn(copy, id) as Record<string, unknown>;
    delete target[key];
    return copy;
  };
}

/** `<prefix>_<n>`, `n` one more than the highest number of an id of that form. */
export function nextName(taken: readonly string[], prefix: string): string {
  const pattern = new RegExp(`^${prefix}_(\\d+)$`);
  let highest = 0;
  for (const id of taken) {
    const found = pattern.exec(id);
    if (found) highest = Math.max(highest, Number(found[1]));
  }
  return identifier(`${prefix}_${highest + 1}`, taken, prefix);
}

export interface Scenario {
  id: string;
  set: Record<string, unknown>;
}

export function scenariosOf(experiment: Experiment | undefined): Scenario[] {
  const listed = experiment?.scenarios;
  if (!Array.isArray(listed)) return [];
  return listed.filter(
    (item): item is Scenario =>
      typeof item === "object" &&
      item !== null &&
      typeof (item as Scenario).id === "string" &&
      typeof (item as Scenario).set === "object" &&
      (item as Scenario).set !== null,
  );
}

/** The parameters a scenario table shows: every parameter, then any other name a set holds. */
export function scenarioColumns(model: Model, scenarios: readonly Scenario[]): string[] {
  const names = Object.keys(model.parameters ?? {});
  for (const scenario of scenarios) {
    for (const name of Object.keys(scenario.set)) if (!names.includes(name)) names.push(name);
  }
  return names;
}

/** The kind a parameter's values are written in: a time as text, else a number. */
export function parameterKind(model: Model, name: string): FieldKind | "quantity-parameter" {
  const type = own<{ type?: unknown }>(model.parameters, name)?.type;
  return type === "quantity" ? "quantity-parameter" : type === "integer" ? "integer" : "number";
}

/**
 * `set_scenario` with one parameter's value changed, or left out when `value` is
 * `undefined` (the scenario then uses the model's value). The rest of `set` is kept.
 */
export function scenarioValuePlan(
  experimentId: string,
  scenarioId: string,
  name: string,
  value: unknown,
): ModelPlan {
  return (model) => {
    const scenario = scenariosOf(experimentIn(model, experimentId)).find(
      (item) => item.id === scenarioId,
    );
    if (scenario === undefined) return null;
    if (value === undefined && !hasOwn(scenario.set, name)) return null;
    const set = record<unknown>();
    for (const [key, held] of Object.entries(scenario.set)) {
      if (key !== name) setOwn(set, key, held);
    }
    if (value !== undefined) setOwn(set, name, value);
    return [{ edit: "set_scenario", experiment_id: experimentId, id: scenarioId, set }];
  };
}

/** A new scenario with an empty `set`, unless the experiment already has one of that id. */
export function addScenarioPlan(experimentId: string, scenarioId: string): ModelPlan {
  return (model) => {
    const experiment = experimentIn(model, experimentId);
    if (experiment === undefined) return null;
    if (scenariosOf(experiment).some((item) => item.id === scenarioId)) return null;
    return [{ edit: "set_scenario", experiment_id: experimentId, id: scenarioId, set: {} }];
  };
}

/** The metric names objectives and constraints may use (spec 1 "Metric names"). */
export function metricNames(model: Model, types: Record<string, ComponentType>): string[] {
  const names: string[] = [];
  for (const component of components(model)) {
    for (const metric of own<ComponentType>(types, component.type)?.metrics ?? []) {
      names.push(`${component.id}.${metric}`);
    }
  }
  names.push("model.wip.mean");
  return names;
}

export interface MetricObjective {
  id: unknown;
  metric: unknown;
  sense: unknown;
}

export interface MetricConstraint {
  id: unknown;
  metric: unknown;
  op: unknown;
  value: unknown;
}

export function listOf<T>(model: Model, key: "objectives" | "constraints"): T[] {
  const listed = own(model, key);
  return Array.isArray(listed) ? (listed as T[]) : [];
}

/** Appends an item to `/objectives` or `/constraints`, creating the list when absent. */
export function appendPlan(key: "objectives" | "constraints", item: unknown): ModelPlan {
  return (model) =>
    Array.isArray(own(model, key))
      ? [{ edit: "set_path", path: `/${key}/-`, value: item }]
      : [{ edit: "set_path", path: `/${key}`, value: [item] }];
}

/** Ids of the items of `/objectives` or `/constraints`, for a new one's name. */
export function idsOf(model: Model, key: "objectives" | "constraints"): string[] {
  return listOf<{ id?: unknown }>(model, key)
    .map((item) => item?.id)
    .filter((id): id is string => typeof id === "string");
}

/** `set_path` or `remove_path` at `rest` inside an experiment's `search`. */
export function searchPlan(
  experimentId: string,
  rest: readonly string[],
  value: unknown | undefined,
): ModelPlan {
  return (model) => {
    const at = experimentPointer(model, experimentId);
    const search = experimentIn(model, experimentId)?.search;
    if (at === null) return null;
    const path = `${at}/search${pointer(rest)}`;
    if (value !== undefined) return [{ edit: "set_path", path, value }];
    // Removing what is not there would be refused; nothing is sent.
    let here: unknown = search;
    for (const segment of rest) here = own(here, segment);
    return here === undefined ? null : [{ edit: "remove_path", path }];
  };
}

/** The parameters a search can vary: those with both a `min` and a `max` (spec 1). */
export function searchable(model: Model): string[] {
  return Object.entries(model.parameters ?? {})
    .filter(([, parameter]) => parameter.min !== undefined && parameter.max !== undefined)
    .map(([name]) => name);
}

/**
 * Renames objective `index`: its `id`, and in the same batch every search that names it,
 * unless another objective already has the new name (the service then reports the
 * duplicate, and no search is moved to the other objective).
 */
export function renameObjectivePlan(index: number, name: string): ModelPlan {
  return (model) => {
    const objectives = listOf<{ id?: unknown }>(model, "objectives");
    const old = objectives[index]?.id;
    if (objectives[index] === undefined || old === name) return null;
    const edits: Edit[] = [{ edit: "set_path", path: `/objectives/${index}/id`, value: name }];
    if (typeof old !== "string" || objectives.some((item) => item?.id === name)) return edits;
    experimentsOf(model).forEach((experiment, at) => {
      if (own<{ objective?: unknown }>(experiment, "search")?.objective === old) {
        edits.push({ edit: "set_path", path: `/experiments/${at}/search/objective`, value: name });
      }
    });
    return edits;
  };
}
