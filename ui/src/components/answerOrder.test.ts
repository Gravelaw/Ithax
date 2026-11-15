import { describe, expect, it } from "vitest";
import { AnswerOrder } from "./answerOrder";

describe("which overlapping answers are taken", () => {
  it("takes a write's answer unless a later write's was taken first", () => {
    const order = new AnswerOrder();
    const first = order.write();
    const second = order.write();
    expect(second(true)).toBe(true);
    expect(first(true)).toBe(false);
    const third = order.write();
    expect(third(false)).toBe(false);
    expect(order.write()(true)).toBe(true);
  });

  it("takes a read's answer only when no write was open or sent since", () => {
    const order = new AnswerOrder();
    expect(order.read()(true)).toBe(true);
    expect(order.read()(false)).toBe(false);
    const before = order.read();
    const write = order.write();
    const during = order.read();
    expect(write(true)).toBe(true);
    expect(before(true)).toBe(false);
    expect(during(true)).toBe(false);
    expect(order.read()(true)).toBe(true);
  });
});
