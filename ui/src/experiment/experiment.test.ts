/**
 * The Experiment screen's plans (spec 3 "Model edits"), built from the model shown.
 */
import { describe, expect, it } from "vitest";
import type { ComponentType, Model } from "../api/types";
import componentTypeFixture from "../test/component-types.json";
import { coffeeShop } from "../test/fakeModel";
import {
  addScenarioPlan,
  appendPlan,
  clearFieldPlan,
  experimentPointer,
  metricNames,
  nextName,
  parameterKind,
  renameObjectivePlan,
  scenarioColumns,
  scenariosOf,
  scenarioValuePlan,
  searchable,
  searchPlan,
  setFieldPlan,
  typedValue,
} from "./experiment";

const componentTypes = componentTypeFixture as unknown as Record<string, ComponentType>;

function withScenarios(): Model {
  const model = coffeeShop();
  model.parameters = {
    tills: { value: 1, type: "integer", min: 1, max: 5 },
    service: { value: "1.5 min", type: "quantity" },
  };
  model.experiments = [
    { id: "base", length: "8 h", replications: 30 },
    {
      id: "busy",
      length: "8 h",
      scenarios: [
        { id: "one", set: { tills: 1 } },
        { id: "two", set: { tills: 2, service: "1 min" } },
      ],
      search: { objective: "wait", variables: ["tills"] },
    },
  ];
  model.objectives = [{ id: "wait", metric: "till.wait.mean", sense: "minimize" }];
  return model;
}

describe("experiment fields", () => {
  it("types a time as text and a number by spec 1's grammar", () => {
    expect(typedValue("quantity", " 200 h ")).toBe("200 h");
    expect(typedValue("integer", "30")).toBe(30);
    expect(typedValue("number", "0.9")).toBe(0.9);
    // Text that is not a number goes as typed, so the service says what is wrong.
    expect(typedValue("integer", "thirty")).toBe("thirty");
    // A whole number the interface cannot hold exactly is never rounded.
    expect(typedValue("integer", "9223372036854775807")).toBe("9223372036854775807");
    expect(typedValue("integer", "9007199254740991")).toBe(9007199254740991);
  });

  it("sets one field of the experiment shown, and nothing for one that is gone", () => {
    const model = withScenarios();
    expect(setFieldPlan("base", "seed", 12345)(model)).toEqual([
      { edit: "set_experiment", id: "base", seed: 12345 },
    ]);
    expect(setFieldPlan("gone", "seed", 1)(model)).toBeNull();
  });

  it("clears a field by writing the whole model without it", () => {
    const model = withScenarios();
    const cleared = clearFieldPlan("base", "replications")(model);
    expect(cleared?.experiments?.[0]).toEqual({ id: "base", length: "8 h" });
    expect(model.experiments?.[0]?.replications).toBe(30);
    expect(clearFieldPlan("base", "seed")(model)).toBeNull();
    expect(clearFieldPlan("gone", "seed")(model)).toBeNull();
  });

  it("names a new item one more than the highest number of its form", () => {
    expect(nextName([], "objective")).toBe("objective_1");
    expect(nextName(["objective_2", "objective_x", "other_7"], "objective")).toBe("objective_3");
  });

  it("points at the first experiment of an id", () => {
    expect(experimentPointer(withScenarios(), "busy")).toBe("/experiments/1");
    expect(experimentPointer(withScenarios(), "none")).toBeNull();
  });
});

describe("scenarios", () => {
  it("shows a column for every parameter and any other name a set holds", () => {
    const model = withScenarios();
    const scenarios = scenariosOf(model.experiments?.[1]);
    expect(scenarios.map((item) => item.id)).toEqual(["one", "two"]);
    expect(scenarioColumns(model, scenarios)).toEqual(["tills", "service"]);
    expect(scenarioColumns(model, [{ id: "x", set: { unknown: 1, constructor: 2 } }])).toEqual([
      "tills",
      "service",
      "unknown",
      "constructor",
    ]);
    expect(scenariosOf(undefined)).toEqual([]);
    expect(scenariosOf({ id: "a", scenarios: [null, { id: 1 }, { id: "b", set: {} }] })).toEqual([
      { id: "b", set: {} },
    ]);
  });

  it("writes a parameter's value by its type", () => {
    const model = withScenarios();
    expect(parameterKind(model, "service")).toBe("quantity-parameter");
    expect(parameterKind(model, "tills")).toBe("integer");
    expect(parameterKind(model, "constructor")).toBe("number");
    expect(typedValue(parameterKind(model, "service"), "2 min")).toBe("2 min");
  });

  it("changes one value and keeps the rest of the set; an empty cell leaves it out", () => {
    const model = withScenarios();
    expect(scenarioValuePlan("busy", "two", "tills", 3)(model)).toEqual([
      {
        edit: "set_scenario",
        experiment_id: "busy",
        id: "two",
        set: { tills: 3, service: "1 min" },
      },
    ]);
    expect(scenarioValuePlan("busy", "two", "service", undefined)(model)).toEqual([
      { edit: "set_scenario", experiment_id: "busy", id: "two", set: { tills: 2 } },
    ]);
    // Leaving out what the set does not hold sends nothing.
    expect(scenarioValuePlan("busy", "one", "service", undefined)(model)).toBeNull();
    expect(scenarioValuePlan("busy", "gone", "tills", 1)(model)).toBeNull();
    // A parameter named like an Object property is an ordinary name.
    const named = scenarioValuePlan("busy", "one", "constructor", 4)(model);
    expect(JSON.parse(JSON.stringify(named))).toEqual([
      { edit: "set_scenario", experiment_id: "busy", id: "one", set: { tills: 1, constructor: 4 } },
    ]);
  });

  it("adds a scenario with an empty set, never over one of the same id", () => {
    const model = withScenarios();
    expect(addScenarioPlan("base", "faster")(model)).toEqual([
      { edit: "set_scenario", experiment_id: "base", id: "faster", set: {} },
    ]);
    expect(addScenarioPlan("busy", "one")(model)).toBeNull();
    expect(addScenarioPlan("gone", "x")(model)).toBeNull();
  });
});

describe("objectives, constraints and the search", () => {
  it("lists the metrics of each block's type, and the model's", () => {
    expect(metricNames(coffeeShop(), componentTypes)).toEqual([
      "arrivals.created",
      "arrivals.discarded",
      "till.wait.mean",
      "till.utilization",
      "till.availability",
      "till.scheduled_fraction",
      "till.queue_length.mean",
      "till.queue_length.max",
      "exit.throughput",
      "exit.cycle_time.mean",
      "exit.count",
      "model.wip.mean",
    ]);
  });

  it("appends to a list, creating it when absent", () => {
    const model = withScenarios();
    const item = { id: "c", metric: "till.utilization", op: "<=", value: 0.85 };
    expect(appendPlan("objectives", item)(model)).toEqual([
      { edit: "set_path", path: "/objectives/-", value: item },
    ]);
    expect(appendPlan("constraints", item)(model)).toEqual([
      { edit: "set_path", path: "/constraints", value: [item] },
    ]);
  });

  it("sets and removes inside an experiment's search, sending nothing for what is absent", () => {
    const model = withScenarios();
    expect(searchPlan("busy", ["budget"], 20)(model)).toEqual([
      { edit: "set_path", path: "/experiments/1/search/budget", value: 20 },
    ]);
    expect(searchPlan("busy", ["variables"], undefined)(model)).toEqual([
      { edit: "remove_path", path: "/experiments/1/search/variables" },
    ]);
    expect(searchPlan("busy", ["budget"], undefined)(model)).toBeNull();
    expect(searchPlan("base", [], { objective: "wait" })(model)).toEqual([
      { edit: "set_path", path: "/experiments/0/search", value: { objective: "wait" } },
    ]);
    expect(searchPlan("base", [], undefined)(model)).toBeNull();
    expect(searchPlan("gone", [], undefined)(model)).toBeNull();
  });

  it("lists the parameters a search can vary: those with a min and a max", () => {
    expect(searchable(withScenarios())).toEqual(["tills"]);
  });

  it("renames an objective with every search that names it", () => {
    const model = withScenarios();
    expect(renameObjectivePlan(0, "queue")(model)).toEqual([
      { edit: "set_path", path: "/objectives/0/id", value: "queue" },
      { edit: "set_path", path: "/experiments/1/search/objective", value: "queue" },
    ]);
    expect(renameObjectivePlan(0, "wait")(model)).toBeNull();
    expect(renameObjectivePlan(3, "x")(model)).toBeNull();
    // A name another objective has: only the id, and the service reports the duplicate.
    model.objectives = [
      ...(model.objectives as unknown[]),
      { id: "cost", metric: "x", sense: "minimize" },
    ];
    expect(renameObjectivePlan(0, "cost")(model)).toEqual([
      { edit: "set_path", path: "/objectives/0/id", value: "cost" },
    ]);
  });
});
