/** The display rules of spec 4 "Finding rules", as `src/ithax/findings/display.py` has them. */
import { describe, expect, it } from "vitest";
import {
  confidenceText,
  figures,
  isShare,
  percent,
  quantity,
  rangeText,
  timeUnit,
  UNDEFINED,
  valueText,
} from "./display";

describe("display units", () => {
  it.each([
    [15.6914, 3, "15.7"],
    [2200, 3, "2,200"],
    [13.999999999999998, 4, "14"],
    [9.996, 3, "10"],
    [0.000277778, 3, "0.000278"],
    [-3.14158, 3, "-3.14"],
    [1234567, 3, "1,230,000"],
    [0, 3, "0"],
    [1e-7, 3, "0.0000001"],
    [Number.POSITIVE_INFINITY, 3, "Infinity"],
  ])("%s to %s figures is %s", (value, digits, text) => {
    expect(figures(value, digits)).toBe(text);
  });

  it("shows shares, times, rates and plain numbers", () => {
    expect(percent(0.900985)).toBe("90%");
    expect(timeUnit(59)).toEqual(["s", 1]);
    expect(timeUnit(3600)).toEqual(["h", 3600]);
    expect(timeUnit(-200_000)).toEqual(["d", 86400]);
    expect(quantity(941.5, "s")).toBe("15.7 min");
    expect(quantity(125.4, "s", 941.5)).toBe("2.09 min");
    expect(quantity(1 / 3600, "1/s")).toBe("1 per hour");
    expect(quantity(12.4, "1")).toBe("12.4");
    expect(isShare("weld.utilization", "1")).toBe(true);
    expect(isShare("weld.utilization", "s")).toBe(false);
    expect(isShare("model.wip.mean", "1")).toBe(false);
    expect(valueText("weld.utilization", 0.901, "1")).toBe("90.1%");
    expect(valueText("weld.wait.mean", null, "s")).toBe(UNDEFINED);
    expect(rangeText("weld.wait.mean", 125.4, "s", 941.5)).toBe("± 2.09 min");
    expect(rangeText("weld.wait.mean", 30, "s", null)).toBe("± 30 s");
    expect(rangeText("weld.utilization", 0.011, "1", 0.901)).toBe("± 1.1%");
    expect(rangeText("x", null, "1", 1)).toBe(UNDEFINED);
    expect(confidenceText(0.95)).toBe("95%");
    expect(confidenceText(0.975)).toBe("97.5%");
  });
});
