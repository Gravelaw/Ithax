/**
 * The ECharts chart: an image with a name, drawn as SVG, redrawn with a new option and
 * disposed of when it goes; its colours follow the colour-blind safe setting.
 */
import { render, renderHook, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { SettingsProvider } from "../settings/SettingsContext";
import { FakeService, SETTINGS } from "../test/fakes";
import { designTokens } from "../theme/tokens";
import { Chart, useChartColours, useSeriesColours } from "./Chart";
import { histogramData, histogramOption } from "./histogram";

const colours = { bars: "#000000", curve: "#000000", text: "#000000", grid: "#000000" };

function option(curveName: string) {
  return histogramOption(
    histogramData(
      { values: 10, histogram: { edges: [0, 1, 2], counts: [6, 4] } },
      { dist: "exponential", mean: 1 },
    ),
    { column: "gap", unit: "min", curveName },
    colours,
  );
}

describe("the chart", () => {
  it("draws its option as an SVG image with a name, and goes with its screen", () => {
    const { rerender, unmount } = render(<Chart option={option("Fitted one")} label="Histogram" />);
    const image = screen.getByRole("img", { name: "Histogram" });
    expect(image.querySelector("svg")).not.toBeNull();
    rerender(<Chart option={option("Fitted two")} label="Histogram" />);
    expect(image.querySelector("svg")).not.toBeNull();
    unmount();
    expect(screen.queryByRole("img", { name: "Histogram" })).toBeNull();
  });

  it("uses the colour-blind safe series colours when that setting is on", () => {
    const wrapper =
      (safe: boolean) =>
      ({ children }: { children: ReactNode }) => (
        <SettingsProvider
          client={new FakeService().client()}
          initial={{ ...SETTINGS, interface: { ...SETTINGS.interface, colour_blind_charts: safe } }}
          root={document.createElement("div")}
        >
          {children}
        </SettingsProvider>
      );
    const light = designTokens.themes.light;
    const standard = renderHook(() => useChartColours(), { wrapper: wrapper(false) }).result
      .current;
    expect(standard.bars).toBe(light["chart-1"]);
    expect(standard.curve).toBe(light["chart-2"]);
    const safe = renderHook(() => useChartColours(), { wrapper: wrapper(true) }).result.current;
    expect(safe.bars).toBe(light["chart-cb-1"]);
    expect(safe.curve).toBe(light["chart-cb-2"]);
    const series = renderHook(() => useSeriesColours(), { wrapper: wrapper(false) }).result.current;
    expect(series.series).toEqual(
      ["chart-1", "chart-2", "chart-3", "chart-4"].map((name) => light[name]),
    );
    const safeSeries = renderHook(() => useSeriesColours(), { wrapper: wrapper(true) }).result
      .current;
    expect(safeSeries.series).toEqual(
      ["chart-cb-1", "chart-cb-2", "chart-cb-3", "chart-cb-4"].map((name) => light[name]),
    );
    expect(safeSeries.text).toBe(light["text-muted"]);
  });
});
