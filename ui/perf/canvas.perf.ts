/**
 * Spec 3 "Performance targets" (proposed): "Canvas stays responsive with 200 components: an
 * end-to-end test adds 200 components by API and selecting a block paints within 100 ms"
 * (AKS-121). Started by `tests/perf/test_interface.py`, which starts the service and passes
 * its address and token in `ITHAX_PERF_ORIGIN` and `ITHAX_PERF_TOKEN`, and reads what this
 * writes to `ITHAX_PERF_OUT`; not part of `npm run e2e`.
 *
 * The model is a source, 198 servers in a line and a sink (as spec 3's validation target
 * measures), written by API with `PUT .../model`, each block placed in a grid of 20 columns.
 * The Canvas opens on it (fitted to the view); then each of 12 drawn blocks, spread over
 * those drawn, is clicked in turn. One selection's time runs from the `pointerdown` event's
 * time stamp to the first frame painted after the block is drawn selected and the side
 * panel names it: the frame's `requestAnimationFrame` callback, then a message posted from
 * it, which the browser delivers after that frame has been painted.
 */
import { writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const ORIGIN = process.env.ITHAX_PERF_ORIGIN ?? "";
const TOKEN = process.env.ITHAX_PERF_TOKEN ?? "";
const OUT = process.env.ITHAX_PERF_OUT ?? "";
const SELECTIONS = 12;
const COLUMNS = 20;

async function api(method: string, path: string, body?: unknown): Promise<unknown> {
  const response = await fetch(ORIGIN + path, {
    method,
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  expect(response.status, `${method} ${path}`).toBeLessThan(300);
  return response.json();
}

function lineModel(components: number): Record<string, unknown> {
  const servers = Array.from({ length: components - 2 }, (_, index) => `s${index + 1}`);
  const names = ["arrivals", ...servers, "exit"];
  const at = (index: number) => ({
    x: (index % COLUMNS) * 224,
    y: Math.floor(index / COLUMNS) * 120,
  });
  return {
    format_version: "0.1",
    meta: { name: `${components} components` },
    domain: "process",
    parameters: {},
    components: [
      {
        id: "arrivals",
        type: "source",
        params: { interarrival: { dist: "exponential", mean: "2 min" } },
        ui: at(0),
      },
      ...servers.map((id, index) => ({
        id,
        type: "server",
        params: { capacity: 1, service: { dist: "exponential", mean: "1 min" } },
        ui: at(index + 1),
      })),
      { id: "exit", type: "sink", params: {}, ui: at(components - 1) },
    ],
    connections: names
      .slice(1)
      .map((to, index) => ({ from: `${names[index]}.out`, to: `${to}.in` })),
    experiments: [{ id: "base", length: "8 h", warmup: "0 s", replications: 30 }],
    run: { target: "local", fidelity: "standard" },
  };
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? (sorted[middle] ?? 0)
    : ((sorted[middle - 1] ?? 0) + (sorted[middle] ?? 0)) / 2;
}

test("selecting a block on a 200-component canvas paints within 100 ms", async ({
  page,
  browser,
}) => {
  test.setTimeout(180_000);
  expect(
    ORIGIN && TOKEN && OUT,
    "ITHAX_PERF_ORIGIN, ITHAX_PERF_TOKEN and ITHAX_PERF_OUT",
  ).toBeTruthy();
  await api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  const { id: pid } = (await api("POST", "/v1/projects", {
    name: "200 components",
    domain: "process",
  })) as { id: string };
  const model = lineModel(200);
  await api("PUT", `/v1/projects/${pid}/model`, model);

  const opening = Date.now();
  await page.goto(`${ORIGIN}/v1/ui/#token=${TOKEN}`);
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
  await page.evaluate((hash) => {
    window.location.hash = hash;
  }, `#/canvas/${pid}`);
  await expect(page.locator(".save-state")).toHaveText("Saved");
  await expect(page.locator(".problems [role=status]")).toHaveText("No problems", {
    timeout: 60_000,
  });
  const nodes = page.locator(".react-flow__node");
  await expect(nodes.first()).toBeVisible();
  const openMs = Date.now() - opening;
  const drawn = await nodes.evaluateAll((elements) =>
    elements.map((element) => element.getAttribute("data-id") ?? ""),
  );
  expect(drawn.length).toBeGreaterThanOrEqual(SELECTIONS);
  const chosen = Array.from(
    { length: SELECTIONS },
    (_, index) => drawn[Math.floor((index * drawn.length) / SELECTIONS)] ?? "",
  );

  await page.evaluate(() => {
    const state = window as unknown as { pressed: number };
    document.addEventListener(
      "pointerdown",
      (event) => {
        state.pressed = event.timeStamp;
      },
      true,
    );
  });
  const times: number[] = [];
  for (const id of chosen) {
    await page.evaluate((target) => {
      const state = window as unknown as { pressed: number; painted: Promise<number> };
      state.painted = new Promise((resolve) => {
        const shown = () => {
          const node = document.querySelector(`.react-flow__node[data-id="${target}"]`);
          const heading = document.getElementById("block-heading");
          return (
            node?.classList.contains("selected") === true &&
            heading?.textContent?.startsWith(`${target} `) === true
          );
        };
        const observer = new MutationObserver(() => {
          if (!shown()) return;
          observer.disconnect();
          requestAnimationFrame(() => {
            const channel = new MessageChannel();
            channel.port1.onmessage = () => resolve(performance.now() - state.pressed);
            channel.port2.postMessage(0);
          });
        });
        observer.observe(document.body, {
          subtree: true,
          childList: true,
          attributes: true,
          characterData: true,
        });
      });
    }, id);
    const box = await page.locator(`.react-flow__node[data-id="${id}"]`).boundingBox();
    expect(box, id).not.toBeNull();
    if (box === null) return;
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    times.push(
      await page.evaluate(() => (window as unknown as { painted: Promise<number> }).painted),
    );
    await expect(page.locator("#block-heading")).toContainText(id);
  }

  const result = {
    components: (model.components as unknown[]).length,
    drawn: drawn.length,
    open_ms: openMs,
    selected: chosen,
    selection_ms: times.map((time) => Math.round(time * 10) / 10),
    max_ms: Math.round(Math.max(...times) * 10) / 10,
    median_ms: Math.round(median(times) * 10) / 10,
    first_ms: Math.round((times[0] ?? 0) * 10) / 10,
    browser: `${browser.browserType().name()} ${browser.version()}`,
    viewport: page.viewportSize(),
  };
  writeFileSync(OUT, JSON.stringify(result, null, 2));
  expect(Math.max(...times)).toBeLessThan(100);
});
