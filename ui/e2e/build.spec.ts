/**
 * Spec 4's M9/M10 acceptance row "A Build-mode user without data reaches a completed run
 * changing only parameters" (AKS-124), against a real service and the built interface.
 *
 * From the first start: Home's Build opens the form; the first answer, "How long will
 * people or items wait?", and "No, I will estimate" make the coffee shop from its template
 * and open the Canvas with its parameters; the parameter `tills` goes from 1 to 2, the only
 * change; Run, the Run monitor to Done, and Results. Then:
 *
 * - the saved model equals the template's `model.json` except `meta` (the project's name
 *   and template of origin) and `parameters.tills.value`, and no data file was imported;
 * - the service's own request log (`tests/service/logged_service.py`) holds only routes of
 *   spec 3's endpoint table, none refused (`tests/service/request_log.py`), as for the
 *   pointer-only test; the page sent nothing but `/v1` requests to the service.
 *
 * Also: the form meets WCAG 2.2 AA in both themes, and works from the keyboard alone.
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
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

type Model = Record<string, unknown> & {
  meta: Record<string, unknown>;
  parameters: Record<string, { value: unknown }>;
};

const template = JSON.parse(
  readFileSync(join(REPOSITORY_ROOT, "templates", "coffee_shop", "model.json"), "utf8"),
) as Model;

async function accessible(page: Page): Promise<void> {
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
}

async function settled(page: Page): Promise<void> {
  await expect(page.locator(".save-state")).toHaveText("Saved");
  await expect(page.locator(".problems [role=status]")).not.toContainText("Checking");
}

logged.setTimeout(240_000);

logged(
  "a Build-mode user without data reaches a completed run changing only parameters",
  async ({ page, service, sent, outside }) => {
    const requests: string[] = [];
    page.on("request", (request) => requests.push(request.url()));

    await page.goto(service.url);
    await page
      .getByRole("dialog", { name: "Welcome" })
      .getByRole("button", { name: "Continue" })
      .click();
    await expect(page.locator(".gallery .card")).toHaveCount(10);
    await page.getByRole("button", { name: /^Build/ }).click();
    await expect(page.getByRole("heading", { name: "Build a model" })).toBeVisible();
    const first = page.getByRole("group", { name: "Step 1 of 2: What do you want to find out?" });
    await expect(first.getByRole("radio")).toHaveCount(6);
    await accessible(page);

    await first.getByRole("radio", { name: /How long will people or items wait\?/ }).check();
    await expect(first).toContainText("Opens: Coffee shop queue");
    await page.getByRole("radio", { name: /No, I will estimate/ }).check();
    await expect(page.getByRole("textbox", { name: "Project name" })).toHaveValue(
      "Coffee shop queue",
    );
    await page.getByRole("button", { name: "Continue" }).click();

    // The Canvas, nothing selected: the side panel shows the template's parameters.
    await expect(page.getByRole("heading", { name: "Canvas" })).toBeAttached();
    await settled(page);
    await expect(page.locator(".problems [role=status]")).toHaveText("No problems");
    await expect(page.getByRole("heading", { name: "Parameters" })).toBeVisible();
    const pid = decodeURIComponent(new URL(page.url()).hash.split("/").pop() ?? "");
    const tills = page.getByRole("group", { name: "tills" });
    await expect(tills.getByRole("textbox", { name: "Value" })).toHaveValue("1");
    await tills.getByRole("textbox", { name: "Value" }).fill("2");
    await page.getByRole("heading", { name: "Parameters" }).click();
    await settled(page);
    await expect(tills.getByRole("textbox", { name: "Value" })).toHaveValue("2");

    // Only the parameter changed.
    const stored = (await service.api("GET", `/v1/projects/${pid}/model`)).body as {
      model: Model;
    };
    expect(stored.model.meta).toEqual({
      ...template.meta,
      name: "Coffee shop queue",
      template: "coffee_shop",
    });
    expect(stored.model.parameters.tills?.value).toBe(2);
    const { meta: _m, parameters: _p, ...rest } = stored.model;
    const { meta: _tm, parameters: _tp, ...expected } = template;
    expect(rest).toEqual(expected);
    expect(stored.model.parameters).toEqual({
      ...template.parameters,
      tills: { ...template.parameters.tills, value: 2 },
    });
    expect((await service.api("GET", `/v1/projects/${pid}/data`)).body).toEqual([]);

    // Run, follow it to Done, then Results.
    const run = page.getByRole("banner").getByRole("button", { name: "Run" });
    await expect(run).not.toHaveAttribute("aria-disabled", "true");
    await run.click();
    await expect(page.getByRole("heading", { name: "Run monitor" })).toBeVisible();
    await expect(page.locator(".state-badge")).toHaveText("Done", { timeout: 120_000 });
    await page.getByRole("button", { name: "See the results" }).click();
    await expect(page.locator(".headline-card")).toBeVisible();
    await expect(page.locator(".results-footer")).toContainText("Model: Coffee shop queue");
    await expect(page.getByRole("rowheader", { name: "till.wait.mean" })).toBeVisible();

    // The service's log: only documented routes, none refused.
    await page.close();
    const checked = spawnSync(
      python(),
      [join(REPOSITORY_ROOT, "tests", "service", "request_log.py"), service.requestLog ?? ""],
      { encoding: "utf8" },
    );
    const found = JSON.parse(checked.stdout) as {
      clients: Record<string, number>;
      routes: Record<string, number>;
      problems: string[];
    };
    console.log(`request log: ${JSON.stringify(found)}`);
    expect(found.problems).toEqual([]);
    expect(checked.status).toBe(0);
    expect(found.clients.ui ?? 0).toBeGreaterThan(10);
    for (const route of [
      "GET /v1/templates",
      "POST /v1/projects",
      "POST /v1/projects/{pid}/model/edits",
      "POST /v1/projects/{pid}/runs",
      "GET /v1/runs/{rid}/events",
      "GET /v1/runs/{rid}/summary",
    ]) {
      expect(Object.keys(found.routes)).toContain(route);
    }
    // No file was imported: Build mode never requires a data file. (The one data route in
    // the log is the test's own listing above, which found none.)
    expect(Object.keys(found.routes).filter((route) => route.includes("/data"))).toEqual([
      "GET /v1/projects/{pid}/data",
    ]);

    const origin = new URL(service.origin);
    for (const url of requests) {
      expect(new URL(url).host, url).toBe(origin.host);
      expect(new URL(url).pathname.startsWith("/v1/"), url).toBe(true);
    }
    const api = requests.filter((url) => !new URL(url).pathname.startsWith("/v1/ui/"));
    expect(api.length).toBe(sent.length);
    expect(outside).toEqual([]);
  },
);

for (const scheme of ["light", "dark"] as const) {
  base(`the Build form meets WCAG 2.2 AA in the ${scheme} theme`, async ({ page, service }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
    await page.goto(service.url);
    await expect(page.locator(".gallery .card")).toHaveCount(10);
    await page.getByRole("button", { name: /^Build/ }).click();
    await page.getByRole("radio", { name: /What mix, plan or rota is best\?/ }).check();
    await expect(page.getByRole("group", { name: "Which of these?" })).toBeVisible();
    await accessible(page);
  });
}

base("the Build form works from the keyboard alone", async ({ page, service }) => {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  await page.goto(service.url);
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
  const build = page.getByRole("button", { name: /^Build/ });
  // Build is available once the templates are listed.
  await expect(page.locator(".gallery .card")).toHaveCount(10);
  await expect(build).not.toHaveAttribute("aria-disabled", "true");
  await build.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Build a model" })).toBeFocused();
  await expect(page.getByText("Opens: Coffee shop queue")).toBeVisible();
  // Tab into the first group, arrows choose, Space takes the focused answer.
  await page.keyboard.press("Tab");
  await expect(page.getByRole("radio", { name: /How long will people/ })).toBeFocused();
  await page.keyboard.press("Space");
  for (let press = 0; press < 5; press += 1) await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("radio", { name: /What mix, plan or rota/ })).toBeChecked();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("radio", { name: /A product mix/ })).toBeFocused();
  await page.keyboard.press("Space");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("radio", { name: /Yes, import a file/ })).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("radio", { name: /No, I will estimate/ })).toBeChecked();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("textbox", { name: "Project name" })).toHaveValue("Product mix");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Continue" })).toBeFocused();
  await page.keyboard.press("Enter");
  // A plan opens in the Table view: its decisions, goal and limits are its parameters.
  await expect(page.getByRole("textbox", { name: "Name of decision 1" })).toHaveValue("chairs");
  await expect(page.getByRole("button", { name: "Table", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
