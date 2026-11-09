/**
 * Generated identifiers always meet spec 1's rule (`^[a-z][a-z0-9_]{0,63}$`) and are free.
 */
import { describe, expect, it } from "vitest";
import { identifier, MAX_IDENTIFIER } from "./identifiers";

const RULE = /^[a-z][a-z0-9_]{0,63}$/;

describe("identifier", () => {
  it("makes words an identifier", () => {
    expect(identifier("Faster coffee machine", [], "option")).toBe("faster_coffee_machine");
    expect(identifier("  2 more tills! ", [], "option")).toBe("option_2_more_tills");
    expect(identifier("???", [], "option")).toBe("option");
    expect(identifier("till_service_mean", [], "parameter")).toBe("till_service_mean");
    expect(identifier("a__b", [], "x")).toBe("a_b");
  });

  it("takes the first free suffix, never a reserved or taken id", () => {
    expect(identifier("baseline", ["baseline", "baseline_2"], "baseline")).toBe("baseline_3");
    expect(identifier("default", ["default"], "option")).toBe("default_2");
  });

  it("bounds a 60-character id with a field path to 64 characters, with room for the suffix", () => {
    const long = `s${"x".repeat(59)}`;
    const text = `${long}_service_mean`;
    const first = identifier(text, [], "parameter");
    expect(first).toHaveLength(MAX_IDENTIFIER);
    expect(first).toMatch(RULE);
    const second = identifier(text, [first], "parameter");
    expect(second).toMatch(RULE);
    expect(second.endsWith("_2")).toBe(true);
    expect(second.length).toBeLessThanOrEqual(MAX_IDENTIFIER);
    const taken = [first, second];
    for (let n = 3; n <= 120; n += 1) taken.push(identifier(text, taken, "parameter"));
    for (const id of taken) expect(id).toMatch(RULE);
    expect(new Set(taken).size).toBe(taken.length);
    expect(taken.at(-1)?.endsWith("_120")).toBe(true);
  });

  it("never ends the cut base in `_` before the suffix", () => {
    const text = `${"a".repeat(61)}_b`;
    expect(identifier(text, [], "x")).toBe(text.slice(0, 64));
    expect(identifier(text, [text.slice(0, 64)], "x")).toBe(`${"a".repeat(61)}_2`);
  });
});
