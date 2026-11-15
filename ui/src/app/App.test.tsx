import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Settings } from "../api/types";
import { LOST_CONTACT } from "../components/ServiceProblem";
import { NOTICE_TEXT } from "../screens/FirstStartNotice";
import { NO_PROJECTS, PROJECTS_BUSY } from "../screens/Home";
import { ModelService } from "../test/fakeModel";
import { errorBody, SETTINGS, startedService } from "../test/fakes";
import { OPENED_UNSAVED, STEP_UNSAVED } from "./App";
import { Boot, CONNECTING, NO_TOKEN, NOT_ANSWERING, NoToken } from "./Boot";

function boot(settings: Settings = SETTINGS) {
  const fake = startedService(settings);
  const root = document.createElement("html");
  render(<Boot client={fake.client()} root={root} />);
  return { fake, root };
}

const seen = { ...SETTINGS, interface: { ...SETTINGS.interface, first_start_seen: true } };

/**
 * A service holding two projects made from the coffee shop template, its lesson, and the
 * notes the interface writes, as the service keeps them.
 */
function projectService() {
  const shop = { id: "coffee_shop", title: "Coffee shop queue", experiment: "base" };
  const lesson =
    "# Coffee shop queue\n\n## Arrive\n\nComponent: `arrivals`\n\nThey arrive.\n\n" +
    "## Queue\n\nComponent: `line`\n\nThey wait.\n\n" +
    "## Exercise: two tills\n\nComponent: `till`\n\n### Change\n\nSet it.\n\n" +
    "### Prediction\n\n- [x] Less.\n- [ ] More.\n\n### Explanation\n\nBecause.\n";
  const made = (id: string, opened: string) => ({
    id,
    name: `Shop ${id}`,
    created: "2026-11-09T10:00:00Z",
    layout_version: 1,
    model_revision: 0,
    path: `/${id}`,
    available: true,
    template: "coffee_shop",
    opened,
    lesson_step: null as number | null,
  });
  let listed = [made("p1", "2026-11-15T10:00:00Z"), made("p2", "2026-11-15T09:00:00Z")];
  window.location.hash = "#/";
  const { fake } = boot(seen);
  new ModelService(fake);
  new ModelService(fake, { pid: "p2" });
  fake
    .answer("GET /v1/templates", [shop])
    .answer("GET /v1/templates/coffee_shop", { template: shop, lesson, expected: [] })
    .on("GET /v1/projects", () => ({ status: 200, body: listed }));
  for (const id of ["p1", "p2"]) {
    fake
      .on(`PATCH /v1/projects/${id}`, (body) => {
        listed = listed.map((item) =>
          item.id === id ? { ...item, ...(body as Record<string, unknown>) } : item,
        );
        return { status: 200, body: listed.find((item) => item.id === id) };
      })
      .on(`POST /v1/projects/${id}/remove`, () => {
        listed = listed.filter((item) => item.id !== id);
        return { status: 200, body: { id, path: `/${id}` } };
      });
  }
  // The project requests in the order sent (the template gallery's are left out).
  const order = () =>
    fake.requests
      .filter((request) => !request.path.startsWith("/v1/templates"))
      .map((request) => `${request.method} ${request.path}`);
  return { fake, order, listed: () => listed };
}

describe("project actions, one at a time (reviews of pull request 201)", () => {
  it("does not remove a project while its lesson is resuming", async () => {
    const { fake, listed } = projectService();
    const letTemplate = fake.hold("GET /v1/templates/coffee_shop");
    await userEvent.click(
      await screen.findByRole("button", { name: "Resume the lesson Coffee shop queue" }),
    );
    await waitFor(() => expect(fake.heldOn("GET /v1/templates/coffee_shop")).toBe(1));
    // Removing the project being resumed conflicts with it: the button waits, and says why.
    const remove = screen.getByRole("button", { name: "Remove Shop p1 from the list" });
    expect(remove).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText(PROJECTS_BUSY)).toBeVisible();
    await userEvent.click(remove);
    letTemplate();
    expect(await screen.findByRole("region", { name: "Arrive" })).toBeVisible();
    expect(window.location.hash).toBe("#/canvas/p1");
    expect(fake.requested("POST", "/v1/projects/p1/remove")).toHaveLength(0);
    expect(listed().map((item) => item.id)).toEqual(["p1", "p2"]);
  });

  it("renames one at a time, so the name shown is the last one given", async () => {
    const { fake, order } = projectService();
    await userEvent.click(await screen.findByRole("button", { name: "Rename Shop p1" }));
    const letRename = fake.hold("PATCH /v1/projects/p1");
    await userEvent.type(
      screen.getByRole("textbox", { name: "New name for Shop p1" }),
      " A{Enter}",
    );
    await waitFor(() => expect(fake.heldOn("PATCH /v1/projects/p1")).toBe(1));
    // A second rename waits while the first awaits its answer.
    expect(screen.getByRole("button", { name: "Rename Shop p2" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    letRename();
    expect(await screen.findByRole("button", { name: "Rename Shop p1 A" })).toBeVisible();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Rename Shop p1 A" })).not.toHaveAttribute(
        "aria-disabled",
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Rename Shop p1 A" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "New name for Shop p1 A" }),
      "{Backspace}B{Enter}",
    );
    expect(await screen.findByRole("button", { name: "Rename Shop p1 B" })).toBeVisible();
    // Each rename's list is read after it, never while it is in flight.
    const patches = order().flatMap((route, at) => (route === "PATCH /v1/projects/p1" ? [at] : []));
    for (const at of patches) expect(order()[at + 1]).toBe("GET /v1/projects");
  });

  it("reads the project list only after the removal before it, so a removed project stays off", async () => {
    const { fake, order } = projectService();
    const letRemove = fake.hold("POST /v1/projects/p1/remove");
    await userEvent.click(
      await screen.findByRole("button", { name: "Remove Shop p1 from the list" }),
    );
    await waitFor(() => expect(fake.heldOn("POST /v1/projects/p1/remove")).toBe(1));
    expect(screen.getByRole("button", { name: "Remove Shop p2 from the list" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    letRemove();
    await waitFor(() => expect(screen.queryByText("/p1")).toBeNull());
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Remove Shop p2 from the list" }),
      ).not.toHaveAttribute("aria-disabled"),
    );
    await userEvent.click(screen.getByRole("button", { name: "Remove Shop p2 from the list" }));
    expect(await screen.findByText(NO_PROJECTS)).toBeVisible();
    const removal = order().indexOf("POST /v1/projects/p1/remove");
    expect(order().slice(removal + 1)).toEqual([
      "GET /v1/projects",
      "POST /v1/projects/p2/remove",
      "GET /v1/projects",
    ]);
  });

  it.each([
    ["the place reached in a lesson", "lesson_step", STEP_UNSAVED],
    ["the time a project was opened", "opened", OPENED_UNSAVED],
  ])("shows %s when it is not saved, and saves it with Try again", async (_what, field, said) => {
    const { fake } = projectService();
    let refuse = true;
    const sent: unknown[] = [];
    fake.on("PATCH /v1/projects/p1", (body) => {
      const change = body as Record<string, unknown>;
      if (field in change) sent.push(change[field]);
      return refuse && field in change
        ? { status: 503, body: errorBody("E900", "The service did not save it.") }
        : { status: 200, body: { id: "p1" } };
    });
    await userEvent.click(
      await screen.findByRole("button", { name: "Resume the lesson Coffee shop queue" }),
    );
    expect(await screen.findByRole("region", { name: "Arrive" })).toBeVisible();
    if (field === "lesson_step")
      await userEvent.click(screen.getByRole("button", { name: "Next" }));
    // The refused write is said, never taken as saved.
    expect(await screen.findByText(said)).toBeVisible();
    const tries = sent.length;
    refuse = false;
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.queryByText(said)).toBeNull());
    expect(sent.length).toBe(tries + 1);
    expect(sent.at(-1)).toEqual(sent.at(-2));
  });

  it("resumes a lesson at the step whose write was still pending when Home opened", async () => {
    const { fake, listed } = projectService();
    await userEvent.click(
      await screen.findByRole("button", { name: "Resume the lesson Coffee shop queue" }),
    );
    expect(await screen.findByRole("region", { name: "Arrive" })).toBeVisible();
    // The next step's write is held while the user goes Home.
    const letStep = fake.hold("PATCH /v1/projects/p1");
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(fake.heldOn("PATCH /v1/projects/p1")).toBe(1));
    await userEvent.click(screen.getByRole("button", { name: "Home" }));
    // The list is read only after the step's write; until then the lesson button waits.
    const waiting = await screen.findByRole("button", { name: /the lesson Coffee shop queue$/ });
    expect(waiting).toHaveAttribute("aria-disabled", "true");
    expect(fake.requested("GET", "/v1/projects")).toHaveLength(2);
    letStep();
    await waitFor(() => expect(listed()[0]?.lesson_step).toBe(1));
    const resume = await screen.findByRole("button", {
      name: "Resume the lesson Coffee shop queue",
    });
    await waitFor(() => expect(resume).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(resume);
    // At the step the write kept, not the one before it.
    expect(await screen.findByRole("region", { name: "Queue" })).toBeVisible();
  });
});

describe("first start", () => {
  it("shows the notice once: what the tool does, estimates, the licence, Continue", async () => {
    const { fake } = boot();
    const dialog = await screen.findByRole("dialog", { name: "Welcome" });
    expect(dialog).toHaveTextContent(NOTICE_TEXT.does);
    expect(dialog).toHaveTextContent(NOTICE_TEXT.estimates);
    expect(dialog).toHaveTextContent(NOTICE_TEXT.licence);
    const go = screen.getByRole("button", { name: "Continue" });
    expect(go).toHaveFocus();
    fake.answer("PUT /v1/settings", { settings: seen, issues: [] });
    await userEvent.click(go);
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(fake.requested("PUT", "/v1/settings")).toHaveLength(1));
    // The whole interface object, with the other preferences as they were.
    expect(fake.requested("PUT", "/v1/settings")[0]?.body).toEqual({ interface: seen.interface });
  });

  it("does not show the notice once it has been seen", async () => {
    boot(seen);
    expect(
      await screen.findByRole("heading", { name: "What would you like to do?" }),
    ).toBeVisible();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows the service's problem when remembering the notice fails", async () => {
    const { fake } = boot();
    fake.answer("PUT /v1/settings", errorBody("E184", "The setting 'interface' is wrong."), 400);
    await userEvent.click(await screen.findByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "E184 The setting 'interface' is wrong.",
    );
  });

  it("applies the stored preferences to the page", async () => {
    const { root } = boot({
      ...seen,
      interface: { ...seen.interface, theme: "dark", text_size: 200 },
    });
    await screen.findByRole("heading", { name: "What would you like to do?" });
    expect(root.dataset.theme).toBe("dark");
    expect(root.style.fontSize).toBe("200%");
  });
});

describe("boot", () => {
  it("says it is connecting, then that the service did not answer, and tries again", async () => {
    const fake = startedService().on("GET /v1/settings", () => "unreachable");
    render(<Boot client={fake.client()} root={document.createElement("html")} />);
    expect(screen.getByRole("status")).toHaveTextContent(CONNECTING);
    expect(await screen.findByText(NOT_ANSWERING)).toBeInTheDocument();
    fake.answer("GET /v1/settings", { settings: seen, issues: [] });
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { name: "What would you like to do?" }),
    ).toBeVisible();
  });

  it("shows the service's refusal, such as a token from an earlier start", async () => {
    const fake = startedService().answer(
      "GET /v1/settings",
      errorBody("E182", "The request has no token, or not this service's token."),
      401,
    );
    render(<Boot client={fake.client()} root={document.createElement("html")} />);
    const alerts = await screen.findAllByRole("alert");
    expect(alerts.map((alert) => alert.textContent)).toEqual([
      "E182 The request has no token, or not this service's token.",
    ]);
    expect(screen.queryByText(NOT_ANSWERING)).toBeNull();
  });

  it("asks for the launcher without a token", () => {
    render(<NoToken />);
    expect(screen.getByRole("alert")).toHaveTextContent(NO_TOKEN);
  });
});

describe("the frame", () => {
  it("opens a new project on the Canvas, which loads its model and listens to its events", async () => {
    const { fake } = boot(seen);
    new ModelService(fake);
    const created = {
      id: "p1",
      name: "Shop",
      created: "2026-11-08T10:00:00Z",
      layout_version: 1,
      model_revision: 0,
      path: "/p1",
      available: true,
    };
    fake.answer("POST /v1/projects", created).answer("GET /v1/projects", [created]);
    await userEvent.click(await screen.findByRole("button", { name: "New empty project" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Shop");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("heading", { name: "Canvas" })).toBeInTheDocument();
    expect(window.location.hash).toBe("#/canvas/p1");
    expect(screen.getByRole("banner")).toHaveTextContent("Shop");
    // The Canvas's tools sit in the top bar.
    expect(await within(screen.getByRole("banner")).findByText("Saved")).toBeInTheDocument();
    const socket = fake.sockets[0];
    socket?.open();
    expect(socket?.sent).toEqual([JSON.stringify({ token: "test-token" })]);
    socket?.serverClose(1008, "E185");
    expect(await screen.findByText(LOST_CONTACT)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Data" }));
    // The Data screen (AKS-120) loads the model and the project's files.
    expect(await screen.findByRole("heading", { name: "Files" })).toBeVisible();
    expect(fake.requested("GET", "/v1/projects/p1/data")).toHaveLength(1);
    fake.answer("GET /v1/projects/p1/runs", []);
    await userEvent.click(screen.getByRole("button", { name: "Run monitor" }));
    expect(screen.getByRole("heading", { name: "Run monitor" })).toBeVisible();
    expect(await screen.findByText(/No run of this project yet/)).toBeVisible();
    fake.answer("GET /v1/system", {
      cores: 4,
      memory: null,
      graphics: null,
      tier: "low",
      workers: 4,
    });
    fake.answer("GET /v1/engines", []);
    await userEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByRole("heading", { name: "About" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Read the licence" })).toHaveAttribute(
      "href",
      "./LICENSE.txt",
    );
    await userEvent.click(screen.getByRole("button", { name: "Home" }));
    expect(screen.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
  });

  it("finds the project of a reloaded route, or goes Home when it is gone", async () => {
    const listed = {
      id: "p2",
      name: "Line",
      created: null,
      layout_version: 1,
      model_revision: 4,
      path: "/p2",
      available: true,
    };
    window.location.hash = "#/canvas/p2";
    const { fake } = boot(seen);
    new ModelService(fake, { pid: "p2" });
    fake.answer("GET /v1/projects", [listed]);
    expect(await screen.findByRole("heading", { name: "Canvas" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("banner")).toHaveTextContent("Line"));
    window.location.hash = "#/results/gone";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    expect(
      await screen.findByRole("heading", { name: "What would you like to do?" }),
    ).toBeVisible();
  });

  it("Build opens the form, and Continue opens the project on the Data screen or the Canvas", async () => {
    const shop = { id: "coffee_shop", title: "Coffee shop queue" };
    const made = {
      id: "p1",
      name: "Coffee shop queue",
      created: "2026-11-09T10:00:00Z",
      layout_version: 1,
      model_revision: 0,
      path: "/p1",
      available: true,
    };
    window.location.hash = "#/";
    const { fake } = boot(seen);
    new ModelService(fake);
    fake
      .answer("GET /v1/templates", [shop])
      .answer("POST /v1/projects", made)
      .answer("GET /v1/projects/p1/data", []);
    await userEvent.click(await screen.findByRole("button", { name: /^Build/ }));
    expect(await screen.findByRole("heading", { name: "Build a model" })).toBeVisible();
    expect(window.location.hash).toBe("#/build");
    expect(screen.getByRole("banner")).toHaveTextContent("Build a model");
    // The rail shows Home as the current screen.
    expect(screen.getByRole("button", { name: "Home" })).toHaveAttribute("aria-current", "page");
    await userEvent.click(
      await screen.findByRole("radio", { name: /How long will people or items wait\?/ }),
    );
    await userEvent.click(screen.getByRole("radio", { name: /Yes, import a file/ }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("heading", { name: "Files" })).toBeVisible();
    expect(window.location.hash).toBe("#/data/p1");

    await userEvent.click(screen.getByRole("button", { name: "Home" }));
    await userEvent.click(await screen.findByRole("button", { name: /^Build/ }));
    await userEvent.click(
      await screen.findByRole("radio", { name: /How long will people or items wait\?/ }),
    );
    await userEvent.click(screen.getByRole("radio", { name: /No, I will estimate/ }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("heading", { name: "Canvas" })).toBeInTheDocument();
    expect(window.location.hash).toBe("#/canvas/p1");
    await userEvent.click(screen.getByRole("button", { name: "Home" }));
    await userEvent.click(await screen.findByRole("button", { name: /^Build/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Back" }));
    expect(window.location.hash).toBe("#/");
  });

  it("starts a lesson from the gallery on the Canvas, with its step card", async () => {
    const shop = { id: "coffee_shop", title: "Coffee shop queue", experiment: "base" };
    const lesson =
      "# Coffee shop queue\n\n## Arrive\n\nComponent: `arrivals`\n\nThey arrive.\n\n" +
      "## Exercise: two tills\n\nComponent: `till`\n\n### Change\n\nSet it.\n\n" +
      "### Prediction\n\n- [x] Less.\n- [ ] More.\n\n### Explanation\n\nBecause.\n";
    const made = {
      id: "p1",
      name: "Coffee shop queue",
      created: "2026-11-09T10:00:00Z",
      layout_version: 1,
      model_revision: 0,
      path: "/p1",
      available: true,
    };
    window.location.hash = "#/";
    const { fake } = boot(seen);
    new ModelService(fake);
    fake
      .answer("GET /v1/templates", [shop])
      .answer("GET /v1/templates/coffee_shop", { template: shop, lesson, expected: [] })
      .answer("POST /v1/projects", made);
    await userEvent.click(
      await screen.findByRole("button", { name: "Start the lesson Coffee shop queue" }),
    );
    expect(await screen.findByRole("region", { name: "Arrive" })).toBeVisible();
    expect(window.location.hash).toBe("#/canvas/p1");
    // Opened again from Recent projects, the project shows no lesson (spec 4).
    fake.answer("GET /v1/projects", [made]);
    await userEvent.click(screen.getByRole("button", { name: "Home" }));
    await userEvent.click(await screen.findByText("/p1"));
    expect(await screen.findByRole("heading", { name: "Canvas" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("banner")).toHaveTextContent("Saved"));
    expect(screen.queryByRole("region", { name: "Arrive" })).toBeNull();
    expect(document.querySelector(".step-card")).toBeNull();
  });

  it("ends a lesson with Exit lesson", async () => {
    const shop = { id: "coffee_shop", title: "Coffee shop queue", experiment: "base" };
    const lesson =
      "# Coffee shop queue\n\n## Arrive\n\nComponent: `arrivals`\n\nThey arrive.\n\n" +
      "## Exercise: two tills\n\nComponent: `till`\n\n### Change\n\nSet it.\n\n" +
      "### Prediction\n\n- [x] Less.\n- [ ] More.\n\n### Explanation\n\nBecause.\n";
    const made = {
      id: "p1",
      name: "Coffee shop queue",
      created: "2026-11-09T10:00:00Z",
      layout_version: 1,
      model_revision: 0,
      path: "/p1",
      available: true,
    };
    window.location.hash = "#/";
    const { fake } = boot(seen);
    new ModelService(fake);
    fake
      .answer("GET /v1/templates", [shop])
      .answer("GET /v1/templates/coffee_shop", { template: shop, lesson, expected: [] })
      .answer("POST /v1/projects", made);
    await userEvent.click(
      await screen.findByRole("button", { name: "Start the lesson Coffee shop queue" }),
    );
    expect(await screen.findByRole("region", { name: "Arrive" })).toBeVisible();
    const steps = () =>
      fake
        .requested("PATCH", "/v1/projects/p1")
        .map((request) => request.body as Record<string, unknown>)
        .filter((body) => "lesson_step" in body)
        .map((body) => body.lesson_step);
    await waitFor(() => expect(steps()).toEqual([0]));
    // Opening the new project notes the time, as every opening does (review of pull request 201).
    expect(fake.requested("PATCH", "/v1/projects/p1").map((r) => r.body)).toContainEqual({
      opened: true,
    });
    // With a step's write held, Exit's clearing waits for it, so it is the last kept.
    const release = fake.holdWrites();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(steps()).toEqual([0, 1]));
    await userEvent.click(screen.getByRole("button", { name: "Exit lesson" }));
    expect(screen.queryByRole("region", { name: "Arrive" })).toBeNull();
    expect(steps()).toEqual([0, 1]);
    release();
    await waitFor(() => expect(steps()).toEqual([0, 1, null]));
  });

  it("closes the open project and its lesson when Home removes it (review of pull request 201)", async () => {
    const shop = { id: "coffee_shop", title: "Coffee shop queue", experiment: "base" };
    const lesson =
      "# Coffee shop queue\n\n## Arrive\n\nComponent: `arrivals`\n\nThey arrive.\n\n" +
      "## Exercise: two tills\n\nComponent: `till`\n\n### Change\n\nSet it.\n\n" +
      "### Prediction\n\n- [x] Less.\n- [ ] More.\n\n### Explanation\n\nBecause.\n";
    const made = {
      id: "p1",
      name: "Coffee shop queue",
      created: "2026-11-09T10:00:00Z",
      layout_version: 1,
      model_revision: 0,
      path: "/p1",
      available: true,
    };
    window.location.hash = "#/";
    const { fake } = boot(seen);
    new ModelService(fake);
    let listed = [made];
    fake
      .answer("GET /v1/templates", [shop])
      .answer("GET /v1/templates/coffee_shop", { template: shop, lesson, expected: [] })
      .answer("POST /v1/projects", made)
      .on("GET /v1/projects", () => ({ status: 200, body: listed }))
      .on("POST /v1/projects/p1/remove", () => {
        listed = [];
        return { status: 200, body: { id: "p1", path: "/p1" } };
      });
    await userEvent.click(
      await screen.findByRole("button", { name: "Start the lesson Coffee shop queue" }),
    );
    expect(await screen.findByRole("region", { name: "Arrive" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Home" }));
    expect(screen.getByRole("button", { name: "Canvas" })).not.toHaveAttribute("aria-disabled");
    await userEvent.click(
      await screen.findByRole("button", { name: "Remove Coffee shop queue from the list" }),
    );
    // The project screens wait for a project again, and no lesson is left.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Canvas" })).toHaveAttribute(
        "aria-disabled",
        "true",
      ),
    );
    const cleared = fake
      .requested("PATCH", "/v1/projects/p1")
      .filter((request) => (request.body as Record<string, unknown>).lesson_step === null);
    expect(cleared).toEqual([]);
    await userEvent.click(screen.getByRole("button", { name: "Canvas" }));
    expect(screen.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
    expect(document.querySelector(".step-card")).toBeNull();
  });

  it("renames the open project in the top bar when Home renames it (review of pull request 201)", async () => {
    const made = {
      id: "p1",
      name: "Shop",
      created: "2026-11-08T10:00:00Z",
      layout_version: 1,
      model_revision: 0,
      path: "/p1",
      available: true,
    };
    const { fake } = boot(seen);
    new ModelService(fake);
    let current = made;
    fake
      .answer("POST /v1/projects", made)
      .on("GET /v1/projects", () => ({ status: 200, body: [current] }))
      .on("PATCH /v1/projects/p1", (body) => {
        const name = (body as { name?: string }).name;
        if (name !== undefined) current = { ...current, name };
        return { status: 200, body: current };
      });
    await userEvent.click(await screen.findByRole("button", { name: "New empty project" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Shop");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("heading", { name: "Canvas" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Home" }));
    await userEvent.click(await screen.findByRole("button", { name: "Rename Shop" }));
    const field = screen.getByRole("textbox", { name: "New name for Shop" });
    await userEvent.clear(field);
    await userEvent.type(field, "Corner shop{Enter}");
    expect(await screen.findByRole("button", { name: "Rename Corner shop" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Canvas" }));
    await waitFor(() => expect(screen.getByRole("banner")).toHaveTextContent("Corner shop"));
  });

  it("moves between regions with F6", async () => {
    boot(seen);
    await screen.findByRole("heading", { name: "What would you like to do?" });
    await userEvent.keyboard("{F6}");
    expect(screen.getByRole("button", { name: "Home" })).toHaveFocus();
    await userEvent.keyboard("{F6}");
    expect(screen.getByRole("banner")).toHaveFocus();
    await userEvent.keyboard("{Shift>}{F6}{/Shift}");
    expect(screen.getByRole("button", { name: "Home" })).toHaveFocus();
    await userEvent.keyboard("{F5}");
    expect(screen.getByRole("button", { name: "Home" })).toHaveFocus();
  });
});
