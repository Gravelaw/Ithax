/**
 * The Run monitor (spec 3 "Screens" 5 and "Run monitor, Results and Settings";
 * `docs/design/wireframes/05-run-monitor.svg`; flows L8 and B11).
 *
 * The run shown is the one the address names, or else the project's most recently
 * accepted run that is `queued` or `running`, or else its most recent run, so a page
 * opened or reloaded while a run goes on finds it. Its state, progress and the service's
 * message come from `GET /v1/runs/{rid}/events`, which starts with the state and the
 * latest progress; the view of one run is keyed by its id, so nothing of one run is shown
 * for another. The project's runs are read when the screen opens and again at each `run`
 * event of the project. One cancel at a time, its controls inert meanwhile; a refusal is
 * the service's issue. Live key numbers are not available (no Phase 1 adapter sends
 * `metrics` events), which the screen says.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiClient, ApiResult } from "../api/client";
import { FINAL_STATES, type Project, type Run, type RunState } from "../api/types";
import type { Route } from "../app/router";
import { IssueList, LOST_CONTACT, ServiceProblem } from "../components/ServiceProblem";
import { usePendingRequest } from "../components/usePendingRequest";
import "../results/results.css";

/** Said in place of live key numbers (AKS-138, logged fallback). */
export const NO_LIVE_NUMBERS =
  "Live numbers are not available: this engine reports them only when the run is done.";

/** Said when a cancel is pressed while another awaits its answer: it is not sent. */
export const CANCEL_WAIT = "Not sent: a cancel was waiting for its answer. Press it again.";

/** The state words, in plain language. */
export const STATE_WORDS: Readonly<Record<RunState, string>> = {
  queued: "Waiting to start",
  running: "Running",
  done: "Done",
  failed: "Failed",
  cancelled: "Cancelled",
};

const UNFINISHED: readonly RunState[] = ["queued", "running"];

/** The run a page without a run in its address shows. */
export function chooseRun(runs: readonly Run[]): string | null {
  const unfinished = runs.filter((run) => UNFINISHED.includes(run.state));
  return (unfinished.at(-1) ?? runs.at(-1))?.run_id ?? null;
}

interface Props {
  client: ApiClient;
  project: Project | null;
  runId: string | undefined;
  onGo: (route: Route) => void;
}

export function RunMonitor({ client, project, runId, onGo }: Props) {
  if (project === null) {
    return (
      <p className="screen-message" role="status">
        Opening the project…
      </p>
    );
  }
  return <Monitor key={project.id} client={client} project={project} runId={runId} onGo={onGo} />;
}

function Monitor({
  client,
  project,
  runId,
  onGo,
}: {
  client: ApiClient;
  project: Project;
  runId: string | undefined;
  onGo: (route: Route) => void;
}) {
  const [listed, setListed] = useState<ApiResult<Run[]> | null>(null);
  const asked = useRef(0);
  const cancel = usePendingRequest();
  const [refused, setRefused] = useState<ApiResult<Run> | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // The latest answer wins: an earlier request answered late is not shown.
  const reload = useCallback(() => {
    const ask = ++asked.current;
    void client.listRuns(project.id).then((result) => {
      if (ask === asked.current) setListed(result);
    });
  }, [client, project.id]);

  useEffect(() => {
    reload();
    const socket = client.projectEvents(project.id, {
      onEvent: (event) => {
        if (event.type === "run") reload();
      },
    });
    return () => {
      asked.current += 1;
      socket.close();
    };
  }, [client, project.id, reload]);

  const runs = listed?.kind === "ok" ? listed.data : [];
  const shown = runId ?? (listed?.kind === "ok" ? chooseRun(runs) : null);

  const cancelRun = (rid: string) => {
    if (cancel.busy) {
      setNotice(CANCEL_WAIT);
      return;
    }
    setNotice(null);
    void cancel.run(
      () => client.cancelRun(rid),
      (result) => setRefused(result.kind === "ok" ? null : result),
    );
  };

  return (
    <section className="results-screen" aria-labelledby="monitor-heading">
      <h1 id="monitor-heading" className="title">
        Run monitor
      </h1>
      <div className="screen-notices" aria-live="polite">
        {notice !== null ? <p className="notice">{notice}</p> : null}
      </div>
      <ServiceProblem result={refused} />
      {listed === null ? (
        <p className="screen-message" role="status">
          Reading the runs…
        </p>
      ) : null}
      <ServiceProblem result={listed} />
      {shown !== null ? (
        <RunView
          key={shown}
          client={client}
          rid={shown}
          run={runs.find((run) => run.run_id === shown) ?? null}
          busy={cancel.busy}
          onCancel={() => cancelRun(shown)}
          onResults={() => onGo({ screen: "results", projectId: project.id, runId: shown })}
        />
      ) : listed?.kind === "ok" ? (
        <p>
          No run of this project yet. Start one with Run on the{" "}
          <button
            type="button"
            className="link"
            onClick={() => onGo({ screen: "canvas", projectId: project.id })}
          >
            Canvas
          </button>
          .
        </p>
      ) : null}
      {runs.length > 0 ? (
        <>
          <h2 className="heading">Runs of this project</h2>
          <div className="table-wrap">
            <table className="data-table">
              <caption className="visually-hidden">Runs of this project, oldest first</caption>
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">State</th>
                  <th scope="col">Experiment</th>
                  <th scope="col">Accepted</th>
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.run_id} data-selected={run.run_id === shown || undefined}>
                    <th scope="row" className="mono">
                      {run.run_id}
                    </th>
                    <td>{STATE_WORDS[run.state] ?? run.state}</td>
                    <td className="mono">{run.experiment_id ?? "none"}</td>
                    <td>{run.created}</td>
                    <td className="row-actions">
                      {run.run_id !== shown ? (
                        <button
                          type="button"
                          className="link"
                          aria-label={`Watch ${run.run_id}`}
                          onClick={() =>
                            onGo({ screen: "monitor", projectId: project.id, runId: run.run_id })
                          }
                        >
                          Watch
                        </button>
                      ) : null}
                      {UNFINISHED.includes(run.state) ? (
                        <button
                          type="button"
                          className="link"
                          aria-label={`Cancel ${run.run_id}`}
                          aria-disabled={cancel.busy || undefined}
                          onClick={() => cancelRun(run.run_id)}
                        >
                          Cancel
                        </button>
                      ) : null}
                      {run.state === "done" ? (
                        <button
                          type="button"
                          className="link"
                          aria-label={`Results of ${run.run_id}`}
                          onClick={() =>
                            onGo({ screen: "results", projectId: project.id, runId: run.run_id })
                          }
                        >
                          Results
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="chart-caption">
            Runs keep going if this window closes; opening it again finds the run that is going. At
            most the number of runs Settings allows run at once; the others wait their turn.
          </p>
        </>
      ) : null}
    </section>
  );
}

interface Progress {
  state: RunState | null;
  fraction: number;
  message: string;
}

/** One run's progress, from its events; `key` it by the run id. */
function RunView({
  client,
  rid,
  run,
  busy,
  onCancel,
  onResults,
}: {
  client: ApiClient;
  rid: string;
  /** The run as the project's list shows it, for its experiment and error. */
  run: Run | null;
  busy: boolean;
  onCancel: () => void;
  onResults: () => void;
}) {
  const [progress, setProgress] = useState<Progress>({ state: null, fraction: 0, message: "" });
  const [lost, setLost] = useState(false);
  const [missing, setMissing] = useState<ApiResult<Run> | null>(null);
  const [attempt, setAttempt] = useState(0);

  // biome-ignore lint/correctness/useExhaustiveDependencies: "Connect again" counts an attempt, which opens the stream again
  useEffect(() => {
    let open = true;
    let final = false;
    const socket = client.runEvents(rid, {
      onEvent: (event) => {
        if (!open) return;
        if (event.type === "state") {
          final = FINAL_STATES.includes(event.state);
          setProgress((before) => ({ ...before, state: event.state }));
        } else if (event.type === "progress") {
          setProgress((before) => ({
            ...before,
            fraction: event.fraction,
            message: event.message,
          }));
        }
      },
      onClose: (code) => {
        if (!open) return;
        if (code === 1008) {
          // The service does not know the run (E185): show its own words for it.
          void client.getRun(rid).then((result) => {
            if (open) setMissing(result);
          });
        } else if (!final) {
          setLost(true);
        }
      },
    });
    return () => {
      open = false;
      socket.close();
    };
  }, [client, rid, attempt]);

  const percent = Math.round(progress.fraction * 100);
  const going = progress.state === "queued" || progress.state === "running";
  return (
    <section className="run-view" aria-labelledby="run-heading">
      <h2 id="run-heading" className="title mono">
        Run {rid}
      </h2>
      <p className="run-facts">
        <span className="state-badge" role="status">
          {progress.state === null ? "Connecting…" : STATE_WORDS[progress.state]}
        </span>
        {run !== null ? (
          <span className="muted">
            Experiment {run.experiment_id ?? "none"} · accepted {run.created}
          </span>
        ) : null}
      </p>
      {missing !== null ? <ServiceProblem result={missing} /> : null}
      {lost ? (
        <div className="notice notice-error" role="alert">
          <span>{LOST_CONTACT}</span>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setLost(false);
              setAttempt((count) => count + 1);
            }}
          >
            Connect again
          </button>
        </div>
      ) : null}
      <div
        className="progress"
        role="progressbar"
        aria-label={`Progress of run ${rid}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-valuetext={`${percent}%${progress.message === "" ? "" : `, ${progress.message}`}`}
      >
        <div className="progress-done" style={{ width: `${percent}%` }} />
      </div>
      <p className="progress-text">
        <span className="progress-percent">{percent}%</span> {progress.message}
      </p>
      <div className="button-row">
        {going ? (
          <button
            type="button"
            className="secondary"
            aria-disabled={busy || undefined}
            onClick={onCancel}
          >
            Cancel run
          </button>
        ) : null}
        {progress.state === "done" ? (
          <button type="button" className="primary" onClick={onResults}>
            See the results
          </button>
        ) : null}
      </div>
      {progress.state === "failed" && run?.error ? <IssueList issues={[run.error]} /> : null}
      <h3 className="subheading">Key numbers</h3>
      <p className="live-note">{NO_LIVE_NUMBERS}</p>
      <p className="chart-caption">
        The averages and their likely ranges are on Results once the run is done.
      </p>
    </section>
  );
}
