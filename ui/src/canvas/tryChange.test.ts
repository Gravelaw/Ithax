/**
 * "Try a change" (`canvas-interactions.md` "Trying a change"): one batch that makes a field
 * a parameter and adds the option as a scenario, keeping the current model as a baseline.
 */
import { describe, expect, it } from "vitest";
import type { Model } from "../api/types";
import { coffeeShop } from "../test/fakeModel";
import { triedValue, tryChangeEdits } from "./tryChange";

const plan = {
  component: "till",
  segments: ["service", "mean"],
  kind: "quantity" as const,
  experiment: "base",
  option: "Faster coffee machine",
  tried: "1.2 min",
};

describe("the value tried", () => {
  it("is written as the parameter's type", () => {
    expect(triedValue("quantity", " 1.2 min ")).toBe("1.2 min");
    expect(triedValue("integer", "3")).toBe(3);
  });
});

describe("the batch", () => {
  it("creates the parameter, links the field, keeps a baseline and adds the option", () => {
    expect(tryChangeEdits(coffeeShop(), plan)).toEqual([
      { edit: "set_parameter", id: "till_service_mean", value: "1.5 min", type: "quantity" },
      {
        edit: "set_setting",
        id: "till",
        path: "/service/mean",
        value: { $param: "till_service_mean" },
      },
      { edit: "set_scenario", experiment_id: "base", id: "baseline", set: {} },
      {
        edit: "set_scenario",
        experiment_id: "base",
        id: "faster_coffee_machine",
        set: { till_service_mean: "1.2 min" },
      },
    ]);
  });

  it("adds only the option for a field already linked, to an experiment with scenarios", () => {
    const model = coffeeShop();
    model.experiments = [
      { id: "base", length: "8 h", scenarios: [{ id: "faster_coffee_machine", set: {} }] },
    ];
    expect(
      tryChangeEdits(model, { ...plan, segments: ["capacity"], kind: "integer", tried: "2" }),
    ).toEqual([
      {
        edit: "set_scenario",
        experiment_id: "base",
        id: "faster_coffee_machine_2",
        set: { tills: 2 },
      },
    ]);
  });

  it("never takes a name in use: a parameter, `default`, or a baseline taken", () => {
    const model: Model = coffeeShop();
    model.parameters = {
      ...model.parameters,
      till_service_mean: { value: "9 min", type: "quantity" },
    };
    const edits = tryChangeEdits(model, { ...plan, option: "default" });
    expect(edits?.[0]).toMatchObject({ id: "till_service_mean_2" });
    expect(edits?.[3]).toMatchObject({ id: "default_2", set: { till_service_mean_2: "1.2 min" } });
  });

  it("keeps every id it makes within spec 1's identifier rule, for a 60-character block id", () => {
    const long = `b${"x".repeat(59)}`;
    const model = coffeeShop();
    const till = model.components?.find((item) => item.id === "till");
    if (till) till.id = long;
    // `<block>_service_mean` is 73 characters: cut to 64, which is taken here, so `_2`.
    const cutName = `${long}_ser`;
    model.parameters = { ...model.parameters, [cutName]: { value: 1, type: "number" } };
    const edits = tryChangeEdits(model, {
      ...plan,
      component: long,
      option: `A ${"very ".repeat(20)}long option`,
    }) as { id?: string; value?: unknown }[];
    const ids = [edits[0]?.id, edits[2]?.id, edits[3]?.id];
    for (const id of ids) expect(id).toMatch(/^[a-z][a-z0-9_]{0,63}$/);
    expect(ids[0]).toBe(`${long}_s_2`);
    expect(edits[1]).toMatchObject({ value: { $param: ids[0] } });
    expect(ids[2]).toHaveLength(64);
  });

  it("sends nothing for a block, experiment or value that is not in the model shown", () => {
    expect(tryChangeEdits(coffeeShop(), { ...plan, component: "gone" })).toBeNull();
    expect(tryChangeEdits(coffeeShop(), { ...plan, experiment: "gone" })).toBeNull();
    expect(tryChangeEdits(coffeeShop(), { ...plan, segments: ["queue_capacity"] })).toBeNull();
  });
});
