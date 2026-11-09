import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Settings } from "../api/types";
import { LOST_CONTACT } from "../components/ServiceProblem";
import { NOTICE_TEXT } from "../screens/FirstStartNotice";
import { ModelService } from "../test/fakeModel";
import { errorBody, SETTINGS, startedService } from "../test/fakes";
import { Boot, CONNECTING, NO_TOKEN, NOT_ANSWERING, NoToken } from "./Boot";

function boot(settings: Settings = SETTINGS) {
  const fake = startedService(settings);
  const root = document.createElement("html");
  render(<Boot client={fake.client()} root={root} />);
  return { fake, root };
}

const seen = { ...SETTINGS, interface: { ...SETTINGS.interface, first_start_seen: true } };

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
