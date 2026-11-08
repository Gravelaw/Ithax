/**
 * The Data screen's histogram: the closed-form densities of spec 1's distributions, the
 * curve as expected counts, and the ECharts option.
 */
import { describe, expect, it } from "vitest";
import {
  density,
  fieldNumber,
  fieldsText,
  histogramData,
  histogramOption,
  rounded,
} from "./histogram";

/** The area under a density from `low` to `high` (a check in the test, by the midpoint rule). */
function area(f: (x: number) => number, low: number, high: number, steps = 200_000): number {
  const width = (high - low) / steps;
  let sum = 0;
  for (let index = 0; index < steps; index += 1) sum += f(low + (index + 0.5) * width) * width;
  return sum;
}

function mean(f: (x: number) => number, low: number, high: number): number {
  return area((x) => x * f(x), low, high);
}

describe("densities in spec 1's parameterisation", () => {
  it("reads a field as a number in the column's unit", () => {
    expect(fieldNumber("2.5 min")).toBe(2.5);
    expect(fieldNumber(3)).toBe(3);
    expect(fieldNumber("2.5 minutes")).toBeNaN();
    expect(fieldNumber(null)).toBeNaN();
  });

  it.each([
    [{ dist: "exponential", mean: "2 min" }, 0, 60, 2],
    [{ dist: "uniform", min: 1, max: 3 }, 0, 4, 2],
    [{ dist: "triangular", min: 0, mode: 1, max: 4 }, 0, 4, 5 / 3],
    [{ dist: "normal", mean: 10, sd: 2 }, -10, 30, 10],
    [{ dist: "lognormal", mean: "2 h", sd: "1 h" }, 0, 40, 2],
    [{ dist: "weibull", shape: 2, scale: "3 min" }, 0, 30, 3 * 0.886226925452758],
  ])("%o has area 1 and its mean", (distribution, low, high, expected) => {
    const f = density(distribution);
    expect(f).not.toBeNull();
    if (f === null) return;
    expect(area(f, low, high)).toBeCloseTo(1, 3);
    expect(mean(f, low, high)).toBeCloseTo(expected, 2);
  });

  it("has no curve for a constant, an empirical, or fields that make no distribution", () => {
    expect(density({ dist: "constant", value: "2 min" })).toBeNull();
    expect(density({ dist: "empirical", values: [1, 2] })).toBeNull();
    expect(density({ dist: "exponential", mean: "0 min" })).toBeNull();
    expect(density({ dist: "uniform", min: 3, max: 3 })).toBeNull();
    expect(density({ dist: "triangular", min: 0, mode: 5, max: 4 })).toBeNull();
    expect(density({ dist: "normal", mean: 1, sd: 0 })).toBeNull();
    expect(density({ dist: "lognormal", mean: -1, sd: 1 })).toBeNull();
    expect(density({ dist: "weibull", shape: "x", scale: 1 })).toBeNull();
    expect(density({ dist: "constructor" })).toBeNull();
  });

  it("is zero outside a distribution's range", () => {
    expect(density({ dist: "exponential", mean: 1 })?.(-1)).toBe(0);
    expect(density({ dist: "uniform", min: 1, max: 2 })?.(3)).toBe(0);
    expect(density({ dist: "triangular", min: 0, mode: 1, max: 2 })?.(1)).toBe(1);
    expect(density({ dist: "triangular", min: 0, mode: 1, max: 2 })?.(-1)).toBe(0);
    expect(density({ dist: "lognormal", mean: 1, sd: 1 })?.(0)).toBe(0);
    expect(density({ dist: "weibull", shape: 1, scale: 1 })?.(-1)).toBe(0);
  });
});

describe("the histogram's data", () => {
  const fit = { values: 100, histogram: { edges: [0, 1, 2, 3, 4], counts: [60, 25, 10, 5] } };

  it("draws the curve as the count each bin would hold", () => {
    const data = histogramData(fit, { dist: "exponential", mean: "1 min" });
    expect(data.bins).toHaveLength(4);
    expect(data.bins[0]).toMatchObject({ from: 0, to: 1, count: 60 });
    // n × width × density at the bin's middle: 100 × 1 × e^-0.5.
    expect(data.bins[0]?.fitted).toBeCloseTo(100 * Math.exp(-0.5), 10);
    expect(data.curve).toHaveLength(121);
    expect(data.curve[0]).toEqual([0, 100]);
    expect(data.low).toBe(0);
    expect(data.high).toBe(4);
  });

  it("has no curve without a distribution, and widens the axis around a constant column", () => {
    const none = histogramData(fit, null);
    expect(none.curve).toEqual([]);
    expect(none.bins.every((bin) => bin.fitted === null)).toBe(true);
    const constant = histogramData(
      { values: 3, histogram: { edges: [20, 20], counts: [3] } },
      { dist: "constant", value: "20 s" },
    );
    expect(constant.bins).toEqual([{ from: 20, to: 20, count: 3, fitted: null }]);
    expect(constant.low).toBe(18);
    expect(constant.high).toBe(22);
  });

  it("leaves a gap where the density is not finite", () => {
    const data = histogramData(fit, { dist: "weibull", shape: 0.5, scale: 1 });
    expect(data.curve[0]).toEqual([0, null]);
  });

  it("writes fields to 4 significant digits, or exactly", () => {
    const distribution = { dist: "normal", mean: "1.4974025 min", sd: 0.123456 };
    expect(fieldsText(distribution)).toBe("mean 1.497 min, sd 0.1235");
    expect(fieldsText(distribution, true)).toBe("mean 1.4974025 min, sd 0.123456");
    expect(fieldsText({ dist: "x", data: { file: "a" }, note: "text" })).toBe(
      'data {"file":"a"}, note text',
    );
    expect(rounded(Number.POSITIVE_INFINITY)).toBe("Infinity");
  });
});

describe("the chart's option", () => {
  const colours = { bars: "var-1", curve: "var-2", text: "var-3", grid: "var-4" };

  it("has the column's bars and the candidate's line, named with the unit", () => {
    const data = histogramData(
      { values: 10, histogram: { edges: [0, 2, 4], counts: [7, 3] } },
      { dist: "exponential", mean: "2 min" },
    );
    const option = histogramOption(
      data,
      { column: "gap", unit: "min", curveName: "Fitted exponential" },
      colours,
    ) as {
      xAxis: { name: string; min: number; max: number };
      series: { type: string; name: string; data: unknown[]; renderItem?: unknown }[];
    };
    expect(option.xAxis).toMatchObject({ name: "gap (min)", min: 0, max: 4 });
    expect(option.series.map((series) => [series.type, series.name])).toEqual([
      ["custom", "Your data"],
      ["line", "Fitted exponential"],
    ]);
    expect(option.series[0]?.data).toEqual([
      [0, 2, 7],
      [2, 4, 3],
    ]);
    const unitless = histogramOption(
      data,
      { column: "n", unit: null, curveName: "c" },
      colours,
    ) as {
      xAxis: { name: string };
    };
    expect(unitless.xAxis.name).toBe("n");
  });

  it("draws each bin as a rectangle, and a bin of no width 2% of the axis wide", () => {
    const data = histogramData({ values: 3, histogram: { edges: [5, 5], counts: [3] } }, null);
    const option = histogramOption(data, { column: "c", unit: "s", curveName: "c" }, colours) as {
      series: {
        renderItem: (params: unknown, api: unknown) => { shape: { x: number; width: number } };
      }[];
    };
    const values = [5, 5, 3];
    const api = {
      value: (dimension: number) => values[dimension] ?? 0,
      coord: ([x, y]: number[]) => [(x ?? 0) * 10, 100 - (y ?? 0) * 10],
    };
    const drawn = option.series[0]?.renderItem({}, api);
    // The axis is 4 to 6 (wide 2), so the bar is 0.04 wide around 5: x from 49.8 to 50.2.
    expect(drawn?.shape.x).toBeCloseTo(49.8, 6);
    expect(drawn?.shape.width).toBe(1);
  });
});
