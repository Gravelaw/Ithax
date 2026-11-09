import { afterEach, describe, expect, it } from "vitest";
import { cycleRegion } from "./regions";

afterEach(() => {
  document.body.innerHTML = "";
});

function layout() {
  document.body.innerHTML = `
    <nav data-region="rail"><button id="home">Home</button><button id="current" data-region-entry>Canvas</button></nav>
    <header data-region="top" tabindex="-1" id="top"><button id="in-top">x</button></header>
    <main data-region="main" tabindex="-1" id="main"></main>`;
}

describe("F6 regions", () => {
  it("moves forwards through the regions, entering the rail at its current screen", () => {
    layout();
    cycleRegion(document, false);
    expect(document.activeElement?.id).toBe("current");
    cycleRegion(document, false);
    expect(document.activeElement?.id).toBe("top");
    document.getElementById("in-top")?.focus();
    cycleRegion(document, false);
    expect(document.activeElement?.id).toBe("main");
    cycleRegion(document, false);
    expect(document.activeElement?.id).toBe("current");
  });

  it("moves backwards with Shift+F6", () => {
    layout();
    cycleRegion(document, true);
    expect(document.activeElement?.id).toBe("main");
    cycleRegion(document, true);
    expect(document.activeElement?.id).toBe("top");
  });

  it("skips regions behind a dialog and does nothing without regions", () => {
    layout();
    document.getElementById("top")?.setAttribute("inert", "");
    document.getElementById("main")?.setAttribute("inert", "");
    cycleRegion(document, false);
    cycleRegion(document, false);
    expect(document.activeElement?.id).toBe("current");
    document.body.innerHTML = "";
    expect(() => cycleRegion(document, false)).not.toThrow();
  });
});
