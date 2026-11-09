import { describe, expect, it } from "vitest";
import { applyPreferences, DEFAULT_PREFERENCES } from "./preferences";

describe("applyPreferences", () => {
  it("sets the theme, motion, chart palette and text size on the root", () => {
    const root = document.createElement("html");
    applyPreferences(root, {
      ...DEFAULT_PREFERENCES,
      theme: "dark",
      motion: "off",
      text_size: 150,
      colour_blind_charts: true,
    });
    expect(root.dataset.theme).toBe("dark");
    expect(root.dataset.motion).toBe("off");
    expect(root.dataset.charts).toBe("colour-blind");
    expect(root.style.fontSize).toBe("150%");
    applyPreferences(root, DEFAULT_PREFERENCES);
    expect(root.dataset.theme).toBe("system");
    expect(root.dataset.charts).toBe("standard");
    expect(root.style.fontSize).toBe("100%");
  });
});
