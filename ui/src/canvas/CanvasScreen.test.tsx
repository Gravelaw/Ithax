/**
 * The Canvas's rules (spec 3 "Canvas behaviour"; `docs/design/canvas-interactions.md`),
 * one or more tests each, against the fake service of `test/fakeModel.ts`. The pointer
 * drags of React Flow (moving a block, dragging port to port) are checked end to end in
 * `e2e/canvas.spec.ts`, since jsdom lays nothing out.
 */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Issue, Model, Project, Settings } from "../api/types";
import { LOST_CONTACT } from "../components/ServiceProblem";
import { SettingsProvider } from "../settings/SettingsContext";
import { coffeeShop, emptyModel, ModelService, PID } from "../test/fakeModel";
import { FakeService, SETTINGS } from "../test/fakes";
import { CanvasScreen, runBlocked, WAIT } from "./CanvasScreen";
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
  it("writes both axes for a block drawn in the grid, from where it is drawn", async () => {
    const model = coffeeShop();
    for (const item of model.components ?? []) delete item.ui;
    const { fake, toolbar, user } = renderCanvas({ model });
    await select(user, "till");
    expect(screen.getByRole("textbox", { name: "x" })).toHaveValue("264");
    expect(screen.getByRole("textbox", { name: "y" })).toHaveValue("40");
    const x = screen.getByRole("textbox", { name: "x" });
    await user.clear(x);
    await user.type(x, "512{Enter}");
    await settled(toolbar);
    expect(sentEdits(fake)).toEqual([[{ edit: "set_ui", id: "till", ui: { x: 512, y: 40 } }]]);
  });

  it("moves with the Position fields", async () => {
    const { fake, toolbar, user } = renderCanvas();
    await select(user, "exit");
    const x = screen.getByRole("textbox", { name: "x" });
    await user.clear(x);
    await user.type(x, "512{Enter}");
    await settled(toolbar);
    expect(sentEdits(fake)).toEqual([[{ edit: "set_ui", id: "exit", ui: { x: 512, y: 0 } }]]);
  });

  it("sends each arrow press at once, a burst being one undo step; Shift moves 40 px", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await select(user, "exit");
    const press = async (key: string, shiftKey = false) => {
      fireEvent.keyDown(node("exit"), { key, shiftKey });
      await waitFor(() => expect(within(toolbar).getByRole("status")).toHaveTextContent("Saved"));
    };
    await press("ArrowRight");
    await press("ArrowRight");
    await press("ArrowUp", true);
    await waitFor(() => expect(sentEdits(fake)).toHaveLength(3));
    expect(sentEdits(fake)).toEqual([
      [{ edit: "set_ui", id: "exit", ui: { x: 488, y: 0 } }],
      [{ edit: "set_ui", id: "exit", ui: { x: 496, y: 0 } }],
      [{ edit: "set_ui", id: "exit", ui: { x: 496, y: -40 } }],
    ]);
    await settled(toolbar);
    await user.click(within(toolbar).getByRole("button", { name: "Undo: move exit" }));
    await settled(toolbar);
    expect(service.component("exit")?.ui).toEqual({ x: 480, y: 0 });
    expect(within(toolbar).getByRole("button", { name: "Undo" })).toBeDisabled();
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

  it("starts a run once saved and checked with no errors, by the button or Ctrl+Enter", async () => {
    const { fake, go, toolbar, user } = renderCanvas();
    let next = 0;
    fake.on(`POST /v1/projects/${PID}/runs`, () => ({
      status: 202,
      body: { run_id: `20261108T10000${next++}-AAAAAA` },
    }));
    await drawn("till");
    await settled(toolbar);
    await user.click(within(toolbar).getByRole("button", { name: "Run" }));
    await waitFor(() =>
      expect(go).toHaveBeenCalledWith({
        screen: "monitor",
        projectId: PID,
        runId: "20261108T100000-AAAAAA",
      }),
    );
    expect(fake.requested("POST", `/v1/projects/${PID}/runs`)[0]?.body).toEqual({
      experiment_id: "base",
    });
    fireEvent.keyDown(document.body, { key: "Enter", ctrlKey: true });
    await waitFor(() => expect(go).toHaveBeenCalledTimes(2));
    expect(within(toolbar).getByRole("combobox", { name: "Experiment" })).toHaveValue("base");
  });

  it("takes nothing else while the start awaits its answer, and shows a refusal", async () => {
    const { fake, go, toolbar, user } = renderCanvas();
    fake.answer(
      `POST /v1/projects/${PID}/runs`,
      {
        error: { code: "E122", message: "The model has errors." },
        issues: [
          {
            code: "E122",
            severity: "error",
            component: "till",
            path: "/components/1/params/service",
            message: "Component 'till' is missing the required setting 'service'.",
            hint: null,
          },
        ],
      },
      422,
    );
    await drawn("till");
    await settled(toolbar);
    const release = fake.holdWrites();
    const run = within(toolbar).getByRole("button", { name: "Run" });
    await user.click(run);
    await waitFor(() => expect(fake.held).toBe(1));
    expect(within(toolbar).getByText("Starting the run…")).toBeVisible();
    expect(run).toHaveAttribute("aria-disabled", "true");
    await user.click(run);
    fireEvent.keyDown(document.body, { key: "Enter", ctrlKey: true });
    await select(user, "till");
    await user.type(screen.getByRole("textbox", { name: "Label (optional)" }), "A{Enter}");
    expect(await screen.findByText(WAIT)).toBeVisible();
    release();
    expect(
      await screen.findByText("Component 'till' is missing the required setting 'service'."),
    ).toBeVisible();
    expect(fake.requested("POST", `/v1/projects/${PID}/runs`)).toHaveLength(1);
    expect(sentEdits(fake)).toHaveLength(0);
    expect(go).not.toHaveBeenCalled();
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
    // The keys go to the canvas region, not to a block: zooming in can take a block out of
    // view, and React Flow then stops drawing it (onlyRenderVisibleElements).
    const area = screen.getByRole("region", { name: "Canvas" });
    await user.click(screen.getByRole("button", { name: /Set to 100%/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /^Zoom 100%/ })).toBeVisible());
    await user.click(screen.getByRole("button", { name: "Zoom in" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /^Zoom 120%/ })).toBeVisible());
    for (let press = 0; press < 20; press += 1)
      fireEvent.keyDown(area, { key: "-", ctrlKey: true });
    await waitFor(() => expect(screen.getByRole("button", { name: /^Zoom 20%/ })).toBeVisible());
    for (let press = 0; press < 20; press += 1)
      fireEvent.keyDown(area, { key: "=", ctrlKey: true });
    await waitFor(() => expect(screen.getByRole("button", { name: /^Zoom 200%/ })).toBeVisible());
    fireEvent.keyDown(area, { key: "1", ctrlKey: true });
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
    baseline: null,
    outside: null,
    writers: {},
    eventsClosed: null,
    busy: false,
    starting: false,
    renamed: {},
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
    expect(runBlocked({ ...base, busy: true, starting: true })).toEqual({
      reason: "Starting the run…",
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

describe("while a write awaits its answer (review of PR #45)", () => {
  const busyStatus = (toolbar: HTMLElement) =>
    waitFor(() => expect(within(toolbar).getByRole("status")).toHaveTextContent("Saving…"));

  it("takes no other change: controls say so, keys are ignored, and nothing is sent", async () => {
    const { fake, toolbar, user } = renderCanvas();
    await select(user, "exit");
    const open = fake.holdWrites();
    fireEvent.keyDown(node("exit"), { key: "ArrowRight" });
    await busyStatus(toolbar);
    expect(screen.getByRole("region", { name: "Canvas" }).closest("[aria-busy]")).toHaveAttribute(
      "aria-busy",
      "true",
    );
    expect(screen.getByRole("button", { name: "sink" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("button", { name: "Delete" })).toHaveAttribute("aria-disabled", "true");
    expect(within(toolbar).getByRole("button", { name: "Undo" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    fireEvent.keyDown(node("exit"), { key: "ArrowRight" });
    fireEvent.keyDown(node("exit"), { key: "Delete" });
    fireEvent.keyDown(document.body, { key: "z", ctrlKey: true });
    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByText(WAIT)).toBeVisible();
    open();
    await settled(toolbar);
    expect(sentEdits(fake)).toEqual([[{ edit: "set_ui", id: "exit", ui: { x: 488, y: 0 } }]]);
    expect(fake.requested("PUT", MODEL)).toEqual([]);
  });

  it("sends a keyboard move made just before the canvas closes", async () => {
    const { fake, service, user } = renderCanvas();
    await select(user, "exit");
    fireEvent.keyDown(node("exit"), { key: "ArrowDown" });
    cleanup();
    await waitFor(() => expect(service.component("exit")?.ui).toEqual({ x: 480, y: 8 }));
    expect(sentEdits(fake)).toHaveLength(1);
  });

  it("refuses a unit change while a write awaits its answer", async () => {
    const { fake, service, toolbar, user } = renderCanvas({
      model: {
        ...coffeeShop(),
        components: [
          ...(coffeeShop().components ?? []),
          {
            id: "server_1",
            type: "server",
            params: { service: { dist: "exponential", mean: "1 s" } },
            ui: { x: 0, y: 200 },
          },
        ],
      },
    });
    await select(user, "server_1");
    const open = fake.holdWrites();
    await user.type(screen.getByRole("textbox", { name: "Label (optional)" }), "S{Enter}");
    await busyStatus(toolbar);
    const unit = screen.getByRole("combobox", { name: "Unit of Mean" });
    expect(unit).toHaveAttribute("aria-disabled", "true");
    await user.selectOptions(unit, "min");
    expect(await screen.findByText(WAIT)).toBeVisible();
    open();
    await settled(toolbar);
    expect(sentEdits(fake)).toHaveLength(1);
    expect(service.component("server_1")?.params.service).toEqual({
      dist: "exponential",
      mean: "1 s",
    });
    expect(screen.getByRole("combobox", { name: "Unit of Mean" })).toHaveValue("s");
  });

  it("refuses to remove a row while a row is being removed, so no index shifts under it", async () => {
    const { fake, service, toolbar, user } = renderCanvas({
      model: {
        ...coffeeShop(),
        components: [
          ...(coffeeShop().components ?? []),
          {
            id: "shifts",
            type: "schedule",
            params: { shifts: [{ capacity: 1 }, { capacity: 2 }] },
            ui: { x: 0, y: 200 },
          },
        ],
      },
    });
    await select(user, "shifts");
    const open = fake.holdWrites();
    await user.click(screen.getByRole("button", { name: "Remove shifts 1" }));
    await busyStatus(toolbar);
    await user.click(screen.getByRole("button", { name: "Remove shifts 1" }));
    expect(await screen.findByText(WAIT)).toBeVisible();
    open();
    await settled(toolbar);
    expect(sentEdits(fake)).toHaveLength(1);
    expect(service.component("shifts")?.params.shifts).toEqual([{ capacity: 2 }]);
  });

  it("does not let a block be dragged, nor ports connected", async () => {
    const { fake, toolbar, user } = renderCanvas();
    await select(user, "exit");
    expect(node("exit")).toHaveClass("draggable");
    const open = fake.holdWrites();
    await user.type(screen.getByRole("textbox", { name: "Label (optional)" }), "Door{Enter}");
    await busyStatus(toolbar);
    expect(node("exit")).not.toHaveClass("draggable");
    expect(node("till")).not.toHaveClass("draggable");
    expect(node("till").querySelector(".port.source")).not.toHaveClass("connectable");
    open();
    await settled(toolbar);
    expect(node("exit")).toHaveClass("draggable");
    expect(node("till").querySelector(".port.source")).toHaveClass("connectable");
  });

  it("refuses a commit, says so, and shows the saved value; nothing is sent later", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await select(user, "exit");
    const open = fake.holdWrites();
    await user.type(screen.getByRole("textbox", { name: "Label (optional)" }), "Door{Enter}");
    await busyStatus(toolbar);
    const x = screen.getByRole("textbox", { name: "x" });
    await user.clear(x);
    await user.type(x, "512{Enter}");
    expect(await screen.findByText(WAIT)).toBeVisible();
    expect(x).toHaveValue("480");
    open();
    await settled(toolbar);
    await new Promise((resolve) => setTimeout(resolve, 600));
    expect(sentEdits(fake)).toEqual([[{ edit: "set_label", id: "exit", label: "Door" }]]);
    expect(screen.getByRole("textbox", { name: "x" })).toHaveValue("480");
    expect(service.component("exit")?.ui).toEqual({ x: 480, y: 0 });
    // Entered again once the canvas is free, it is saved.
    await user.clear(screen.getByRole("textbox", { name: "x" }));
    await user.type(screen.getByRole("textbox", { name: "x" }), "512{Enter}");
    await settled(toolbar);
    expect(service.component("exit")?.ui).toEqual({ x: 512, y: 0 });
  });

  it("puts no draft into another row when a row is removed meanwhile", async () => {
    const { fake, service, toolbar, user } = renderCanvas({
      model: {
        ...coffeeShop(),
        components: [
          ...(coffeeShop().components ?? []),
          {
            id: "shifts",
            type: "schedule",
            params: { shifts: [{ capacity: 1 }, { capacity: 2 }, { capacity: 3 }] },
            ui: { x: 0, y: 200 },
          },
        ],
      },
    });
    await select(user, "shifts");
    const open = fake.holdWrites();
    await user.click(screen.getByRole("button", { name: "Remove shifts 1" }));
    await busyStatus(toolbar);
    const second = within(screen.getByRole("group", { name: "Shifts 2" })).getByRole("textbox", {
      name: "Capacity",
    });
    await user.clear(second);
    await user.type(second, "9{Enter}");
    expect(await screen.findByText(WAIT)).toBeVisible();
    open();
    await settled(toolbar);
    expect(sentEdits(fake)).toHaveLength(1);
    expect(service.component("shifts")?.params.shifts).toEqual([{ capacity: 2 }, { capacity: 3 }]);
    const shown = [1, 2].map((row) =>
      within(screen.getByRole("group", { name: `Shifts ${row}` })).getByRole("textbox", {
        name: "Capacity",
      }),
    );
    expect(shown.map((box) => (box as HTMLInputElement).value)).toEqual(["2", "3"]);
  });

  it("shows the saved value in a box whose draft was not committed when the model changes", async () => {
    const { fake, service, user } = renderCanvas();
    await select(user, "exit");
    const y = screen.getByRole("textbox", { name: "y" });
    await user.clear(y);
    await user.type(y, "77");
    // Another client's change arrives: the model shown changes, and so does the box.
    service.outsideWrite((model) => {
      (model.components?.[0] as { label?: string }).label = "In";
    });
    act(() => fake.sockets[0]?.emit({ type: "model", revision: service.revision, client: "mcp" }));
    await waitFor(() => expect(node("arrivals")).toHaveTextContent("In"));
    expect(screen.getByRole("textbox", { name: "y" })).toHaveValue("0");
    expect(sentEdits(fake)).toEqual([]);
  });

  it("refuses a rename of a block renamed by the write in flight; no id is reused under it", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await select(user, "till");
    const open = fake.holdWrites();
    await user.click(screen.getByRole("button", { name: "Undo" }));
    const id = screen.getByRole("textbox", { name: "Id" });
    await user.clear(id);
    await user.type(id, "a{Enter}");
    await busyStatus(toolbar);
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Discipline (optional)" }),
      "lifo",
    );
    expect(await screen.findByText(WAIT)).toBeVisible();
    open();
    await settled(toolbar);
    expect(sentEdits(fake)).toEqual([[{ edit: "rename_component", id: "till", new_id: "a" }]]);
    expect(service.component("a")?.params.discipline).toBeUndefined();
  });
});

describe("reviewing an outside change (AKS-137)", () => {
  const panel = () => screen.getByRole("complementary", { name: "Block settings" });

  async function outsideWrite(
    fake: FakeService,
    service: ModelService,
    client: string | null = "script",
  ) {
    service.outsideWrite((model) => {
      const till = model.components?.find((item) => item.id === "till");
      if (till) till.params.capacity = 2;
      model.components?.push({ id: "queue_1", type: "queue", params: {}, ui: { x: 0, y: 300 } });
      model.components = model.components?.filter((item) => item.id !== "exit");
      model.connections = model.connections?.filter((item) => item.to !== "exit.in");
    });
    act(() => fake.sockets[0]?.emit({ type: "model", revision: service.revision, client }));
    await drawn("queue_1");
  }

  it("names the client, clears undo and marks what was added, changed and removed", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await select(user, "till");
    await user.type(screen.getByRole("textbox", { name: "Label (optional)" }), "A{Enter}");
    await settled(toolbar);
    await outsideWrite(fake, service);
    expect(
      screen.getByText(
        "The model was changed by a script (script). The canvas has been reloaded; undo history was cleared.",
      ),
    ).toBeVisible();
    expect(within(toolbar).getByRole("button", { name: "Undo" })).toBeDisabled();
    expect(within(toolbar).getByRole("button", { name: "4 changes to review" })).toBeVisible();
    expect(node("till").querySelector(".block")).toHaveClass("block-mark-changed");
    expect(node("till")).toHaveTextContent("Changed");
    expect(node("till")).toHaveAttribute(
      "aria-label",
      expect.stringContaining("changed by another client, to review"),
    );
    expect(node("queue_1").querySelector(".block")).toHaveClass("block-mark-added");
    expect(node("ghost:exit")).toHaveTextContent("Removed");
    expect(document.querySelector(".react-flow__edge.review-removed")).not.toBeNull();
    // The list, with nothing selected: one row per change.
    await user.click(within(toolbar).getByRole("button", { name: "4 changes to review" }));
    const list = within(panel()).getByRole("region", { name: "4 changes to review" });
    expect(
      within(list)
        .getAllByRole("listitem")
        .map((item) => item.firstChild?.textContent),
    ).toEqual([
      "Changed: block till (capacity: tills → 2)",
      "Added: block queue_1",
      "Removed: block exit",
      "Removed: connection till.out",
    ]);
    await waitFor(() => expect(document.getElementById("review-heading")).toHaveFocus());
  });

  it("rejects one change with a whole-model write and base_revision, an undo step", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await settled(toolbar);
    await outsideWrite(fake, service);
    await settled(toolbar);
    await user.click(
      within(panel()).getByRole("button", { name: "Reject the change to block till" }),
    );
    await settled(toolbar);
    expect(fake.requested("PUT", MODEL).at(-1)?.search).toBe("?base_revision=4");
    expect(service.component("till")?.params.capacity).toEqual({ $param: "tills" });
    expect(service.component("queue_1")).toBeDefined();
    expect(node("till").querySelector(".block")).not.toHaveClass("block-mark");
    expect(within(toolbar).getByRole("button", { name: "3 changes to review" })).toBeVisible();
    expect(
      within(toolbar).getByRole("button", { name: "Undo: reject the change to block till" }),
    ).toBeEnabled();
    // Reject puts a removed block back, with its connection when that is rejected too.
    await user.click(
      within(panel()).getByRole("button", { name: "Reject the change to block exit" }),
    );
    await settled(toolbar);
    await user.click(
      within(panel()).getByRole("button", { name: "Reject the change to connection till.out" }),
    );
    await settled(toolbar);
    await drawn("exit");
    expect(service.model.connections).toEqual(coffeeShop().connections);
  });

  it("accepts without writing, one change or all, and Reject all restores every change", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await settled(toolbar);
    await outsideWrite(fake, service);
    await settled(toolbar);
    const writes = fake.requests.filter((request) => request.method !== "GET").length;
    await user.click(
      within(panel()).getByRole("button", { name: "Accept the change to block queue_1" }),
    );
    expect(within(toolbar).getByRole("button", { name: "3 changes to review" })).toBeVisible();
    expect(node("queue_1").querySelector(".block")).not.toHaveClass("block-mark");
    await user.click(within(panel()).getByRole("button", { name: "Reject all" }));
    await settled(toolbar);
    expect(fake.requests.filter((request) => request.method !== "GET").length).toBeGreaterThan(
      writes,
    );
    const back = coffeeShop();
    back.components?.push({ id: "queue_1", type: "queue", params: {}, ui: { x: 0, y: 300 } });
    expect(service.model).toEqual(back);
    expect(within(toolbar).queryByRole("button", { name: /changes? to review/ })).toBeNull();

    await outsideWrite(fake, service, "mcp");
    expect(screen.getByText(/changed by an assistant \(mcp\)/)).toBeVisible();
    await user.click(within(panel()).getByRole("button", { name: "Accept all" }));
    expect(within(toolbar).queryByRole("button", { name: /changes? to review/ })).toBeNull();
    expect(document.querySelector(".react-flow__node-ghost")).toBeNull();
  });

  it("shows a changed block's fields, old beside new, when it is selected", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await settled(toolbar);
    await outsideWrite(fake, service);
    await select(user, "till");
    const review = within(panel()).getByRole("region", { name: /by another client/ });
    expect(review).toHaveTextContent("capacity: tills → 2");
    await user.click(
      within(review).getByRole("button", { name: "Accept the change to block till" }),
    );
    expect(within(panel()).queryByRole("region", { name: /by another client/ })).toBeNull();
  });

  it("refuses Accept and Reject while a write awaits its answer, and says so", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await settled(toolbar);
    await outsideWrite(fake, service);
    await settled(toolbar);
    const release = fake.holdWrites();
    await user.click(
      within(panel()).getByRole("button", { name: "Reject the change to block till" }),
    );
    const accept = within(panel()).getByRole("button", {
      name: "Accept the change to block queue_1",
    });
    await waitFor(() => expect(accept).toHaveAttribute("aria-disabled", "true"));
    await user.click(accept);
    expect(screen.getByText(WAIT)).toBeVisible();
    expect(within(toolbar).getByRole("button", { name: "4 changes to review" })).toBeVisible();
    release();
    await settled(toolbar);
    expect(fake.requested("PUT", MODEL)).toHaveLength(1);
    expect(within(toolbar).getByRole("button", { name: "3 changes to review" })).toBeVisible();
  });

  it("says a change was not saved when it raced another client's (409 E181)", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await select(user, "till");
    await settled(toolbar);
    service.outsideWrite((model) => {
      model.meta = { name: "Cafe" };
    });
    await user.type(screen.getByRole("textbox", { name: "Label (optional)" }), "A{Enter}");
    expect(
      await screen.findByText(
        "Your last change was not saved because the model had just been changed by another program. Please make it again.",
      ),
    ).toBeVisible();
    act(() => fake.sockets[0]?.emit({ type: "model", revision: service.revision, client: "ui" }));
    expect(screen.getByText(/had just been changed in another window \(ui\)/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText(/had just been changed/)).toBeNull();
    expect(within(toolbar).getByRole("button", { name: "1 change to review" })).toBeVisible();
  });

  it("marks, rejects and accepts parameters named like Object.prototype's members (review of PR #46)", async () => {
    const model = coffeeShop();
    model.components?.push({ id: "odd", type: "constructor", params: {}, ui: { x: 0, y: 300 } });
    const { fake, service, toolbar, user } = renderCanvas({ model });
    await settled(toolbar);
    expect(node("odd")).toHaveAttribute("aria-label", "odd, constructor");
    service.outsideWrite((written) => {
      written.parameters = JSON.parse(
        `{"tills": {"value": 1, "type": "integer", "min": 1, "max": 5},
          "constructor": {"value": 1, "type": "integer"}, "__proto__": {"value": 2, "type": "integer"},
          "toString": {"value": 3, "type": "integer"}, "hasOwnProperty": {"value": 4, "type": "integer"}}`,
      );
    });
    act(() => fake.sockets[0]?.emit({ type: "model", revision: service.revision, client: "mcp" }));
    const list = await within(panel()).findByRole("region", { name: "4 changes to review" });
    expect(within(list).getByText("Added: parameter __proto__")).toBeVisible();
    await user.click(
      within(list).getByRole("button", { name: "Reject the change to parameter constructor" }),
    );
    await settled(toolbar);
    expect(Object.hasOwn(service.model.parameters ?? {}, "constructor")).toBe(false);
    expect(Object.hasOwn(service.model.parameters ?? {}, "__proto__")).toBe(true);
    await user.click(
      within(panel()).getByRole("button", { name: "Reject the change to parameter __proto__" }),
    );
    await settled(toolbar);
    expect(Object.keys(service.model.parameters ?? {})).toEqual([
      "tills",
      "toString",
      "hasOwnProperty",
    ]);
    await user.click(within(panel()).getByRole("button", { name: "Accept all" }));
    expect(within(toolbar).queryByRole("button", { name: /changes? to review/ })).toBeNull();
  });
});

describe("Try a change (AKS-120)", () => {
  it("makes the field a parameter and adds the option beside the current model, in one write", async () => {
    const { fake, service, toolbar, user } = renderCanvas();
    await select(user, "till");
    await settled(toolbar);
    await user.click(screen.getByRole("button", { name: "Try a change to Mean" }));
    const form = screen.getByRole("form", { name: "Try a change to Mean" });
    const tried = within(form).getByRole("textbox", { name: "What value do you want to try?" });
    expect(tried).toHaveValue("1.5 min");
    await user.clear(tried);
    await user.type(tried, "1.2 min");
    await user.type(
      within(form).getByRole("textbox", { name: "Name for the option" }),
      "Faster coffee machine",
    );
    await user.click(within(form).getByRole("button", { name: "Add the option" }));
    await settled(toolbar);
    expect(sentEdits(fake).at(-1)).toEqual([
      { edit: "set_parameter", id: "till_service_mean", value: "1.5 min", type: "quantity" },
      {
        edit: "set_setting",
        id: "till",
        path: "/service/mean",
        value: { $param: "till_service_mean" },
      },
      { edit: "set_scenario", experiment_id: "base", id: "baseline", set: {} },
      {
        edit: "set_scenario",
        experiment_id: "base",
        id: "faster_coffee_machine",
        set: { till_service_mean: "1.2 min" },
      },
    ]);
    expect(service.model.experiments?.[0]?.scenarios).toHaveLength(2);
    // The form went with the model it was filled against; the field now uses the parameter.
    expect(screen.queryByRole("form", { name: "Try a change to Mean" })).toBeNull();
    expect(screen.getByText("= till_service_mean")).toBeVisible();
    expect(screen.getByText(/Added an option to experiment base/)).toBeVisible();
    expect(
      within(toolbar).getByRole("button", { name: "Undo: try a change to till/service/mean" }),
    ).toBeEnabled();
  });

  it("is refused while a write awaits its answer, and says what to do without an experiment", async () => {
    const model = coffeeShop();
    const { fake, toolbar, user } = renderCanvas({ model });
    await select(user, "till");
    await settled(toolbar);
    await user.click(screen.getByRole("button", { name: "Try a change to Mean" }));
    const release = fake.holdWrites();
    await user.click(screen.getByRole("checkbox", { name: "Use parameter for Capacity" }));
    await user.click(screen.getByRole("button", { name: "Add the option" }));
    expect(screen.getByText(WAIT)).toBeVisible();
    release();
    await settled(toolbar);
    const noExperiment = coffeeShop();
    noExperiment.experiments = [];
    cleanup();
    const second = renderCanvas({ model: noExperiment });
    await select(second.user, "till");
    await settled(second.toolbar);
    await second.user.click(screen.getByRole("button", { name: "Try a change to Mean" }));
    expect(screen.getByText("The model has no experiment to add the option to.")).toBeVisible();
    await second.user.click(screen.getByRole("button", { name: "Add the option" }));
    expect(screen.getByText(/Add an experiment on the Experiment screen first/)).toBeVisible();
    expect(second.fake.requested("POST", `/v1/projects/${PID}/model/edits`)).toHaveLength(0);
  });
});
