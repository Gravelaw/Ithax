/**
 * Reading a `process` model for the Canvas, and building the edits of its actions. Nothing
 * here judges the model: validation is the service's (spec 1 "Validation"), and the issues
 * shown are the service's own.
 */
import type {
  Component,
  ComponentType,
  Connection,
  Edit,
  Issue,
  Model,
  SettingDescription,
} from "../api/types";

/** The palette's groups and the block shapes (`docs/design/design-system.md` "Block styles"). */
export type Category = "flow" | "work" | "resource" | "other";

export const GROUPS: readonly { category: Category; label: string; types: readonly string[] }[] = [
  { category: "flow", label: "Flow", types: ["source", "sink", "delay", "branch"] },
  { category: "work", label: "Work", types: ["server", "queue", "batch", "unbatch", "store"] },
  { category: "resource", label: "Resources", types: ["resource_pool", "schedule", "failure"] },
];

export function categoryOf(type: string): Category {
  return GROUPS.find((group) => group.types.includes(type))?.category ?? "other";
}

/** Block size at 100% zoom, for placing (`design-system.md`: about 176 × 64 px). */
export const BLOCK_WIDTH = 176;
export const BLOCK_HEIGHT = 64;
export const GRID = 8;

export function components(model: Model | null): Component[] {
  return Array.isArray(model?.components) ? model.components : [];
}

export function connections(model: Model | null): Connection[] {
  return Array.isArray(model?.connections) ? model.connections : [];
}

/**
 * `<type>_<n>` with `n` one more than the highest number any component id of that form
 * uses (owner review choice 5), so a deleted block's id is not given to the next one.
 */
export function nextId(model: Model, type: string): string {
  const pattern = new RegExp(`^${type.replace(/[^a-z0-9_]/g, "")}_(\\d+)$`);
  let highest = 0;
  for (const component of components(model)) {
    const found = pattern.exec(component.id);
    if (found) highest = Math.max(highest, Number(found[1]));
  }
  return `${type}_${highest + 1}`;
}

export function snap(value: number): number {
  return Math.round(value / GRID) * GRID;
}

export interface Point {
  x: number;
  y: number;
}

/** A component's position: its `ui` when it holds one, else a place in a grid by order. */
export function positionOf(component: Component, index: number): Point {
  const ui = component.ui;
  if (ui && typeof ui.x === "number" && typeof ui.y === "number") return { x: ui.x, y: ui.y };
  return { x: 40 + (index % 4) * 224, y: 40 + Math.floor(index / 4) * 120 };
}

/** The edit that places a component, keeping any other key its `ui` holds. */
export function moveEdit(component: Component, to: Point): Edit {
  return { edit: "set_ui", id: component.id, ui: { ...(component.ui ?? {}), x: to.x, y: to.y } };
}

/** Where a new block goes when added from the keyboard: down 24 px until it overlaps none. */
export function freePlace(model: Model, centre: Point): Point {
  const placed = components(model).map(positionOf);
  let at = { x: snap(centre.x - BLOCK_WIDTH / 2), y: snap(centre.y - BLOCK_HEIGHT / 2) };
  const overlaps = (point: Point) =>
    placed.some(
      (other) =>
        Math.abs(other.x - point.x) < BLOCK_WIDTH && Math.abs(other.y - point.y) < BLOCK_HEIGHT,
    );
  for (let tries = 0; tries < 1000 && overlaps(at); tries += 1) at = { ...at, y: at.y + 24 };
  return at;
}

/** A connection end, split at its first dot (spec 1). */
export function splitEnd(end: string): [string, string] | null {
  const dot = end.indexOf(".");
  if (dot <= 0 || dot === end.length - 1) return null;
  return [end.slice(0, dot), end.slice(dot + 1)];
}

/** A component's ports: its type's inputs and outputs, a branch's routes as outputs. */
export function portsOf(
  component: Component,
  type: ComponentType | undefined,
): { inputs: string[]; outputs: string[] } {
  if (type === undefined) return { inputs: [], outputs: [] };
  let outputs = type.outputs;
  if (type.outputs_from !== null) {
    const listed = component.params[type.outputs_from];
    outputs = Array.isArray(listed)
      ? listed.filter((item): item is string => typeof item === "string")
      : [];
  }
  return { inputs: type.inputs, outputs };
}

/** What kind of reference line a setting draws (`design-system.md` "Line styles"). */
export type ReferenceKind = "pool" | "schedule" | "failure";

export interface Reference {
  /** The resource block the line starts at, and the block it names. */
  from: string;
  to: string;
  kind: ReferenceKind;
}

/** A server's `pool` and a `schedule`'s or `failure`'s `target`, where both blocks exist. */
export function references(model: Model): Reference[] {
  const all = components(model);
  const ids = new Set(all.map((component) => component.id));
  const found: Reference[] = [];
  for (const component of all) {
    const pool = component.params.pool;
    if (component.type === "server" && typeof pool === "string" && ids.has(pool)) {
      found.push({ from: pool, to: component.id, kind: "pool" });
    }
    const target = component.params.target;
    if (
      (component.type === "schedule" || component.type === "failure") &&
      typeof target === "string" &&
      ids.has(target)
    ) {
      found.push({ from: component.id, to: target, kind: component.type });
    }
  }
  return found;
}

/** The component an issue is about: by its `path` (`/components/<i>`), else its `component`. */
export function issueComponent(issue: Issue, model: Model | null): string | null {
  const found = /^\/components\/(\d+)(\/|$)/.exec(issue.path);
  if (found) {
    const component = components(model)[Number(found[1])];
    if (component) return component.id;
  }
  return issue.component;
}

/** The setting an issue points at inside a component's `params`: `/service/mean`, or null. */
export function issueSetting(issue: Issue): string | null {
  const found = /^\/components\/\d+\/params(\/.*)$/.exec(issue.path);
  return found?.[1] ?? null;
}

export function issueCounts(issues: Issue[]): { errors: number; warnings: number } {
  const errors = issues.filter((issue) => issue.severity === "error").length;
  return { errors, warnings: issues.length - errors };
}

/** "2 errors, 1 warning", or "No problems". */
export function countsText(issues: Issue[]): string {
  const { errors, warnings } = issueCounts(issues);
  if (errors === 0 && warnings === 0) return "No problems";
  const part = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;
  return [errors ? part(errors, "error") : null, warnings ? part(warnings, "warning") : null]
    .filter(Boolean)
    .join(", ");
}

/** JSON Pointer tokens (RFC 6901). */
export function pointer(segments: readonly (string | number)[]): string {
  return segments
    .map((segment) => `/${String(segment).replace(/~/g, "~0").replace(/\//g, "~1")}`)
    .join("");
}

export function valueAt(root: unknown, segments: readonly (string | number)[]): unknown {
  let value: unknown = root;
  for (const segment of segments) {
    if (Array.isArray(value)) value = value[Number(segment)];
    else if (typeof value === "object" && value !== null)
      value = (value as Record<string, unknown>)[String(segment)];
    else return undefined;
  }
  return value;
}

function nest(segments: readonly (string | number)[], value: unknown): unknown {
  let nested = value;
  for (const segment of [...segments].reverse()) {
    nested = typeof segment === "number" ? [nested] : { [segment]: nested };
  }
  return nested;
}

/**
 * The `set_setting` that puts `value` at `segments` inside a component's `params`. Every
 * segment but the last must exist (spec 3 "Model edits"), so the edit is sent at the first
 * segment that is missing, holding the rest.
 */
export function settingEdit(
  component: Component,
  segments: readonly (string | number)[],
  value: unknown,
): Edit {
  let depth = 0;
  let here: unknown = component.params;
  while (depth < segments.length - 1) {
    const next = valueAt(here, [segments[depth] as string | number]);
    if (typeof next !== "object" || next === null) break;
    here = next;
    depth += 1;
  }
  return {
    edit: "set_setting",
    id: component.id,
    path: pointer(segments.slice(0, depth + 1)),
    value: nest(segments.slice(depth + 1), value),
  };
}

/**
 * A copy of `model` without the value at `segments` of a component's `params`. No edit
 * removes a setting (spec 3 "Model edits"), so clearing an optional one writes the whole
 * model, as undo does.
 */
export function withoutSetting(
  model: Model,
  id: string,
  segments: readonly (string | number)[],
): Model {
  const copy = structuredClone(model);
  const component = components(copy).find((item) => item.id === id);
  if (!component || segments.length === 0) return copy;
  const parent = valueAt(component.params, segments.slice(0, -1));
  const last = segments.at(-1) as string | number;
  if (Array.isArray(parent)) parent.splice(Number(last), 1);
  else if (typeof parent === "object" && parent !== null)
    delete (parent as Record<string, unknown>)[String(last)];
  return copy;
}

/** A copy of `model` without a parameter field, such as `min` (no edit removes one). */
export function withoutParameterField(model: Model, id: string, field: string): Model {
  const copy = structuredClone(model);
  const parameter = copy.parameters?.[id];
  if (parameter) delete (parameter as unknown as Record<string, unknown>)[field];
  return copy;
}

const NUMBER = /^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$/;

/**
 * A typed number, read by spec 1's number grammar; text that is not one is sent as it was
 * typed, so the service, not the interface, says what is wrong with it.
 */
export function readNumber(text: string): unknown {
  const trimmed = text.trim();
  if (NUMBER.test(trimmed)) {
    const value = Number(trimmed);
    if (Number.isFinite(value)) return value;
  }
  return text;
}

export const TIME_UNITS = ["s", "min", "h", "d"] as const;

/** `"2 min"` as number text and unit; `null` for anything else. */
export function splitQuantity(value: unknown): { number: string; unit: string } | null {
  if (typeof value !== "string") return null;
  const found = /^(\S+) (s|min|h|d)$/.exec(value);
  return found ? { number: found[1] as string, unit: found[2] as string } : null;
}

/** `{"$param": id}`'s id, or null. */
export function paramOf(value: unknown): string | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const keys = Object.keys(value);
  const id = (value as Record<string, unknown>).$param;
  return keys.length === 1 && typeof id === "string" ? id : null;
}

/** A value as one line of text, for the type line and summaries. */
export function shown(value: unknown): string {
  if (value === undefined) return "";
  const param = paramOf(value);
  if (param !== null) return param;
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

/** The block's type line: the type and one key setting (`design-system.md` "Block styles"). */
export function typeLine(component: Component): string {
  const params = component.params;
  const key: Record<string, string> = {
    source: "interarrival",
    server: "capacity",
    delay: "time",
    queue: "capacity",
    batch: "size",
    store: "initial",
    resource_pool: "capacity",
    schedule: "target",
    failure: "target",
    branch: "rule",
  };
  const name = key[component.type];
  if (name === undefined || params[name] === undefined) return component.type;
  const value = params[name];
  if (component.type === "source" && typeof value === "object" && value !== null) {
    const mean = (value as Record<string, unknown>).mean;
    if (mean !== undefined) return `source · every ${shown(mean)}`;
    return `source · ${shown((value as Record<string, unknown>).dist)}`;
  }
  if (typeof value === "object" && value !== null && paramOf(value) === null) {
    return `${component.type} · ${shown((value as Record<string, unknown>).dist ?? name)}`;
  }
  const joiner = paramOf(value) !== null ? " = " : " ";
  return `${component.type} · ${name}${joiner}${shown(value)}`;
}

/** The fields of each spec 1 distribution, and whether each is a time. */
export const DISTRIBUTIONS: Record<string, readonly { name: string; time: boolean }[]> = {
  constant: [{ name: "value", time: true }],
  exponential: [{ name: "mean", time: true }],
  uniform: [
    { name: "min", time: true },
    { name: "max", time: true },
  ],
  triangular: [
    { name: "min", time: true },
    { name: "mode", time: true },
    { name: "max", time: true },
  ],
  normal: [
    { name: "mean", time: true },
    { name: "sd", time: true },
  ],
  lognormal: [
    { name: "mean", time: true },
    { name: "sd", time: true },
  ],
  weibull: [
    { name: "shape", time: false },
    { name: "scale", time: true },
  ],
  empirical: [],
};

/** Words for a setting's name: `queue_capacity` → "Queue capacity". */
export function words(name: string): string {
  const text = name.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Whether a setting is required now (`required`, or `required_when` its condition holds). */
export function isRequired(setting: SettingDescription, params: Record<string, unknown>): boolean {
  if (setting.required) return true;
  const when = setting.required_when;
  return when !== undefined && params[when[0]] === when[1];
}
