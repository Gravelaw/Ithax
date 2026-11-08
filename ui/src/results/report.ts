/**
 * The Results screen's content as the PDF export holds it (spec 3 "Run monitor, Results
 * and Settings": the headline, the findings, the key numbers and the run kind's tables,
 * with the footer on every page). Charts are left out: the PDF is text, and each chart's
 * numbers are in a table here or on the screen.
 */
import type { Finding, Issue, Summary } from "../api/types";
import { own } from "../canvas/own";
import { figures, rangeText, UNDEFINED, valueText } from "./display";
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

export function headline(findings: readonly Finding[]): string {
  return findings[0]?.text ?? NO_FINDING;
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
  blocks.push({ text: headline(findings), size: H2, bold: true, before: 10 });

  heading("Findings");
  if (findings.length === 0) line("None.");
  for (const finding of findings) {
    line(`${ruleName(finding.rule)}: ${finding.text}`, 4);
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
        `${trial.index}${trial.best ? " (best)" : ""}: ${values}; ${search.metric} ${average}; ` +
          `${trial.feasible ? "meets every limit" : "breaks a limit"}; ` +
          `${trial.confirmed ? "checked with all repeat runs" : "not checked"}`,
      );
    }
  }

  for (const scenario of scenariosOf(summary)) {
    heading(`Key numbers: ${scenario.id}`);
    for (const [name, estimate] of scenario.metrics) {
      line(
        `${name}: ${valueText(name, estimate.mean, estimate.unit)}, likely range ` +
          `${rangeText(name, estimate.half_width, estimate.unit, estimate.mean)}, ` +
          `${estimate.n} repeat runs`,
      );
    }
  }
  for (const difference of differencesOf(summary)) {
    heading(`${difference.scenario} against ${difference.against}`);
    for (const { name, estimate, separated } of difference.metrics) {
      line(
        `${name}: ${valueText(name, estimate.mean, estimate.unit)} ` +
          `${rangeText(name, estimate.half_width, estimate.unit, estimate.mean)}, ` +
          `${separated ? "told apart" : "cannot be told apart yet"}`,
      );
    }
  }
  return blocks;
}
