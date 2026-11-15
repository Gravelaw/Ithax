/**
 * Recent projects against a real service (#97, Reviewer B finding 10): a lesson is resumed
 * at its step after a reload, in the same project, not a new copy; the project is renamed
 * and taken off the list, its folder kept.
 */
import { expect, test } from "./fixtures";

test("a lesson resumes at its step after a reload, in the same project", async ({
  page,
  service,
}) => {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  await page.goto(service.url);
  await page.getByRole("button", { name: "Start the lesson Coffee shop queue" }).click();
  const card = page.locator(".step-card");
  await expect(card).toContainText("Step 1 of 4");
  await card.getByRole("button", { name: "Next" }).click();
  await expect(card).toContainText("Step 2 of 4");
  await expect
    .poll(async () => {
      const listed = (await service.api("GET", "/v1/projects")).body as { lesson_step: number }[];
      return listed[0]?.lesson_step;
    })
    .toBe(1);

  // A reload ends the lesson in the interface; Home offers to resume it.
  await page.reload();
  await page.getByRole("button", { name: "Home", exact: true }).click();
  await page.getByRole("button", { name: "Resume the lesson Coffee shop queue" }).click();
  await expect(card).toContainText("Step 2 of 4");
  const projects = (await service.api("GET", "/v1/projects")).body as unknown[];
  expect(projects).toHaveLength(1);

  // Leaving the lesson clears its step.
  await card.getByRole("button", { name: "Exit lesson" }).click();
  await expect
    .poll(async () => {
      const listed = (await service.api("GET", "/v1/projects")).body as {
        lesson_step: number | null;
      }[];
      return listed[0]?.lesson_step;
    })
    .toBeNull();
});

test("a project is renamed and taken off the list, its folder kept", async ({ page, service }) => {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  const made = (await service.api("POST", "/v1/projects", { name: "Shop" })).body as {
    id: string;
    path: string;
  };
  await page.goto(service.url);
  const recent = page.getByRole("region", { name: "Recent projects" });
  await recent.getByRole("button", { name: "Rename Shop" }).click();
  await recent.getByRole("textbox", { name: "New name for Shop" }).fill("Corner café");
  await recent.getByRole("textbox", { name: "New name for Shop" }).press("Enter");
  await expect(recent.getByText("Corner café")).toBeVisible();
  await recent.getByRole("button", { name: "Remove Corner café from the list" }).click();
  await expect(recent.getByText("Corner café")).toHaveCount(0);
  const listed = (await service.api("GET", "/v1/projects")).body as unknown[];
  expect(listed).toEqual([]);
  // The folder is kept: opening it lists the project again, under its new name.
  const again = (await service.api("POST", "/v1/projects/open", { path: made.path })).body as {
    name: string;
  };
  expect(again.name).toBe("Corner café");
});
