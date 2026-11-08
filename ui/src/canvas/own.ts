/**
 * Reading and writing objects keyed by names a model holds (component types, parameter and
 * decision names, coefficient keys, route and port names, clients). Such a name can be
 * `constructor`, `toString` or `__proto__`, which a plain `record[name]` or `name in
 * record` would find on `Object.prototype` (review of PR #46). Every lookup by such a name
 * goes through these helpers, which see only the object's own properties.
 */

/** Whether `record` is an object with an own property `key`. */
export function hasOwn(record: unknown, key: string): boolean {
  return typeof record === "object" && record !== null && Object.hasOwn(record, key);
}

/** `record[key]` when it is an own property, else `undefined`. */
export function own<T = unknown>(record: unknown, key: string): T | undefined {
  return hasOwn(record, key) ? ((record as Record<string, unknown>)[key] as T) : undefined;
}

/** Sets an own property, even one named `__proto__` (an assignment would set the prototype). */
export function setOwn(record: object, key: string, value: unknown): void {
  Object.defineProperty(record, key, {
    value,
    writable: true,
    enumerable: true,
    configurable: true,
  });
}

/** An empty record without a prototype, for names a model holds. */
export function record<T>(): Record<string, T> {
  return Object.create(null) as Record<string, T>;
}
