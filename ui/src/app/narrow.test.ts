import { describe, expect, it } from "vitest";
import { isNarrow, NARROW_REM } from "./narrow";

describe("isNarrow (#93)", () => {
  it("is narrow below 1,024 px at 100% text, and at 1,280 px with 200% text", () => {
    expect(NARROW_REM).toBe(64);
    expect(isNarrow(1023, 16)).toBe(true);
    expect(isNarrow(1024, 16)).toBe(false);
    expect(isNarrow(1280, 16)).toBe(false);
    expect(isNarrow(1280, 32)).toBe(true);
    expect(isNarrow(2048, 32)).toBe(false);
  });

  it("is never narrow with no root size", () => {
    expect(isNarrow(100, 0)).toBe(false);
  });
});
