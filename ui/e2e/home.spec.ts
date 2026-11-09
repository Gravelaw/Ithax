/**
 * Home against a real service: recent projects, a new Process or Plan project, opening a
 * folder, the template gallery, the Learn and Build entries; every request with the
 * token and `X-Client: ui`, the WebSocket from the interface's own origin, nothing fetched
 * from outside, and WCAG 2.2 AA in both themes (AKS-119).
 */
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import type { Service } from "./service";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function home(page: Page, service: Service): Promise<void> {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  await page.goto(service.url);
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
}

async function create(page: Page, name: string, kind: RegExp): Promise<string> {
  await page.getByRole("button", { name: "New empty project" }).click();
  const dialog = page.getByRole("dialog", { name: "New empty project" });
  await dialog.getByRole("textbox", { name: "Name" }).fill(name);
  await dialog.getByRole("radio", { name: kind }).check();
  await dialog.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("heading", { name: "Canvas" })).toBeAttached();
  await expect(page.getByRole("banner")).toContainText(name);
  return decodeURIComponent(new URL(page.url()).hash.split("/").pop() ?? "");
}

test("Home creates Process and Plan projects and lists them", async ({
  page,
  service,
  sent,
  outside,
}) => {
  await home(page, service);
  await expect(page.getByText("No projects yet.")).toBeVisible();
  // The service serves the repository's ten templates (AKS-122, AKS-139, AKS-123,
  // AKS-140), so the gallery lists them in id order, each with "Start the lesson", and
  // Build is available (AKS-124; `e2e/learn.spec.ts` and `e2e/build.spec.ts` use them).
  const gallery = page.getByRole("list", { name: "Templates" });
  await expect(gallery.locator(".card .subheading")).toHaveText([
    "Clinic patient flow",
    "Coffee shop queue",
    "How many machines?",
    "Inventory reorder point",
    "Machine breakdowns",
    "Product mix",
    "Staff rota",
    "Three-machine production line",
    "Transport plan",
    "Warehouse pick and pack",
  ]);
  await expect(gallery.getByRole("button", { name: /^Start the lesson/ })).toHaveCount(10);
  const build = page.getByRole("button", { name: /^Build/ });
  await expect(build).not.toHaveAttribute("aria-disabled", "true");
  await page.getByRole("button", { name: /^Learn/ }).click();
  await expect(page.getByRole("heading", { name: "Templates" })).toBeFocused();

  const process = await create(page, "Coffee", /Process/);
  const processModel = await service.api("GET", `/v1/projects/${process}/model`);
  expect((processModel.body as { model: { domain: string } }).model.domain).toBe("process");

  await page.getByRole("button", { name: "Home" }).click();
  const plan = await create(page, "Mix", /Plan/);
  const planModel = await service.api("GET", `/v1/projects/${plan}/model`);
  expect((planModel.body as { model: { domain: string } }).model.domain).toBe("optimization");

  await page.getByRole("button", { name: "Home" }).click();
  const recent = page.getByRole("region", { name: "Recent projects" });
  await expect(recent.locator(".project .subheading")).toHaveText(["Mix", "Coffee"]);
  await recent.getByText("Coffee").click();
  await expect(page.getByRole("banner")).toContainText("Coffee");

  // Every request the interface made is a documented /v1 route with the token and
  // X-Client: ui (spec 3 "Service rules").
  expect(sent.length).toBeGreaterThan(5);
  for (const request of sent) {
    expect(request.headers.authorization, request.path).toBe(`Bearer ${service.token}`);
    expect(request.headers["x-client"], request.path).toBe("ui");
  }
  expect(
    new Set(
      sent.map(
        (request) =>
          `${request.method} ${request.path.replace(/\/projects\/[0-9a-f-]{36}\//, "/projects/{pid}/")}`,
      ),
    ),
  ).toEqual(
    new Set([
      "GET /v1/settings",
      "GET /v1/projects",
      "GET /v1/templates",
      "POST /v1/projects",
      // The Canvas opens each project: its model, the component types, a validation.
      "GET /v1/schema",
      "GET /v1/projects/{pid}/model",
      "POST /v1/projects/{pid}/validate",
    ]),
  );
  expect(outside).toEqual([]);
});

test("Home opens a project folder, and shows the service's refusal", async ({ page, service }) => {
  const made = await service.api("POST", "/v1/projects", { name: "Line" });
  const folder = (made.body as { path: string }).path;
  await home(page, service);
  await page.getByRole("button", { name: "Open a project folder" }).click();
  const dialog = page.getByRole("dialog", { name: "Open a project folder" });
  await dialog.getByRole("textbox", { name: "Folder" }).fill(`${folder}-missing`);
  await dialog.getByRole("button", { name: "Open" }).click();
  // The service's own issue, as it wrote it.
  await expect(dialog.getByRole("alert")).toContainText("E185");
  await dialog.getByRole("textbox", { name: "Folder" }).fill(folder);
  await dialog.getByRole("button", { name: "Open" }).click();
  await expect(page.locator(".save-state")).toHaveText("Saved");
  await expect(page.getByRole("banner")).toContainText("Line");
});

test("Home works from the keyboard alone", async ({ page, service }) => {
  await home(page, service);
  await page.keyboard.press("F6");
  await expect(page.getByRole("button", { name: "Home" })).toBeFocused();
  for (let presses = 0; presses < 20; presses += 1) {
    if (
      await page
        .getByRole("button", { name: "New empty project" })
        .evaluate((b) => b === document.activeElement)
    )
      break;
    await page.keyboard.press("Tab");
  }
  await expect(page.getByRole("button", { name: "New empty project" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("textbox", { name: "Name" })).toBeFocused();
  await page.keyboard.type("By keys");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("radio", { name: /Process/ })).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("radio", { name: /Plan/ })).toBeChecked();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Canvas" })).toBeAttached();
  await page.keyboard.press("F6");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
});

for (const scheme of ["light", "dark"] as const) {
  test(`Home meets WCAG 2.2 AA in the ${scheme} theme`, async ({ page, service }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await service.api("POST", "/v1/projects", { name: "Shop" });
    await home(page, service);
    await expect(page.locator(".project")).toHaveCount(1);
    expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
    await page.getByRole("button", { name: "New empty project" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
  });
}
