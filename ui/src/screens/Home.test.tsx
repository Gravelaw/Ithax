import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../api/client";
import type { Project } from "../api/types";
import type { ProjectActions } from "../app/projectActions";
import { errorBody, FakeService, issue, ORIGIN, TOKEN } from "../test/fakes";
import {
  BUILD_UNAVAILABLE,
  EMPTY_GALLERY,
  Home,
  LESSON_UNREADABLE,
  NO_PROJECTS,
  REMOVED_KEEPS_FILES,
} from "./Home";

function project(id: string, name: string, available = true): Project {
  return {
    id,
    name: available ? name : null,
    created: available ? "2026-11-08T10:00:00Z" : null,
    layout_version: available ? 1 : null,
    model_revision: available ? 0 : null,
    path: `/data/projects/${id}`,
    available,
  };
}

/**
 * Home with the application's project actions: rename and remove sent to `client` as App
 * sends them, open and lesson as the test gives them.
 */
function actions(client: ApiClient, given: Partial<ProjectActions> = {}): ProjectActions {
  return {
    open: () => {},
    lesson: () => {},
    rename: (target, name) => client.changeProject(target.id, { name }),
    remove: (target) => client.removeProject(target.id),
    ...given,
  };
}

function renderHome(client: ApiClient, given: Partial<ProjectActions> = {}, onBuild?: () => void) {
  return render(<Home client={client} projects={actions(client, given)} onBuild={onBuild} />);
}

function service(projects: Project[] = [], templates: unknown[] = []) {
  return new FakeService()
    .answer("GET /v1/projects", projects)
    .answer("GET /v1/templates", templates);
}

describe("Home", () => {
  it("lists recent projects, newest registered first", async () => {
    const fake = service([project("a", "First"), project("b", "Second")]);
    renderHome(fake.client());
    const recent = await screen.findByRole("region", { name: "Recent projects" });
    await within(recent).findByText("Second");
    const names = within(recent)
      .getAllByRole("button")
      .map((button) => button.querySelector(".subheading")?.textContent)
      .filter(Boolean);
    expect(names).toEqual(["Second", "First"]);
    expect(within(recent).getAllByText("Created 8 Nov 2026")).toHaveLength(2);
    expect(within(recent).getByText("/data/projects/a")).toBeInTheDocument();
  });

  it("opens a project, but not one that is not available", async () => {
    const onOpen = vi.fn();
    const fake = service([project("a", "Shop"), project("b", "", false)]);
    renderHome(fake.client(), { open: onOpen });
    await userEvent.click(await screen.findByText("/data/projects/b", { selector: ".subheading" }));
    expect(onOpen).not.toHaveBeenCalled();
    expect(screen.getByText("Not available")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Shop"));
    expect(onOpen).toHaveBeenCalledWith(project("a", "Shop"));
  });

  it("says when there are no projects and no templates", async () => {
    renderHome(service().client());
    expect(await screen.findByText(NO_PROJECTS)).toBeInTheDocument();
    expect(await screen.findByText(EMPTY_GALLERY)).toBeInTheDocument();
  });

  it("shows the Learn and Build entries, Build unavailable with its reason", async () => {
    renderHome(service().client());
    await screen.findByText(EMPTY_GALLERY);
    const build = screen.getByRole("button", { name: /^Build/ });
    expect(build).toHaveAttribute("aria-disabled", "true");
    expect(build).toHaveAccessibleDescription(BUILD_UNAVAILABLE);
    expect(screen.getByText(BUILD_UNAVAILABLE)).toBeVisible();
  });

  it("Learn goes to the template gallery, lessons for students first", async () => {
    const templates = [
      { id: "mix", title: "Product mix", audience: "Business", minutes: 20 },
      { id: "shop", title: "Coffee shop queue", audience: "Students", minutes: 15 },
      { id: "x", title: "Other" },
    ];
    renderHome(service([], templates).client());
    await screen.findByText("Product mix");
    // None of these ids is one the Build form opens, so Build stays unavailable.
    expect(screen.getByRole("button", { name: /^Build/ })).toHaveAccessibleDescription(
      BUILD_UNAVAILABLE,
    );
    await userEvent.click(screen.getByRole("button", { name: /^Learn/ }));
    expect(screen.getByRole("heading", { name: "Templates" })).toHaveFocus();
    const titles = within(screen.getByRole("list", { name: "Templates" }))
      .getAllByRole("listitem")
      .map((item) => item.querySelector(".subheading")?.textContent);
    expect(titles).toEqual(["Coffee shop queue", "Product mix", "Other"]);
    expect(screen.getByText("Students · 15 min")).toBeInTheDocument();
  });

  it("opens the Build form when the service serves one of its templates", async () => {
    const onBuild = vi.fn();
    const templates = [{ id: "coffee_shop", title: "Coffee shop queue" }];
    renderHome(service([], templates).client(), {}, onBuild);
    await screen.findByText("Coffee shop queue");
    const build = screen.getByRole("button", { name: /^Build/ });
    expect(build).not.toHaveAttribute("aria-disabled");
    expect(screen.queryByText(BUILD_UNAVAILABLE)).toBeNull();
    await userEvent.click(build);
    expect(onBuild).toHaveBeenCalledTimes(1);
  });

  it("orders by last opened, and says when each was opened (#97)", async () => {
    const opened = (id: string, name: string, at: string | null): Project => ({
      ...project(id, name),
      opened: at,
    });
    const fake = service([
      opened("a", "Old", "2026-11-09T10:00:00Z"),
      opened("b", "Never opened", null),
      opened("c", "Newest", "2026-11-12T10:00:00Z"),
    ]);
    renderHome(fake.client());
    const recent = await screen.findByRole("region", { name: "Recent projects" });
    await within(recent).findByText("Newest");
    const names = [...recent.querySelectorAll(".project .subheading")].map((n) => n.textContent);
    expect(names).toEqual(["Newest", "Old", "Never opened"]);
    expect(within(recent).getByText(/^Last opened 12 Nov 2026/)).toBeVisible();
  });

  it("hands an opened project to onOpen, which notes the time (#97)", async () => {
    const onOpen = vi.fn();
    const fake = service([project("a", "Shop")]);
    renderHome(fake.client(), { open: onOpen });
    await userEvent.click(await screen.findByText("Shop"));
    expect(onOpen).toHaveBeenCalledWith(project("a", "Shop"));
  });

  it("renames a project and takes one off the list, keeping its files (#97)", async () => {
    const fake = service([project("a", "Shop"), project("b", "Spare")])
      .answer("PATCH /v1/projects/a", { ...project("a", "Corner café") })
      .answer("POST /v1/projects/b/remove", { id: "b", path: "/data/projects/b" });
    renderHome(fake.client());
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Rename Shop" }));
    const box = screen.getByRole("textbox", { name: "New name for Shop" });
    await user.clear(box);
    await user.type(box, "Corner café{Enter}");
    await waitFor(() =>
      expect(fake.requested("PATCH", "/v1/projects/a")[0]?.body).toEqual({ name: "Corner café" }),
    );
    await user.click(screen.getByRole("button", { name: "Remove Spare from the list" }));
    await waitFor(() => expect(fake.requested("POST", "/v1/projects/b/remove")).toHaveLength(1));
    expect(await screen.findByText(REMOVED_KEEPS_FILES)).toBeVisible();
  });

  it("starts a lesson in the project already made from its template, at its step (#97)", async () => {
    const onLesson = vi.fn();
    const shop = { id: "coffee_shop", title: "Coffee shop queue", summary: "Customers wait." };
    const lesson =
      "# Coffee shop queue\n\n## Arrive\n\nComponent: `arrivals`\n\nThey arrive.\n\n" +
      "## Exercise: two tills\n\nComponent: `till`\n\n### Change\n\nSet it.\n\n" +
      "### Prediction\n\n- [x] Less.\n- [ ] More.\n\n### Explanation\n\nBecause.\n";
    const earlier: Project = {
      ...project("made", "Coffee shop queue"),
      template: "coffee_shop",
      lesson_step: 1,
    };
    const fake = service([earlier], [shop])
      .answer("GET /v1/templates/coffee_shop", { template: shop, lesson, expected: [] })
      .answer("PATCH /v1/projects/made", earlier);
    renderHome(fake.client(), { lesson: onLesson });
    // The card offers to resume, in place of starting a new project (#97).
    const resume = await screen.findByRole("button", {
      name: "Resume the lesson Coffee shop queue",
    });
    expect(screen.queryByRole("button", { name: "Start the lesson Coffee shop queue" })).toBeNull();
    await userEvent.click(resume);
    await waitFor(() => expect(onLesson).toHaveBeenCalledTimes(1));
    const [made, , , step] = onLesson.mock.calls[0] ?? [];
    expect(made).toEqual(earlier);
    expect(step).toBe(1);
    expect(fake.requested("POST", "/v1/projects")).toHaveLength(0);
  });

  it("starts a lesson: the template first, then a project named after it", async () => {
    const onLesson = vi.fn();
    const shop = { id: "coffee_shop", title: "Coffee shop queue", summary: "Customers wait." };
    const lesson =
      "# Coffee shop queue\n\n## Arrive\n\nComponent: `arrivals`\n\nThey arrive.\n\n" +
      "## Exercise: two tills\n\nComponent: `till`\n\n### Change\n\nSet it.\n\n" +
      "### Prediction\n\n- [x] Less.\n- [ ] More.\n\n### Explanation\n\nBecause.\n";
    const created = project("made", "Coffee shop queue");
    const fake = service([], [shop])
      .answer("GET /v1/templates/coffee_shop", { template: shop, lesson, expected: [] })
      .answer("POST /v1/projects", created);
    renderHome(fake.client(), { lesson: onLesson });
    expect(await screen.findByText("Customers wait.")).toBeVisible();
    const start = screen.getByRole("button", { name: "Start the lesson Coffee shop queue" });
    const release = fake.holdWrites();
    await userEvent.click(start);
    await waitFor(() => expect(fake.held).toBe(1));
    // One lesson starts at a time: a press meanwhile sends nothing.
    expect(start).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("status")).toHaveTextContent("Starting the lesson…");
    await userEvent.click(start);
    release();
    await waitFor(() => expect(onLesson).toHaveBeenCalledTimes(1));
    const [made, template, read] = onLesson.mock.calls[0] ?? [];
    expect(made).toEqual(created);
    expect(template).toEqual(shop);
    expect(read.steps.map((step: { component: string }) => step.component)).toEqual(["arrivals"]);
    expect(read.exercise.choices).toHaveLength(2);
    expect(fake.requests.map((request) => `${request.method} ${request.path}`)).toEqual([
      "GET /v1/projects",
      "GET /v1/templates",
      "GET /v1/templates/coffee_shop",
      "POST /v1/projects",
    ]);
    expect(fake.requested("POST", "/v1/projects")[0]?.body).toEqual({
      name: "Coffee shop queue",
      template: "coffee_shop",
    });
  });

  it("does nothing with answers that arrive after Home was left", async () => {
    const onLesson = vi.fn();
    const shop = { id: "coffee_shop", title: "Coffee shop queue" };
    const lesson =
      "# T\n## A\nComponent: `a`\nText\n## Exercise: x\nComponent: `a`\n### Change\nc\n" +
      "### Prediction\n- [x] y\n- [ ] n\n### Explanation\ne\n";
    const fake = service([], [shop])
      .answer("GET /v1/templates/coffee_shop", { template: shop, lesson, expected: [] })
      .answer("POST /v1/projects", project("made", "Coffee shop queue"));
    const shown = renderHome(fake.client(), { lesson: onLesson });
    const release = fake.holdWrites();
    await userEvent.click(
      await screen.findByRole("button", { name: "Start the lesson Coffee shop queue" }),
    );
    await waitFor(() => expect(fake.held).toBe(1));
    shown.unmount();
    release();
    await waitFor(() => expect(fake.requested("POST", "/v1/projects")).toHaveLength(1));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(onLesson).not.toHaveBeenCalled();
  });

  it("makes no project when the template cannot be read, and shows the service's issue", async () => {
    const onLesson = vi.fn();
    const shop = { id: "coffee_shop", title: "Coffee shop queue" };
    const fake = service([], [shop]).answer(
      "GET /v1/templates/coffee_shop",
      errorBody("E185", "There is no template 'coffee_shop'."),
      404,
    );
    renderHome(fake.client(), { lesson: onLesson });
    await userEvent.click(
      await screen.findByRole("button", { name: "Start the lesson Coffee shop queue" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "E185 There is no template 'coffee_shop'.",
    );
    expect(fake.requested("POST", "/v1/projects")).toHaveLength(0);
    expect(onLesson).not.toHaveBeenCalled();
  });

  it("says when a lesson does not read, and when the project is refused", async () => {
    const onLesson = vi.fn();
    const shop = { id: "coffee_shop", title: "Coffee shop queue" };
    const good =
      "# T\n## A\nComponent: `a`\nText\n## Exercise: x\nComponent: `a`\n### Change\nc\n" +
      "### Prediction\n- [x] y\n- [ ] n\n### Explanation\ne\n";
    let lesson = "not a lesson";
    const fake = service([], [shop])
      .on("GET /v1/templates/coffee_shop", () => ({
        status: 200,
        body: { template: shop, lesson, expected: [] },
      }))
      .answer("POST /v1/projects", errorBody("E186", "The folder cannot be written."), 400);
    renderHome(fake.client(), { lesson: onLesson });
    const start = await screen.findByRole("button", { name: "Start the lesson Coffee shop queue" });
    await userEvent.click(start);
    expect(await screen.findByRole("alert")).toHaveTextContent(LESSON_UNREADABLE);
    expect(fake.requested("POST", "/v1/projects")).toHaveLength(0);
    lesson = good;
    await userEvent.click(start);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "E186 The folder cannot be written.",
    );
    expect(screen.queryByText(LESSON_UNREADABLE)).toBeNull();
    expect(onLesson).not.toHaveBeenCalled();
  });

  it("says contact was lost when the projects cannot be listed, and tries again", async () => {
    let answered = false;
    const fake = service().on("GET /v1/projects", () => {
      if (answered) return { status: 200, body: [] };
      answered = true;
      return "unreachable";
    });
    fake.on("GET /v1/templates", () => "unreachable");
    renderHome(fake.client());
    expect(await screen.findAllByText("Lost contact with the engine service.")).toHaveLength(2);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(NO_PROJECTS)).toBeInTheDocument();
  });

  it("creates an empty project of the kind chosen", async () => {
    const onOpen = vi.fn();
    const created = project("new", "Plan A");
    const fake = service().answer("POST /v1/projects", created);
    renderHome(fake.client(), { open: onOpen });
    await userEvent.click(await screen.findByRole("button", { name: "New empty project" }));
    const dialog = screen.getByRole("dialog", { name: "New empty project" });
    expect(within(dialog).getByRole("textbox", { name: "Name" })).toHaveFocus();
    const process = within(dialog).getByRole("radio", { name: /Process \(flows and queues\)/ });
    expect(process).toBeChecked();
    await userEvent.type(within(dialog).getByRole("textbox", { name: "Name" }), "Plan A");
    await userEvent.click(
      within(dialog).getByRole("radio", { name: /Plan \(decisions and limits\)/ }),
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Create" }));
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith(created));
    expect(fake.requested("POST", "/v1/projects")[0]?.body).toEqual({
      name: "Plan A",
      domain: "optimization",
    });
  });

  it("sends one creation however often Create is pressed while it is pending", async () => {
    const onOpen = vi.fn();
    const created = project("one", "Once");
    let release: (response: Response) => void = () => {};
    const fake = service();
    const posts: string[] = [];
    const client = new ApiClient({
      origin: ORIGIN,
      token: TOKEN,
      fetch: (input, init) => {
        if (init?.method === "POST") {
          posts.push(String(input));
          return new Promise<Response>((resolve) => {
            release = resolve;
          });
        }
        return fake.fetch(input, init);
      },
    });
    renderHome(client, { open: onOpen });
    await userEvent.click(await screen.findByRole("button", { name: "New empty project" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Once");
    const create = screen.getByRole("button", { name: "Create" });
    await userEvent.click(create);
    await userEvent.click(create);
    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "{Enter}");
    expect(posts).toHaveLength(1);
    expect(create).toHaveAttribute("aria-disabled", "true");
    release(new Response(JSON.stringify(created), { status: 200 }));
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith(created));
    expect(posts).toHaveLength(1);
  });

  it("sends one open however often Open is pressed while it is pending", async () => {
    let release: (response: Response) => void = () => {};
    const fake = service();
    const posts: string[] = [];
    const client = new ApiClient({
      origin: ORIGIN,
      token: TOKEN,
      fetch: (input, init) => {
        if (init?.method === "POST") {
          posts.push(String(input));
          return new Promise<Response>((resolve) => {
            release = resolve;
          });
        }
        return fake.fetch(input, init);
      },
    });
    renderHome(client);
    await userEvent.click(await screen.findByRole("button", { name: "Open a project folder" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Folder" }), "/x");
    const open = screen.getByRole("button", { name: "Open" });
    await userEvent.click(open);
    await userEvent.click(open);
    expect(posts).toHaveLength(1);
    expect(open).toHaveAttribute("aria-disabled", "true");
    release(
      new Response(JSON.stringify(errorBody("E185", "There is no folder '/x'.")), { status: 404 }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("E185");
    expect(open).not.toHaveAttribute("aria-disabled");
  });

  it("shows the service's issues when it refuses the new project", async () => {
    const onOpen = vi.fn();
    const refusal = errorBody("E184", "The request field 'name' is empty.", [
      issue(
        "E184",
        "The request field 'name' is empty.",
        "/name",
        "Give it at least one character.",
      ),
    ]);
    const fake = service().answer("POST /v1/projects", refusal, 400);
    renderHome(fake.client(), { open: onOpen });
    await userEvent.click(await screen.findByRole("button", { name: "New empty project" }));
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("E184 The request field 'name' is empty.");
    expect(alert).toHaveTextContent("Give it at least one character.");
    expect(onOpen).not.toHaveBeenCalled();
    expect(fake.requested("POST", "/v1/projects")[0]?.body).toEqual({
      name: "",
      domain: "process",
    });
  });

  it("cancels the new project with Cancel or Escape, giving focus back", async () => {
    renderHome(service().client());
    const link = await screen.findByRole("button", { name: "New empty project" });
    await userEvent.click(link);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(link).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens a project folder by its path", async () => {
    const onOpen = vi.fn();
    const opened = project("o", "Opened");
    const fake = service().answer("POST /v1/projects/open", opened);
    renderHome(fake.client(), { open: onOpen });
    await userEvent.click(await screen.findByRole("button", { name: "Open a project folder" }));
    const field = screen.getByRole("textbox", { name: "Folder" });
    expect(field).toHaveAccessibleDescription(
      "The full path of a folder that holds a project.json.",
    );
    await userEvent.type(field, "/home/me/shop");
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith(opened));
    expect(fake.requested("POST", "/v1/projects/open")[0]?.body).toEqual({ path: "/home/me/shop" });
  });

  it("shows the service's error when the folder cannot be opened, and cancels", async () => {
    const fake = service().answer(
      "POST /v1/projects/open",
      errorBody("E185", "There is no folder '/nowhere'."),
      404,
    );
    renderHome(fake.client());
    await userEvent.click(await screen.findByRole("button", { name: "Open a project folder" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Folder" }), "/nowhere");
    await userEvent.keyboard("{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "E185 There is no folder '/nowhere'.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
