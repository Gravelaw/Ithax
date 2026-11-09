/**
 * The Data screen against a real service (AKS-120).
 *
 * On a coffee shop project, a CSV file is imported through the file picker, its number
 * column is given its unit (minutes), the column is fitted, the histogram is drawn with the
 * best candidate's curve and shown as a table, and the best candidate is used for the
 * till's service time after the waiting question; the column itself is then used, as it
 * is, for the arrivals' interarrival time. The saved model holds exactly what the service's
 * fit returned and the `empirical` `data` reference, and validates with no issues. Only
 * documented routes are used, and the screen meets WCAG 2.2 AA.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

const REPOSITORY = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const coffeeShop = JSON.parse(
  readFileSync(join(REPOSITORY, "examples", "coffee_shop.json"), "utf8"),
) as Record<string, unknown>;

/** 200 service times in minutes: the quantiles of an exponential of mean 1.5 (no randomness). */
function serviceTimes(): string {
  const rows = ["day,service_min"];
  for (let index = 0; index < 200; index += 1) {
    const quantile = -1.5 * Math.log(1 - (index + 0.5) / 200);
    rows.push(`${index % 5 === 0 ? "Mon" : "Tue"},${quantile.toFixed(4)}`);
  }
  return `${rows.join("\n")}\n`;
}

async function settled(page: Page): Promise<void> {
  await expect(page.locator(".save-state")).toHaveText("Saved");
}

interface Distribution {
  dist: string;
  [field: string]: unknown;
}

test("a CSV column is imported, fitted and used for a setting", async ({ page, service, sent }) => {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  const made = await service.api("POST", "/v1/projects", { name: "Coffee shop" });
  const pid = (made.body as { id: string }).id;
  await service.api("POST", `/v1/projects/${pid}/model/edits`, {
    edits: [
      { edit: "set_parameter", id: "tills", value: 1, type: "integer", min: 1, max: 5 },
      ...(coffeeShop.components as { id: string; type: string; params: unknown }[]).map(
        (component) => ({ edit: "add_component", ...component }),
      ),
      ...(coffeeShop.connections as { from: string; to: string }[]).map((connection) => ({
        edit: "connect",
        ...connection,
      })),
    ],
  });
  await page.goto(service.url);
  await page.getByRole("region", { name: "Recent projects" }).getByText("Coffee shop").click();
  await settled(page);
  await page
    .getByRole("navigation", { name: "Screens" })
    .getByRole("button", { name: "Data" })
    .click();
  await expect(page.getByText("No files imported yet.")).toBeVisible();
  const before = sent.length;

  // Import: the file picker, then the columns and the first rows.
  await page.locator("input[type=file]").setInputFiles({
    name: "service_times.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(serviceTimes()),
  });
  await expect(page.getByRole("heading", { name: "service_times.csv" })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "service_min" })).toBeVisible();
  await expect(page.locator(".data-main tbody tr")).toHaveCount(2 + 10);
  // The unit: the file is imported again with it.
  await page.getByRole("combobox", { name: "Unit of service_min" }).selectOption("min");
  await expect(page.getByRole("combobox", { name: "Unit of service_min" })).toHaveValue("min");
  const listed = (await service.api("GET", `/v1/projects/${pid}/data`)).body as {
    columns: { name: string; unit: string | null }[];
  }[];
  expect(listed[0]?.columns.find((item) => item.name === "service_min")?.unit).toBe("min");

  // Fit: the candidates best first, the histogram and its table.
  await page.getByRole("button", { name: "Fit a distribution" }).click();
  const fitted = (
    await service.api("POST", `/v1/projects/${pid}/data/service_times.csv/fit`, {
      column: "service_min",
    })
  ).body as {
    candidates: { distribution: Distribution }[];
    histogram: { counts: number[] };
  };
  const best = fitted.candidates[0]?.distribution as Distribution;
  await expect(page.getByRole("rowheader", { name: best.dist, exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /^Histogram of service_min/ })).toBeVisible();
  await expect(page.locator(".chart svg path").first()).toBeAttached();
  await page.getByRole("button", { name: "Show as table" }).click();
  await expect(page.locator(".fit-panel table").nth(1).locator("tbody tr")).toHaveCount(
    fitted.histogram.counts.length,
  );
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);

  // Use for the till's service time: the waiting question first.
  const target = page.getByRole("combobox", { name: "Block setting" });
  await target.selectOption({ label: "till · service (a service or process time)" });
  await expect(page.getByText("Does this column include time spent waiting?")).toBeVisible();
  await expect(page.getByRole("button", { name: "Use it" })).toHaveAttribute(
    "aria-disabled",
    "true",
  );
  await page.getByRole("radio", { name: "Not sure" }).check();
  await expect(page.getByRole("alert")).toContainText("counts the wait twice");
  await page.getByRole("radio", { name: "No", exact: true }).check();
  await page.getByRole("button", { name: "Use it", exact: true }).click();
  await settled(page);
  const afterFit = (await service.api("GET", `/v1/projects/${pid}/model`)).body as {
    model: { components: { id: string; params: Record<string, unknown> }[] };
  };
  expect(afterFit.model.components.find((item) => item.id === "till")?.params.service).toEqual(
    best,
  );

  // The column as it is, for the arrivals: no question for an interarrival time.
  await target.selectOption({ label: "arrivals · interarrival" });
  await expect(page.getByText("Does this column include time spent waiting?")).toHaveCount(0);
  await page.getByRole("radio", { name: /Use the data as it is/ }).check();
  await page.getByRole("button", { name: "Use it", exact: true }).click();
  await settled(page);
  const afterData = (await service.api("GET", `/v1/projects/${pid}/model`)).body as {
    model: { components: { id: string; params: Record<string, unknown> }[] };
  };
  expect(
    afterData.model.components.find((item) => item.id === "arrivals")?.params.interarrival,
  ).toEqual({ dist: "empirical", data: { file: "service_times.csv", column: "service_min" } });
  const checked = await service.api("POST", `/v1/projects/${pid}/validate`);
  expect((checked.body as { issues: unknown[] }).issues).toEqual([]);

  // Only the documented routes: the data routes, model edits and validation.
  const data = `/v1/projects/${pid}/data`;
  for (const request of sent.slice(before)) {
    expect([
      `GET ${data}`,
      `POST ${data}`,
      `POST ${data}/service_times.csv/fit`,
      `POST /v1/projects/${pid}/model/edits`,
      `POST /v1/projects/${pid}/validate`,
      `GET /v1/projects/${pid}/model`,
    ]).toContain(`${request.method} ${request.path}`);
  }
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
});

test("the service's refusal of a file is shown as its issue", async ({ page, service }) => {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  await service.api("POST", "/v1/projects", { name: "Shop" });
  await page.goto(service.url);
  await page.getByRole("region", { name: "Recent projects" }).getByText("Shop").click();
  await settled(page);
  await page
    .getByRole("navigation", { name: "Screens" })
    .getByRole("button", { name: "Data" })
    .click();
  await page.locator("input[type=file]").setInputFiles({
    name: "bad.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("a,b\n1,2,3\n"),
  });
  await expect(page.getByRole("alert")).toContainText("E189");
  await expect(page.getByText("No files imported yet.")).toBeVisible();
});
