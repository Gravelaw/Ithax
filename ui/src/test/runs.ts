/**
 * Runs and summaries for the component tests of the Run monitor and Results (AKS-138),
 * shaped as the service gives them (spec 3 "A run as the run endpoints show it"; spec 1
 * "Run folder and results"; spec 2 for `search` and a solution).
 */
import type { Finding, Run, Summary } from "../api/types";

export const RID = "20261108T101502-K3QX7A";

export function aRun(change: Partial<Run> = {}): Run {
  return {
    run_id: RID,
    project_id: "p1",
    experiment_id: "base",
    engine: { name: "simpy", version: "0.0.0" },
    state: "done",
    fraction: 1,
    message: "",
    created: "2026-11-08T10:15:02.000Z",
    started: "2026-11-08T10:15:02.100Z",
    ended: "2026-11-08T10:15:05.000Z",
    error: null,
    ...change,
  };
}

/** The three-machine line at the M8 values (seed 12345), shortened to the metrics used. */
export function lineSummary(): Summary {
  return {
    model: "Three-machine line",
    experiment: "base",
    fidelity: "standard",
    fidelity_label: "Standard: 30 replications of 100 h, 95% confidence",
    replications: 30,
    confidence: 0.95,
    scenarios: {
      default: {
        set: {},
        metrics: {
          "cut.utilization": { mean: 0.6, half_width: 0.004, unit: "1", n: 30 },
          "cut.wait.mean": { mean: 108, half_width: 9, unit: "s", n: 30 },
          "weld.utilization": { mean: 0.901, half_width: 0.011, unit: "1", n: 30 },
          "weld.wait.mean": { mean: 941.5, half_width: 125.4, unit: "s", n: 30 },
          "exit.throughput": { mean: 0.00833, half_width: 0.0001, unit: "1/s", n: 30 },
          "model.wip.mean": { mean: 12.4, half_width: null, unit: "1", n: 30 },
        },
      },
    },
    differences: [],
    warnings: [],
  };
}

export const LINE_FINDINGS: Finding[] = [
  {
    rule: "bottleneck",
    severity: "info",
    component: "weld",
    scenario: "default",
    text: "weld is the bottleneck: busy 90% of the time, with an average wait of 15.7 min.",
    evidence: { "weld.utilization": 0.901, "weld.wait.mean": 941.5 },
  },
  {
    rule: "not_enough_runs",
    severity: "warning",
    component: null,
    scenario: "default",
    text: "The estimates for weld.wait.mean are still uncertain: weld.wait.mean is 15.7 min plus or minus 2.09 min. About 60 replications would be needed for a 10% interval.",
    evidence: {},
  },
];

/** Two scenarios, for the differences and the bars side by side. */
export function optionsSummary(): Summary {
  const one = lineSummary();
  const scenarios = one.scenarios as Record<string, unknown>;
  return {
    ...one,
    scenarios: { default: scenarios.default, faster: scenarios.default },
    differences: [
      {
        scenario: "faster",
        against: "default",
        metrics: {
          "weld.wait.mean": { mean: -300, half_width: 50, unit: "s", n: 30, separated: true },
          "weld.utilization": { mean: 0, half_width: 0.01, unit: "1", n: 30, separated: false },
        },
      },
    ],
  };
}

/** The machine-count search (spec 2): tills 1 to 3, the best 2. */
export function searchSummary(): Summary {
  const metrics = (wait: number, busy: number, n: number) => ({
    "till.wait.mean": { mean: wait, half_width: wait / 10, unit: "s", n },
    "till.utilization": { mean: busy, half_width: 0.01, unit: "1", n },
  });
  return {
    model: "Coffee shop",
    experiment: "base",
    fidelity: "standard",
    fidelity_label: "Standard: 30 replications of 200 h, 95% confidence",
    replications: 30,
    confidence: 0.95,
    scenarios: { default: { set: { tills: 2 }, metrics: metrics(14.7, 0.375, 30) } },
    differences: [],
    warnings: [],
    search: {
      status: "feasible",
      best: { set: { tills: 2 } },
      objective: { metric: "till.wait.mean", before: 270, after: 14.7 },
      separated: true,
      candidates: [
        { set: { tills: 1 }, metrics: metrics(270, 0.75, 30), feasible: true, confirmed: true },
        { set: { tills: 2 }, metrics: metrics(14.7, 0.375, 30), feasible: true, confirmed: true },
        { set: { tills: 3 }, metrics: metrics(1.5, 0.25, 10), feasible: false, confirmed: false },
      ],
    },
  };
}

export const SEARCH_FINDINGS: Finding[] = [
  {
    rule: "optimization_result",
    severity: "info",
    component: null,
    scenario: null,
    text: "Best found: tills 2. till.wait.mean improved from 4.5 min to 14.7 s. It is clearly better than the next best setting tried.",
    evidence: {},
  },
];

/** The product mix (spec 2): 24 chairs, 14 tables, 2,200. */
export function planSummary(): Summary {
  return {
    model: "Product mix",
    status: "optimal",
    objective: 2200,
    variables: { chairs: 24, tables: 14 },
    constraints: {
      wood: { tight: true, slack: 0 },
      labour: { tight: true, slack: 0 },
    },
    fidelity_label: "Standard",
    warnings: [],
  };
}
