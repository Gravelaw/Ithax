/**
 * The Settings screen (spec 3 "Screens" 7 and "Run monitor, Results and Settings";
 * `docs/design/wireframes/07-settings.svg`).
 *
 * It reads `GET /v1/settings`, `GET /v1/system` and `GET /v1/engines` when it opens, and
 * writes every change with one `PUT /v1/settings`, one at a time: while a write awaits its
 * answer every control is inert and a change tried meanwhile is not sent, which a notice
 * says. A typed value is sent as a number when it follows spec 1's number grammar and as
 * typed otherwise, so the service says what is wrong (E184); an emptied field sends `null`,
 * its default. `finding_thresholds` and `interface` are sent whole: the values shown with
 * the one change. Every field shows the saved value again after each answer, so no draft
 * outlives a write, accepted or refused.
 */
import { useEffect, useId, useRef, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type {
  Engine,
  FindingThresholds,
  InterfacePreferences,
  Motion,
  SettingsBody,
  SettingsChange,
  SystemInfo,
  TextSize,
  Theme,
  TierName,
} from "../api/types";
import { readNumber } from "../canvas/model";
import { RECOMMENDED_UNDO_STEPS } from "../canvas/useSession";
import { Dialog } from "../components/Dialog";
import { IssueList, ServiceProblem } from "../components/ServiceProblem";
import { usePendingRequest } from "../components/usePendingRequest";
import { figures, quantity } from "../results/display";
import { DEFAULT_PREFERENCES } from "./preferences";
import { useSettings } from "./SettingsContext";
import "../results/results.css";

/** Said when a change is tried while a write awaits its answer: it is not sent. */
export const SETTINGS_WAIT = "Not saved: a change was being saved. Make the change again.";
export const AT_NEXT_START =
  "Takes effect at the next start of the engine service. An empty field restores the default.";
export const AT_NEXT_RESULTS = "Takes effect at the next results you open.";
export const AT_ONCE = "Takes effect at once.";

const TIERS: readonly { value: TierName; label: string }[] = [
  { value: "low", label: "Low (4 cores, 8 GB)" },
  { value: "mid", label: "Mid (8 cores, 16 GB)" },
  { value: "high", label: "High (16 cores, 32 GB)" },
];
const THEMES: readonly { value: Theme; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];
const TEXT_SIZES: readonly TextSize[] = [100, 125, 150, 175, 200];
const MOTIONS: readonly { value: Motion; label: string }[] = [
  { value: "system", label: "System" },
  { value: "full", label: "Full" },
  { value: "reduced", label: "Reduced" },
  { value: "off", label: "Off" },
];

/** A size in bytes in plain words: "8.59 GB". */
export function bytesText(bytes: number): string {
  for (const [unit, size] of [
    ["TB", 1e12],
    ["GB", 1e9],
    ["MB", 1e6],
    ["kB", 1e3],
  ] as const) {
    if (bytes >= size) return `${figures(bytes / size)} ${unit}`;
  }
  return `${figures(bytes)} bytes`;
}

/** A typed value as written: empty is `null` (the default); a whole number beyond what the
 * interface holds exactly is sent as typed, so it is never rounded. */
export function typed(text: string): unknown {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  if (/^-?[0-9]+$/.test(trimmed) && !Number.isSafeInteger(Number(trimmed))) return trimmed;
  return readNumber(trimmed);
}

export function SettingsScreen({ client }: { client: ApiClient }) {
  const { settings, issues, save, refresh } = useSettings();
  const pending = usePendingRequest();
  const [answer, setAnswer] = useState<ApiResult<SettingsBody> | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Counts the answers, so every field shows the saved value again after each one.
  const [answers, setAnswers] = useState(0);
  const [system, setSystem] = useState<ApiResult<SystemInfo> | null>(null);
  const [engines, setEngines] = useState<ApiResult<Engine[]> | null>(null);
  const [restoring, setRestoring] = useState(false);

  useEffect(() => {
    let open = true;
    void refresh().then((result) => {
      if (open) {
        setAnswer(result.kind === "ok" ? null : result);
        setAnswers((count) => count + 1);
      }
    });
    void client.getSystem().then((result) => {
      if (open) setSystem(result);
    });
    void client.getEngines().then((result) => {
      if (open) setEngines(result);
    });
    return () => {
      open = false;
    };
  }, [client, refresh]);

  /** Sends one change, unless one awaits its answer; says so when it is not sent. */
  const write = (change: SettingsChange) => {
    if (pending.busy) {
      setNotice(SETTINGS_WAIT);
      setAnswers((count) => count + 1);
      return;
    }
    setNotice(null);
    void pending.run(
      () => save(change),
      (result) => {
        setAnswer(result.kind === "ok" ? null : result);
        setAnswers((count) => count + 1);
      },
    );
  };
  // The thresholds are sent whole; an emptied one is left out, which restores its default
  // (`null` is not a threshold the service takes, unlike a top-level key).
  const thresholds = (key: keyof FindingThresholds, value: unknown) => {
    const { [key]: _replaced, ...others } = settings.finding_thresholds;
    write({
      finding_thresholds: value === null ? others : { ...others, [key]: value },
    } as SettingsChange);
  };
  const preference = (key: keyof InterfacePreferences, value: unknown) =>
    write({ interface: { ...settings.interface, [key]: value } } as SettingsChange);

  const busy = pending.busy;
  const detected = system?.kind === "ok" ? system.data : null;
  const undoDefault = RECOMMENDED_UNDO_STEPS[settings.tier];

  return (
    <section className="settings-screen" aria-labelledby="screen-heading" aria-busy={busy}>
      <h1 id="screen-heading" className="title">
        Settings
      </h1>
      <div className="screen-notices" aria-live="polite">
        {notice !== null ? <p className="notice">{notice}</p> : null}
      </div>
      <ServiceProblem result={answer} />

      <div className="settings-section">
        <h2 className="heading">Run targets</h2>
        <table className="data-table">
          <caption className="visually-hidden">Where runs happen</caption>
          <tbody>
            <tr>
              <th scope="row" className="mono">
                local
              </th>
              <td>This computer: available</td>
            </tr>
            <tr>
              <th scope="row" className="mono">
                remote (SSH)
              </th>
              <td>Not available in this version</td>
            </tr>
            <tr>
              <th scope="row" className="mono">
                cluster (Slurm)
              </th>
              <td>Not available in this version</td>
            </tr>
          </tbody>
        </table>

        <h2 className="heading">Runs and limits</h2>
        <div className="settings-fields">
          <NumberField
            key={`runs ${answers}`}
            label="Runs at once"
            term="max_concurrent_runs"
            saved={settings.max_concurrent_runs}
            plain={(value) => `${figures(value)} at the same time (1 to 64)`}
            busy={busy}
            onCommit={(value) => write({ max_concurrent_runs: value } as SettingsChange)}
          />
          <NumberField
            key={`time ${answers}`}
            label="Time limit, in seconds"
            term="run_time_limit_s"
            saved={settings.run_time_limit_s}
            plain={(value) => `= ${quantity(value, "s")}`}
            busy={busy}
            onCommit={(value) => write({ run_time_limit_s: value } as SettingsChange)}
          />
          <NumberField
            key={`memory ${answers}`}
            label="Memory limit, in bytes"
            term="run_memory_limit_bytes"
            saved={settings.run_memory_limit_bytes}
            plain={(value) => `= ${bytesText(value)}`}
            busy={busy}
            onCommit={(value) => write({ run_memory_limit_bytes: value } as SettingsChange)}
          />
        </div>
        <p className="takes-effect">{AT_NEXT_START}</p>

        <h2 className="heading">Hardware</h2>
        <ServiceProblem result={system} />
        {detected !== null ? (
          <p>
            Detected: {detected.cores} cores,{" "}
            {detected.memory === null ? "memory unknown" : `${bytesText(detected.memory)} memory`},
            graphics:{" "}
            {detected.graphics === null ? "unknown" : detected.graphics.join(", ") || "none"}. This
            start uses the {detected.tier} tier, with {detected.workers} workers per run.
          </p>
        ) : null}
        <label className="settings-field">
          <span>Tier at the next start</span>
          <select
            key={`tier ${answers}`}
            defaultValue={settings.tier}
            aria-disabled={busy || undefined}
            onChange={(event) =>
              write({ tier: event.target.value === "" ? null : (event.target.value as TierName) })
            }
          >
            {TIERS.map((tier) => (
              <option key={tier.value} value={tier.value}>
                {tier.label}
              </option>
            ))}
            <option value="">Detect again at the next start</option>
          </select>
        </label>
        <p className="takes-effect">Takes effect at the next start of the engine service.</p>

        <h2 className="heading">Engines</h2>
        <ServiceProblem result={engines} />
        {engines?.kind === "ok" ? (
          <table className="data-table">
            <caption className="visually-hidden">Installed engines</caption>
            <thead>
              <tr>
                <th scope="col">Engine</th>
                <th scope="col">Version</th>
                <th scope="col">Domains</th>
                <th scope="col">Licence</th>
              </tr>
            </thead>
            <tbody>
              {engines.data.map((engine) => (
                <tr key={engine.name}>
                  <th scope="row" className="mono">
                    {engine.name}
                  </th>
                  <td>{engine.version}</td>
                  <td>{engine.domains.join(", ")}</td>
                  <td>{engine.licence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
        <p className="chart-caption">The engines are part of this version.</p>

        <h2 className="heading">Findings thresholds (proposals)</h2>
        <div className="settings-fields">
          <NumberField
            key={`bottleneck ${answers}`}
            label="Bottleneck at"
            term="bottleneck_utilization"
            saved={settings.finding_thresholds.bottleneck_utilization}
            plain={(value) => `busy ${figures(value * 100)}% of the time (0 to 1)`}
            busy={busy}
            onCommit={(value) => thresholds("bottleneck_utilization", value)}
          />
          <NumberField
            key={`idle ${answers}`}
            label="Idle below"
            term="idle_utilization"
            saved={settings.finding_thresholds.idle_utilization}
            plain={(value) => `busy ${figures(value * 100)}% of the time (0 to 1)`}
            busy={busy}
            onCommit={(value) => thresholds("idle_utilization", value)}
          />
          <NumberField
            key={`range ${answers}`}
            label="Likely range wider than"
            term="relative_half_width"
            saved={settings.finding_thresholds.relative_half_width}
            plain={(value) => `${figures(value * 100)}% of the average (above 0, at most 1)`}
            busy={busy}
            onCommit={(value) => thresholds("relative_half_width", value)}
          />
          <NumberField
            key={`time-floor ${answers}`}
            label="Shortest time judged, in seconds"
            term="min_time_s"
            saved={settings.finding_thresholds.min_time_s}
            plain={(value) => `= ${quantity(value, "s")}`}
            busy={busy}
            onCommit={(value) => thresholds("min_time_s", value)}
          />
          <NumberField
            key={`rate-floor ${answers}`}
            label="Lowest rate judged, per second"
            term="min_rate_per_s"
            saved={settings.finding_thresholds.min_rate_per_s}
            plain={(value) => `= ${quantity(value, "1/s")}`}
            busy={busy}
            onCommit={(value) => thresholds("min_rate_per_s", value)}
          />
        </div>
        <p className="takes-effect">{AT_NEXT_RESULTS} An empty field restores the default.</p>
        {issues.length > 0 ? (
          <div className="problem">
            <IssueList issues={issues} />
          </div>
        ) : null}
      </div>

      <div className="settings-section">
        <h2 className="heading">Appearance</h2>
        <p className="takes-effect">{AT_ONCE}</p>
        <Choices
          key={`theme ${answers}`}
          legend="Theme"
          name="theme"
          options={THEMES}
          saved={settings.interface.theme}
          busy={busy}
          onChoose={(value) => preference("theme", value)}
        />
        <Choices
          key={`text ${answers}`}
          legend="Text size"
          name="text-size"
          options={TEXT_SIZES.map((size) => ({ value: size, label: `${size}%` }))}
          saved={settings.interface.text_size}
          busy={busy}
          onChoose={(value) => preference("text_size", value)}
        />
        <Choices
          key={`motion ${answers}`}
          legend="Motion"
          name="motion"
          options={MOTIONS}
          saved={settings.interface.motion}
          busy={busy}
          onChoose={(value) => preference("motion", value)}
        />
        <Tick
          key={`charts ${answers}`}
          label="Colour-blind safe charts"
          saved={settings.interface.colour_blind_charts}
          busy={busy}
          onChange={(value) => preference("colour_blind_charts", value)}
        />

        <h2 className="heading">Canvas</h2>
        <p className="takes-effect">{AT_ONCE}</p>
        <Tick
          key={`ask ${answers}`}
          label="Ask before deleting"
          saved={settings.interface.ask_before_deleting}
          busy={busy}
          onChange={(value) => preference("ask_before_deleting", value)}
        />
        <NumberField
          key={`undo ${answers}`}
          label="Undo steps"
          term="undo_steps"
          saved={settings.interface.undo_steps}
          empty={`Empty: the tier's recommendation, ${undoDefault} (100 to 10,000)`}
          plain={(value) => `${figures(value)} steps (100 to 10,000)`}
          busy={busy}
          onCommit={(value) => preference("undo_steps", value)}
        />
        <div>
          <button
            type="button"
            className="secondary"
            aria-disabled={busy || undefined}
            onClick={() => (busy ? setNotice(SETTINGS_WAIT) : setRestoring(true))}
          >
            Restore all defaults
          </button>
          <p className="chart-caption">
            Appearance and canvas only; the other settings keep their values.
          </p>
        </div>

        <h2 className="heading">Service</h2>
        <p>Remote access: not available in this version (only this computer can connect).</p>

        <h2 className="heading" id="about-heading">
          About
        </h2>
        <p>
          Build a model of a process, run it many times, and see where the waits and bottlenecks
          are. Results are estimates from a simulation. Use them to support your judgement, not to
          replace it.
        </p>
        <p>
          This is free software under the GNU AGPL version 3.{" "}
          <a href="./LICENSE.txt">Read the licence</a>.{" "}
          <a href="./THIRD-PARTY-NOTICES.txt">Notices of the software it includes</a>.
        </p>
      </div>
      {restoring ? (
        <RestoreDialog
          onCancel={() => setRestoring(false)}
          onRestore={() => {
            setRestoring(false);
            write({
              interface: {
                ...DEFAULT_PREFERENCES,
                first_start_seen: settings.interface.first_start_seen,
              },
            });
          }}
        />
      ) : null}
    </section>
  );
}

/**
 * A number field: shows the saved value; Enter or leaving it sends the typed value when it
 * differs. `key` it by the answers' count, so it shows the saved value after each answer.
 */
function NumberField({
  label,
  term,
  saved,
  plain,
  empty,
  busy,
  onCommit,
}: {
  label: string;
  term: string;
  saved: number | null;
  plain: (value: number) => string;
  empty?: string;
  busy: boolean;
  onCommit: (value: unknown) => void;
}) {
  const id = useId();
  const shown = saved === null ? "" : String(saved);
  const commit = (text: string) => {
    if (text.trim() !== shown) onCommit(typed(text));
  };
  return (
    <div className="settings-field">
      <label htmlFor={id} title={term}>
        {label}
      </label>
      <input
        id={id}
        defaultValue={shown}
        inputMode="decimal"
        aria-describedby={`${id}-plain`}
        aria-disabled={busy || undefined}
        onBlur={(event) => commit(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") commit(event.currentTarget.value);
        }}
      />
      <span id={`${id}-plain`} className="hint">
        {saved === null ? (empty ?? "Default") : plain(saved)}
      </span>
    </div>
  );
}

function Choices<T extends string | number>({
  legend,
  name,
  options,
  saved,
  busy,
  onChoose,
}: {
  legend: string;
  name: string;
  options: readonly { value: T; label: string }[];
  saved: T;
  busy: boolean;
  onChoose: (value: T) => void;
}) {
  return (
    <fieldset className="choices">
      <legend>{legend}</legend>
      {options.map((option) => (
        <label key={option.value} className="choice">
          <input
            type="radio"
            name={name}
            defaultChecked={option.value === saved}
            aria-disabled={busy || undefined}
            onChange={() => onChoose(option.value)}
          />
          {option.label}
        </label>
      ))}
    </fieldset>
  );
}

function Tick({
  label,
  saved,
  busy,
  onChange,
}: {
  label: string;
  saved: boolean;
  busy: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="choice">
      <input
        type="checkbox"
        defaultChecked={saved}
        aria-disabled={busy || undefined}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  );
}

function RestoreDialog({ onCancel, onRestore }: { onCancel: () => void; onRestore: () => void }) {
  const cancel = useRef<HTMLButtonElement>(null);
  return (
    <Dialog
      labelledBy="restore-title"
      describedBy="restore-text"
      onEscape={onCancel}
      initialFocus={cancel}
    >
      <h2 className="subheading" id="restore-title">
        Restore all defaults?
      </h2>
      <p id="restore-text">
        Theme, text size, motion, colour-blind safe charts, ask before deleting and undo steps go
        back to their defaults. Runs, limits, the tier and the thresholds keep their values.
      </p>
      <div className="dialog-actions">
        <button ref={cancel} type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="primary" onClick={onRestore}>
          Restore
        </button>
      </div>
    </Dialog>
  );
}
