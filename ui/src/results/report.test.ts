/** The PDF report's content (AKS-138). */
import { describe, expect, it } from "vitest";
import {
  LINE_FINDINGS,
  lineSummary,
  optionsSummary,
  planSummary,
  SEARCH_FINDINGS,
  searchSummary,
} from "../test/runs";
import { metricPhrase } from "./display";
import { headline, NO_FINDING, reportBlocks, ruleName } from "./report";

const texts = (blocks: { text: string }[]) => blocks.map((block) => block.text);

describe("the report", () => {
  it("leads with the headline and the findings, then the key numbers", () => {
    const issue = {
      code: "W220",
      severity: "warning" as const,
      component: null,
      path: "/finding_thresholds/x",
      message: "The threshold 'x' is not one of the five.",
      hint: null,
    };
    const lines = texts(reportBlocks(lineSummary(), LINE_FINDINGS, [issue]));
    expect(lines[0]).toBe("Results: Three-machine line");
    expect(lines[1]).toBe(LINE_FINDINGS[0]?.text);
    expect(lines.indexOf("Findings")).toBeLessThan(lines.indexOf("Key numbers: default"));
    expect(lines).toContain(`Bottleneck: ${LINE_FINDINGS[0]?.text}`);
    expect(lines).toContain("W220 The threshold 'x' is not one of the five.");
    expect(lines).toContain(
      "weld: average wait: 15.7 min, likely range ± 2.09 min, 30 repeat runs",
    );
    expect(lines).toContain(
      "whole model: average items in the system: 12.4, likely range not defined, 30 repeat runs",
    );
  });

  it("says when no finding fired, and lists differences", () => {
    const lines = texts(reportBlocks({ ...optionsSummary(), model: 3 }, [], []));
    expect(lines[0]).toBe("Results");
    // Two options: the headline names the change (#94), the findings say none fired.
    expect(lines[1]).toBe("Option faster cuts the average wait at weld from 15.7 min to 10.7 min.");
    expect(lines).toContain("None.");
    expect(lines).toContain("faster against default");
    expect(lines).toContain("weld: average wait: -5 min ± 0.833 min, told apart");
    expect(lines).toContain("weld: busy share: 0% ± 1%, cannot be told apart yet");
  });

  it("lists every trial of a search", () => {
    const lines = texts(reportBlocks(searchSummary(), SEARCH_FINDINGS, []));
    expect(lines).toContain("All trials");
    expect(lines).toContain(
      "1 (best): tills 2; till: average wait 14.7 s ± 1.47 s; meets every limit; checked with all repeat runs",
    );
    expect(lines).toContain(
      "2: tills 3; till: average wait 1.5 s ± 0.15 s; breaks a limit; not checked",
    );
    const odd = searchSummary();
    const search = odd.search as { candidates: Record<string, unknown>[] };
    search.candidates.push({ set: {}, metrics: {}, feasible: false, confirmed: false });
    expect(texts(reportBlocks(odd, [], []))).toContain(
      "3: tills -; till: average wait not defined; breaks a limit; not checked",
    );
  });

  it("gives an optimization's plan and limits", () => {
    const lines = texts(reportBlocks(planSummary(), [], []));
    expect(lines).toEqual(
      expect.arrayContaining([
        "Best plan",
        "Status: optimal",
        "Goal: 2,200",
        "chairs: 24",
        "wood: fully used, slack 0",
      ]),
    );
    const bare = texts(reportBlocks({ constraints: { a: { tight: false, slack: null } } }, [], []));
    expect(bare).toEqual(
      expect.arrayContaining(["Goal: not defined", "a: not fully used, slack not defined"]),
    );
  });

  it("names the rules in plain words", () => {
    expect(ruleName("idle_capacity")).toBe("Idle capacity");
    expect(ruleName("unstable")).toBe("Cannot keep up");
    expect(ruleName("something_new")).toBe("something_new");
    expect(ruleName("constructor")).toBe("constructor");
    expect(headline([])).toBe(NO_FINDING);
  });
});

describe('the comparison headline (#94; canvas-interactions.md "Results say why")', () => {
  it("names the change between the options and the cause the findings point to", () => {
    expect(headline(LINE_FINDINGS, optionsSummary())).toBe(
      "Option faster cuts the average wait at weld from 15.7 min to 10.7 min, because weld " +
        "is the bottleneck: busy 90% of the time, with an average wait of 15.7 min.",
    );
  });

  it("names each finding's option in the report when the run compares options", () => {
    const lines = texts(reportBlocks(optionsSummary(), LINE_FINDINGS, []));
    expect(lines).toContain(`Bottleneck (option default): ${LINE_FINDINGS[0]?.text}`);
  });

  it("gives the change only when no finding names a cause in the first option", () => {
    expect(headline([], optionsSummary())).toBe(
      "Option faster cuts the average wait at weld from 15.7 min to 10.7 min.",
    );
  });

  it("says when the options cannot be told apart yet", () => {
    const summary = optionsSummary();
    const [difference] = summary.differences as {
      metrics: Record<string, { separated: boolean }>;
    }[];
    for (const value of Object.values(difference?.metrics ?? {})) value.separated = false;
    expect(headline(LINE_FINDINGS, summary)).toBe(
      "Option faster and option default cannot be told apart yet on any measure; more " +
        "repeat runs would tell.",
    );
  });

  it("keeps the first finding for a run of one option", () => {
    expect(headline(LINE_FINDINGS, lineSummary())).toBe(LINE_FINDINGS[0]?.text);
  });

  it("reads the option's own mean, not the baseline plus the paired difference (review of pull request 199)", () => {
    // Baseline repeats [100, 100, 1000] s, the option's [50, 50, NaN]: the option's mean is
    // 50 s; the paired difference over the two defined pairs is -50 s, so 400 + -50 = 350
    // would be wrong.
    const summary = optionsSummary();
    const scenarios = summary.scenarios as Record<string, { metrics: Record<string, unknown> }>;
    const at = (mean: number, n: number) => ({ mean, half_width: 5, unit: "s", n });
    scenarios.default = { ...scenarios.default, metrics: { "weld.wait.mean": at(400, 3) } };
    scenarios.faster = { ...scenarios.faster, metrics: { "weld.wait.mean": at(50, 2) } };
    summary.differences = [
      {
        scenario: "faster",
        against: "default",
        metrics: {
          "weld.wait.mean": { mean: -50, half_width: 1, unit: "s", n: 2, separated: true },
        },
      },
    ];
    const expected = "Option faster cuts the average wait at weld from 6.67 min to 0.833 min.";
    expect(headline([], summary)).toBe(expected);
    expect(texts(reportBlocks(summary, [], []))[1]).toBe(expected);
  });

  it("puts a metric in a sentence", () => {
    expect(metricPhrase("weld.wait.mean")).toBe("the average wait at weld");
    expect(metricPhrase("model.wip.mean")).toBe("the average items in the system");
    expect(metricPhrase("plain")).toBe("plain");
  });
});
