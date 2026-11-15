/**
 * The class of review findings 1 and 3 of pull request 192: an action that moves the focus
 * into the side panel while it is a closed overlay finds the target hidden and inert. Every
 * such move goes through `useSheet`'s `reveal`, which opens the overlay first; the Canvas
 * looks up no element by id itself.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("moving the focus into the side panel", () => {
  it("goes through reveal: the Canvas calls no getElementById of its own", () => {
    const source = readFileSync(join(__dirname, "CanvasScreen.tsx"), "utf-8");
    expect(source.match(/getElementById\(/g) ?? []).toEqual([]);
  });
});
