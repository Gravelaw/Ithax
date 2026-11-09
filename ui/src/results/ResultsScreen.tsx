/**
 * The Results screen (spec 3 "Screens" 6 and "Run monitor, Results and Settings"; spec 4
 * "Findings in plain language"; `docs/design/wireframes/06-results.svg`; flows L9 and B12).
 *
 * It shows the run its address names, or else the project's most recent `done` run, from
 * `GET /v1/runs/{rid}`, `.../summary` and, for a simulation, `.../tables/replications` and
 * `.../tables/timeseries`. Everything shown is worked out from those answers for that run;
 * the view of one run is keyed by its id, so nothing outlives the run it came from.
 *
 * The order: the headline card (the first finding, which says why), the findings and the
 * thresholds' W220 issues, the key numbers with their likely range, the differences
 * between scenarios, the charts of the run's kind each with a table, the replications
 * table, the "Tell us what you built" link and the footer. Exports: each table as CSV,
 * a PDF made here with the footer on every page, and the project zip.
 */
import { DownloadSimpleIcon } from "@phosphor-icons/react";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import type { Project, Run, SummaryBody, TableRow } from "../api/types";
import type { Route } from "../app/router";
import { own } from "../canvas/own";
import { Chart, useSeriesColours } from "../charts/Chart";
import { IssueList, ServiceProblem } from "../components/ServiceProblem";
import { usePendingRequest } from "../components/usePendingRequest";
import { useLessonFor } from "../learn/LearnContext";
import { LessonResult } from "../learn/LessonResult";
import {
  barGroups,
  barsOption,
  decisionsOption,
  overTime,
  overTimeOption,
  timeseriesMetrics,
  trialPoints,
  trialsOption,
} from "./charts";
import { figures, rangeText, UNDEFINED, valueText } from "./display";
import { makePdf } from "./pdf";
import { headline, reportBlocks, ruleName } from "./report";
import { saveFile } from "./save";
import {
  differencesOf,
  footerOf,
  kindOf,
  type Scenario,
  type Search,
  type Solution,
  scenariosOf,
  searchOf,
  solutionOf,
} from "./summary";
import "./results.css";

/** Where "Tell us what you built" goes (spec 0 "Success measures"): it only opens the browser. */
export const FEEDBACK_URL = "https://github.com/Gravelaw/Ithax/issues/new";

/** Said when an export is pressed while another awaits its answer: it is not made. */
export const EXPORT_WAIT = "Not exported: an export was under way. Press it again.";

interface Props {
  client: ApiClient;
  project: Project | null;
  runId: string | undefined;
  onGo: (route: Route) => void;
}

export function ResultsScreen({ client, project, runId, onGo }: Props) {
  if (project === null) {
    return (
      <p className="screen-message" role="status">
        Opening the project…
      </p>
    );
  }
  if (runId !== undefined) {
    return <RunResults key={runId} client={client} project={project} rid={runId} onGo={onGo} />;
  }
  return <LatestDone key={project.id} client={client} project={project} onGo={onGo} />;
}

/** The project's most recent `done` run, read when the screen opens. */
function LatestDone({
  client,
  project,
  onGo,
}: {
  client: ApiClient;
  project: Project;
  onGo: (route: Route) => void;
}) {
  const [listed, setListed] = useState<ApiResult<Run[]> | null>(null);
  useEffect(() => {
    let open = true;
    void client.listRuns(project.id).then((result) => {
      if (open) setListed(result);
    });
    return () => {
      open = false;
    };
  }, [client, project.id]);
  if (listed === null) {
    return (
      <p className="screen-message" role="status">
        Reading the runs…
      </p>
    );
  }
  if (listed.kind !== "ok") return <ServiceProblem result={listed} />;
  const done = listed.data.filter((run) => run.state === "done").at(-1);
  if (done === undefined) {
    return (
      <section className="results-screen" aria-labelledby="results-heading">
        <h1 id="results-heading" className="title">
          Results
        </h1>
        <p>No run of this project is done yet.</p>
        <button
          type="button"
          className="secondary"
          onClick={() => onGo({ screen: "monitor", projectId: project.id })}
        >
          Open the Run monitor
        </button>
      </section>
    );
  }
  return (
    <RunResults key={done.run_id} client={client} project={project} rid={done.run_id} onGo={onGo} />
  );
}

interface Loaded {
  run: Run;
  body: SummaryBody;
  replications: ApiResult<TableRow[]> | null;
  timeseries: ApiResult<TableRow[]> | null;
}

/** One run's results; `key` it by the run id. */
function RunResults({
  client,
  project,
  rid,
  onGo,
}: {
  client: ApiClient;
  project: Project;
  rid: string;
  onGo: (route: Route) => void;
}) {
  const [problem, setProblem] = useState<ApiResult<unknown> | null>(null);
  const [notDone, setNotDone] = useState<Run | null>(null);
  const [loaded, setLoaded] = useState<Loaded | null>(null);

  useEffect(() => {
    let open = true;
    void (async () => {
      const run = await client.getRun(rid);
      if (!open) return;
      if (run.kind !== "ok") {
        setProblem(run);
        return;
      }
      if (run.data.state !== "done") {
        setNotDone(run.data);
        return;
      }
      const summary = await client.getSummary(rid);
      if (!open) return;
      if (summary.kind !== "ok") {
        setProblem(summary);
        return;
      }
      const simulated = kindOf(summary.data.summary) !== "optimization";
      const [replications, timeseries] = simulated
        ? await Promise.all([
            client.getTable(rid, "replications"),
            client.getTable(rid, "timeseries"),
          ])
        : [null, null];
      if (open) setLoaded({ run: run.data, body: summary.data, replications, timeseries });
    })();
    return () => {
      open = false;
    };
  }, [client, rid]);

  if (problem !== null) {
    return (
      <section className="results-screen" aria-labelledby="results-heading">
        <h1 id="results-heading" className="title">
          Results
        </h1>
        <ServiceProblem result={problem} />
      </section>
    );
  }
  if (notDone !== null) {
    return (
      <section className="results-screen" aria-labelledby="results-heading">
        <h1 id="results-heading" className="title">
          Results
        </h1>
        <p>
          The run <span className="mono">{rid}</span> is {notDone.state}; its results are written
          when it is done.
        </p>
        <button
          type="button"
          className="secondary"
          onClick={() => onGo({ screen: "monitor", projectId: project.id, runId: rid })}
        >
          Open the Run monitor
        </button>
      </section>
    );
  }
  if (loaded === null) {
    return (
      <p className="screen-message" role="status">
        Reading the results…
      </p>
    );
  }
  return <Shown client={client} project={project} rid={rid} loaded={loaded} onGo={onGo} />;
}

function Shown({
  client,
  project,
  rid,
  loaded,
  onGo,
}: {
  client: ApiClient;
  project: Project;
  rid: string;
  loaded: Loaded;
  onGo: (route: Route) => void;
}) {
  // The run of a lesson's exercise shows the prediction and the explanation first (AKS-124).
  const { learning, exit } = useLessonFor(project.id);
  const { run, body } = loaded;
  const { summary, findings, issues } = body;
  const kind = kindOf(summary);
  const scenarios = scenariosOf(summary);
  const differences = differencesOf(summary);
  const search = searchOf(summary);
  const footer = footerOf(summary, run);
  const exports = usePendingRequest();
  const [exportProblem, setExportProblem] = useState<ApiResult<unknown> | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const replications = loaded.replications?.kind === "ok" ? loaded.replications.data : null;
  const timeseries = loaded.timeseries?.kind === "ok" ? loaded.timeseries.data : null;

  /** One export at a time; a press meanwhile is not taken, and says so. */
  const exportWith = (make: () => Promise<ApiResult<unknown> | null>) => {
    if (exports.busy) {
      setNotice(EXPORT_WAIT);
      return;
    }
    setNotice(null);
    setExportProblem(null);
    void exports.run(make, (result) => setExportProblem(result));
  };
  const table = (name: string) =>
    exportWith(async () => {
      const result = await client.tableCsv(rid, name);
      if (result.kind === "ok") saveFile(result.data.blob, `${rid}-${name}.csv`);
      return result;
    });
  const pdf = () =>
    exportWith(async () => {
      const title = typeof summary.model === "string" ? summary.model : rid;
      const bytes = makePdf(reportBlocks(summary, findings, issues), footer, `Results: ${title}`);
      saveFile(new Blob([bytes as BlobPart], { type: "application/pdf" }), `${rid}.pdf`);
      return null;
    });
  const zip = () =>
    exportWith(async () => {
      const result = await client.exportProject(project.id);
      if (result.kind === "ok") saveFile(result.data.blob, `${fileName(project)}.zip`);
      return result;
    });

  return (
    <section className="results-screen" aria-labelledby="results-heading">
      <div className="results-top">
        <h1 id="results-heading" className="title">
          Results
        </h1>
        <div className="button-row" aria-busy={exports.busy}>
          {kind !== "optimization" ? (
            <>
              <button
                type="button"
                className="secondary"
                aria-disabled={exports.busy || undefined}
                onClick={() => table("replications")}
              >
                <DownloadSimpleIcon aria-hidden="true" size={16} />
                Export repeat runs (CSV)
              </button>
              <button
                type="button"
                className="secondary"
                aria-disabled={exports.busy || undefined}
                onClick={() => table("timeseries")}
              >
                <DownloadSimpleIcon aria-hidden="true" size={16} />
                Export values over time (CSV)
              </button>
            </>
          ) : null}
          <button
            type="button"
            className="secondary"
            aria-disabled={exports.busy || undefined}
            onClick={pdf}
          >
            <DownloadSimpleIcon aria-hidden="true" size={16} />
            Export PDF
          </button>
          <button
            type="button"
            className="secondary"
            aria-disabled={exports.busy || undefined}
            onClick={zip}
          >
            <DownloadSimpleIcon aria-hidden="true" size={16} />
            Export project (zip)
          </button>
        </div>
      </div>
      <div className="screen-notices" aria-live="polite">
        {notice !== null ? <p className="notice">{notice}</p> : null}
      </div>
      <ServiceProblem result={exportProblem} />
      {learning !== null && learning.runId === rid ? (
        <LessonResult learning={learning} onGo={onGo} onExit={exit} />
      ) : null}
      <p className="headline-card">{headline(findings)}</p>

      <h2 className="heading" id="findings-heading">
        Findings
      </h2>
      {findings.length === 0 ? (
        <p>No finding rule fired at the thresholds in Settings.</p>
      ) : (
        <ul className="findings" aria-labelledby="findings-heading">
          {findings.map((finding, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: findings are in the rules' order
            <li key={index} className={`finding finding-${finding.severity}`}>
              <span className="finding-rule">{ruleName(finding.rule)}</span>
              <span>{finding.text}</span>
            </li>
          ))}
        </ul>
      )}
      {issues.length > 0 ? (
        <div className="problem">
          <IssueList issues={issues} />
        </div>
      ) : null}

      {kind === "optimization" ? <Plan solution={solutionOf(summary)} /> : null}
      {search !== null ? <Trials search={search} /> : null}
      {scenarios.length > 0 ? <KeyNumbers scenarios={scenarios} /> : null}
      {differences.length > 0 ? (
        <>
          <h2 className="heading">Differences between options</h2>
          {differences.map((difference) => (
            <div key={`${difference.scenario} ${difference.against}`} className="table-wrap">
              <table className="data-table">
                <caption>
                  <span className="mono">{difference.scenario}</span> against{" "}
                  <span className="mono">{difference.against}</span>
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Metric</th>
                    <th scope="col">Difference</th>
                    <th scope="col">Likely range of the difference</th>
                    <th scope="col">Told apart?</th>
                  </tr>
                </thead>
                <tbody>
                  {difference.metrics.map(({ name, estimate, separated }) => (
                    <tr key={name}>
                      <th scope="row" className="mono">
                        {name}
                      </th>
                      <td>{valueText(name, estimate.mean, estimate.unit)}</td>
                      <td>{rangeText(name, estimate.half_width, estimate.unit, estimate.mean)}</td>
                      <td>{separated ? "Yes" : "Not yet"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </>
      ) : null}
      {scenarios.length > 0 ? <Bars scenarios={scenarios} /> : null}
      {timeseries !== null && timeseries.length > 0 ? <OverTimeChart rows={timeseries} /> : null}
      <ServiceProblem result={loaded.timeseries} />

      {kind !== "optimization" ? (
        <>
          <h2 className="heading">Repeat runs</h2>
          <ServiceProblem result={loaded.replications} />
          {replications !== null ? <Replications rows={replications} /> : null}
        </>
      ) : null}

      <p className="feedback">
        <a href={FEEDBACK_URL} target="_blank" rel="noopener noreferrer">
          Tell us what you built (opens your browser)
        </a>
      </p>
      <footer className="results-footer">
        {footer.map((item) => (
          <span key={item}>{item}</span>
        ))}
      </footer>
    </section>
  );
}

/** A name for the zip from the project's name: letters, digits, space, `.`, `_` and `-`. */
export function fileName(project: Project): string {
  const name = (project.name ?? "").replace(/[^A-Za-z0-9 ._-]/g, "_").trim();
  return name === "" ? "project" : name;
}

function ShowAsTable({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        className="link"
        aria-expanded={open}
        aria-label={`${open ? "Hide the table" : "Show as table"}: ${label}`}
        onClick={() => setOpen((shown) => !shown)}
      >
        {open ? "Hide the table" : "Show as table"}
      </button>
      {open ? <div className="table-wrap">{children}</div> : null}
    </>
  );
}

function KeyNumbers({ scenarios }: { scenarios: readonly Scenario[] }) {
  return (
    <>
      <h2 className="heading">Key numbers</h2>
      {scenarios.map((scenario) => (
        <div key={scenario.id} className="table-wrap">
          <table className="data-table key-numbers">
            <caption>
              {scenarios.length > 1 ? (
                <>
                  Option <span className="mono">{scenario.id}</span>
                </>
              ) : (
                <span className="visually-hidden">Key numbers</span>
              )}
            </caption>
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">Average</th>
                <th scope="col" title="The 95% confidence interval, as a half-width">
                  Likely range of the average
                </th>
                <th scope="col" title="Replications">
                  Repeat runs
                </th>
              </tr>
            </thead>
            <tbody>
              {scenario.metrics.map(([name, estimate]) => (
                <tr key={name}>
                  <th scope="row" className="mono">
                    {name}
                  </th>
                  <td>{valueText(name, estimate.mean, estimate.unit)}</td>
                  <td>{rangeText(name, estimate.half_width, estimate.unit, estimate.mean)}</td>
                  <td>{estimate.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      <p className="chart-caption">
        Display units are chosen here; the run's files and tables stay in SI units.
      </p>
    </>
  );
}

function Bars({ scenarios }: { scenarios: readonly Scenario[] }) {
  const colours = useSeriesColours();
  const groups = useMemo(() => barGroups(scenarios), [scenarios]);
  return (
    <>
      {groups.map((group) => (
        <figure key={group.family} className="result-chart">
          <figcaption className="subheading">{group.title}</figcaption>
          <Chart
            option={barsOption(group, colours)}
            label={`${group.title}. Show as table gives the numbers.`}
          />
          <ShowAsTable label={group.title}>
            <table className="data-table">
              <caption className="visually-hidden">{group.title}</caption>
              <thead>
                <tr>
                  <th scope="col">Component</th>
                  <th scope="col">Option</th>
                  <th scope="col">{group.unit}</th>
                  <th scope="col">Likely range</th>
                </tr>
              </thead>
              <tbody>
                {group.scenarios.flatMap((scenario, s) =>
                  group.components.map((component, c) => {
                    const value = group.values[s]?.[c] ?? null;
                    return (
                      <tr key={`${scenario} ${component}`}>
                        <th scope="row" className="mono">
                          {component}
                        </th>
                        <td className="mono">{scenario}</td>
                        <td>{value === null ? UNDEFINED : figures(value.mean)}</td>
                        <td>
                          {value === null || value.half === null
                            ? UNDEFINED
                            : `± ${figures(value.half)}`}
                        </td>
                      </tr>
                    );
                  }),
                )}
              </tbody>
            </table>
          </ShowAsTable>
        </figure>
      ))}
    </>
  );
}

function OverTimeChart({ rows }: { rows: readonly TableRow[] }) {
  const colours = useSeriesColours();
  const metrics = useMemo(() => timeseriesMetrics(rows), [rows]);
  const [picked, setPicked] = useState("");
  const metric = metrics.includes(picked) ? picked : (metrics[0] ?? "");
  const data = useMemo(() => overTime(rows, metric), [rows, metric]);
  const title = `Over time: ${metric}, average of the repeat runs`;
  return (
    <figure className="result-chart">
      <figcaption className="subheading">Over time, average of the repeat runs</figcaption>
      <label className="inline-field">
        <span>Value</span>
        <select className="mono" value={metric} onChange={(event) => setPicked(event.target.value)}>
          {metrics.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <Chart
        option={overTimeOption(data, colours)}
        label={`${title}. Show as table gives the numbers.`}
      />
      <p className="chart-caption">
        The value at each recorded time, averaged over the repeat runs; the settling-in time is
        included.
      </p>
      <ShowAsTable label={title}>
        <table className="data-table">
          <caption className="visually-hidden">{title}</caption>
          <thead>
            <tr>
              <th scope="col">Time ({data.timeSymbol})</th>
              {data.lines.map((line) => (
                <th key={line.scenario} scope="col" className="mono">
                  {line.scenario}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.times.map((time, index) => (
              <tr key={time}>
                <th scope="row">{figures(time, 4)}</th>
                {data.lines.map((line) => {
                  const value = line.values[index] ?? null;
                  return <td key={line.scenario}>{value === null ? "—" : figures(value, 4)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </ShowAsTable>
    </figure>
  );
}

function Trials({ search }: { search: Search }) {
  const colours = useSeriesColours();
  const points = useMemo(() => trialPoints(search), [search]);
  return (
    <>
      <h2 className="heading">The search</h2>
      <figure className="result-chart">
        <figcaption className="subheading">Every trial, and the best found</figcaption>
        <Chart
          option={trialsOption(search, points, colours)}
          label={`Every trial's ${search.metric} in the order tried, with the best found. The table of all trials gives the numbers.`}
        />
        <p className="chart-caption">
          One dot per trial. Filled: meets every limit. Hollow: breaks one. The dashed line is the
          best found. A trial checked with all repeat runs shows that check's average.
        </p>
      </figure>
      <div className="table-wrap">
        <table className="data-table trials">
          <caption>All trials, in the order tried</caption>
          <thead>
            <tr>
              <th scope="col">Trial</th>
              {search.variables.map((name) => (
                <th key={name} scope="col" className="mono">
                  {name}
                </th>
              ))}
              <th scope="col" className="mono">
                {search.metric}
              </th>
              <th scope="col">Likely range</th>
              <th scope="col">Meets every limit?</th>
              <th scope="col">Checked with all repeat runs?</th>
            </tr>
          </thead>
          <tbody>
            {search.trials.map((trial) => {
              const objective = trial.objective;
              return (
                <tr key={trial.index} data-selected={trial.best || undefined}>
                  <th scope="row">
                    {trial.index}
                    {trial.index === 0 ? " (starting values)" : ""}
                    {trial.best ? " (best)" : ""}
                  </th>
                  {search.variables.map((name) => {
                    const value = own<number>(trial.set, name);
                    return <td key={name}>{value === undefined ? "—" : figures(value, 4)}</td>;
                  })}
                  <td>
                    {objective === null
                      ? UNDEFINED
                      : valueText(search.metric, objective.mean, objective.unit)}
                  </td>
                  <td>
                    {objective === null
                      ? UNDEFINED
                      : rangeText(
                          search.metric,
                          objective.half_width,
                          objective.unit,
                          objective.mean,
                        )}
                  </td>
                  <td>{trial.feasible ? "Yes" : "No"}</td>
                  <td>{trial.confirmed ? "Yes" : "No"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="chart-caption">
        {search.status === "infeasible"
          ? "No trial checked with all repeat runs meets every limit."
          : search.separated
            ? "The best is clearly better than the next best trial."
            : "The best cannot yet be told apart from the next best trial."}
      </p>
    </>
  );
}

function Plan({ solution }: { solution: Solution }) {
  const colours = useSeriesColours();
  return (
    <>
      <h2 className="heading">The best plan</h2>
      <p>
        Status: <span className="mono">{solution.status}</span>. Goal:{" "}
        {solution.objective === null ? UNDEFINED : figures(solution.objective, 4)}.
      </p>
      {solution.variables.length > 0 ? (
        <figure className="result-chart">
          <figcaption className="subheading">Decisions</figcaption>
          <Chart
            option={decisionsOption(solution, colours)}
            label="The value of each decision. The table beside it gives the numbers."
          />
          <div className="table-wrap">
            <table className="data-table">
              <caption className="visually-hidden">Decisions</caption>
              <thead>
                <tr>
                  <th scope="col">Decision</th>
                  <th scope="col">Value</th>
                </tr>
              </thead>
              <tbody>
                {solution.variables.map(([name, value]) => (
                  <tr key={name}>
                    <th scope="row" className="mono">
                      {name}
                    </th>
                    <td>{figures(value, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </figure>
      ) : null}
      {solution.limits.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table">
            <caption>Limits: the fully used ones hold the result back</caption>
            <thead>
              <tr>
                <th scope="col">Limit</th>
                <th scope="col">Fully used?</th>
                <th scope="col">Room left</th>
              </tr>
            </thead>
            <tbody>
              {solution.limits.map((limit) => (
                <tr key={limit.name}>
                  <th scope="row" className="mono">
                    {limit.name}
                  </th>
                  <td>{limit.tight ? "Yes" : "No"}</td>
                  <td>{limit.slack === null ? UNDEFINED : figures(limit.slack, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}

function Replications({ rows }: { rows: readonly TableRow[] }) {
  const columns = rows[0] === undefined ? [] : Object.keys(rows[0]);
  return (
    <section
      className="table-wrap replications"
      // biome-ignore lint/a11y/noNoninteractiveTabindex: a scrolling region takes the focus, so the keyboard can scroll it (WCAG 2.1.1)
      tabIndex={0}
      aria-label="Every repeat run's values"
    >
      <table className="data-table">
        <caption className="visually-hidden">
          Every repeat run's value of every metric, in SI units
        </caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} scope="col">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: rows are in the table's order
            <tr key={index}>
              {columns.map((column) => {
                const value = row[column];
                return (
                  <td
                    key={column}
                    className={column === "metric" || column === "scenario" ? "mono" : undefined}
                  >
                    {value === null ? "" : String(value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
