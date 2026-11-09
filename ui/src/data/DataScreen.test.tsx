/**
 * The Data screen (spec 3 "Screens" 3; flows B5b to B7b; `03-data.svg`) against the fake
 * service: import, units, removal, the fit with its histogram and table, and "Use for" with
 * the waiting question, under the Canvas's rules. The chart itself is ECharts, drawn in the
 * end-to-end test; here it is a stand-in that shows its name and option.
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ComponentType, DataFile, FitBody, Model, Project } from "../api/types";
import { WAIT_MODEL } from "../canvas/ModelFrame";
import { SettingsProvider } from "../settings/SettingsContext";
import componentTypeFixture from "../test/component-types.json";
import { coffeeShop, ModelService, PID } from "../test/fakeModel";
import { errorBody, FakeService, issue, SETTINGS } from "../test/fakes";
import { DataScreen, targetsOf, usedValue, WAITING_QUESTION, WAITING_WARNING } from "./DataScreen";

const componentTypes = componentTypeFixture as unknown as Record<string, ComponentType>;

vi.mock("../charts/Chart", () => ({
  Chart: ({ label, option }: { label: string; option: { series: { name: string }[] } }) => (
    <div role="img" aria-label={label} data-series={option.series.map((s) => s.name).join(",")} />
  ),
  useChartColours: () => ({ bars: "a", curve: "b", text: "c", grid: "d" }),
}));

const PROJECT: Project = {
  id: PID,
  name: "Coffee shop",
  created: "2026-11-08T10:00:00Z",
  layout_version: 1,
  model_revision: 0,
  path: "/p1",
  available: true,
};
const DATA = `/v1/projects/${PID}/data`;
const EDITS = `/v1/projects/${PID}/model/edits`;

function entry(name: string, unit: string | null = null, sha256 = "a".repeat(64)): DataFile {
  return {
    name,
    format: "csv",
    sheet: null,
    size: 40,
    sha256,
    imported: "2026-11-08T10:00:00.000Z",
    rows: 3,
    columns: [
      { name: "day", type: "text", unit: null, largest: null },
      { name: "minutes", type: "number", unit, largest: 3 },
    ],
  };
}

const FIT: FitBody = {
  file: "times.csv",
  column: "minutes",
  unit: "min",
  values: 3,
  score: "ks",
  candidates: [
    { distribution: { dist: "exponential", mean: "2.0 min" }, score: 0.12 },
    { distribution: { dist: "normal", mean: "2.0 min", sd: "1.0 min" }, score: 0.2 },
  ],
  histogram: { edges: [1, 2, 3], counts: [2, 1] },
};

function renderScreen(options: { files?: DataFile[]; model?: Model } = {}) {
  const fake = new FakeService();
  const service = new ModelService(fake, { model: options.model ?? coffeeShop(), revision: 1 });
  let files = options.files ?? [];
  const units: (string | null)[] = [];
  fake
    .on(`GET ${DATA}`, () => ({ status: 200, body: files }))
    .on(`POST ${DATA}`, (body) => {
      const form = body as FormData;
      const file = form.get("file") as File;
      units.push((form.get("units") as string | null) ?? null);
      const declared = JSON.parse((form.get("units") as string | null) ?? "{}") as Record<
        string,
        string | null
      >;
      const made = entry(file.name, declared.minutes ?? null, "b".repeat(64));
      files = [...files.filter((item) => item.name !== made.name), made];
      return {
        status: 200,
        body: {
          ...made,
          preview: [
            ["Mon", 1],
            ["Tue", 3],
            [null, 2],
          ],
        },
      };
    })
    .on(`DELETE ${DATA}/times.csv`, () => {
      files = files.filter((item) => item.name !== "times.csv");
      return { status: 200, body: files };
    })
    .on(`POST ${DATA}/times.csv/fit`, () => ({ status: 200, body: FIT }));
  const go = vi.fn();
  const client = fake.client();
  const toolbar = document.createElement("div");
  document.body.append(toolbar);
  render(
    <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
      <DataScreen client={client} project={PROJECT} toolbar={toolbar} onGo={go} />
    </SettingsProvider>,
  );
  return { fake, service, go, toolbar, units, user: userEvent.setup({ applyAccept: false }) };
}

async function settled(toolbar: HTMLElement) {
  await waitFor(() => expect(within(toolbar).getByRole("status")).toHaveTextContent("Saved"));
}

const csv = () => new File(["day,minutes\nMon,1\nTue,3\n,2\n"], "times.csv", { type: "text/csv" });

async function importFile(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText("Import CSV or Excel"), csv());
  await screen.findByRole("heading", { name: "times.csv" });
}

describe("files", () => {
  it("imports a picked file, shows its columns and first rows, and lists it", async () => {
    const { fake, toolbar, user } = renderScreen();
    expect(await screen.findByText("No files imported yet.")).toBeVisible();
    await settled(toolbar);
    await importFile(user);
    const form = fake.requested("POST", DATA)[0]?.body as FormData;
    expect((form.get("file") as File).name).toBe("times.csv");
    expect(form.has("units")).toBe(false);
    expect(screen.getByRole("rowheader", { name: "minutes" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "Mon" })).toBeVisible();
    expect(screen.getByRole("button", { name: /times\.csv 2 columns · 3 rows/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    // Validation is asked again: a data reference may now be met.
    await waitFor(() =>
      expect(fake.requested("POST", `/v1/projects/${PID}/validate`).length).toBeGreaterThan(1),
    );
  });

  it("imports the file again with the unit chosen for a number column", async () => {
    const { fake, units, user } = renderScreen();
    await screen.findByText("No files imported yet.");
    await importFile(user);
    await user.selectOptions(screen.getByRole("combobox", { name: "Unit of minutes" }), "min");
    await waitFor(() => expect(fake.requested("POST", DATA)).toHaveLength(2));
    expect(units).toEqual([null, '{"minutes":"min"}']);
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Unit of minutes" })).toHaveValue("min"),
    );
  });

  it("asks for the file again to change a unit of a file imported elsewhere", async () => {
    const { fake, user } = renderScreen({ files: [entry("times.csv")] });
    await screen.findByRole("heading", { name: "times.csv" });
    expect(screen.getByText(/The first rows are shown after the file is imported/)).toBeVisible();
    await user.selectOptions(screen.getByRole("combobox", { name: "Unit of minutes" }), "h");
    expect(
      screen.getByText("To change a unit, import times.csv again in this window first."),
    ).toBeVisible();
    expect(fake.requested("POST", DATA)).toHaveLength(0);
    expect(screen.getByRole("combobox", { name: "Unit of minutes" })).toHaveValue("");
  });

  it("shows the service's refusal of a file as its issue", async () => {
    const { fake, user } = renderScreen();
    await screen.findByText("No files imported yet.");
    fake.answer(
      `POST ${DATA}`,
      errorBody("E189", "Row 2 has a cell beyond the header.", [
        issue("E189", "Row 2 has a cell beyond the header.", "/file"),
      ]),
      400,
    );
    await user.upload(screen.getByLabelText("Import CSV or Excel"), csv());
    expect(await screen.findByRole("alert")).toHaveTextContent("E189");
    expect(screen.getByText("Row 2 has a cell beyond the header.")).toBeVisible();
    expect(screen.getByText("No files imported yet.")).toBeVisible();
  });

  it("shows why the files cannot be listed", async () => {
    const fake = new FakeService();
    new ModelService(fake, { model: coffeeShop(), revision: 1 });
    fake.answer(`GET ${DATA}`, errorBody("E186", "The project cannot be read.", []), 400);
    const client = fake.client();
    render(
      <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
        <DataScreen client={client} project={PROJECT} toolbar={null} onGo={vi.fn()} />
      </SettingsProvider>,
    );
    expect(await screen.findByText("The project cannot be read.")).toBeVisible();
  });

  it("removes a file after asking, and Cancel keeps it", async () => {
    const { fake, user } = renderScreen({ files: [entry("times.csv")] });
    await screen.findByRole("heading", { name: "times.csv" });
    await user.click(screen.getByRole("button", { name: "Remove times.csv" }));
    const dialog = screen.getByRole("dialog", { name: "Remove times.csv?" });
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(fake.requested("DELETE", `${DATA}/times.csv`)).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Remove times.csv" }));
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(await screen.findByText("No files imported yet.")).toBeVisible();
    expect(fake.requested("DELETE", `${DATA}/times.csv`)).toHaveLength(1);
  });
});

describe("the fit", () => {
  it("lists the candidates best first and draws the histogram, with a table of it", async () => {
    const { fake, user } = renderScreen({ files: [entry("times.csv", "min")] });
    await screen.findByRole("heading", { name: "times.csv" });
    // The first number column is chosen.
    expect(screen.getByRole("radio", { name: "Fit minutes" })).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Fit a distribution" }));
    expect(await screen.findByRole("rowheader", { name: "exponential" })).toBeVisible();
    expect(fake.requested("POST", `${DATA}/times.csv/fit`)[0]?.body).toEqual({
      column: "minutes",
    });
    expect(screen.getByRole("cell", { name: "0.120 (best)" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "How well it fits" })).toHaveAttribute(
      "title",
      expect.stringContaining("Kolmogorov"),
    );
    const chart = screen.getByRole("img", {
      name: /^Histogram of minutes with the fitted exponential/,
    });
    expect(chart).toHaveAttribute("data-series", "Your data,Fitted exponential");
    await user.click(screen.getByRole("button", { name: "Show as table" }));
    const table = screen.getByRole("table", {
      name: "The histogram of minutes and the fitted exponential",
    });
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getByRole("columnheader", { name: "From (min)" })).toBeVisible();
    // Choosing another candidate draws its curve.
    await user.click(screen.getByRole("radio", { name: "Choose normal" }));
    expect(screen.getByRole("img", { name: /fitted normal/ })).toBeVisible();
  });

  it("drops a fit when the unit changes, until the column is fitted again", async () => {
    const { fake, user } = renderScreen();
    await screen.findByText("No files imported yet.");
    await importFile(user);
    await user.selectOptions(screen.getByRole("combobox", { name: "Unit of minutes" }), "min");
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Unit of minutes" })).toHaveValue("min"),
    );
    await user.click(screen.getByRole("button", { name: "Fit a distribution" }));
    expect(await screen.findByRole("rowheader", { name: "exponential" })).toBeVisible();
    // The same bytes imported again in seconds: the hash is unchanged, the fit is not valid.
    await user.selectOptions(screen.getByRole("combobox", { name: "Unit of minutes" }), "s");
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Unit of minutes" })).toHaveValue("s"),
    );
    expect(screen.queryByRole("rowheader", { name: "exponential" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Use for" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Use it" })).toBeNull();
    expect(fake.requested("POST", `${DATA}/times.csv/fit`)).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Fit a distribution" }));
    expect(await screen.findByRole("rowheader", { name: "exponential" })).toBeVisible();
  });

  it("shows the service's refusal of a fit, such as a column of text", async () => {
    const { fake, user } = renderScreen({ files: [entry("times.csv")] });
    await screen.findByRole("heading", { name: "times.csv" });
    fake.answer(
      `POST ${DATA}/times.csv/fit`,
      errorBody("E189", "The column 'day' of 'times.csv' holds text.", [
        issue("E189", "The column 'day' of 'times.csv' holds text.", "/column"),
      ]),
      400,
    );
    await user.click(screen.getByRole("radio", { name: "Fit day" }));
    await user.click(screen.getByRole("button", { name: "Fit a distribution" }));
    expect(await screen.findByText("The column 'day' of 'times.csv' holds text.")).toBeVisible();
    expect(screen.queryByRole("img", { name: /Histogram/ })).toBeNull();
  });
});

describe("Use for", () => {
  async function fitted() {
    const rendered = renderScreen({ files: [entry("times.csv", "min")] });
    await screen.findByRole("heading", { name: "times.csv" });
    await settled(rendered.toolbar);
    await rendered.user.click(screen.getByRole("button", { name: "Fit a distribution" }));
    await screen.findByRole("rowheader", { name: "exponential" });
    return rendered;
  }

  it("lists every distribution setting of the model's blocks", () => {
    const model = coffeeShop();
    model.components?.push({ id: "fix", type: "failure", params: {} });
    expect(targetsOf(model, componentTypes).map((item) => [item.key, item.work])).toEqual([
      ["arrivals/interarrival", false],
      ["till/service", true],
      ["fix/time_to_failure", false],
      ["fix/time_to_repair", false],
    ]);
    expect(usedValue("data", FIT, null)).toEqual({
      dist: "empirical",
      data: { file: "times.csv", column: "minutes" },
    });
    expect(usedValue("fitted", FIT, null)).toBeNull();
  });

  it("sets an interarrival time to the candidate, with no question", async () => {
    const { fake, service, toolbar, user } = await fitted();
    const use = screen.getByRole("button", { name: "Use it" });
    expect(use).toHaveAttribute("aria-disabled", "true");
    expect(use).toHaveAccessibleDescription("Choose a block setting first.");
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Block setting" }),
      "arrivals/interarrival",
    );
    expect(screen.queryByText(WAITING_QUESTION)).toBeNull();
    await user.click(screen.getByRole("button", { name: "Use it" }));
    await settled(toolbar);
    expect(fake.requested("POST", EDITS).at(-1)?.body).toMatchObject({
      edits: [
        {
          edit: "set_setting",
          id: "arrivals",
          path: "/interarrival",
          value: { dist: "exponential", mean: "2.0 min" },
        },
      ],
    });
    expect(service.component("arrivals")?.params.interarrival).toEqual({
      dist: "exponential",
      mean: "2.0 min",
    });
    expect(
      screen.getByText("arrivals interarrival is now exponential, mean 2.0 min."),
    ).toBeVisible();
    // The form went with the model it was filled against.
    expect(screen.getByRole("combobox", { name: "Block setting" })).toHaveValue("");
  });

  it("asks whether a service time includes waiting before setting it", async () => {
    const { fake, service, toolbar, user } = await fitted();
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Block setting" }),
      "till/service",
    );
    expect(screen.getByText(WAITING_QUESTION)).toBeVisible();
    expect(screen.getByRole("button", { name: "Use it" })).toHaveAccessibleDescription(
      "Answer the question about waiting first.",
    );
    await user.click(screen.getByRole("button", { name: "Use it" }));
    expect(fake.requested("POST", EDITS)).toHaveLength(0);
    await user.click(screen.getByRole("radio", { name: "Yes" }));
    expect(screen.getByRole("alert")).toHaveTextContent(WAITING_WARNING);
    await user.click(screen.getByRole("radio", { name: "Not sure" }));
    expect(screen.getByRole("alert")).toHaveTextContent(WAITING_WARNING);
    // The column itself, as it is.
    await user.click(screen.getByRole("radio", { name: /Use the data as it is/ }));
    await user.click(screen.getByRole("button", { name: "Use it anyway" }));
    await settled(toolbar);
    expect(service.component("till")?.params.service).toEqual({
      dist: "empirical",
      data: { file: "times.csv", column: "minutes" },
    });
    expect(screen.getByText("till service now uses the data of minutes as it is.")).toBeVisible();
    // No: set at once with "Use it".
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Block setting" }),
      "till/service",
    );
    await user.click(screen.getByRole("radio", { name: "No" }));
    expect(screen.queryByRole("alert")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Use it" }));
    await settled(toolbar);
    expect(service.component("till")?.params.service).toEqual({
      dist: "exponential",
      mean: "2.0 min",
    });
    // Cancel clears the form.
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Block setting" }),
      "till/service",
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText(WAITING_QUESTION)).toBeNull();
  });

  it("shows the service's issues of the setting it set", async () => {
    const rendered = renderScreen({ files: [entry("times.csv", "min")] });
    await screen.findByRole("heading", { name: "times.csv" });
    rendered.service.validateIssues = (model) =>
      JSON.stringify(model).includes("empirical")
        ? [
            issue(
              "E162",
              "The column has no unit.",
              "/components/0/params/interarrival/data/column",
            ),
          ]
        : [];
    await settled(rendered.toolbar);
    await rendered.user.click(screen.getByRole("button", { name: "Fit a distribution" }));
    await screen.findByRole("rowheader", { name: "exponential" });
    await rendered.user.selectOptions(
      screen.getByRole("combobox", { name: "Block setting" }),
      "arrivals/interarrival",
    );
    await rendered.user.click(screen.getByRole("radio", { name: /Use the data as it is/ }));
    await rendered.user.click(screen.getByRole("button", { name: "Use it" }));
    expect(await screen.findByText("The column has no unit.")).toBeVisible();
  });

  it("is refused while a write awaits its answer, and goes with an outside change", async () => {
    const { fake, service, toolbar, user } = await fitted();
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Block setting" }),
      "arrivals/interarrival",
    );
    const release = fake.holdWrites();
    await user.click(screen.getByRole("button", { name: "Use it" }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Block setting" }),
      "till/service",
    );
    await user.click(screen.getByRole("radio", { name: "No" }));
    await user.click(screen.getByRole("button", { name: "Use it" }));
    expect(screen.getByText(WAIT_MODEL)).toBeVisible();
    release();
    await settled(toolbar);
    expect(fake.requested("POST", EDITS)).toHaveLength(1);
    // Another client's write: the form's draft goes, and the change is listed.
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Block setting" }),
      "till/service",
    );
    service.outsideWrite((model) => {
      model.components = model.components?.filter((item) => item.id !== "exit");
    });
    act(() =>
      fake.sockets[0]?.emit({ type: "model", revision: service.revision, client: "script" }),
    );
    expect(await screen.findByText(/The model was changed by a script \(script\)/)).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Block setting" })).toHaveValue("");
    expect(screen.getByRole("region", { name: "1 change to review" })).toBeVisible();
  });

  it("goes to the canvas, and says when the model has no time to set", async () => {
    const model = coffeeShop();
    model.components = [];
    const { go, user } = renderScreen({ files: [entry("times.csv", "min")], model });
    await screen.findByRole("heading", { name: "times.csv" });
    await user.click(screen.getByRole("button", { name: "Fit a distribution" }));
    expect(await screen.findByText(/The model has no block with a time to set/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Go to the canvas" }));
    expect(go).toHaveBeenCalledWith({ screen: "canvas", projectId: PID });
  });
});
