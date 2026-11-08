/**
 * The first start against a real service: the launcher's address, the token taken from it,
 * the first-start notice shown once and remembered through `/v1/settings` (AKS-119).
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

test("the notice is shown once and remembered by the service", async ({
  page,
  service,
  outside,
}) => {
  await page.goto(service.url);
  const notice = page.getByRole("dialog", { name: "Welcome" });
  await expect(notice).toBeVisible();
  // The token left the address bar, and the history entry, as soon as the page took it.
  expect(page.url()).toBe(`${service.origin}/v1/ui/`);
  await expect(notice).toContainText("Results are estimates from a simulation.");
  await expect(notice).toContainText("GNU AGPL version 3");
  await expect(page.getByRole("button", { name: "Continue" })).toBeFocused();
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);

  await page.keyboard.press("Enter");
  await expect(notice).toBeHidden();
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
  await expect
    .poll(async () => {
      const { body } = await service.api("GET", "/v1/settings");
      return (body as { settings: { interface: { first_start_seen: boolean } } }).settings.interface
        .first_start_seen;
    })
    .toBe(true);

  // A reload of the tab keeps working without the token in the address, and the notice
  // is not shown again.
  await page.reload();
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(outside).toEqual([]);
});

test("the page without the token asks for the launcher", async ({ page, service }) => {
  await page.goto(`${service.origin}/v1/ui/`);
  await expect(page.getByRole("alert")).toContainText("python -m lcsim.launcher");
});

test("the interface's files carry a policy that keeps the page to the service", async ({
  service,
}) => {
  const response = await fetch(`${service.origin}/v1/ui/`);
  expect(response.status).toBe(200);
  const policy = response.headers.get("content-security-policy") ?? "";
  expect(policy).toContain("default-src 'self'");
  expect(policy).toContain(`connect-src 'self' ws://127.0.0.1:`);
  const notices = await (await fetch(`${service.origin}/v1/ui/THIRD-PARTY-NOTICES.txt`)).text();
  for (const font of ["bricolage-grotesque", "atkinson-hyperlegible-next", "jetbrains-mono"]) {
    expect(notices).toContain(`@fontsource-variable/${font} 5.3.0\nLicence: OFL-1.1`);
  }
  expect(await (await fetch(`${service.origin}/v1/ui/LICENSE.txt`)).text()).toContain(
    "GNU AFFERO GENERAL PUBLIC LICENSE",
  );
});
