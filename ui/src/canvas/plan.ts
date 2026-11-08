/**
 * An `optimization` model as the Canvas's Table and Diagram views read and change it
 * (spec 3 "Canvas behaviour", Optimization models; spec 2 "Mathematical optimization in the
 * model file"; `docs/design/canvas-interactions.md` "The model and the canvas").
 *
 * In the interface's words the variables are decisions, the objective the goal and the
 * constraints limits. Every change is one batch of `set_path` and `remove_path` edits on
 * `/variables`, `/objective` and `/constraints`, built from the model shown; `null` sends
 * nothing. The interface checks nothing itself: a number is sent as a number when it
 * follows spec 1's number grammar and as typed otherwise, so the service says what is wrong.
 */
import type { Edit, LinearConstraint, Model, Variable } from "../api/types";
import { pointer, readNumber, shown } from "./model";
import { hasOwn, own } from "./own";
import { sameValue } from "./review";

type Plain = Record<string, unknown>;

function isPlain(value: unknown): value is Plain {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export interface Row<T> {
  /** The entry's place in its list, which its pointers use. */
  index: number;
  item: T;
}

function rows<T>(list: unknown): Row<T>[] {
  if (!Array.isArray(list)) return [];
  return list.flatMap((item, index) => (isPlain(item) ? [{ index, item: item as T }] : []));
}

export function variablesOf(model: Model): Row<Variable>[] {
  return rows<Variable>(model.variables);
}

export function constraintsOf(model: Model): Row<LinearConstraint>[] {
  return rows<LinearConstraint>(model.constraints);
}

/** The objective's coefficients, or `{}` when it has none that can be read. */
export function linearOf(holder: unknown): Plain {
  const linear = own(holder, "linear");
  return isPlain(holder) && isPlain(linear) ? linear : {};
}

function idText(item: { id?: unknown }): string {
  return typeof item.id === "string" ? item.id : shown(item.id);
}

const OPS: Readonly<Record<string, string>> = { "<=": "≤", ">=": "≥", "==": "=" };

/** `5 × chairs − 2 × tables`, or `0` for no coefficients. */
function terms(linear: Plain): string {
  const parts = Object.entries(linear).map(([name, value], index) => {
    const negative = typeof value === "number" && value < 0;
    const amount = negative ? shown(-value) : shown(value);
    const sign = index === 0 ? (negative ? "−" : "") : negative ? " − " : " + ";
    return `${sign}${amount} × ${name}`;
  });
  return parts.length === 0 ? "0" : parts.join("");
}

/** "Maximize 45 × chairs + 80 × tables". */
export function goalSentence(model: Model): string {
  const objective = isPlain(model.objective) ? model.objective : {};
  const sense =
    objective.sense === "minimize"
      ? "Minimize"
      : objective.sense === "maximize"
        ? "Maximize"
        : shown(objective.sense);
  const linear = linearOf(objective);
  return Object.keys(linear).length === 0
    ? `${sense}: no decision has a coefficient yet`
    : `${sense} ${terms(linear)}`;
}

/** "5 × chairs + 20 × tables ≤ 400". */
export function limitText(limit: LinearConstraint): string {
  const op =
    typeof limit.op === "string" ? (own<string>(OPS, limit.op) ?? limit.op) : shown(limit.op);
  return `${terms(linearOf(limit))} ${op} ${shown(limit.rhs)}`;
}

/** `<prefix>_<n>`, `n` one more than the highest of any id of that form in the list. */
function nextName(list: unknown, prefix: string): string {
  let highest = 0;
  for (const { item } of rows<{ id?: unknown }>(list)) {
    const found =
      typeof item.id === "string" ? new RegExp(`^${prefix}_(\\d+)$`).exec(item.id) : null;
    if (found) highest = Math.max(highest, Number(found[1]));
  }
  return `${prefix}_${highest + 1}`;
}

/** Appends to a list, or writes the list whole when the model has none. */
function append(model: Model, key: string, value: unknown): Edit[] {
  return Array.isArray(model[key])
    ? [{ edit: "set_path", path: `/${key}/-`, value }]
    : [{ edit: "set_path", path: `/${key}`, value: [value] }];
}

export function addDecision(model: Model): Edit[] {
  return append(model, "variables", {
    id: nextName(model.variables, "decision"),
    type: "continuous",
  });
}

export function addLimit(model: Model): Edit[] {
  return append(model, "constraints", {
    id: nextName(model.constraints, "limit"),
    linear: {},
    op: "<=",
    rhs: 0,
  });
}

function valueAtPath(model: Model, path: string): unknown {
  let here: unknown = model;
  for (const part of path.split("/").slice(1)) {
    const key = part.replace(/~1/g, "/").replace(/~0/g, "~");
    if (Array.isArray(here)) here = here[Number(key)];
    else if (isPlain(here)) here = own(here, key);
    else return undefined;
  }
  return here;
}

/**
 * A field committed with `text`: a number when it reads as one, else the text; an emptied
 * optional field is removed. `null` when nothing would change.
 */
export function fieldEdits(
  model: Model,
  path: string,
  text: string,
  optional: boolean,
): Edit[] | null {
  const current = valueAtPath(model, path);
  if (optional && text.trim() === "") {
    return current === undefined ? null : [{ edit: "remove_path", path }];
  }
  const value = readNumber(text);
  return sameValue(current, value) ? null : [{ edit: "set_path", path, value }];
}

/** A text field (a choice, a name) set as it is. */
export function textEdits(model: Model, path: string, value: string): Edit[] | null {
  return sameValue(valueAtPath(model, path), value) ? null : [{ edit: "set_path", path, value }];
}

/** A coefficient of `name` in the goal (`/objective`) or a limit (`/constraints/<i>`). */
export function coefficientEdits(
  model: Model,
  holder: string,
  name: string,
  text: string,
): Edit[] | null {
  const found = valueAtPath(model, holder);
  if (isPlain(found) && isPlain(found.linear)) {
    return fieldEdits(model, `${holder}/linear${pointer([name])}`, text, true);
  }
  if (text.trim() === "") return null;
  return [{ edit: "set_path", path: `${holder}/linear`, value: { [name]: readNumber(text) } }];
}

function renamedKeys(linear: Plain, from: string, to: string): Plain {
  return Object.fromEntries(
    Object.entries(linear).map(([key, value]) => [key === from ? to : key, value]),
  );
}

/**
 * Renames decision `index` to `text`, and its coefficients in the goal and the limits in
 * the same batch, unless another decision has that name (the service reports it).
 */
export function renameDecision(model: Model, index: number, text: string): Edit[] | null {
  const variables = Array.isArray(model.variables) ? model.variables : [];
  const variable = variables[index];
  if (!isPlain(variable) || variable.id === text) return null;
  const edits: Edit[] = [{ edit: "set_path", path: `/variables/${index}/id`, value: text }];
  const from = variable.id;
  const taken = variables.some((other, at) => at !== index && isPlain(other) && other.id === text);
  if (typeof from !== "string" || taken) return edits;
  const objective = linearOf(model.objective);
  if (hasOwn(objective, from) && isPlain(model.objective)) {
    edits.push({
      edit: "set_path",
      path: "/objective/linear",
      value: renamedKeys(objective, from, text),
    });
  }
  for (const { index: at, item } of constraintsOf(model)) {
    const linear = linearOf(item);
    if (hasOwn(linear, from)) {
      edits.push({
        edit: "set_path",
        path: `/constraints/${at}/linear`,
        value: renamedKeys(linear, from, text),
      });
    }
  }
  return edits;
}

/** Removes decision `index` and its coefficients in the goal and the limits. */
export function removeDecision(model: Model, index: number): Edit[] | null {
  const variable = Array.isArray(model.variables) ? model.variables[index] : undefined;
  if (variable === undefined) return null;
  const edits: Edit[] = [{ edit: "remove_path", path: `/variables/${index}` }];
  const name = isPlain(variable) ? variable.id : undefined;
  if (typeof name !== "string") return edits;
  if (hasOwn(linearOf(model.objective), name)) {
    edits.push({ edit: "remove_path", path: `/objective/linear${pointer([name])}` });
  }
  for (const { index: at, item } of constraintsOf(model)) {
    if (hasOwn(linearOf(item), name)) {
      edits.push({ edit: "remove_path", path: `/constraints/${at}/linear${pointer([name])}` });
    }
  }
  return edits;
}

export function removeLimit(model: Model, index: number): Edit[] | null {
  return Array.isArray(model.constraints) && model.constraints[index] !== undefined
    ? [{ edit: "remove_path", path: `/constraints/${index}` }]
    : null;
}

export const CARD_WIDTH = 220;
export const CARD_HEIGHT = 64;
const GAP_X = 160;
const STEP_Y = 88;

export interface Card {
  key: string;
  x: number;
  y: number;
}

export interface DecisionCard extends Card {
  id: string;
  index: number;
}

export interface TargetCard extends Card {
  /** `goal`, or `limit:<index>`. */
  kind: "goal" | "limit";
  index: number;
}

export interface Line {
  /** A decision's id. */
  from: string;
  /** A target card's key. */
  to: string;
  label: string;
}

/**
 * The Diagram view's layout: decisions on the left, the goal and each limit on the right,
 * and a line from a decision to each card whose coefficients name it. Nothing is stored.
 */
export function diagramLayout(model: Model): {
  decisions: DecisionCard[];
  targets: TargetCard[];
  lines: Line[];
  width: number;
  height: number;
} {
  const decisions = variablesOf(model).map(({ index, item }, at) => ({
    key: `decision:${index}`,
    id: idText(item),
    index,
    x: 0,
    y: at * STEP_Y,
  }));
  const right = CARD_WIDTH + GAP_X;
  const targets: TargetCard[] = [
    { key: "goal", kind: "goal", index: -1, x: right, y: 0 },
    ...constraintsOf(model).map(({ index }, at) => ({
      key: `limit:${index}`,
      kind: "limit" as const,
      index,
      x: right,
      y: (at + 1) * STEP_Y,
    })),
  ];
  const known = new Set(decisions.map((card) => card.id));
  const lines: Line[] = [];
  const link = (to: string, linear: Plain) => {
    for (const [name, value] of Object.entries(linear)) {
      if (known.has(name)) lines.push({ from: name, to, label: shown(value) });
    }
  };
  link("goal", linearOf(model.objective));
  for (const { index, item } of constraintsOf(model)) link(`limit:${index}`, linearOf(item));
  const rowsDrawn = Math.max(decisions.length, targets.length);
  return {
    decisions,
    targets,
    lines,
    width: right + CARD_WIDTH,
    height: Math.max(rowsDrawn - 1, 0) * STEP_Y + CARD_HEIGHT,
  };
}
