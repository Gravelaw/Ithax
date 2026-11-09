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
 *
 * An indexed model (spec 1 "Indexed optimization", format 0.2; AKS-123) is read as written,
 * not expanded: a decision with `over` repeats over sets, a limit with `for` repeats too, and
 * `terms` add a decision times a number or a table, summed over the decision's other sets.
 * The views read them in words and draw them, but do not edit sets, tables or terms; renaming
 * or removing a decision carries its terms with it.
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

/** The set ids of an `over` or a `for`, or `[]` when there are none that can be read. */
export function setsOf(holder: unknown, key: "over" | "for"): string[] {
  const value = own(holder, key);
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

/** A term of the goal or a limit, as the file holds it. */
export interface PlanTerm {
  index: number;
  variable: unknown;
  coefficient?: unknown;
}

/** The terms of the goal or a limit that are objects. */
export function termsOf(holder: unknown): PlanTerm[] {
  const list = own(holder, "terms");
  if (!Array.isArray(list)) return [];
  return list.flatMap((item, index) =>
    isPlain(item)
      ? [{ index, variable: own(item, "variable"), coefficient: own(item, "coefficient") }]
      : [],
  );
}

/** The table a `{"$table": "id"}` names, or `null`. */
export function tableOf(value: unknown): string | null {
  if (!isPlain(value)) return null;
  const id = own(value, "$table");
  return Object.keys(value).length === 1 && typeof id === "string" ? id : null;
}

/** Whether the model uses the indexed layout: sets, tables, `over`, `for` or `terms`. */
export function isIndexed(model: Model): boolean {
  if (hasOwn(model, "sets") || hasOwn(model, "tables") || hasOwn(model.objective, "terms")) {
    return true;
  }
  return (
    variablesOf(model).some(({ item }) => hasOwn(item, "over")) ||
    constraintsOf(model).some(({ item }) => hasOwn(item, "for") || hasOwn(item, "terms"))
  );
}

/** "one for each depots × customers", or `null` for a decision with no sets. */
export function repeatsText(holder: unknown): string | null {
  const sets = setsOf(holder, "over");
  return sets.length === 0 ? null : `one for each ${sets.join(" × ")}`;
}

/** `name[a, b]` for a value over sets `a` and `b`; `name` for none. */
function indexed(name: string, sets: readonly string[]): string {
  return sets.length === 0 ? name : `${name}[${sets.join(", ")}]`;
}

/** The sets of the table `id`. */
function tableSets(model: Model, id: string): string[] {
  return setsOf(own(model.tables, id), "over");
}

/** A table reference or a number, as text: `cost[depots, customers]`, `2`. */
function amountText(model: Model, value: unknown): string {
  const table = tableOf(value);
  return table === null ? shown(value) : indexed(table, tableSets(model, table));
}

/** "Σ over customers cost[depots, customers] × ship[depots, customers]". */
function termText(model: Model, term: PlanTerm, bound: readonly string[]): string {
  const name = typeof term.variable === "string" ? term.variable : shown(term.variable);
  const variable = variablesOf(model).find(({ item }) => item.id === term.variable)?.item;
  const sets = setsOf(variable, "over");
  const summed = sets.filter((set) => !bound.includes(set));
  const factor = term.coefficient === undefined ? "" : `${amountText(model, term.coefficient)} × `;
  const sum = summed.length === 0 ? "" : `Σ over ${summed.join(", ")} `;
  return `${sum}${factor}${indexed(name, sets)}`;
}

/** The left-hand side: the coefficients, then the terms. */
function sideText(model: Model, holder: unknown, bound: readonly string[]): string {
  const linear = linearOf(holder);
  const parts = termsOf(holder).map((term) => termText(model, term, bound));
  if (Object.keys(linear).length > 0) parts.unshift(terms(linear));
  return parts.join(" + ");
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
  const side = sideText(model, objective, []);
  return side === "" ? `${sense}: no decision has a coefficient yet` : `${sense} ${side}`;
}

/**
 * "5 × chairs + 20 × tables ≤ 400"; for an indexed limit "For each depots: Σ over customers
 * ship[depots, customers] ≤ supply[depots]".
 */
export function limitText(limit: LinearConstraint, model: Model = {}): string {
  const op =
    typeof limit.op === "string" ? (own<string>(OPS, limit.op) ?? limit.op) : shown(limit.op);
  const bound = setsOf(limit, "for");
  const side = sideText(model, limit, bound) || "0";
  const each = bound.length === 0 ? "" : `For each ${bound.join(" × ")}: `;
  return `${each}${side} ${op} ${amountText(model, limit.rhs)}`;
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

/**
 * One place where the goal or a limit uses a decision: a `linear` coefficient, keyed by the
 * decision's id or, for an indexed decision, by one of its expanded names
 * (`ship[north,park]`, spec 2 "Indexed problems"), or a term naming it (AKS-123).
 *
 * `references` is the one resolver that renaming, removing and the Diagram view all read,
 * so the three can never disagree about what uses a decision (review of PR #53, three
 * findings on this mapping).
 */
export interface Reference {
  /** The declared id of the decision used. */
  decision: string;
  /** The goal (`/objective`) or a limit (`/constraints/<i>`). */
  holder: string;
  /** The Diagram card of the holder: `goal` or `limit:<i>`. */
  card: string;
  kind: "linear" | "term";
  /** The `linear` key, as written (`ship`, `ship[north,park]`). */
  key: string;
  /** For an expanded key, its members with their brackets (`[north,park]`); else `""`. */
  members: string;
  /** For a term, its index in `terms`; else -1. */
  term: number;
  /** What it adds, as text: the coefficient, or the term's table id or number. */
  label: string;
}

const EXPANDED = /^(.+)(\[[^[\]]*\])$/;

/** Every use of a declared decision in the goal and the limits, in model order: within each
 * holder its `linear` keys first, then its terms. Keys and terms naming no decision are not
 * listed (the service reports them, E175). */
export function references(model: Model): Reference[] {
  const ids = new Set(
    variablesOf(model).flatMap(({ item }) => (typeof item.id === "string" ? [item.id] : [])),
  );
  const holders: [string, string, unknown][] = [
    ["/objective", "goal", model.objective],
    ...constraintsOf(model).map(({ index, item }): [string, string, unknown] => [
      `/constraints/${index}`,
      `limit:${index}`,
      item,
    ]),
  ];
  const found: Reference[] = [];
  for (const [holder, card, item] of holders) {
    for (const [key, value] of Object.entries(linearOf(item))) {
      const expanded = EXPANDED.exec(key);
      const decision = ids.has(key)
        ? key
        : expanded && ids.has(expanded[1] ?? "")
          ? expanded[1]
          : null;
      if (decision === null || decision === undefined) continue;
      const members = decision === key ? "" : key.slice(decision.length);
      const label = members === "" ? shown(value) : `${shown(value)} ${members}`;
      found.push({ decision, holder, card, kind: "linear", key, members, term: -1, label });
    }
    for (const term of termsOf(item)) {
      if (typeof term.variable !== "string" || !ids.has(term.variable)) continue;
      const label =
        term.coefficient === undefined
          ? "1"
          : (tableOf(term.coefficient) ?? shown(term.coefficient));
      found.push({
        decision: term.variable,
        holder,
        card,
        kind: "term",
        key: "",
        members: "",
        term: term.index,
        label,
      });
    }
  }
  return found;
}

/**
 * Renames decision `index` to `text`, and its uses in the goal and the limits (coefficients,
 * expanded names and terms) in the same batch, unless another decision has that name (the
 * service reports it).
 */
export function renameDecision(model: Model, index: number, text: string): Edit[] | null {
  const variables = Array.isArray(model.variables) ? model.variables : [];
  const variable = variables[index];
  if (!isPlain(variable) || variable.id === text) return null;
  const edits: Edit[] = [{ edit: "set_path", path: `/variables/${index}/id`, value: text }];
  const from = variable.id;
  const taken = variables.some((other, at) => at !== index && isPlain(other) && other.id === text);
  if (typeof from !== "string" || taken) return edits;
  const uses = references(model).filter((use) => use.decision === from);
  // A holder's coefficients are written whole, with each key naming it renamed in place.
  const renamed = new Map<string, Map<string, string>>();
  for (const use of uses) {
    if (use.kind !== "linear") continue;
    const keys = renamed.get(use.holder) ?? new Map<string, string>();
    keys.set(use.key, `${text}${use.members}`);
    renamed.set(use.holder, keys);
  }
  for (const [holder, keys] of renamed) {
    const linear = linearOf(valueAtPath(model, holder));
    edits.push({
      edit: "set_path",
      path: `${holder}/linear`,
      value: Object.fromEntries(
        Object.entries(linear).map(([key, value]) => [keys.get(key) ?? key, value]),
      ),
    });
  }
  for (const use of uses) {
    if (use.kind === "term") {
      edits.push({
        edit: "set_path",
        path: `${use.holder}/terms/${use.term}/variable`,
        value: text,
      });
    }
  }
  return edits;
}

/** Removes decision `index` and its uses in the goal and the limits. */
export function removeDecision(model: Model, index: number): Edit[] | null {
  const variable = Array.isArray(model.variables) ? model.variables[index] : undefined;
  if (variable === undefined) return null;
  const edits: Edit[] = [{ edit: "remove_path", path: `/variables/${index}` }];
  const name = isPlain(variable) ? variable.id : undefined;
  if (typeof name !== "string") return edits;
  const uses = references(model).filter((use) => use.decision === name);
  for (const use of uses) {
    if (use.kind === "linear") {
      edits.push({ edit: "remove_path", path: `${use.holder}/linear${pointer([use.key])}` });
    }
  }
  // Terms the last first within each holder, so each index still names the term it was
  // read from.
  const terms = uses.filter((use) => use.kind === "term");
  const holders = [...new Set(terms.map((use) => use.holder))];
  for (const holder of holders) {
    for (const use of terms.filter((item) => item.holder === holder).reverse()) {
      edits.push({ edit: "remove_path", path: `${holder}/terms/${use.term}` });
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
  // One line per decision and card, labelled with every part the decision adds there, in
  // model order, joined with "+": a coefficient, an expanded name's coefficient with its
  // members (`1 [north,park]`), a term's table or number (review of PR #53).
  const known = new Set(decisions.map((card) => card.id));
  const parts = new Map<string, Line>();
  for (const use of references(model)) {
    if (!known.has(use.decision)) continue;
    const key = `${use.decision}>${use.card}`;
    const line = parts.get(key);
    if (line) line.label = `${line.label} + ${use.label}`;
    else parts.set(key, { from: use.decision, to: use.card, label: use.label });
  }
  const order = new Map(targets.map((card, at) => [card.key, at]));
  const lines = [...parts.values()].sort((a, b) => (order.get(a.to) ?? 0) - (order.get(b.to) ?? 0));
  const rowsDrawn = Math.max(decisions.length, targets.length);
  return {
    decisions,
    targets,
    lines,
    width: right + CARD_WIDTH,
    height: Math.max(rowsDrawn - 1, 0) * STEP_Y + CARD_HEIGHT,
  };
}
