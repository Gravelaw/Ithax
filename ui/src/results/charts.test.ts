/** The data and options of the Results charts (AKS-138). */
import { init } from "echarts/core";
import { describe, expect, it } from "vitest";
import "../charts/Chart";
import { optionsSummary, planSummary, searchSummary } from "../test/runs";
import {
  type BarGroup,
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

  it("draws one bar per component and scenario, each range at its own bar", () => {
    const [group] = barGroups(scenariosOf(optionsSummary()));
    if (group === undefined) throw new Error("no group");
    const option = barsOption(group, colours);
    const series = option.series as Series[];
    expect(series.map((item) => item.type)).toEqual(["bar", "custom"]);
    expect(option.legend).toBeUndefined();
    expect((option.xAxis as { data: string[] }).data).toEqual([
      "cut (default)",
      "cut (faster)",
      "weld (default)",
      "weld (faster)",
    ]);
    const [bars, ranges] = series;
    expect(
      bars?.data.map((bar) => (bar as { itemStyle: { color: string } }).itemStyle.color),
    ).toEqual(["#111111", "#222222", "#111111", "#222222"]);
    // Each range names its own bar's category, and both bounds as values of the value axis.
    expect(((ranges?.data ?? []) as number[][]).map((range) => range[0])).toEqual([0, 1, 2, 3]);
    expect((ranges as unknown as { encode: unknown }).encode).toEqual({ x: 0, y: [1, 2] });
    const api = {
      value: (dimension: number) => [1, 80, 100][dimension] ?? 0,
      coord: ([x, y]: number[]) => [(x ?? 0) * 100 + 50, 200 - (y ?? 0)],
      size: () => [100, 0],
    };
    const drawn = ranges?.renderItem?.({}, api) as {
      children: { shape: { x1: number; y1: number; y2: number } }[];
    };
    expect(drawn.children[0]?.shape).toEqual({ x1: 150, y1: 120, x2: 150, y2: 100 });
    const single = barsOption(
      { ...group, scenarios: ["default"], values: [group.values[0] ?? []] },
      colours,
    );
    expect((single.xAxis as { data: string[] }).data).toEqual(["cut", "weld"]);
  });

  it("drawn by ECharts, a range above every bar sets the axis, and each sits over its bar", () => {
    const group: BarGroup = {
      family: "wait.mean",
      title: "Average wait",
      unit: "Average wait (min)",
      components: ["a", "b"],
      scenarios: ["one", "two"],
      values: [
        [
          { mean: 10, half: 30 },
          { mean: 5, half: 1 },
        ],
        [{ mean: 8, half: 2 }, null],
      ],
    };
    const box = document.createElement("div");
    const chart = init(box, null, { renderer: "svg", width: 600, height: 300 });
    chart.setOption(barsOption(group, colours));
    const model = chart as unknown as {
      getModel(): {
        getComponent(type: string): { axis: { scale: { getExtent(): number[] } } };
        getSeriesByIndex(index: number): {
          getData(): {
            count(): number;
            getItemLayout(index: number): { x: number; width: number };
          };
        };
      };
    };
    const [, top] = model.getModel().getComponent("yAxis").axis.scale.getExtent();
    expect(top).toBeGreaterThanOrEqual(40);
    const bars = model.getModel().getSeriesByIndex(0).getData();
    const centres = [0, 1, 2].map((index) => {
      const layout = bars.getItemLayout(index);
      return layout.x + layout.width / 2;
    });
    // The ranges' x: a (one), a (two), b (one); the fourth (b, two) has no bar.
    const ranges = (barsOption(group, colours).series as Series[])[1];
    const at = ((ranges?.data ?? []) as number[][]).map((range) =>
      chart.convertToPixel({ xAxisIndex: 0 }, range[0] ?? 0),
    );
    expect(at).toEqual(centres.map((centre) => expect.closeTo(centre, 6)));
    chart.dispose();
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
    // A decision may be negative (a free or negative bound): the axis is not cut at zero.
    const negative = decisionsOption(
      { ...solutionOf(planSummary()), variables: [["x", -3]] },
      colours,
    );
    expect((negative.xAxis as { min?: number }).min).toBeUndefined();
  });
});
