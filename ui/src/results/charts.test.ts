/** The data and options of the Results charts (AKS-138). */
import { describe, expect, it } from "vitest";
import { optionsSummary, planSummary, searchSummary } from "../test/runs";
import {
  barGroups,
  barsOption,
  decisionsOption,
  overTime,
  overTimeOption,
  timeseriesMetrics,
  trialPoints,
  trialsOption,
} from "./charts";
import { scenariosOf, searchOf, solutionOf } from "./summary";

const colours = {
  series: ["#111111", "#222222", "#333333", "#444444"],
  text: "#555555",
  grid: "#666666",
};

type Series = {
  type: string;
  name?: string;
  data: unknown[];
  renderItem?: (params: unknown, api: unknown) => unknown;
  itemStyle?: { color: string };
};

describe("the bars of a run", () => {
  it("groups utilization and waits by component, per scenario, in display units", () => {
    const groups = barGroups(scenariosOf(optionsSummary()));
    expect(groups.map((group) => [group.family, group.unit, group.components])).toEqual([
      ["utilization", "Busy share (%)", ["cut", "weld"]],
      ["wait.mean", "Average wait (min)", ["cut", "weld"]],
    ]);
    const waits = groups[1];
    expect(waits?.scenarios).toEqual(["default", "faster"]);
    expect(waits?.values[0]?.[1]?.mean).toBeCloseTo(15.69, 2);
    expect(waits?.values[0]?.[1]?.half).toBeCloseTo(2.09, 2);
    expect(barGroups([{ id: "default", metrics: [] }])).toEqual([]);
    const sparse = barGroups([
      { id: "a", metrics: [["s.wait.mean", { mean: null, half_width: null, unit: "s", n: 0 }]] },
      { id: "b", metrics: [["s.wait.mean", { mean: 30, half_width: null, unit: "s", n: 2 }]] },
      { id: "c", metrics: [] },
    ]);
    expect(sparse[0]?.values).toEqual([[null], [{ mean: 30, half: null }], [null]]);
  });

  it("draws a bar series and a range series per scenario, ranges over their own bars", () => {
    const [group] = barGroups(scenariosOf(optionsSummary()));
    if (group === undefined) throw new Error("no group");
    const option = barsOption(group, colours);
    const series = option.series as Series[];
    expect(series.map((item) => item.type)).toEqual(["bar", "custom", "bar", "custom"]);
    expect((option.legend as { data: string[] }).data).toEqual(["default", "faster"]);
    const ranges = series[3];
    expect(ranges?.data).toHaveLength(2);
    const api = {
      value: (dimension: number) => [1, 80, 100][dimension] ?? 0,
      coord: ([x, y]: number[]) => [(x ?? 0) * 100 + 50, 200 - (y ?? 0)],
      size: () => [100, 0],
    };
    const drawn = ranges?.renderItem?.({}, api) as {
      children: { shape: { x1: number; y1: number; y2: number } }[];
    };
    // The second of two bars in a category 100 px wide: 70 px of bars, the second centred at +17.5.
    expect(drawn.children[0]?.shape).toEqual({ x1: 167.5, y1: 120, x2: 167.5, y2: 100 });
    const single = barsOption(
      { ...group, scenarios: ["default"], values: [group.values[0] ?? []] },
      colours,
    );
    expect(single.legend).toEqual({ show: false });
  });
});

describe("over time", () => {
  const rows = [
    { scenario: "default", replication: 0, metric: "till.utilization", time_s: 0, value: 0.5 },
    { scenario: "default", replication: 1, metric: "till.utilization", time_s: 0, value: 0.7 },
    { scenario: "default", replication: 0, metric: "till.utilization", time_s: 7200, value: 1 },
    { scenario: "default", replication: 0, metric: "till.queue_length", time_s: 0, value: 2 },
    { scenario: "b", replication: 0, metric: "till.utilization", time_s: 7200, value: 0 },
    { scenario: "default", metric: "till.utilization", time_s: "x", value: 1 },
    { scenario: 3, metric: "till.utilization", time_s: 0, value: 1 },
  ];

  it("averages the repeat runs at each time, per scenario, in display units", () => {
    expect(timeseriesMetrics(rows)).toEqual(["till.utilization", "till.queue_length"]);
    const share = overTime(rows, "till.utilization");
    expect(share.timeSymbol).toBe("h");
    expect(share.times).toEqual([0, 2]);
    expect(share.valueName).toBe("till.utilization (%)");
    expect(share.lines).toEqual([
      { scenario: "default", values: [60, 100] },
      { scenario: "b", values: [null, 0] },
    ]);
    const queue = overTime(rows, "till.queue_length");
    expect(queue.lines).toEqual([{ scenario: "default", values: [2] }]);
    expect(queue.valueName).toBe("till.queue_length");
    expect(overTime([], "x").timeSymbol).toBe("s");
    const option = overTimeOption(share, colours);
    expect((option.series as Series[])[1]?.data).toEqual([
      [0, null],
      [2, 0],
    ]);
    expect(overTimeOption(queue, colours).legend).toEqual({ show: false });
  });
});

describe("a search's trials", () => {
  it("draws each trial, filled when it meets every limit, and the best found", () => {
    const search = searchOf(searchSummary());
    if (search === null) throw new Error("no search");
    const points = trialPoints(search);
    expect(points.unit).toBe("min");
    expect(points.feasible).toEqual([
      [0, 4.5],
      [1, 0.245],
    ]);
    expect(points.infeasible).toEqual([[2, 0.025]]);
    expect(points.best).toBeCloseTo(0.245);
    const series = trialsOption(search, points, colours).series as Series[];
    expect(series.map((item) => item.name)).toEqual([
      "Meets every limit",
      "Breaks a limit",
      "Best found",
    ]);
    expect(series[2]?.data).toEqual([
      [0, points.best],
      [2, points.best],
    ]);
    const none = trialsOption(search, { ...points, best: null }, colours).series as Series[];
    expect(none).toHaveLength(2);
  });

  it("chooses the unit of the objective metric", () => {
    const base = searchOf(searchSummary());
    if (base === null) throw new Error("no search");
    const of = (unit: string, metric = base.metric) =>
      trialPoints({
        ...base,
        metric,
        trials: base.trials.map((trial) => ({
          ...trial,
          objective: trial.objective && { ...trial.objective, unit },
        })),
      }).unit;
    expect(of("1/s")).toBe("per hour");
    expect(of("1", "till.utilization")).toBe("%");
    expect(of("1")).toBe("");
    expect(trialPoints({ ...base, trials: [] }).unit).toBe("");
  });
});

describe("an optimization's decisions", () => {
  it("draws a bar per decision with its value", () => {
    const option = decisionsOption(solutionOf(planSummary()), colours);
    const [series] = option.series as (Series & {
      label: { formatter: (item: { value: number }) => string };
    })[];
    expect(series?.data).toEqual([24, 14]);
    expect(series?.label.formatter({ value: 2200 })).toBe("2,200");
    expect((option.yAxis as { data: string[] }).data).toEqual(["chairs", "tables"]);
  });
});
