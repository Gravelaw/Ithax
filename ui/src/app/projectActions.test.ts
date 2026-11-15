/**
 * Every change to a project from Home goes through App's `ProjectActions` (review of pull
 * request 201, three findings of one class): no screen calls the client's project-changing
 * requests itself, so App's open project and lesson always follow them.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SCREENS = join(__dirname, "..", "screens");

describe("project changes made on Home", () => {
  it("go through App: no screen renames, notes or removes a project itself", () => {
    const callers = readdirSync(SCREENS)
      .filter((name) => /\.tsx?$/.test(name) && !/\.test\./.test(name))
      .filter((name) =>
        /\.(changeProject|removeProject)\(/.test(readFileSync(join(SCREENS, name), "utf-8")),
      );
    expect(callers).toEqual([]);
  });
});
