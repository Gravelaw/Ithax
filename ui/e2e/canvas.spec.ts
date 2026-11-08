/**
 * The Canvas against a real service (AKS-136).
 *
 * The first test is AKS-121's gate brought forward: the coffee shop's components,
 * connections and parameter built by pointer alone (dragging from the palette, dragging
 * port to port, choosing in pickers and typing values into fields; no keyboard shortcut)
 * give a model whose `components`, `connections` and `parameters` equal
 * `examples/coffee_shop.json` except `ui`. The others: the events socket reloads the model
 * on another client's write; undo and redo; the keyboard way; WCAG 2.2 AA in both themes.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import type { Locator, Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import type { Service } from "./service";

const REPOSITORY = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

interface Model {
  parameters: Record<string, unknown>;
  components: { id: string; ui?: unknown; [key: string]: unknown }[];
  connections: unknown[];
  [key: string]: unknown;
}

const example = JSON.parse(
  readFileSync(join(REPOSITORY, "examples", "coffee_shop.json"), "utf8"),
) as Model;

async function openCanvas(page: Page, service: Service, name: string): Promise<string> {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  const made = await service.api("POST", "/v1/projects", { name });
  const pid = (made.body as { id: string }).id;
  await page.goto(service.url);
  await page.getByRole("region", { name: "Recent projects" }).getByText(name).click();
  await expect(page.locator(".save-state")).toHaveText("Saved");
  await expect(page.locator(".problems [role=status]")).toHaveText("No problems");
  return pid;
}

async function model(service: Service, pid: string): Promise<Model> {
  return ((await service.api("GET", `/v1/projects/${pid}/model`)).body as { model: Model }).model;
}

function block(page: Page, id: string): Locator {
  return page.locator(`.react-flow__node[data-id="${id}"]`);
}

/** Leaves a field by clicking the side panel's heading, which commits it. */
async function commit(page: Page): Promise<void> {
  await page.locator(".side-panel h2").first().click();
}

async function settled(page: Page): Promise<void> {
  await expect(page.locator(".save-state")).toHaveText("Saved");
  await expect(page.locator(".problems [role=status]")).not.toContainText("Checking");
}

async function drop(page: Page, type: string, x: number, y: number, id: string): Promise<void> {
  const pane = page.locator(".react-flow__pane");
  await page.getByRole("button", { name: type, exact: true }).dragTo(pane, {
    targetPosition: { x, y },
  });
  await expect(block(page, id)).toBeVisible();
  await settled(page);
}

async function rename(page: Page, from: string, to: string): Promise<void> {
  await block(page, from).click();
  await page.getByRole("textbox", { name: "Id" }).fill(to);
  await commit(page);
  await expect(block(page, to)).toBeVisible();
  await settled(page);
}

async function connect(page: Page, from: string, to: string): Promise<void> {
  const source = block(page, from).locator(".react-flow__handle.port.source");
  const target = block(page, to).locator(".react-flow__handle.port.target");
  await source.hover();
  await page.mouse.down();
  await target.hover();
  await page.mouse.up();
  await settled(page);
}

async function distribution(page: Page, mean: string): Promise<void> {
  await page.getByLabel("Distribution", { exact: true }).selectOption("exponential");
  await settled(page);
  await page.getByLabel("Unit of Mean").selectOption("min");
  await page.getByRole("textbox", { name: "Mean", exact: true }).fill(mean);
  await commit(page);
  await settled(page);
}

test("a coffee shop built by pointer equals the example except ui", async ({
  page,
  service,
  sent,
}) => {
  const pid = await openCanvas(page, service, "Coffee shop");

  await drop(page, "source", 140, 160, "source_1");
  await drop(page, "server", 380, 160, "server_1");
  await drop(page, "sink", 620, 160, "sink_1");
  // A new block holds only what the model needs: no settings until the user sets them.
  expect((await model(service, pid)).components.map((item) => item.params)).toEqual([{}, {}, {}]);

  await rename(page, "source_1", "arrivals");
  await distribution(page, "2");

  // The parameter, from the side panel with nothing selected.
  await page.locator(".react-flow__pane").click({ position: { x: 300, y: 30 } });
  const form = page.getByRole("form", { name: "Add parameter" });
  await form.getByRole("textbox", { name: "Id" }).fill("tills");
  await form.getByRole("combobox", { name: "Type" }).selectOption("integer");
  await form.getByRole("textbox", { name: "Value" }).fill("1");
  await form.getByRole("textbox", { name: "Min (optional)" }).fill("1");
  await form.getByRole("textbox", { name: "Max (optional)" }).fill("5");
  await form.getByRole("button", { name: "Add parameter" }).click();
  await settled(page);

  await rename(page, "server_1", "till");
  await page.getByRole("checkbox", { name: "Use parameter for Capacity" }).check();
  await page.getByRole("combobox", { name: "Parameter for Capacity" }).selectOption("tills");
  await settled(page);
  await distribution(page, "1.5");

  await rename(page, "sink_1", "exit");

  await connect(page, "arrivals", "till");
  await connect(page, "till", "exit");
  await expect(page.locator(".problems [role=status]")).toHaveText("No problems");
  await expect(page.getByRole("button", { name: "Run", exact: true })).not.toHaveAttribute(
    "aria-disabled",
    "true",
  );

  const saved = await model(service, pid);
  expect(saved.components.map(({ ui: _ui, ...rest }) => rest)).toEqual(example.components);
  expect(saved.connections).toEqual(example.connections);
  expect(saved.parameters).toEqual(example.parameters);

  // Every request went to a documented /v1 route (spec 3; AKS-121 checks the whole log).
  const routes = new Set(
    sent.map(
      (request) =>
        `${request.method} ${request.path
          .replace(/\/projects\/[0-9a-f-]{36}\//, "/projects/{pid}/")
          .replace(/\/schema\/components\/[a-z_]+$/, "/schema/components/{type}")}`,
    ),
  );
  expect(routes).toEqual(
    new Set([
      "GET /v1/settings",
      "GET /v1/projects",
      "GET /v1/templates",
      "GET /v1/schema",
      "GET /v1/schema/components/{type}",
      "GET /v1/projects/{pid}/model",
      "POST /v1/projects/{pid}/model/edits",
      "POST /v1/projects/{pid}/validate",
    ]),
  );
});

test("a renamed branch route can be connected by pointer, and its line is drawn", async ({
  page,
  service,
}) => {
  const pid = await openCanvas(page, service, "Routes");
  await drop(page, "branch", 160, 160, "branch_1");
  await drop(page, "sink", 520, 160, "sink_1");
  await block(page, "branch_1").click();
  const routes = page.getByRole("textbox", { name: "Routes" });
  await routes.fill("left, right");
  await routes.press("Enter");
  await settled(page);
  await expect(block(page, "branch_1").locator(".port.source")).toHaveCount(2);
  // The routes change after React Flow has measured the ports: "right" becomes "other".
  await routes.fill("left, other");
  await routes.press("Enter");
  await settled(page);
  const other = block(page, "branch_1").locator(
    '.react-flow__handle.source[data-handleid="other"]',
  );
  await expect(other).toBeVisible();
  const from = await other.boundingBox();
  const to = await block(page, "sink_1").locator(".react-flow__handle.port.target").boundingBox();
  if (from === null || to === null) throw new Error("no ports");
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 10 });
  await page.mouse.up();
  await settled(page);
  expect((await model(service, pid)).connections).toEqual([
    { from: "branch_1.other", to: "sink_1.in" },
  ]);
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
  await expect(page.locator(".react-flow__edge path.react-flow__edge-path")).toHaveAttribute(
    "d",
    /\d/,
  );
});

test("another client's write reloads the canvas; undo and redo write whole models", async ({
  page,
  service,
}) => {
  const pid = await openCanvas(page, service, "Shop");
  await drop(page, "server", 300, 160, "server_1");
  await expect(page.getByRole("button", { name: "Undo: add server_1" })).toBeEnabled();
  await page.getByRole("button", { name: "Undo: add server_1" }).click();
  await expect(block(page, "server_1")).toHaveCount(0);
  await settled(page);
  await page.getByRole("button", { name: "Redo: add server_1" }).click();
  await expect(block(page, "server_1")).toBeVisible();
  await settled(page);

  // A script's write arrives through the events socket; the canvas reloads and clears undo.
  const current = await service.api("GET", `/v1/projects/${pid}/model`);
  await service.api("POST", `/v1/projects/${pid}/model/edits`, {
    edits: [{ edit: "set_label", id: "server_1", label: "Barista" }],
    base_revision: (current.body as { revision: number }).revision,
  });
  await expect(block(page, "server_1")).toContainText("Barista");
  await expect(page.getByRole("button", { name: "Undo" })).toBeDisabled();
});

test("the canvas works from the keyboard", async ({ page, service }) => {
  const pid = await openCanvas(page, service, "Keys");
  await page.getByRole("button", { name: "source", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(block(page, "source_1")).toBeFocused();
  await settled(page);
  await page.getByRole("button", { name: "sink", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(block(page, "sink_1")).toBeFocused();
  await settled(page);

  // Connect with C on the selected source.
  await block(page, "source_1").focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("c");
  const dialog = page.getByRole("dialog", { name: "Connect source_1" });
  await dialog.getByRole("combobox", { name: "Goes to" }).selectOption("sink_1.in");
  await dialog.getByRole("button", { name: "Connect" }).click();
  await settled(page);
  expect((await model(service, pid)).connections).toEqual([
    { from: "source_1.out", to: "sink_1.in" },
  ]);

  // Arrow keys move the selection; a burst is one undo step.
  await block(page, "source_1").focus();
  const before = (await model(service, pid)).components[0]?.ui as { x: number; y: number };
  // One write at a time: each press waits for the last one to be saved, as a person's do
  // on a local service; a press during a write is not taken.
  const steps: [string, number, number][] = [
    ["ArrowRight", 8, 0],
    ["ArrowRight", 16, 0],
    ["Shift+ArrowDown", 16, 40],
  ];
  for (const [key, dx, dy] of steps) {
    await page.keyboard.press(key);
    await expect
      .poll(async () => (await model(service, pid)).components[0]?.ui)
      .toEqual({ x: before.x + dx, y: before.y + dy });
    await expect(page.locator(".save-state")).toHaveText("Saved");
  }
  await settled(page);
  await expect(page.getByRole("button", { name: "Undo: move source_1" })).toBeEnabled();

  // Delete asks first; focus starts on Cancel.
  await page.keyboard.press("Delete");
  const confirm = page.getByRole("dialog", { name: "Delete 1 block?" });
  await expect(confirm.getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(confirm.getByRole("button", { name: "Delete" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(block(page, "source_1")).toHaveCount(0);
  await settled(page);
  expect((await model(service, pid)).connections).toEqual([]);
  await page.keyboard.press("Control+z");
  await expect(block(page, "source_1")).toBeVisible();
  await settled(page);
  expect((await model(service, pid)).connections).toEqual([
    { from: "source_1.out", to: "sink_1.in" },
  ]);
});

test("a block cannot be dragged while a write awaits its answer", async ({ page, service }) => {
  const pid = await openCanvas(page, service, "Busy");
  await drop(page, "sink", 200, 160, "sink_1");
  await drop(page, "source", 420, 160, "source_1");
  const before = (await model(service, pid)).components[0]?.ui;
  // The service's answer to the next write waits until the test lets it through.
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/model/edits", async (route) => {
    await held;
    await route.continue();
  });
  await block(page, "source_1").click();
  await page.getByRole("textbox", { name: "Label (optional)" }).fill("Door");
  await commit(page);
  await expect(page.locator(".save-state")).toHaveText("Saving…");
  const box = await block(page, "sink_1").boundingBox();
  const other = await block(page, "source_1").boundingBox();
  if (box === null || other === null) throw new Error("the blocks are not drawn");
  const apart = async () => {
    const [a, b] = [
      await block(page, "sink_1").boundingBox(),
      await block(page, "source_1").boundingBox(),
    ];
    return a && b ? { x: Math.round(b.x - a.x), y: Math.round(b.y - a.y) } : null;
  };
  const start = await apart();
  await page.mouse.move(box.x + 40, box.y + 30);
  await page.mouse.down();
  await page.mouse.move(box.x + 140, box.y + 130, { steps: 8 });
  // The block does not follow the pointer (the view may pan; the blocks stay as they were).
  expect(await apart()).toEqual(start);
  await page.mouse.up();
  release();
  await settled(page);
  await page.unroute("**/model/edits");
  const after = await model(service, pid);
  expect(after.components[0]?.ui).toEqual(before);
  expect(after.components[1]).toMatchObject({ label: "Door" });
});

for (const scheme of ["light", "dark"] as const) {
  test(`the canvas meets WCAG 2.2 AA in the ${scheme} theme`, async ({ page, service }) => {
    await page.emulateMedia({ colorScheme: scheme });
    const pid = await openCanvas(page, service, "Coffee");
    const current = await service.api("GET", `/v1/projects/${pid}/model`);
    await service.api(
      "PUT",
      `/v1/projects/${pid}/model?base_revision=${(current.body as { revision: number }).revision}`,
      {
        ...example,
        components: [
          ...example.components.map((item, index) => ({ ...item, ui: { x: index * 240, y: 0 } })),
          { id: "server_2", type: "server", params: {}, ui: { x: 240, y: 160 } },
          { id: "staff", type: "resource_pool", params: { capacity: 2 }, ui: { x: 0, y: 160 } },
        ],
      },
    );
    await expect(block(page, "server_2")).toBeVisible();
    await settled(page);
    await expect(page.locator(".problem-row").first()).toBeVisible();
    expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
    await block(page, "till").click();
    await expect(page.getByRole("textbox", { name: "Id" })).toHaveValue("till");
    expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
    await block(page, "server_2").click();
    await page.keyboard.press("Delete");
    await expect(page.getByRole("dialog")).toBeVisible();
    expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
  });
}
