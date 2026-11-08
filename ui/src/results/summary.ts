/**
 * What the Results screen reads from a run's `summary.json` (spec 1 "Run folder and
 * results"; spec 2 "Simulation-based optimization" for `search`, "Mathematical
 * optimization" for a solution). The file is the product's own, but it is read
 * defensively: a part of another shape is not shown, never guessed.
 */
import type { Estimate, Run, Summary } from "../api/types";
import { hasOwn, own } from "../canvas/own";
import { confidenceText } from "./display";

/** Exactly the sentence spec 3 "Screens" 6 asks for. */
export const NO_WARRANTY = "Simulation results are estimates and carry no warranty.";

export type RunKind = "process" | "search" | "optimization";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function numberOrNull(value: unknown): number | null | undefined {
  if (value === null) return null;
  return isNumber(value) ? value : undefined;
}

/** A metric's estimate, when it has the shape spec 1 gives it. */
export function estimateOf(value: unknown): Estimate | null {
  if (!isRecord(value)) return null;
  const mean = numberOrNull(value.mean);
  const half = numberOrNull(value.half_width);
  if (mean === undefined || half === undefined) return null;
  if (typeof value.unit !== "string" || !isNumber(value.n)) return null;
  return { mean, half_width: half, unit: value.unit, n: value.n };
}

/** The estimates of a `metrics` object, in its order; others are left out. */
export function metricsOf(value: unknown): [string, Estimate][] {
  if (!isRecord(value)) return [];
  const found: [string, Estimate][] = [];
  for (const [name, item] of Object.entries(value)) {
    const estimate = estimateOf(item);
    if (estimate !== null) found.push([name, estimate]);
  }
  return found;
}

/** A search run holds `search`; a process run `scenarios`; an optimization neither. */
export function kindOf(summary: Summary): RunKind {
  if (isRecord(summary.search)) return "search";
  if (isRecord(summary.scenarios)) return "process";
  return "optimization";
}

export interface Scenario {
  id: string;
  metrics: [string, Estimate][];
}

/** The scenarios in the summary's order, each with its metrics in the table's order. */
export function scenariosOf(summary: Summary): Scenario[] {
  const scenarios = summary.scenarios;
  if (!isRecord(scenarios)) return [];
  return Object.entries(scenarios).map(([id, scenario]) => ({
    id,
    metrics: isRecord(scenario) ? metricsOf(scenario.metrics) : [],
  }));
}

export interface Difference {
  scenario: string;
  against: string;
  metrics: { name: string; estimate: Estimate; separated: boolean }[];
}

/** The paired differences between scenarios (spec 1 "Differences"). */
export function differencesOf(summary: Summary): Difference[] {
  if (!Array.isArray(summary.differences)) return [];
  const found: Difference[] = [];
  for (const item of summary.differences) {
    if (!isRecord(item) || typeof item.scenario !== "string" || typeof item.against !== "string") {
      continue;
    }
    const metrics = isRecord(item.metrics) ? item.metrics : {};
    found.push({
      scenario: item.scenario,
      against: item.against,
      metrics: Object.entries(metrics).flatMap(([name, value]) => {
        const estimate = estimateOf(value);
        return estimate === null || !isRecord(value)
          ? []
          : [{ name, estimate, separated: value.separated === true }];
      }),
    });
  }
  return found;
}

export interface Trial {
  /** The order evaluated, from 0 (the starting values). */
  index: number;
  set: Record<string, number>;
  objective: Estimate | null;
  feasible: boolean;
  confirmed: boolean;
  best: boolean;
}

export interface Search {
  status: string;
  metric: string;
  before: number | null;
  after: number | null;
  separated: boolean;
  variables: string[];
  trials: Trial[];
}

function numbersOf(value: unknown): Record<string, number> {
  if (!isRecord(value)) return {};
  return Object.fromEntries(
    Object.entries(value).filter((entry): entry is [string, number] => isNumber(entry[1])),
  );
}

function sameSet(first: Record<string, number>, second: Record<string, number>): boolean {
  const keys = Object.keys(first);
  return (
    keys.length === Object.keys(second).length &&
    keys.every((key) => hasOwn(second, key) && own(second, key) === own(first, key))
  );
}

/** A search run's `search` object, with every trial in the order evaluated. */
export function searchOf(summary: Summary): Search | null {
  const search = summary.search;
  if (!isRecord(search) || !isRecord(search.objective)) return null;
  const metric = search.objective.metric;
  if (typeof metric !== "string") return null;
  const best = numbersOf(isRecord(search.best) ? search.best.set : undefined);
  const candidates = Array.isArray(search.candidates) ? search.candidates : [];
  const trials = candidates.flatMap((item, index): Trial[] => {
    if (!isRecord(item)) return [];
    const set = numbersOf(item.set);
    const metrics = isRecord(item.metrics) ? item.metrics : {};
    return [
      {
        index,
        set,
        objective: estimateOf(own(metrics, metric)),
        feasible: item.feasible === true,
        confirmed: item.confirmed === true,
        best: search.status === "feasible" && sameSet(set, best),
      },
    ];
  });
  const variables = [...new Set(trials.flatMap((trial) => Object.keys(trial.set)))];
  return {
    status: typeof search.status === "string" ? search.status : "",
    metric,
    before: numberOrNull(search.objective.before) ?? null,
    after: numberOrNull(search.objective.after) ?? null,
    separated: search.separated === true,
    variables,
    trials,
  };
}

export interface Solution {
  status: string;
  objective: number | null;
  variables: [string, number][];
  limits: { name: string; tight: boolean; slack: number | null }[];
}

/** An optimization run's solution (spec 2: `status`, `objective`, `variables`, `constraints`). */
export function solutionOf(summary: Summary): Solution {
  const constraints = isRecord(summary.constraints) ? summary.constraints : {};
  return {
    status: typeof summary.status === "string" ? summary.status : "",
    objective: numberOrNull(summary.objective) ?? null,
    variables: Object.entries(numbersOf(summary.variables)),
    limits: Object.entries(constraints).flatMap(([name, value]) =>
      isRecord(value)
        ? [{ name, tight: value.tight === true, slack: numberOrNull(value.slack) ?? null }]
        : [],
    ),
  };
}

/**
 * The footer of spec 3 "Screens" 6, one item per entry: model name, run id, fidelity
 * label, replications and confidence, engine name and version, and the sentence.
 */
export function footerOf(summary: Summary, run: Run): string[] {
  const model = typeof summary.model === "string" ? summary.model : "not recorded";
  const fidelity =
    typeof summary.fidelity_label === "string" ? summary.fidelity_label : "not recorded";
  const replications = summary.replications;
  const confidence = summary.confidence;
  const replicated =
    isNumber(replications) && isNumber(confidence)
      ? `Replications: ${replications} · Confidence: ${confidenceText(confidence)}`
      : "Replications and confidence: not replicated";
  const engine =
    run.engine === null
      ? "not recorded"
      : run.engine.version === null
        ? run.engine.name
        : `${run.engine.name} ${run.engine.version}`;
  return [
    `Model: ${model}`,
    `Run: ${run.run_id}`,
    `Fidelity: ${fidelity}`,
    replicated,
    `Engine: ${engine}`,
    NO_WARRANTY,
  ];
}
