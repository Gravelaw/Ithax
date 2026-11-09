/**
 * Learn mode end to end (spec 4 "Learn and Build modes"; AKS-124), against a real service
 * and the built interface: one lesson walked by pointer through its exercise, and one from
 * the keyboard alone, each meeting WCAG 2.2 AA, with nothing fetched from outside.
 *
 * - The coffee shop, by pointer: Home's Learn and the gallery's "Start the lesson" make the
 *   project from the template; each step's card names its block, which is ringed and
 *   selected; the exercise shows its change, "Make the change" sends the template's edits,
 *   a prediction is chosen, and its Run runs the template's experiment; Results of that
 *   run show the prediction, that it is right, and the explanation above the headline. The
 *   service's own request log holds only documented routes, none refused.
 * - The product mix, from the keyboard: the plan's rows are ringed step by step in the
 *   Table view, F6 reaches the step card, and the exercise runs as one solve.
 */
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import type { Locator, Page } from "@playwright/test";
import { test as base, expect } from "./fixtures";
import { python, REPOSITORY_ROOT, type Service, startService } from "./service";

const logged = base.extend<{ service: Service }>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright's fixture signature
  service: async ({}, use) => {
    const service = await startService({ requestLog: true });
    try {
      await use(service);
    } finally {
      await service.stop();
    }
  },
});

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function accessible(page: Page): Promise<void> {
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
}

async function settled(page: Page): Promise<void> {
  await expect(page.locator(".save-state")).toHaveText("Saved");
  await expect(page.locator(".problems [role=status]")).not.toContainText("Checking");
}

function card(page: Page): Locator {
  return page.locator(".step-card");
}

function block(page: Page, id: string): Locator {
  return page.locator(`.react-flow__node[data-id="${id}"] .block`);
}

logged.setTimeout(240_000);

logged(
  "a first lesson is walked through its exercise by pointer, through documented routes only",
  async ({ page, service, sent, outside }) => {
    await page.goto(service.url);
    await page
      .getByRole("dialog", { name: "Welcome" })
      .getByRole("button", { name: "Continue" })
      .click();
    await page.getByRole("button", { name: /^Learn/ }).click();
    await expect(page.getByRole("heading", { name: "Templates" })).toBeFocused();
    // Students first: the coffee shop and the product mix lead the gallery.
    await expect(page.locator(".gallery .card .subheading").first()).toHaveText(
      "Coffee shop queue",
    );
    await page.getByRole("button", { name: "Start the lesson Coffee shop queue" }).click();

    // Step 1: the arrivals.
    await expect(card(page).getByRole("heading", { name: "Customers arrive" })).toBeVisible();
    await expect(card(page)).toContainText("Coffee shop queue · Step 1 of 4");
    await settled(page);
    const pid = decodeURIComponent(new URL(page.url()).hash.split("/").pop() ?? "");
    await expect(page.getByRole("banner")).toContainText("Coffee shop queue");
    await expect(block(page, "arrivals")).toHaveClass(/block-learn/);
    await expect(block(page, "arrivals")).toContainText("Step 1 of 4");
    await expect(page.getByRole("textbox", { name: "Id" })).toHaveValue("arrivals");
    await accessible(page);

    // Steps 2 and 3, each ringing its block.
    for (const [heading, id] of [
      ["One till serves them", "till"],
      ["Customers leave", "exit"],
    ] as const) {
      await card(page).getByRole("button", { name: "Next" }).click();
      await expect(card(page).getByRole("heading", { name: heading })).toBeVisible();
      await expect(block(page, id)).toHaveClass(/block-learn/);
      await expect(page.getByRole("textbox", { name: "Id" })).toHaveValue(id);
    }
    // One block is ringed at a time.
    await expect(page.locator(".block-learn")).toHaveCount(1);

    // The exercise: the change, the prediction, the run.
    await card(page).getByRole("button", { name: "Next" }).click();
    await expect(
      card(page).getByRole("heading", { name: "Exercise: open a second till" }),
    ).toBeVisible();
    await expect(card(page)).toContainText("Step 4 of 4 · Try it");
    await expect(card(page).getByRole("list", { name: "The change" })).toHaveText("tills: 1 → 2");
    const runExercise = card(page).getByRole("button", { name: "Run the exercise" });
    await expect(runExercise).toHaveAttribute("aria-disabled", "true");
    await accessible(page);
    await card(page).getByRole("button", { name: "Make the change" }).click();
    await settled(page);
    await expect(card(page).getByText("The change is made.")).toBeVisible();
    await card(page)
      .getByRole("radio", { name: /far less than half/ })
      .check();
    await expect(runExercise).not.toHaveAttribute("aria-disabled", "true");
    const model = (await service.api("GET", `/v1/projects/${pid}/model`)).body as {
      model: { parameters: { tills: { value: number } }; meta: { template: string } };
    };
    expect(model.model.parameters.tills.value).toBe(2);
    expect(model.model.meta.template).toBe("coffee_shop");
    await runExercise.click();

    await expect(page.getByRole("heading", { name: "Run monitor" })).toBeVisible();
    const rid = decodeURIComponent(new URL(page.url()).hash.split("/").pop() ?? "");
    await expect(page.locator(".state-badge")).toHaveText("Done", { timeout: 120_000 });
    const runBody = (await service.api("GET", `/v1/runs/${rid}`)).body as {
      experiment_id: string;
    };
    expect(runBody.experiment_id).toBe("base");
    await page.getByRole("button", { name: "See the results" }).click();

    // Results: the answer first, then the headline.
    const answer = page.getByRole("region", { name: "Exercise: open a second till" });
    await expect(answer).toContainText(
      "You predicted: The wait falls to about a quarter of a minute, far less than half.",
    );
    await expect(answer).toContainText("That is right.");
    await expect(answer).toContainText("Two tills are each busy 37.5% of the time");
    await expect(page.locator(".headline-card")).toBeVisible();
    await accessible(page);
    await answer.getByRole("button", { name: "Back to the canvas" }).click();
    await expect(card(page).getByRole("heading", { name: /Exercise/ })).toBeVisible();
    await card(page).getByRole("button", { name: "Exit lesson" }).click();
    await expect(card(page)).toHaveCount(0);

    await page.close();
    const checked = spawnSync(
      python(),
      [join(REPOSITORY_ROOT, "tests", "service", "request_log.py"), service.requestLog ?? ""],
      { encoding: "utf8" },
    );
    const found = JSON.parse(checked.stdout) as {
      routes: Record<string, number>;
      problems: string[];
    };
    console.log(`request log: ${JSON.stringify(found)}`);
    expect(found.problems).toEqual([]);
    expect(checked.status).toBe(0);
    for (const route of [
      "GET /v1/templates",
      "GET /v1/templates/{tid}",
      "POST /v1/projects",
      "POST /v1/projects/{pid}/model/edits",
      "POST /v1/projects/{pid}/runs",
      "GET /v1/runs/{rid}/summary",
    ]) {
      expect(Object.keys(found.routes)).toContain(route);
    }
    expect(sent.every((request) => request.headers["x-client"] === "ui")).toBe(true);
    expect(outside).toEqual([]);
  },
);

base("the product mix lesson works from the keyboard alone", async ({ page, service }) => {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  await page.goto(service.url);
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
  await page.getByRole("button", { name: /^Learn/ }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Templates" })).toBeFocused();
  // Tab from the gallery's heading to the product mix's button.
  const start = page.getByRole("button", { name: "Start the lesson Product mix" });
  for (let press = 0; press < 12; press += 1) {
    if (await start.evaluate((button) => button === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expect(start).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(card(page)).toContainText("Product mix · Step 1 of 5");
  await settled(page);
  const row = (name: string) => page.getByRole("textbox", { name }).locator("xpath=ancestor::tr");
  await expect(row("Name of decision 1")).toHaveClass(/learn-target/);
  await accessible(page);

  // F6 reaches the step card; Tab moves inside it; Enter presses.
  for (let press = 0; press < 8; press += 1) {
    if (await card(page).evaluate((element) => element === document.activeElement)) break;
    await page.keyboard.press("F6");
  }
  await expect(card(page)).toBeFocused();
  const next = card(page).getByRole("button", { name: "Next" });
  for (let press = 0; press < 6; press += 1) {
    if (await next.evaluate((button) => button === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expect(next).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator(".plan-section.learn-target")).toHaveCount(1);
  await expect(next).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(row("Name of limit 1")).toHaveClass(/learn-target/);
  await page.keyboard.press("Enter");
  await expect(row("Name of limit 2")).toHaveClass(/learn-target/);
  await page.keyboard.press("Enter");
  await expect(card(page)).toContainText("Step 5 of 5 · Try it");
  await expect(row("Name of decision 2")).toHaveClass(/learn-target/);
  await expect(card(page).getByRole("list", { name: "The change" })).toHaveText(
    "/objective/linear/tables: 80 → 100",
  );

  // The exercise: Make the change, a choice, Run, all by keys.
  const make = card(page).getByRole("button", { name: "Make the change" });
  await make.focus();
  await page.keyboard.press("Enter");
  await settled(page);
  await expect(card(page).getByText("The change is made.")).toBeVisible();
  const choice = card(page).getByRole("radio").first();
  await choice.focus();
  await page.keyboard.press("Space");
  await expect(choice).toBeChecked();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  const runExercise = card(page).getByRole("button", { name: "Run the exercise" });
  await expect(runExercise).toBeFocused();
  await expect(runExercise).not.toHaveAttribute("aria-disabled", "true");
  await accessible(page);
  await page.keyboard.press("Enter");
  await expect(page.locator(".state-badge")).toHaveText("Done", { timeout: 60_000 });
  const results = page.getByRole("button", { name: "See the results" });
  await results.focus();
  await page.keyboard.press("Enter");
  const answer = page.getByRole("region", { name: /^Exercise/ });
  await expect(answer).toContainText("You predicted:");
  await expect(page.locator(".headline-card")).toBeVisible();
  await accessible(page);
});
