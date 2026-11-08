/**
 * The Canvas's rules (spec 3 "Canvas behaviour"; `docs/design/canvas-interactions.md`),
 * one or more tests each, against the fake service of `test/fakeModel.ts`. The pointer
 * drags of React Flow (moving a block, dragging port to port) are checked end to end in
 * `e2e/canvas.spec.ts`, since jsdom lays nothing out.
 */
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Issue, Model, Project, Settings } from "../api/types";
import { LOST_CONTACT } from "../components/ServiceProblem";
import { SettingsProvider } from "../settings/SettingsContext";
import { coffeeShop, emptyModel, ModelService, PID } from "../test/fakeModel";
import { FakeService, SETTINGS } from "../test/fakes";
import { CanvasScreen, runBlocked } from "./CanvasScreen";
import { BLOCK_MIME } from "./Palette";
import type { SessionState } from "./session";

const PROJECT: Project = {
  id: PID,
  name: "Shop",
  created: "2026-11-08T10:00:00Z",
  layout_version: 1,
  model_revision: 3,
  path: "/p1",
  available: true,
};
const EDITS = `/v1/projects/${PID}/model/edits`;
const MODEL = `/v1/projects/${PID}/model`;

interface Options {
  model?: Model;
  settings?: Settings;
  validate?: (model: Model) => Issue[];
}

function renderCanvas(options: Options = {}) {
  const settings = options.settings ?? SETTINGS;
  const fake = new FakeService();
  const service = new ModelService(fake, {
    model: options.model ?? coffeeShop(),
    revision: 3,
    ...(options.validate ? { validate: options.validate } : {}),
  });
  fake.on("PUT /v1/settings", (body) => ({
    status: 200,
    body: { settings: { ...settings, ...(body as object) }, issues: [] },
  }));
  const go = vi.fn();
  const client = fake.client();
  const toolbar = document.createElement("div");
  document.body.append(toolbar);
  render(
    <SettingsProvider client={client} initial={settings} root={document.documentElement}>
      <CanvasScreen client={client} project={PROJECT} toolbar={toolbar} onGo={go} />
    </SettingsProvider>,
  );
  return { fake, service, go, toolbar, user: userEvent.setup() };
}

function node(id: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`.react-flow__node[data-id="${id}"]`);
  if (found === null) throw new Error(`no block ${id}`);
  return found;
}

async function drawn(id: string): Promise<HTMLElement> {
  await waitFor(() =>
    expect(document.querySelector(`.react-flow__node[data-id="${id}"]`)).not.toBeNull(),
  );
  return node(id);
}

function sentEdits(fake: FakeService): unknown[] {
  return fake
    .requested("POST", EDITS)
    .map((request) => (request.body as { edits: unknown[] }).edits);
}

async function settled(toolbar: HTMLElement) {
  await waitFor(() => expect(within(toolbar).getByRole("status")).toHaveTextContent("Saved"));
  const counts = within(screen.getByRole("region", { name: "Problems" })).getByRole("status");
  await waitFor(() => expect(counts).not.toHaveTextContent("Checking"));
}

/** Clicks a block (React Flow selects on click; its drag needs a mousedown jsdom cannot give). */
async function select(_user: ReturnType<typeof userEvent.setup>, id: string) {
  fireEvent.click(await drawn(id));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "Id" })).toHaveValue(id));
}

describe("the Canvas draws the model and nothing else", () => {
  it("draws a block per component, a line per connection and a reference line per pool or target", async () => {
    const model = coffeeShop();
    model.components?.push(
      { id: "staff", type: "resource_pool", params: { capacity: 2 }, ui: { x: 0, y: 160 } },
      { id: "pick", type: "server", params: { pool: "staff" }, ui: { x: 240, y: 160 } },
      { id: "shifts", type: "schedule", params: { target: "pick" }, ui: { x: 480, y: 160 } },
      { id: "breaks", type: "failure", params: { target: "till" }, ui: { x: 480, y: 320 } },
    );
    renderCanvas({ model });
    expect(await drawn("arrivals")).toHaveAttribute("aria-label", "arrivals, source, every 2 min");
    expect(node("till")).toHaveAttribute("aria-label", "till, server, capacity = tills");
    expect(node("arrivals").querySelector(".block")).toHaveClass("block-flow");
    expect(node("till").querySelector(".block")).toHaveClass("block-work");
    expect(node("staff").querySelector(".block")).toHaveClass("block-resource");
    expect(node("staff")).toHaveTextContent("2");
    expect(document.querySelectorAll(".react-flow__edge-smoothstep")).toHaveLength(2);
    await waitFor(() => expect(screen.getByText("staffs")).toBeInTheDocument());
    expect(screen.getByText("sets hours")).toBeInTheDocument();
    expect(screen.getByText("breaks down")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Overview of the model" })).toBeInTheDocument();
  });
});

describe("adding a block", () => {
  it("adds with Enter on a palette type: the next id, params {}, and selects it", async () => {
    const model = coffeeShop();
    model.components?.push({ id: "server_2", type: "server", params: {}, ui: { x: 0, y: 200 } });
    const { fake, toolbar, user } = renderCanvas({ model });
    await drawn("till");
    await settled(toolbar);
    screen.getByRole("button", { name: "server" }).focus();
    await user.keyboard("{Enter}");
    await drawn("server_3");
    const [edits] = sentEdits(fake) as { id: string; params: unknown; ui: unknown }[][];
    expect(edits).toEqual([
      expect.objectContaining({
        edit: "add_component",
        id: "server_3",
        type: "server",
        params: {},
      }),
    ]);
    expect(edits?.[0]?.ui).toEqual({ x: expect.any(Number), y: expect.any(Number) });
    expect(await screen.findByRole("textbox", { name: "Id" })).toHaveValue("server_3");
    await waitFor(() => expect(node("server_3")).toHaveFocus());
  });

  it("adds by dropping a palette type on the canvas", async () => {
    const { fake, toolbar } = renderCanvas({ model: emptyModel() });
    await settled(toolbar);
    const area = screen.getByRole("region", { name: "Canvas" });
    const data = { types: [BLOCK_MIME], getData: () => "sink", dropEffect: "" };
    fireEvent.dragOver(area, { dataTransfer: data });
    fireEvent.drop(area, { dataTransfer: data, clientX: 300, clientY: 200 });
    await drawn("sink_1");
    expect(sentEdits(fake)).toEqual([
      [
        {
          edit: "add_component",
          id: "sink_1",
          type: "sink",
          params: {},
          ui: { x: expect.any(Number), y: expect.any(Number) },
        },
      ],
    ]);
  });

  it("adds by clicking a type then the canvas; Escape stops placing", async () => {
    const { fake, toolbar, user } = renderCanvas({ model: emptyModel() });
    await settled(toolbar);
    const delay = screen.getByRole("button", { name: "delay" });
    await user.click(delay);
    expect(delay).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Click the canvas to place delay. Escape cancels.")).toBeVisible();
    await user.keyboard("{Escape}");
    expect(delay).toHaveAttribute("aria-pressed", "false");
    await user.click(delay);
    const pane = document.querySelector(".react-flow__pane") as HTMLElement;
    fireEvent.click(pane, { clientX: 200, clientY: 100 });
    await drawn("delay_1");
    expect(sentEdits(fake)).toHaveLength(1);
    expect(delay).toHaveAttribute("aria-pressed", "false");
  });

  it("filters the palette and lists only the installed process types, by group", async () => {
    const { toolbar, user } = renderCanvas();
    await settled(toolbar);
    const palette = screen.getByRole("complementary", { name: "Blocks" });
    expect(
      within(palette)
        .getAllByRole("heading", { level: 3 })
        .map((item) => item.textContent),
    ).toEqual(["Flow", "Work", "Resources"]);
    await user.type(screen.getByRole("searchbox", { name: "Filter blocks" }), "sch");
    expect(
      within(palette)
        .getAllByRole("button")
        .map((item) => item.textContent),
    ).toEqual(["schedule"]);
  });
});

describe("connecting", () => {
  it("connects from the side panel's picker, and says when it replaces a connection", async () => {
    const { fake, toolbar, user } = renderCanvas();
    await select(user, "arrivals");
    await user.selectOptions(screen.getByRole("combobox", { name: "out goes to" }), "exit.in");
    expect(
      await screen.findByText("arrivals.out now goes to exit.in (was till.in)."),
    ).toBeVisible();
    expect(sentEdits(fake)).toEqual([[{ edit: "connect", from: "arrivals.out", to: "exit.in" }]]);
    await settled(toolbar);
    await user.selectOptions(screen.getByRole("combobox", { name: "out goes to" }), "");
    await waitFor(() =>
      expect(sentEdits(fake)[1]).toEqual([{ edit: "disconnect", from: "arrivals.out" }]),
    );
  });

  it("connects with C and the Connect dialog", async () => {
    const { fake, toolbar, user } = renderCanvas();
    await select(user, "till");
    fireEvent.keyDown(node("till"), { key: "c" });
    const dialog = await screen.findByRole("dialog", { name: "Connect till" });
    expect(within(dialog).getByRole("combobox", { name: "Goes to" })).toHaveValue("exit.in");
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Goes to" }), "till.in");
    await user.click(within(dialog).getByRole("button", { name: "Connect" }));
    await settled(toolbar);
    expect(sentEdits(fake)).toEqual([[{ edit: "connect", from: "till.out", to: "till.in" }]]);
  });
});

describe("deleting", () => {
  it("asks first, names what goes, and turns the question off when asked to", async () => {
    const { fake, toolbar, user } = renderCanvas();
    await select(user, "till");
    fireEvent.keyDown(node("till"), { key: "Delete" });
    const dialog = await screen.findByRole("dialog", { name: "Delete 1 block?" });
    expect(dialog).toHaveTextContent(
      "This removes till and 2 connections. You can undo it with Ctrl+Z.",
    );
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.click(within(dialog).getByRole("checkbox", { name: "Don't ask me again" }));
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    expect(await screen.findByText("Deleted till and 2 connections. Undo (Ctrl+Z).")).toBeVisible();
    expect(sentEdits(fake)).toEqual([[{ edit: "remove_component", id: "till" }]]);
    const saved = fake.requested("PUT", "/v1/settings")[0]?.body as Settings;
    expect(saved.interface).toEqual({ ...SETTINGS.interface, ask_before_deleting: false });
    await settled(toolbar);
    expect(document.querySelector('.react-flow__node[data-id="till"]')).toBeNull();
  });

  it("cancels with Escape and sends nothing", async () => {
    const { fake, user } = renderCanvas();
    await select(user, "exit");
    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", { name: "Delete 1 block?" });
    await user.keyboard("{Escape}");
    expect(dialog).not.toBeInTheDocument();
    expect(sentEdits(fake)).toEqual([]);
  });

  it("does not ask when Settings says so", async () => {
    const settings = {
      ...SETTINGS,
      interface: { ...SETTINGS.interface, ask_before_deleting: false },
    };
    const { fake, user } = renderCanvas({ settings });
    await select(user, "exit");
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() =>
      expect(sentEdits(fake)).toEqual([[{ edit: "remove_component", id: "exit" }]]),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("removes a selected connection with Disconnect or Delete, without asking", async () => {
    const { fake, toolbar, user } = renderCanvas();
    await drawn("till");
    await settled(toolbar);
    const line = (name: string) =>
      document.querySelector(`[aria-label="Connection from ${name}"]`) as HTMLElement;
    fireEvent.click(line("till.out to exit.in"));
    expect(await screen.findByRole("heading", { name: "Connection" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Disconnect" }));
    await waitFor(() =>
      expect(sentEdits(fake)).toEqual([[{ edit: "disconnect", from: "till.out" }]]),
    );
    await settled(toolbar);
    fireEvent.click(line("arrivals.out to till.in"));
    fireEvent.keyDown(line("arrivals.out to till.in"), { key: "Backspace" });
    await waitFor(() => expect(sentEdits(fake)).toHaveLength(2));
    expect(sentEdits(fake)[1]).toEqual([{ edit: "disconnect", from: "arrivals.out" }]);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("deletes a selection of several items in one batch", async () => {
    const settings = {
      ...SETTINGS,
      interface: { ...SETTINGS.interface, ask_before_deleting: false },
    };
    const { fake, toolbar } = renderCanvas({ settings });
    await drawn("till");
    await settled(toolbar);
    fireEvent.keyDown(node("till"), { key: "a", ctrlKey: true });
    expect(await screen.findByRole("heading", { name: "3 items selected" })).toBeVisible();
    fireEvent.keyDown(node("till"), { key: "Delete" });
    await waitFor(() =>
      expect(sentEdits(fake)).toEqual([
        [
          { edit: "remove_component", id: "arrivals" },
          { edit: "remove_component", id: "till" },
          { edit: "remove_component", id: "exit" },
        ],
      ]),
    );
    expect(
      await screen.findByText("Deleted arrivals, till, exit and 2 connections. Undo (Ctrl+Z)."),
    ).toBeVisible();
  });

  it("Escape clears the selection", async () => {
    const { user } = renderCanvas();
    await select(user, "till");
    fireEvent.keyDown(node("till"), { key: "Escape" });
    expect(await screen.findByRole("heading", { name: "Parameters" })).toBeVisible();
  });
});

describe("undo and redo", () => {
  it("write whole models with base_revision, named by their step", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await drawn("till");
    await settled(toolbar);
    const undo = within(toolbar).getByRole("button", { name: "Undo" });
    expect(undo).toBeDisabled();
    const before = structuredClone(service.model);
    await select(user, "till");
    const label = screen.getByRole("textbox", { name: "Label (optional)" });
    await user.type(label, "Counter{Enter}");
    await settled(toolbar);
    expect(sentEdits(fake)).toEqual([[{ edit: "set_label", id: "till", label: "Counter" }]]);
    await user.click(within(toolbar).getByRole("button", { name: "Undo: label till" }));
    await settled(toolbar);
    const put = fake.requested("PUT", MODEL)[0];
    expect(put?.search).toBe("?base_revision=4");
    expect(put?.body).toEqual(before);
    expect(node("till")).not.toHaveTextContent("Counter");
    fireEvent.keyDown(document.body, { key: "y", ctrlKey: true });
    await waitFor(() => expect(fake.requested("PUT", MODEL)).toHaveLength(2));
    await settled(toolbar);
    expect(node("till")).toHaveTextContent("Counter");
    fireEvent.keyDown(document.body, { key: "z", ctrlKey: true });
    await waitFor(() => expect(fake.requested("PUT", MODEL)).toHaveLength(3));
  });

  it("are cleared by another client's write, which reloads the model", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await select(user, "till");
    await user.type(screen.getByRole("textbox", { name: "Label (optional)" }), "A{Enter}");
    await settled(toolbar);
    expect(within(toolbar).getByRole("button", { name: "Undo: label till" })).toBeEnabled();
    service.outsideWrite((model) => {
      model.components?.push({ id: "queue_1", type: "queue", params: {}, ui: { x: 0, y: 300 } });
    });
    act(() => fake.sockets[0]?.emit({ type: "model", revision: service.revision, client: "mcp" }));
    await drawn("queue_1");
    expect(within(toolbar).getByRole("button", { name: "Undo" })).toBeDisabled();
  });
});

describe("renaming and labels", () => {
  it("renames with rename_component, and shows the service's refusal under the field", async () => {
    const { fake, toolbar, user } = renderCanvas();
    await select(user, "till");
    const id = screen.getByRole("textbox", { name: "Id" });
    await user.clear(id);
    await user.type(id, "exit{Enter}");
    const refusal = await screen.findByText("A component 'exit' already exists.");
    expect(refusal.closest("[role=alert]")).toHaveTextContent("E180");
    expect(id).toHaveValue("exit");
    await user.clear(id);
    await user.type(id, "counter{Enter}");
    await drawn("counter");
    await settled(toolbar);
    expect(sentEdits(fake)[1]).toEqual([
      { edit: "rename_component", id: "till", new_id: "counter" },
    ]);
    expect(screen.getByRole("textbox", { name: "Id" })).toHaveValue("counter");
  });

  it("F2 goes to the Id field; an empty label removes the label", async () => {
    const model = coffeeShop();
    (model.components?.[1] as { label?: string }).label = "Till";
    const { fake, toolbar, user } = renderCanvas({ model });
    await select(user, "till");
    expect(node("till")).toHaveTextContent("Till");
    fireEvent.keyDown(node("till"), { key: "F2" });
    expect(screen.getByRole("textbox", { name: "Id" })).toHaveFocus();
    await user.clear(screen.getByRole("textbox", { name: "Label (optional)" }));
    await user.keyboard("{Enter}");
    await settled(toolbar);
    expect(sentEdits(fake)).toEqual([[{ edit: "set_label", id: "till", label: null }]]);
  });
});

describe("moving", () => {
  it("moves with the Position fields", async () => {
    const { fake, toolbar, user } = renderCanvas();
    await select(user, "exit");
    const x = screen.getByRole("textbox", { name: "x" });
    await user.clear(x);
    await user.type(x, "512{Enter}");
    await settled(toolbar);
    expect(sentEdits(fake)).toEqual([[{ edit: "set_ui", id: "exit", ui: { x: 512, y: 0 } }]]);
  });

  it("makes a burst of arrow presses one write; Shift moves 40 px", async () => {
    const { fake, toolbar, user } = renderCanvas();
    await select(user, "exit");
    fireEvent.keyDown(node("exit"), { key: "ArrowRight" });
    fireEvent.keyDown(node("exit"), { key: "ArrowRight" });
    fireEvent.keyDown(node("exit"), { key: "ArrowUp", shiftKey: true });
    await waitFor(() => expect(sentEdits(fake)).toHaveLength(1), { timeout: 2000 });
    expect(sentEdits(fake)).toEqual([[{ edit: "set_ui", id: "exit", ui: { x: 496, y: -40 } }]]);
    await settled(toolbar);
    expect(within(toolbar).getByRole("button", { name: "Undo: move exit" })).toBeEnabled();
  });
});

describe("validation and Run", () => {
  const problems = (model: Model): Issue[] =>
    model.components?.some((item) => item.id === "server_1")
      ? [
          {
            code: "E122",
            severity: "error",
            component: "server_1",
            path: "/components/3/params/capacity",
            message: "Component 'server_1' is missing the required setting 'capacity'.",
            hint: "Add 'capacity' to the 'params' of 'server_1'.",
          },
          {
            code: "W200",
            severity: "warning",
            component: "server_1",
            path: "/components/3",
            message: "'server_1' cannot be reached from any source.",
            hint: null,
          },
        ]
      : [];

  it("marks blocks, lists the service's issues, and a list entry selects its block", async () => {
    const { fake, toolbar, user } = renderCanvas({ validate: problems });
    await drawn("till");
    await settled(toolbar);
    expect(screen.getByText("No problems")).toBeVisible();
    const run = within(toolbar).getByRole("button", { name: "Run" });
    expect(run).toHaveAttribute("aria-disabled", "false");
    screen.getByRole("button", { name: "server" }).focus();
    await user.keyboard("{Enter}");
    await drawn("server_1");
    await waitFor(() => expect(screen.getByText("1 error, 1 warning")).toBeVisible());
    await waitFor(() =>
      expect(node("server_1")).toHaveAttribute(
        "aria-label",
        "server_1, server, 1 error, 1 warning",
      ),
    );
    expect(node("server_1").querySelector(".block")).toHaveClass("block-error");
    expect(run).toHaveAttribute("aria-disabled", "true");
    expect(run).toHaveAttribute("data-blocked", "errors");
    const reason = within(toolbar).getByRole("button", { name: "1 error. Fix it to run." });
    await user.click(reason);
    expect(screen.getByRole("region", { name: "Problems" })).toHaveFocus();
    // Errors first; the service's code, message and hint as it wrote them.
    const rows = within(screen.getByRole("region", { name: "Problems" })).getAllByRole("button", {
      name: /Error|Warning/,
    });
    expect(rows[0]).toHaveTextContent("Error E122 server_1");
    expect(rows[0]).toHaveTextContent("Add 'capacity' to the 'params' of 'server_1'.");
    expect(rows[1]).toHaveTextContent("Warning W200 server_1");
    await user.click(rows[0] as HTMLElement);
    expect(await screen.findByRole("textbox", { name: "Id" })).toHaveValue("server_1");
    // The field the issue names shows it.
    expect(
      screen.getByText("Component 'server_1' is missing the required setting 'capacity'.", {
        selector: ".field-issue *",
      }),
    ).toBeVisible();
    await user.click(run);
    expect(sentEdits(fake)).toHaveLength(1);
  });

  it("waits half a second after the last edit before validating", async () => {
    const { fake, toolbar, user } = renderCanvas();
    await drawn("till");
    await settled(toolbar);
    const validations = () => fake.requested("POST", `/v1/projects/${PID}/validate`).length;
    expect(validations()).toBe(1);
    await select(user, "till");
    await user.type(screen.getByRole("textbox", { name: "Label (optional)" }), "A{Enter}");
    await waitFor(() => expect(sentEdits(fake)).toHaveLength(1));
    expect(within(toolbar).getByText("Checking…")).toBeVisible();
    expect(validations()).toBe(1);
    await waitFor(() => expect(validations()).toBe(2), { timeout: 2000 });
  });

  it("runs once saved and checked with no errors, by the button or Ctrl+Enter", async () => {
    const { go, toolbar, user } = renderCanvas();
    await drawn("till");
    await settled(toolbar);
    await user.click(within(toolbar).getByRole("button", { name: "Run" }));
    expect(go).toHaveBeenCalledWith({ screen: "monitor", projectId: PID });
    fireEvent.keyDown(document.body, { key: "Enter", ctrlKey: true });
    expect(go).toHaveBeenCalledTimes(2);
    expect(within(toolbar).getByRole("combobox", { name: "Experiment" })).toHaveValue("base");
  });

  it("opens the Experiment screen for an experiment's issue", async () => {
    const { go, toolbar, user } = renderCanvas({
      validate: () => [
        {
          code: "E170",
          severity: "error",
          component: null,
          path: "/experiments/0/replications",
          message: "replications below 2",
          hint: null,
        },
      ],
    });
    await drawn("till");
    await settled(toolbar);
    await user.click(screen.getByRole("button", { name: /E170/ }));
    expect(go).toHaveBeenCalledWith({ screen: "experiment", projectId: PID });
  });
});

describe("a write that fails", () => {
  it("makes the canvas read-only and is sent again every 2 seconds", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await select(user, "till");
    service.unreachable = true;
    await user.type(screen.getByRole("textbox", { name: "Label (optional)" }), "A{Enter}");
    await waitFor(() =>
      expect(within(toolbar).getByRole("status")).toHaveTextContent(
        "Not saved: the service is not answering. Retrying.",
      ),
    );
    expect(screen.getByRole("button", { name: "sink" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "Id" })).toHaveAttribute("readonly");
    expect(within(toolbar).getByRole("button", { name: "Run" })).toHaveAttribute(
      "data-blocked",
      "busy",
    );
    service.unreachable = false;
    await waitFor(() => expect(within(toolbar).getByRole("status")).toHaveTextContent("Saved"), {
      timeout: 4000,
    });
    expect(fake.requested("POST", EDITS).length).toBeGreaterThanOrEqual(2);
    expect(service.component("till")?.label).toBe("A");
  });
});

describe("the properties panel", () => {
  it("is built from GET /v1/schema/components/{type}", async () => {
    const { fake, user } = renderCanvas();
    await select(user, "till");
    expect(fake.requested("GET", "/v1/schema/components/server")).toHaveLength(1);
    expect(await screen.findByText("Capacity")).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Queue capacity (optional)" })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "Discipline (optional)" })).toHaveValue("");
    expect(screen.getByRole("option", { name: "Default (fifo)" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Pool (optional)" })).toHaveValue("");
    await select(user, "exit");
    expect(await screen.findByText("This block has no settings.")).toBeVisible();
  });

  it("edits a distribution: its type, then each field as a number and a time unit", async () => {
    const model = coffeeShop();
    model.components?.push({ id: "server_1", type: "server", params: {}, ui: { x: 0, y: 200 } });
    const { fake, toolbar, user } = renderCanvas({ model });
    await select(user, "server_1");
    const service = screen.getByRole("group", { name: "Service" });
    await user.selectOptions(
      within(service).getByRole("combobox", { name: "Distribution" }),
      "uniform",
    );
    await settled(toolbar);
    expect(sentEdits(fake)).toEqual([
      [{ edit: "set_setting", id: "server_1", path: "/service", value: { dist: "uniform" } }],
    ]);
    const fields = screen.getByRole("group", { name: "Service" });
    await user.selectOptions(within(fields).getByRole("combobox", { name: "Unit of Min" }), "min");
    expect(sentEdits(fake)).toHaveLength(1);
    await user.type(within(fields).getByRole("textbox", { name: "Min" }), "1{Enter}");
    await settled(toolbar);
    expect(sentEdits(fake)[1]).toEqual([
      { edit: "set_setting", id: "server_1", path: "/service/min", value: "1 min" },
    ]);
    // A unit chosen for a saved value rewrites it; another type keeps the shared fields.
    await user.selectOptions(
      within(screen.getByRole("group", { name: "Service" })).getByRole("combobox", {
        name: "Unit of Min",
      }),
      "h",
    );
    await settled(toolbar);
    expect(sentEdits(fake)[2]).toEqual([
      { edit: "set_setting", id: "server_1", path: "/service/min", value: "1 h" },
    ]);
    await user.selectOptions(
      within(screen.getByRole("group", { name: "Service" })).getByRole("combobox", {
        name: "Distribution",
      }),
      "triangular",
    );
    await settled(toolbar);
    expect(sentEdits(fake)[3]).toEqual([
      {
        edit: "set_setting",
        id: "server_1",
        path: "/service",
        value: { dist: "triangular", min: "1 h" },
      },
    ]);
  });

  it("sends numbers as numbers and other text as typed, and binds a parameter", async () => {
    const model = coffeeShop();
    model.components?.push({ id: "server_1", type: "server", params: {}, ui: { x: 0, y: 200 } });
    const { fake, service, toolbar, user } = renderCanvas({ model });
    await select(user, "server_1");
    await user.type(screen.getByRole("textbox", { name: "Capacity" }), "2{Enter}");
    await settled(toolbar);
    await user.clear(screen.getByRole("textbox", { name: "Capacity" }));
    await user.type(screen.getByRole("textbox", { name: "Capacity" }), "two{Enter}");
    await settled(toolbar);
    expect(sentEdits(fake)).toEqual([
      [{ edit: "set_setting", id: "server_1", path: "/capacity", value: 2 }],
      [{ edit: "set_setting", id: "server_1", path: "/capacity", value: "two" }],
    ]);
    await user.click(screen.getByRole("checkbox", { name: "Use parameter for Capacity" }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Parameter for Capacity" }),
      "tills",
    );
    await settled(toolbar);
    expect(service.component("server_1")?.params.capacity).toEqual({ $param: "tills" });
    expect(screen.getByText("= tills")).toBeVisible();
    // Unticking writes the parameter's value in its place.
    await user.click(screen.getByRole("checkbox", { name: "Use parameter for Capacity" }));
    await settled(toolbar);
    expect(service.component("server_1")?.params.capacity).toBe(1);
  });

  it("clears an optional setting by writing the whole model without it", async () => {
    const model = coffeeShop();
    model.components?.push({
      id: "server_1",
      type: "server",
      params: { queue_capacity: 4, discipline: "lifo" },
      ui: { x: 0, y: 200 },
    });
    const { fake, service, toolbar, user } = renderCanvas({ model });
    await select(user, "server_1");
    await user.clear(screen.getByRole("textbox", { name: "Queue capacity (optional)" }));
    await user.keyboard("{Enter}");
    await settled(toolbar);
    expect(fake.requested("PUT", MODEL)).toHaveLength(1);
    expect(service.component("server_1")?.params).toEqual({ discipline: "lifo" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Discipline (optional)" }), "");
    await settled(toolbar);
    expect(service.component("server_1")?.params).toEqual({});
    expect(within(toolbar).getByRole("button", { name: /^Undo: clear server_1/ })).toBeEnabled();
  });

  it("edits a branch's routes and weights, a pool reference and a schedule's shifts", async () => {
    const model = coffeeShop();
    model.components?.push(
      { id: "split", type: "branch", params: { rule: "probability" }, ui: { x: 0, y: 200 } },
      { id: "staff", type: "resource_pool", params: { capacity: 2 }, ui: { x: 240, y: 200 } },
      { id: "shifts", type: "schedule", params: {}, ui: { x: 480, y: 200 } },
    );
    const { fake, service, toolbar, user } = renderCanvas({ model });
    await select(user, "split");
    expect(screen.getByText("One entry for each of Routes; none yet.")).toBeVisible();
    await user.type(screen.getByRole("textbox", { name: "Routes" }), "left, right{Enter}");
    await settled(toolbar);
    expect(service.component("split")?.params.routes).toEqual(["left", "right"]);
    await user.type(screen.getByRole("textbox", { name: "left" }), "3{Enter}");
    await settled(toolbar);
    expect(sentEdits(fake).at(-1)).toEqual([
      { edit: "set_setting", id: "split", path: "/weights", value: { left: 3 } },
    ]);
    await user.type(screen.getByRole("textbox", { name: "right" }), "1{Enter}");
    await settled(toolbar);
    expect(sentEdits(fake).at(-1)).toEqual([
      { edit: "set_setting", id: "split", path: "/weights/right", value: 1 },
    ]);
    // Each route is an output port.
    await waitFor(() => expect(node("split").querySelectorAll(".port.source")).toHaveLength(2));

    await select(user, "till");
    expect(
      within(screen.getByRole("combobox", { name: "Pool (optional)" }))
        .getAllByRole("option")
        .map((item) => item.textContent),
    ).toEqual(["None", "staff"]);
    await user.selectOptions(screen.getByRole("combobox", { name: "Pool (optional)" }), "staff");
    await settled(toolbar);
    expect(service.component("till")?.params.pool).toBe("staff");
    await waitFor(() => expect(screen.getByText("staffs")).toBeInTheDocument());

    await select(user, "shifts");
    await user.click(screen.getByRole("button", { name: "Add to shifts" }));
    await settled(toolbar);
    expect(service.component("shifts")?.params.shifts).toEqual([{}]);
    await user.click(screen.getByRole("button", { name: "Add to shifts" }));
    await settled(toolbar);
    expect(sentEdits(fake).at(-1)).toEqual([
      { edit: "set_setting", id: "shifts", path: "/shifts/-", value: {} },
    ]);
    const first = screen.getByRole("group", { name: "Shifts 1" });
    await user.type(within(first).getByRole("textbox", { name: "Capacity" }), "2{Enter}");
    await settled(toolbar);
    expect(service.component("shifts")?.params.shifts).toEqual([{ capacity: 2 }, {}]);
    await user.click(screen.getByRole("button", { name: "Remove shifts 2" }));
    await settled(toolbar);
    expect(service.component("shifts")?.params.shifts).toEqual([{ capacity: 2 }]);
  });
});

describe("the Parameters section", () => {
  it("creates, edits, clears and removes parameters without a scenario", async () => {
    const { fake, service, toolbar, user } = renderCanvas({ model: emptyModel() });
    await settled(toolbar);
    const form = screen.getByRole("form", { name: "Add parameter" });
    await user.type(within(form).getByRole("textbox", { name: "Id" }), "rate");
    await user.selectOptions(within(form).getByRole("combobox", { name: "Type" }), "quantity");
    await user.type(within(form).getByRole("textbox", { name: "Value" }), "2 min");
    await user.type(within(form).getByRole("textbox", { name: "Max (optional)" }), "5 min");
    await user.click(within(form).getByRole("button", { name: "Add parameter" }));
    await settled(toolbar);
    expect(sentEdits(fake)).toEqual([
      [{ edit: "set_parameter", id: "rate", type: "quantity", value: "2 min", max: "5 min" }],
    ]);
    const row = screen.getByRole("group", { name: "rate" });
    await user.clear(within(row).getByRole("textbox", { name: "Value" }));
    await user.type(within(row).getByRole("textbox", { name: "Value" }), "3 min{Enter}");
    await settled(toolbar);
    expect(sentEdits(fake)[1]).toEqual([{ edit: "set_parameter", id: "rate", value: "3 min" }]);
    await user.selectOptions(
      within(screen.getByRole("group", { name: "rate" })).getByRole("combobox", { name: "Type" }),
      "number",
    );
    await settled(toolbar);
    expect(sentEdits(fake)[2]).toEqual([{ edit: "set_parameter", id: "rate", type: "number" }]);
    await user.clear(
      within(screen.getByRole("group", { name: "rate" })).getByRole("textbox", {
        name: "Max (optional)",
      }),
    );
    await user.keyboard("{Enter}");
    await settled(toolbar);
    expect(service.model.parameters?.rate).toEqual({ value: "3 min", type: "number" });
    expect(fake.requested("PUT", MODEL)).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Remove rate" }));
    await settled(toolbar);
    expect(service.model.parameters).toEqual({});
    expect(service.model.experiments?.[0]?.scenarios).toBeUndefined();
  });

  it("shows the service's refusal when a used parameter is removed", async () => {
    const { toolbar, user } = renderCanvas();
    await drawn("till");
    await settled(toolbar);
    await user.click(screen.getByRole("button", { name: "Remove tills" }));
    expect(await screen.findByText("Parameter 'tills' is still used.")).toBeVisible();
  });
});

describe("other screens and states", () => {
  it("lists every block in a table whose Select buttons select it", async () => {
    const { user } = renderCanvas();
    await drawn("till");
    const table = await screen.findByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    await user.click(within(table).getByRole("button", { name: "Select till" }));
    expect(await screen.findByRole("textbox", { name: "Id" })).toHaveValue("till");
  });

  it("shows a plan's model as a later view", async () => {
    renderCanvas({
      model: { format_version: "0.1", meta: { name: "Mix" }, domain: "optimization" },
    });
    expect(
      await screen.findByText(/Table and Diagram views arrive in a later build/),
    ).toBeVisible();
  });

  it("says when the service refuses the model, or the project's events stop", async () => {
    const { fake, toolbar } = renderCanvas();
    await drawn("till");
    await settled(toolbar);
    act(() => fake.sockets[0]?.serverClose(1011, "gone"));
    expect(await screen.findByText(LOST_CONTACT)).toBeVisible();
  });

  it("zooms with its buttons and keys, between 20% and 200%", async () => {
    const { toolbar, user } = renderCanvas();
    await drawn("till");
    await settled(toolbar);
    await user.click(screen.getByRole("button", { name: /Set to 100%/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /^Zoom 100%/ })).toBeVisible());
    await user.click(screen.getByRole("button", { name: "Zoom in" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /^Zoom 120%/ })).toBeVisible());
    for (let press = 0; press < 20; press += 1)
      fireEvent.keyDown(node("till"), { key: "-", ctrlKey: true });
    await waitFor(() => expect(screen.getByRole("button", { name: /^Zoom 20%/ })).toBeVisible());
    for (let press = 0; press < 20; press += 1)
      fireEvent.keyDown(node("till"), { key: "=", ctrlKey: true });
    await waitFor(() => expect(screen.getByRole("button", { name: /^Zoom 200%/ })).toBeVisible());
    fireEvent.keyDown(node("till"), { key: "1", ctrlKey: true });
    await waitFor(() => expect(screen.getByRole("button", { name: /^Zoom 100%/ })).toBeVisible());
  });
});

describe("why Run waits", () => {
  const base: SessionState = {
    status: "ready",
    loadProblem: null,
    model: emptyModel(),
    revision: 1,
    issues: [],
    checking: false,
    saving: false,
    failing: false,
    refusal: null,
    undoLabel: null,
    redoLabel: null,
    reloads: 0,
    eventsClosed: null,
  };
  const error: Issue = {
    code: "E122",
    severity: "error",
    component: "a",
    path: "/components/0",
    message: "m",
    hint: null,
  };

  it("names the first reason, with the pointer to show", () => {
    expect(runBlocked(base)).toBeNull();
    expect(runBlocked({ ...base, issues: [{ ...error, severity: "warning" }] })).toBeNull();
    expect(runBlocked({ ...base, issues: [error, error] })).toEqual({
      reason: "2 errors. Fix them to run.",
      pointer: "errors",
    });
    expect(runBlocked({ ...base, issues: [error], checking: true })).toEqual({
      reason: "Checking…",
      pointer: "busy",
    });
    expect(runBlocked({ ...base, checking: true, saving: true })).toEqual({
      reason: "Saving…",
      pointer: "busy",
    });
    expect(runBlocked({ ...base, saving: true, failing: true })?.reason).toBe(
      "Not saved: the service is not answering. Retrying.",
    );
  });

  it("has no save button: every edit is saved", async () => {
    const { toolbar } = renderCanvas();
    await drawn("till");
    await settled(toolbar);
    expect(screen.queryByRole("button", { name: /^Save/ })).toBeNull();
  });
});
