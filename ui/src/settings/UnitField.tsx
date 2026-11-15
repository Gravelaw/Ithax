/**
 * A setting entered in a unit the user picks (#87: the idle timeout "in minutes, hours or
 * days, up to 7 days or never", owner decision D8; #96: no setting typed in bytes). The
 * service keeps the base unit (minutes, seconds, bytes); the field shows the saved value in
 * the largest unit that shows it whole, and writes what is typed times the unit's size.
 * Changing the unit re-reads the number shown in the new unit, as the Experiment screen's
 * unit pickers do. `never` adds a "Never" box that writes 0 (only the idle timeout).
 */
import { useId, useState } from "react";
import { inSize, TIME_UNITS, typedInBase } from "../results/display";

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
  const shown = inSize(saved, unit.size);
  return shown === null ? String(saved) : String(Number(shown.toPrecision(12)));
}

/** Typed text in the base unit, through the shared `typedInBase` (review of pull request 196). */
export function inUnits(text: string, unit: Unit): unknown {
  return typedInBase(text, unit.size);
}

/** Said when 0 is typed where "Never" has its own box (review of pull request 196). */
export const USE_NEVER = 'For no limit, tick "Never"; a typed 0 is not taken.';

export function UnitField(props: {
  label: string;
  term: string;
  saved: number | null;
  units: readonly Unit[];
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
  const [refused, setRefused] = useState(false);
  const commit = (typedText: string, inUnit: Unit) => {
    const value = inUnits(typedText, inUnit);
    // "Never" is reached only through its own box (review of pull request 196).
    setRefused(props.never === true && value === 0);
    if (props.never === true && value === 0) return;
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
      {refused ? (
        <span className="hint notice" role="status">
          {USE_NEVER}
        </span>
      ) : null}
      {props.hint ? (
        <span id={`${id}-hint`} className="hint">
          {props.hint}
        </span>
      ) : null}
    </div>
  );
}
