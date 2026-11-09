/**
 * "Try a change" (`docs/design/canvas-interactions.md` "Trying a change"; AKS-136 reading 17,
 * built at AKS-120): beside a number or time field in the side panel, one action makes the
 * field a parameter and adds a scenario that sets the parameter to the value tried, on the
 * experiment chosen in the top bar. It is one batch of edits, so one write and one undo
 * step under the one-write rule, built from the model shown:
 *
 * 1. `set_parameter` creating a parameter named from the block and the field
 *    (`till_service_mean`, then `_2`, `_3` when taken; `identifiers.ts` keeps every
 *    generated id within spec 1's identifier rule) with the field's value and the type
 *    the field takes (`quantity` for a time, `integer` for a whole number, else `number`);
 * 2. `set_setting` linking the field to it (`{"$param": ...}`) at the field itself;
 * 3. when the experiment has no scenarios of its own, `set_scenario` adding `baseline` (or
 *    `baseline_2`, ...) with an empty `set`, so the current model stays one side of the
 *    comparison;
 * 4. `set_scenario` adding the option, its id made from the name typed (an identifier:
 *    lower case, other characters as `_`), never one already taken or `default`.
 *
 * A field already linked to a parameter adds only the scenarios.
 */
import type { Edit, Model } from "../api/types";
import { identifier } from "./identifiers";
import { components, paramOf, readNumber, settingEdit, valueAt } from "./model";
import { hasOwn, own } from "./own";

export type ParameterKind = "quantity" | "integer" | "number";

/** The value tried, as the parameter's type writes it. */
export function triedValue(type: unknown, text: string): unknown {
  return type === "quantity" ? text.trim() : readNumber(text);
}

export interface TryPlan {
  component: string;
  segments: readonly (string | number)[];
  kind: ParameterKind;
  experiment: string;
  option: string;
  tried: string;
}

/** The batch of "Try a change", from the model shown; `null` sends nothing. */
export function tryChangeEdits(model: Model, plan: TryPlan): Edit[] | null {
  const component = components(model).find((item) => item.id === plan.component);
  const experiment = (Array.isArray(model.experiments) ? model.experiments : []).find(
    (item) => item.id === plan.experiment,
  );
  if (component === undefined || experiment === undefined) return null;
  const current = valueAt(component.params, plan.segments);
  if (current === undefined) return null;
  const edits: Edit[] = [];
  let parameter = paramOf(current);
  if (parameter === null) {
    parameter = identifier(
      [plan.component, ...plan.segments.map(String)].join("_"),
      Object.keys(model.parameters ?? {}),
      "parameter",
    );
    edits.push({ edit: "set_parameter", id: parameter, value: current, type: plan.kind });
    edits.push(settingEdit(component, plan.segments, { $param: parameter }));
  }
  const type = hasOwn(model.parameters, parameter)
    ? own<{ type?: unknown }>(model.parameters, parameter)?.type
    : plan.kind;
  const listed = Array.isArray(experiment.scenarios) ? experiment.scenarios : [];
  const taken = [
    "default",
    ...listed
      .map((item) => (item as { id?: unknown })?.id)
      .filter((id): id is string => typeof id === "string"),
  ];
  if (listed.length === 0) {
    const baseline = identifier("baseline", taken, "baseline");
    taken.push(baseline);
    edits.push({ edit: "set_scenario", experiment_id: plan.experiment, id: baseline, set: {} });
  }
  const set: Record<string, unknown> = Object.create(null);
  Object.defineProperty(set, parameter, {
    value: triedValue(type, plan.tried),
    enumerable: true,
    writable: true,
    configurable: true,
  });
  edits.push({
    edit: "set_scenario",
    experiment_id: plan.experiment,
    id: identifier(plan.option, taken, "option"),
    set,
  });
  return edits;
}
