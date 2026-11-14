/**
 * The Experiment screen (spec 3 "Screens" 4; `docs/design/wireframes/04-experiment.svg`)
 * against the fake service: each control sends its model edit through the session, under
 * the Canvas's rules (one write at a time, drafts gone with the model shown, outside
 * changes reviewed).
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Model, Project } from "../api/types";
import { WAIT_MODEL } from "../canvas/ModelFrame";
import { SettingsProvider } from "../settings/SettingsContext";
import { coffeeShop, ModelService, PID } from "../test/fakeModel";
import { errorBody, FakeService, issue, SETTINGS } from "../test/fakes";
import { ExperimentScreen } from "./ExperimentScreen";

const PROJECT: Project = {
  id: PID,
  name: "Coffee shop",
  created: "2026-11-08T10:00:00Z",
  layout_version: 1,
  model_revision: 0,
  path: "/p1",
  available: true,
};
const EDITS = `/v1/projects/${PID}/model/edits`;
const MODEL = `/v1/projects/${PID}/model`;

function renderScreen(model: Model = coffeeShop(), options: { project?: Project | null } = {}) {
  const fake = new FakeService();
  const service = new ModelService(fake, { model, revision: 1 });
  const go = vi.fn();
  const client = fake.client();
  const toolbar = document.createElement("div");
  document.body.append(toolbar);
  render(
    <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
      <ExperimentScreen
        client={client}
        project={options.project === undefined ? PROJECT : options.project}
        toolbar={toolbar}
        onGo={go}
      />
    </SettingsProvider>,
  );
  return { fake, service, go, toolbar, user: userEvent.setup() };
}

async function settled(toolbar: HTMLElement) {
  await waitFor(() => expect(within(toolbar).getByRole("status")).toHaveTextContent("Saved"));
}

function lastEdits(fake: FakeService): unknown {
  const body = fake.requested("POST", EDITS).at(-1)?.body as { edits: unknown } | undefined;
  return body?.edits;
}

const box = (name: string) => screen.getByRole("textbox", { name });
const picker = (name: string) => screen.getByRole("combobox", { name });

describe("the run settings of an experiment", () => {
  it("sets the coffee shop's base experiment from a new project's, field by field", async () => {
    const { fake, service, toolbar, user } = renderScreen();
    expect(await screen.findByRole("heading", { name: "base" })).toBeVisible();
    await settled(toolbar);
    expect(box("Run length")).toHaveValue("8");
    expect(picker("Unit of Run length")).toHaveValue("h");
    await user.clear(box("Run length"));
    await user.type(box("Run length"), "200{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([{ edit: "set_experiment", id: "base", length: "200 h" }]);
    // A unit chosen for a saved time rewrites it in that unit.
    await user.selectOptions(picker("Unit of Settling-in time"), "h");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([{ edit: "set_experiment", id: "base", warmup: "0 h" }]);
    await user.clear(box("Settling-in time"));
    await user.type(box("Settling-in time"), "10{Enter}");
    await settled(toolbar);
    await user.type(box("Seed"), "12345{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([{ edit: "set_experiment", id: "base", seed: 12345 }]);
    expect(service.model.experiments).toEqual([
      { id: "base", length: "200 h", warmup: "10 h", replications: 30, seed: 12345 },
    ]);
  });

  it("names each field in plain words, with its technical term", async () => {
    const { toolbar } = renderScreen();
    await screen.findByRole("heading", { name: "base" });
    await settled(toolbar);
    expect(box("Repeat runs")).toHaveAccessibleDescription(/Replications/);
    expect(box("Settling-in time")).toHaveAccessibleDescription(/Warm-up/);
    expect(box("Sure of the likely range")).toHaveAccessibleDescription(/Confidence level/);
    expect(box("Seed")).toHaveAccessibleDescription(/Empty: chosen at random/);
  });

  it("writes numbers as numbers and other text as typed; clearing writes the whole model", async () => {
    const { fake, service, toolbar, user } = renderScreen();
    await screen.findByRole("heading", { name: "base" });
    await settled(toolbar);
    await user.type(box("Sure of the likely range"), "0.9{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([{ edit: "set_experiment", id: "base", confidence: 0.9 }]);
    await user.clear(box("Repeat runs"));
    await user.type(box("Repeat runs"), "ten{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([{ edit: "set_experiment", id: "base", replications: "ten" }]);
    // An empty time keeps the unit chosen until its number is committed.
    await user.selectOptions(picker("Unit of Record interval"), "min");
    expect(fake.requested("POST", EDITS)).toHaveLength(2);
    await user.type(box("Record interval"), "5{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_experiment", id: "base", record_interval: "5 min" },
    ]);
    // No edit removes a field: clearing one writes the whole model without it.
    await user.clear(box("Sure of the likely range"));
    await user.tab();
    await settled(toolbar);
    const put = fake.requested("PUT", MODEL).at(-1);
    expect(put?.search).toBe("?base_revision=4");
    expect(service.model.experiments?.[0]).not.toHaveProperty("confidence");
    expect(
      within(toolbar).getByRole("button", { name: "Undo: clear confidence of experiment base" }),
    ).toBeEnabled();
    // A required field left empty sends nothing, and shows its saved value again.
    const writes = fake.requests.filter((request) => !request.path.endsWith("/validate")).length;
    await user.clear(box("Run length"));
    await user.tab();
    expect(box("Run length")).toHaveValue("8");
    expect(fake.requests.filter((request) => !request.path.endsWith("/validate"))).toHaveLength(
      writes,
    );
  });

  it("shows a time of another form as text, and the service's issues at the field", async () => {
    const model = coffeeShop();
    model.experiments = [{ id: "base", length: "8 hours", replications: 1 }];
    const fake = new FakeService();
    new ModelService(fake, {
      model,
      revision: 1,
      validate: () => [
        issue("E141", "'8 hours' is not a quantity.", "/experiments/0/length"),
        issue("E170", "replications must be at least 2.", "/experiments/0/replications"),
      ],
    });
    const client = fake.client();
    const toolbar = document.createElement("div");
    render(
      <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
        <ExperimentScreen client={client} project={PROJECT} toolbar={toolbar} onGo={vi.fn()} />
      </SettingsProvider>,
    );
    expect(await screen.findByText("'8 hours' is not a quantity.")).toBeVisible();
    expect(box("Run length")).toHaveValue("8 hours");
    expect(screen.queryByRole("combobox", { name: "Unit of Run length" })).toBeNull();
    expect(screen.getByText("replications must be at least 2.")).toBeVisible();
    expect(box("Repeat runs")).toHaveAttribute("aria-invalid", "true");
  });
});

describe("the experiments list", () => {
  it("adds, chooses and removes an experiment", async () => {
    const { fake, service, toolbar, user } = renderScreen();
    await screen.findByRole("heading", { name: "base" });
    await settled(toolbar);
    await user.type(box("New experiment id"), "long");
    await user.click(screen.getByRole("button", { name: "Add experiment" }));
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([{ edit: "set_experiment", id: "long" }]);
    expect(await screen.findByRole("heading", { name: "long" })).toBeVisible();
    expect(box("New experiment id")).toHaveValue("");
    // An id the model already has is not added over it.
    await user.type(box("New experiment id"), "long");
    await user.click(screen.getByRole("button", { name: "Add experiment" }));
    expect(screen.getByText("The model already has an experiment long.")).toBeVisible();
    expect(fake.requested("POST", EDITS)).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "base" }));
    expect(screen.getByRole("heading", { name: "base" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Remove experiment base" }));
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([{ edit: "remove_experiment", id: "base" }]);
    expect(service.model.experiments?.map((item) => item.id)).toEqual(["long"]);
    expect(screen.getByRole("heading", { name: "long" })).toBeVisible();
  });

  it("says so when the model has none", async () => {
    const model = coffeeShop();
    model.experiments = [];
    const { toolbar } = renderScreen(model);
    expect(await screen.findByText(/No experiments yet/)).toBeVisible();
    await settled(toolbar);
  });
});

describe("scenarios", () => {
  it("adds a scenario, sets a parameter in it, clears it and removes the scenario", async () => {
    const { fake, service, toolbar, user } = renderScreen();
    await screen.findByRole("heading", { name: "base" });
    await settled(toolbar);
    expect(
      screen.getByText(/No scenarios: the experiment runs the model as written/),
    ).toBeVisible();
    await user.type(box("New scenario id"), "two_tills");
    await user.click(screen.getByRole("button", { name: "Add scenario" }));
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_scenario", experiment_id: "base", id: "two_tills", set: {} },
    ]);
    // One column per parameter; an empty cell shows the parameter's value.
    expect(box("tills in two_tills")).toHaveAttribute("placeholder", "1");
    await user.type(box("tills in two_tills"), "2{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_scenario", experiment_id: "base", id: "two_tills", set: { tills: 2 } },
    ]);
    await user.clear(box("tills in two_tills"));
    await user.tab();
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_scenario", experiment_id: "base", id: "two_tills", set: {} },
    ]);
    // An id the experiment already has is not added again over it.
    await user.type(box("New scenario id"), "two_tills");
    await user.click(screen.getByRole("button", { name: "Add scenario" }));
    expect(screen.getByText("The experiment already has a scenario two_tills.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Remove scenario two_tills" }));
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "remove_scenario", experiment_id: "base", id: "two_tills" },
    ]);
    expect(service.model.experiments?.[0]?.scenarios).toEqual([]);
  });

  it("shows the service's refusal of an edit as its issue", async () => {
    const { fake, toolbar, user } = renderScreen();
    await screen.findByRole("heading", { name: "base" });
    await settled(toolbar);
    fake.answer(
      `POST ${EDITS}`,
      errorBody("E180", "The scenario 'x' sets 'nope'.", [
        issue("E180", "The scenario 'x' sets 'nope'.", "/edits/0"),
      ]),
      400,
    );
    await user.type(box("New scenario id"), "x");
    await user.click(screen.getByRole("button", { name: "Add scenario" }));
    expect(await screen.findByText("The scenario 'x' sets 'nope'.")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("E180");
  });
});

describe("objectives, constraints and the search", () => {
  it("adds an objective and a constraint and edits each field", { timeout: 20_000 }, async () => {
    const { fake, service, toolbar, user } = renderScreen();
    await screen.findByRole("heading", { name: "base" });
    await settled(toolbar);
    await user.click(screen.getByRole("button", { name: "Add objective" }));
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      {
        edit: "set_path",
        path: "/objectives",
        value: [{ id: "objective_1", metric: "arrivals.created", sense: "minimize" }],
      },
    ]);
    await user.selectOptions(picker("Metric of objective objective_1"), "till.wait.mean");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_path", path: "/objectives/0/metric", value: "till.wait.mean" },
    ]);
    await user.selectOptions(picker("Goal of objective objective_1"), "maximize");
    await settled(toolbar);
    await user.clear(box("Name of objective 1"));
    await user.type(box("Name of objective 1"), "wait{Enter}");
    await settled(toolbar);
    expect(service.model.objectives).toEqual([
      { id: "wait", metric: "till.wait.mean", sense: "maximize" },
    ]);
    await user.click(screen.getByRole("button", { name: "Add constraint" }));
    await settled(toolbar);
    await user.selectOptions(picker("Must be, for constraint constraint_1"), ">=");
    await settled(toolbar);
    await user.clear(box("Value of constraint constraint_1"));
    await user.type(box("Value of constraint constraint_1"), "5 min{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_path", path: "/constraints/0/value", value: "5 min" },
    ]);
    // A rate with its unit is sent as written (#77; format 0.3).
    await user.clear(box("Value of constraint constraint_1"));
    await user.type(box("Value of constraint constraint_1"), "30 1/h{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_path", path: "/constraints/0/value", value: "30 1/h" },
    ]);
    await user.clear(box("Value of constraint constraint_1"));
    await user.type(box("Value of constraint constraint_1"), "0.85{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_path", path: "/constraints/0/value", value: 0.85 },
    ]);
    await user.click(screen.getByRole("button", { name: "Remove constraint constraint_1" }));
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([{ edit: "remove_path", path: "/constraints/0" }]);
    await user.click(screen.getByRole("button", { name: "Remove objective wait" }));
    await settled(toolbar);
    expect(service.model.objectives).toEqual([]);
  });

  it("turns the search on and sets its objective, budget, repeat runs and parameters", {
    timeout: 20_000,
  }, async () => {
    const model = coffeeShop();
    model.objectives = [
      { id: "wait", metric: "till.wait.mean", sense: "minimize" },
      { id: "busy", metric: "till.utilization", sense: "maximize" },
    ];
    const { fake, service, toolbar, user } = renderScreen(model);
    await screen.findByRole("heading", { name: "base" });
    await settled(toolbar);
    await user.click(
      screen.getByRole("checkbox", { name: "Search for the best parameter values" }),
    );
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_path", path: "/experiments/0/search", value: { objective: "wait" } },
    ]);
    await user.selectOptions(picker("Objective of the search"), "busy");
    await settled(toolbar);
    await user.type(box("Budget"), "20{Enter}");
    await settled(toolbar);
    await user.type(box("Repeat runs each"), "5{Enter}");
    await settled(toolbar);
    await user.click(screen.getByRole("checkbox", { name: /tills from 1 to 5/ }));
    await settled(toolbar);
    expect(service.model.experiments?.[0]?.search).toEqual({
      objective: "busy",
      budget: 20,
      replications: 5,
      variables: ["tills"],
    });
    await user.click(screen.getByRole("checkbox", { name: /tills from 1 to 5/ }));
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "remove_path", path: "/experiments/0/search/variables" },
    ]);
    await user.clear(box("Budget"));
    await user.tab();
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "remove_path", path: "/experiments/0/search/budget" },
    ]);
    await user.click(
      screen.getByRole("checkbox", { name: "Search for the best parameter values" }),
    );
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([{ edit: "remove_path", path: "/experiments/0/search" }]);
    expect(service.model.experiments?.[0]).not.toHaveProperty("search");
  });
});

describe("the one-write rule and outside changes", () => {
  it("refuses a change while a write awaits its answer, and says so", async () => {
    const { fake, toolbar, user } = renderScreen();
    await screen.findByRole("heading", { name: "base" });
    await settled(toolbar);
    const release = fake.holdWrites();
    await user.type(box("Seed"), "1{Enter}");
    await waitFor(() => expect(within(toolbar).getByRole("status")).toHaveTextContent("Saving"));
    await user.clear(box("Run length"));
    await user.type(box("Run length"), "9{Enter}");
    expect(screen.getByText(WAIT_MODEL)).toBeVisible();
    expect(box("Run length")).toHaveValue("8");
    expect(screen.getByRole("button", { name: "Add scenario" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    release();
    await settled(toolbar);
    expect(fake.requested("POST", EDITS)).toHaveLength(1);
  });

  it("reloads after another client's write, names it and lists the changes to review", async () => {
    const { fake, service, toolbar, user } = renderScreen();
    await screen.findByRole("heading", { name: "base" });
    await settled(toolbar);
    await user.type(box("New scenario id"), "draft");
    service.outsideWrite((model) => {
      (model.experiments?.[0] as Record<string, unknown>).replications = 50;
    });
    act(() => fake.sockets[0]?.emit({ type: "model", revision: service.revision, client: "mcp" }));
    expect(
      await screen.findByText(
        "The model was changed by an assistant (mcp). The model has been reloaded; undo history was cleared.",
      ),
    ).toBeVisible();
    expect(box("Repeat runs")).toHaveValue("50");
    // The draft went with the model it was typed against.
    expect(box("New scenario id")).toHaveValue("");
    expect(within(toolbar).getByRole("button", { name: "1 change to review" })).toBeVisible();
    const list = screen.getByRole("region", { name: "1 change to review" });
    await user.click(within(list).getByRole("button", { name: /^Reject the change/ }));
    await settled(toolbar);
    expect(service.model.experiments?.[0]?.replications).toBe(30);
    expect(screen.queryByRole("region", { name: /change to review/ })).toBeNull();
    // Undo and redo name their step.
    await user.click(within(toolbar).getByRole("button", { name: /^Undo: reject/ }));
    await settled(toolbar);
    expect(service.model.experiments?.[0]?.replications).toBe(50);
    await user.click(within(toolbar).getByRole("button", { name: /^Redo: reject/ }));
    await settled(toolbar);
    expect(service.model.experiments?.[0]?.replications).toBe(30);
  });
});

describe("other models and states", () => {
  it("says a plan has no experiments, and goes to the canvas", async () => {
    const model: Model = {
      format_version: "0.1",
      meta: { name: "Mix" },
      domain: "optimization",
      variables: [],
      objective: { sense: "maximize", linear: {} },
      constraints: [],
    };
    const { go, user } = renderScreen(model);
    expect(await screen.findByText(/A plan has no experiments/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Go to the canvas" }));
    expect(go).toHaveBeenCalledWith({ screen: "canvas", projectId: PID });
  });

  it("waits for its project, and shows why the model cannot be read", async () => {
    renderScreen(coffeeShop(), { project: null });
    expect(screen.getByText("Opening the project…")).toBeVisible();
    const fake = new FakeService().answer(
      `GET ${MODEL}`,
      errorBody("E186", "The project cannot be read.", []),
      400,
    );
    const client = fake.client();
    render(
      <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
        <ExperimentScreen client={client} project={PROJECT} toolbar={null} onGo={vi.fn()} />
      </SettingsProvider>,
    );
    expect(await screen.findByText("The project cannot be read.")).toBeVisible();
  });
});
