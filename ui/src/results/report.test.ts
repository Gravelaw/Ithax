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
    expect(lines).toContain("weld.wait.mean: 15.7 min, likely range ± 2.09 min, 30 repeat runs");
    expect(lines).toContain("model.wip.mean: 12.4, likely range not defined, 30 repeat runs");
  });

  it("says when no finding fired, and lists differences", () => {
    const lines = texts(reportBlocks({ ...optionsSummary(), model: 3 }, [], []));
    expect(lines[0]).toBe("Results");
    expect(lines[1]).toBe(NO_FINDING);
    expect(lines).toContain("None.");
    expect(lines).toContain("faster against default");
    expect(lines).toContain("weld.wait.mean: -5 min ± 0.833 min, told apart");
    expect(lines).toContain("weld.utilization: 0% ± 1%, cannot be told apart yet");
  });

  it("lists every trial of a search", () => {
    const lines = texts(reportBlocks(searchSummary(), SEARCH_FINDINGS, []));
    expect(lines).toContain("All trials");
    expect(lines).toContain(
      "1 (best): tills 2; till.wait.mean 14.7 s ± 1.47 s; meets every limit; checked with all repeat runs",
    );
    expect(lines).toContain(
      "2: tills 3; till.wait.mean 1.5 s ± 0.15 s; breaks a limit; not checked",
    );
    const odd = searchSummary();
    const search = odd.search as { candidates: Record<string, unknown>[] };
    search.candidates.push({ set: {}, metrics: {}, feasible: false, confirmed: false });
    expect(texts(reportBlocks(odd, [], []))).toContain(
      "3: tills -; till.wait.mean not defined; breaks a limit; not checked",
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
