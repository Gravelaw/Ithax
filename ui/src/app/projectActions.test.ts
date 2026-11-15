/**
 * Every read and write of project state goes through App's one queue of actions (reviews of
 * pull request 201, seven findings of one class): only `projectApi` calls the client's
 * project requests, and an action receives it from `run`, so no screen or App code can read
 * or change a project outside the queue.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const FOLDERS = ["app", "screens"].map((name) => join(__dirname, "..", name));
const PROJECT_REQUESTS =
  /\.(listProjects|getTemplate|createProject|openProject|changeProject|removeProject)\(/;

describe("project reads and writes", () => {
  it("are made only by projectApi, inside an action of App's queue", () => {
    const callers = FOLDERS.flatMap((folder) =>
      readdirSync(folder)
        .filter((name) => /\.tsx?$/.test(name) && !/\.test\./.test(name))
        .filter((name) => name !== "projectActions.ts")
        .filter((name) => PROJECT_REQUESTS.test(readFileSync(join(folder, name), "utf-8")))
        .map((name) => name),
    );
    expect(callers).toEqual([]);
  });
});
