/**
 * A typed number in a unit, in the base unit the service keeps (review of pull request 196, two
 * findings at one site): the value sent never means something else than what was typed. A
 * non-zero entry never becomes 0 (the idle timeout's "never") or `null` (the default), and
 * a result that is not a finite number is sent as typed, so the service refuses it (E184).
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { inSize, typedInBase } from "./display";

const SIZES = [1, 60, 3600, 86400, 1440, 1e6, 1e9];

describe("typedInBase", () => {
  it.each(SIZES)("keeps each entry's meaning in a unit of size %d", (size) => {
    expect(typedInBase("", size)).toBeNull();
    expect(typedInBase("  ", size)).toBeNull();
    expect(typedInBase("0", size)).toBe(0);
    expect(typedInBase("2", size)).toBe(2 * size);
    // Huge: past a finite number in the base unit, so sent as typed for the service to
    // refuse; in the base unit itself it is a number, which the service refuses by range.
    expect(typedInBase("1e308", size)).toEqual(size === 1 ? 1e308 : "1e308");
    // Tiny: never 0 and never null.
    const tiny = typedInBase("0.0000000001", size);
    expect(tiny).not.toBe(0);
    expect(tiny).not.toBeNull();
    expect(typeof tiny).toBe("number");
    // Negative: kept, for the service to refuse.
    expect(typedInBase("-3", size)).toBe(-3 * size);
    // Not a number: as typed.
    expect(typedInBase("NaN", size)).toBe("NaN");
    expect(typedInBase("lots", size)).toBe("lots");
  });

  it("snaps a float's noise to the whole number, and keeps a true fraction", () => {
    expect(typedInBase("0.1", 60)).toBe(6);
    expect(typedInBase("8.59", 1e9)).toBe(8_590_000_000);
    expect(typedInBase("0.01", 60)).toBe(0.6);
  });

  it("gives a value in a unit, or null when it is not a finite number", () => {
    expect(inSize(120, 60)).toBe(2);
    expect(inSize(1e308, 1e-9)).toBeNull();
  });
});

/** UI code that scales by a unit's size: the helpers above are the only place. */
function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) ? [path] : [];
  });
}

describe("unit scaling", () => {
  it("is done only in display.ts: no other code multiplies or divides by a unit size", () => {
    const scaling = /[*/]\s*(?:unit\.size|size\b|60\b|3600\b|86400\b|1e[369]\b)/;
    const found = sources(join(__dirname, ".."))
      .filter((path) => !path.endsWith(join("results", "display.ts")))
      // Font metrics, not units; and the test fixtures.
      .filter((path) => !path.endsWith(join("results", "pdf.ts")))
      .filter((path) => !path.includes(`${join("src", "test")}/`))
      .flatMap((path) =>
        readFileSync(path, "utf-8")
          .split("\n")
          .filter((line) => scaling.test(line) && !line.trim().startsWith("*"))
          .map((line) => `${path}: ${line.trim()}`),
      );
    expect(found).toEqual([]);
  });
});
