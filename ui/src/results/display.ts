/**
 * How the interface shows a result's numbers (spec 1 "Results": results are stored in SI
 * units and the interface chooses display units). The rules are spec 4's for a finding's
 * text ("Finding rules", Display units; `src/ithax/findings/display.py`), so a key number
 * reads as the finding that names it:
 *
 * - a time in the largest Phase 1 unit it reaches (`s`, `min`, `h`, `d`), a half-width in
 *   its mean's unit;
 * - a rate (`1/s`) per hour, or per second when its hourly figure is not a finite number;
 * - a share metric (`utilization`, `availability`, `scheduled_fraction`) as a percentage;
 * - three significant figures, never an exponent, a comma between thousands.
 */

/** Seconds in each Phase 1 time unit (spec 1 "Quantities"; `ithax.model.units.UNIT_SIZES`). */
const SECONDS: Readonly<Record<string, number>> = { s: 1, min: 60, h: 3_600, d: 86_400 };

/** Phase 1 time units above the second, largest first, with their length in seconds. */
export const TIME_UNITS: readonly (readonly [string, number])[] = (["d", "h", "min"] as const).map(
  (symbol) => [symbol, SECONDS[symbol] as number] as const,
);

/**
 * A value in SI units in a Phase 1 unit: a time in `s`, `min`, `h` or `d`, a rate per
 * second in `1/s`, `1/min`, `1/h` or `1/d`; `null` for another unit, or when the result
 * is not a finite number, as 1e308 per second is per hour (review of PR #165). Every rate
 * shown per hour goes through here.
 */
export function inUnit(si: number, unit: string): number | null {
  const rate = unit.startsWith("1/");
  const seconds = SECONDS[rate ? unit.slice(2) : unit];
  if (seconds === undefined) return null;
  const shown = rate ? si * seconds : si / seconds;
  return Number.isFinite(shown) ? shown : null;
}

const FRACTIONS = [".utilization", ".availability", ".scheduled_fraction"];

/** Shown for a mean or half-width that `summary.json` gives as `null` (undefined). */
export const UNDEFINED = "not defined";

/** `value` to `digits` significant figures, without an exponent: 2200 is "2,200". */
export function figures(value: number, digits = 3): string {
  if (!Number.isFinite(value)) return String(value);
  const rounded = Number(value.toPrecision(digits));
  if (rounded === 0) return "0";
  const places = Math.max(digits - 1 - Math.floor(Math.log10(Math.abs(rounded))), 0);
  return rounded.toLocaleString("en-US", {
    maximumFractionDigits: Math.min(places, 100),
    useGrouping: true,
  });
}

/** A fraction as a whole percentage, a half rounding up: 0.900985 is "90%". */
export function percent(fraction: number): string {
  return `${Math.floor(fraction * 100 + 0.5)}%`;
}

/** The largest Phase 1 time unit `seconds` reaches, and its length in seconds. */
export function timeUnit(seconds: number): readonly [string, number] {
  for (const unit of TIME_UNITS) {
    if (Math.abs(seconds) >= unit[1]) return unit;
  }
  return ["s", 1];
}

/** Whether a metric is a share of time, shown as a percentage. */
export function isShare(metric: string, unit: string): boolean {
  return unit === "1" && FRACTIONS.some((ending) => metric.endsWith(ending));
}

/**
 * A value in SI units as the interface shows it: a time in the largest unit `like` (by
 * default the value itself) reaches, a rate per hour, anything else as a plain number.
 */
export function quantity(value: number, unit: string, like?: number): string {
  if (unit === "s") {
    const [symbol] = timeUnit(like ?? value);
    return `${figures(inUnit(value, symbol) ?? value)} ${symbol}`;
  }
  if (unit === "1/s") {
    const perHour = inUnit(value, "1/h");
    return perHour === null ? `${figures(value)} per second` : `${figures(perHour)} per hour`;
  }
  return figures(value);
}

/** A metric's value: a share as a percentage to three figures, else as `quantity`. */
export function valueText(
  metric: string,
  value: number | null,
  unit: string,
  like?: number,
): string {
  if (value === null) return UNDEFINED;
  if (isShare(metric, unit)) return `${figures(value * 100)}%`;
  return quantity(value, unit, like);
}

/** A half-width as the likely range shows it, in its mean's unit: "± 2.09 min". */
export function rangeText(
  metric: string,
  halfWidth: number | null,
  unit: string,
  mean: number | null,
): string {
  if (halfWidth === null) return UNDEFINED;
  return `± ${valueText(metric, halfWidth, unit, mean ?? halfWidth)}`;
}

/** A confidence level as a percentage, without a trailing ".0": 0.975 is "97.5%". */
export function confidenceText(confidence: number): string {
  return `${Number((confidence * 100).toPrecision(12))}%`;
}
