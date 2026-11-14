/**
 * The Results screen (spec 3 "Screens" 6 and "Run monitor, Results and Settings"; spec 4
 * "Findings in plain language") against a fake service.
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Project } from "../api/types";
import { SettingsProvider } from "../settings/SettingsContext";
import { FakeService, SETTINGS } from "../test/fakes";
import { readPdf } from "../test/readPdf";
import {
  aRun,
  LINE_FINDINGS,
  lineSummary,
  optionsSummary,
  planSummary,
  RID,
  SEARCH_FINDINGS,
  searchSummary,
} from "../test/runs";
import { EXPORT_WAIT, FEEDBACK_URL, fileName, ResultsScreen } from "./ResultsScreen";
import { NO_WARRANTY } from "./summary";

vi.mock("../charts/Chart", () => ({
  Chart: ({ label, option }: { label: string; option: { series: { name: string }[] } }) => (
    <div role="img" aria-label={label} data-series={option.series.map((s) => s.name).join(",")} />
  ),
  useSeriesColours: () => ({ series: ["a", "b", "c", "d"], text: "e", grid: "f" }),
}));

const saved: { blob: Blob; name: string }[] = [];
vi.mock("./save", () => ({
  saveFile: (blob: Blob, name: string) => {
    saved.push({ blob, name });
  },
}));

const PROJECT: Project = {
  id: "p1",
  name: "Line / 2",
  created: "2026-11-08T10:00:00Z",
  layout_version: 1,
  model_revision: 0,
  path: "/p1",
  available: true,
};

const REPLICATIONS = [
  { scenario: "default", replication: 0, metric: "weld.wait.mean", value: 912.4, unit: "s" },
  { scenario: "default", replication: 1, metric: "weld.wait.mean", value: null, unit: "s" },
];
const TIMESERIES = [
  {
    scenario: "default",
    replication: 0,
    metric: "weld.queue_length",
    time_s: 0,
    value: 1,
    unit: "1",
  },
  {
    scenario: "default",
    replication: 0,
    metric: "weld.utilization",
    time_s: 0,
    value: 0.5,
    unit: "1",
  },
];

function service(summary = lineSummary(), findings = LINE_FINDINGS) {
  const fake = new FakeService()
    .answer(`GET /v1/runs/${RID}`, aRun())
    .answer(`GET /v1/runs/${RID}/summary`, { summary, findings, issues: [] })
    .answer(`GET /v1/runs/${RID}/tables/replications`, REPLICATIONS)
    .answer(`GET /v1/runs/${RID}/tables/timeseries`, TIMESERIES);
  return fake;
}

/** Shows the screen at `runId`; `null` for an address that names no run. */
function show(fake: FakeService, runId: string | null = RID) {
  const go = vi.fn();
  const client = fake.client();
  const view = render(
    <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
      <ResultsScreen client={client} project={PROJECT} runId={runId ?? undefined} onGo={go} />
    </SettingsProvider>,
  );
  return { go, user: userEvent.setup(), view };
}

beforeEach(() => {
  saved.length = 0;
});
afterEach(() => {
  vi.useRealTimers();
});

describe("a run's results", () => {
  it("shows the headline, then the findings, before the key numbers, charts and tables", async () => {
    show(service());
    const card = await screen.findByText(LINE_FINDINGS[0]?.text ?? "", {
      selector: ".headline-card",
    });
    const findings = screen.getByRole("heading", { name: "Findings" });
    const firstChart = screen.getAllByRole("img")[0];
    const keyNumbers = screen.getByRole("heading", { name: "Key numbers" });
    const tables = screen.getByRole("heading", { name: "Repeat runs" });
    const order = [card, findings, keyNumbers, firstChart, tables];
    for (let index = 1; index < order.length; index += 1) {
      const earlier = order[index - 1] as Node;
      expect(
        earlier.compareDocumentPosition(order[index] as Node) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
    }
    const list = screen.getByRole("list", { name: "Findings" });
    expect(
      within(list)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual([`Bottleneck${LINE_FINDINGS[0]?.text}`, `Not enough runs${LINE_FINDINGS[1]?.text}`]);
    expect(within(list).getAllByRole("listitem")[1]).toHaveClass("finding-warning");
    const row = screen.getByRole("rowheader", { name: "weld.wait.mean" }).closest("tr");
    expect(row).toHaveTextContent("15.7 min± 2.09 min30");
    expect(
      screen.getByRole("rowheader", { name: "weld.utilization" }).closest("tr"),
    ).toHaveTextContent("90.1%± 1.1%30");
    expect(
      screen.getByRole("rowheader", { name: "model.wip.mean" }).closest("tr"),
    ).toHaveTextContent("12.4not defined30");
    expect(screen.getByRole("img", { name: /^Busy share by component/ })).toHaveAttribute(
      "data-series",
      "Busy share by component, with the likely range,Likely range",
    );
    expect(screen.getByRole("img", { name: /^Over time: weld.queue_length/ })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Every repeat run's values" })).toHaveTextContent(
      "912.4",
    );
  });

  it("carries every footer item and the feedback link, which only opens the browser", async () => {
    const { view } = show(service());
    await screen.findByRole("heading", { name: "Findings" });
    const footer = view.container.querySelector(".results-footer");
    for (const item of [
      "Model: Three-machine line",
      `Run: ${RID}`,
      "Fidelity: Standard: 30 replications of 100 h, 95% confidence",
      "Replications: 30 · Confidence: 95%",
      "Engine: simpy 4.1.2",
      NO_WARRANTY,
    ]) {
      expect(footer).toHaveTextContent(item);
    }
    const link = screen.getByRole("link", { name: "Tell us what you built (opens your browser)" });
    expect(link).toHaveAttribute("href", FEEDBACK_URL);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("says when nothing fired, and shows the thresholds' W220 issues", async () => {
    const fake = service(lineSummary(), []).answer(`GET /v1/runs/${RID}/summary`, {
      summary: lineSummary(),
      findings: [],
      issues: [
        {
          code: "W220",
          severity: "warning",
          component: null,
          path: "/finding_thresholds/bottleneck_utilization",
          message: "The threshold 'bottleneck_utilization' in settings.json is 2.",
          hint: null,
        },
      ],
    });
    show(fake);
    expect(
      await screen.findByText("No finding rule fired at the thresholds in Settings.", {
        selector: ".headline-card",
      }),
    ).toBeVisible();
    expect(
      screen.getByText("The threshold 'bottleneck_utilization' in settings.json is 2."),
    ).toBeVisible();
  });

  it("shows the bars and their table, the differences and the time series picked", async () => {
    const { user } = show(service(optionsSummary(), []));
    await screen.findByRole("heading", { name: "Differences between options" });
    const difference = screen
      .getAllByRole("rowheader", { name: "weld.wait.mean" })
      .at(-1)
      ?.closest("tr");
    expect(difference).toHaveTextContent("-5 min± 0.833 minYes");
    await user.click(
      screen.getByRole("button", { name: /^Show as table: Average wait by component/ }),
    );
    const table = screen.getByRole("table", { name: /^Average wait by component/ });
    expect(within(table).getAllByRole("row")).toHaveLength(5);
    expect(table).toHaveTextContent("weldfaster15.7± 2.09");
    await user.click(
      screen.getByRole("button", { name: /^Hide the table: Average wait by component/ }),
    );
    expect(screen.queryByRole("table", { name: /^Average wait by component/ })).toBeNull();
    await user.selectOptions(screen.getByRole("combobox", { name: "Value" }), "weld.utilization");
    expect(screen.getByRole("img", { name: /^Over time: weld.utilization/ })).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: /^Show as table: Over time: weld.utilization/ }),
    );
    expect(screen.getByRole("table", { name: /^Over time: weld.utilization/ })).toHaveTextContent(
      "050",
    );
  });

  it("shows a search's trials, the best marked, before the key numbers", async () => {
    show(service(searchSummary(), SEARCH_FINDINGS));
    const table = await screen.findByRole("table", { name: "All trials, in the order tried" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((row) => row.textContent)).toEqual([
      "0 (starting values)14.5 min± 0.45 minYesYes",
      "1 (best)214.7 s± 1.47 sYesYes",
      "231.5 s± 0.15 sNoNo",
    ]);
    expect(rows[1]).toHaveAttribute("data-selected", "true");
    expect(screen.getByRole("img", { name: /^Every trial's till.wait.mean/ })).toHaveAttribute(
      "data-series",
      "Meets every limit,Breaks a limit,Best found",
    );
    expect(screen.getByText("The best is clearly better than the next best trial.")).toBeVisible();
    expect(
      table.compareDocumentPosition(screen.getByRole("heading", { name: "Key numbers" })) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("says when a search found nothing within the limits, or cannot tell the best apart", async () => {
    const infeasible = searchSummary();
    (infeasible.search as Record<string, unknown>).status = "infeasible";
    const { view } = show(service(infeasible, []));
    expect(
      await screen.findByText("No trial checked with all repeat runs meets every limit."),
    ).toBeVisible();
    view.unmount();
    const close = searchSummary();
    (close.search as Record<string, unknown>).separated = false;
    show(service(close, []));
    expect(
      await screen.findByText("The best cannot yet be told apart from the next best trial."),
    ).toBeVisible();
  });

  it("shows an optimization's plan and limits, without simulation tables", async () => {
    const fake = service(planSummary(), []);
    show(fake);
    expect(await screen.findByRole("heading", { name: "The best plan" })).toBeVisible();
    expect(screen.getByText(/Goal:/)).toHaveTextContent("Status: optimal. Goal: 2,200.");
    expect(screen.getByRole("rowheader", { name: "chairs" }).closest("tr")).toHaveTextContent(
      "chairs24",
    );
    expect(screen.getByRole("rowheader", { name: "wood" }).closest("tr")).toHaveTextContent(
      "woodYes0",
    );
    expect(screen.queryByRole("button", { name: /CSV/ })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Repeat runs" })).toBeNull();
    expect(fake.requested("GET", `/v1/runs/${RID}/tables/replications`)).toHaveLength(0);
    expect(document.querySelector(".results-footer")).toHaveTextContent(
      "Replications and confidence: not replicated",
    );
  });

  it("shows an empty plan and a table that cannot be read", async () => {
    const fake = service({ model: "Empty", status: "infeasible", objective: null }, []).answer(
      `GET /v1/runs/${RID}/tables/timeseries`,
      {
        error: { code: "E185", message: "The run has no readable table 'timeseries'." },
        issues: [],
      },
      404,
    );
    show(fake);
    expect(await screen.findByText("The best plan")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Decisions" })).toBeNull();
    expect(screen.getByText(/Goal:/)).toHaveTextContent("Goal: not defined.");
  });

  it("shows a simulation table the service refused", async () => {
    show(
      service().answer(
        `GET /v1/runs/${RID}/tables/timeseries`,
        {
          error: { code: "E185", message: "The run has no readable table 'timeseries'." },
          issues: [],
        },
        404,
      ),
    );
    expect(await screen.findByText("The run has no readable table 'timeseries'.")).toBeVisible();
    expect(screen.queryByRole("img", { name: /^Over time/ })).toBeNull();
  });
});

describe("which run", () => {
  it("shows the project's most recent done run when the address names none", async () => {
    const fake = service().answer("GET /v1/projects/p1/runs", [
      aRun({ run_id: "20261108T090000-AAAAAA" }),
      aRun(),
      aRun({ run_id: "20261108T110000-BBBBBB", state: "running" }),
    ]);
    show(fake, null);
    expect(await screen.findByRole("heading", { name: "Findings" })).toBeVisible();
    expect(fake.requested("GET", `/v1/runs/${RID}/summary`)).toHaveLength(1);
  });

  it("says when no run is done, and when the list or the run cannot be read", async () => {
    const fake = new FakeService().answer("GET /v1/projects/p1/runs", [aRun({ state: "running" })]);
    const { go, user, view } = show(fake, null);
    expect(await screen.findByText("No run of this project is done yet.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Open the Run monitor" }));
    expect(go).toHaveBeenCalledWith({ screen: "monitor", projectId: "p1" });
    view.unmount();
    const refused = new FakeService().answer(
      "GET /v1/projects/p1/runs",
      { error: { code: "E186", message: "The project cannot be used." }, issues: [] },
      400,
    );
    const second = show(refused, null);
    expect(await screen.findByText("The project cannot be used.")).toBeVisible();
    second.view.unmount();
    show(new FakeService(), "20261108T000000-ZZZZZZ");
    expect(
      await screen.findByText("The service has no '/v1/runs/20261108T000000-ZZZZZZ'."),
    ).toBeVisible();
  });

  it("says a run that is not done yet has no results, with a way to the monitor", async () => {
    const fake = new FakeService().answer(`GET /v1/runs/${RID}`, aRun({ state: "running" }));
    const { go, user } = show(fake);
    expect(
      await screen.findByText(/is running; its results are written when it is done/),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Open the Run monitor" }));
    expect(go).toHaveBeenCalledWith({ screen: "monitor", projectId: "p1", runId: RID });
    expect(fake.requested("GET", `/v1/runs/${RID}/summary`)).toHaveLength(0);
  });

  it("shows the service's refusal of the summary", async () => {
    show(
      service().answer(
        `GET /v1/runs/${RID}/summary`,
        {
          error: { code: "E185", message: "The summary.json of the run cannot be read." },
          issues: [],
        },
        404,
      ),
    );
    expect(await screen.findByText("The summary.json of the run cannot be read.")).toBeVisible();
  });

  it("drops a run's answers once the screen shows another", async () => {
    const fake = service();
    const go = vi.fn();
    const client = fake.client();
    const { rerender } = render(
      <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
        <ResultsScreen client={client} project={PROJECT} runId={RID} onGo={go} />
      </SettingsProvider>,
    );
    rerender(
      <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
        <ResultsScreen client={client} project={null} runId={RID} onGo={go} />
      </SettingsProvider>,
    );
    expect(await screen.findByText("Opening the project…")).toBeVisible();
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    expect(screen.queryByRole("heading", { name: "Findings" })).toBeNull();
  });
});

describe("exports", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  it("saves each table as CSV, the PDF with its footer and the project zip", async () => {
    const fake = service();
    fake.on(`GET /v1/runs/${RID}/tables/replications`, (_, url) =>
      url.search === "?format=csv"
        ? { status: 200, body: "scenario,replication\r\n" }
        : { status: 200, body: REPLICATIONS },
    );
    fake.on("GET /v1/projects/p1/export", () => ({ status: 200, body: "zip bytes" }));
    const { user } = show(fake);
    await user.click(await screen.findByRole("button", { name: "Export repeat runs (CSV)" }));
    await waitFor(() =>
      expect(saved.map((file) => file.name)).toEqual([`${RID}-replications.csv`]),
    );
    expect(fake.requests.at(-1)?.search).toBe("?format=csv");
    await user.click(screen.getByRole("button", { name: "Export PDF" }));
    await waitFor(() => expect(saved).toHaveLength(2));
    expect(saved[1]?.name).toBe(`${RID}.pdf`);
    const pdfBlob = saved[1]?.blob;
    if (pdfBlob === undefined) throw new Error("no PDF");
    const pages = await readPdf(new Uint8Array(await pdfBlob.arrayBuffer()));
    for (const page of pages) {
      for (const item of [
        "Model: Three-machine line",
        `Run: ${RID}`,
        "Engine: simpy 4.1.2",
        NO_WARRANTY,
      ]) {
        expect(page.text).toContain(item);
      }
    }
    expect(pages[0]?.text).toContain(LINE_FINDINGS[0]?.text);
    await user.click(screen.getByRole("button", { name: "Export project (zip)" }));
    await waitFor(() => expect(saved).toHaveLength(3));
    expect(saved[2]?.name).toBe("Line _ 2.zip");
    expect(fake.requested("GET", "/v1/projects/p1/export")).toHaveLength(1);
  });

  it("makes one export at a time and says so; shows a refused one", async () => {
    const fake = service();
    let answer: (() => void) | null = null;
    const original = fake.fetch;
    const held = async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).includes("format=csv"))
        await new Promise<void>((resolve) => (answer = resolve));
      return original(input, init);
    };
    fake.on(`GET /v1/runs/${RID}/tables/timeseries`, (_, url) =>
      url.search === "?format=csv"
        ? { status: 404, body: { error: { code: "E185", message: "No table." }, issues: [] } }
        : { status: 200, body: TIMESERIES },
    );
    const client = new (await import("../api/client")).ApiClient({
      origin: "http://127.0.0.1:8765",
      token: "t",
      fetch: held as typeof fetch,
    });
    render(
      <SettingsProvider client={client} initial={SETTINGS} root={document.documentElement}>
        <ResultsScreen client={client} project={PROJECT} runId={RID} onGo={vi.fn()} />
      </SettingsProvider>,
    );
    const user = userEvent.setup();
    const csv = await screen.findByRole("button", { name: "Export values over time (CSV)" });
    await user.click(csv);
    await waitFor(() => expect(answer).not.toBeNull());
    expect(csv).toHaveAttribute("aria-disabled", "true");
    await user.click(screen.getByRole("button", { name: "Export PDF" }));
    expect(screen.getByText(EXPORT_WAIT)).toBeVisible();
    expect(saved).toHaveLength(0);
    (answer as unknown as () => void)();
    expect(await screen.findByText("No table.")).toBeVisible();
  });

  it("names the zip after the project, or 'project'", () => {
    expect(fileName({ ...PROJECT, name: "Café: line" })).toBe("Caf__ line");
    expect(fileName({ ...PROJECT, name: null })).toBe("project");
  });
});
