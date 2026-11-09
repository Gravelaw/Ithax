/**
 * The Data screen's histogram with the chosen candidate's curve (`docs/design/design-system.md`
 * "Charts"; `docs/research/spec-3-results-visualization.md`, Data screen).
 *
 * The bars are the service's histogram of the column (spec 3 fit note: `{edges, counts}`,
 * in the column's unit). The curve is the candidate's density, written in closed form from
 * its fitted fields (spec 1 "Distributions"), drawn as the count each bin would hold:
 * n × bin width × density. Nothing is fitted or solved here (guide rule 7): fitting is the
 * service's.
 */
import type { FitBody } from "../api/types";
import { own } from "../canvas/own";

/** A field of a fitted distribution as a number in the column's unit: `"2.0 min"` → 2. */
export function fieldNumber(value: unknown): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const found = /^(\S+) (s|min|h|d)$/.exec(value);
    if (found) return Number(found[1]);
  }
  return Number.NaN;
}

/**
 * The density of a spec 1 distribution with these fields, or `null` when it has none to
 * draw (a `constant`, an `empirical`, or fields that do not make a distribution).
 */
export function density(
  distribution: Readonly<Record<string, unknown>>,
): ((x: number) => number) | null {
  const get = (name: string) => fieldNumber(own(distribution, name));
  const fine = (...values: number[]) => values.every(Number.isFinite);
  switch (own(distribution, "dist")) {
    case "exponential": {
      const mean = get("mean");
      if (!fine(mean) || mean <= 0) return null;
      return (x) => (x < 0 ? 0 : Math.exp(-x / mean) / mean);
    }
    case "uniform": {
      const low = get("min");
      const high = get("max");
      if (!fine(low, high) || high <= low) return null;
      return (x) => (x < low || x > high ? 0 : 1 / (high - low));
    }
    case "triangular": {
      const low = get("min");
      const mode = get("mode");
      const high = get("max");
      if (!fine(low, mode, high) || high <= low || mode < low || mode > high) return null;
      return (x) => {
        if (x < low || x > high) return 0;
        if (x < mode) return (2 * (x - low)) / ((high - low) * (mode - low));
        if (x === mode) return 2 / (high - low);
        return (2 * (high - x)) / ((high - low) * (high - mode));
      };
    }
    case "normal": {
      const mean = get("mean");
      const sd = get("sd");
      if (!fine(mean, sd) || sd <= 0) return null;
      return (x) => Math.exp(-(((x - mean) / sd) ** 2) / 2) / (sd * Math.sqrt(2 * Math.PI));
    }
    case "lognormal": {
      // Spec 1: the mean and sd of the variable; σ² = ln(1 + sd²/mean²), μ = ln(mean) − σ²/2.
      const mean = get("mean");
      const sd = get("sd");
      if (!fine(mean, sd) || mean <= 0 || sd <= 0) return null;
      const variance = Math.log(1 + (sd * sd) / (mean * mean));
      const sigma = Math.sqrt(variance);
      const mu = Math.log(mean) - variance / 2;
      return (x) =>
        x <= 0
          ? 0
          : Math.exp(-((Math.log(x) - mu) ** 2) / (2 * variance)) /
            (x * sigma * Math.sqrt(2 * Math.PI));
    }
    case "weibull": {
      const shape = get("shape");
      const scale = get("scale");
      if (!fine(shape, scale) || shape <= 0 || scale <= 0) return null;
      return (x) =>
        x < 0
          ? 0
          : (shape / scale) * (x / scale) ** (shape - 1) * Math.exp(-((x / scale) ** shape));
    }
    default:
      return null;
  }
}

export interface Bin {
  from: number;
  to: number;
  count: number;
  /** The count the curve gives at the bin's centre, `null` without a curve. */
  fitted: number | null;
}

export interface HistogramData {
  bins: Bin[];
  /** The curve as points `[x, expected count]`; empty without one. */
  curve: [number, number | null][];
  /** The x axis's range. */
  low: number;
  high: number;
}

const CURVE_POINTS = 120;

/** The bars, the curve and the table rows of a fit and one of its candidates. */
export function histogramData(
  fit: Pick<FitBody, "histogram" | "values">,
  distribution: Readonly<Record<string, unknown>> | null,
): HistogramData {
  const { edges, counts } = fit.histogram;
  const first = edges[0] ?? 0;
  const last = edges.at(-1) ?? first;
  const width = counts.length > 0 ? (last - first) / counts.length : 0;
  const curveOf = distribution === null ? null : density(distribution);
  const scale = fit.values * width;
  const expected = (x: number): number | null => {
    if (curveOf === null || width <= 0) return null;
    const y = scale * curveOf(x);
    return Number.isFinite(y) ? y : null;
  };
  const bins = counts.map((count, index) => {
    const from = edges[index] ?? first;
    const to = edges[index + 1] ?? last;
    return { from, to, count, fitted: expected((from + to) / 2) };
  });
  // A constant column is one bin of no width: the axis is widened around it.
  const pad = width > 0 ? 0 : Math.max(Math.abs(first) * 0.1, 1);
  const curve: [number, number | null][] = [];
  if (curveOf !== null && width > 0) {
    for (let index = 0; index <= CURVE_POINTS; index += 1) {
      const x = first + ((last - first) * index) / CURVE_POINTS;
      curve.push([x, expected(x)]);
    }
  }
  return { bins, curve, low: first - pad, high: last + pad };
}

/** A number shown to 4 significant digits: `1.4974025` → `1.497`. */
export function rounded(value: number): string {
  return Number.isFinite(value) ? String(Number(value.toPrecision(4))) : String(value);
}

/**
 * The words of a distribution's fitted fields: "mean 1.497 min, sd 1.483 min", each number
 * to 4 significant digits; `exact` gives them as the model holds them.
 */
export function fieldsText(distribution: Readonly<Record<string, unknown>>, exact = false): string {
  return Object.entries(distribution)
    .filter(([key]) => key !== "dist")
    .map(([key, value]) => {
      if (exact) return `${key} ${typeof value === "string" ? value : JSON.stringify(value)}`;
      if (typeof value === "number") return `${key} ${rounded(value)}`;
      const quantity = typeof value === "string" ? /^(\S+) (s|min|h|d)$/.exec(value) : null;
      if (quantity) return `${key} ${rounded(Number(quantity[1]))} ${quantity[2]}`;
      return `${key} ${typeof value === "string" ? value : JSON.stringify(value)}`;
    })
    .join(", ");
}

export interface ChartColours {
  bars: string;
  curve: string;
  text: string;
  grid: string;
}

/** The ECharts option of the histogram: bars of the column and the candidate's curve. */
export function histogramOption(
  data: HistogramData,
  axis: { column: string; unit: string | null; curveName: string },
  colours: ChartColours,
): Record<string, unknown> {
  const label = { color: colours.text };
  return {
    animation: false,
    grid: { left: 48, right: 16, top: 16, bottom: 44 },
    xAxis: {
      type: "value",
      min: data.low,
      max: data.high,
      scale: true,
      name: axis.unit === null ? axis.column : `${axis.column} (${axis.unit})`,
      nameLocation: "middle",
      nameGap: 28,
      nameTextStyle: label,
      axisLabel: label,
      axisLine: { lineStyle: { color: colours.grid } },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      name: "Count",
      nameTextStyle: label,
      axisLabel: label,
      splitLine: { lineStyle: { color: colours.grid, opacity: 0.4 } },
    },
    series: [
      {
        type: "custom",
        name: "Your data",
        data: data.bins.map((bin) => [bin.from, bin.to, bin.count]),
        encode: { x: [0, 1], y: 2 },
        renderItem: (
          _params: unknown,
          api: { value: (dimension: number) => number; coord: (point: number[]) => number[] },
        ) => {
          let from = api.value(0);
          let to = api.value(1);
          // A bin of no width (a constant column) is a bar 2% of the axis wide, centred on it.
          if (to <= from) {
            const half = (data.high - data.low) * 0.01;
            from -= half;
            to = from + 2 * half;
          }
          const [left = 0, top = 0] = api.coord([from, api.value(2)]);
          const [right = 0, bottom = 0] = api.coord([to, 0]);
          return {
            type: "rect",
            shape: { x: left, y: top, width: Math.max(right - left - 1, 1), height: bottom - top },
            style: { fill: colours.bars, opacity: 0.45, stroke: colours.bars, lineWidth: 1 },
          };
        },
      },
      {
        type: "line",
        name: axis.curveName,
        data: data.curve,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { color: colours.curve, width: 2.5 },
        itemStyle: { color: colours.curve },
      },
    ],
  };
}
