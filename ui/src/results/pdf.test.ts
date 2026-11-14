/**
 * The PDF writer, read back by an independent reader (Mozilla's pdf.js, a development
 * dependency): every page holds every footer item, the text wraps inside the page, and
 * characters outside WinAnsi are written as "?".
 */
import { describe, expect, it } from "vitest";
import { readPdf } from "../test/readPdf";
import { type Block, makePdf, PAGE_WIDTH, textWidth, winAnsi, wrap } from "./pdf";

const FOOTER = [
  "Model: Coffee shop",
  "Run: 20261108T101502-K3QX7A",
  "Fidelity: Standard: 30 replications of 200 h, 95% confidence",
  "Replications: 30 · Confidence: 95%",
  "Engine: simpy 4.1.2",
  "Simulation results are estimates and carry no warranty.",
];

describe("the PDF writer", () => {
  it("puts every footer item on every page of a long report", async () => {
    const blocks: Block[] = Array.from({ length: 150 }, (_, index) => ({
      text: `Line ${index}: till.wait.mean is 4.46 min, likely range ± 0.163 min (a long line that has to wrap because it does not fit on one line of an A4 page at eleven points)`,
      size: 11,
    }));
    const pages = await readPdf(makePdf(blocks, FOOTER, "Results"));
    expect(pages.length).toBeGreaterThan(2);
    pages.forEach((page, index) => {
      for (const item of FOOTER) expect(page.text).toContain(item);
      expect(page.text).toContain(`Page ${index + 1} of ${pages.length}`);
      for (const item of page.items)
        expect(item.x + item.width).toBeLessThanOrEqual(PAGE_WIDTH - 50);
    });
    expect(pages.map((page) => page.text).join(" ")).toContain("Line 149:");
  });

  it("writes WinAnsi characters and escapes, and '?' for the others", async () => {
    const [page] = await readPdf(
      makePdf([{ text: "A (b) \\ c ± 2 – é € − 漢", size: 11, bold: true }], ["F"], "T (1)"),
    );
    expect(page?.text).toContain("A (b) \\ c ± 2 – é € - ?");
    expect(winAnsi("漢")).toBe(63);
    expect(winAnsi("€")).toBe(0x80);
  });

  it("wraps at spaces, cuts a word too long for a line, and keeps empty lines", () => {
    expect(wrap("a b", 11, 1000)).toEqual(["a b"]);
    const long = "x".repeat(200);
    const cut = wrap(long, 11, 100);
    expect(cut.join("")).toBe(long);
    for (const line of cut) expect(textWidth(line, 11)).toBeLessThanOrEqual(100);
    expect(wrap("one\n\ntwo", 11, 100)).toEqual(["one", "", "two"]);
    expect(textWidth("a", 10, true)).toBeGreaterThan(textWidth("a", 10));
  });
});
