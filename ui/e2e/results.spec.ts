/**
 * The Run monitor and Results against a real service (AKS-138).
 *
 * Runs start from the Canvas's Run button. The coffee shop (`examples/coffee_shop.json`,
 * 30 repeat runs of 200 h at seed 12345) fires no finding (spec 4: till 0.749, 3.7%), and
 * its results carry every footer item; its exports give the CSV, a PDF whose every page
 * carries the footer, and the project zip. The three-machine line fires `bottleneck` (weld
 * 90%) and `not_enough_runs` (15.7 min plus or minus 2.09 min) before any chart. A fresh
 * load of the page while a run goes on finds the run and shows its progress until done
 * (spec 3's acceptance row "Reopening the interface mid-run shows its progress"). The
 * product mix's run shows 24 chairs, 14 tables and 2,200.
 */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";
import { expect, test } from "./fixtures";
import { python, type Service } from "./service";

const REPOSITORY = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const NO_WARRANTY = "Simulation results are estimates and carry no warranty.";

function example(...path: string[]): Record<string, unknown> {
  return JSON.parse(readFileSync(join(REPOSITORY, ...path), "utf8")) as Record<string, unknown>;
}

/** A project holding `model`, made as a script would; the page opens on its Canvas. */
async function openProject(
  page: Page,
  service: Service,
  name: string,
  model: Record<string, unknown>,
): Promise<string> {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  const created = await service.api("POST", "/v1/projects", {
    name,
    domain: model.domain ?? "process",
  });
  const pid = (created.body as { id: string }).id;
  const put = await service.api("PUT", `/v1/projects/${pid}/model`, model);
  expect(put.status).toBe(200);
  await page.goto(service.url);
  await page.evaluate((hash) => {
    window.location.hash = hash;
  }, `#/canvas/${pid}`);
  await expect(page.locator(".save-state")).toHaveText("Saved");
  return pid;
}

/** Presses Run once it is free, and returns the run id the monitor opens at. */
async function run(page: Page): Promise<string> {
  const button = page.getByRole("banner").getByRole("button", { name: "Run" });
  await expect(button).not.toHaveAttribute("aria-disabled", "true");
  await button.click();
  await expect(page.getByRole("heading", { name: "Run monitor" })).toBeVisible();
  const rid = decodeURIComponent(new URL(page.url()).hash.split("/").pop() ?? "");
  await expect(page.getByRole("heading", { name: `Run ${rid}` })).toBeVisible();
  return rid;
}

async function done(page: Page): Promise<void> {
  await expect(page.locator(".state-badge")).toHaveText("Done", { timeout: 60_000 });
}

async function pdfPages(path: string): Promise<string[]> {
  const document = await getDocument({
    data: new Uint8Array(readFileSync(path)),
    standardFontDataUrl: `${join(dirname(fileURLToPath(import.meta.url)), "..", "node_modules", "pdfjs-dist", "standard_fonts")}/`,
  }).promise;
  const pages: string[] = [];
  for (let number = 1; number <= document.numPages; number += 1) {
    const content = await (await document.getPage(number)).getTextContent();
    pages.push(
      content.items
        .map((item) => ("str" in item ? item.str : ""))
        .join(" ")
        .replace(/\s+/g, " "),
    );
  }
  await document.destroy();
  return pages;
}

async function saved(page: Page, button: string): Promise<{ name: string; path: string }> {
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: button }).click(),
  ]);
  return { name: download.suggestedFilename(), path: await download.path() };
}

test("the coffee shop runs from the Canvas; its results have no finding, the footer and the exports", async ({
  page,
  service,
  sent,
}) => {
  const pid = await openProject(
    page,
    service,
    "Coffee shop",
    example("examples", "coffee_shop.json"),
  );
  const rid = await run(page);
  await expect(page.getByRole("progressbar", { name: `Progress of run ${rid}` })).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
  await done(page);
  await page.getByRole("button", { name: "See the results" }).click();
  await expect(page.locator(".headline-card")).toHaveText(
    "No finding rule fired at the thresholds in Settings.",
  );
  const runBody = (await service.api("GET", `/v1/runs/${rid}`)).body as {
    engine: { name: string; version: string };
  };
  expect(runBody.engine.name).toBe("simpy");
  const footerItems = [
    "Model: Coffee shop",
    `Run: ${rid}`,
    "Fidelity: Standard: 30 replications of 200 h, 95% confidence",
    "Replications: 30 · Confidence: 95%",
    `Engine: simpy ${runBody.engine.version}`,
    NO_WARRANTY,
  ];
  const footer = page.locator(".results-footer");
  for (const item of footerItems) await expect(footer).toContainText(item);
  const wait = page.getByRole("rowheader", { name: "till.wait.mean" }).locator("xpath=..");
  await expect(wait).toContainText("4.46 min");
  await expect(page.getByRole("img", { name: /^Busy share by component/ })).toBeVisible();
  const feedback = page.getByRole("link", { name: "Tell us what you built (opens your browser)" });
  await expect(feedback).toHaveAttribute("rel", "noopener noreferrer");
  await expect(feedback).toHaveAttribute("target", "_blank");
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);

  const csv = await saved(page, "Export repeat runs (CSV)");
  expect(csv.name).toBe(`${rid}-replications.csv`);
  expect(readFileSync(csv.path, "utf8").split("\r\n")[0]).toBe(
    "scenario,replication,metric,value,unit",
  );
  const pdf = await saved(page, "Export PDF");
  expect(pdf.name).toBe(`${rid}.pdf`);
  const pages = await pdfPages(pdf.path);
  expect(pages.length).toBeGreaterThan(0);
  for (const text of pages) for (const item of footerItems) expect(text).toContain(item);
  const zip = await saved(page, "Export project (zip)");
  expect(zip.name).toBe("Coffee shop.zip");
  const names = execFileSync(
    python(),
    [
      "-I",
      "-c",
      "import sys, zipfile; print('\\n'.join(zipfile.ZipFile(sys.argv[1]).namelist()))",
      zip.path,
    ],
    { encoding: "utf8" },
  )
    .trim()
    .split("\n");
  expect(names).toEqual(
    expect.arrayContaining(["project.json", "model.json", `runs/${rid}/summary.json`]),
  );
  expect(names).not.toContain("index.sqlite");
  // The routes the screens used (a WebSocket is not a request the page records).
  const paths = new Set(sent.map((request) => `${request.method} ${request.path}`));
  for (const path of [
    `POST /v1/projects/${pid}/runs`,
    `GET /v1/runs/${rid}/summary`,
    `GET /v1/runs/${rid}/tables/replications`,
    `GET /v1/projects/${pid}/export`,
  ]) {
    expect(paths).toContain(path);
  }
});

test("the three-machine line shows its bottleneck and not-enough-runs findings before its charts", async ({
  page,
  service,
}) => {
  await openProject(
    page,
    service,
    "Three-machine line",
    example("examples", "three_machine_line.json"),
  );
  await run(page);
  await done(page);
  await page.getByRole("button", { name: "See the results" }).click();
  const findings = page.getByRole("list", { name: "Findings" }).getByRole("listitem");
  await expect(findings).toHaveCount(2);
  await expect(findings.nth(0)).toContainText("Bottleneck");
  await expect(findings.nth(0)).toContainText("weld is the bottleneck: busy 90% of the time");
  await expect(findings.nth(1)).toContainText("Not enough runs");
  await expect(findings.nth(1)).toContainText("15.7 min plus or minus 2.09 min");
  await expect(page.locator(".headline-card")).toContainText("weld is the bottleneck");
  const before = await page.evaluate(() => {
    const list = document.querySelector(".findings");
    const chart = document.querySelector(".result-chart");
    return list !== null && chart !== null && Boolean(list.compareDocumentPosition(chart) & 4);
  });
  expect(before).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
});

test("a fresh load mid-run finds the run and shows its progress until it is done", async ({
  page,
  service,
}) => {
  const model = example("examples", "coffee_shop.json");
  const [experiment] = model.experiments as Record<string, unknown>[];
  if (experiment) experiment.length = "1500 h";
  const pid = await openProject(page, service, "Long coffee shop", model);
  const rid = await run(page);
  const bar = page.getByRole("progressbar", { name: `Progress of run ${rid}` });
  await expect(page.locator(".state-badge")).toHaveText("Running");
  // A fresh load of the project's Run monitor, which names no run, while the run goes on.
  await page.evaluate((hash) => {
    window.location.hash = hash;
  }, `#/monitor/${pid}`);
  await page.reload();
  await expect(page.getByRole("heading", { name: `Run ${rid}` })).toBeVisible();
  await expect(page.locator(".state-badge")).toHaveText("Running");
  await expect(bar).toHaveAttribute("aria-valuetext", /replication \d+ of 30/);
  const shown = Number(await bar.getAttribute("aria-valuenow"));
  expect(shown).toBeGreaterThanOrEqual(0);
  expect(shown).toBeLessThanOrEqual(100);
  await done(page);
  await expect(bar).toHaveAttribute("aria-valuenow", "100");
});

test("an optimization model's run shows the best plan", async ({ page, service }) => {
  await openProject(
    page,
    service,
    "Product mix",
    example("benchmarks", "product_mix", "model.json"),
  );
  await run(page);
  await done(page);
  await page.getByRole("button", { name: "See the results" }).click();
  await expect(page.getByRole("heading", { name: "The best plan" })).toBeVisible();
  await expect(page.getByText(/Goal: 2,200/)).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "chairs" }).locator("xpath=..")).toContainText(
    "24",
  );
  await expect(page.getByRole("rowheader", { name: "tables" }).locator("xpath=..")).toContainText(
    "14",
  );
  await expect(page.locator(".results-footer")).toContainText(
    "Replications and confidence: not replicated",
  );
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
});
