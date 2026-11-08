/** Reading `summary.json` (spec 1, spec 2) for the Results screen, defensively. */
import { describe, expect, it } from "vitest";
import { aRun, lineSummary, optionsSummary, planSummary, RID, searchSummary } from "../test/runs";
import {
  differencesOf,
  estimateOf,
  footerOf,
  kindOf,
  metricsOf,
  NO_WARRANTY,
  scenariosOf,
  searchOf,
  solutionOf,
} from "./summary";

describe("summary.json", () => {
  it("tells the run kinds apart", () => {
    expect(kindOf(lineSummary())).toBe("process");
    expect(kindOf(searchSummary())).toBe("search");
    expect(kindOf(planSummary())).toBe("optimization");
  });

  it("reads estimates of spec 1's shape only", () => {
    expect(estimateOf({ mean: 1, half_width: null, unit: "s", n: 2 })).toEqual({
      mean: 1,
      half_width: null,
      unit: "s",
      n: 2,
    });
    expect(estimateOf({ mean: "1", half_width: 0, unit: "s", n: 2 })).toBeNull();
    expect(estimateOf({ mean: 1, half_width: 0, unit: 1, n: 2 })).toBeNull();
    expect(estimateOf([1])).toBeNull();
    expect(metricsOf({ a: { mean: 1, half_width: 0, unit: "1", n: 1 }, b: 3 })).toHaveLength(1);
    expect(metricsOf(null)).toEqual([]);
  });

  it("reads scenarios and their differences in order", () => {
    const scenarios = scenariosOf(optionsSummary());
    expect(scenarios.map((scenario) => scenario.id)).toEqual(["default", "faster"]);
    expect(scenarios[0]?.metrics.map(([name]) => name)).toContain("weld.wait.mean");
    expect(scenariosOf({ scenarios: { odd: 3 } })).toEqual([{ id: "odd", metrics: [] }]);
    expect(scenariosOf(planSummary())).toEqual([]);
    const [difference] = differencesOf(optionsSummary());
    expect(difference?.scenario).toBe("faster");
    expect(difference?.metrics.map((item) => [item.name, item.separated])).toEqual([
      ["weld.wait.mean", true],
      ["weld.utilization", false],
    ]);
    expect(
      differencesOf({ differences: [3, { scenario: 1 }, { scenario: "a", against: "b" }] }),
    ).toEqual([{ scenario: "a", against: "b", metrics: [] }]);
    expect(differencesOf({})).toEqual([]);
  });

  it("reads every trial of a search, the best marked", () => {
    const search = searchOf(searchSummary());
    expect(search?.metric).toBe("till.wait.mean");
    expect(search?.variables).toEqual(["tills"]);
    expect(
      search?.trials.map((trial) => [trial.index, trial.best, trial.feasible, trial.confirmed]),
    ).toEqual([
      [0, false, true, true],
      [1, true, true, true],
      [2, false, false, false],
    ]);
    expect(search?.after).toBe(14.7);
    const infeasible = searchSummary();
    (infeasible.search as Record<string, unknown>).status = "infeasible";
    expect(searchOf(infeasible)?.trials.some((trial) => trial.best)).toBe(false);
    expect(searchOf({ search: { objective: { metric: 3 } } })).toBeNull();
    expect(
      searchOf({
        search: { objective: { metric: "m" }, candidates: [3, { set: { constructor: 1 } }] },
      }),
    ).toEqual({
      status: "",
      metric: "m",
      before: null,
      after: null,
      separated: false,
      variables: ["constructor"],
      trials: [
        {
          index: 1,
          set: { constructor: 1 },
          objective: null,
          feasible: false,
          confirmed: false,
          best: false,
        },
      ],
    });
  });

  it("reads an optimization's solution", () => {
    expect(solutionOf(planSummary())).toEqual({
      status: "optimal",
      objective: 2200,
      variables: [
        ["chairs", 24],
        ["tables", 14],
      ],
      limits: [
        { name: "wood", tight: true, slack: 0 },
        { name: "labour", tight: true, slack: 0 },
      ],
    });
    expect(solutionOf({ constraints: { a: 3 } })).toEqual({
      status: "",
      objective: null,
      variables: [],
      limits: [],
    });
  });

  it("gives every footer item", () => {
    expect(footerOf(lineSummary(), aRun())).toEqual([
      "Model: Three-machine line",
      `Run: ${RID}`,
      "Fidelity: Standard: 30 replications of 100 h, 95% confidence",
      "Replications: 30 · Confidence: 95%",
      "Engine: simpy 0.0.0",
      NO_WARRANTY,
    ]);
    expect(NO_WARRANTY).toBe("Simulation results are estimates and carry no warranty.");
    const plan = footerOf(planSummary(), aRun({ engine: { name: "highs", version: null } }));
    expect(plan[3]).toBe("Replications and confidence: not replicated");
    expect(plan[4]).toBe("Engine: highs");
    const bare = footerOf({}, aRun({ engine: null }));
    expect(bare[0]).toBe("Model: not recorded");
    expect(bare[2]).toBe("Fidelity: not recorded");
    expect(bare[4]).toBe("Engine: not recorded");
  });
});
