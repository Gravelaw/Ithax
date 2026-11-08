/**
 * How a Canvas action becomes a write. The session takes one write at a time and refuses
 * changes while one awaits its answer, so a plan is built from the model the user sees.
 */
import type { Component, Edit, Model } from "../api/types";
import { components, pointer, settingEdit, valueAt, withoutSetting } from "./model";
import type { Plan } from "./session";

/** Edits, or a plan that builds them from the model shown; `null` or `[]` sends nothing. */
export type EditPlan = Edit[] | ((model: Model) => Edit[] | null);

export function componentIn(model: Model, id: string): Component | undefined {
  return components(model).find((item) => item.id === id);
}

/** The session's plan for one action of edits. */
export function editsWrite(label: string, edits: EditPlan): Plan {
  return (model) => {
    const built = typeof edits === "function" ? edits(model) : edits;
    if (built === null || built.length === 0) return null;
    return { kind: "edits", label, edits: built };
  };
}

/** The session's plan for one action that writes a whole model; `null` sends nothing. */
export function modelWrite(label: string, build: (model: Model) => Model | null): Plan {
  return (model) => {
    const built = build(model);
    return built === null ? null : { kind: "model", label, model: built };
  };
}

/**
 * Sets the value at `segments` of a component's `params`; the `set_setting` path depends
 * on what exists. A function value is given the value there now; `undefined` sends nothing.
 */
export function settingPlan(
  id: string,
  segments: readonly (string | number)[],
  value: unknown | ((current: unknown) => unknown),
): EditPlan {
  return (model) => {
    const component = componentIn(model, id);
    if (component === undefined) return null;
    const next =
      typeof value === "function"
        ? (value as (current: unknown) => unknown)(valueAt(component.params, segments))
        : value;
    return next === undefined ? null : [settingEdit(component, segments, next)];
  };
}

/** Clears the value at `segments`, if the component holds one. */
export function clearPlan(
  id: string,
  segments: readonly (string | number)[],
): (model: Model) => Model | null {
  return (model) => {
    const component = componentIn(model, id);
    if (component === undefined || valueAt(component.params, segments) === undefined) return null;
    return withoutSetting(model, id, segments);
  };
}

/** The label of a setting's change, for its undo step. */
export function settingLabel(id: string, segments: readonly (string | number)[]): string {
  return `set ${id}${pointer(segments)}`;
}
