/**
 * The step card's buttons stay in view (#90, Reviewer B finding 1): at the designed size,
 * 1,280 × 800 (design-system.md "Layout"), every step of every template's lesson shows Back,
 * Next or "Run the exercise", and "Exit lesson" whole, without scrolling the card, as
 * `wireframes/01b-canvas-learn.svg` draws them. Before #90 they followed the step's text and
 * the exercise's choices inside a card capped at 60% of the column, so a long step pushed
 * them below its fold.
 */
import type { Locator, Page } from "@playwright/test";
import { expect, test } from "./fixtures";

interface Listed {
  id: string;
  title: string;
}

/** The step's controls, each wholly inside the window and not clipped by the card. */
async function inView(page: Page, controls: Locator[]): Promise<void> {
  for (const control of controls) await expect(control).toBeInViewport({ ratio: 1 });
  // Seen through the card: the card's own scroll would clip a control it holds.
  const card = await page.locator(".step-card").boundingBox();
  if (card === null) throw new Error("no step card");
  for (const control of controls) {
    const box = await control.boundingBox();
    if (box === null) throw new Error("a control has no box");
    expect(box.y).toBeGreaterThanOrEqual(card.y);
    expect(box.y + box.height).toBeLessThanOrEqual(card.y + card.height + 0.5);
  }
}

test.setTimeout(300_000);

test("every lesson step shows its buttons whole at 1,280 × 800", async ({ page, service }) => {
  const templates = (await service.api("GET", "/v1/templates")).body as Listed[];
  expect(templates.length).toBeGreaterThan(0);
  await page.goto(service.url);
  await page
    .getByRole("dialog", { name: "Welcome" })
    .getByRole("button", { name: "Continue" })
    .click();
  for (const template of templates) {
    await page.getByRole("button", { name: "Home", exact: true }).click();
    await page.getByRole("button", { name: `Start the lesson ${template.title}` }).click();
    const card = page.locator(".step-card");
    await expect(card).toBeVisible();
    for (;;) {
      const back = card.getByRole("button", { name: "Back" });
      const next = card.getByRole("button", { name: "Next" });
      const run = card.getByRole("button", { name: "Run the exercise" });
      const exit = card.getByRole("button", { name: "Exit lesson" });
      await expect(back).toBeVisible();
      const last = (await run.count()) > 0;
      await inView(page, [back, last ? run : next, exit]);
      if (last) break;
      const label = await card.locator(".step-label").textContent();
      await next.click();
      await expect(card.locator(".step-label")).not.toHaveText(label ?? "");
    }
  }
});
