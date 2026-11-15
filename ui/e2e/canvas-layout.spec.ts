/**
 * The Canvas at 200% text and below 1,024 px (#93, Reviewer B finding 4; WCAG 1.4.4 and
 * 1.4.10, `docs/design/accessibility.md`; design-system.md "Spacing and layout": "Below
 * 1024 px wide the side panel becomes an overlay that opens on selection").
 *
 * In each case the top bar shows every tool whole, Run with it, and the side panel is not a
 * column taking the canvas's room: it opens over the canvas when a block is selected and
 * closes with its Close button. At the designed size the panel stays a column.
 */
import type { Locator, Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import type { Service } from "./service";

async function open(page: Page, service: Service, textSize: number): Promise<void> {
  await service.api("PUT", "/v1/settings", {
    interface: { first_start_seen: true, text_size: textSize },
  });
  const made = (await service.api("POST", "/v1/projects", {
    name: "Coffee shop queue",
    template: "coffee_shop",
  })) as { body: { id: string } };
  await page.goto(service.url);
  await expect(page.locator("#home-heading")).toBeVisible();
  await page.evaluate((pid) => {
    window.location.hash = `#/canvas/${encodeURIComponent(pid)}`;
  }, made.body.id);
  await expect(page.locator(".save-state")).toHaveText("Saved");
}

/** Each control wholly inside the window and inside the top bar. */
async function whole(page: Page, controls: Locator[]): Promise<void> {
  const bar = await page.locator(".topbar").boundingBox();
  if (bar === null) throw new Error("no top bar");
  for (const control of controls) {
    await expect(control).toBeInViewport({ ratio: 1 });
    const box = await control.boundingBox();
    if (box === null) throw new Error("a control has no box");
    expect(box.y).toBeGreaterThanOrEqual(bar.y - 0.5);
    expect(box.y + box.height).toBeLessThanOrEqual(bar.y + bar.height + 0.5);
  }
}

function tools(page: Page): Locator[] {
  const bar = page.locator(".topbar");
  return [
    bar.getByRole("button", { name: "Undo" }),
    bar.getByRole("button", { name: "Redo" }),
    bar.getByRole("combobox", { name: "Experiment" }),
    bar.getByRole("button", { name: "Run" }),
  ];
}

for (const [name, width, height, textSize] of [
  ["200% text at 1,280 × 800", 1280, 800, 200],
  ["100% text at 900 × 700", 900, 700, 100],
] as const) {
  test(`the canvas reflows: ${name}`, async ({ page, service }) => {
    await page.setViewportSize({ width, height });
    await open(page, service, textSize);
    await whole(page, tools(page));

    // No block selected: no panel over the canvas, and the canvas has the room.
    const sheet = page.locator(".side-sheet");
    await expect(sheet).toBeHidden();
    const canvas = await page.locator(".canvas-flow").boundingBox();
    expect(canvas?.width ?? 0).toBeGreaterThan(width * 0.4);

    // Selecting a block opens the panel over the canvas; Close closes it.
    await page.locator('.react-flow__node[data-id="till"]').click();
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("textbox", { name: "Id" })).toHaveValue("till");
    await expect(sheet).toBeInViewport({ ratio: 1 });
    const after = await page.locator(".canvas-flow").boundingBox();
    expect(after?.width).toBe(canvas?.width);
    await sheet.getByRole("button", { name: "Close the panel" }).click();
    await expect(sheet).toBeHidden();

    // The parameters, with nothing selected, open from the top bar.
    await page.locator(".topbar").getByRole("button", { name: "Show the panel" }).click();
    await expect(sheet).toBeVisible();
  });
}

test("at the designed size the side panel stays a column", async ({ page, service }) => {
  await open(page, service, 100);
  await whole(page, tools(page));
  await expect(page.locator(".side-sheet")).toHaveCount(0);
  await expect(page.locator(".side-panel")).toBeVisible();
});
