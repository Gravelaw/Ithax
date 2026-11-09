import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Project } from "../api/types";
import { errorBody, FakeService } from "../test/fakes";
import {
  ANSWERS,
  BUILD_TEMPLATES,
  BuildForm,
  NEED_ANSWER,
  NEED_DATA,
  NEED_NAME,
  NEED_SECOND,
  NOT_INSTALLED,
} from "./BuildForm";

const TITLES: Record<string, string> = {
  coffee_shop: "Coffee shop queue",
  three_machine_line: "Three-machine production line",
  machine_breakdowns: "Machine breakdowns",
  how_many_machines: "How many machines?",
  inventory_reorder_point: "Inventory reorder point",
  product_mix: "Product mix",
  transport_plan: "Transport plan",
  staff_rota: "Staff rota",
  clinic_patient_flow: "Clinic patient flow",
  warehouse_pick_pack: "Warehouse pick and pack",
};

function made(name: string): Project {
  return {
    id: "new",
    name,
    created: "2026-11-09T10:00:00Z",
    layout_version: 1,
    model_revision: 0,
    path: "/data/projects/new",
    available: true,
  };
}

function setup(served: string[] = Object.keys(TITLES)) {
  const fake = new FakeService()
    .answer(
      "GET /v1/templates",
      served.map((id) => ({ id, title: TITLES[id] })),
    )
    .on("POST /v1/projects", (body) => ({
      status: 200,
      body: made((body as { name: string }).name),
    }));
  const onCreated = vi.fn();
  const onBack = vi.fn();
  render(<BuildForm client={fake.client()} onCreated={onCreated} onBack={onBack} />);
  return { fake, onCreated, onBack, user: userEvent.setup() };
}

function group(name: string | RegExp): HTMLElement {
  return screen.getByRole("group", { name });
}

describe("the Build form", () => {
  it("asks spec 4's six answers, each with the template it opens, nothing preselected", async () => {
    setup();
    expect(screen.getByRole("heading", { name: "Build a model" })).toHaveFocus();
    const first = group("Step 1 of 2: What do you want to find out?");
    await within(first).findByText("Opens: Coffee shop queue");
    const radios = within(first).getAllByRole("radio");
    expect(radios.map((radio) => radio.closest("label")?.textContent)).toEqual([
      "How long will people or items wait?Opens: Coffee shop queue",
      "Where is the bottleneck?Opens: Three-machine production line",
      "How much does downtime cost?Opens: Machine breakdowns",
      "How many staff or machines do I need?Opens: How many machines?",
      "How much stock should I hold?Opens: Inventory reorder point",
      "What mix, plan or rota is best?Asks one more question",
    ]);
    for (const radio of radios) expect(radio).not.toBeChecked();
    const data = group("Step 2 of 2: Do you have data?");
    expect(
      within(data)
        .getAllByRole("radio")
        .map((radio) => radio.closest("label")?.textContent),
    ).toEqual([
      "Yes, import a fileOpens the Data screen (CSV or Excel)",
      "No, I will estimateOpens the canvas with the parameters",
    ]);
    expect(screen.queryByRole("group", { name: "Which of these?" })).toBeNull();
    expect(screen.getByText("Build mode never requires a data file.")).toBeVisible();
  });

  it("maps each answer to spec 4's template, the last by a second question", () => {
    expect(ANSWERS.map((item) => [item.answer, item.template ?? null])).toEqual([
      ["How long will people or items wait?", "coffee_shop"],
      ["Where is the bottleneck?", "three_machine_line"],
      ["How much does downtime cost?", "machine_breakdowns"],
      ["How many staff or machines do I need?", "how_many_machines"],
      ["How much stock should I hold?", "inventory_reorder_point"],
      ["What mix, plan or rota is best?", null],
    ]);
    expect(ANSWERS[5]?.second?.map((item) => [item.answer, item.template])).toEqual([
      ["A product mix", "product_mix"],
      ["A transport plan", "transport_plan"],
      ["A staff rota", "staff_rota"],
    ]);
    expect(BUILD_TEMPLATES).toEqual([
      "coffee_shop",
      "three_machine_line",
      "machine_breakdowns",
      "how_many_machines",
      "inventory_reorder_point",
      "product_mix",
      "transport_plan",
      "staff_rota",
    ]);
  });

  it("says what is missing until every question is answered", async () => {
    const { user, fake } = setup();
    const go = screen.getByRole("button", { name: "Continue" });
    expect(go).toHaveAttribute("aria-disabled", "true");
    expect(go).toHaveAccessibleDescription(NEED_ANSWER);
    await user.click(
      await screen.findByRole("radio", { name: /What mix, plan or rota is best\?/ }),
    );
    expect(go).toHaveAccessibleDescription(NEED_SECOND);
    const second = group("Which of these?");
    expect(
      within(second)
        .getAllByRole("radio")
        .map((radio) => radio.closest("label")?.textContent),
    ).toEqual([
      "A product mixOpens: Product mix",
      "A transport planOpens: Transport plan",
      "A staff rotaOpens: Staff rota",
    ]);
    await user.click(within(second).getByRole("radio", { name: /A staff rota/ }));
    expect(go).toHaveAccessibleDescription(NEED_DATA);
    await user.click(screen.getByRole("radio", { name: /No, I will estimate/ }));
    // The name starts as the template's title; emptied, Continue says so.
    const name = screen.getByRole("textbox", { name: "Project name" });
    expect(name).toHaveValue("Staff rota");
    expect(go).not.toHaveAttribute("aria-disabled");
    await user.clear(name);
    expect(go).toHaveAccessibleDescription(NEED_NAME);
    await user.click(go);
    expect(fake.requested("POST", "/v1/projects")).toHaveLength(0);
    // Another first answer forgets the second.
    await user.click(screen.getByRole("radio", { name: /Where is the bottleneck\?/ }));
    expect(screen.queryByRole("group", { name: "Which of these?" })).toBeNull();
  });

  it("creates the project from the template, and opens the Canvas without data", async () => {
    const { user, fake, onCreated } = setup();
    await user.click(
      await screen.findByRole("radio", { name: /How long will people or items wait\?/ }),
    );
    await user.click(screen.getByRole("radio", { name: /No, I will estimate/ }));
    expect(screen.getByRole("textbox", { name: "Project name" })).toHaveValue("Coffee shop queue");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(made("Coffee shop queue"), false));
    expect(fake.requested("POST", "/v1/projects")[0]?.body).toEqual({
      name: "Coffee shop queue",
      template: "coffee_shop",
    });
  });

  it("opens the Data screen with data, under the name typed", async () => {
    const { user, fake, onCreated } = setup();
    await user.click(await screen.findByRole("radio", { name: /What mix, plan or rota/ }));
    await user.click(screen.getByRole("radio", { name: /A transport plan/ }));
    await user.click(screen.getByRole("radio", { name: /Yes, import a file/ }));
    const name = screen.getByRole("textbox", { name: "Project name" });
    await user.clear(name);
    await user.type(name, "Depots");
    // Choosing another template keeps the name typed.
    await user.click(screen.getByRole("radio", { name: /A product mix/ }));
    expect(name).toHaveValue("Depots");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(made("Depots"), true));
    expect(fake.requested("POST", "/v1/projects")[0]?.body).toEqual({
      name: "Depots",
      template: "product_mix",
    });
  });

  it("shows the service's refusal and keeps the answers; sends one creation at a time", async () => {
    const { user, fake, onCreated } = setup();
    fake.answer("POST /v1/projects", errorBody("E186", "The folder cannot be written."), 400);
    await user.click(await screen.findByRole("radio", { name: /How much stock should I hold\?/ }));
    await user.click(screen.getByRole("radio", { name: /No, I will estimate/ }));
    const release = fake.holdWrites();
    const go = screen.getByRole("button", { name: "Continue" });
    await user.click(go);
    await waitFor(() => expect(fake.held).toBe(1));
    expect(go).toHaveAttribute("aria-disabled", "true");
    expect(go).toHaveTextContent("Creating…");
    await user.click(go);
    release();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "E186 The folder cannot be written.",
    );
    expect(fake.requested("POST", "/v1/projects")).toHaveLength(1);
    expect(onCreated).not.toHaveBeenCalled();
    expect(screen.getByRole("radio", { name: /How much stock should I hold\?/ })).toBeChecked();
  });

  it("shows an answer whose template is not served as unavailable", async () => {
    const { user } = setup(["coffee_shop", "product_mix"]);
    const line = await screen.findByRole("radio", { name: /Where is the bottleneck\?/ });
    expect(line).toBeDisabled();
    expect(line.closest("label")).toHaveTextContent(NOT_INSTALLED);
    await user.click(screen.getByRole("radio", { name: /What mix, plan or rota/ }));
    expect(screen.getByRole("radio", { name: /A staff rota/ })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /A product mix/ })).toBeEnabled();
  });

  it("shows the service's problem when the templates cannot be listed, and goes back", async () => {
    const fake = new FakeService().on("GET /v1/templates", () => "unreachable");
    const onBack = vi.fn();
    render(<BuildForm client={fake.client()} onCreated={() => {}} onBack={onBack} />);
    expect(await screen.findByText("Lost contact with the engine service.")).toBeVisible();
    // Without the list, no answer is called not installed: the service judges the template.
    expect(screen.queryByText(NOT_INSTALLED)).toBeNull();
    expect(screen.getByRole("radio", { name: /Where is the bottleneck\?/ })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
