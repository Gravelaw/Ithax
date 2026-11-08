/**
 * A chart drawn by Apache ECharts (`docs/design/design-system.md` "Charts": SVG or canvas,
 * never WebGL). Only the parts the interface uses are imported, so the build leaves the
 * rest of ECharts out; it is drawn as SVG and bundled, nothing is fetched at run time.
 *
 * A chart is an image with a name (`role="img"`); every chart has a data table beside it
 * with the same numbers (`accessibility.md`, WCAG 1.1.1 and 1.4.1), which its screen draws.
 */
import { BarChart, CustomChart, LineChart, ScatterChart } from "echarts/charts";
import { GridComponent, LegendComponent } from "echarts/components";
import { type EChartsType, init, use } from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";
import { useSettings } from "../settings/SettingsContext";
import { designTokens } from "../theme/tokens";
import type { ChartColours } from "./histogram";

use([BarChart, CustomChart, LineChart, ScatterChart, GridComponent, LegendComponent, SVGRenderer]);

/** A token's colour as the page shows it now (the theme in use), else the light theme's. */
function token(name: string): string {
  const shown =
    typeof document === "undefined"
      ? ""
      : getComputedStyle(document.documentElement).getPropertyValue(`--color-${name}`).trim();
  return shown !== "" ? shown : (designTokens.themes.light[name] ?? "");
}

/**
 * The colours of the first two series and of the axes: `chart-1` and `chart-2`, or
 * `chart-cb-1` and `chart-cb-2` when "Colour-blind safe charts" is on (owner review).
 */
export function useChartColours(): ChartColours {
  const { settings } = useSettings();
  const safe = settings.interface.colour_blind_charts;
  // Read again at each drawing, so a change of theme is followed; the same colours give
  // the same object.
  const bars = token(safe ? "chart-cb-1" : "chart-1");
  const curve = token(safe ? "chart-cb-2" : "chart-2");
  const text = token("text-muted");
  const grid = token("border-strong");
  return useMemo(() => ({ bars, curve, text, grid }), [bars, curve, text, grid]);
}

/** The colours of up to four series and of the axes (Results, AKS-138). */
export interface SeriesColours {
  series: readonly string[];
  text: string;
  grid: string;
}

/**
 * `chart-1` to `chart-4`, or `chart-cb-1` to `chart-cb-4` when "Colour-blind safe charts"
 * is on (`design-system.md` "Charts"); beyond four series the colours repeat and the
 * marker shape and the legend tell them apart.
 */
export function useSeriesColours(): SeriesColours {
  const { settings } = useSettings();
  const prefix = settings.interface.colour_blind_charts ? "chart-cb-" : "chart-";
  const first = token(`${prefix}1`);
  const second = token(`${prefix}2`);
  const third = token(`${prefix}3`);
  const fourth = token(`${prefix}4`);
  const text = token("text-muted");
  const grid = token("border-strong");
  return useMemo(
    () => ({ series: [first, second, third, fourth], text, grid }),
    [first, second, third, fourth, text, grid],
  );
}

export function Chart({ option, label }: { option: Record<string, unknown>; label: string }) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<EChartsType | null>(null);

  useEffect(() => {
    const element = box.current;
    if (element === null) return;
    const made = init(element, null, { renderer: "svg" });
    chart.current = made;
    const observer = new ResizeObserver(() => made.resize());
    observer.observe(element);
    return () => {
      observer.disconnect();
      made.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, true);
  }, [option]);

  return <div ref={box} className="chart" role="img" aria-label={label} />;
}
