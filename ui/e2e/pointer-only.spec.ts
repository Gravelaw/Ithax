/**
 * Spec 3's M9 acceptance rows "A pointer-only end-to-end test builds, runs and views the
 * coffee shop" and "Every interface action is reproducible by API: the end-to-end request
 * log contains only documented `/v1` routes" (AKS-121).
 *
 * One test, from the first start to the results, by pointer: the mouse for every action
 * (clicks, drags from the palette, drags port to port, choices in pickers and tick boxes),
 * typing only values into fields, and no keyboard shortcut. The welcome notice is closed
 * with Continue; Home makes a new Process project; the Canvas builds the coffee shop; the
 * Experiment screen sets its `base` experiment; Run starts it, the Run monitor follows it
 * and Results shows it. Then:
 *
 * - the saved model (`GET .../model`) equals `examples/coffee_shop.json` except `ui` and
 *   `format_version` (a new project is written at the reader's 0.2 since AKS-123; the
 *   example is 0.1);
 * - `till.wait.mean` from the run's summary is within 3 standard errors of 270 s at the
 *   example's seed, 12345, with 30 repeat runs of 200 h (spec 2's pass rule; the standard
 *   error is the half-width divided by the t quantile the summary used);
 * - Results shows no finding and the footer;
 * - the service's own request log (`tests/service/logged_service.py`, every call that
 *   reached it) holds only routes of spec 3's endpoint table, none refused, checked by
 *   `tests/service/request_log.py`; and the page sent nothing but `/v1` requests to the
 *   service, the only ones outside the API being the interface's own files at `/v1/ui/`.
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import { test as base, expect } from "./fixtures";
import { python, REPOSITORY_ROOT, type Service, startService } from "./service";

const test = base.extend<{ service: Service }>({
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

test.setTimeout(240_000);

interface Component {
  id: string;
  ui?: unknown;
  [key: string]: unknown;
}

interface Model {
  components: Component[];
  ui?: unknown;
  [key: string]: unknown;
}

interface Metric {
  mean: number;
  half_width: number;
  n: number;
  unit: string;
}

const example = JSON.parse(
  readFileSync(join(REPOSITORY_ROOT, "examples", "coffee_shop.json"), "utf8"),
) as Model;

/** Student's t quantile at 0.975 for 29 degrees of freedom: the summary's 95% interval of 30
 * repeat runs (spec 2 "Statistic definitions"; scipy.stats.t.ppf(0.975, 29)). */
const T_975_29 = 2.045229642132703;
const NO_WARRANTY = "Simulation results are estimates and carry no warranty.";

function withoutUi(model: Model): Model {
  const { ui: _ui, ...rest } = model;
  return { ...rest, components: rest.components.map(({ ui: _c, ...component }) => component) };
}

function block(page: Page, id: string): Locator {
  return page.locator(`.react-flow__node[data-id="${id}"]`);
}

function rail(page: Page, screen: string): Locator {
  return page.getByRole("navigation", { name: "Screens" }).getByRole("button", { name: screen });
}

async function saved(page: Page): Promise<void> {
  await expect(page.locator(".save-state")).toHaveText("Saved");
}

async function settled(page: Page): Promise<void> {
  await saved(page);
  await expect(page.locator(".problems [role=status]")).not.toContainText("Checking");
}

/** Leaves a side-panel field by clicking the panel's heading, which commits it. */
async function commitPanel(page: Page): Promise<void> {
  await page.locator(".side-panel h2").first().click();
}

async function drop(page: Page, type: string, x: number, y: number, id: string): Promise<void> {
  await page
    .getByRole("button", { name: type, exact: true })
    .dragTo(page.locator(".react-flow__pane"), { targetPosition: { x, y } });
  await expect(block(page, id)).toBeVisible();
  await settled(page);
}

async function rename(page: Page, from: string, to: string): Promise<void> {
  await block(page, from).click();
  await page.getByRole("textbox", { name: "Id" }).fill(to);
  await commitPanel(page);
  await expect(block(page, to)).toBeVisible();
  await settled(page);
}

async function connect(page: Page, from: string, to: string): Promise<void> {
  await block(page, from).locator(".react-flow__handle.port.source").hover();
  await page.mouse.down();
  await block(page, to).locator(".react-flow__handle.port.target").hover();
  await page.mouse.up();
  await settled(page);
}

async function exponential(page: Page, mean: string): Promise<void> {
  await page.getByLabel("Distribution", { exact: true }).selectOption("exponential");
  await settled(page);
  await page.getByLabel("Unit of Mean").selectOption("min");
  await page.getByRole("textbox", { name: "Mean", exact: true }).fill(mean);
  await commitPanel(page);
  await settled(page);
}

/** Types into an Experiment field and leaves it by clicking the experiment's title. */
async function enter(page: Page, name: string, value: string): Promise<void> {
  const field = page.getByRole("textbox", { name, exact: true });
  await field.fill(value);
  await page.locator("#experiment-id-heading").click();
  await saved(page);
  await expect(field).toHaveValue(value);
}

/** Fails on a keyboard action: every key the page sees must be typing into a field. */
async function refuseShortcuts(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as { shortcuts: string[] }).shortcuts = seen;
    window.addEventListener(
      "keydown",
      (event) => {
        const target = event.target as HTMLElement | null;
        const typing =
          target !== null &&
          (target.tagName === "INPUT" || target.tagName === "TEXTAREA") &&
          !event.ctrlKey &&
          !event.metaKey &&
          !event.altKey;
        if (!typing) seen.push(`${event.key} on ${target?.tagName ?? "nothing"}`);
      },
      true,
    );
  });
}

test("the coffee shop is built, run and viewed by pointer, through documented routes only", async ({
  page,
  service,
  sent,
  outside,
}) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  const sockets: string[] = [];
  page.on("websocket", (socket) => sockets.push(socket.url()));
  await refuseShortcuts(page);

  // First start: the welcome notice, closed with Continue.
  await page.goto(service.url);
  await page
    .getByRole("dialog", { name: "Welcome" })
    .getByRole("button", { name: "Continue" })
    .click();
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();

  // Home: a new Process project.
  await page.getByRole("button", { name: "New empty project" }).click();
  const dialog = page.getByRole("dialog", { name: "New empty project" });
  await dialog.getByRole("textbox", { name: "Name" }).fill("Coffee shop");
  await dialog.getByRole("radio", { name: /Process/ }).check();
  await dialog.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("heading", { name: "Canvas" })).toBeAttached();
  await settled(page);
  const pid = decodeURIComponent(new URL(page.url()).hash.split("/").pop() ?? "");

  // The Canvas: three blocks, the parameter, the settings and two connections.
  await drop(page, "source", 140, 160, "source_1");
  await drop(page, "server", 380, 160, "server_1");
  await drop(page, "sink", 620, 160, "sink_1");
  await rename(page, "source_1", "arrivals");
  await exponential(page, "2");
  await page.locator(".react-flow__pane").click({ position: { x: 300, y: 30 } });
  const parameter = page.getByRole("form", { name: "Add parameter" });
  await parameter.getByRole("textbox", { name: "Id" }).fill("tills");
  await parameter.getByRole("combobox", { name: "Type" }).selectOption("integer");
  await parameter.getByRole("textbox", { name: "Value" }).fill("1");
  await parameter.getByRole("textbox", { name: "Min (optional)" }).fill("1");
  await parameter.getByRole("textbox", { name: "Max (optional)" }).fill("5");
  await parameter.getByRole("button", { name: "Add parameter" }).click();
  await settled(page);
  await rename(page, "server_1", "till");
  await page.getByRole("checkbox", { name: "Use parameter for Capacity" }).check();
  await page.getByRole("combobox", { name: "Parameter for Capacity" }).selectOption("tills");
  await settled(page);
  await exponential(page, "1.5");
  await rename(page, "sink_1", "exit");
  await connect(page, "arrivals", "till");
  await connect(page, "till", "exit");
  await expect(page.locator(".problems [role=status]")).toHaveText("No problems");

  // The Experiment screen: the base experiment of 30 repeat runs of 200 h at seed 12345.
  await rail(page, "Experiment").click();
  await expect(page.getByRole("heading", { name: "base", exact: true })).toBeVisible();
  await enter(page, "Run length", "200");
  await page.getByRole("combobox", { name: "Unit of Settling-in time" }).selectOption("h");
  await saved(page);
  await enter(page, "Settling-in time", "10");
  await expect(page.getByRole("textbox", { name: "Repeat runs" })).toHaveValue("30");
  await enter(page, "Seed", "12345");

  // The saved model is the example's, except `ui` and `format_version`: a new project is
  // written at the reader's version, 0.2 since AKS-123, and the example is 0.1.
  const stored = (await service.api("GET", `/v1/projects/${pid}/model`)).body as { model: Model };
  expect(stored.model.format_version).toBe("0.2");
  expect(example.format_version).toBe("0.1");
  expect(withoutUi({ ...stored.model, format_version: "0.1" })).toEqual(withoutUi(example));

  // Run from the Canvas, follow it on the Run monitor, then Results.
  await rail(page, "Canvas").click();
  await settled(page);
  await expect(page.locator(".problems [role=status]")).toHaveText("No problems");
  const run = page.getByRole("banner").getByRole("button", { name: "Run" });
  await expect(run).not.toHaveAttribute("aria-disabled", "true");
  await run.click();
  await expect(page.getByRole("heading", { name: "Run monitor" })).toBeVisible();
  const rid = decodeURIComponent(new URL(page.url()).hash.split("/").pop() ?? "");
  await expect(page.getByRole("heading", { name: `Run ${rid}` })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: `Progress of run ${rid}` })).toBeVisible();
  await expect(page.locator(".state-badge")).toHaveText("Done", { timeout: 120_000 });
  await page.getByRole("button", { name: "See the results" }).click();
  await expect(page.locator(".headline-card")).toHaveText(
    "No finding rule fired at the thresholds in Settings.",
  );
  const footer = page.locator(".results-footer");
  for (const item of [
    "Model: Coffee shop",
    `Run: ${rid}`,
    "Fidelity: Standard: 30 replications of 200 h, 95% confidence",
    "Replications: 30 · Confidence: 95%",
    "Engine: simpy",
    NO_WARRANTY,
  ]) {
    await expect(footer).toContainText(item);
  }
  await expect(
    page.getByRole("rowheader", { name: "till.wait.mean" }).locator("xpath=.."),
  ).toBeVisible();

  // till.wait.mean within 3 standard errors of 270 s (spec 2's pass rule).
  const answer = (await service.api("GET", `/v1/runs/${rid}/summary`)).body as {
    summary: {
      confidence: number;
      scenarios: Record<string, { metrics: Record<string, Metric> }>;
    };
    findings: unknown[];
  };
  expect(answer.findings).toEqual([]);
  expect(answer.summary.confidence).toBe(0.95);
  const wait = answer.summary.scenarios.default?.metrics["till.wait.mean"];
  expect(wait).toBeDefined();
  if (wait === undefined) return;
  expect(wait.unit).toBe("s");
  expect(wait.n).toBe(30);
  const standardError = wait.half_width / T_975_29;
  const distance = (wait.mean - 270) / standardError;
  test.info().annotations.push({
    type: "till.wait.mean",
    description: `${wait.mean} s, half-width ${wait.half_width} s, standard error ${standardError} s, ${distance} standard errors from 270 s`,
  });
  console.log(
    `till.wait.mean ${wait.mean} s (half-width ${wait.half_width} s, standard error ${standardError.toFixed(3)} s): ${distance.toFixed(3)} standard errors from 270 s`,
  );
  expect(Math.abs(distance)).toBeLessThanOrEqual(3);

  // No key was pressed but in typing a value.
  expect(
    await page.evaluate(() => (window as unknown as { shortcuts: string[] }).shortcuts),
  ).toEqual([]);

  // Nothing more is sent once the page is closed; then the service's log is read.
  await page.close();
  const log = service.requestLog ?? "";
  const checked = spawnSync(
    python(),
    [join(REPOSITORY_ROOT, "tests", "service", "request_log.py"), log],
    { encoding: "utf8" },
  );
  const found = JSON.parse(checked.stdout) as {
    requests: number;
    clients: Record<string, number>;
    routes: Record<string, number>;
    problems: string[];
  };
  console.log(`request log: ${JSON.stringify(found)}`);
  expect(found.problems).toEqual([]);
  expect(checked.status).toBe(0);
  // The interface's own calls carry X-Client: ui; the test's (no header) are the others.
  expect(found.clients.ui ?? 0).toBeGreaterThan(20);
  for (const route of [
    "GET /v1/ui/{path}",
    "PUT /v1/settings",
    "POST /v1/projects",
    "POST /v1/projects/{pid}/model/edits",
    "POST /v1/projects/{pid}/runs",
    "GET /v1/runs/{rid}/events",
    "GET /v1/runs/{rid}/summary",
  ]) {
    expect(Object.keys(found.routes)).toContain(route);
  }

  // The page: every request went to the service under /v1, and every one outside the
  // interface's files was an API request.
  const origin = new URL(service.origin);
  for (const url of [...requests, ...sockets]) {
    const parsed = new URL(url);
    expect(parsed.host, url).toBe(origin.host);
    expect(parsed.pathname.startsWith("/v1/"), url).toBe(true);
  }
  const api = requests.filter((url) => !new URL(url).pathname.startsWith("/v1/ui/"));
  expect(api.length).toBe(sent.length);
  expect(sockets.length).toBeGreaterThan(0);
  expect(outside).toEqual([]);
});
