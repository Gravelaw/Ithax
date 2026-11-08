/**
 * "Try a change" (`canvas-interactions.md` "Trying a change"): one batch that makes a field
 * a parameter and adds the option as a scenario, keeping the current model as a baseline.
 */
import { describe, expect, it } from "vitest";
import type { Model } from "../api/types";
import { coffeeShop } from "../test/fakeModel";
import { freeName, parameterName, scenarioId, triedValue, tryChangeEdits } from "./tryChange";

const plan = {
  component: "till",
  segments: ["service", "mean"],
  kind: "quantity" as const,
  experiment: "base",
  option: "Faster coffee machine",
  tried: "1.2 min",
};

describe("names", () => {
  it("takes the first free name", () => {
    expect(freeName([], "baseline")).toBe("baseline");
    expect(freeName(["baseline", "baseline_2"], "baseline")).toBe("baseline_3");
  });

  it("makes an option's name a scenario id", () => {
    expect(scenarioId("Faster coffee machine")).toBe("faster_coffee_machine");
    expect(scenarioId("  2 more tills! ")).toBe("option_2_more_tills");
    expect(scenarioId("???")).toBe("option");
    expect(scenarioId("a".repeat(80))).toHaveLength(64);
  });

  it("names a parameter from the block and the field", () => {
    expect(parameterName("till", ["service", "mean"])).toBe("till_service_mean");
    expect(parameterName("shifts", ["shifts", 0, "start"])).toBe("shifts_shifts_0_start");
  });

  it("writes the value tried as the parameter's type", () => {
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

  it("sends nothing for a block, experiment or value that is not in the model shown", () => {
    expect(tryChangeEdits(coffeeShop(), { ...plan, component: "gone" })).toBeNull();
    expect(tryChangeEdits(coffeeShop(), { ...plan, experiment: "gone" })).toBeNull();
    expect(tryChangeEdits(coffeeShop(), { ...plan, segments: ["queue_capacity"] })).toBeNull();
  });
});
