/**
 * A template's lesson as the interface reads it (spec 4 "Template package" and "Learn and
 * Build modes"; AKS-124).
 *
 * `parseLesson` reads `lesson.md` by the rules `ithax.templates.lesson` checks: a first
 * line `# <title>`, one `## <heading>` section per step, each starting with
 * ``Component: `<id>` ``, and a last step whose text is the three parts `### Change`,
 * `### Prediction` (choices `- [ ] <text>` and one `- [x] <text>`) and `### Explanation`.
 * The service serves only packages that keep these rules, so a lesson it serves always
 * reads; anything else gives `null`. Word limits are the loader's to check, not the
 * interface's.
 *
 * `changeRows` and `changeMade` read the exercise's edits (`template.json` `exercise`)
 * against the model shown: what each edit sets, what the model holds now, and whether the
 * model already holds the change (so a change made by hand counts, and an undo takes it
 * back).
 */
import type { Edit, Model } from "../api/types";
import { components, valueAt, words } from "../canvas/model";
import { hasOwn, own } from "../canvas/own";

export interface LessonStep {
  heading: string;
  /** What the step highlights: a component, or a variable, a constraint or `objective`. */
  component: string;
  text: string;
}

export interface Choice {
  text: string;
  right: boolean;
}

export interface Exercise extends LessonStep {
  change: string;
  choices: Choice[];
  explanation: string;
}

export interface Lesson {
  title: string;
  steps: LessonStep[];
  exercise: Exercise;
}

const COMPONENT = /^Component: `([^`]+)`$/;
const CHOICE = /^- \[( |x)\] (\S.*)$/;
const PARTS = ["Change", "Prediction", "Explanation"] as const;

interface Section {
  heading: string;
  lines: string[];
}

function sections(lines: readonly string[], marker: string): [string[], Section[]] {
  const before: string[] = [];
  const found: Section[] = [];
  for (const line of lines) {
    if (line.startsWith(marker))
      found.push({ heading: line.slice(marker.length).trim(), lines: [] });
    else if (found.length > 0) found[found.length - 1]?.lines.push(line);
    else before.push(line);
  }
  return [before, found];
}

function joined(lines: readonly string[]): string {
  return lines.join("\n").trim();
}

/** The step's component and the lines after its `Component:` line; `null` without one. */
function component(section: Section): [string, string[]] | null {
  const first = section.lines.findIndex((line) => line.trim() !== "");
  if (first < 0) return null;
  const match = COMPONENT.exec(section.lines[first]?.trim() ?? "");
  if (match === null || match[1] === undefined) return null;
  return [match[1], section.lines.slice(first + 1)];
}

export function parseLesson(text: string): Lesson | null {
  const lines = text.split(/\r?\n/);
  const head = lines[0] ?? "";
  const title = head.startsWith("# ") ? head.slice(2).trim() : "";
  if (title === "") return null;
  const [before, steps] = sections(lines.slice(1), "## ");
  if (joined(before) !== "" || steps.length < 2) return null;
  const read: LessonStep[] = [];
  for (const section of steps.slice(0, -1)) {
    const found = component(section);
    if (found === null || found[1].some((line) => line.startsWith("### "))) return null;
    read.push({ heading: section.heading, component: found[0], text: joined(found[1]) });
  }
  const last = steps[steps.length - 1] as Section;
  const found = component(last);
  if (!last.heading.startsWith("Exercise") || found === null) return null;
  const [intro, parts] = sections(found[1], "### ");
  if (joined(intro) !== "" || parts.map((part) => part.heading).join("|") !== PARTS.join("|")) {
    return null;
  }
  const choices: Choice[] = [];
  for (const line of parts[1]?.lines ?? []) {
    const trimmed = line.trim();
    if (trimmed === "") continue;
    const match = CHOICE.exec(trimmed);
    if (match === null || match[2] === undefined) return null;
    choices.push({ text: match[2].trim(), right: match[1] === "x" });
  }
  if (choices.length < 2 || choices.filter((choice) => choice.right).length !== 1) return null;
  return {
    title,
    steps: read,
    exercise: {
      heading: last.heading,
      component: found[0],
      text: "",
      change: joined(parts[0]?.lines ?? []),
      choices,
      explanation: joined(parts[2]?.lines ?? []),
    },
  };
}

/** A paragraph's parts: plain text, and code (text between backticks). */
export type Inline = { code: boolean; text: string };

/** Text as paragraphs (split at blank lines), each as plain and code parts. */
export function paragraphs(text: string): Inline[][] {
  return text
    .split(/\n\s*\n/)
    .map((block) => block.replace(/\s*\n\s*/g, " ").trim())
    .filter((block) => block !== "")
    .map((block) =>
      block
        .split("`")
        .map((part, index) => ({ code: index % 2 === 1, text: part }))
        .filter((part) => part.text !== ""),
    );
}

function segments(path: string): string[] {
  return path
    .split("/")
    .slice(1)
    .map((part) => part.replace(/~1/g, "/").replace(/~0/g, "~"));
}

function equal(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== "object" || typeof b !== "object" || a === null || b === null) return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  return (
    keysA.length === keysB.length &&
    keysA.every((key) => hasOwn(b, key) && equal(own(a, key), own(b, key)))
  );
}

/** One edit of the exercise: where it changes the model, the value there now, the value it sets. */
export interface ChangeRow {
  where: string;
  /** The value the model shown holds; `undefined` when it holds none. */
  now: unknown;
  to: unknown;
}

/** The values the edit would compare, or `null` for an edit whose kind is not read here. */
function readEdit(model: Model, edit: Edit): { pairs: ChangeRow[] } | null {
  const fields = edit as Record<string, unknown>;
  if (edit.edit === "set_parameter") {
    const id = String(fields.id);
    const parameter = own<Record<string, unknown>>(
      (model.parameters ?? {}) as Record<string, unknown>,
      id,
    );
    const pairs = ["value", "type", "min", "max"]
      .filter((key) => hasOwn(fields, key))
      .map((key) => ({
        where: key === "value" ? id : `${id}: ${key}`,
        now: parameter === undefined ? undefined : own(parameter, key),
        to: fields[key],
      }));
    return { pairs };
  }
  if (edit.edit === "set_setting") {
    const id = String(fields.id);
    const path = String(fields.path);
    const found = components(model).find((item) => item.id === id);
    const now = found === undefined ? undefined : valueAt(found.params, segments(path));
    return { pairs: [{ where: `${id}: ${segments(path).join(" ")}`, now, to: fields.value }] };
  }
  if (edit.edit === "set_path") {
    const path = String(fields.path);
    const at = segments(path);
    return { pairs: [{ where: placeWords(model, at), now: valueAt(model, at), to: fields.value }] };
  }
  return null;
}

/** Each value the exercise's edits set, beside the value the model shown holds there. */
export function changeRows(model: Model, edits: readonly Edit[]): ChangeRow[] {
  return edits.flatMap(
    (edit) =>
      readEdit(model, edit)?.pairs ?? [{ where: words(edit.edit), now: undefined, to: edit }],
  );
}

/**
 * Whether the model shown holds the exercise's change: `true` or `false` when every edit is
 * of a kind read here, `null` when one is not (it then counts once its button was accepted).
 */
export function changeMade(model: Model, edits: readonly Edit[]): boolean | null {
  let made = true;
  for (const edit of edits) {
    const read = readEdit(model, edit);
    if (read === null) return null;
    if (!read.pairs.every((pair) => equal(pair.now, pair.to))) made = false;
  }
  return made;
}

/** A value as the step card shows it, in words (#91): `{dist, mean}` is "exponential, mean 1 min". */
export function valueText(value: unknown): string {
  if (value === undefined) return "not set";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(valueText).join(", ");
  if (typeof value !== "object" || value === null) return JSON.stringify(value);
  const entries = Object.entries(value);
  const param = own(value, "$param");
  if (typeof param === "string" && entries.length === 1) return `= ${param}`;
  return entries
    .map(([key, item]) => (key === "dist" ? valueText(item) : `${key} ${valueText(item)}`))
    .join(", ");
}

/** A list entry by its `name` or `id`, else its place counted from 1. */
function entryName(list: unknown, index: string): string {
  const entry = Array.isArray(list) ? list[Number(index)] : undefined;
  const name = entry === undefined ? undefined : (own(entry, "name") ?? own(entry, "id"));
  return typeof name === "string" ? name : String(Number(index) + 1);
}

/**
 * A place in the model in words, not a JSON pointer (#91): an objective's or a limit's
 * coefficient and a limit's right-hand side by name; else each part in words, a list entry
 * by its name.
 */
function placeWords(model: Model, at: readonly string[]): string {
  const [top, index, key, variable] = at;
  if (top === "objective" && index === "linear" && at.length === 3) {
    return `objective coefficient of ${key}`;
  }
  const list = (model as Record<string, unknown>)[top ?? ""];
  if (top === "constraints" && index !== undefined && Array.isArray(list) && list[Number(index)]) {
    const name = entryName(list, index);
    if (key === "rhs" && at.length === 3) return `${name}: limit`;
    if (key === "linear" && at.length === 4) return `${name}: coefficient of ${variable}`;
  }
  let here: unknown = model;
  return at
    .map((part) => {
      const shown = Array.isArray(here) ? entryName(here, part) : part === "rhs" ? "limit" : part;
      here = here !== null && typeof here === "object" ? own(here, part) : undefined;
      return shown;
    })
    .join(" › ");
}
