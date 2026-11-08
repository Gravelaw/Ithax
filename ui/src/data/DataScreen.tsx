/**
 * The Data screen (spec 3 "Screens" 3; `docs/design/flows.md` B5b to B7b;
 * `docs/design/wireframes/03-data.svg`).
 *
 * - **Files.** Import a CSV or Excel file (`POST .../data`, multipart), list them
 *   (`GET .../data`) and remove one (`DELETE .../data/{file}`). A number column's time unit
 *   is chosen in the columns table; choosing one imports the file again with its units,
 *   which needs the file picked in this window (the service keeps the bytes, not a way to
 *   send them back). The preview is the import's answer, so it is shown for files imported
 *   in this window.
 * - **Fit.** `POST .../data/{file}/fit` lists the candidates best first with "how well it
 *   fits" (the Kolmogorov–Smirnov statistic, 0 best); a histogram of the column (the fit's
 *   `histogram`) draws the chosen candidate's curve, with the same numbers as a table.
 * - **Use for.** A block's distribution setting takes the chosen candidate, or the column
 *   itself as an `empirical` `data` reference, with one `set_setting` through the same
 *   session and rules as the Canvas (`ModelFrame.tsx`). Before a column becomes a service
 *   or process time (a server's `service`, a delay's `time`) the screen asks "Does this
 *   column include time spent waiting?" (flows B7b): No sets it; Yes or Not sure shows the
 *   warning, and only "Use it anyway" sets it.
 *
 * Problems are the service's issue objects (E184, E185, E189), shown as it wrote them.
 * One data request at a time: its controls are unavailable until it is answered.
 */
import { TrashIcon, UploadSimpleIcon } from "@phosphor-icons/react";
import { type ChangeEvent, useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { ComponentType, DataFile, FitBody, Issue, Model, Project } from "../api/types";
import type { Route } from "../app/router";
import { lock, useBusy } from "../canvas/busy";
import { ModelScreen, type ModelWrites, useDraft, useSchema } from "../canvas/ModelFrame";
import {
  components,
  issueComponent,
  issueSetting,
  settingEdit,
  TIME_UNITS,
  words,
} from "../canvas/model";
import { own } from "../canvas/own";
import { FieldIssues } from "../canvas/SettingFields";
import type { CanvasSession } from "../canvas/session";
import { Chart, useChartColours } from "../charts/Chart";
import { fieldsText, histogramData, histogramOption, rounded } from "../charts/histogram";
import { Dialog } from "../components/Dialog";
import { ServiceProblem } from "../components/ServiceProblem";
import { usePendingRequest } from "../components/usePendingRequest";

/** The settings that are a service or process time: the question of flows B7b is asked. */
export const WORK_TIMES: readonly (readonly [string, string])[] = [
  ["server", "service"],
  ["delay", "time"],
];

export const WAITING_QUESTION = "Does this column include time spent waiting?";
export const WAITING_WARNING =
  "Service time must not include waiting, or the model counts the wait twice. Use a column that measures only the work, or estimate it.";

/** A block's distribution setting the column can be used for. */
export interface Target {
  key: string;
  id: string;
  setting: string;
  /** A service or process time: the waiting question is asked. */
  work: boolean;
}

/** Every distribution setting of the model's blocks, in model order. */
export function targetsOf(model: Model, types: Record<string, ComponentType>): Target[] {
  const found: Target[] = [];
  for (const component of components(model)) {
    for (const setting of own<ComponentType>(types, component.type)?.settings ?? []) {
      if (setting.kind !== "distribution") continue;
      found.push({
        key: `${component.id}/${setting.name}`,
        id: component.id,
        setting: setting.name,
        work: WORK_TIMES.some(([type, name]) => type === component.type && name === setting.name),
      });
    }
  }
  return found;
}

/** What "Use for" writes: the candidate, or the column itself as `empirical` `data`. */
export function usedValue(
  choice: "fitted" | "data",
  fit: Pick<FitBody, "file" | "column">,
  distribution: Readonly<Record<string, unknown>> | null,
): Record<string, unknown> | null {
  if (choice === "data") {
    return { dist: "empirical", data: { file: fit.file, column: fit.column } };
  }
  return distribution === null ? null : structuredClone({ ...distribution });
}

export function DataScreen({
  client,
  project,
  toolbar,
  onGo,
}: {
  client: ApiClient;
  project: Project | null;
  toolbar: HTMLElement | null;
  onGo: (route: Route) => void;
}) {
  const schema = useSchema(client);
  const types = schema?.kind === "ok" ? (schema.data["x-component-types"] ?? {}) : {};
  return (
    <ModelScreen client={client} project={project} toolbar={toolbar} heading="Data">
      {({ state, model, session, writes }) =>
        project === null ? null : (
          <DataParts
            client={client}
            pid={project.id}
            model={model}
            issues={state.issues}
            readOnly={state.failing}
            session={session}
            writes={writes}
            types={types}
            onCanvas={() => onGo({ screen: "canvas", projectId: project.id })}
          />
        )
      }
    </ModelScreen>
  );
}

/**
 * A fit and the listing it was computed from. It belongs to that listing alone: any change
 * of the listing (an import, which may change a unit while the bytes and their hash stay
 * the same, or a removal) is a new listing, so the fit is no longer shown or usable until
 * the column is fitted again (review of PR #47).
 */
interface FitShown {
  listing: DataFile[];
  body: FitBody;
}

function DataParts({
  client,
  pid,
  model,
  issues,
  readOnly,
  session,
  writes,
  types,
  onCanvas,
}: {
  client: ApiClient;
  pid: string;
  model: Model;
  issues: Issue[];
  readOnly: boolean;
  session: CanvasSession;
  writes: ModelWrites;
  types: Record<string, ComponentType>;
  onCanvas: () => void;
}) {
  const pending = usePendingRequest();
  const [files, setFiles] = useState<DataFile[] | null>(null);
  const [listProblem, setListProblem] = useState<ApiResult<unknown> | null>(null);
  const [problem, setProblem] = useState<ApiResult<unknown> | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [column, setColumn] = useState<string | null>(null);
  const [fit, setFit] = useState<FitShown | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  // The files picked in this window, by name, so a unit can be changed by importing again;
  // and the first rows each import answered with.
  const held = useRef(new Map<string, File>());
  const [previews, setPreviews] = useState(new Map<string, (number | string | null)[][]>());
  const inputId = useId();

  useEffect(() => {
    let live = true;
    void client.listData(pid).then((result) => {
      if (!live) return;
      if (result.kind === "ok") setFiles(result.data);
      else setListProblem(result);
    });
    return () => {
      live = false;
    };
  }, [client, pid]);

  const file = files?.find((item) => item.name === selected) ?? files?.[0] ?? null;

  const imported = useCallback(
    (result: ApiResult<DataFile & { preview: (number | string | null)[][] }>, picked: File) => {
      if (result.kind !== "ok") {
        setProblem(result);
        return;
      }
      setProblem(null);
      const { preview, ...entry } = result.data;
      held.current.set(entry.name, picked);
      setPreviews((before) => new Map(before).set(entry.name, preview));
      setFiles((before) => {
        const list = before ?? [];
        return list.some((item) => item.name === entry.name)
          ? list.map((item) => (item.name === entry.name ? entry : item))
          : [...list, entry];
      });
      setSelected(entry.name);
      // A data reference to this file is checked again (spec 1 E162).
      session.revalidate();
    },
    [session],
  );

  const importPicked = (event: ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0];
    event.target.value = "";
    if (picked === undefined) return;
    void pending.run(
      () => client.importData(pid, picked, picked.name),
      (result) => imported(result, picked),
    );
  };

  const changeUnit = (target: DataFile, name: string, unit: string | null) => {
    const picked = held.current.get(target.name);
    if (picked === undefined) {
      setProblem(null);
      writes.say(`To change a unit, import ${target.name} again in this window first.`);
      return;
    }
    const units: Record<string, string | null> = {};
    for (const item of target.columns) {
      if (item.type === "number") units[item.name] = item.name === name ? unit : item.unit;
    }
    void pending.run(
      () => client.importData(pid, picked, target.name, units),
      (result) => imported(result, picked),
    );
  };

  const remove = (name: string) => {
    setRemoving(null);
    void pending.run(
      () => client.deleteData(pid, name),
      (result) => {
        if (result.kind !== "ok") {
          setProblem(result);
          return;
        }
        setProblem(null);
        held.current.delete(name);
        setFiles(result.data);
        if (selected === name) setSelected(null);
        session.revalidate();
      },
    );
  };

  const runFit = (target: DataFile, name: string) => {
    // The listing the fit is asked against; a later listing does not show it.
    const listing = files;
    void pending.run(
      () => client.fitData(pid, target.name, name),
      (result) => {
        if (result.kind !== "ok") {
          setProblem(result);
          setFit(null);
          return;
        }
        setProblem(null);
        if (listing !== null) setFit({ listing, body: result.data });
      },
    );
  };

  const chosenColumn =
    file?.columns.find((item) => item.name === column)?.name ??
    file?.columns.find((item) => item.type === "number")?.name ??
    null;
  // A fit is shown only with the listing it was computed from, for the column chosen.
  const shownFit =
    fit !== null &&
    fit.listing === files &&
    fit.body.file === file?.name &&
    fit.body.column === chosenColumn
      ? fit.body
      : null;
  const preview = file === null ? undefined : previews.get(file.name);

  return (
    <div className="screen-body data-screen">
      <nav className="screen-list" aria-labelledby="files-heading" data-region="list">
        <h2 className="heading" id="files-heading">
          Files
        </h2>
        <input
          id={inputId}
          type="file"
          className="file-input"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          disabled={pending.busy}
          onChange={importPicked}
        />
        <label
          htmlFor={inputId}
          className="primary import-button"
          aria-disabled={pending.busy || undefined}
        >
          <UploadSimpleIcon aria-hidden="true" size={16} />
          Import CSV or Excel
        </label>
        {pending.busy ? (
          <p className="hint" role="status">
            Waiting for the service…
          </p>
        ) : null}
        <ServiceProblem result={listProblem} />
        {files !== null && files.length === 0 ? (
          <p className="muted">No files imported yet.</p>
        ) : null}
        <ul>
          {(files ?? []).map((item) => (
            <li key={item.name}>
              <button
                type="button"
                className="list-item"
                aria-current={item === file ? "true" : undefined}
                onClick={() => setSelected(item.name)}
              >
                <span className="mono">{item.name}</span>{" "}
                <span className="small">
                  {item.columns.length} column{item.columns.length === 1 ? "" : "s"} ·{" "}
                  {item.rows.toLocaleString("en")} row{item.rows === 1 ? "" : "s"}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {file !== null ? (
          <button
            type="button"
            className="secondary small-button"
            aria-disabled={pending.busy || undefined}
            onClick={() => {
              if (!pending.busy) setRemoving(file.name);
            }}
          >
            <TrashIcon aria-hidden="true" size={14} />
            Remove {file.name}
          </button>
        ) : null}
      </nav>
      <section className="data-main" aria-labelledby="file-heading">
        <ServiceProblem result={problem} />
        {file === null ? (
          <p className="muted">Import a file to see its columns and fit a distribution to one.</p>
        ) : (
          <>
            <h2 className="title mono" id="file-heading">
              {file.name}
            </h2>
            <Columns
              file={file}
              chosen={chosenColumn}
              busy={pending.busy}
              onChoose={setColumn}
              onUnit={(name, unit) => changeUnit(file, name, unit)}
            />
            <h3 className="heading">Preview (first rows)</h3>
            {preview === undefined ? (
              <p className="muted">
                The first rows are shown after the file is imported in this window.
              </p>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      {file.columns.map((item) => (
                        <th key={item.name} scope="col" className="mono">
                          {item.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.map((row, index) => (
                      // biome-ignore lint/suspicious/noArrayIndexKey: the preview's rows are in file order
                      <tr key={index}>
                        {file.columns.map((item, at) => (
                          <td key={item.name} className="mono">
                            {row[at] === null || row[at] === undefined ? "" : String(row[at])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>
      <section className="fit-panel" aria-labelledby="fit-heading">
        <h2 className="heading" id="fit-heading">
          {chosenColumn === null ? "Fit a distribution" : `Fit a distribution to ${chosenColumn}`}
        </h2>
        <button
          type="button"
          className="secondary"
          aria-disabled={pending.busy || file === null || chosenColumn === null || undefined}
          onClick={() => {
            if (!pending.busy && file !== null && chosenColumn !== null) runFit(file, chosenColumn);
          }}
        >
          Fit a distribution
        </button>
        {shownFit !== null ? (
          <FitResult
            key={`${shownFit.file} ${shownFit.column}`}
            fit={shownFit}
            model={model}
            issues={issues}
            readOnly={readOnly}
            writes={writes}
            types={types}
          />
        ) : null}
        <button type="button" className="link" onClick={onCanvas}>
          Go to the canvas
        </button>
      </section>
      {removing !== null ? (
        <RemoveDialog name={removing} onCancel={() => setRemoving(null)} onRemove={remove} />
      ) : null}
    </div>
  );
}

function RemoveDialog({
  name,
  onCancel,
  onRemove,
}: {
  name: string;
  onCancel: () => void;
  onRemove: (name: string) => void;
}) {
  const cancel = useRef<HTMLButtonElement>(null);
  return (
    <Dialog
      labelledBy="remove-file-title"
      describedBy="remove-file-text"
      onEscape={onCancel}
      initialFocus={cancel}
    >
      <h2 className="subheading" id="remove-file-title">
        Remove {name}?
      </h2>
      <p id="remove-file-text">
        The file is removed from the project. A block that uses its data then shows an error until
        it uses other data.
      </p>
      <div className="dialog-actions">
        <button ref={cancel} type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="danger" onClick={() => onRemove(name)}>
          <TrashIcon aria-hidden="true" size={16} />
          Remove
        </button>
      </div>
    </Dialog>
  );
}

function Columns({
  file,
  chosen,
  busy,
  onChoose,
  onUnit,
}: {
  file: DataFile;
  chosen: string | null;
  busy: boolean;
  onChoose: (name: string) => void;
  onUnit: (name: string, unit: string | null) => void;
}) {
  const group = useId();
  return (
    <>
      <h3 className="heading" id={`${group}-heading`}>
        Columns
      </h3>
      <div className="table-wrap">
        <table className="data-table" aria-labelledby={`${group}-heading`}>
          <thead>
            <tr>
              <th scope="col">Column</th>
              <th scope="col">Type</th>
              <th scope="col">Unit</th>
              <th scope="col">Fit this column</th>
            </tr>
          </thead>
          <tbody>
            {file.columns.map((item) => (
              <tr key={item.name} data-selected={item.name === chosen}>
                <th scope="row" className="mono">
                  {item.name}
                </th>
                <td>
                  {item.type === "number" ? "numbers" : item.type === "text" ? "text" : "empty"}
                </td>
                <td>
                  {item.type === "number" ? (
                    <select
                      aria-label={`Unit of ${item.name}`}
                      value={item.unit ?? ""}
                      {...lock(false, busy)}
                      onChange={(event) =>
                        onUnit(item.name, event.target.value === "" ? null : event.target.value)
                      }
                    >
                      <option value="">No unit (plain numbers)</option>
                      {TIME_UNITS.map((unit) => (
                        <option key={unit} value={unit}>
                          {unit}
                        </option>
                      ))}
                    </select>
                  ) : (
                    "—"
                  )}
                </td>
                <td>
                  <input
                    type="radio"
                    name={group}
                    aria-label={`Fit ${item.name}`}
                    checked={item.name === chosen}
                    onChange={() => onChoose(item.name)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function FitResult({
  fit,
  model,
  issues,
  readOnly,
  writes,
  types,
}: {
  fit: FitBody;
  model: Model;
  issues: Issue[];
  readOnly: boolean;
  writes: ModelWrites;
  types: Record<string, ComponentType>;
}) {
  const [chosen, setChosen] = useState(0);
  const [table, setTable] = useState(false);
  const colours = useChartColours();
  const candidate = fit.candidates[chosen] ?? fit.candidates[0];
  const distribution = candidate?.distribution ?? null;
  const name = typeof distribution?.dist === "string" ? distribution.dist : "distribution";
  const data = useMemo(() => histogramData(fit, distribution), [fit, distribution]);
  const option = useMemo(
    () =>
      histogramOption(
        data,
        { column: fit.column, unit: fit.unit, curveName: `Fitted ${name}` },
        colours,
      ),
    [data, fit.column, fit.unit, name, colours],
  );
  const group = useId();
  const unit = fit.unit === null ? "" : ` (${fit.unit})`;
  return (
    <>
      <p className="hint">
        {fit.values.toLocaleString("en")} values
        {fit.unit === null ? ", no unit" : `, in ${fit.unit}`}.
      </p>
      {fit.candidates.length === 0 ? (
        <p className="muted">No distribution fits this column.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <caption className="visually-hidden">Candidate distributions, best first</caption>
            <thead>
              <tr>
                <th scope="col">Use</th>
                <th scope="col">Distribution</th>
                <th scope="col">Fitted fields</th>
                <th
                  scope="col"
                  title="Kolmogorov–Smirnov statistic: 0 is a perfect fit, 1 the worst"
                >
                  How well it fits
                </th>
              </tr>
            </thead>
            <tbody>
              {fit.candidates.map((item, index) => {
                const dist = String(item.distribution.dist);
                return (
                  <tr key={dist} data-selected={index === chosen}>
                    <td>
                      <input
                        type="radio"
                        name={group}
                        aria-label={`Choose ${dist}`}
                        checked={index === chosen}
                        onChange={() => setChosen(index)}
                      />
                    </td>
                    <th scope="row" className="mono">
                      {dist}
                    </th>
                    <td title={fieldsText(item.distribution, true)}>
                      {fieldsText(item.distribution)}
                    </td>
                    <td title="Kolmogorov–Smirnov statistic: 0 is a perfect fit">
                      {item.score.toFixed(3)}
                      {index === 0 ? " (best)" : ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <h3 className="subheading" id={`${group}-chart`}>
        Your data and the fitted {name}
      </h3>
      <Chart
        option={option}
        label={`Histogram of ${fit.column} with the fitted ${name} curve. Show as table gives the numbers.`}
      />
      <p className="chart-caption">
        {data.curve.length > 0
          ? `Bars: your data. Line: the fitted ${name}. A good fit follows the bars.`
          : "Bars: your data. This distribution has no curve to draw."}
      </p>
      <button
        type="button"
        className="link"
        aria-expanded={table}
        onClick={() => setTable((open) => !open)}
      >
        {table ? "Hide the table" : "Show as table"}
      </button>
      {table ? (
        <div className="table-wrap">
          <table className="data-table">
            <caption className="visually-hidden">
              The histogram of {fit.column} and the fitted {name}
            </caption>
            <thead>
              <tr>
                <th scope="col">From{unit}</th>
                <th scope="col">To{unit}</th>
                <th scope="col">Values</th>
                <th scope="col">Fitted {name} (at the middle)</th>
              </tr>
            </thead>
            <tbody>
              {data.bins.map((bin, index) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: bins are in order
                <tr key={index}>
                  <td>{rounded(bin.from)}</td>
                  <td>{rounded(bin.to)}</td>
                  <td>{bin.count}</td>
                  <td>{bin.fitted === null ? "—" : bin.fitted.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <UseFor
        fit={fit}
        distribution={distribution}
        name={name}
        model={model}
        issues={issues}
        readOnly={readOnly}
        writes={writes}
        types={types}
      />
    </>
  );
}

type Answer = "yes" | "no" | "unsure" | null;

function UseFor({
  fit,
  distribution,
  name,
  model,
  issues,
  readOnly,
  writes,
  types,
}: {
  fit: FitBody;
  distribution: Record<string, unknown> | null;
  name: string;
  model: Model;
  issues: Issue[];
  readOnly: boolean;
  writes: ModelWrites;
  types: Record<string, ComponentType>;
}) {
  const busy = useBusy();
  const targets = targetsOf(model, types);
  // Drafts of this action: they go whenever the model shown changes (rule 3).
  const [targetKey, setTargetKey] = useDraft<string>("");
  const [choice, setChoice] = useDraft<"fitted" | "data">("fitted");
  const [answer, setAnswer] = useDraft<Answer>(null);
  const [applied, setApplied] = useState<{ id: string; setting: string } | null>(null);
  const target = targets.find((item) => item.key === targetKey) ?? null;
  const ids = useId();
  const value = usedValue(choice, fit, distribution);
  const waiting = target?.work === true;
  const needsAnswer = waiting && answer === null;
  const reason =
    target === null
      ? "Choose a block setting first."
      : value === null
        ? "Choose a distribution first."
        : needsAnswer
          ? "Answer the question about waiting first."
          : null;

  const apply = () => {
    if (reason !== null || target === null || value === null) return;
    const { id, setting } = target;
    void writes
      .edit(`use ${fit.column} for ${id} ${setting}`, (current) => {
        const component = components(current).find((item) => item.id === id);
        return component === undefined ? null : [settingEdit(component, [setting], value)];
      })
      .then((result) => {
        if (result?.kind !== "ok") return;
        setApplied({ id, setting });
        writes.say(
          choice === "data"
            ? `${id} ${words(setting).toLowerCase()} now uses the data of ${fit.column} as it is.`
            : `${id} ${words(setting).toLowerCase()} is now ${fieldsTextOf(value)}.`,
        );
      });
  };

  const shownIssues =
    applied === null
      ? []
      : issues.filter(
          (issue) =>
            issueComponent(issue, model) === applied.id &&
            (issueSetting(issue) ?? "").startsWith(`/${applied.setting}`),
        );

  return (
    <section className="use-for" aria-labelledby={`${ids}-heading`}>
      <h3 className="heading" id={`${ids}-heading`}>
        Use for
      </h3>
      {targets.length === 0 ? (
        <p className="muted">The model has no block with a time to set. Add one on the canvas.</p>
      ) : null}
      <div className="panel-field">
        <label htmlFor={`${ids}-target`} className="field-label">
          Block setting
        </label>
        <select
          id={`${ids}-target`}
          className="mono"
          value={target?.key ?? ""}
          {...lock(readOnly, busy)}
          onChange={(event) => {
            setTargetKey(event.target.value);
            setAnswer(null);
          }}
        >
          <option value="" disabled>
            Choose a block setting
          </option>
          {targets.map((item) => (
            <option key={item.key} value={item.key}>
              {item.id} · {item.setting}
              {item.work ? " (a service or process time)" : ""}
            </option>
          ))}
        </select>
      </div>
      <fieldset className="stack">
        <legend className="visually-hidden">What to use</legend>
        <label>
          <input
            type="radio"
            name={`${ids}-choice`}
            checked={choice === "fitted"}
            {...lock(readOnly, busy)}
            onChange={() => setChoice("fitted")}
          />
          Use the fitted distribution ({name}
          {distribution ? `, ${fieldsText(distribution)}` : ""})
        </label>
        <label>
          <input
            type="radio"
            name={`${ids}-choice`}
            checked={choice === "data"}
            {...lock(readOnly, busy)}
            onChange={() => setChoice("data")}
          />
          Use the data as it is (empirical, from this column)
        </label>
      </fieldset>
      {waiting ? (
        <fieldset className="waiting-question">
          <legend>{WAITING_QUESTION}</legend>
          <div className="choices-inline">
            {(
              [
                ["yes", "Yes"],
                ["no", "No"],
                ["unsure", "Not sure"],
              ] as const
            ).map(([option, label]) => (
              <label key={option}>
                <input
                  type="radio"
                  name={`${ids}-waiting`}
                  checked={answer === option}
                  {...lock(readOnly, busy)}
                  onChange={() => setAnswer(option)}
                />
                {label}
              </label>
            ))}
          </div>
          {answer === "yes" || answer === "unsure" ? (
            <p className="warning-text" role="alert">
              {WAITING_WARNING}
            </p>
          ) : null}
        </fieldset>
      ) : null}
      <div className="button-row">
        <button
          type="button"
          className="primary"
          {...lock(readOnly, busy || reason !== null)}
          aria-describedby={reason !== null ? `${ids}-reason` : undefined}
          onClick={apply}
        >
          {waiting && (answer === "yes" || answer === "unsure") ? "Use it anyway" : "Use it"}
        </button>
        {reason !== null ? (
          <span className="hint" id={`${ids}-reason`}>
            {reason}
          </span>
        ) : null}
        {target !== null ? (
          <button
            type="button"
            className="link"
            onClick={() => {
              setTargetKey("");
              setAnswer(null);
            }}
          >
            Cancel
          </button>
        ) : null}
      </div>
      <FieldIssues issues={shownIssues} />
    </section>
  );
}

function fieldsTextOf(value: Record<string, unknown>): string {
  const fields = fieldsText(value, true);
  return fields === "" ? String(value.dist) : `${String(value.dist)}, ${fields}`;
}
