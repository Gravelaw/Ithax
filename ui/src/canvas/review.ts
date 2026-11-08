/**
 * The review of an outside change (spec 3 "Canvas behaviour", External edits;
 * `docs/design/canvas-interactions.md` "Reviewing an outside change"; owner review choice 2).
 *
 * When another client's write reloads the model, the model shown before is compared with
 * the one read, item by item: components by `id`, connections by `from`, parameters by
 * name, experiments, `objectives`, variables and constraints by `id`, and every other
 * top-level key (an `optimization` model's `objective`, `meta`, `run`, ...) as one item. A
 * list that is not a list of objects with distinct ids is one item; key order and list
 * order are not changes. A component removed and one added that equals it once
 * `rename_component`'s rewrite is applied is one rename, and the references the rename
 * rewrote are compared as renamed, so they are not marked.
 *
 * Each change keeps the item before and after. Its mark is shown while the model shown
 * holds the item as the other client left it and the user has not accepted it. Rejecting
 * writes the model shown with the item as it was before (spec 3: a whole-model write).
 * Everything here is pure: the session keeps the list and makes the writes.
 */
import type { Component, Model } from "../api/types";
import { pointer, shown } from "./model";

/** Where an item lives in the model. */
export type ItemRef =
  | { kind: "list"; key: string; id: string }
  | { kind: "map"; key: string; id: string }
  | { kind: "top"; key: string }
  | { kind: "rename"; was: string; id: string };

export interface Change {
  ref: ItemRef;
  /** The item before the other client's write; `undefined` when it was not there. */
  before: unknown;
  /** The item as the other client left it; `undefined` when it removed it. */
  after: unknown;
  /** A removed list item's place in its list, to put it back there. */
  index?: number;
}

export interface ReviewItem extends Change {
  /** Stable for the open project, for the buttons that act on it. */
  id: number;
  accepted: boolean;
}

export type ChangeKind = "added" | "changed" | "removed" | "renamed";

/** The lists compared item by item, and the field that names an item in each. */
const LISTS: Readonly<Record<string, string>> = {
  components: "id",
  connections: "from",
  experiments: "id",
  objectives: "id",
  variables: "id",
  constraints: "id",
};
const MAPS: readonly string[] = ["parameters"];
/** The settings that name another component, which `rename_component` rewrites (spec 3). */
const REFERENCES: readonly string[] = ["pool", "target"];

type Plain = Record<string, unknown>;

function isPlain(value: unknown): value is Plain {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Deep equality of JSON values; key order does not count, list order does. */
export function sameValue(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    return a.every((item, index) => sameValue(item, b[index]));
  }
  if (isPlain(a) && isPlain(b)) {
    const keys = Object.keys(a);
    if (keys.length !== Object.keys(b).length) return false;
    return keys.every((key) => Object.hasOwn(b, key) && sameValue(a[key], b[key]));
  }
  return false;
}

/** A list whose entries are objects with distinct text ids in `field`, else `null`. */
function keyed(value: unknown, field: string): Map<string, Plain> | null {
  if (value === undefined) return new Map();
  if (!Array.isArray(value)) return null;
  const found = new Map<string, Plain>();
  for (const entry of value) {
    if (!isPlain(entry) || typeof entry[field] !== "string") return null;
    const id = entry[field] as string;
    if (found.has(id)) return null;
    found.set(id, entry);
  }
  return found;
}

function mapOf(value: unknown): Plain | null {
  if (value === undefined) return {};
  return isPlain(value) ? value : null;
}

function endRenamed(end: unknown, from: string, to: string): unknown {
  return typeof end === "string" && end.startsWith(`${from}.`) ? to + end.slice(from.length) : end;
}

/** A component as `rename_component` leaves it: its own id, and its references to `from`. */
function renamedComponent(component: Plain, from: string, to: string): Plain {
  const copy = structuredClone(component);
  if (copy.id === from) copy.id = to;
  const params = copy.params;
  if (isPlain(params)) {
    for (const key of REFERENCES) if (params[key] === from) params[key] = to;
  }
  return copy;
}

/**
 * The model as `rename_component` from `from` to `to` leaves it (spec 3 "Model edits",
 * Names): the component's id, connection ends, `pool` and `target` settings that name it,
 * and objective and constraint metrics that start with `<from>.`.
 */
export function renameIn(model: Model, from: string, to: string): Model {
  const copy = structuredClone(model);
  if (Array.isArray(copy.components)) {
    copy.components = copy.components.map((component) =>
      isPlain(component)
        ? (renamedComponent(component, from, to) as unknown as Component)
        : component,
    );
  }
  if (Array.isArray(copy.connections)) {
    for (const connection of copy.connections) {
      if (!isPlain(connection)) continue;
      connection.from = endRenamed(connection.from, from, to) as string;
      connection.to = endRenamed(connection.to, from, to) as string;
    }
  }
  for (const key of ["objectives", "constraints"]) {
    const list = copy[key];
    if (!Array.isArray(list)) continue;
    for (const entry of list) {
      if (isPlain(entry) && "metric" in entry) entry.metric = endRenamed(entry.metric, from, to);
    }
  }
  return copy;
}

/** Pairs of a removed and an added component that are one rename. */
function renamesBetween(before: Model, after: Model): [string, string][] {
  const old = keyed(before.components, "id");
  const now = keyed(after.components, "id");
  if (old === null || now === null) return [];
  const added = [...now.keys()].filter((id) => !old.has(id));
  const used = new Set<string>();
  const pairs: [string, string][] = [];
  for (const [was, component] of old) {
    if (now.has(was)) continue;
    const id = added.find(
      (candidate) =>
        !used.has(candidate) &&
        sameValue(renamedComponent(component, was, candidate), now.get(candidate)),
    );
    if (id === undefined) continue;
    used.add(id);
    pairs.push([was, id]);
  }
  return pairs;
}

/** The changes from `before` to `after`, in the order of `after`'s keys and items. */
export function changesBetween(before: Model, after: Model): Change[] {
  const renames = renamesBetween(before, after);
  // Compared as renamed, so what a rename rewrote is not marked as well.
  const base = renames.reduce((model, [was, id]) => renameIn(model, was, id), before);
  const keys = [...Object.keys(after), ...Object.keys(base).filter((key) => !(key in after))];
  const changes: Change[] = [];
  for (const key of keys) {
    const field = LISTS[key];
    if (field !== undefined) {
      const old = keyed(base[key], field);
      const now = keyed(after[key], field);
      if (old !== null && now !== null) {
        for (const [id, item] of now) {
          const was = old.get(id);
          if (!sameValue(was, item))
            changes.push({ ref: { kind: "list", key, id }, before: was, after: item });
        }
        [...old.keys()].forEach((id, index) => {
          if (!now.has(id)) {
            changes.push({
              ref: { kind: "list", key, id },
              before: old.get(id),
              after: undefined,
              index,
            });
          }
        });
        continue;
      }
    }
    if (MAPS.includes(key)) {
      const old = mapOf(base[key]);
      const now = mapOf(after[key]);
      if (old !== null && now !== null) {
        const names = [...Object.keys(now), ...Object.keys(old).filter((name) => !(name in now))];
        for (const id of names) {
          if (!sameValue(old[id], now[id])) {
            changes.push({ ref: { kind: "map", key, id }, before: old[id], after: now[id] });
          }
        }
        continue;
      }
    }
    if (!sameValue(base[key], after[key])) {
      changes.push({ ref: { kind: "top", key }, before: base[key], after: after[key] });
    }
  }
  for (const [was, id] of renames) {
    const old = keyed(before.components, "id")?.get(was);
    const now = keyed(after.components, "id")?.get(id);
    changes.push({ ref: { kind: "rename", was, id }, before: old, after: now });
  }
  return changes;
}

export function changeKind(change: Change): ChangeKind {
  if (change.ref.kind === "rename") return "renamed";
  if (change.before === undefined) return "added";
  if (change.after === undefined) return "removed";
  return "changed";
}

function listFind(list: unknown, field: string, id: string): number {
  if (!Array.isArray(list)) return -1;
  return list.findIndex((entry) => isPlain(entry) && entry[field] === id);
}

/** The item `ref` names in `model`, or `undefined`. */
export function itemAt(model: Model, ref: ItemRef): unknown {
  if (ref.kind === "rename") {
    if (listFind(model.components, "id", ref.was) >= 0) return undefined;
    const list = model.components;
    const at = listFind(list, "id", ref.id);
    return at >= 0 ? (list as unknown[])[at] : undefined;
  }
  if (ref.kind === "top") return model[ref.key];
  if (ref.kind === "map") {
    const map = model[ref.key];
    return isPlain(map) ? map[ref.id] : undefined;
  }
  const list = model[ref.key];
  const at = listFind(list, LISTS[ref.key] ?? "id", ref.id);
  return at >= 0 ? (list as unknown[])[at] : undefined;
}

/** Whether a change's mark is shown on `model`. */
export function isShown(item: ReviewItem, model: Model): boolean {
  return !item.accepted && sameValue(itemAt(model, item.ref), item.after);
}

/** The marks shown on `model`, in their order. */
export function shownItems(review: readonly ReviewItem[], model: Model | null): ReviewItem[] {
  return model === null ? [] : review.filter((item) => isShown(item, model));
}

/** `model` with the item of `change` as it was before the other client's write. */
export function restore(model: Model, change: Change): Model {
  const { ref } = change;
  if (ref.kind === "rename") return renameIn(model, ref.id, ref.was);
  const copy = structuredClone(model);
  const before = structuredClone(change.before);
  if (ref.kind === "top") {
    if (before === undefined) delete copy[ref.key];
    else copy[ref.key] = before;
    return copy;
  }
  if (ref.kind === "map") {
    const map = isPlain(copy[ref.key]) ? (copy[ref.key] as Plain) : {};
    if (before === undefined) delete map[ref.id];
    else map[ref.id] = before;
    copy[ref.key] = map;
    return copy;
  }
  const list = Array.isArray(copy[ref.key]) ? (copy[ref.key] as unknown[]) : [];
  const at = listFind(list, LISTS[ref.key] ?? "id", ref.id);
  if (before === undefined) {
    if (at >= 0) list.splice(at, 1);
  } else if (at >= 0) list[at] = before;
  else list.splice(Math.min(change.index ?? list.length, list.length), 0, before);
  copy[ref.key] = list;
  return copy;
}

/** `model` with every change restored: the other items first, then the renames. */
export function restoreAll(model: Model, changes: readonly Change[]): Model {
  const ordered = [
    ...changes.filter((change) => change.ref.kind !== "rename"),
    ...changes.filter((change) => change.ref.kind === "rename"),
  ];
  return ordered.reduce(restore, model);
}

function refKey(ref: ItemRef): string {
  return ref.kind === "rename"
    ? `rename:${ref.was}>${ref.id}`
    : `${ref.kind}:${ref.key}:${"id" in ref ? ref.id : ""}`;
}

/**
 * The marks after a later outside change: `fresh` compares the model shown with the one
 * read. An item already marked keeps its first `before`, so Reject restores it as it was
 * before the first outside change; one the other client put back loses its mark. Items
 * made or replaced get ids from `nextId` on.
 */
export function mergeReview(
  existing: readonly ReviewItem[],
  fresh: readonly Change[],
  nextId: number,
): ReviewItem[] {
  const result: (ReviewItem | null)[] = [...existing];
  let id = nextId;
  for (const change of fresh) {
    const key = refKey(change.ref);
    const at = result.findIndex((item) => item !== null && refKey(item.ref) === key);
    const earlier = at >= 0 ? result[at] : null;
    const merged: Change = earlier
      ? {
          ...change,
          before: earlier.before,
          ...(earlier.index !== undefined ? { index: earlier.index } : {}),
        }
      : change;
    const item = sameValue(merged.before, merged.after)
      ? null
      : { ...merged, id: 0, accepted: false };
    if (item !== null) item.id = id++;
    if (at >= 0) result[at] = item;
    else if (item !== null) result.push(item);
  }
  return result.filter((item) => item !== null);
}

export interface FieldChange {
  path: string;
  before: unknown;
  after: unknown;
}

/** The leaves that differ between two items, as JSON Pointers into the item. */
export function fieldChanges(before: unknown, after: unknown, at: string[] = []): FieldChange[] {
  if (isPlain(before) && isPlain(after)) {
    const keys = [...Object.keys(before), ...Object.keys(after).filter((key) => !(key in before))];
    return keys.flatMap((key) => fieldChanges(before[key], after[key], [...at, key]));
  }
  return sameValue(before, after) ? [] : [{ path: pointer(at), before, after }];
}

const NOUNS: Readonly<Record<string, Readonly<Record<string, string>>>> = {
  process: {
    components: "block",
    connections: "connection",
    parameters: "parameter",
    experiments: "experiment",
    objectives: "objective",
    constraints: "constraint",
  },
  optimization: { variables: "decision", constraints: "limit", objective: "the goal" },
};

/** What a change is about, in the model's words: "block till", "the goal", "meta". */
export function changeSubject(change: Change, domain: unknown): string {
  const { ref } = change;
  const nouns = NOUNS[String(domain)] ?? NOUNS.process ?? {};
  if (ref.kind === "rename") return `block ${ref.was}`;
  if (ref.kind === "top") return nouns[ref.key] ?? ref.key;
  return `${nouns[ref.key] ?? ref.key} ${ref.id}`;
}

function valueText(value: unknown): string {
  return value === undefined ? "(none)" : shown(value);
}

/** A field's name for people: a block's setting without `/params`, else the path's words. */
export function fieldName(path: string): string {
  const inner = path.startsWith("/params/") ? path.slice("/params".length) : path;
  return inner.slice(1).replaceAll("/", " ") || "value";
}

/** One line for a change: "Changed: block till (capacity: 1 → 2)". */
export function describeChange(change: Change, domain: unknown): string {
  const kind = changeKind(change);
  const word = kind[0]?.toUpperCase() + kind.slice(1);
  const subject = changeSubject(change, domain);
  if (change.ref.kind === "rename") return `${word}: ${subject} → ${change.ref.id}`;
  if (kind !== "changed") return `${word}: ${subject}`;
  const fields = fieldChanges(change.before, change.after);
  const parts = fields
    .slice(0, 3)
    .map(
      (field) => `${fieldName(field.path)}: ${valueText(field.before)} → ${valueText(field.after)}`,
    );
  if (fields.length > 3) parts.push(`${fields.length - 3} more`);
  return `${word}: ${subject} (${parts.join("; ")})`;
}
