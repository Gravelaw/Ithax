/**
 * The Results screen's charts (spec 3 "Run monitor, Results and Settings";
 * `docs/design/design-system.md` "Charts"): the data each one draws, worked out from the
 * run's answers, and its ECharts option. Every chart's numbers are also given as a table by
 * the screen ("Show as table"). Nothing here is a solver: averages and unit conversions.
 */

import type { Estimate, TableRow } from "../api/types";
import type { SeriesColours } from "../charts/Chart";
import { figures, isShare, timeUnit } from "./display";
import type { Scenario, Search, Solution } from "./summary";

/** Marker shapes, one per series, so no series is told apart by colour alone. */
export const SHAPES = ["circle", "rect", "triangle", "diamond"] as const;

function colour(colours: SeriesColours, index: number): string {
  return colours.series[index % colours.series.length] ?? colours.text;
}

function axis(colours: SeriesColours, name: string): Record<string, unknown> {
  return {
    name,
    nameLocation: "middle",
    nameGap: 32,
    nameTextStyle: { color: colours.text },
    axisLabel: { color: colours.text },
    axisLine: { lineStyle: { color: colours.grid } },
    splitLine: { lineStyle: { color: colours.grid, opacity: 0.3 } },
  };
}

// --- bars of a metric family, with their likely ranges ---------------------------------

export interface BarGroup {
  /** `utilization` or `wait.mean`. */
  family: string;
  title: string;
  /** The axis name, with the display unit. */
  unit: string;
  components: string[];
  scenarios: string[];
  /** `values[s][c]`: scenario `s`, component `c`, in display units; `null` when undefined. */
  values: ({ mean: number; half: number | null } | null)[][];
}

const FAMILIES: readonly { family: string; title: string }[] = [
  { family: "utilization", title: "Busy share by component, with the likely range" },
  { family: "wait.mean", title: "Average wait by component, with the likely range" },
];

/** One group of bars per family the run's metrics hold (`model.*` left out). */
export function barGroups(scenarios: readonly Scenario[]): BarGroup[] {
  const groups: BarGroup[] = [];
  for (const { family, title } of FAMILIES) {
    const ending = `.${family}`;
    const components: string[] = [];
    for (const scenario of scenarios) {
      for (const [name] of scenario.metrics) {
        const component = name.slice(0, -ending.length);
        if (name.endsWith(ending) && component !== "model" && !components.includes(component)) {
          components.push(component);
        }
      }
    }
    if (components.length === 0) continue;
    const found = (scenario: Scenario, component: string): Estimate | null =>
      scenario.metrics.find(([name]) => name === `${component}${ending}`)?.[1] ?? null;
    const means = scenarios.flatMap((scenario) =>
      components.map((component) => found(scenario, component)?.mean ?? 0),
    );
    const share = family === "utilization";
    const [symbol, size] = share ? ["%", 0.01] : timeUnit(Math.max(...means.map(Math.abs)));
    groups.push({
      family,
      title,
      unit: share ? "Busy share (%)" : `Average wait (${symbol})`,
      components,
      scenarios: scenarios.map((scenario) => scenario.id),
      values: scenarios.map((scenario) =>
        components.map((component) => {
          const estimate = found(scenario, component);
          if (estimate === null || estimate.mean === null) return null;
          return {
            mean: estimate.mean / size,
            half: estimate.half_width === null ? null : estimate.half_width / size,
          };
        }),
      ),
    });
  }
  return groups;
}

/** Bars side by side per component, one series per scenario, each with its likely range. */
export function barsOption(group: BarGroup, colours: SeriesColours): Record<string, unknown> {
  const count = group.scenarios.length;
  const series: Record<string, unknown>[] = [];
  group.scenarios.forEach((scenario, index) => {
    const values = group.values[index] ?? [];
    series.push({
      name: scenario,
      type: "bar",
      barGap: "0%",
      barCategoryGap: "30%",
      itemStyle: { color: colour(colours, index) },
      data: values.map((value) => value?.mean ?? null),
    });
    series.push({
      name: scenario,
      type: "custom",
      silent: true,
      data: values.flatMap((value, component) =>
        value === null || value.half === null
          ? []
          : [[component, value.mean - value.half, value.mean + value.half]],
      ),
      // A vertical line with caps over the bar of this scenario in its category.
      renderItem: (
        params: unknown,
        api: {
          value(dimension: number): number;
          coord(point: number[]): number[];
          size(span: number[]): number[];
        },
      ) => {
        const category = api.value(0);
        const width = (api.size([1, 0])[0] ?? 0) * 0.7;
        const offset = -width / 2 + ((index + 0.5) * width) / count;
        const [x0 = 0, low = 0] = api.coord([category, api.value(1)]);
        const [, high = 0] = api.coord([category, api.value(2)]);
        const x = x0 + offset;
        const cap = Math.min(6, width / count / 4);
        const style = { stroke: colours.text, lineWidth: 1.5 };
        void params;
        return {
          type: "group",
          children: [
            { type: "line", shape: { x1: x, y1: low, x2: x, y2: high }, style },
            { type: "line", shape: { x1: x - cap, y1: low, x2: x + cap, y2: low }, style },
            { type: "line", shape: { x1: x - cap, y1: high, x2: x + cap, y2: high }, style },
          ],
        };
      },
      z: 3,
    });
  });
  return {
    animation: false,
    grid: { left: 64, right: 16, top: count > 1 ? 36 : 16, bottom: 48 },
    legend:
      count > 1
        ? { top: 0, textStyle: { color: colours.text }, data: group.scenarios }
        : { show: false },
    xAxis: { type: "category", data: group.components, ...axis(colours, "Component") },
    yAxis: { type: "value", min: 0, ...axis(colours, group.unit), nameGap: 48 },
    series,
  };
}

// --- the average of the repeat runs over time --------------------------------------------

export interface OverTime {
  metric: string;
  /** The axis name, with the display unit. */
  valueName: string;
  timeSymbol: string;
  times: number[];
  /** One line per scenario: the value at each time, in display units. */
  lines: { scenario: string; values: (number | null)[] }[];
}

/** The metrics of a `timeseries` table, in its order. */
export function timeseriesMetrics(rows: readonly TableRow[]): string[] {
  const found: string[] = [];
  for (const row of rows) {
    if (typeof row.metric === "string" && !found.includes(row.metric)) found.push(row.metric);
  }
  return found;
}

/**
 * The average over the repeat runs of `metric` at each sample time, per scenario: the
 * rows of the `timeseries` table (spec 1) are summed and counted, never solved.
 */
export function overTime(rows: readonly TableRow[], metric: string): OverTime {
  const sums = new Map<string, Map<number, { sum: number; count: number }>>();
  const times = new Set<number>();
  for (const row of rows) {
    if (row.metric !== metric || typeof row.scenario !== "string") continue;
    if (typeof row.time_s !== "number" || typeof row.value !== "number") continue;
    const scenario = sums.get(row.scenario) ?? new Map();
    sums.set(row.scenario, scenario);
    const point = scenario.get(row.time_s) ?? { sum: 0, count: 0 };
    point.sum += row.value;
    point.count += 1;
    scenario.set(row.time_s, point);
    times.add(row.time_s);
  }
  const sorted = [...times].sort((a, b) => a - b);
  const [timeSymbol, size] = timeUnit(sorted.at(-1) ?? 0);
  const share = isShare(metric, "1");
  return {
    metric,
    valueName: share ? `${metric} (%)` : metric,
    timeSymbol,
    times: sorted.map((time) => time / size),
    lines: [...sums.entries()].map(([scenario, points]) => ({
      scenario,
      values: sorted.map((time) => {
        const point = points.get(time);
        return point === undefined ? null : (point.sum / point.count) * (share ? 100 : 1);
      }),
    })),
  };
}

export function overTimeOption(data: OverTime, colours: SeriesColours): Record<string, unknown> {
  return {
    animation: false,
    grid: { left: 64, right: 16, top: data.lines.length > 1 ? 36 : 16, bottom: 48 },
    legend:
      data.lines.length > 1 ? { top: 0, textStyle: { color: colours.text } } : { show: false },
    xAxis: { type: "value", min: 0, ...axis(colours, `Time (${data.timeSymbol})`) },
    yAxis: { type: "value", ...axis(colours, data.valueName), nameGap: 48 },
    series: data.lines.map((line, index) => ({
      name: line.scenario,
      type: "line",
      showSymbol: false,
      symbol: SHAPES[index % SHAPES.length],
      lineStyle: { color: colour(colours, index), width: 2 },
      itemStyle: { color: colour(colours, index) },
      data: line.values.map((value, at) => [data.times[at], value]),
    })),
  };
}

// --- a search: every trial, and the best found -------------------------------------------

export interface TrialPoints {
  unit: string;
  feasible: [number, number][];
  infeasible: [number, number][];
  best: number | null;
  count: number;
}

/** The trials' objective averages in display units, and the best found's. */
export function trialPoints(search: Search): TrialPoints {
  const units = search.trials.flatMap((trial) => (trial.objective ? [trial.objective.unit] : []));
  const unit = units[0] ?? "1";
  const means = search.trials.flatMap((trial) =>
    trial.objective?.mean === null || trial.objective === null ? [] : [trial.objective.mean],
  );
  const share = isShare(search.metric, unit);
  const [symbol, size] =
    unit === "s"
      ? timeUnit(Math.max(0, ...means.map(Math.abs)))
      : unit === "1/s"
        ? ["per hour", 1 / 3600]
        : share
          ? ["%", 0.01]
          : ["", 1];
  const point = (index: number, mean: number): [number, number] => [index, mean / size];
  return {
    unit: symbol,
    feasible: search.trials.flatMap((trial) =>
      trial.feasible && trial.objective?.mean != null
        ? [point(trial.index, trial.objective.mean)]
        : [],
    ),
    infeasible: search.trials.flatMap((trial) =>
      !trial.feasible && trial.objective?.mean != null
        ? [point(trial.index, trial.objective.mean)]
        : [],
    ),
    best: search.after === null ? null : search.after / size,
    count: search.trials.length,
  };
}

export function trialsOption(
  search: Search,
  points: TrialPoints,
  colours: SeriesColours,
): Record<string, unknown> {
  const name = points.unit === "" ? search.metric : `${search.metric} (${points.unit})`;
  const series: Record<string, unknown>[] = [
    {
      name: "Meets every limit",
      type: "scatter",
      symbol: "circle",
      symbolSize: 9,
      itemStyle: { color: colour(colours, 0) },
      data: points.feasible,
    },
    {
      name: "Breaks a limit",
      type: "scatter",
      symbol: "emptyCircle",
      symbolSize: 9,
      itemStyle: { color: colour(colours, 0), borderColor: colour(colours, 0) },
      data: points.infeasible,
    },
  ];
  if (points.best !== null) {
    series.push({
      name: "Best found",
      type: "line",
      symbol: "none",
      lineStyle: { color: colour(colours, 1), type: "dashed", width: 2 },
      itemStyle: { color: colour(colours, 1) },
      data: [
        [0, points.best],
        [Math.max(points.count - 1, 1), points.best],
      ],
    });
  }
  return {
    animation: false,
    grid: { left: 64, right: 16, top: 36, bottom: 48 },
    legend: { top: 0, textStyle: { color: colours.text } },
    xAxis: { type: "value", min: 0, minInterval: 1, ...axis(colours, "Trial, in the order tried") },
    yAxis: { type: "value", ...axis(colours, name), nameGap: 48 },
    series,
  };
}

// --- an optimization: the decisions -------------------------------------------------------

export function decisionsOption(
  solution: Solution,
  colours: SeriesColours,
): Record<string, unknown> {
  return {
    animation: false,
    grid: { left: 96, right: 48, top: 16, bottom: 40 },
    xAxis: { type: "value", min: 0, ...axis(colours, "Value") },
    yAxis: {
      type: "category",
      inverse: true,
      data: solution.variables.map(([name]) => name),
      ...axis(colours, ""),
    },
    series: [
      {
        name: "Decisions",
        type: "bar",
        itemStyle: { color: colour(colours, 0) },
        label: {
          show: true,
          position: "right",
          color: colours.text,
          formatter: (item: { value: number }) => figures(item.value, 4),
        },
        data: solution.variables.map(([, value]) => value),
      },
    ],
  };
}
