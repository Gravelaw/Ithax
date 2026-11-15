/**
 * The Results screen's content as the PDF export holds it (spec 3 "Run monitor, Results
 * and Settings": the headline, the findings, the key numbers and the run kind's tables,
 * with the footer on every page). Charts are left out: the PDF is text, and each chart's
 * numbers are in a table here or on the screen.
 */
import type { Finding, Issue, Summary } from "../api/types";
import { own } from "../canvas/own";
import { figures, metricPhrase, metricWords, rangeText, UNDEFINED, valueText } from "./display";
import type { Block } from "./pdf";
import { differencesOf, kindOf, scenariosOf, searchOf, solutionOf } from "./summary";

/** The rules' names in plain words (spec 4 "Findings in plain language"). */
export const RULE_NAMES: Readonly<Record<string, string>> = {
  bottleneck: "Bottleneck",
  unstable: "Cannot keep up",
  idle_capacity: "Idle capacity",
  not_enough_runs: "Not enough runs",
  optimization_result: "Optimization result",
};

/** A finding's rule in plain words; an unknown rule as the service named it. */
export function ruleName(rule: string): string {
  return Object.hasOwn(RULE_NAMES, rule) ? (RULE_NAMES[rule] ?? rule) : rule;
}

/** The headline: the first finding, in the rules' order; or that none fired. */
export const NO_FINDING = "No finding rule fired at the thresholds in Settings.";

/** The measures a comparison headline names first, by the end of their name. */
const HEADLINE_MEASURES = [".wait.mean", ".cycle_time.mean", ".throughput", ".queue_length.mean"];

/** The findings that name a cause (spec 4 "Finding rules"). */
const CAUSES = ["bottleneck", "idle_capacity"];

/**
 * The headline (canvas-interactions.md "Results say why"; #94). With two options or more
 * it names the change between the first pair the summary compares, on the measure it tells
 * apart first (a wait, then a time in the system, a throughput, a queue, else the first
 * told apart), and the cause a finding of the earlier option points to: "Option faster
 * cuts the average wait at weld from 15.7 min to 10.7 min, because weld is the
 * bottleneck: …". With no cause it gives the change only; when nothing is told apart it
 * says so. With one option it is the first finding, or that none fired.
 */
export function headline(findings: readonly Finding[], summary?: Summary): string {
  const compared = summary === undefined ? null : comparison(summary, findings);
  return compared ?? findings[0]?.text ?? NO_FINDING;
}

function comparison(summary: Summary, findings: readonly Finding[]): string | null {
  const [pair] = differencesOf(summary);
  if (pair === undefined) return null;
  const apart = pair.metrics.filter((item) => item.separated && item.estimate.mean !== 0);
  const chosen =
    HEADLINE_MEASURES.map((end) => apart.find((item) => item.name.endsWith(end))).find(
      (item) => item !== undefined,
    ) ?? apart[0];
  if (chosen === undefined || chosen.estimate.mean === null) {
    return `Option ${pair.scenario} and option ${pair.against} cannot be told apart yet on any measure; more repeat runs would tell.`;
  }
  // Each option's own mean, as its key numbers show it; the paired difference only says
  // whether they are told apart and which way (review of pull request 199: with a
  // replication undefined on one side, the baseline plus the difference is not the option's
  // mean).
  const meanOf = (id: string) =>
    scenariosOf(summary)
      .find((scenario) => scenario.id === id)
      ?.metrics.find(([name]) => name === chosen.name)?.[1];
  const before = meanOf(pair.against);
  const after = meanOf(pair.scenario)?.mean;
  if (before === undefined || before.mean === null || after === undefined || after === null) {
    return null;
  }
  const name = chosen.name;
  const change =
    `Option ${pair.scenario} ${chosen.estimate.mean < 0 ? "cuts" : "raises"} ` +
    `${metricPhrase(name)} from ${valueText(name, before.mean, before.unit)} to ` +
    `${valueText(name, after, before.unit, before.mean)}`;
  const cause = findings.find(
    (finding) => finding.scenario === pair.against && CAUSES.includes(finding.rule),
  );
  if (cause === undefined) return `${change}.`;
  const text = cause.text.replace(/\.$/, "");
  return `${change}, because ${text.charAt(0).toLowerCase()}${text.slice(1)}.`;
}

const H1 = 18;
const H2 = 14;
const BODY = 11;

export function reportBlocks(
  summary: Summary,
  findings: readonly Finding[],
  issues: readonly Issue[],
): Block[] {
  const blocks: Block[] = [];
  const heading = (text: string) => blocks.push({ text, size: H2, bold: true, before: 12 });
  const line = (text: string, before = 2) => blocks.push({ text, size: BODY, before });
  const model = typeof summary.model === "string" ? summary.model : "";
  blocks.push({ text: `Results${model === "" ? "" : `: ${model}`}`, size: H1, bold: true });
  blocks.push({ text: headline(findings, summary), size: H2, bold: true, before: 10 });

  heading("Findings");
  if (findings.length === 0) line("None.");
  const options = scenariosOf(summary).length > 1;
  for (const finding of findings) {
    const option = options && finding.scenario !== null ? ` (option ${finding.scenario})` : "";
    line(`${ruleName(finding.rule)}${option}: ${finding.text}`, 4);
  }
  for (const issue of issues) line(`${issue.code} ${issue.message}`, 4);

  const kind = kindOf(summary);
  if (kind === "optimization") {
    const solution = solutionOf(summary);
    heading("Best plan");
    line(`Status: ${solution.status}`);
    line(`Goal: ${solution.objective === null ? UNDEFINED : figures(solution.objective, 4)}`);
    for (const [name, value] of solution.variables) line(`${name}: ${figures(value, 4)}`);
    heading("Limits");
    for (const limit of solution.limits) {
      const slack = limit.slack === null ? UNDEFINED : figures(limit.slack, 4);
      line(`${limit.name}: ${limit.tight ? "fully used" : "not fully used"}, slack ${slack}`);
    }
    return blocks;
  }

  const search = searchOf(summary);
  if (search !== null) {
    heading("All trials");
    for (const trial of search.trials) {
      const values = search.variables
        .map((name) => {
          const value = own<number>(trial.set, name);
          return `${name} ${value === undefined ? "-" : figures(value, 4)}`;
        })
        .join(", ");
      const objective = trial.objective;
      const average =
        objective === null
          ? UNDEFINED
          : `${valueText(search.metric, objective.mean, objective.unit)} ${rangeText(search.metric, objective.half_width, objective.unit, objective.mean)}`;
      line(
        `${trial.index}${trial.best ? " (best)" : ""}: ${values}; ${metricWords(search.metric)} ${average}; ` +
          `${trial.feasible ? "meets every limit" : "breaks a limit"}; ` +
          `${trial.confirmed ? "checked with all repeat runs" : "not checked"}`,
      );
    }
  }

  for (const scenario of scenariosOf(summary)) {
    heading(`Key numbers: ${scenario.id}`);
    for (const [name, estimate] of scenario.metrics) {
      line(
        `${metricWords(name)}: ${valueText(name, estimate.mean, estimate.unit)}, likely range ` +
          `${rangeText(name, estimate.half_width, estimate.unit, estimate.mean)}, ` +
          `${estimate.n} repeat runs`,
      );
    }
  }
  for (const difference of differencesOf(summary)) {
    heading(`${difference.scenario} against ${difference.against}`);
    for (const { name, estimate, separated } of difference.metrics) {
      line(
        `${metricWords(name)}: ${valueText(name, estimate.mean, estimate.unit)} ` +
          `${rangeText(name, estimate.half_width, estimate.unit, estimate.mean)}, ` +
          `${separated ? "told apart" : "cannot be told apart yet"}`,
      );
    }
  }
  return blocks;
}
