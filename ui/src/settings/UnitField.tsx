/**
 * A setting entered in a unit the user picks (#87: the idle timeout "in minutes, hours or
 * days, up to 7 days or never", owner decision D8; #96: no setting typed in bytes). The
 * service keeps the base unit (minutes, seconds, bytes); the field shows the saved value in
 * the largest unit that shows it whole, and writes what is typed times the unit's size.
 * Changing the unit re-reads the number shown in the new unit, as the Experiment screen's
 * unit pickers do. `never` adds a "Never" box that writes 0 (only the idle timeout).
 */
import { useId, useState } from "react";
import { readNumber } from "../canvas/model";
import { TIME_UNITS } from "../results/display";

export interface Unit {
  label: string;
  /** The unit's size in the setting's base unit. */
  size: number;
}

const SECONDS_IN: Readonly<Record<string, number>> = Object.fromEntries(TIME_UNITS);

function seconds(symbol: string): number {
  return SECONDS_IN[symbol] ?? 1;
}

/** The idle timeout's units, in minutes. */
export const IDLE_MINUTES: readonly Unit[] = [
  { label: "minutes", size: 1 },
  { label: "hours", size: seconds("h") / seconds("min") },
  { label: "days", size: seconds("d") / seconds("min") },
];

/** A run's time limit's units, in seconds. */
export const LIMIT_SECONDS: readonly Unit[] = [
  { label: "seconds", size: 1 },
  { label: "minutes", size: seconds("min") },
  { label: "hours", size: seconds("h") },
];

/** A memory size's units, in bytes (decimal, as `bytesText` names them). */
export const BYTES: readonly Unit[] = [
  { label: "MB", size: 1e6 },
  { label: "GB", size: 1e9 },
];

/** The largest unit that shows `saved` whole; else the largest it reaches; else the first. */
export function unitFor(saved: number | null, units: readonly Unit[]): Unit {
  const largest = [...units].reverse();
  const first = units[0] as Unit;
  if (saved === null || saved === 0) return largest.find((unit) => unit.size > 1) ?? first;
  return (
    largest.find((unit) => saved % unit.size === 0) ??
    largest.find((unit) => saved >= unit.size) ??
    first
  );
}

/** `saved` in `unit`, as typed text, without a float's noise. */
export function shownIn(saved: number, unit: Unit): string {
  return String(Number((saved / unit.size).toPrecision(12)));
}

/**
 * Typed text in the base unit: empty is `null` (the default); text that is not a number is
 * sent as typed, so the service refuses it with its own issue; with `whole`, a result within
 * a float's noise of a whole number is that number (0.1 h is 6 minutes).
 */
export function inUnits(text: string, unit: Unit, whole: boolean): unknown {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  const read = readNumber(trimmed);
  if (typeof read !== "number") return read;
  const value = read * unit.size;
  const rounded = Math.round(value);
  if (!whole) return rounded;
  return Math.abs(value - rounded) <= 1e-9 * Math.max(1, Math.abs(value)) ? rounded : value;
}

export function UnitField(props: {
  label: string;
  term: string;
  saved: number | null;
  units: readonly Unit[];
  /** The base unit holds whole numbers only (minutes, seconds); bytes are always rounded. */
  whole?: boolean;
  never?: boolean;
  hint?: string;
  busy: boolean;
  onCommit: (value: unknown) => void;
}) {
  const id = useId();
  const [unit, setUnit] = useState(() => unitFor(props.saved, props.units));
  const isNever = props.never === true && props.saved === 0;
  const shown = props.saved === null || isNever ? "" : shownIn(props.saved, unit);
  const [text, setText] = useState(shown);
  const whole = props.whole === true;
  const commit = (typedText: string, inUnit: Unit) => {
    const value = inUnits(typedText, inUnit, whole);
    if (value !== props.saved) props.onCommit(value);
  };
  return (
    <div className="settings-field">
      <label htmlFor={id} title={props.term}>
        {props.label}
      </label>
      <span className="unit-entry">
        <input
          id={id}
          value={text}
          inputMode="decimal"
          disabled={isNever}
          aria-describedby={props.hint ? `${id}-hint` : undefined}
          aria-disabled={props.busy || undefined}
          onChange={(event) => setText(event.target.value)}
          onBlur={(event) => commit(event.target.value, unit)}
          onKeyDown={(event) => {
            if (event.key === "Enter") commit(event.currentTarget.value, unit);
          }}
        />
        <select
          aria-label={`Unit of ${props.label}`}
          value={unit.label}
          disabled={isNever}
          aria-disabled={props.busy || undefined}
          onChange={(event) => {
            const chosen = props.units.find((item) => item.label === event.target.value) ?? unit;
            setUnit(chosen);
            if (text.trim() !== "") commit(text, chosen);
          }}
        >
          {props.units.map((item) => (
            <option key={item.label} value={item.label}>
              {item.label}
            </option>
          ))}
        </select>
        {props.never ? (
          <label className="choice">
            <input
              type="checkbox"
              checked={isNever}
              aria-disabled={props.busy || undefined}
              onChange={(event) => props.onCommit(event.target.checked ? 0 : null)}
            />
            Never
          </label>
        ) : null}
      </span>
      {props.hint ? (
        <span id={`${id}-hint`} className="hint">
          {props.hint}
        </span>
      ) : null}
    </div>
  );
}
