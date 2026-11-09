/**
 * The review of an outside change (spec 3 "Canvas behaviour", External edits;
 * `docs/design/canvas-interactions.md` "Reviewing an outside change"; owner review choice 2).
 *
 * The session keeps one baseline: the model shown before the first outside change not yet
 * reviewed, with the user's own writes since folded in. The marks are always the plain
 * comparison of that baseline with the model shown, item by item by stable id: components
 * by `id`, connections by `from`, parameters by name, experiments, `objectives`, variables
 * and constraints by `id`, and every other top-level key (an `optimization` model's
 * `objective`, `meta`, `run`, ...) as one item. A list that is not a list of objects with
 * distinct ids is one item; key order and list order are not changes. A rename is a
 * removal and an addition. Nothing is composed: a later outside change only changes the
 * model shown, and the comparison is made again (review of PR #46).
 *
 * Every lookup by a name the model holds reads own properties only (`own.ts`).
 */
import type { Model } from "../api/types";
import { pointer, shown } from "./model";
import { hasOwn, own, record, setOwn } from "./own";

/** Where an item lives in the model. */
export type ItemRef =
  | { kind: "list"; key: string; id: string }
  | { kind: "map"; key: string; id: string }
  | { kind: "top"; key: string };

export interface Change {
  /** Stable for the item: what the buttons that act on it name. */
  key: string;
  ref: ItemRef;
  /** The item in the baseline; `undefined` when it was not there. */
  before: unknown;
  /** The item in the model shown; `undefined` when it is gone. */
  after: unknown;
  /** The item's place in the baseline's list, to put it back there. */
  index?: number;
}

export type ChangeKind = "added" | "changed" | "removed";

/** The lists compared item by item, and the field that names an item in each. */
const LISTS: Readonly<Record<string, string>> = Object.assign(record<string>(), {
  components: "id",
  connections: "from",
  experiments: "id",
  objectives: "id",
  variables: "id",
  constraints: "id",
});
const MAPS: readonly string[] = ["parameters"];

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
    return keys.every((key) => hasOwn(b, key) && sameValue(own(a, key), own(b, key)));
  }
  return false;
}

/** A list whose entries are objects with distinct text ids in `field`, else `null`. */
function keyed(value: unknown, field: string): Map<string, { item: Plain; index: number }> | null {
  if (value === undefined) return new Map();
  if (!Array.isArray(value)) return null;
  const found = new Map<string, { item: Plain; index: number }>();
  for (const [index, entry] of value.entries()) {
    const id = isPlain(entry) ? own(entry, field) : undefined;
    if (typeof id !== "string" || found.has(id)) return null;
    found.set(id, { item: entry as Plain, index });
  }
  return found;
}

function mapOf(value: unknown): Plain | null {
  if (value === undefined) return record();
  return isPlain(value) ? value : null;
}

function keyOf(ref: ItemRef): string {
  return ref.kind === "top" ? `top:${ref.key}` : `${ref.kind}:${ref.key}:${ref.id}`;
}

function change(ref: ItemRef, before: unknown, after: unknown, index?: number): Change {
  return { key: keyOf(ref), ref, before, after, ...(index !== undefined ? { index } : {}) };
}

/** The changes from `before` to `after`, in the order of `after`'s keys and items. */
export function changesBetween(before: Model, after: Model): Change[] {
  const keys = [...Object.keys(after), ...Object.keys(before).filter((key) => !hasOwn(after, key))];
  const changes: Change[] = [];
  for (const key of keys) {
    const was = own(before, key);
    const now = own(after, key);
    const field = own<string>(LISTS, key);
    if (field !== undefined) {
      const old = keyed(was, field);
      const fresh = keyed(now, field);
      if (old !== null && fresh !== null) {
        for (const [id, { item }] of fresh) {
          const earlier = old.get(id);
          if (!sameValue(earlier?.item, item)) {
            changes.push(change({ kind: "list", key, id }, earlier?.item, item, earlier?.index));
          }
        }
        for (const [id, { item, index }] of old) {
          if (!fresh.has(id))
            changes.push(change({ kind: "list", key, id }, item, undefined, index));
        }
        continue;
      }
    }
    if (MAPS.includes(key)) {
      const old = mapOf(was);
      const fresh = mapOf(now);
      if (old !== null && fresh !== null) {
        const names = [
          ...Object.keys(fresh),
          ...Object.keys(old).filter((name) => !hasOwn(fresh, name)),
        ];
        for (const id of names) {
          if (!sameValue(own(old, id), own(fresh, id))) {
            changes.push(change({ kind: "map", key, id }, own(old, id), own(fresh, id)));
          }
        }
        continue;
      }
    }
    if (!sameValue(was, now)) changes.push(change({ kind: "top", key }, was, now));
  }
  return changes;
}

export function changeKind(item: Change): ChangeKind {
  if (item.before === undefined) return "added";
  if (item.after === undefined) return "removed";
  return "changed";
}

function listFind(list: unknown, field: string, id: string): number {
  if (!Array.isArray(list)) return -1;
  return list.findIndex((entry) => isPlain(entry) && own(entry, field) === id);
}

/** A copy of `model` with the item `ref` names set to `value` (`undefined` removes it). */
export function putItem(model: Model, ref: ItemRef, value: unknown, index?: number): Model {
  const copy = structuredClone(model);
  const item = structuredClone(value);
  if (ref.kind === "top") {
    if (item === undefined) delete copy[ref.key];
    else setOwn(copy, ref.key, item);
    return copy;
  }
  if (ref.kind === "map") {
    const map: Plain = isPlain(own(copy, ref.key)) ? (own(copy, ref.key) as Plain) : {};
    if (item === undefined) delete map[ref.id];
    else setOwn(map, ref.id, item);
    setOwn(copy, ref.key, map);
    return copy;
  }
  const found = own(copy, ref.key);
  const list = Array.isArray(found) ? found : [];
  const at = listFind(list, own<string>(LISTS, ref.key) ?? "id", ref.id);
  if (item === undefined) {
    if (at >= 0) list.splice(at, 1);
  } else if (at >= 0) list[at] = item;
  else list.splice(Math.min(index ?? list.length, list.length), 0, item);
  setOwn(copy, ref.key, list);
  return copy;
}

/** `model` with the item of `item` as it is in the baseline (Reject). */
export function restore(model: Model, item: Change): Model {
  return putItem(model, item.ref, item.before, item.index);
}

/** The baseline with the item of `item` as it is in the model shown (Accept). */
export function adopt(baseline: Model, item: Change): Model {
  return putItem(baseline, item.ref, item.after);
}

/**
 * The baseline after one of the user's own writes, `before` to `after`: each item that
 * write changed is taken into the baseline as the write left it, so the user's changes
 * are never marked, and a marked item the user changed is the user's from then on.
 */
export function absorb(baseline: Model, before: Model, after: Model): Model {
  return changesBetween(before, after).reduce(
    (model, item) => putItem(model, item.ref, item.after),
    baseline,
  );
}

export interface FieldChange {
  path: string;
  before: unknown;
  after: unknown;
}

/** The leaves that differ between two items, as JSON Pointers into the item. */
export function fieldChanges(before: unknown, after: unknown, at: string[] = []): FieldChange[] {
  if (isPlain(before) && isPlain(after)) {
    const keys = [
      ...Object.keys(before),
      ...Object.keys(after).filter((key) => !hasOwn(before, key)),
    ];
    return keys.flatMap((key) => fieldChanges(own(before, key), own(after, key), [...at, key]));
  }
  return sameValue(before, after) ? [] : [{ path: pointer(at), before, after }];
}

const NOUNS: Readonly<Record<string, Readonly<Record<string, string>>>> = Object.assign(
  record<Readonly<Record<string, string>>>(),
  {
    process: Object.assign(record<string>(), {
      components: "block",
      connections: "connection",
      parameters: "parameter",
      experiments: "experiment",
      objectives: "objective",
      constraints: "constraint",
    }),
    optimization: Object.assign(record<string>(), {
      variables: "decision",
      constraints: "limit",
      objective: "the goal",
    }),
  },
);

/** What a change is about, in the model's words: "block till", "the goal", "meta". */
export function changeSubject(item: Change, domain: unknown): string {
  const { ref } = item;
  const nouns = own<Record<string, string>>(NOUNS, String(domain)) ?? own(NOUNS, "process");
  const noun = own<string>(nouns, ref.key) ?? ref.key;
  return ref.kind === "top" ? noun : `${noun} ${ref.id}`;
}

function valueText(value: unknown): string {
  return value === undefined ? "(none)" : shown(value);
}

/** A field's name for people: a block's setting without `/params`, else the path's words. */
export function fieldName(path: string): string {
  const inner = path.startsWith("/params/") ? path.slice("/params".length) : path;
  return inner.slice(1).replaceAll("/", " ") || "value";
}

const WORDS: Readonly<Record<ChangeKind, string>> = {
  added: "Added",
  changed: "Changed",
  removed: "Removed",
};

/** One line for a change: "Changed: block till (capacity: 1 → 2)". */
export function describeChange(item: Change, domain: unknown): string {
  const kind = changeKind(item);
  const subject = changeSubject(item, domain);
  if (kind !== "changed") return `${WORDS[kind]}: ${subject}`;
  const fields = fieldChanges(item.before, item.after);
  const parts = fields
    .slice(0, 3)
    .map(
      (field) => `${fieldName(field.path)}: ${valueText(field.before)} → ${valueText(field.after)}`,
    );
  if (fields.length > 3) parts.push(`${fields.length - 3} more`);
  return `${WORDS[kind]}: ${subject} (${parts.join("; ")})`;
}
