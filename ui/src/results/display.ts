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

import { readNumber } from "../canvas/model";
import { own } from "../canvas/own";

/** Seconds in each Phase 1 time unit (spec 1 "Quantities"; `ithax.model.units.UNIT_SIZES`). */
const SECONDS: Readonly<Record<string, number>> = { s: 1, min: 60, h: 3_600, d: 86_400 };

/** Phase 1 time units above the second, largest first, with their length in seconds. */
export const TIME_UNITS: readonly (readonly [string, number])[] = (["d", "h", "min"] as const).map(
  (symbol) => [symbol, SECONDS[symbol] as number] as const,
);

/**
 * A value in SI units in a Phase 1 unit: a time in `s`, `min`, `h` or `d`, a rate per
 * second in `1/s`, `1/min`, `1/h` or `1/d`; `null` for another unit, or when the result
 * is not a finite number, as 1e308 per second is per hour (review of pull request 165). Every rate
 * shown per hour goes through here.
 */
export function inUnit(si: number, unit: string): number | null {
  const rate = unit.startsWith("1/");
  const seconds = own<number>(SECONDS, rate ? unit.slice(2) : unit);
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

const UNIT_WORDS: Readonly<Record<string, string>> = {
  s: "seconds",
  min: "minutes",
  h: "hours",
  d: "days",
  "1": "no unit",
};

/** A unit symbol in words (#96): `min` is "minutes", `1/h` "per hour", `1` "no unit". */
export function unitWords(symbol: string): string {
  const words = own<string>(UNIT_WORDS, symbol);
  if (words !== undefined) return words;
  const per = symbol.startsWith("1/") ? own<string>(UNIT_WORDS, symbol.slice(2)) : undefined;
  return per === undefined ? symbol : `per ${per.replace(/s$/, "")}`;
}

/** An ISO 8601 moment as a date, in local time: "8 Nov 2026"; other text as it is (#96). */
export function dateText(iso: string): string {
  const date = new Date(iso);
  if (iso === "" || Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** An ISO 8601 moment as a date and a time, in local time: "8 Nov 2026, 10:15" (#96). */
export function whenText(iso: string): string {
  const date = new Date(iso);
  if (iso === "" || Number.isNaN(date.getTime())) return iso;
  const time = date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  return `${dateText(iso)}, ${time}`;
}

/** Each statistic of spec 2 "Statistic definitions" in words. */
const STATISTICS: Readonly<Record<string, string>> = {
  "wait.mean": "average wait",
  utilization: "busy share",
  throughput: "throughput",
  "cycle_time.mean": "average time in the system",
  availability: "availability",
  scheduled_fraction: "scheduled share",
  "queue_length.mean": "average queue length",
  "queue_length.max": "longest queue",
  "stock.mean": "average stock",
  stockouts: "stockouts",
  orders: "orders placed",
  created: "items created",
  count: "items finished",
  discarded: "items discarded",
  "wip.mean": "average items in the system",
  // The time series' (spec 1 "Tables for the `process` domain").
  queue_length: "queue length",
  stock: "stock",
  wip: "items in the system",
};

/**
 * A metric's name in words (#91): the component's id, which the user chose, then its
 * statistic, so `till.wait.mean` is "till: average wait" and `model.wip.mean` "whole model:
 * average items in the system". A statistic not in spec 2's table is its parts in words.
 */
export function metricWords(metric: string): string {
  const dot = metric.indexOf(".");
  if (dot < 0) return metric;
  const component = metric.slice(0, dot);
  const statistic = metric.slice(dot + 1);
  const words = own<string>(STATISTICS, statistic) ?? statistic.replace(/[._]/g, " ");
  return `${component === "model" ? "whole model" : component}: ${words}`;
}

/**
 * A value in the base unit shown in a unit of `size` base units, or `null` when that is
 * not a finite number. Every display of a setting in a chosen unit goes through here
 * (review of pull request 196; `units.test.ts` checks no other code scales by a unit's size).
 */
export function inSize(value: number, size: number): number | null {
  const shown = value / size;
  return Number.isFinite(shown) ? shown : null;
}

/**
 * Typed text in a unit of `size` base units, as the value to send (review of pull request 196, two
 * findings): it never means something else than what was typed.
 *
 * - Empty is `null`, the default; text that is not a number is sent as typed.
 * - A result that is not a finite number is sent as typed, never as `null` (which the
 *   service takes as "use the default"), so the service refuses it with E184.
 * - A result within a float's noise of a whole number is that number (0.1 h is 6 min);
 *   otherwise it is sent as it is, and a whole-number setting refuses it.
 * - A non-zero entry is never sent as 0, which for the idle timeout means "never".
 */
export function typedInBase(text: string, size: number): unknown {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  const read = readNumber(trimmed);
  if (typeof read !== "number") return read;
  const value = read * size;
  if (!Number.isFinite(value)) return trimmed;
  const rounded = Math.round(value);
  if (rounded === 0 && read !== 0) return value === 0 ? trimmed : value;
  return Math.abs(value - rounded) <= 1e-9 * Math.max(1, Math.abs(value)) ? rounded : value;
}

/**
 * A metric in a sentence (#94): its statistic, then "at" its component, as in "the
 * average wait at weld"; a whole-model metric has no place ("the average items in the
 * system"); a name with no statistic as it is.
 */
export function metricPhrase(metric: string): string {
  const dot = metric.indexOf(".");
  if (dot < 0) return metric;
  const component = metric.slice(0, dot);
  const statistic = metric.slice(dot + 1);
  const words = own<string>(STATISTICS, statistic) ?? statistic.replace(/[._]/g, " ");
  return component === "model" ? `the ${words}` : `the ${words} at ${component}`;
}
