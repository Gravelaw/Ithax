/**
 * The three optimization templates of AKS-140 open in the interface against a real
 * service (spec 3 "Screens": the Experiment screen's optimization setup; spec 2
 * "Optimization": the table-style editor of decisions, goal and limits).
 *
 * Each project is made from its template with `POST /v1/projects` and `template`, the
 * route the gallery's Learn mode will use (AKS-124), and opened from Home's recent
 * projects. The product mix and the staff rota open in the Table view with no problem and
 * draw the Diagram view; the staff rota is indexed, so the Table view says so and reads its
 * sets in words. The search of "How many machines?" is shown on the Experiment screen.
 * Every view meets WCAG 2.2 AA.
 */
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import type { Service } from "./service";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function openTemplate(page: Page, service: Service, template: string, name: string) {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  const made = await service.api("POST", "/v1/projects", { name, template });
  expect(made.status).toBe(200);
  const pid = (made.body as { id: string }).id;
  const saved = (await service.api("GET", `/v1/projects/${pid}/model`)).body as {
    model: { meta: { template?: string } };
  };
  expect(saved.model.meta.template).toBe(template);
  await page.goto(service.url);
  await page.getByRole("region", { name: "Recent projects" }).getByText(name).click();
  await expect(page.locator(".save-state")).toHaveText("Saved");
  await expect(page.locator(".problems [role=status]")).toHaveText("No problems");
  return pid;
}

async function accessible(page: Page): Promise<void> {
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
}

test("the product mix template opens in the Table and Diagram views", async ({ page, service }) => {
  await openTemplate(page, service, "product_mix", "Workshop");
  await expect(page.getByRole("button", { name: "Table", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByRole("textbox", { name: "Name of decision 1" })).toHaveValue("chairs");
  await expect(page.getByRole("textbox", { name: "Name of decision 2" })).toHaveValue("tables");
  await expect(page.getByText("Maximize 45 × chairs + 80 × tables")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Limit of wood" })).toHaveValue("400");
  await expect(page.getByRole("textbox", { name: "Limit of labour" })).toHaveValue("450");
  await expect(page.getByTestId("indexed-notice")).toHaveCount(0);
  await accessible(page);

  await page.getByRole("button", { name: "Diagram", exact: true }).click();
  await expect(page.getByRole("button", { name: "chairs decision, continuous ≥ 0" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "wood 5 × chairs + 20 × tables ≤ 400" }),
  ).toBeVisible();
  await expect(page.locator(".plan-line")).toHaveCount(6);
  await accessible(page);
});

test("the staff rota template opens as an indexed integer plan", async ({ page, service }) => {
  await openTemplate(page, service, "staff_rota", "Rota");
  await expect(page.getByTestId("indexed-notice")).toContainText("This plan is indexed");
  await expect(page.getByRole("textbox", { name: "Name of decision 1" })).toHaveValue("staff");
  await expect(page.getByRole("combobox", { name: "Kind of staff" })).toHaveValue("integer");
  await expect(page.getByText("one for each patterns")).toBeVisible();
  await expect(page.getByText("Minimize Σ over patterns staff[patterns]")).toBeVisible();
  await expect(
    page.getByText(
      "For each days: Σ over patterns works[patterns, days] × staff[patterns] ≥ need[days]",
    ),
  ).toBeVisible();
  await accessible(page);

  await page.getByRole("button", { name: "Diagram", exact: true }).click();
  await expect(
    page.getByRole("button", {
      name: "staff decision, integer ≥ 0, one for each patterns",
    }),
  ).toBeVisible();
  await expect(page.locator(".plan-line-text")).toHaveText(["1", "works"]);
  await accessible(page);
});

test("the Experiment screen shows the search of How many machines?", async ({ page, service }) => {
  await openTemplate(page, service, "how_many_machines", "Tills");
  await page
    .getByRole("navigation", { name: "Screens" })
    .getByRole("button", { name: "Experiment" })
    .click();
  await expect(page.getByRole("heading", { name: "base", exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Name of objective 1" })).toHaveValue("wait");
  await expect(page.getByRole("textbox", { name: "Name of constraint 1" })).toHaveValue("busy");
  await expect(page.getByRole("textbox", { name: "Value of constraint busy" })).toHaveValue("0.35");
  await expect(
    page.getByRole("checkbox", { name: "Search for the best parameter values" }),
  ).toBeChecked();
  await expect(page.getByRole("combobox", { name: "Objective of the search" })).toHaveValue("wait");
  await expect(page.getByRole("textbox", { name: "Budget" })).toHaveValue("10");
  await expect(page.getByText("tills from 1 to 5")).toBeVisible();
  await accessible(page);
});
