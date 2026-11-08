/**
 * How a Canvas action becomes a write (review of PR #45).
 *
 * An action waits in `CanvasSession`'s queue behind the writes asked before it. So nothing
 * it sends may be decided from the model as it was drawn: an edit is a plan, built when it
 * is sent, from the model as the earlier writes left it, and every component id the action
 * named is resolved then through `resolve`, which follows the renames applied since the
 * action was asked (a rename of `till` to `counter` queued before a label of `till` makes
 * the label go to `counter`). A plan whose component is gone is not dropped: it is sent
 * naming it, and the service refuses it (E180), which the canvas shows.
 */
import type { Component, Edit, Model } from "../api/types";
import { components, pointer, settingEdit, splitEnd, valueAt, withoutSetting } from "./model";
import type { Plan } from "./session";

/** The id a component named when the action was asked has now. */
export type Resolve = (id: string) => string;

/** Edits, or a plan that builds them when the write is sent; `null` or `[]` sends nothing. */
export type EditPlan = Edit[] | ((model: Model, resolve: Resolve) => Edit[] | null);

export function componentIn(model: Model, id: string): Component | undefined {
  return components(model).find((item) => item.id === id);
}

/**
 * The edit sent for a component that is gone when the write is sent: one the service
 * cannot apply (spec 3 "Model edits": an unknown id is E180), so the batch is refused,
 * nothing changes, and the canvas shows the service's own issue.
 */
export function gone(id: string): Edit[] {
  return [{ edit: "set_label", id, label: null }];
}

function end(text: string, resolve: Resolve): string {
  const split = splitEnd(text);
  return split ? `${resolve(split[0])}.${split[1]}` : text;
}

/** Every component an edit names, resolved: ids, connection ends, `pool` and `target`. */
export function resolveEdits(edits: Edit[], resolve: Resolve): Edit[] {
  return edits.map((edit): Edit => {
    switch (edit.edit) {
      case "remove_component":
      case "rename_component":
      case "set_ui":
      case "set_label":
        return { ...edit, id: resolve(edit.id) };
      case "set_setting":
        return {
          ...edit,
          id: resolve(edit.id),
          value:
            (edit.path === "/pool" || edit.path === "/target") && typeof edit.value === "string"
              ? resolve(edit.value)
              : edit.value,
        };
      case "connect":
        return { ...edit, from: end(edit.from, resolve), to: end(edit.to, resolve) };
      case "disconnect":
        return { ...edit, from: end(edit.from, resolve) };
      default:
        return edit;
    }
  });
}

/** The session's plan for one action of edits. */
export function editsWrite(label: string, edits: EditPlan): Plan {
  return (model, resolve) => {
    const built = typeof edits === "function" ? edits(model, resolve) : edits;
    if (built === null || built.length === 0) return null;
    return { kind: "edits", label, edits: resolveEdits(built, resolve) };
  };
}

/** The session's plan for one action that writes a whole model; `null` sends nothing. */
export function modelWrite(
  label: string,
  build: (model: Model, resolve: Resolve) => Model | Edit[] | null,
): Plan {
  return (model, resolve) => {
    const built = build(model, resolve);
    if (built === null) return null;
    if (Array.isArray(built)) return { kind: "edits", label, edits: built };
    return { kind: "model", label, model: built };
  };
}

/**
 * Sets the value at `segments` of a component's `params`, built when sent: the path
 * depends on what exists then. A function value is given the value there at that moment;
 * `undefined` sends nothing.
 */
export function settingPlan(
  id: string,
  segments: readonly (string | number)[],
  value: unknown | ((current: unknown) => unknown),
): EditPlan {
  return (model, resolve) => {
    const component = componentIn(model, resolve(id));
    if (component === undefined) return gone(resolve(id));
    const next =
      typeof value === "function"
        ? (value as (current: unknown) => unknown)(valueAt(component.params, segments))
        : value;
    return next === undefined ? null : [settingEdit(component, segments, next)];
  };
}

/** Clears the value at `segments`, if the component holds one when the write is sent. */
export function clearPlan(
  id: string,
  segments: readonly (string | number)[],
): (model: Model, resolve: Resolve) => Model | Edit[] | null {
  return (model, resolve) => {
    const component = componentIn(model, resolve(id));
    if (component === undefined) return gone(resolve(id));
    if (valueAt(component.params, segments) === undefined) return null;
    return withoutSetting(model, component.id, segments);
  };
}

/** The label of `pointer(segments)` for an undo step. */
export function settingLabel(id: string, segments: readonly (string | number)[]): string {
  return `set ${id}${pointer(segments)}`;
}
