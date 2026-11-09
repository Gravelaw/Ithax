/**
 * The one way the interface makes an identifier from words or other ids (spec 1
 * "Identifiers": `^[a-z][a-z0-9_]{0,63}$`, unique in its list, `default` reserved for a
 * scenario). "Try a change" names a parameter from a block id and a field path, and a
 * scenario from the option's name; both come here, so a generated id is always one the
 * model takes (review of PR #47: a 60-character block id gave a 73-character parameter).
 */

/** The longest identifier spec 1 allows. */
export const MAX_IDENTIFIER = 64;

/** Words as an identifier's body: lower case, other characters as `_`, no `_` at the ends. */
function body(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

/** `text` cut to `length` characters, without a `_` at its end. */
function cut(text: string, length: number): string {
  return text.slice(0, length).replace(/_+$/, "");
}

/**
 * An identifier made from `text`, not in `taken`: its words as an identifier (with
 * `<fallback>_` before one that does not start with a letter, `fallback` alone for none),
 * at most 64 characters, and when that is taken the first of `_2`, `_3`, ... that is free,
 * the base cut short so the suffix always fits.
 */
export function identifier(text: string, taken: readonly string[], fallback: string): string {
  const words = body(text);
  const start = body(fallback) || "id";
  const base = words === "" ? start : /^[a-z]/.test(words) ? words : `${start}_${words}`;
  const first = cut(base, MAX_IDENTIFIER);
  if (!taken.includes(first)) return first;
  for (let n = 2; ; n += 1) {
    const suffix = `_${n}`;
    const candidate = `${cut(base, MAX_IDENTIFIER - suffix.length)}${suffix}`;
    if (!taken.includes(candidate)) return candidate;
  }
}
