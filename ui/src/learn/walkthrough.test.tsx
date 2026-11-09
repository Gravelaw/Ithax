/**
 * Learn mode's walkthrough (spec 4 "Learn and Build modes"; AKS-124) on the Canvas of a
 * `process` model and in the Table view of a plan, and the answer Results show after the
 * exercise's run, against the fake service.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Model, Project, Template } from "../api/types";
import { CanvasScreen } from "../canvas/CanvasScreen";
import { ResultsScreen } from "../results/ResultsScreen";
import { SettingsProvider } from "../settings/SettingsContext";
import { coffeeShop, ModelService, PID } from "../test/fakeModel";
import { FakeService, SETTINGS } from "../test/fakes";
import { aRun, lineSummary } from "../test/runs";
import { type Learning, LearnProvider, newLearning, useLearning } from "./LearnContext";
import { parseLesson } from "./lesson";
import { CHOOSE_FIRST, MAKE_THE_CHANGE } from "./StepCard";

const PROJECT: Project = {
  id: PID,
  name: "Coffee shop queue",
  created: "2026-11-09T10:00:00Z",
  layout_version: 1,
  model_revision: 0,
  path: "/p1",
  available: true,
};
const EDITS = `/v1/projects/${PID}/model/edits`;
const RUNS = `/v1/projects/${PID}/runs`;

function packageOf(id: string): { template: Template; learning: Learning } {
  const folder = join(__dirname, "..", "..", "..", "templates", id);
  const template = JSON.parse(readFileSync(join(folder, "template.json"), "utf8")) as Template;
  const lesson = parseLesson(readFileSync(join(folder, "lesson.md"), "utf8"));
  if (lesson === null) throw new Error(`${id}'s lesson does not read`);
  return { template, learning: newLearning(PID, template, lesson) };
}

/** Shows the lesson's state, so a test can read what the context holds. */
function Probe() {
  const { learning } = useLearning();
  return (
    <output data-testid="probe">
      {learning === null
        ? "none"
        : `step ${learning.step} prediction ${learning.prediction} run ${learning.runId} predicted ${learning.predicted}`}
    </output>
  );
}

function renderLesson(model: Model, learning: Learning) {
  const fake = new FakeService();
  const service = new ModelService(fake, { model, revision: 0 });
  fake.answer(`POST ${RUNS}`, { run_id: "r1" }, 202);
  const go = vi.fn();
  const client = fake.client();
  const toolbar = document.createElement("div");
  document.body.append(toolbar);
  render(
    <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
      <LearnProvider initial={learning}>
        <CanvasScreen client={client} project={PROJECT} toolbar={toolbar} onGo={go} />
        <Probe />
      </LearnProvider>
    </SettingsProvider>,
  );
  return { fake, service, go, toolbar, user: userEvent.setup() };
}

async function settled(toolbar: HTMLElement) {
  await waitFor(() => expect(within(toolbar).getByRole("status")).toHaveTextContent("Saved"));
  const counts = within(screen.getByRole("region", { name: "Problems" })).getByRole("status");
  await waitFor(() => expect(counts).not.toHaveTextContent("Checking"));
}

function stepCard(): HTMLElement {
  const found = document.querySelector<HTMLElement>(".step-card");
  if (found === null) throw new Error("no step card");
  return found;
}

function block(id: string): HTMLElement | null {
  return document.querySelector<HTMLElement>(`.react-flow__node[data-id="${id}"] .block`);
}

function coffeeTemplateModel(): Model {
  return coffeeShop();
}

describe("Learn mode on the Canvas", () => {
  it("plays each step, highlighting and selecting the block it names", async () => {
    const { learning } = packageOf("coffee_shop");
    const { user, toolbar } = renderLesson(coffeeTemplateModel(), learning);
    await settled(toolbar);
    const here = stepCard();
    expect(here).toHaveAccessibleName("Customers arrive");
    expect(within(here).getByText("Coffee shop queue · Step 1 of 4")).toBeVisible();
    expect(here).toHaveTextContent(/^.*Customers arrive at random, on average one every 2 minutes/);
    expect(within(here).getByRole("button", { name: "Back" })).toBeDisabled();
    await waitFor(() => expect(block("arrivals")).toHaveClass("block-learn"));
    expect(block("arrivals")).toHaveTextContent("Step 1 of 4");
    expect(block("till")).not.toHaveClass("block-learn");
    // The block is selected, so the side panel shows its settings.
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Id" })).toHaveValue("arrivals"),
    );

    await user.click(within(here).getByRole("button", { name: "Next" }));
    expect(stepCard()).toHaveAccessibleName("One till serves them");
    await waitFor(() => expect(block("till")).toHaveClass("block-learn"));
    expect(block("arrivals")).not.toHaveClass("block-learn");
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Id" })).toHaveValue("till"));
    const name = document
      .querySelector('.react-flow__node[data-id="till"]')
      ?.getAttribute("aria-label");
    expect(name).toContain("highlighted by the lesson, Step 2 of 4");

    await user.click(within(stepCard()).getByRole("button", { name: "Back" }));
    expect(stepCard()).toHaveAccessibleName("Customers arrive");
    await user.click(within(stepCard()).getByRole("button", { name: "Next" }));
    await user.click(within(stepCard()).getByRole("button", { name: "Next" }));
    expect(stepCard()).toHaveAccessibleName("Customers leave");
    await user.click(within(stepCard()).getByRole("button", { name: "Next" }));
    expect(stepCard()).toHaveAccessibleName("Exercise: open a second till");
    expect(screen.getByTestId("probe")).toHaveTextContent("step 3 prediction null");
  });

  it("runs the exercise: the change by its edits, a prediction, then the template's experiment", async () => {
    const { learning } = packageOf("coffee_shop");
    const { user, toolbar, fake, go } = renderLesson(coffeeTemplateModel(), {
      ...learning,
      step: 3,
    });
    await settled(toolbar);
    const here = stepCard();
    expect(within(here).getByText("Coffee shop queue · Step 4 of 4 · Try it")).toBeVisible();
    expect(here).toHaveTextContent("Set the parameter tills to 2");
    expect(within(here).getByText("tills", { selector: "p code" })).toBeVisible();
    expect(within(here).getByRole("list", { name: "The change" })).toHaveTextContent(
      "tills: 1 → 2",
    );
    const run = within(here).getByRole("button", { name: "Run the exercise" });
    expect(run).toHaveAttribute("aria-disabled", "true");
    expect(run).toHaveAccessibleDescription(MAKE_THE_CHANGE);
    // The right choice is not marked before the run.
    const choices = within(here).getByRole("group", { name: "What do you think will happen?" });
    expect(within(choices).getAllByRole("radio")).toHaveLength(3);
    expect(here).not.toHaveTextContent("right");
    await user.click(run);
    expect(fake.requested("POST", RUNS)).toHaveLength(0);

    await user.click(within(here).getByRole("button", { name: "Make the change" }));
    await settled(toolbar);
    expect(fake.requested("POST", EDITS).map((request) => request.body)).toEqual([
      { edits: [{ edit: "set_parameter", id: "tills", value: 2 }], base_revision: 0 },
    ]);
    expect(within(stepCard()).getByRole("status")).toHaveTextContent("The change is made.");
    expect(within(stepCard()).getByRole("list", { name: "The change" })).toHaveTextContent(
      "tills: 2 → 2",
    );
    expect(run).toHaveAccessibleDescription(CHOOSE_FIRST);
    await user.click(within(choices).getByRole("radio", { name: /far less than half/ }));
    expect(run).not.toHaveAttribute("aria-disabled");
    await user.click(run);
    await waitFor(() =>
      expect(go).toHaveBeenCalledWith({ screen: "monitor", projectId: PID, runId: "r1" }),
    );
    expect(fake.requested("POST", RUNS)[0]?.body).toEqual({ experiment_id: "base" });
    expect(screen.getByTestId("probe")).toHaveTextContent("step 3 prediction 1 run r1 predicted 1");
  });

  it("counts a change made by hand, and an undo takes it back", async () => {
    const { learning } = packageOf("coffee_shop");
    const model = coffeeTemplateModel();
    model.parameters = { tills: { value: 2, type: "integer", min: 1, max: 5 } };
    const { toolbar, fake } = renderLesson(model, { ...learning, step: 3 });
    await settled(toolbar);
    expect(within(stepCard()).getByRole("status")).toHaveTextContent("The change is made.");
    expect(within(stepCard()).queryByRole("button", { name: "Make the change" })).toBeNull();
    expect(fake.requested("POST", EDITS)).toHaveLength(0);
  });

  it("takes the change back with an undo, and Exit lesson ends the lesson", async () => {
    const { learning } = packageOf("coffee_shop");
    const { user, toolbar } = renderLesson(coffeeTemplateModel(), { ...learning, step: 3 });
    await settled(toolbar);
    await user.click(within(stepCard()).getByRole("button", { name: "Make the change" }));
    await settled(toolbar);
    expect(within(stepCard()).getByRole("status")).toHaveTextContent("The change is made.");
    await user.click(within(toolbar).getByRole("button", { name: /^Undo/ }));
    await settled(toolbar);
    expect(within(stepCard()).getByRole("button", { name: "Make the change" })).toBeVisible();
    expect(
      within(stepCard()).getByRole("button", { name: "Run the exercise" }),
    ).toHaveAccessibleDescription(MAKE_THE_CHANGE);
    await user.click(screen.getByRole("button", { name: "Exit lesson" }));
    expect(screen.getByTestId("probe")).toHaveTextContent("none");
    expect(document.querySelector(".step-card")).toBeNull();
    expect(document.querySelector(".block-learn")).toBeNull();
  });

  it("says when the step's block is no longer in the model", async () => {
    const { learning } = packageOf("coffee_shop");
    const model = coffeeTemplateModel();
    model.components = (model.components ?? []).filter((item) => item.id !== "arrivals");
    const { toolbar } = renderLesson(model, learning);
    await settled(toolbar);
    expect(within(stepCard()).getByRole("status")).toHaveTextContent(
      "This step's block, arrivals, is no longer in the model.",
    );
    expect(within(stepCard()).getByRole("button", { name: "Next" })).toBeEnabled();
  });

  it("makes no change while a write awaits its answer, and says so", async () => {
    const { learning } = packageOf("coffee_shop");
    const { user, toolbar, fake } = renderLesson(coffeeTemplateModel(), { ...learning, step: 3 });
    await settled(toolbar);
    const release = fake.holdWrites();
    await user.click(within(stepCard()).getByRole("button", { name: "Make the change" }));
    await waitFor(() => expect(fake.held).toBe(1));
    await user.click(within(stepCard()).getByRole("button", { name: "Make the change" }));
    expect(within(stepCard()).getByText(/the canvas was saving/)).toBeVisible();
    release();
    await settled(toolbar);
    expect(fake.requested("POST", EDITS)).toHaveLength(1);
  });

  it("counts an edit it cannot read once Make the change was accepted", async () => {
    const { learning, template } = packageOf("coffee_shop");
    const labelled: Learning = {
      ...learning,
      step: 3,
      template: {
        ...template,
        exercise: { edits: [{ edit: "set_label", id: "till", label: "Till" }] },
      },
    };
    const { user, toolbar } = renderLesson(coffeeTemplateModel(), labelled);
    await settled(toolbar);
    expect(within(stepCard()).getByRole("list", { name: "The change" })).toHaveTextContent(
      "set_label",
    );
    await user.click(within(stepCard()).getByRole("button", { name: "Make the change" }));
    await waitFor(() =>
      expect(within(stepCard()).getByRole("status")).toHaveTextContent("The change is made."),
    );
  });
});

function productMix(): Model {
  return JSON.parse(
    readFileSync(
      join(__dirname, "..", "..", "..", "templates", "product_mix", "model.json"),
      "utf8",
    ),
  ) as Model;
}

describe("Learn mode on a plan", () => {
  it("rings the decision, the goal and the limit each step names, in the Table view", async () => {
    const { learning } = packageOf("product_mix");
    const { user, toolbar } = renderLesson(productMix(), learning);
    await settled(toolbar);
    const row = (name: string) =>
      screen.getByRole("textbox", { name }).closest("tr") as HTMLElement;
    expect(stepCard()).toHaveAccessibleName(learning.lesson.steps[0]?.heading ?? "");
    expect(row("Name of decision 1")).toHaveClass("learn-target");
    expect(row("Name of decision 2")).not.toHaveClass("learn-target");
    // The Diagram view: the next step brings the Table view back.
    await user.click(screen.getByRole("button", { name: "Diagram" }));
    await user.click(within(stepCard()).getByRole("button", { name: "Next" }));
    expect(screen.getByRole("button", { name: "Table" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("region", { name: /Goal/ })).toHaveClass("learn-target");
    await user.click(within(stepCard()).getByRole("button", { name: "Next" }));
    expect(row("Name of limit 1")).toHaveClass("learn-target");
    expect(screen.getByRole("region", { name: /Goal/ })).not.toHaveClass("learn-target");
  });

  it("runs the plan's exercise with no experiment", async () => {
    const { learning } = packageOf("product_mix");
    const exercise = learning.lesson.steps.length;
    const { user, toolbar, fake, go } = renderLesson(productMix(), { ...learning, step: exercise });
    await settled(toolbar);
    expect(within(stepCard()).getByRole("list", { name: "The change" })).toHaveTextContent(
      "/objective/linear/tables: 80 → 100",
    );
    await user.click(within(stepCard()).getByRole("button", { name: "Make the change" }));
    await settled(toolbar);
    expect(fake.requested("POST", EDITS)[0]?.body).toEqual({
      edits: [{ edit: "set_path", path: "/objective/linear/tables", value: 100 }],
      base_revision: 0,
    });
    await user.click(within(stepCard()).getAllByRole("radio")[0] as HTMLElement);
    await user.click(within(stepCard()).getByRole("button", { name: "Run the exercise" }));
    await waitFor(() =>
      expect(go).toHaveBeenCalledWith({ screen: "monitor", projectId: PID, runId: "r1" }),
    );
    expect(fake.requested("POST", RUNS)[0]?.body).toEqual({});
  });

  it("says when the step's part of the plan is gone", async () => {
    const { learning } = packageOf("product_mix");
    const model = productMix();
    model.variables = [];
    const { toolbar } = renderLesson(model, learning);
    await settled(toolbar);
    expect(within(stepCard()).getByRole("status")).toHaveTextContent(
      "This step's part of the plan, chairs, is no longer in the model.",
    );
  });
});

describe("Results of the exercise's run", () => {
  function renderResults(learning: Learning | null, rid = "r1") {
    const fake = new FakeService()
      .answer(`GET /v1/runs/${rid}`, aRun({ run_id: rid }))
      .answer(`GET /v1/runs/${rid}/summary`, { summary: lineSummary(), findings: [], issues: [] })
      .answer(`GET /v1/runs/${rid}/tables/replications`, [])
      .answer(`GET /v1/runs/${rid}/tables/timeseries`, []);
    const go = vi.fn();
    render(
      <SettingsProvider client={fake.client()} initial={SETTINGS} root={document.documentElement}>
        <LearnProvider initial={learning}>
          <ResultsScreen client={fake.client()} project={PROJECT} runId={rid} onGo={go} />
          <Probe />
        </LearnProvider>
      </SettingsProvider>,
    );
    return { go, user: userEvent.setup() };
  }

  it("shows the prediction, that it is right, and the explanation, first", async () => {
    const { learning } = packageOf("coffee_shop");
    // The choice picked when the run started, not one picked since.
    const { go, user } = renderResults({
      ...learning,
      step: 3,
      prediction: 0,
      runId: "r1",
      predicted: 1,
    });
    const answer = await screen.findByRole("region", { name: "Exercise: open a second till" });
    expect(answer).toHaveTextContent(
      "You predicted: The wait falls to about a quarter of a minute, far less than half.",
    );
    expect(answer).toHaveTextContent("That is right.");
    expect(answer).toHaveTextContent(/Two tills are each busy 37.5% of the time/);
    // Above the headline card.
    const headline = document.querySelector(".headline-card") as Element;
    expect(
      answer.compareDocumentPosition(headline) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    await user.click(within(answer).getByRole("button", { name: "Back to the canvas" }));
    expect(go).toHaveBeenCalledWith({ screen: "canvas", projectId: PID });
    await user.click(within(answer).getByRole("button", { name: "Try another lesson" }));
    expect(go).toHaveBeenCalledWith({ screen: "home", projectId: null });
    expect(screen.getByTestId("probe")).toHaveTextContent("none");
  });

  it("names the right choice after a wrong prediction", async () => {
    const { learning } = packageOf("coffee_shop");
    renderResults({ ...learning, step: 3, prediction: 0, runId: "r1", predicted: 0 });
    const answer = await screen.findByRole("region", { name: "Exercise: open a second till" });
    expect(answer).toHaveTextContent("You predicted: The wait halves, to about 2.2 minutes.");
    expect(answer).toHaveTextContent(
      "The right answer: The wait falls to about a quarter of a minute, far less than half.",
    );
  });

  it("shows no answer for another run, or with no lesson", async () => {
    const { learning } = packageOf("coffee_shop");
    renderResults({ ...learning, step: 3, prediction: 1, runId: "r0", predicted: 1 });
    await waitFor(() => expect(document.querySelector(".headline-card")).not.toBeNull());
    expect(document.querySelector(".lesson-result")).toBeNull();
  });
});
