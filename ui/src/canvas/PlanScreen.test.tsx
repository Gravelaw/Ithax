/**
 * The Canvas screen of an optimization model (spec 3 "Canvas behaviour", Optimization
 * models; `docs/design/wireframes/09-optimization.svg`), against the fake service.
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Issue, Model, Project } from "../api/types";
import { SettingsProvider } from "../settings/SettingsContext";
import { ModelService, PID } from "../test/fakeModel";
import { FakeService, SETTINGS } from "../test/fakes";
import { CanvasScreen, WAIT } from "./CanvasScreen";

const PROJECT: Project = {
  id: PID,
  name: "Mix",
  created: "2026-11-08T10:00:00Z",
  layout_version: 1,
  model_revision: 0,
  path: "/p1",
  available: true,
};
const EDITS = `/v1/projects/${PID}/model/edits`;

function plan(): Model {
  return {
    format_version: "0.1",
    meta: { name: "Mix" },
    domain: "optimization",
    variables: [],
    objective: { sense: "maximize", linear: {} },
    constraints: [],
    run: { target: "local", fidelity: "standard" },
  };
}

function mix(): Model {
  return {
    ...plan(),
    variables: [
      { id: "chairs", type: "continuous", lower: 0 },
      { id: "tables", type: "continuous", lower: 0 },
    ],
    objective: { sense: "maximize", linear: { chairs: 45, tables: 80 } },
    constraints: [
      { id: "wood", linear: { chairs: 5, tables: 20 }, op: "<=", rhs: 400 },
      { id: "labour", linear: { chairs: 10, tables: 15 }, op: "<=", rhs: 450 },
    ],
  };
}

function renderPlan(model: Model = plan(), validate?: (model: Model) => Issue[]) {
  const fake = new FakeService();
  const service = new ModelService(fake, { model, revision: 1, ...(validate ? { validate } : {}) });
  const go = vi.fn();
  const client = fake.client();
  const toolbar = document.createElement("div");
  document.body.append(toolbar);
  render(
    <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
      <CanvasScreen client={client} project={PROJECT} toolbar={toolbar} onGo={go} />
    </SettingsProvider>,
  );
  return { fake, service, go, toolbar, user: userEvent.setup() };
}

async function settled(toolbar: HTMLElement) {
  await waitFor(() => expect(within(toolbar).getByRole("status")).toHaveTextContent("Saved"));
  const counts = within(screen.getByRole("region", { name: "Problems" })).getByRole("status");
  await waitFor(() => expect(counts).not.toHaveTextContent("Checking"));
}

function lastEdits(fake: FakeService): unknown {
  const body = fake.requested("POST", EDITS).at(-1)?.body as { edits: unknown } | undefined;
  return body?.edits;
}

const box = (name: string) => screen.getByRole("textbox", { name });

describe("the Table view of a plan", () => {
  it("opens first, with Decisions, the Goal and Limits, and no experiment picker", async () => {
    const { toolbar } = renderPlan(mix());
    expect(await screen.findByRole("heading", { name: /^Decisions/ })).toBeVisible();
    expect(screen.getByRole("heading", { name: /^Goal/ })).toBeVisible();
    expect(screen.getByRole("heading", { name: /^Limits/ })).toBeVisible();
    expect(screen.getByRole("button", { name: "Table" })).toHaveAttribute("aria-pressed", "true");
    expect(box("Name of decision 1")).toHaveValue("chairs");
    expect(box("Coefficient of tables in wood")).toHaveValue("20");
    expect(screen.getByText("Maximize 45 × chairs + 80 × tables")).toBeVisible();
    await settled(toolbar);
    expect(within(toolbar).queryByRole("combobox")).toBeNull();
    expect(within(toolbar).getByRole("button", { name: "Run" })).not.toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("adds a decision and edits its name, kind, bound and goal coefficient", {
    timeout: 20_000,
  }, async () => {
    const { fake, toolbar, user } = renderPlan();
    await settled(toolbar);
    await user.click(screen.getByRole("button", { name: "Add decision" }));
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_path", path: "/variables/-", value: { id: "decision_1", type: "continuous" } },
    ]);
    // The new row's name takes the focus.
    await waitFor(() => expect(box("Name of decision 1")).toHaveFocus());
    await user.clear(box("Name of decision 1"));
    await user.type(box("Name of decision 1"), "chairs{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_path", path: "/variables/0/id", value: "chairs" },
    ]);
    await user.selectOptions(screen.getByRole("combobox", { name: "Kind of chairs" }), "integer");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_path", path: "/variables/0/type", value: "integer" },
    ]);
    await user.type(box("Lower bound of chairs"), "0{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([{ edit: "set_path", path: "/variables/0/lower", value: 0 }]);
    await user.type(box("Coefficient of chairs in the goal"), "45{Enter}");
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_path", path: "/objective/linear/chairs", value: 45 },
    ]);
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Maximize or minimize" }),
      "minimize",
    );
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      { edit: "set_path", path: "/objective/sense", value: "minimize" },
    ]);
  });

  it("adds a limit and edits its coefficient, how it must hold and its limit", {
    timeout: 20_000,
  }, async () => {
    const model = plan();
    model.variables = [{ id: "chairs", type: "continuous" }];
    const { fake, service, toolbar, user } = renderPlan(model);
    await settled(toolbar);
    await user.click(screen.getByRole("button", { name: "Add limit" }));
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([
      {
        edit: "set_path",
        path: "/constraints/-",
        value: { id: "limit_1", linear: {}, op: "<=", rhs: 0 },
      },
    ]);
    await user.type(box("Coefficient of chairs in limit_1"), "5{Enter}");
    await settled(toolbar);
    await user.selectOptions(screen.getByRole("combobox", { name: "How limit_1 must hold" }), ">=");
    await settled(toolbar);
    await user.clear(box("Limit of limit_1"));
    await user.type(box("Limit of limit_1"), "400{Enter}");
    await settled(toolbar);
    expect(service.model.constraints).toEqual([
      { id: "limit_1", linear: { chairs: 5 }, op: ">=", rhs: 400 },
    ]);
  });

  it("clears an optional field, renames and removes with the coefficients, and undoes", {
    timeout: 20_000,
  }, async () => {
    const { fake, service, toolbar, user } = renderPlan(mix());
    await settled(toolbar);
    await user.clear(box("Lower bound of chairs"));
    await user.tab();
    await settled(toolbar);
    expect(lastEdits(fake)).toEqual([{ edit: "remove_path", path: "/variables/0/lower" }]);
    await user.clear(box("Name of decision 1"));
    await user.type(box("Name of decision 1"), "seats{Enter}");
    await settled(toolbar);
    expect(service.model.objective).toEqual({
      sense: "maximize",
      linear: { seats: 45, tables: 80 },
    });
    expect((service.model.constraints as { linear: unknown }[])[0]?.linear).toEqual({
      seats: 5,
      tables: 20,
    });
    await user.click(screen.getByRole("button", { name: "Remove decision seats" }));
    await settled(toolbar);
    expect((service.model.variables as { id: string }[]).map((item) => item.id)).toEqual([
      "tables",
    ]);
    expect(service.model.objective).toEqual({ sense: "maximize", linear: { tables: 80 } });
    await user.click(screen.getByRole("button", { name: "Remove limit wood" }));
    await settled(toolbar);
    expect((service.model.constraints as { id: string }[]).map((item) => item.id)).toEqual([
      "labour",
    ]);
    await user.click(within(toolbar).getByRole("button", { name: "Undo: remove wood" }));
    await settled(toolbar);
    expect(service.model.constraints).toHaveLength(2);
  });

  it("shows the service's issues at the field their path names, and from the problems list", async () => {
    const issue: Issue = {
      code: "E175",
      severity: "error",
      component: null,
      path: "/constraints/0/linear/desks",
      message: "'desks' names no variable.",
      hint: null,
    };
    const typeIssue: Issue = {
      code: "E120",
      severity: "error",
      component: null,
      path: "/variables/0/type",
      message: "'type' must be continuous, integer or binary.",
      hint: null,
    };
    const model = mix();
    model.variables = [
      { id: "chairs", type: "real" },
      { id: "tables", type: "continuous", lower: 0 },
    ];
    model.constraints = [
      { id: "wood", linear: { chairs: 5, tables: 20, desks: 1 }, op: "<=", rhs: 400 },
    ];
    const { toolbar, user } = renderPlan(model, () => [typeIssue, issue]);
    await settled(toolbar);
    const kind = screen.getByRole("combobox", { name: "Kind of chairs" });
    expect(kind).toHaveValue("real");
    expect(kind.closest("td")).toHaveTextContent(
      "E120 'type' must be continuous, integer or binary.",
    );
    // A coefficient for no decision has no field: it shows under its row.
    expect(box("Name of limit 1").closest("tr")?.nextElementSibling).toHaveTextContent(
      "E175 'desks' names no variable.",
    );
    expect(within(toolbar).getByText("2 errors. Fix them to run.")).toBeVisible();
    const problems = screen.getByRole("region", { name: "Problems" });
    await user.click(within(problems).getByRole("button", { name: /E175/ }));
    await waitFor(() => expect(box("Name of limit 1")).toHaveFocus());
  });

  it("refuses a commit while a write awaits its answer, and says so", async () => {
    const { fake, toolbar, user } = renderPlan(mix());
    await settled(toolbar);
    const release = fake.holdWrites();
    await user.click(screen.getByRole("button", { name: "Add limit" }));
    await user.clear(box("Limit of wood"));
    await user.type(box("Limit of wood"), "500{Enter}");
    expect(screen.getByText(WAIT)).toBeVisible();
    expect(box("Limit of wood")).toHaveValue("400");
    release();
    await settled(toolbar);
    expect(fake.requested("POST", EDITS)).toHaveLength(1);
  });
});

describe("the Diagram view", () => {
  it("draws decision cards linked to the goal and limits by their coefficients", async () => {
    const { toolbar, user } = renderPlan(mix());
    await settled(toolbar);
    await user.click(screen.getByRole("button", { name: "Diagram" }));
    expect(screen.getByRole("button", { name: "chairs decision, continuous ≥ 0" })).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Goal Maximize 45 × chairs + 80 × tables" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "wood 5 × chairs + 20 × tables ≤ 400" }),
    ).toBeVisible();
    expect(document.querySelectorAll(".plan-line")).toHaveLength(6);
    expect(
      [...document.querySelectorAll(".plan-line-text")].map((label) => label.textContent),
    ).toEqual(["45", "80", "5", "20", "10", "15"]);
    await user.click(screen.getByRole("button", { name: /^labour/ }));
    await waitFor(() => expect(box("Name of limit 2")).toHaveFocus());
  });
});

describe("an outside change to a plan", () => {
  it("names the client and marks the rows, with Accept and Reject", async () => {
    const { fake, service, toolbar, user } = renderPlan(mix());
    await settled(toolbar);
    service.outsideWrite((model) => {
      (model.variables as unknown[]).push({ id: "stools", type: "integer" });
      model.constraints = (model.constraints as { id: string }[]).filter(
        (item) => item.id !== "labour",
      );
      (model.objective as { sense: string }).sense = "minimize";
    });
    act(() => fake.sockets[0]?.emit({ type: "model", revision: service.revision, client: "mcp" }));
    expect(await screen.findByText(/The model was changed by an assistant \(mcp\)/)).toBeVisible();
    expect(within(toolbar).getByRole("button", { name: "3 changes to review" })).toBeVisible();
    expect(box("Name of decision 3").closest("tr")).toHaveClass("mark-added");
    expect(screen.getByRole("region", { name: /^Goal/ })).toHaveClass("mark-changed");
    const list = screen.getByRole("region", { name: "3 changes to review" });
    expect(within(list).getByText("Removed: limit labour")).toBeVisible();
    await user.click(
      within(list).getByRole("button", { name: "Reject the change to limit labour" }),
    );
    await settled(toolbar);
    expect((service.model.constraints as { id: string }[]).map((item) => item.id)).toEqual([
      "wood",
      "labour",
    ]);
    await user.click(within(list).getByRole("button", { name: "Accept the change to the goal" }));
    expect(within(toolbar).getByRole("button", { name: "1 change to review" })).toBeVisible();
  });
});
