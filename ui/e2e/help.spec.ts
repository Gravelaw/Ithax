/**
 * Help, "Open source licences" against a real service and the built interface (issue 89):
 * reached from Settings, About, it lists the engines, the Python packages and the
 * interface's npm packages with their licences and authors, and meets WCAG 2.2 AA in both
 * themes.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

for (const scheme of ["light", "dark"] as const) {
  test(`Help lists every package and engine, in the ${scheme} theme`, async ({ page, service }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
    await page.goto(service.url);
    await page
      .getByRole("navigation", { name: "Screens" })
      .getByRole("button", { name: "Settings" })
      .click();
    await page.getByRole("link", { name: "Open source licences" }).click();
    await expect(page.getByRole("heading", { name: "Help", level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "Settings" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    const engines = page.getByRole("table", { name: "Engines" });
    await expect(
      engines.getByRole("row", { name: /^highs .* MIT HiGHS developers$/ }),
    ).toBeVisible();
    await expect(engines.getByRole("rowheader", { name: "simpy" })).toBeVisible();
    const packages = page.getByRole("table", { name: "Python packages" });
    await expect(packages.getByRole("row", { name: /^numpy .* BSD-3-Clause/ })).toBeVisible();
    const npm = page.getByRole("table", { name: "Interface packages" });
    await expect(npm.getByRole("rowheader", { name: "react", exact: true })).toBeVisible();
    await expect(npm.getByRole("rowheader", { name: "echarts", exact: true })).toBeVisible();
    expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
  });
}
