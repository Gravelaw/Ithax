import { describe, expect, it } from "vitest";
import { oneAtATime } from "./oneAtATime";

describe("requests one at a time", () => {
  it("starts each after the one before has settled, a failure included", async () => {
    const queue = oneAtATime();
    const log: string[] = [];
    let finishFirst: () => void = () => {};
    const first = queue(
      () =>
        new Promise<string>((resolve) => {
          log.push("first sent");
          finishFirst = () => resolve("first");
        }),
    );
    const failed = queue(async () => {
      log.push("second sent");
      throw new Error("refused");
    });
    const third = queue(async () => {
      log.push("third sent");
      return "third";
    });
    await Promise.resolve();
    expect(log).toEqual(["first sent"]);
    finishFirst();
    expect(await first).toBe("first");
    await expect(failed).rejects.toThrow("refused");
    expect(await third).toBe("third");
    expect(log).toEqual(["first sent", "second sent", "third sent"]);
  });
});
